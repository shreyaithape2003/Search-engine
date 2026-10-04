import pytest

from app.crawler.links import extract_links
from app.crawler.url_utils import is_url_in_scope, normalize_url
from app.models.seed_source import SeedSource


def make_source() -> SeedSource:
    return SeedSource(
        id=1,
        name="Python Documentation",
        start_url="https://docs.python.org/3/",
        domain="docs.python.org",
        description="Official Python documentation.",
        source_type="technical_documentation",
        education_levels=["University", "Professional"],
        subjects=["Programming"],
        allowed_url_prefixes=["https://docs.python.org/3/"],
        active=True,
        priority=10,
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://Example.com/Page", "http://example.com/Page"),
        (
            "https://Example.com/Page#section",
            "https://example.com/Page",
        ),
        (
            "https://EXAMPLE.com:443/a?topic=math#section",
            "https://example.com/a?topic=math",
        ),
    ],
)
def test_normalize_url_accepts_http_urls_and_normalizes(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_normalize_url_resolves_relative_links() -> None:
    assert (
        normalize_url("../tutorial/#intro", "https://docs.python.org/3/library/")
        == "https://docs.python.org/3/tutorial/"
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "javascript:alert(1)",
        "mailto:student@example.edu",
        "tel:+15551234567",
        "data:text/html,hello",
        "https:///missing-host",
        "https://example.com:invalid/",
        "https://example.com/has space",
    ],
)
def test_normalize_url_rejects_empty_malformed_and_unsupported_urls(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_url(url)


def test_seed_source_scope_requires_matching_host_and_allowed_prefix() -> None:
    source = make_source()

    assert is_url_in_scope("https://docs.python.org/3/tutorial/", source)
    assert not is_url_in_scope("https://example.com/3/tutorial/", source)
    assert not is_url_in_scope("https://docs.python.org.example.com/3/", source)
    assert not is_url_in_scope("https://docs.python.org/2/tutorial/", source)
    assert not is_url_in_scope("https://docs.python.org/30/tutorial/", source)
    assert not is_url_in_scope("https://docs.python.org.evil/3/", source)


def test_seed_source_host_comparison_is_case_insensitive() -> None:
    source = make_source()

    assert is_url_in_scope("HTTPS://DOCS.PYTHON.ORG/3/tutorial/", source)


def test_seed_start_url_still_must_match_configured_domain() -> None:
    source = make_source()
    source.domain = "example.com"

    assert not is_url_in_scope(source.start_url, source)


def test_extract_links_resolves_deduplicates_and_ignores_non_page_links() -> None:
    html = """
    <a href="/tutorial/">Tutorial</a>
    <a href="https://docs.python.org/3/library/#index">Library</a>
    <a href="#section">Section</a>
    <a href="mailto:test@example.com">Email</a>
    <a href="javascript:void(0)">Script</a>
    <a href="/files/guide.pdf">PDF</a>
    <img src="/image.png">
    <a href="/tutorial/">Duplicate</a>
    """

    assert extract_links(html, "https://docs.python.org/3/") == [
        "https://docs.python.org/tutorial/",
        "https://docs.python.org/3/library/",
        "https://docs.python.org/3/",
    ]
