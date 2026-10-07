from collections import defaultdict

from app.indexing.models import FieldStatisticsData, PostingData
from app.indexing.repository import IndexRepository
from app.indexing.tokenizer import tokenize
from app.models.document import Document

INDEXED_FIELDS = ("title", "description", "headings", "body")


class DocumentIndexer:
    """Build and persist field-aware postings for a stored Document."""

    def __init__(self, repository: IndexRepository) -> None:
        self.repository = repository

    def index_document(self, document: Document) -> int:
        """Replace the index for a document and return the posting count."""
        if document.id is None:
            raise ValueError("Only persisted documents can be indexed.")

        fields = {
            "title": document.title,
            "description": document.description,
            "headings": " ".join(document.headings or []),
            "body": document.body,
        }
        postings: list[PostingData] = []
        statistics: list[FieldStatisticsData] = []

        for field in INDEXED_FIELDS:
            tokens = tokenize(fields[field])
            positions_by_term: dict[str, list[int]] = defaultdict(list)
            for position, term in enumerate(tokens):
                positions_by_term[term].append(position)

            statistics.append(
                FieldStatisticsData(
                    document_id=document.id,
                    field=field,
                    document_length=len(tokens),
                )
            )
            postings.extend(
                PostingData(
                    term=term,
                    document_id=document.id,
                    field=field,
                    term_frequency=len(positions),
                    positions=positions,
                )
                for term, positions in sorted(positions_by_term.items())
            )

        self.repository.replace_document_index(document.id, postings, statistics)
        return len(postings)
