from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ExtractedDocument(BaseModel):
    """Normalized content and metadata extracted from one HTML page."""

    title: str | None = None
    description: str | None = None
    body: str | None = None
    headings: list[str] = Field(default_factory=list)
    author: str | None = None
    publisher: str | None = None
    language: str | None = None
    canonical_url: HttpUrl
    published_at: datetime | None = None
    source_updated_at: datetime | None = None
    content_type: str = "webpage"
    content_hash: str

    model_config = ConfigDict(extra="forbid")
