import asyncio
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.crawler.config import CrawlerConfig
from app.crawler.crawler import Crawler
from app.crawler.models import CrawlPage
from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.seed_source_repository import SeedSourceRepository
from app.ingestion.document_ingestor import DocumentIngestor
from app.models.seed_source import SeedSource
from app.schemas.seed_source import SeedSourceCreate


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'ingestion.db').as_posix()}"
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


def make_source(session: Session) -> SeedSource:
    return SeedSourceRepository(session).create(
        SeedSourceCreate(
            name="Example Learning",
            start_url="https://example.edu/learn/",
            description="Curated learning resources.",
            source_type="open_education",
            education_levels=["University"],
            subjects=["Computer Science"],
            allowed_url_prefixes=["https://example.edu/learn/"],
        )
    )


def make_page(
    html: str = "<title>Lesson</title><h1>Overview</h1><p>Educational text.</p>",
    url: str = "https://example.edu/learn/lesson",
) -> CrawlPage:
    return CrawlPage(
        url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
        depth=0,
    )


def test_ingestor_persists_extracted_content_and_source_metadata(
    session: Session,
) -> None:
    source = make_source(session)
    repository = DocumentRepository(session)

    document = DocumentIngestor(repository).ingest(
        make_page(
            '<html lang="en"><head><title> Lesson  One </title>'
            '<meta name="description" content="Introductory material">'
            '<meta name="author" content="A. Teacher">'
            '<meta property="og:site_name" content="Example University">'
            '<meta property="article:published_time" content="2024-03-01">'
            '<meta property="article:modified_time" content="2024-04-01">'
            '<link rel="canonical" href="/learn/lesson">'
            '</head><body><h1>Overview</h1><p>Educational   text.</p>'
            '<script>ignore this</script></body></html>'
        ),
        source,
    )

    assert document.id is not None
    assert document.url == "https://example.edu/learn/lesson"
    assert document.canonical_url == "https://example.edu/learn/lesson"
    assert document.domain == "example.edu"
    assert document.title == "Lesson One"
    assert document.description == "Introductory material"
    assert document.body == "Overview\nEducational text."
    assert document.headings == ["Overview"]
    assert document.author == "A. Teacher"
    assert document.publisher == "Example University"
    assert document.language == "en"
    assert document.source_type == "open_education"
    assert document.subject == "Computer Science"
    assert document.education_level == "University"
    assert document.content_type == "webpage"
    assert document.published_at is not None
    assert document.source_updated_at is not None
    assert len(document.content_hash or "") == 64
    assert repository.get_by_id(document.id) is document


def test_reingesting_same_url_returns_existing_document(session: Session) -> None:
    source = make_source(session)
    repository = DocumentRepository(session)
    ingestor = DocumentIngestor(repository)
    page = make_page()

    first = ingestor.ingest(page, source)
    second = ingestor.ingest(page, source)

    assert second.id == first.id
    assert repository.list() == [first]


def test_duplicate_canonical_url_returns_existing_document(session: Session) -> None:
    source = make_source(session)
    repository = DocumentRepository(session)
    ingestor = DocumentIngestor(repository)
    first = ingestor.ingest(
        make_page(
            '<link rel="canonical" href="/learn/canonical">'
            "<title>First</title>",
            "https://example.edu/learn/first",
        ),
        source,
    )
    second = ingestor.ingest(
        make_page(
            '<link rel="canonical" href="/learn/canonical">'
            "<title>Second</title>",
            "https://example.edu/learn/second",
        ),
        source,
    )

    assert second.id == first.id
    assert repository.list() == [first]


def test_external_canonical_url_falls_back_and_malformed_html_ingests(
    session: Session,
) -> None:
    source = make_source(session)
    page = make_page(
        '<link rel="canonical" href="https://unrelated.example/page">'
        "<title>Broken <p>but useful",
        "https://example.edu/learn/broken",
    )

    document = DocumentIngestor(DocumentRepository(session)).ingest(page, source)

    assert document.canonical_url == "https://example.edu/learn/broken"
    assert document.title == "Broken but useful"
    assert document.content_hash is not None


def test_seed_source_metadata_is_not_arbitrarily_collapsed(session: Session) -> None:
    source = SeedSourceRepository(session).create(
        SeedSourceCreate(
            name="Broad Source",
            start_url="https://broad.example.edu/",
            description="Broad educational materials.",
            source_type="open_education",
            education_levels=["School", "University"],
            subjects=["Science", "Mathematics"],
            allowed_url_prefixes=["https://broad.example.edu/"],
        )
    )

    document = DocumentIngestor(DocumentRepository(session)).ingest(
        make_page(url="https://broad.example.edu/lesson"),
        source,
    )

    assert document.source_type == "open_education"
    assert document.education_level is None
    assert document.subject is None


def test_end_to_end_mock_crawler_to_document_repository(session: Session) -> None:
    source = make_source(session)
    html = (
        "<html lang='en'><head><title>Mocked Lesson</title>"
        "<meta name='description' content='No network used'>"
        "</head><body><h1>Learning</h1><p>Persisted body.</p></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.edu/learn/")
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=html,
        )

    async def crawl_page():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await Crawler(
                CrawlerConfig(
                    max_pages=1,
                    request_delay=0,
                    respect_robots_txt=False,
                ),
                client=client,
            ).crawl(source)

    crawl_result = asyncio.run(crawl_page())
    repository = DocumentRepository(session)
    ingestor = DocumentIngestor(repository)
    documents = [ingestor.ingest(page, source) for page in crawl_result.pages]

    assert crawl_result.pages_fetched == 1
    assert len(documents) == 1
    stored = repository.get_by_url("https://example.edu/learn/")
    assert stored is not None
    assert stored.title == "Mocked Lesson"
    assert stored.description == "No network used"
    assert stored.body == "Learning\nPersisted body."
    assert stored.content_hash == documents[0].content_hash
