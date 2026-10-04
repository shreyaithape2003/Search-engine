import asyncio

import httpx

from app.crawler.config import CrawlerConfig
from app.crawler.crawler import Crawler
from app.models.seed_source import SeedSource


def make_source() -> SeedSource:
    return SeedSource(
        id=1,
        name="Python Documentation",
        start_url="https://docs.python.org/3/",
        domain="docs.python.org",
        description="Official Python documentation.",
        source_type="technical_documentation",
        education_levels=["University"],
        subjects=["Programming"],
        allowed_url_prefixes=["https://docs.python.org/3/"],
        active=True,
        priority=10,
    )


def test_robots_allowed_page_is_fetched_and_rules_are_cached() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: EduSearchBot\nDisallow: /3/private\n",
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text='<a href="/3/tutorial/">Tutorial</a>',
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(max_pages=5, max_depth=1, request_delay=0),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 2
        assert requests.count("https://docs.python.org/robots.txt") == 1
        assert requests.count("https://docs.python.org/3/") == 1
        assert requests.count("https://docs.python.org/3/tutorial/") == 1

    asyncio.run(run())


def test_robots_disallowed_page_is_skipped_and_reported() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /3/private\n",
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text='<a href="/3/private/lesson/">Private lesson</a>',
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(max_pages=5, max_depth=1, request_delay=0),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 1
        assert result.pages_skipped == 1
        assert any(
            issue.url == "https://docs.python.org/3/private/lesson/"
            and issue.skipped
            and "robots.txt" in issue.reason
            for issue in result.errors
        )
        assert "https://docs.python.org/3/private/lesson/" not in requests

    asyncio.run(run())


def test_robots_retrieval_failure_denies_page_and_is_cached() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(503, text="Unavailable")
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text='<a href="/3/tutorial/">Tutorial</a>',
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(max_pages=5, max_depth=2, request_delay=0),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 0
        assert result.pages_skipped == 1
        assert requests == ["https://docs.python.org/robots.txt"]
        assert "denied conservatively" in result.errors[0].reason

    asyncio.run(run())


def test_robots_can_be_disabled_explicitly() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html></html>",
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(
                    max_pages=1,
                    request_delay=0,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 1
        assert requests == ["/3/"]

    asyncio.run(run())
