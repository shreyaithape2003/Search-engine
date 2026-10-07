from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.indexing.indexer import DocumentIndexer
from app.indexing.repository import IndexRepository
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'indexer.db').as_posix()}"
    )
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Iterator[Session]:
    initialize_database(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


def create_document(
    repository: DocumentRepository,
    url: str,
    **fields: Any,
) -> Document:
    return repository.create(DocumentCreate(url=url, **fields))


def test_indexes_documents_by_term_and_field_with_frequencies(
    session: Session,
) -> None:
    documents = DocumentRepository(session)
    index_repository = IndexRepository(session)
    indexer = DocumentIndexer(index_repository)
    first = create_document(
        documents,
        "https://one.edu/",
        title="Python Programming",
        description="A programming course",
        headings=["Variables", "Python Functions"],
        body="Python is a programming language.",
    )
    second = create_document(
        documents,
        "https://two.edu/",
        title="Machine Learning",
        body="Python can be used for machine learning.",
    )

    indexer.index_document(first)
    indexer.index_document(second)

    python_postings = index_repository.get_postings_for_term("PYTHON")
    assert [
        (posting.document_id, posting.field, posting.term_frequency)
        for posting in python_postings
    ] == [
        (first.id, "body", 1),
        (first.id, "headings", 1),
        (first.id, "title", 1),
        (second.id, "body", 1),
    ]

    title_programming = [
        posting
        for posting in index_repository.get_postings_for_term("programming")
        if posting.document_id == first.id and posting.field == "title"
    ]
    assert title_programming[0].term_frequency == 1
    assert title_programming[0].positions == [1]
    assert index_repository.get_term_statistics("python").document_frequency == 2


def test_indexing_same_document_twice_does_not_duplicate_postings(
    session: Session,
) -> None:
    document = create_document(
        DocumentRepository(session),
        "https://repeat.edu/",
        title="Python Python programming",
    )
    repository = IndexRepository(session)
    indexer = DocumentIndexer(repository)

    indexer.index_document(document)
    first_snapshot = [
        (p.term, p.field, p.term_frequency, p.positions)
        for p in repository.get_postings_for_term("python")
    ]
    indexer.index_document(document)
    second_snapshot = [
        (p.term, p.field, p.term_frequency, p.positions)
        for p in repository.get_postings_for_term("python")
    ]

    assert first_snapshot == second_snapshot == [
        ("python", "title", 2, [0, 1])
    ]
    assert repository.get_document_statistics(document.id) == {
        "body": 0,
        "description": 0,
        "headings": 0,
        "title": 3,
    }


def test_reindexing_replaces_stale_terms_and_field_statistics(
    session: Session,
) -> None:
    documents = DocumentRepository(session)
    document = create_document(
        documents,
        "https://update.edu/",
        title="Python programming",
        body="Python tutorial",
    )
    repository = IndexRepository(session)
    indexer = DocumentIndexer(repository)
    indexer.index_document(document)

    changed = documents.update(
        document.id,
        DocumentUpdate(title="Java programming", body="Java reference"),
    )
    assert changed is not None
    indexer.index_document(changed)

    assert repository.get_postings_for_term("python") == []
    assert {
        (posting.document_id, posting.field, posting.term_frequency)
        for posting in repository.get_postings_for_term("java")
    } == {
        (document.id, "title", 1),
        (document.id, "body", 1),
    }
    assert repository.get_document_statistics(document.id) == {
        "body": 2,
        "description": 0,
        "headings": 0,
        "title": 2,
    }


def test_only_persisted_documents_can_be_indexed(session: Session) -> None:
    indexer = DocumentIndexer(IndexRepository(session))
    transient = Document(
        url="https://transient.edu/",
        domain="transient.edu",
    )

    with pytest.raises(ValueError, match="persisted"):
        indexer.index_document(transient)
