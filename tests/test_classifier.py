import pytest

from app.classification.classifier import EducationalClassifier
from app.classification.models import ClassificationInput


@pytest.fixture
def classifier() -> EducationalClassifier:
    return EducationalClassifier()


def classify(
    classifier: EducationalClassifier,
    *,
    url: str = "https://example.edu/resource",
    title: str | None = None,
    description: str | None = None,
    headings: list[str] | None = None,
    body: str | None = None,
    seed_source_type: str | None = None,
    seed_education_levels: list[str] | None = None,
    seed_subjects: list[str] | None = None,
    document_education_level: str | None = None,
    document_subject: str | None = None,
    document_content_type: str | None = None,
    document_difficulty: str | None = None,
):
    return classifier.classify(
        ClassificationInput(
            url=url,
            title=title,
            description=description,
            headings=headings or [],
            body=body,
            seed_source_type=seed_source_type,
            seed_education_levels=seed_education_levels or [],
            seed_subjects=seed_subjects or [],
            document_education_level=document_education_level,
            document_subject=document_subject,
            document_content_type=document_content_type,
            document_difficulty=document_difficulty,
        )
    )


@pytest.mark.parametrize(
    (
        "classification",
        "expected_level",
        "expected_subject",
        "expected_type",
        "expected_difficulty",
    ),
    [
        (
            {
                "url": "https://learn.example/training/python/",
                "title": "Python Programming Tutorial for Beginners",
                "headings": ["Variables and functions"],
                "description": "Learn the Python programming language.",
            },
            "Professional",
            "Computer Science",
            "tutorial",
            "Beginner",
        ),
        (
            {
                "url": "https://university.example/university/courses/calculus/",
                "title": "University Calculus Course",
            },
            "University",
            "Mathematics",
            "course",
            "Unknown",
        ),
        (
            {
                "url": "https://engineering.example/docs/",
                "title": "Engineering API Reference Documentation",
            },
            None,
            "Engineering",
            "documentation",
            "Unknown",
        ),
        (
            {
                "url": "https://school.example/materials/",
                "title": "Grade 7 Biology Study Material",
            },
            "School",
            "Biology",
            "study material",
            "Unknown",
        ),
        (
            {
                "url": "https://medical.example/articles/",
                "title": "Medical Education Article: Anatomy Overview",
            },
            None,
            "Medicine",
            "article",
            "Unknown",
        ),
        (
            {
                "url": "https://archive.example/research/papers/",
                "title": "Biology Research Paper on Cell Genetics",
            },
            "Research",
            "Biology",
            "research paper",
            "Unknown",
        ),
        (
            {
                "url": "https://business.example/courses/",
                "title": "MBA Business Management Course",
            },
            None,
            "Business / MBA",
            "course",
            "Unknown",
        ),
        (
            {
                "url": "https://learn.example/training/modules/cloud/",
                "title": "Cloud Skills Training Module",
                "seed_source_type": "professional_learning",
                "seed_education_levels": ["Professional"],
                "seed_subjects": ["Computer Science"],
            },
            "Professional",
            "Computer Science",
            "course",
            "Unknown",
        ),
    ],
)
def test_representative_educational_resources(
    classifier: EducationalClassifier,
    classification: dict[str, object],
    expected_level: str | None,
    expected_subject: str,
    expected_type: str,
    expected_difficulty: str,
) -> None:
    result = classify(classifier, **classification)

    assert result.education_level == expected_level
    assert result.subject == expected_subject
    assert result.content_type == expected_type
    assert result.difficulty == expected_difficulty


def test_generic_technology_article_does_not_get_a_guessed_subject(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/articles/technology-trends",
        title="Technology Trends",
        description="A general article about technology changes.",
        headings=["How technology affects daily life"],
    )

    assert result.subject is None
    assert result.content_type == "article"
    assert result.education_level is None
    assert result.provenance["subject"].method == "unknown"
    assert result.provenance["subject"].confidence == "Low"


