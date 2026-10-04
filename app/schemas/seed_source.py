from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveInt,
    StringConstraints,
    model_validator,
)

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
NonEmptyList = Annotated[list[NonEmptyString], Field(min_length=1)]
URLPrefixList = Annotated[list[HttpUrl], Field(min_length=1)]


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
