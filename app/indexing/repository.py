from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

from app.indexing.models import (
    DocumentFieldStatistics,
    FieldStatisticsData,
    IndexPosting,
    PostingData,
    TermStatistics,
)
from app.indexing.tokenizer import tokenize


class IndexRepository:
    """Persistence operations for postings and index statistics."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_document_index(
        self,
        document_id: int,
        postings: list[PostingData],
        field_statistics: list[FieldStatisticsData],
    ) -> None:
        """Atomically replace one document's postings and field statistics."""
        try:
            self.session.execute(
                delete(IndexPosting).where(IndexPosting.document_id == document_id)
            )
            self.session.execute(
                delete(DocumentFieldStatistics).where(
                    DocumentFieldStatistics.document_id == document_id
                )
            )
            self.session.add_all(
                [
                    IndexPosting(
                        term=posting.term,
                        document_id=document_id,
                        field=posting.field,
                        term_frequency=posting.term_frequency,
                        positions=posting.positions,
                    )
                    for posting in postings
                ]
            )
            self.session.add_all(
                [
                    DocumentFieldStatistics(
                        document_id=stat.document_id,
                        field=stat.field,
                        document_length=stat.document_length,
                    )
                    for stat in field_statistics
                ]
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def delete_document_index(self, document_id: int) -> None:
        """Remove all index rows for a document."""
        try:
            self.session.execute(
                delete(IndexPosting).where(IndexPosting.document_id == document_id)
            )
            self.session.execute(
                delete(DocumentFieldStatistics).where(
                    DocumentFieldStatistics.document_id == document_id
                )
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def get_postings_for_term(self, term: str) -> list[IndexPosting]:
        tokens = tokenize(term)
        if len(tokens) != 1:
            return []
        statement = (
            select(IndexPosting)
            .where(IndexPosting.term == tokens[0])
            .order_by(IndexPosting.document_id, IndexPosting.field)
        )
        return list(self.session.scalars(statement).all())

    def get_document_statistics(self, document_id: int) -> dict[str, int]:
        statement = (
            select(
                DocumentFieldStatistics.field,
                DocumentFieldStatistics.document_length,
            )
            .where(DocumentFieldStatistics.document_id == document_id)
            .order_by(DocumentFieldStatistics.field)
        )
        return {
            field: length
            for field, length in self.session.execute(statement).all()
        }

    def get_term_statistics(self, term: str) -> TermStatistics:
        tokens = tokenize(term)
        normalized_term = tokens[0] if len(tokens) == 1 else ""

        if normalized_term:
            statement = select(
                func.count(distinct(IndexPosting.document_id)),
                func.coalesce(func.sum(IndexPosting.term_frequency), 0),
            ).where(IndexPosting.term == normalized_term)
            document_frequency, collection_term_frequency = (
                self.session.execute(statement).one()
            )
        else:
            document_frequency = 0
            collection_term_frequency = 0

        indexed_document_count = self.session.scalar(
            select(func.count(distinct(DocumentFieldStatistics.document_id)))
        )
        return TermStatistics(
            term=normalized_term,
            document_frequency=document_frequency,
            collection_term_frequency=collection_term_frequency,
            indexed_document_count=indexed_document_count or 0,
        )
