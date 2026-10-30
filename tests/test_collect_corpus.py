import asyncio
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.collect_corpus as collect_command
from app.crawler.config import CrawlerConfig
from app.db.build_index import build_development_index
from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.seed_source_repository import SeedSourceRepository
from app.indexing.repository import IndexRepository
from app.models.seed_source import SeedSource
from app.schemas.seed_source import SeedSourceCreate

EDUCATIONAL_HTML = """
<html><head><title>Python programming foundations</title>
<meta name="description" content="A detailed guide to programming and computer science.">
</head><body><main><h1>Python programming foundations</h1>
<p>Python is a programming language used to teach computer science concepts.
This lesson explains variables, functions, data structures, and how learners
can apply them to solve practical problems with clear examples.</p></main></body></html>
"""


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'collection.db').as_posix()}"
    )
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Iterator[Session]:
    initialize_database(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


def create_source(
    session: Session,
    *,
    name: str = "Collector Test Source",
    start_url: str = "https://collector.example.edu/learn/",
    active: bool = True,
) -> SeedSource:
    return SeedSourceRepository(session).create(
        SeedSourceCreate(
            name=name,
            start_url=start_url,
            description="Curated educational lessons.",
            source_type="open_education",
            education_levels=["University"],
            subjects=["Computer Science"],
            allowed_url_prefixes=[start_url],
            active=active,
        )
    )


def collect(
    session: Session,
    sources: list[SeedSource],
    handler,
    config: CrawlerConfig | None = None,
):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
        ) as client:
            return await collect_command.collect_sources(
                session,
                sources,
                config
                or CrawlerConfig(
                    max_pages=10,
                    max_depth=2,
                    request_delay=0,
                ),
                client,
            )

    return asyncio.run(run())


def test_select_sources_excludes_inactive_sources(session: Session) -> None:
    active = create_source(session)
    inactive = create_source(
        session,
        name="Inactive Source",
        start_url="https://inactive.example.edu/learn/",
        active=False,
    )

    assert collect_command.select_sources([inactive, active]) == [active]
    with pytest.raises(ValueError, match="inactive"):
        collect_command.select_sources([inactive], ["Inactive Source"])


def test_collection_respects_robots_scope_and_crawl_limits(
    session: Session,
) -> None:
    source = create_source(session)
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /learn/private/\n",
            )
        if request.url.path == "/learn/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    EDUCATIONAL_HTML.replace(
                        "</main>",
                        "</main>"
                        '<a href="/learn/private/lesson/">private</a>'
                        '<a href="/learn/lesson/">in scope</a>'
                        '<a href="/other/page/">out of prefix</a>'
                        '<a href="https://elsewhere.example.edu/learn/">other domain</a>',
                    )
                ),
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=EDUCATIONAL_HTML,
        )

    [stats] = collect(
        session,
        [source],
        handler,
        CrawlerConfig(
            max_pages=2,
            max_depth=1,
            request_delay=0,
        ),
    )

    assert stats.attempted_urls == 3
    assert stats.fetched_pages == 2
    assert stats.new_documents == 2
    assert stats.skipped_pages >= 3
    assert not any("private" in url or "elsewhere" in url for url in requested)
    assert "https://collector.example.edu/other/page/" not in requested


def test_successful_pages_are_classified_deduplicated_and_indexable(
    session: Session,
) -> None:
    source = create_source(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        html = EDUCATIONAL_HTML
        if request.url.path == "/learn/":
            html += '<a href="/learn/python/">Python lesson</a>'
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=html,
        )

    first = collect(session, [source], handler)
    second = collect(session, [source], handler)
    documents = DocumentRepository(session).list(limit=10)

    assert first[0].new_documents == 2
    assert first[0].duplicate_documents == 0
    assert second[0].new_documents == 0
    assert second[0].duplicate_documents == 2
    assert len(documents) == 2
    assert documents[0].subject == "Computer Science"
    assert documents[0].education_level == "University"
    assert documents[0].classification_provenance["subject"]["method"] == "seed_source"
    assert build_development_index(session) == 2
    assert IndexRepository(session).get_postings_for_term("programming")


def test_collection_skips_low_quality_and_error_pages(session: Session) -> None:
    source = create_source(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><title>404 Not Found</title><body>Nothing here.</body></html>",
        )

    [stats] = collect(session, [source], handler)

    assert stats.fetched_pages == 1
    assert stats.accepted_pages == 0
    assert stats.skipped_pages == 1
    assert stats.new_documents == 0
    assert DocumentRepository(session).list() == []


@pytest.mark.parametrize(
    ("response", "error_text"),
    [
        (
            httpx.Response(
                503,
                headers={"content-type": "text/html"},
                text="Unavailable",
            ),
            "status 503",
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF",
            ),
            "not an HTML",
        ),
    ],
)
def test_collection_reports_http_and_content_type_failures(
    session: Session,
    response: httpx.Response,
    error_text: str,
) -> None:
    source = create_source(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        return response

    [stats] = collect(session, [source], handler)

    assert stats.fetched_pages == 0
    assert stats.failures + stats.skipped_pages == 1
    assert any(error_text in issue.reason for issue in stats.issues)


def test_timeout_is_reported_and_later_pages_are_still_ingested(
    session: Session,
) -> None:
    source = create_source(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\n")
        if request.url.path == "/learn/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    EDUCATIONAL_HTML.replace(
                        "</main>",
                        "</main>"
                        '<a href="/learn/timeout/">timeout</a>'
                        '<a href="/learn/available/">available</a>',
                    )
                ),
            )
        if request.url.path == "/learn/timeout/":
            raise httpx.ReadTimeout(
                "mocked timeout",
                request=request,
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=EDUCATIONAL_HTML,
        )

    [stats] = collect(
        session,
        [source],
        handler,
        CrawlerConfig(
            max_pages=3,
            max_depth=1,
            request_delay=0,
        ),
    )

    assert stats.failures == 1
    assert stats.fetched_pages == 2
    assert stats.new_documents == 2
    assert any("timed out" in issue.reason for issue in stats.issues)


def test_dry_run_does_not_make_requests_or_persist_data(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = create_source(session)
    monkeypatch.setattr(collect_command, "initialize_database", lambda: None)
    monkeypatch.setattr(collect_command, "SessionLocal", lambda: session)

    collect_command.main(["--source", source.name, "--max-pages", "3"])

    output = capsys.readouterr().out
    assert "Dry run" in output
    assert source.name in output
    assert DocumentRepository(session).list() == []


def test_cli_rejects_unsafe_limits_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        collect_command,
        "initialize_database",
        lambda: pytest.fail("database must not initialize for invalid arguments"),
    )

    with pytest.raises(SystemExit) as error:
        collect_command.main(["--max-pages", "101"])

    assert error.value.code == 2


def test_live_cli_requires_explicit_source_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        collect_command,
        "initialize_database",
        lambda: pytest.fail("database must not initialize without explicit selection"),
    )

    with pytest.raises(SystemExit) as error:
        collect_command.main(["--execute"])

    assert error.value.code == 2
