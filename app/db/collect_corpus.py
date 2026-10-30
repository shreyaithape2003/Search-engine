import argparse
import asyncio
from dataclasses import dataclass, field
import math

import httpx
from sqlalchemy.orm import Session

from app.crawler.config import CrawlerConfig
from app.crawler.crawler import Crawler
from app.crawler.models import CrawlIssue
from app.db.database import SessionLocal, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.seed_source_repository import SeedSourceRepository
from app.ingestion.document_ingestor import DocumentIngestor
from app.ingestion.html_extractor import HTMLContentExtractor
from app.ingestion.quality import educational_content_skip_reason
from app.models.seed_source import SeedSource

MAX_COLLECTION_PAGES = 100
MAX_COLLECTION_DEPTH = 5


@dataclass
class SourceCollectionStats:
    source_name: str
    attempted_urls: int = 0
    fetched_pages: int = 0
    accepted_pages: int = 0
    skipped_pages: int = 0
    failures: int = 0
    new_documents: int = 0
    duplicate_documents: int = 0
    issues: list[CrawlIssue] = field(default_factory=list)


def select_sources(
    sources: list[SeedSource],
    requested_names: list[str] | None = None,
) -> list[SeedSource]:
    """Select active sources by exact case-insensitive name."""
    ordered_sources = sorted(sources, key=lambda source: (source.priority, source.id))
    active_sources = [source for source in ordered_sources if source.active]
    if not requested_names:
        return active_sources

    selected: list[SeedSource] = []
    seen_ids: set[int] = set()
    for requested_name in requested_names:
        matches = [
            source
            for source in sources
            if source.name.casefold() == requested_name.strip().casefold()
        ]
        if not matches:
            raise ValueError(f"No seed source named {requested_name!r} exists.")
        if len(matches) > 1:
            raise ValueError(f"Seed source name {requested_name!r} is ambiguous.")
        source = matches[0]
        if not source.active:
            raise ValueError(f"Seed source {source.name!r} is inactive.")
        if source.id not in seen_ids:
            selected.append(source)
            seen_ids.add(source.id)
    return sorted(selected, key=lambda source: (source.priority, source.id))


async def collect_sources(
    session: Session,
    sources: list[SeedSource],
    config: CrawlerConfig,
    client: httpx.AsyncClient,
) -> list[SourceCollectionStats]:
    """Crawl selected sources and persist only useful extracted pages."""
    repository = DocumentRepository(session)
    extractor = HTMLContentExtractor()
    ingestor = DocumentIngestor(repository, extractor=extractor)
    summaries: list[SourceCollectionStats] = []

    for source in sources:
        stats = SourceCollectionStats(source_name=source.name)
        crawl_result = await Crawler(config=config, client=client).crawl(source)
        stats.attempted_urls = crawl_result.pages_visited
        stats.fetched_pages = crawl_result.pages_fetched
        stats.skipped_pages = crawl_result.pages_skipped
        stats.issues.extend(crawl_result.errors)
        stats.failures = sum(not issue.skipped for issue in crawl_result.errors)

        for page in crawl_result.pages:
            try:
                extracted = extractor.extract(page, source)
                skip_reason = educational_content_skip_reason(extracted)
                if skip_reason is not None:
                    stats.skipped_pages += 1
                    stats.issues.append(
                        CrawlIssue(
                            url=str(page.url),
                            reason=skip_reason,
                            skipped=True,
                        )
                    )
                    continue
                _, created = ingestor.ingest_extracted_with_status(
                    page,
                    source,
                    extracted,
                )
                stats.accepted_pages += 1
                if created:
                    stats.new_documents += 1
                else:
                    stats.duplicate_documents += 1
            except Exception as error:
                session.rollback()
                stats.failures += 1
                stats.issues.append(
                    CrawlIssue(
                        url=str(page.url),
                        reason=f"Document ingestion failed: {error}",
                    )
                )

        summaries.append(stats)
    return summaries


def _bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            result = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError("must be an integer") from error
        if not minimum <= result <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return result

    return parse


def _nonnegative_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if not math.isfinite(result) or result < 0:
        raise argparse.ArgumentTypeError("must be finite and zero or greater")
    return result


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect educational pages from curated SeedSources."
    )
    source_selection = parser.add_mutually_exclusive_group()
    source_selection.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="NAME",
        help="active source name; repeat to select multiple sources",
    )
    source_selection.add_argument(
        "--all-sources",
        action="store_true",
        help="explicitly select every active source for collection",
    )
    parser.add_argument(
        "--max-pages",
        type=_bounded_int(1, MAX_COLLECTION_PAGES),
        default=20,
        help=f"maximum pages per source, 1-{MAX_COLLECTION_PAGES} (default: 20)",
    )
    parser.add_argument(
        "--max-depth",
        type=_bounded_int(0, MAX_COLLECTION_DEPTH),
        default=2,
        help=f"maximum link depth, 0-{MAX_COLLECTION_DEPTH} (default: 2)",
    )
    parser.add_argument(
        "--request-delay",
        type=_nonnegative_float,
        default=1.0,
        help="minimum seconds between requests (default: 1; robots.txt may require more)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform network requests and persist accepted documents; otherwise preview only",
    )
    return parser


async def _run_collection(
    session: Session,
    sources: list[SeedSource],
    config: CrawlerConfig,
) -> list[SourceCollectionStats]:
    async with httpx.AsyncClient(follow_redirects=False) as client:
        return await collect_sources(session, sources, config, client)


def main(argv: list[str] | None = None) -> None:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    config = CrawlerConfig(
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        request_delay=args.request_delay,
        respect_robots_txt=True,
    )

    if args.execute and not args.sources and not args.all_sources:
        parser.error(
            "Live collection requires --source NAME or the explicit --all-sources option."
        )

    initialize_database()
    with SessionLocal() as session:
        sources = SeedSourceRepository(session).list(limit=500)
        try:
            selected_sources = select_sources(sources, args.sources)
        except ValueError as error:
            parser.error(str(error))

        if not selected_sources:
            parser.error(
                "No active seed sources are registered. Run "
                "'python -m app.db.seed_sources' first."
            )

        if not args.execute:
            print("Dry run: no network requests or documents were created.")
            for source in selected_sources:
                print(f"- {source.name}: {source.start_url}")
            print(
                f"Limits: {config.max_pages} pages/source, depth "
                f"{config.max_depth}, request delay {config.request_delay:g}s "
                "(robots.txt delays are also enforced)."
            )
            print("Use --execute to begin collection.")
            return

        summaries = asyncio.run(_run_collection(session, selected_sources, config))

    for summary in summaries:
        print(
            f"{summary.source_name}: attempted={summary.attempted_urls}, "
            f"fetched={summary.fetched_pages}, accepted={summary.accepted_pages}, "
            f"skipped={summary.skipped_pages}, failures={summary.failures}, "
            f"new={summary.new_documents}, duplicates={summary.duplicate_documents}"
        )
        for issue in summary.issues:
            outcome = "skipped" if issue.skipped else "failed"
            print(f"  {outcome}: {issue.url}: {issue.reason}")

    totals = {
        field_name: sum(getattr(summary, field_name) for summary in summaries)
        for field_name in (
            "attempted_urls",
            "fetched_pages",
            "accepted_pages",
            "skipped_pages",
            "failures",
            "new_documents",
            "duplicate_documents",
        )
    }
    print(
        "Total: "
        + ", ".join(f"{name}={value}" for name, value in totals.items())
    )


if __name__ == "__main__":
    main()
