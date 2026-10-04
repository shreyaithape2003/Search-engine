from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.seed_source_repository import (
    DuplicateSeedSourceError,
    SeedSourceRepository,
)
from app.db.seed_sources import CURATED_SEED_SOURCES, seed_curated_sources
from app.schemas.seed_source import (
    SeedSourceCreate,
    SeedSourceRead,
    SeedSourceUpdate,
)


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'seed_sources.db').as_posix()}"
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


def make_source(
    start_url: str = "https://docs.example.edu/catalog/",
) -> SeedSourceCreate:
    return SeedSourceCreate(
        name="Example Education",
        start_url=start_url,
        description="Curated educational material.",
        source_type="open_education",
        education_levels=["University"],
        subjects=["Computer Science"],
        allowed_url_prefixes=[start_url],
    )


def test_database_initializes_both_document_and_seed_source_tables(
    test_engine: Engine,
) -> None:
    initialize_database(test_engine)
    inspector = inspect(test_engine)

    assert inspector.has_table("documents")
    assert inspector.has_table("seed_sources")


def test_seed_source_schema_accepts_valid_data() -> None:
    source = make_source()

    assert source.start_url.host == "docs.example.edu"
    assert source.priority == 100
    assert source.active is True


def test_seed_source_schemas_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        make_source("not a valid URL")

    for field in ("name", "description", "source_type"):
        values = make_source().model_dump()
        values[field] = "   "
        with pytest.raises(ValidationError):
            SeedSourceCreate.model_validate(values)

    for field in ("education_levels", "subjects", "allowed_url_prefixes"):
        values = make_source().model_dump()
        values[field] = []
        with pytest.raises(ValidationError):
            SeedSourceCreate.model_validate(values)

    with pytest.raises(ValidationError):
        SeedSourceCreate(
            **{**make_source().model_dump(), "priority": 0}
        )

    with pytest.raises(ValidationError):
        SeedSourceCreate(
            **{**make_source().model_dump(), "unexpected": "not allowed"}
        )


def test_update_rejects_clearing_start_url_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SeedSourceUpdate(start_url=None)
    with pytest.raises(ValidationError):
        SeedSourceUpdate(name=None)
    with pytest.raises(ValidationError):
        SeedSourceUpdate(unrecognized="no")


def test_repository_create_and_get_by_id_and_start_url(session: Session) -> None:
    repository = SeedSourceRepository(session)
    created = repository.create(make_source())

    assert created.id is not None
    assert repository.get_by_id(created.id) is created
    assert repository.get_by_start_url("https://docs.example.edu/catalog/") is created
    assert created.domain == "docs.example.edu"
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None
    assert SeedSourceRead.model_validate(created).id == created.id


def test_domain_is_derived_and_normalized_from_start_url(session: Session) -> None:
    source = SeedSourceRepository(session).create(
        make_source("https://DOCS.Example.edu:8443/catalog/")
    )

    assert source.domain == "docs.example.edu"


def test_repository_list_update_and_delete(session: Session) -> None:
    repository = SeedSourceRepository(session)
    first = repository.create(make_source())
    second = repository.create(make_source("https://other.example.edu/"))

    assert repository.list() == [first, second]
    assert repository.list(limit=1, offset=1) == [second]

    updated = repository.update(
        first.id,
        SeedSourceUpdate(
            start_url="https://learn.example.org/",
            name="Updated Learning Source",
            priority=5,
            active=False,
        ),
    )
    assert updated is not None
    assert updated.name == "Updated Learning Source"
    assert updated.start_url == "https://learn.example.org/"
    assert updated.domain == "learn.example.org"
    assert updated.priority == 5
    assert updated.active is False

    assert repository.delete(first.id) is True
    assert repository.get_by_id(first.id) is None
    assert repository.delete(first.id) is False


def test_duplicate_start_url_is_rejected_and_session_recovers(session: Session) -> None:
    repository = SeedSourceRepository(session)
    repository.create(make_source())

    with pytest.raises(DuplicateSeedSourceError):
        repository.create(make_source())

    assert repository.create(make_source("https://another.example.edu/")).id is not None


def test_curated_source_seed_contains_12_sources_and_is_idempotent(
    session: Session,
) -> None:
    assert len(CURATED_SEED_SOURCES) == 12
    assert seed_curated_sources(session) == 12
    assert seed_curated_sources(session) == 0

    sources = SeedSourceRepository(session).list(limit=20)
    assert len(sources) == 12
    assert {source.name for source in sources} == {
        "MIT OpenCourseWare",
        "OpenLearn",
        "OpenStax",
        "Khan Academy",
        "NASA Science",
        "NCBI Bookshelf",
        "PubMed Central",
        "arXiv",
        "Python Documentation",
        "MDN Web Docs",
        "Microsoft Learn",
        "AWS Documentation",
    }
