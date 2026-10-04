"""HTML extraction and persistence of crawled educational pages."""

from app.ingestion.document_ingestor import DocumentIngestor
from app.ingestion.html_extractor import HTMLContentExtractor
from app.ingestion.models import ExtractedDocument

__all__ = ["DocumentIngestor", "ExtractedDocument", "HTMLContentExtractor"]
