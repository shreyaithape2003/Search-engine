import hashlib
import json
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from app.crawler.models import CrawlPage
from app.crawler.url_utils import is_url_in_scope, normalize_url
from app.ingestion.models import ExtractedDocument
from app.models.seed_source import SeedSource

WHITESPACE = re.compile(r"\s+")
REMOVED_ELEMENTS = ("script", "style", "noscript", "template", "svg")


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = WHITESPACE.sub(" ", value).strip()
    return normalized or None


def _meta_content(soup: BeautifulSoup, *keys: tuple[str, str]) -> str | None:
    for attribute, expected in keys:
        for meta in soup.find_all("meta"):
            value = meta.get(attribute)
            content = meta.get("content")
            if (
                isinstance(value, str)
                and value.strip().casefold() == expected.casefold()
                and isinstance(content, str)
            ):
                normalized = _normalize_text(content)
                if normalized is not None:
                    return normalized
    return None


def _tag_text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    return _normalize_text(tag.get_text(" ", strip=True))


def _parse_datetime(value: str | None) -> datetime | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _date_metadata(
    soup: BeautifulSoup,
    *keys: str,
    use_time_element: bool = False,
) -> datetime | None:
    for key in keys:
        for meta in soup.find_all("meta"):
            for attribute in ("property", "name", "itemprop"):
                value = meta.get(attribute)
                content = meta.get("content")
                if (
                    isinstance(value, str)
                    and value.strip().casefold() == key.casefold()
                    and isinstance(content, str)
                ):
                    parsed = _parse_datetime(content)
                    if parsed is not None:
                        return parsed

    if use_time_element:
        for time_tag in soup.find_all("time"):
            value = time_tag.get("datetime")
            if isinstance(value, str):
                parsed = _parse_datetime(value)
                if parsed is not None:
                    return parsed
    return None


def _canonical_url(
    soup: BeautifulSoup,
    page_url: str,
    source: SeedSource,
) -> HttpUrl:
    for link in soup.find_all("link"):
        rel = link.get("rel", [])
        href = link.get("href")
        rel_values = rel if isinstance(rel, list) else [rel]
        if (
            not any(str(value).casefold() == "canonical" for value in rel_values)
            or not isinstance(href, str)
        ):
            continue
        try:
            candidate = normalize_url(href, base_url=page_url)
        except ValueError:
            continue
        if is_url_in_scope(candidate, source):
            return HttpUrl(candidate)
    return HttpUrl(normalize_url(page_url))


def _extract_body(soup: BeautifulSoup) -> str | None:
    for element in soup.find_all(REMOVED_ELEMENTS):
        element.decompose()

    content_root = soup.body
    if content_root is None:
        head = soup.find("head")
        if head is not None:
            head.decompose()
        for title in soup.find_all("title"):
            if title.find(re.compile(r"^(p|div|h[1-6]|ul|ol|table)$", re.IGNORECASE)):
                title.unwrap()
            else:
                title.decompose()
        content_root = soup

    lines = [
        normalized
        for line in content_root.get_text("\n").splitlines()
        if (normalized := _normalize_text(line)) is not None
    ]
    body = "\n".join(lines).strip()
    return body or None


def _content_hash(
    title: str | None,
    headings: list[str],
    body: str | None,
) -> str:
    meaningful_content = json.dumps(
        {"title": title, "headings": headings, "body": body},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(meaningful_content.encode("utf-8")).hexdigest()


class HTMLContentExtractor:
    """Extract normalized educational page content from a crawler result."""

    def extract(self, page: CrawlPage, source: SeedSource) -> ExtractedDocument:
        page_url = normalize_url(str(page.url))
        soup = BeautifulSoup(page.html, "html.parser")

        title = _tag_text(soup.title)
        if title is None:
            title = _meta_content(
                soup,
                ("property", "og:title"),
                ("name", "twitter:title"),
            )

        description = _meta_content(
            soup,
            ("name", "description"),
            ("property", "og:description"),
        )
        headings = [
            normalized
            for heading in soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))
            if (normalized := _tag_text(heading)) is not None
        ]

        language: str | None = None
        html_tag = soup.find("html")
        if isinstance(html_tag, Tag):
            language = _normalize_text(html_tag.get("lang"))

        author = _meta_content(
            soup,
            ("name", "author"),
            ("property", "article:author"),
        )
        publisher = _meta_content(
            soup,
            ("property", "og:site_name"),
            ("name", "application-name"),
        )
        published_at = _date_metadata(
            soup,
            "article:published_time",
            "datePublished",
            use_time_element=True,
        )
        source_updated_at = _date_metadata(
            soup,
            "article:modified_time",
            "dateModified",
        )
        body = _extract_body(soup)

        return ExtractedDocument(
            title=title,
            description=description,
            body=body,
            headings=headings,
            author=author,
            publisher=publisher,
            language=language,
            canonical_url=_canonical_url(soup, page_url, source),
            published_at=published_at,
            source_updated_at=source_updated_at,
            content_type="webpage",
            content_hash=_content_hash(title, headings, body),
        )
