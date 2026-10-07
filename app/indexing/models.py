from dataclasses import dataclass

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class IndexPosting(Base):
    """Term frequency and token positions for one document field."""

    __tablename__ = "index_postings"
    __table_args__ = (
        UniqueConstraint(
            "term",
            "document_id",
            "field",
            name="uq_index_postings_term_document_field",
        ),
        Index("ix_index_postings_term_document", "term", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    term_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    positions: Mapped[list[int]] = mapped_column(JSON, nullable=False)


class DocumentFieldStatistics(Base):
    """Token length for one indexed field of a document."""

    __tablename__ = "document_field_statistics"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "field",
            name="uq_document_field_statistics_document_field",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    document_length: Mapped[int] = mapped_column(Integer, nullable=False)


@dataclass(frozen=True)
class PostingData:
    term: str
    document_id: int
    field: str
    term_frequency: int
    positions: list[int]


@dataclass(frozen=True)
class FieldStatisticsData:
    document_id: int
    field: str
    document_length: int


@dataclass(frozen=True)
class TermStatistics:
    term: str
    document_frequency: int
    collection_term_frequency: int
    indexed_document_count: int


@dataclass(frozen=True)
class FieldCollectionStatistics:
    field: str
    document_count: int
    total_document_length: int
