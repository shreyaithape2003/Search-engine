from pydantic import BaseModel, ConfigDict, Field


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
