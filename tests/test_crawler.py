import asyncio

import httpx
import pytest

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


def response(html: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        headers={"content-type": "text/html; charset=utf-8"},
        text=html,
    )


def test_crawls_start_discovers_relative_links_and_fetches_duplicates_once() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        if request.url.path == "/3/":
            return response(
                '<a href="/3/tutorial/">Tutorial</a>'
                '<a href="tutorial/#start">Duplicate</a>'
                '<a href="/3/library/">Library</a>'
                '<a href="https://example.com/">External</a>'
            )
        return response("<html><body>Lesson</body></html>")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(max_pages=10, max_depth=2, request_delay=0),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 3
        assert result.pages_visited == 3
        assert [str(page.url) for page in result.pages] == [
            "https://docs.python.org/3/",
            "https://docs.python.org/3/tutorial/",
            "https://docs.python.org/3/library/",
        ]
        assert requests.count("https://docs.python.org/3/tutorial/") == 1
        assert "https://example.com/" not in requests
        assert "https://example.com/" not in [str(url) for url in result.discovered_urls]
        assert any(issue.url == "https://example.com/" and issue.skipped for issue in result.errors)

    asyncio.run(run())


def test_max_pages_limits_page_requests() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        return response('<a href="/3/a/">A</a><a href="/3/b/">B</a>')

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(
                    max_pages=2,
                    max_depth=2,
                    request_delay=0,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(make_source())

        page_requests = [url for url in requests if url != "https://docs.python.org/robots.txt"]
        assert len(page_requests) == 2
        assert result.pages_fetched == 2

    asyncio.run(run())


def test_max_depth_zero_only_fetches_start_page() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return response('<a href="/3/tutorial/">Tutorial</a>')

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(
                    max_pages=5,
                    max_depth=0,
                    request_delay=0,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 1
        assert requests == ["https://docs.python.org/3/"]
        assert result.discovered_urls == ["https://docs.python.org/3/tutorial/"]

    asyncio.run(run())


@pytest.mark.parametrize(
    ("handler", "expected_reason"),
    [
        (
            lambda _: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF",
            ),
            "not an HTML",
        ),
        (
            lambda _: httpx.Response(
                503,
                headers={"content-type": "text/html"},
                text="Unavailable",
            ),
            "status 503",
        ),
        (
            lambda _: httpx.Response(
                200,
                headers={
                    "content-type": "text/html",
                    "content-length": "100",
                },
                content=b"x" * 100,
            ),
            "size limit",
        ),
    ],
)
def test_non_html_http_errors_and_oversized_responses_are_reported(
    handler,
    expected_reason: str,
) -> None:
    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        return handler(request)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            result = await Crawler(
                CrawlerConfig(
                    max_pages=2,
                    request_delay=0,
                    max_response_size=20,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 0
        assert len(result.errors) == 1
        assert expected_reason in result.errors[0].reason
        if expected_reason == "size limit":
            assert result.pages_skipped == 1

    asyncio.run(run())


def test_actual_body_size_is_limited_without_content_length() -> None:
    class LargeBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 10
            yield b"y" * 11

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/3/"
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=LargeBody(),
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(
                    max_pages=1,
                    request_delay=0,
                    max_response_size=20,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 0
        assert result.pages_skipped == 1
        assert "size limit" in result.errors[0].reason

    asyncio.run(run())


def test_timeout_does_not_stop_the_crawl() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/3/":
            raise httpx.ReadTimeout("test timeout", request=request)
        return response("<html>Recovered</html>")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Crawler(
                CrawlerConfig(
                    max_pages=2,
                    max_depth=1,
                    request_delay=0,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(make_source())

        assert result.pages_fetched == 0
        assert result.errors[0].reason == "Request timed out."

    asyncio.run(run())


def test_connection_error_does_not_stop_the_crawl() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

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

        assert result.pages_fetched == 0
        assert result.errors[0].reason == "Network request failed."

    asyncio.run(run())


def test_redirect_is_followed_only_when_target_remains_in_scope() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/3/":
            return httpx.Response(302, headers={"location": "/3/start/"})
        return response("<html>Redirected page</html>")

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
        assert str(result.pages[0].url) == "https://docs.python.org/3/start/"
        assert requests == [
            "https://docs.python.org/3/",
            "https://docs.python.org/3/start/",
        ]

    asyncio.run(run())


def test_redirect_outside_scope_is_not_requested() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://example.com/"})

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

        assert requests == ["https://docs.python.org/3/"]
        assert result.pages_skipped == 1
        assert "outside the seed source scope" in result.errors[0].reason

    asyncio.run(run())


def test_zero_request_delay_does_not_sleep() -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: response("<html></html>"))
        ) as client:
            await Crawler(
                CrawlerConfig(max_pages=1, request_delay=0, respect_robots_txt=False),
                client=client,
                sleep=fake_sleep,
            ).crawl(make_source())

    asyncio.run(run())
    assert delays == []


def test_positive_request_delay_is_applied_between_requests() -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    def handler(_: httpx.Request) -> httpx.Response:
        return response('<a href="/3/next/">Next</a>')

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await Crawler(
                CrawlerConfig(
                    max_pages=2,
                    request_delay=0.01,
                    respect_robots_txt=False,
                ),
                client=client,
                sleep=fake_sleep,
            ).crawl(make_source())

    asyncio.run(run())
    assert len(delays) == 1
    assert 0 < delays[0] <= 0.01


@pytest.mark.parametrize(
    "values",
    [
        {"max_pages": 0},
        {"max_depth": -1},
        {"request_timeout": 0},
        {"request_delay": -1},
        {"max_response_size": 0},
        {"user_agent": "   "},
    ],
)
def test_crawler_config_rejects_unsafe_limits(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        CrawlerConfig(**values)
