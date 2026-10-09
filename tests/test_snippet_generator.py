import pytest

from app.services.snippet_generator import SnippetGenerator


@pytest.fixture
def generator() -> SnippetGenerator:
    return SnippetGenerator(maximum_length=60)


def test_prefers_query_match_in_description(generator: SnippetGenerator) -> None:
    snippet = generator.generate(
        "biology",
        description="A clear introduction to biology for new learners.",
        body="An unrelated body.",
    )

    assert "biology" in snippet
    assert snippet.startswith("A clear introduction")


def test_uses_body_when_description_does_not_match(
    generator: SnippetGenerator,
) -> None:
    snippet = generator.generate(
        "photosynthesis",
        description="An introduction to cell structure.",
        body="Photosynthesis converts light into chemical energy.",
    )

    assert "Photosynthesis" in snippet
    assert "cell structure" not in snippet


def test_prefers_passage_covering_multiple_query_terms(
    generator: SnippetGenerator,
) -> None:
    snippet = generator.generate(
        "algebra geometry",
        body=(
            "Algebra is useful. " * 8
            + "Geometry and algebra together help solve problems."
        ),
    )

    assert "Geometry" in snippet
    assert "algebra" in snippet.lower()


def test_repeated_query_terms_do_not_prevent_a_match(
    generator: SnippetGenerator,
) -> None:
    snippet = generator.generate(
        "biology biology",
        description="Biology introduces living systems.",
    )

    assert snippet == "Biology introduces living systems."


def test_matching_is_case_insensitive_and_supports_unicode(
    generator: SnippetGenerator,
) -> None:
    snippet = generator.generate(
        "STRASSE café",
        body="Learners study Straße and cafe\u0301 in this lesson.",
    )

    assert "Straße" in snippet
    assert "cafe\u0301" in snippet


def test_headings_are_considered_after_description(generator: SnippetGenerator) -> None:
    snippet = generator.generate(
        "calculus",
        description="General mathematics information.",
        headings=["Introduction", "Calculus basics"],
        body="Additional text.",
    )

    assert snippet == "Introduction Calculus basics"


@pytest.mark.parametrize(
    ("description", "headings", "body"),
    [
        (None, None, None),
        ("", [], ""),
        ("  ", ["", "  "], None),
    ],
)
def test_missing_and_empty_fields_return_empty_snippet(
    generator: SnippetGenerator,
    description: str | None,
    headings: list[str] | None,
    body: str | None,
) -> None:
    assert generator.generate(
        "topic",
        description=description,
        headings=headings,
        body=body,
    ) == ""


def test_short_text_is_returned_without_ellipsis(generator: SnippetGenerator) -> None:
    assert generator.generate("math", description="Math basics.") == "Math basics."


def test_long_text_is_truncated_with_ellipsis_at_both_ends() -> None:
    generator = SnippetGenerator(maximum_length=40)
    text = "Beginning words. " + ("filler " * 20) + "biology appears here. " + (
        "ending " * 20
    )

    snippet = generator.generate("biology", body=text)

    assert len(snippet) <= 40
    assert snippet.startswith("…")
    assert snippet.endswith("…")
    assert "biology" in snippet


def test_regex_metacharacters_in_query_are_safe() -> None:
    snippet = SnippetGenerator().generate(
        "C++ (arrays)",
        body="C++ arrays are common in programming.",
    )

    assert "C++ arrays" in snippet


def test_no_matching_terms_uses_first_available_field() -> None:
    snippet = SnippetGenerator().generate(
        "unrelated",
        description="Start with a concise description.",
        body="A different body.",
    )

    assert snippet == "Start with a concise description."


def test_script_like_text_remains_plain_text() -> None:
    snippet = SnippetGenerator().generate(
        "lesson",
        body="<script>alert('unsafe')</script> lesson content",
    )

    assert snippet == "<script>alert('unsafe')</script> lesson content"
