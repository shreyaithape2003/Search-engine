from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.build_index as build_index_command
from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.indexing.indexer import DocumentIndexer
from app.indexing.repository import IndexRepository
from app.models.document import Document
from app.schemas.document import DocumentCreate


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'build_index.db').as_posix()}"
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


def add_document(
    repository: DocumentRepository,
    url: str,
    **fields: Any,
) -> Document:
    return repository.create(DocumentCreate(url=url, **fields))


def test_builds_index_for_all_existing_documents(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_index_command, "DOCUMENT_BATCH_SIZE", 1)
    documents = DocumentRepository(session)
    first = add_document(
        documents,
        "https://build-one.edu/",
        title="Python foundations",
    )
    second = add_document(
        documents,
        "https://build-two.edu/",
        body="Python programming",
    )
    indexed_document_ids: list[int] = []
    original_index_document = DocumentIndexer.index_document

    def index_document_spy(
        indexer: DocumentIndexer,
        document: Document,
    ) -> int:
        indexed_document_ids.append(document.id)
        return original_index_document(indexer, document)

    monkeypatch.setattr(DocumentIndexer, "index_document", index_document_spy)

    assert build_index_command.build_development_index(session) == 2
    assert indexed_document_ids == [first.id, second.id]
    assert {
        posting.document_id
        for posting in IndexRepository(session).get_postings_for_term("python")
    } == {first.id, second.id}


def test_running_build_twice_replaces_postings_without_duplicates(
    session: Session,
) -> None:
    document = add_document(
        DocumentRepository(session),
        "https://idempotent-build.edu/",
        title="Python Python indexing",
    )
    repository = IndexRepository(session)

    assert build_index_command.build_development_index(session) == 1
    first_postings = [
        (posting.term, posting.field, posting.term_frequency, posting.positions)
        for term in ("python", "indexing")
        for posting in repository.get_postings_for_term(term)
    ]
    assert build_index_command.build_development_index(session) == 1
    second_postings = [
        (posting.term, posting.field, posting.term_frequency, posting.positions)
        for term in ("python", "indexing")
        for posting in repository.get_postings_for_term(term)
    ]

    assert first_postings == second_postings
    assert first_postings == [
        ("python", "title", 2, [0, 1]),
        ("indexing", "title", 1, [2]),
    ]
    assert repository.get_document_statistics(document.id)["title"] == 3


def test_build_with_no_documents_returns_zero(session: Session) -> None:
    assert build_index_command.build_development_index(session) == 0
    assert IndexRepository(session).get_postings_for_term("python") == []


def test_cli_reports_when_no_documents_exist(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(build_index_command, "initialize_database", lambda: None)
    monkeypatch.setattr(build_index_command, "SessionLocal", lambda: session)

    build_index_command.main()

    assert capsys.readouterr().out.strip() == (
        "No Documents found; development index is empty."
    )


def test_indexing_failures_are_not_silently_swallowed(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_document(
        DocumentRepository(session),
        "https://failed-build.edu/",
        title="Python",
    )

    def fail_indexing(
        _indexer: DocumentIndexer,
        _document: Document,
    ) -> int:
        raise RuntimeError("index write failed")

    monkeypatch.setattr(DocumentIndexer, "index_document", fail_indexing)

    with pytest.raises(RuntimeError, match="index write failed"):
        build_index_command.build_development_index(session)
