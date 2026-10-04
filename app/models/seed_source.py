from datetime import UTC, datetime

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.document import UTCDateTime


class SeedSource(Base):
    """A curated educational website entry point for a future crawler."""

    __tablename__ = "seed_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    education_levels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    subjects: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    allowed_url_prefixes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
