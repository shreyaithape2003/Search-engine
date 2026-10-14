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


def test_excerpt_range_matches_displayed_text_without_ellipses() -> None:
    generator = SnippetGenerator(maximum_length=32)
    text = "  opening text " + ("filler " * 8) + " biology lesson " + (
        "ending " * 8
    )

    snippet, start, end = generator._excerpt(text, text.index("biology"))

    assert snippet == f"…{text[start:end]}…"
    assert snippet[1:-1] == text[start:end]
    assert len(snippet) <= generator.maximum_length


def test_excerpt_scoring_ignores_query_tokens_cut_at_excerpt_boundaries() -> None:
    generator = SnippetGenerator(maximum_length=3)

    assert list(generator._matching_terms("biology", 0, 3, {"bio"})) == []
    assert list(generator._matching_terms("biology", 4, 7, {"ogy"})) == []


def test_query_matches_near_excerpt_boundaries_are_not_counted_when_cut() -> None:
    generator = SnippetGenerator(maximum_length=24)
    text = ("biology " * 40) + "chemistry"

    snippet, start, end = generator._excerpt(text, text.index("chemistry") + 2)

    assert snippet.removeprefix("…").removesuffix("…") == text[start:end]
    assert start == text.index("chemistry")
    assert end == len(text)
    assert "chemistry" in snippet


def test_multiple_query_terms_are_selected_from_the_same_excerpt() -> None:
    generator = SnippetGenerator(maximum_length=48)
    text = ("algebra appears early. " * 12) + (
        "Geometry and algebra solve related problems. "
    ) + ("geometry appears late. " * 12)

    snippet = generator.generate("algebra geometry", body=text)

    assert "algebra" in snippet.lower()
    assert "geometry" in snippet.lower()
    assert len(snippet) <= generator.maximum_length


def test_candidate_generation_is_bounded_and_deterministic() -> None:
    class CountingGenerator(SnippetGenerator):
        excerpt_calls = 0

        def _excerpt(self, text: str, desired_start: int) -> tuple[str, int, int]:
            self.excerpt_calls += 1
            return super()._excerpt(text, desired_start)

    generator = CountingGenerator(maximum_length=40)
    text = "biology " * 10_000

    first = generator.generate("biology", body=text)
    first_count = generator.excerpt_calls
    generator.excerpt_calls = 0
    second = generator.generate("biology", body=text)

    assert first == second
    assert first_count <= generator._MAX_CANDIDATES
    assert generator.excerpt_calls <= generator._MAX_CANDIDATES


@pytest.mark.parametrize("maximum_length", [1, 2, 3, 24, 60])
def test_snippet_never_exceeds_maximum_length(maximum_length: int) -> None:
    generator = SnippetGenerator(maximum_length=maximum_length)
    snippet = generator.generate(
        "biology",
        body="Beginning " + ("biology lesson " * 30) + "ending",
    )

    assert len(snippet) <= maximum_length


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
