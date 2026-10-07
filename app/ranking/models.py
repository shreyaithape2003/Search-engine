from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class BM25Config(BaseModel):
    """Validated BM25 parameters, field weights, and query resource limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    k1: float = Field(default=1.2, gt=0, allow_inf_nan=False)
    b: float = Field(default=0.75, ge=0, le=1, allow_inf_nan=False)
    title_weight: float = Field(default=4.0, ge=0, allow_inf_nan=False)
    headings_weight: float = Field(default=2.5, ge=0, allow_inf_nan=False)
    description_weight: float = Field(default=2.0, ge=0, allow_inf_nan=False)
    body_weight: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    maximum_query_length: int = Field(default=2000, ge=1)
    maximum_unique_terms: int = Field(default=100, ge=1)

    @property
    def field_weights(self) -> dict[str, float]:
        return {
            "title": self.title_weight,
            "headings": self.headings_weight,
            "description": self.description_weight,
            "body": self.body_weight,
        }


@dataclass(frozen=True)
class RankedDocument:
    document_id: int
    score: float
    matched_terms: tuple[str, ...]
