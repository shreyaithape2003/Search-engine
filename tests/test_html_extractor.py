from datetime import UTC, datetime
import hashlib

import pytest

from app.crawler.models import CrawlPage
from app.ingestion.html_extractor import HTMLContentExtractor
from app.models.seed_source import SeedSource


def make_source() -> SeedSource:
    return SeedSource(
        id=1,
        name="Example Education",
        start_url="https://example.edu/catalog/",
        domain="example.edu",
        description="Curated educational content.",
        source_type="open_education",
        education_levels=["University"],
        subjects=["Computer Science"],
        allowed_url_prefixes=["https://example.edu/catalog/"],
        active=True,
        priority=10,
    )


def make_page(html: str, url: str = "https://example.edu/catalog/page") -> CrawlPage:
    return CrawlPage(
        url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
        depth=0,
    )


def test_title_uses_title_then_og_then_twitter_and_can_be_missing() -> None:
    extractor = HTMLContentExtractor()

    assert extractor.extract(make_page("<title>  Main \n Title </title>"), make_source()).title == "Main Title"
    assert extractor.extract(
        make_page('<meta property="og:title" content="  Open Graph   Title ">'),
        make_source(),
    ).title == "Open Graph Title"
    assert extractor.extract(
        make_page('<meta name="twitter:title" content="Twitter Title">'),
        make_source(),
    ).title == "Twitter Title"
    assert extractor.extract(make_page("<p>No title</p>"), make_source()).title is None


def test_description_prefers_meta_then_og_and_never_uses_body_text() -> None:
    extractor = HTMLContentExtractor()

    assert extractor.extract(
        make_page(
            '<meta name="description" content="  Main   description ">'
            '<meta property="og:description" content="Open Graph description">'
        ),
        make_source(),
    ).description == "Main description"
    assert extractor.extract(
        make_page('<meta property="og:description" content="OG description">'),
        make_source(),
    ).description == "OG description"
    assert extractor.extract(make_page("<p>Body is not a description</p>"), make_source()).description is None


def test_headings_are_ordered_normalized_and_empty_headings_removed() -> None:
    extracted = HTMLContentExtractor().extract(
        make_page(
            "<h3>Third <em>level</em></h3><h1> First \n heading </h1>"
            "<h2>   </h2><h6>Sixth level</h6><h4>Fourth</h4>"
        ),
        make_source(),
    )

    assert extracted.headings == [
        "Third level",
        "First heading",
        "Sixth level",
        "Fourth",
    ]


def test_body_removes_non_content_elements_and_normalizes_whitespace() -> None:
    extracted = HTMLContentExtractor().extract(
        make_page(
            "<html><body><p> First   paragraph </p>"
            "<script>secret script</script><style>.x { color: red }</style>"
            "<noscript>secret noscript</noscript><template>secret template</template>"
            "<svg><text>secret svg</text></svg><p>Second\n paragraph</p>"
            "</body></html>"
        ),
        make_source(),
    )

    assert extracted.body == "First paragraph\nSecond\nparagraph"
    for unwanted in ("secret", "color: red"):
        assert unwanted not in (extracted.body or "")


def test_malformed_minimal_html_returns_best_effort_output() -> None:
    extracted = HTMLContentExtractor().extract(
        make_page("<title>Unclosed title<p>Text <b>continues"),
        make_source(),
    )

    assert extracted.title == "Unclosed title Text continues"
    assert extracted.body == "Unclosed title\nText\ncontinues"
    assert str(extracted.canonical_url) == "https://example.edu/catalog/page"


def test_author_publisher_language_and_missing_metadata() -> None:
    extractor = HTMLContentExtractor()
    extracted = extractor.extract(
        make_page(
            '<html lang=" en-US "><head>'
            '<meta name="author" content="  Ada   Lovelace ">'
            '<meta property="og:site_name" content="Example University">'
            "</head><body>Text</body></html>"
        ),
        make_source(),
    )

    assert extracted.author == "Ada Lovelace"
    assert extracted.publisher == "Example University"
    assert extracted.language == "en-US"

    missing = extractor.extract(make_page("<p>Text</p>"), make_source())
    assert missing.author is None
    assert missing.publisher is None
    assert missing.language is None


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            '<link rel="canonical" href="https://example.edu/catalog/canonical">',
            "https://example.edu/catalog/canonical",
        ),
        (
            '<link rel="canonical" href="canonical">',
            "https://example.edu/catalog/canonical",
        ),
        ("<p>No canonical</p>", "https://example.edu/catalog/page"),
        (
            '<link rel="canonical" href="https://other.example/catalog/page">',
            "https://example.edu/catalog/page",
        ),
        (
            '<link rel="canonical" href="javascript:alert(1)">',
            "https://example.edu/catalog/page",
        ),
        (
            '<link rel="canonical" href="https://example.edu/outside/">',
            "https://example.edu/catalog/page",
        ),
    ],
)
def test_canonical_url_is_validated_and_kept_in_source_scope(
    html: str,
    expected: str,
) -> None:
    extracted = HTMLContentExtractor().extract(make_page(html), make_source())

    assert str(extracted.canonical_url) == expected


def test_publication_and_modified_dates_are_parsed_independently() -> None:
    extracted = HTMLContentExtractor().extract(
        make_page(
            '<meta property="article:published_time" content="2024-01-02T03:04:05Z">'
            '<meta property="article:modified_time" content="2025-02-03T04:05:06+02:00">'
        ),
        make_source(),
    )

    assert extracted.published_at == datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert extracted.source_updated_at == datetime(
        2025,
        2,
        3,
        2,
        5,
        6,
        tzinfo=UTC,
    )


def test_date_published_and_time_fallback_work_and_bad_dates_are_ignored() -> None:
    extractor = HTMLContentExtractor()
    from_meta = extractor.extract(
        make_page('<meta itemprop="datePublished" content="2023-09-08">'),
        make_source(),
    )
    from_time = extractor.extract(
        make_page('<time datetime="2022-05-04T12:00:00Z">May 4</time>'),
        make_source(),
    )
    invalid = extractor.extract(
        make_page(
            '<meta property="article:published_time" content="not-a-date">'
            '<meta property="article:modified_time" content="also-not-a-date">'
        ),
        make_source(),
    )

    assert from_meta.published_at == datetime(2023, 9, 8, tzinfo=UTC)
    assert from_time.published_at == datetime(2022, 5, 4, 12, tzinfo=UTC)
    assert invalid.published_at is None
    assert invalid.source_updated_at is None


def test_content_hash_is_stable_sha256_of_normalized_content_only() -> None:
    extractor = HTMLContentExtractor()
    first = extractor.extract(
        make_page("<title>Lesson</title><h1>Intro</h1><p>Text   here</p>"),
        make_source(),
    )
    equivalent = extractor.extract(
        make_page("<title> Lesson </title><h1> Intro </h1><p>Text here</p>"),
        make_source(),
    )
    changed = extractor.extract(
        make_page("<title>Lesson</title><h1>Intro</h1><p>Changed body</p>"),
        make_source(),
    )
    timestamp_changed = extractor.extract(
        make_page(
            '<meta property="article:published_time" content="2025-01-01">'
            "<title>Lesson</title><h1>Intro</h1><p>Text here</p>"
        ),
        make_source(),
    )

    assert first.content_hash == equivalent.content_hash
    assert first.content_hash != changed.content_hash
    assert first.content_hash == timestamp_changed.content_hash
    assert first.content_hash == hashlib.sha256(
        b'{"title":"Lesson","headings":["Intro"],"body":"Intro\\nText here"}'
    ).hexdigest()
