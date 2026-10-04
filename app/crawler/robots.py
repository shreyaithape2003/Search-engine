from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.crawler.config import CrawlerConfig

BeforeRequest = Callable[[], Awaitable[None]]


class RobotsChecker:
    """Cache robots rules for one crawl; deny access when rules cannot load."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: CrawlerConfig,
        before_request: BeforeRequest,
    ) -> None:
        self.client = client
        self.config = config
        self.before_request = before_request
        self._rules: dict[str, RobotFileParser | None] = {}

    async def can_fetch(self, url: str) -> tuple[bool, str | None]:
        origin = self._origin(url)
        if origin not in self._rules:
            await self._load_rules(origin)

        rules = self._rules[origin]
        if rules is None:
            return False, "robots.txt could not be retrieved; denied conservatively."
        if not rules.can_fetch(self.config.user_agent, url):
            return False, "URL is disallowed by robots.txt."
        return True, None

    async def _load_rules(self, origin: str) -> None:
        robots_url = f"{origin}/robots.txt"
        try:
            await self.before_request()
            async with self.client.stream(
                "GET",
                robots_url,
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.request_timeout,
                follow_redirects=False,
            ) as response:
                if not 200 <= response.status_code < 300:
                    self._rules[origin] = None
                    return

                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        if int(content_length) > self.config.max_response_size:
                            self._rules[origin] = None
                            return
                    except ValueError:
                        pass

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > self.config.max_response_size:
                        self._rules[origin] = None
                        return
                    body.extend(chunk)
        except httpx.HTTPError:
            self._rules[origin] = None
            return

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(bytes(body).decode("utf-8", errors="replace").splitlines())
        self._rules[origin] = parser

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
