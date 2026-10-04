from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveInt,
    model_validator,
)


class DocumentCreate(BaseModel):
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    body: str | None = None
    headings: list[str] | None = Field(default_factory=list)
    author: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=35)
    published_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    source_type: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, max_length=200)
    education_level: str | None = Field(default=None, max_length=100)
    content_type: str | None = Field(default=None, max_length=100)
    difficulty: str | None = Field(default=None, max_length=50)
    content_hash: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid")


class DocumentUpdate(BaseModel):
    url: HttpUrl | None = None
    canonical_url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    body: str | None = None
    headings: list[str] | None = None
    author: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=35)
    published_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    source_type: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, max_length=200)
    education_level: str | None = Field(default=None, max_length=100)
    content_type: str | None = Field(default=None, max_length=100)
    difficulty: str | None = Field(default=None, max_length=50)
    content_hash: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ensure_url_is_not_cleared(self) -> "DocumentUpdate":
        if "url" in self.model_fields_set and self.url is None:
            raise ValueError("The document URL cannot be null.")
        return self


class DocumentRead(BaseModel):
    id: PositiveInt
    url: HttpUrl
    canonical_url: HttpUrl | None
    domain: str
    title: str | None
    description: str | None
    body: str | None
    headings: list[str] | None
    author: str | None
    publisher: str | None
    language: str | None
    published_at: AwareDatetime | None
    source_updated_at: AwareDatetime | None
    source_type: str | None
    subject: str | None
    education_level: str | None
    content_type: str | None
    difficulty: str | None
    content_hash: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    model_config = ConfigDict(from_attributes=True)
