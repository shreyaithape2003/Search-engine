from html.parser import HTMLParser
from urllib.parse import urlsplit

from app.crawler.url_utils import normalize_url

NON_PAGE_EXTENSIONS = {
    ".7z",
    ".avi",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value is not None:
                self.hrefs.append(value)
                break

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)


def extract_links(html: str, page_url: str) -> list[str]:
    """Extract unique normalized HTTP(S) page links from anchor elements."""
    parser = _AnchorParser()
    try:
        parser.feed(html)
        parser.close()
    except (AssertionError, ValueError):
        return []

    unique_links: dict[str, None] = {}
    for href in parser.hrefs:
        try:
            normalized = normalize_url(href, base_url=page_url)
        except ValueError:
            continue

        path = urlsplit(normalized).path.lower()
        if any(path.endswith(extension) for extension in NON_PAGE_EXTENSIONS):
            continue
        unique_links.setdefault(normalized, None)
    return list(unique_links)
