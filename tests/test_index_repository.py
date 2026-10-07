from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.indexing.indexer import DocumentIndexer
from app.indexing.repository import IndexRepository
from app.schemas.document import DocumentCreate


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'index_repository.db').as_posix()}"
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


def test_term_statistics_use_distinct_documents_and_count_frequency(
    session: Session,
) -> None:
    repository = DocumentRepository(session)
    first = repository.create(
        DocumentCreate(
            url="https://frequency-one.edu/",
            title="python python python",
        )
    )
    second = repository.create(
        DocumentCreate(
            url="https://frequency-two.edu/",
            body="python",
        )
    )
    index = IndexRepository(session)
    indexer = DocumentIndexer(index)
    indexer.index_document(first)
    indexer.index_document(second)

    statistics = index.get_term_statistics("ＰＹＴＨＯＮ")

    assert statistics.term == "python"
    assert statistics.document_frequency == 2
    assert statistics.collection_term_frequency == 4
    assert statistics.indexed_document_count == 2


def test_term_statistics_count_indexed_documents_with_empty_fields(
    session: Session,
) -> None:
    repository = DocumentRepository(session)
    document = repository.create(DocumentCreate(url="https://empty.edu/"))
    index = IndexRepository(session)
    DocumentIndexer(index).index_document(document)

    statistics = index.get_term_statistics("missing")

    assert statistics.document_frequency == 0
    assert statistics.collection_term_frequency == 0
    assert statistics.indexed_document_count == 1
    assert index.get_document_statistics(document.id) == {
        "body": 0,
        "description": 0,
        "headings": 0,
        "title": 0,
    }


def test_postings_persist_and_can_be_deleted_by_document(session: Session) -> None:
    document = DocumentRepository(session).create(
        DocumentCreate(
            url="https://persistent.edu/",
            title="Persistent index",
        )
    )
    repository = IndexRepository(session)
    DocumentIndexer(repository).index_document(document)

    session.expire_all()
    postings = repository.get_postings_for_term("persistent")
    assert len(postings) == 1
    assert postings[0].document_id == document.id
    assert postings[0].term_frequency == 1
    assert repository.get_document_statistics(document.id)["title"] == 2

    repository.delete_document_index(document.id)

    assert repository.get_postings_for_term("persistent") == []
    assert repository.get_document_statistics(document.id) == {}
    assert repository.get_term_statistics("persistent").indexed_document_count == 0


def test_index_tables_are_registered_with_database_initialization(
    test_engine: Engine,
) -> None:
    initialize_database(test_engine)
    table_names = set(inspect(test_engine).get_table_names())

    assert "index_postings" in table_names
    assert "document_field_statistics" in table_names
