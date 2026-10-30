"""Typed inputs and results for educational classification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ClassificationMethod = Literal[
    "explicit_metadata",
    "seed_source",
    "rule_based",
    "unknown",
]
ConfidenceLevel = Literal["High", "Medium", "Low"]


class ClassificationEvidence(BaseModel):
    method: ClassificationMethod
    confidence: ConfidenceLevel
    reasons: list[str] = Field(default_factory=list, max_length=3)

    model_config = ConfigDict(extra="forbid")


class ClassificationInput(BaseModel):
    url: str = Field(max_length=2048)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    headings: list[str] = Field(default_factory=list, max_length=100)
    body: str | None = None

    document_education_level: str | None = None
    document_subject: str | None = None
    document_content_type: str | None = None
    document_difficulty: str | None = None

    seed_source_type: str | None = None
    seed_education_levels: list[str] = Field(default_factory=list, max_length=100)
    seed_subjects: list[str] = Field(default_factory=list, max_length=100)

    model_config = ConfigDict(extra="forbid")


class ClassificationResult(BaseModel):
    education_level: str | None
    subject: str | None
    content_type: str | None
    difficulty: str
    provenance: dict[str, ClassificationEvidence]

    model_config = ConfigDict(extra="forbid")
