from app.crawler.models import CrawlPage
from app.crawler.url_utils import normalize_url
from app.db.repositories.document_repository import (
    DocumentRepository,
    DuplicateDocumentError,
)
from app.ingestion.html_extractor import HTMLContentExtractor
from app.models.document import Document
from app.models.seed_source import SeedSource
from app.schemas.document import DocumentCreate


class DocumentIngestor:
    """Extract crawled HTML and persist it through DocumentRepository."""

    def __init__(
        self,
        repository: DocumentRepository,
        extractor: HTMLContentExtractor | None = None,
    ) -> None:
        self.repository = repository
        self.extractor = extractor or HTMLContentExtractor()

    def ingest(self, page: CrawlPage, source: SeedSource) -> Document:
        """Convert one crawler page to a Document, idempotently by its URLs."""
        extracted = self.extractor.extract(page, source)
        document_data = DocumentCreate(
            url=normalize_url(str(page.url)),
            canonical_url=str(extracted.canonical_url),
            title=extracted.title,
            description=extracted.description,
            body=extracted.body,
            headings=extracted.headings,
            author=extracted.author,
            publisher=extracted.publisher,
            language=extracted.language,
            published_at=extracted.published_at,
            source_updated_at=extracted.source_updated_at,
            source_type=source.source_type,
            subject=source.subjects[0] if len(source.subjects) == 1 else None,
            education_level=(
                source.education_levels[0]
                if len(source.education_levels) == 1
                else None
            ),
            content_type=extracted.content_type,
            content_hash=extracted.content_hash,
        )

        try:
            return self.repository.create(document_data)
        except DuplicateDocumentError:
            existing = self.repository.get_by_url(document_data.url)
            if existing is None and document_data.canonical_url is not None:
                existing = self.repository.get_by_canonical_url(
                    document_data.canonical_url
                )
            if existing is not None:
                return existing
            raise