def test_insufficient_metadata_returns_unknown_without_failure(
    classifier: EducationalClassifier,
) -> None:
    result = classify(classifier, url="https://example.edu/")

    assert result.education_level is None
    assert result.subject is None
    assert result.content_type is None
    assert result.difficulty == "Unknown"
    assert all(
        item.method == "unknown"
        for item in result.provenance.values()
    )


def test_explicit_metadata_precedes_seed_and_page_rules(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/school/mathematics/",
        title="Grade 7 Mathematics",
        document_education_level=" college ",
        document_subject="math",
        document_content_type="article",
        document_difficulty="intermediate",
        seed_education_levels=["University", "Professional"],
        seed_subjects=["Engineering"],
    )

    assert result.education_level == "University"
    assert result.subject == "Mathematics"
    assert result.content_type == "article"
    assert result.difficulty == "Intermediate"
    assert all(
        evidence.method == "explicit_metadata"
        and evidence.confidence == "High"
        for evidence in result.provenance.values()
    )


def test_seed_source_metadata_fills_missing_fields_when_unambiguous(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/resource",
        seed_education_levels=["college", "University"],
        seed_subjects=["CS", "Computer Science"],
        seed_source_type="technical_documentation",
    )

    assert result.education_level == "University"
    assert result.subject == "Computer Science"
    assert result.content_type == "documentation"
    assert result.provenance["education_level"].method == "seed_source"
    assert result.provenance["subject"].method == "seed_source"


def test_multiple_seed_levels_allow_matching_rule_based_level(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/school/mathematics/",
        title="Grade 7 Mathematics",
        seed_education_levels=["University", "School"],
    )

    assert result.education_level == "School"
    assert result.provenance["education_level"].method == "rule_based"
    assert result.provenance["education_level"].confidence == "High"


def test_multiple_seed_levels_reject_conflicting_rule_based_level(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/school/mathematics/",
        title="Grade 7 Mathematics",
        seed_education_levels=["University", "Professional"],
    )

    evidence = result.provenance["education_level"]
    assert result.education_level is None
    assert evidence.method == "unknown"
    assert evidence.confidence == "Low"
    assert "conflicts" in evidence.reasons[0]


@pytest.mark.parametrize(
    "seed_education_levels",
    [[], ["General"]],
)
def test_missing_or_unsupported_seed_levels_keep_rule_behavior(
    classifier: EducationalClassifier,
    seed_education_levels: list[str],
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/school/mathematics/",
        title="Grade 7 Mathematics",
        seed_education_levels=seed_education_levels,
    )

    assert result.education_level == "School"
    assert result.provenance["education_level"].method == "rule_based"


def test_ambiguous_seed_metadata_is_not_collapsed_or_guessed(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        url="https://example.edu/lesson",
        title="Technology Overview",
        seed_education_levels=["School", "University"],
        seed_subjects=["Computer Science", "Engineering"],
    )

    assert result.education_level is None
    assert result.subject is None


def test_rule_based_subject_does_not_override_conflicting_explicit_metadata(
    classifier: EducationalClassifier,
) -> None:
    result = classify(
        classifier,
        title="Advanced Biology Research",
        document_subject="Mathematics",
        document_education_level="Professional",
        seed_subjects=["Biology"],
    )

    assert result.subject == "Mathematics"
    assert result.education_level == "Professional"
    assert result.provenance["subject"].method == "explicit_metadata"


def test_unsupported_values_are_ignored_and_input_content_is_not_modified(
    classifier: EducationalClassifier,
) -> None:
    html_like_body = "<script> technology </script> General technology overview"
    result = classify(
        classifier,
        title="Technology Overview",
        body=html_like_body,
        document_education_level="General",
        document_subject="Science",
        document_content_type="webpage",
        document_difficulty="expert",
    )

    assert result.education_level is None
    assert result.subject is None
    assert result.content_type is None
    assert result.difficulty == "Unknown"
    assert html_like_body == "<script> technology </script> General technology overview"


def test_body_scanning_is_bounded(classifier: EducationalClassifier) -> None:
    result = classify(
        classifier,
        title="Generic resource",
        body=("ordinary text " * 20_000) + " Python programming",
    )

    assert result.subject is None
