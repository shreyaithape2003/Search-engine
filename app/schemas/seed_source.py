from collections.abc import Callable
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.classification.taxonomy import (
    normalize_education_level,
    normalize_subject,
)

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
NonEmptyList = Annotated[list[NonEmptyString], Field(min_length=1)]
URLPrefixList = Annotated[list[HttpUrl], Field(min_length=1)]


def _normalize_categories(
    values: list[str],
    normalizer: Callable[[str | None], str | None],
) -> list[str]:
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalizer(value)
        if normalized is None:
            raise ValueError(f"Unsupported taxonomy value: {value}")
        category = normalized
        key = category.casefold()
        if key not in seen:
            normalized_values.append(category)
            seen.add(key)
    return normalized_values


class SeedSourceCreate(BaseModel):
    name: NonEmptyString
    start_url: HttpUrl
    description: NonEmptyString
    source_type: NonEmptyString
    education_levels: NonEmptyList
    subjects: NonEmptyList
    allowed_url_prefixes: URLPrefixList
    active: bool = True
    priority: PositiveInt = 100

    model_config = ConfigDict(extra="forbid")

    @field_validator("education_levels")
    @classmethod
    def canonicalize_education_levels(cls, values: list[str]) -> list[str]:
        return _normalize_categories(values, normalize_education_level)

    @field_validator("subjects")
    @classmethod
    def canonicalize_subjects(cls, values: list[str]) -> list[str]:
        return _normalize_categories(values, normalize_subject)


class SeedSourceUpdate(BaseModel):
    name: NonEmptyString | None = None
    start_url: HttpUrl | None = None
    description: NonEmptyString | None = None
    source_type: NonEmptyString | None = None
    education_levels: NonEmptyList | None = None
    subjects: NonEmptyList | None = None
    allowed_url_prefixes: URLPrefixList | None = None
    active: bool | None = None
    priority: PositiveInt | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("education_levels")
    @classmethod
    def canonicalize_education_levels(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is None:
            return None
        return _normalize_categories(values, normalize_education_level)

    @field_validator("subjects")
    @classmethod
    def canonicalize_subjects(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is None:
            return None
        return _normalize_categories(values, normalize_subject)

    @model_validator(mode="after")
    def reject_explicit_null_values(self) -> "SeedSourceUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                if field == "start_url":
                    raise ValueError("The seed source start URL cannot be null.")
                raise ValueError(f"{field} cannot be null.")
        return self


class SeedSourceRead(BaseModel):
    id: PositiveInt
    name: str
    start_url: HttpUrl
    domain: str
    description: str
    source_type: str
    education_levels: list[str]
    subjects: list[str]
    allowed_url_prefixes: list[HttpUrl]
    active: bool
    priority: PositiveInt
    created_at: AwareDatetime
    updated_at: AwareDatetime

    model_config = ConfigDict(from_attributes=True)
