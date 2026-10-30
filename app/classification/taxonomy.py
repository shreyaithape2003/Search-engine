"""Canonical educational metadata values and exact alias normalization."""

from collections.abc import Mapping

EDUCATION_LEVELS = ("School", "University", "Professional", "Research")
SUBJECTS = (
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
)
RESOURCE_TYPES = (
    "course",
    "documentation",
    "article",
    "tutorial",
    "research paper",
    "lecture",
    "blog",
    "study material",
    "Other / Specialized",
)
DIFFICULTY_LEVELS = ("Beginner", "Intermediate", "Advanced", "Unknown")
UNKNOWN_DIFFICULTY = "Unknown"
OTHER_SPECIALIZED = "Other / Specialized"


def _key(value: str | None) -> str | None:
    if not isinstance(value, str) or len(value) > 200:
        return None
    normalized = " ".join(value.split()).casefold()
    return normalized or None


def _lookup(value: str | None, aliases: Mapping[str, str]) -> str | None:
    key = _key(value)
    return aliases.get(key) if key is not None else None


_EDUCATION_ALIASES = {
    **{value.casefold(): value for value in EDUCATION_LEVELS},
    "college": "University",
    "college / university": "University",
    "college/university": "University",
    "high school": "School",
    "k-12": "School",
}
_SUBJECT_ALIASES = {
    **{value.casefold(): value for value in SUBJECTS},
    "cs": "Computer Science",
    "programming": "Computer Science",
    "software development": "Computer Science",
    "math": "Mathematics",
    "bio": "Biology",
    "medical education": "Medicine",
    "business": "Business / MBA",
    "mba": "Business / MBA",
    "social science": "Social Sciences",
    "specialized": OTHER_SPECIALIZED,
}
_RESOURCE_TYPE_ALIASES = {
    **{value.casefold(): value for value in RESOURCE_TYPES},
    "researchpaper": "research paper",
    "academic paper": "research paper",
    "paper": "research paper",
    "docs": "documentation",
    "reference documentation": "documentation",
    "blog post": "blog",
    "study materials": "study material",
    "other": OTHER_SPECIALIZED,
    "specialized": OTHER_SPECIALIZED,
}
_DIFFICULTY_ALIASES = {
    **{value.casefold(): value for value in DIFFICULTY_LEVELS},
    "introductory": "Beginner",
    "novice": "Beginner",
    "unknown": UNKNOWN_DIFFICULTY,
    "": UNKNOWN_DIFFICULTY,
}


def normalize_education_level(value: str | None) -> str | None:
    return _lookup(value, _EDUCATION_ALIASES)


def normalize_subject(value: str | None) -> str | None:
    return _lookup(value, _SUBJECT_ALIASES)


def normalize_resource_type(value: str | None) -> str | None:
    return _lookup(value, _RESOURCE_TYPE_ALIASES)


def normalize_difficulty(value: str | None) -> str | None:
    return _lookup(value, _DIFFICULTY_ALIASES)
