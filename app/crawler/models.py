from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CrawlPage(BaseModel):
    """An HTML page fetched successfully during a crawl."""

    url: HttpUrl
    status_code: int = Field(ge=200, lt=300)
    content_type: str
    html: str
    depth: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class CrawlIssue(BaseModel):
    """A recorded crawl error or deliberate skip."""

    url: str
    reason: str
    skipped: bool = False
    status_code: int | None = None

    model_config = ConfigDict(extra="forbid")


class CrawlResult(BaseModel):
    """Summary and in-memory pages from a single crawl run."""

    start_url: HttpUrl
    pages: list[CrawlPage] = Field(default_factory=list)
    pages_visited: int = Field(default=0, ge=0)
    pages_fetched: int = Field(default=0, ge=0)
    pages_skipped: int = Field(default=0, ge=0)
    discovered_urls: list[str] = Field(default_factory=list)
    errors: list[CrawlIssue] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
