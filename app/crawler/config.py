from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class CrawlerConfig(BaseModel):
    """Safety and politeness limits for one sequential development crawl."""

    max_pages: int = Field(default=20, ge=1)
    max_depth: int = Field(default=2, ge=0)
    request_timeout: float = Field(default=10.0, gt=0)
    request_delay: float = Field(default=1.0, ge=0)
    user_agent: NonEmptyString = "EduSearchBot/0.1"
    max_response_size: int = Field(default=5 * 1024 * 1024, gt=0)
    respect_robots_txt: bool = True

    model_config = ConfigDict(extra="forbid")
