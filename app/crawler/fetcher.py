from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.crawler.config import CrawlerConfig
from app.crawler.models import CrawlPage

BeforeRequest = Callable[[], Awaitable[None]]
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class FetchOutcome:
    status_code: int
    content_type: str | None = None
    page: CrawlPage | None = None
    redirect_location: str | None = None
    skipped_reason: str | None = None


class HTTPFetcher:
    """Fetch bounded HTML responses using a caller-managed async client."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: CrawlerConfig,
        before_request: BeforeRequest,
    ) -> None:
        self.client = client
        self.config = config
        self.before_request = before_request

    async def fetch(self, url: str, depth: int) -> FetchOutcome:
        await self.before_request()
        async with self.client.stream(
            "GET",
            url,
            headers={"User-Agent": self.config.user_agent},
            timeout=self.config.request_timeout,
            follow_redirects=False,
        ) as response:
            content_type = response.headers.get("content-type")
            media_type = (
                content_type.split(";", 1)[0].strip().lower()
                if content_type
                else None
            )

            if response.status_code in REDIRECT_STATUS_CODES:
                return FetchOutcome(
                    status_code=response.status_code,
                    content_type=content_type,
                    redirect_location=response.headers.get("location"),
                )

            if not 200 <= response.status_code < 300:
                return FetchOutcome(
                    status_code=response.status_code,
                    content_type=content_type,
                )

            if media_type not in HTML_CONTENT_TYPES:
                return FetchOutcome(
                    status_code=response.status_code,
                    content_type=content_type,
                    skipped_reason="Response is not an HTML page.",
                )

            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = 0
                if declared_size > self.config.max_response_size:
                    return FetchOutcome(
                        status_code=response.status_code,
                        content_type=content_type,
                        skipped_reason="Response exceeds the configured size limit.",
                    )

            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > self.config.max_response_size:
                    return FetchOutcome(
                        status_code=response.status_code,
                        content_type=content_type,
                        skipped_reason="Response exceeds the configured size limit.",
                    )
                body.extend(chunk)

            try:
                encoding = response.encoding or "utf-8"
            except LookupError:
                encoding = "utf-8"
            html = bytes(body).decode(encoding, errors="replace")
            page = CrawlPage(
                url=url,
                status_code=response.status_code,
                content_type=content_type or media_type or "text/html",
                html=html,
                depth=depth,
            )
            return FetchOutcome(
                status_code=response.status_code,
                content_type=content_type,
                page=page,
            )
