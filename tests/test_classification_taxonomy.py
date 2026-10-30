from pydantic import ValidationError
import pytest

from app.classification.taxonomy import (
    DIFFICULTY_LEVELS,
    EDUCATION_LEVELS,
    RESOURCE_TYPES,
    SUBJECTS,
    normalize_difficulty,
    normalize_education_level,
    normalize_resource_type,
    normalize_subject,
)
from app.schemas.seed_source import SeedSourceCreate, SeedSourceUpdate


def test_taxonomy_values_are_unique_and_match_primary_filter_choices() -> None:
    for values in (
        EDUCATION_LEVELS,
        SUBJECTS,
        RESOURCE_TYPES,
        DIFFICULTY_LEVELS,
    ):
        assert len(values) == len(set(value.casefold() for value in values))

    assert EDUCATION_LEVELS == ("School", "University", "Professional", "Research")
    assert "Other" not in EDUCATION_LEVELS
    assert set(SUBJECTS) == {
        "Computer Science",
        "Engineering",
        "Mathematics",
        "Physics",
        "Chemistry",
        "Biology",
        "Medicine",
        "Business / MBA",
        "Economics",
        "Humanities",
        "Social Sciences",
        "Other / Specialized",
    }
    assert set(RESOURCE_TYPES) == {
        "course",
        "documentation",
        "article",
        "tutorial",
        "research paper",
        "lecture",
        "blog",
        "study material",
        "Other / Specialized",
    }
    assert DIFFICULTY_LEVELS == ("Beginner", "Intermediate", "Advanced", "Unknown")


@pytest.mark.parametrize(
    ("normalizer", "input_value", "expected"),
    [
        (normalize_education_level, " college ", "University"),
        (normalize_education_level, "COLLEGE / UNIVERSITY", "University"),
        (normalize_education_level, " high   school ", "School"),
        (normalize_subject, " computer   science ", "Computer Science"),
        (normalize_subject, "CS", "Computer Science"),
        (normalize_subject, "Programming", "Computer Science"),
        (normalize_subject, "business", "Business / MBA"),
        (normalize_resource_type, "Research Paper", "research paper"),
        (normalize_resource_type, " DOCS ", "documentation"),
        (normalize_resource_type, "Study Materials", "study material"),
        (normalize_difficulty, "beginner", "Beginner"),
        (normalize_difficulty, "introductory", "Beginner"),
        (normalize_difficulty, "UNKNOWN", "Unknown"),
    ],
)
def test_taxonomy_aliases_are_normalized_exactly(
    normalizer,
    input_value: str,
    expected: str,
) -> None:
    assert normalizer(input_value) == expected


@pytest.mark.parametrize(
    ("normalizer", "input_value"),
    [
        (normalize_education_level, "General"),
        (normalize_education_level, "Other"),
        (normalize_subject, "Science"),
        (normalize_subject, "I.T."),
        (normalize_resource_type, "webpage"),
        (normalize_difficulty, "expert"),
    ],
)
def test_unknown_or_ambiguous_values_are_not_guessed(
    normalizer,
    input_value: str,
) -> None:
    assert normalizer(input_value) is None


def test_seed_source_schemas_canonicalize_and_reject_unknown_values() -> None:
    source = SeedSourceCreate(
        name="Example Learning",
        start_url="https://example.edu/",
        description="A curated educational source.",
        source_type="open_education",
        education_levels=[" college ", "University"],
        subjects=["CS", " computer science "],
        allowed_url_prefixes=["https://example.edu/"],
    )

    assert source.education_levels == ["University"]
    assert source.subjects == ["Computer Science"]

    update = SeedSourceUpdate(
        education_levels=["high school"],
        subjects=["math"],
    )
    assert update.education_levels == ["School"]
    assert update.subjects == ["Mathematics"]

    with pytest.raises(ValidationError):
        SeedSourceCreate(
            name="Unsupported",
            start_url="https://unsupported.example/",
            description="Unsupported taxonomy values.",
            source_type="test",
            education_levels=["General"],
            subjects=["Astronomy"],
            allowed_url_prefixes=["https://unsupported.example/"],
        )

    with pytest.raises(ValidationError):
        SeedSourceCreate(
            name="Invalid",
            start_url="https://invalid.example/",
            description="Invalid source.",
            source_type="test",
            education_levels=[],
            subjects=["Computer Science"],
            allowed_url_prefixes=["https://invalid.example/"],
        )
