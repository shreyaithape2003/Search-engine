from collections.abc import Generator
from importlib import import_module

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def create_database_engine(database_url: str) -> Engine:
    """Create an engine, applying SQLite's thread setting when needed."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


engine = create_database_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a short-lived session suitable for a future FastAPI dependency."""
    with SessionLocal() as session:
        yield session


def initialize_database(database_engine: Engine = engine) -> None:
    """Create the tables for all registered models when explicitly requested."""
    import_module("app.models.document")
    Base.metadata.create_all(bind=database_engine)
