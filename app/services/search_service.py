from sqlalchemy.orm import Session

from app.db.repositories.document_repository import DocumentRepository
from app.indexing.repository import IndexRepository
from app.models.document import Document
from app.ranking.bm25 import BM25Ranker
from app.ranking.models import RankedDocument
from app.schemas.search import SearchResponse, SearchResult
from app.services.snippet_generator import SnippetGenerator


class SearchService:
    """Coordinate BM25 ranking and bulk document retrieval."""

    def __init__(
        self,
        ranker: BM25Ranker,
        document_repository: DocumentRepository,
    ) -> None:
        self.ranker = ranker
        self.document_repository = document_repository
        self.snippet_generator = SnippetGenerator()

    def search(self, query: str, limit: int) -> SearchResponse:
        ranked_documents = self.ranker.rank(query)[:limit]
        if not ranked_documents:
            return SearchResponse(query=query, results=[], total=0)

        documents = self.document_repository.get_by_ids(
            [result.document_id for result in ranked_documents]
        )
        documents_by_id = {document.id: document for document in documents}
        results = [
            self._to_result(
                ranked_document,
                documents_by_id[ranked_document.document_id],
                query,
            )
            for ranked_document in ranked_documents
            if ranked_document.document_id in documents_by_id
        ]
        return SearchResponse(query=query, results=results, total=len(results))

    def _to_result(
        self,
        ranked_document: RankedDocument,
        document: Document,
        query: str,
    ) -> SearchResult:
        return SearchResult(
            document_id=ranked_document.document_id,
            title=document.title,
            url=document.url,
            description=document.description,
            snippet=self.snippet_generator.generate(
                query,
                description=document.description,
                headings=document.headings,
                body=document.body,
            ),
            score=ranked_document.score,
            matched_terms=list(ranked_document.matched_terms),
        )


def create_search_service(session: Session) -> SearchService:
    """Build request-scoped repositories and ranker for one SQLAlchemy session."""
    return SearchService(
        ranker=BM25Ranker(IndexRepository(session)),
        document_repository=DocumentRepository(session),
    )
