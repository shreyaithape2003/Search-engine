import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable

import httpx

from app.crawler.config import CrawlerConfig
from app.crawler.fetcher import FetchOutcome, HTTPFetcher
from app.crawler.links import extract_links
from app.crawler.models import CrawlIssue, CrawlPage, CrawlResult
from app.crawler.robots import RobotsChecker
from app.crawler.url_utils import is_url_in_scope, normalize_url
from app.models.seed_source import SeedSource

Sleep = Callable[[float], Awaitable[None]]
MAX_REDIRECTS = 5


class _RequestGate:
    def __init__(self, delay: float, sleep: Sleep) -> None:
        self.delay = delay
        self.sleep = sleep
        self.last_request_at: float | None = None

    async def wait(self) -> None:
        now = time.monotonic()
        if self.last_request_at is not None:
            remaining = self.delay - (now - self.last_request_at)
            if remaining > 0:
                await self.sleep(remaining)
        self.last_request_at = time.monotonic()


class Crawler:
    """Sequential breadth-first crawler driven by one SeedSource record."""

    def __init__(
        self,
        config: CrawlerConfig | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.config = config or CrawlerConfig()
        self.client = client
        self.sleep = sleep

    async def crawl(self, source: SeedSource) -> CrawlResult:
        """Fetch in-scope HTML pages without persisting them."""
        start_url = normalize_url(source.start_url)
        result = CrawlResult(start_url=start_url)
        if not source.active:
            self._record_skip(result, start_url, "Seed source is inactive.")
            return result

        if self.client is None:
            async with httpx.AsyncClient(
                timeout=self.config.request_timeout,
                follow_redirects=False,
            ) as client:
                return await self._crawl_with_client(source, start_url, client, result)
        return await self._crawl_with_client(source, start_url, self.client, result)

    async def _crawl_with_client(
        self,
        source: SeedSource,
        start_url: str,
        client: httpx.AsyncClient,
        result: CrawlResult,
    ) -> CrawlResult:
        gate = _RequestGate(self.config.request_delay, self.sleep)
        fetcher = HTTPFetcher(client, self.config, gate.wait)
        robots = (
            RobotsChecker(client, self.config, gate.wait)
            if self.config.respect_robots_txt
            else None
        )

        queue: deque[tuple[str, int]] = deque([(start_url, 0)])
        queued_or_visited = {start_url}
        discovered: set[str] = set()
        rejected_out_of_scope: set[str] = set()
        page_requests = 0

        while queue and page_requests < self.config.max_pages:
            url, depth = queue.popleft()
            result.pages_visited += 1

            if not is_url_in_scope(url, source):
                self._record_skip(result, url, "URL is outside the seed source scope.")
                continue

            if robots is not None:
                allowed, reason = await robots.can_fetch(url)
                if not allowed:
                    self._record_skip(result, url, reason or "Disallowed by robots.txt.")
                    continue

            page_requests += 1
            page, issue = await self._fetch_with_redirects(
                url,
                depth,
                source,
                fetcher,
                robots,
            )
            if issue is not None:
                result.errors.append(issue)
                if issue.skipped:
                    result.pages_skipped += 1
                continue
            if page is None:
                continue

            result.pages.append(page)
            result.pages_fetched += 1

            for link in extract_links(page.html, str(page.url)):
                if link in discovered or link == start_url:
                    continue
                if not is_url_in_scope(link, source):
                    if link not in rejected_out_of_scope:
                        rejected_out_of_scope.add(link)
                        self._record_skip(
                            result,
                            link,
                            "Discovered URL is outside the seed source scope.",
                        )
                    continue

                discovered.add(link)
                result.discovered_urls.append(link)
                if depth < self.config.max_depth and link not in queued_or_visited:
                    queued_or_visited.add(link)
                    queue.append((link, depth + 1))

        return result

    async def _fetch_with_redirects(
        self,
        initial_url: str,
        depth: int,
        source: SeedSource,
        fetcher: HTTPFetcher,
        robots: RobotsChecker | None,
    ) -> tuple[CrawlPage | None, CrawlIssue | None]:
        current_url = initial_url
        seen_redirects = {current_url}

        for redirect_count in range(MAX_REDIRECTS + 1):
            outcome = await self._fetch_one(current_url, depth, fetcher)
            if isinstance(outcome, CrawlIssue):
                return None, outcome

            if outcome.redirect_location is not None:
                if redirect_count == MAX_REDIRECTS:
                    return None, CrawlIssue(
                        url=current_url,
                        reason="Maximum redirect count exceeded.",
                    )
                try:
                    next_url = normalize_url(
                        outcome.redirect_location,
                        base_url=current_url,
                    )
                except ValueError as error:
                    return None, CrawlIssue(
                        url=current_url,
                        reason=f"Invalid redirect URL: {error}",
                    )
                if next_url in seen_redirects:
                    return None, CrawlIssue(
                        url=current_url,
                        reason="Redirect loop detected.",
                    )
                if not is_url_in_scope(next_url, source):
                    return None, CrawlIssue(
                        url=next_url,
                        reason="Redirect target is outside the seed source scope.",
                        skipped=True,
                    )
                if robots is not None:
                    allowed, reason = await robots.can_fetch(next_url)
                    if not allowed:
                        return None, CrawlIssue(
                            url=next_url,
                            reason=reason or "Redirect target disallowed by robots.txt.",
                            skipped=True,
                        )
                seen_redirects.add(next_url)
                current_url = next_url
                continue

            if outcome.skipped_reason is not None:
                return None, CrawlIssue(
                    url=current_url,
                    reason=outcome.skipped_reason,
                    skipped=True,
                    status_code=outcome.status_code,
                )
            if not 200 <= outcome.status_code < 300:
                return None, CrawlIssue(
                    url=current_url,
                    reason=f"HTTP request returned status {outcome.status_code}.",
                    status_code=outcome.status_code,
                )
            if outcome.page is None:
                return None, CrawlIssue(
                    url=current_url,
                    reason="HTTP response did not contain a usable HTML page.",
                )
            return outcome.page, None

        return None, CrawlIssue(url=current_url, reason="Redirect handling failed.")

    async def _fetch_one(
        self,
        url: str,
        depth: int,
        fetcher: HTTPFetcher,
    ) -> FetchOutcome | CrawlIssue:
        try:
            return await fetcher.fetch(url, depth)
        except httpx.TimeoutException:
            return CrawlIssue(url=url, reason="Request timed out.")
        except httpx.RequestError:
            return CrawlIssue(url=url, reason="Network request failed.")

    @staticmethod
    def _record_skip(result: CrawlResult, url: str, reason: str) -> None:
        result.pages_skipped += 1
        result.errors.append(CrawlIssue(url=url, reason=reason, skipped=True))
