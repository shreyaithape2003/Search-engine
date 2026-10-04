from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import (
    DocumentRepository,
    DuplicateDocumentError,
)
from app.db.seed import SAMPLE_DOCUMENTS, seed_sample_documents
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'documents.db').as_posix()}"
    database_engine = create_database_engine(database_url)
    yield database_engine
    Base.metadata.drop_all(bind=database_engine)
    database_engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Iterator[Session]:
    initialize_database(test_engine)
    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    with session_factory() as database_session:
        yield database_session


def make_document(url: str = "https://example.edu/course") -> DocumentCreate:
    return DocumentCreate(
        url=url,
        title="Sample educational resource",
        body="Sample body text.",
        headings=["Overview", "Lessons"],
    )


def test_database_initializes_successfully(test_engine: Engine) -> None:
    initialize_database(test_engine)

    assert inspect(test_engine).has_table("documents")


def test_document_can_be_created_and_read_with_utc_timestamps(
    session: Session,
) -> None:
    published_at = datetime(2024, 1, 1, tzinfo=UTC)
    source_updated_at = datetime(2025, 1, 1, tzinfo=UTC)
    document = DocumentRepository(session).create(
        DocumentCreate(
            url="https://example.edu/course",
            title="Sample educational resource",
            body="Sample body text.",
            headings=["Overview", "Lessons"],
            published_at=published_at,
            source_updated_at=source_updated_at,
        )
    )

    assert document.id is not None
    assert document.url == "https://example.edu/course"
    assert document.domain == "example.edu"
    assert document.published_at == published_at
    assert document.source_updated_at == source_updated_at
    assert document.created_at.tzinfo == UTC
    assert document.updated_at.tzinfo == UTC
    assert document.headings == ["Overview", "Lessons"]

    read_document = DocumentRead.model_validate(document)
    assert read_document.id == document.id
    assert read_document.created_at.tzinfo is not None


def test_document_can_be_retrieved_by_id_and_url(session: Session) -> None:
    repository = DocumentRepository(session)
    created = repository.create(make_document())

    assert repository.get_by_id(created.id) is created
    assert repository.get_by_url("https://example.edu/course") is created


def test_multiple_documents_can_be_listed_with_pagination(session: Session) -> None:
    repository = DocumentRepository(session)
    first = repository.create(make_document("https://first.edu/course"))
    second = repository.create(make_document("https://second.edu/course"))

    assert repository.list() == [first, second]
    assert repository.list(limit=1, offset=1) == [second]


def test_document_can_be_updated(session: Session) -> None:
    repository = DocumentRepository(session)
    document = repository.create(make_document())
    old_updated_at = document.updated_at

    updated = repository.update(document.id, DocumentUpdate(title="Updated title"))

    assert updated is not None
    assert updated.title == "Updated title"
    assert updated.body == "Sample body text."
    assert updated.updated_at >= old_updated_at


def test_document_url_update_also_updates_derived_domain(session: Session) -> None:
    repository = DocumentRepository(session)
    document = repository.create(make_document())

    updated = repository.update(
        document.id,
        DocumentUpdate(url="https://new.example.org/resource"),
    )

    assert updated is not None
    assert updated.url == "https://new.example.org/resource"
    assert updated.domain == "new.example.org"


def test_document_can_be_deleted(session: Session) -> None:
    repository = DocumentRepository(session)
    document = repository.create(make_document())

    assert repository.delete(document.id) is True
    assert repository.get_by_id(document.id) is None
    assert repository.delete(document.id) is False


def test_duplicate_url_is_rejected_and_session_can_continue(session: Session) -> None:
    repository = DocumentRepository(session)
    repository.create(make_document())

    with pytest.raises(DuplicateDocumentError):
        repository.create(make_document())

    assert repository.create(make_document("https://another.edu/course")).id is not None


def test_duplicate_canonical_url_is_rejected(session: Session) -> None:
    repository = DocumentRepository(session)
    repository.create(
        DocumentCreate(
            url="https://one.edu/resource",
            canonical_url="https://canonical.edu/resource",
        )
    )

    with pytest.raises(DuplicateDocumentError):
        repository.create(
            DocumentCreate(
                url="https://two.edu/resource",
                canonical_url="https://canonical.edu/resource",
            )
        )


def test_content_hash_is_indexed_without_restricting_duplicates(session: Session) -> None:
    repository = DocumentRepository(session)
    first = repository.create(
        DocumentCreate(url="https://one.edu/resource", content_hash="same-content")
    )
    second = repository.create(
        DocumentCreate(url="https://two.edu/resource", content_hash="same-content")
    )

    assert first.content_hash == second.content_hash


def test_optional_metadata_can_be_omitted(session: Session) -> None:
    document = DocumentRepository(session).create(
        DocumentCreate(url="https://minimal.edu/resource")
    )

    assert document.description is None
    assert document.author is None
    assert document.publisher is None
    assert document.language is None
    assert document.published_at is None
    assert document.source_updated_at is None
    assert document.source_type is None
    assert document.subject is None
    assert document.education_level is None
    assert document.content_type is None
    assert document.difficulty is None
    assert document.content_hash is None
    assert document.headings == []


def test_document_schemas_validate_urls_dates_and_ids() -> None:
    document = DocumentCreate(
        url="https://valid.example.edu/resource",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    assert document.url.host == "valid.example.edu"

    with pytest.raises(ValidationError):
        DocumentCreate(url="not a valid URL")

    with pytest.raises(ValidationError):
        DocumentCreate(
            url="https://valid.example.edu/resource",
            published_at=datetime(2025, 1, 1),
        )

    with pytest.raises(ValidationError):
        DocumentUpdate(url=None)

    with pytest.raises(ValidationError):
        DocumentRead.model_validate({"id": 0})


def test_sample_seed_is_development_only_and_idempotent(session: Session) -> None:
    assert len(SAMPLE_DOCUMENTS) == 4
    assert seed_sample_documents(session) == 4
    assert seed_sample_documents(session) == 0
    assert len(DocumentRepository(session).list()) == 4
