from app.classification.classifier import EducationalClassifier
from app.classification.models import ClassificationInput
from app.crawler.models import CrawlPage
from app.crawler.url_utils import normalize_url
from app.db.repositories.document_repository import (
    DocumentRepository,
    DuplicateDocumentError,
)
from app.ingestion.html_extractor import HTMLContentExtractor
from app.ingestion.models import ExtractedDocument
from app.models.document import Document
from app.models.seed_source import SeedSource
from app.schemas.document import DocumentCreate


def _source_categories(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values[:100] if isinstance(value, str)]


class DocumentIngestor:
    """Extract crawled HTML and persist it through DocumentRepository."""

    def __init__(
        self,
        repository: DocumentRepository,
        extractor: HTMLContentExtractor | None = None,
        classifier: EducationalClassifier | None = None,
    ) -> None:
        self.repository = repository
        self.extractor = extractor or HTMLContentExtractor()
        self.classifier = classifier or EducationalClassifier()

    def ingest(self, page: CrawlPage, source: SeedSource) -> Document:
        """Convert one crawler page to a Document, idempotently by its URLs."""
        extracted = self.extractor.extract(page, source)
        return self.ingest_extracted(page, source, extracted)

    def ingest_extracted(
        self,
        page: CrawlPage,
        source: SeedSource,
        extracted: ExtractedDocument,
    ) -> Document:
        """Persist content already extracted and quality-checked by a collector."""
        return self.ingest_extracted_with_status(page, source, extracted)[0]

    def ingest_extracted_with_status(
        self,
        page: CrawlPage,
        source: SeedSource,
        extracted: ExtractedDocument,
    ) -> tuple[Document, bool]:
        """Return the document and whether this call created it."""
        classification = self.classifier.classify(
            ClassificationInput(
                url=str(page.url),
                title=extracted.title,
                description=(
                    extracted.description[:5000]
                    if extracted.description is not None
                    else None
                ),
                headings=extracted.headings[:100],
                body=extracted.body,
                document_subject=None,
                document_education_level=None,
                document_content_type=extracted.content_type,
                seed_source_type=source.source_type,
                seed_subjects=_source_categories(source.subjects),
                seed_education_levels=_source_categories(source.education_levels),
            )
        )
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
            subject=classification.subject,
            education_level=classification.education_level,
            content_type=classification.content_type,
            difficulty=classification.difficulty,
            classification_provenance={
                field: evidence.model_dump()
                for field, evidence in classification.provenance.items()
            },
            content_hash=extracted.content_hash,
        )

        existing = self._find_existing_document(document_data)
        if existing is not None:
            return existing, False

        try:
            return self.repository.create(document_data), True
        except DuplicateDocumentError:
            existing = self._find_existing_document(document_data)
            if existing is not None:
                return existing, False
            raise

    def _find_existing_document(
        self,
        document_data: DocumentCreate,
    ) -> Document | None:
        for candidate_url in (document_data.url, document_data.canonical_url):
            if candidate_url is None:
                continue
            existing = self.repository.get_by_url(candidate_url)
            if existing is not None:
                return existing
            existing = self.repository.get_by_canonical_url(candidate_url)
            if existing is not None:
                return existing
        return None
