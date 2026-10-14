from pydantic import BaseModel, ConfigDict, Field


class SearchFilters(BaseModel):
    education_level: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, max_length=200)
    content_type: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=35)
    domain: str | None = Field(default=None, max_length=253)
    difficulty: str | None = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")


class SearchResult(BaseModel):
    document_id: int
    title: str | None
    url: str
    description: str | None
    snippet: str
    score: float = Field(allow_inf_nan=False)
    matched_terms: list[str]

    model_config = ConfigDict(extra="forbid")


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int

    model_config = ConfigDict(extra="forbid")


class SearchSuggestionsResponse(BaseModel):
    query: str
    suggestions: list[str]

    model_config = ConfigDict(extra="forbid")
