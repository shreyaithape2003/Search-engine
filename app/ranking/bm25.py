import math

from app.indexing.repository import IndexRepository
from app.indexing.tokenizer import tokenize
from app.ranking.models import BM25Config, RankedDocument

INDEXED_FIELDS = ("title", "headings", "description", "body")


class QueryLimitError(ValueError):
    """Raised when an otherwise valid query exceeds ranker resource limits."""


class BM25Ranker:
    """Rank matching indexed documents with field-aware Okapi BM25."""

    def __init__(
        self,
        repository: IndexRepository,
        config: BM25Config | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or BM25Config()

    def rank(self, query: str) -> list[RankedDocument]:
        """Return matching document IDs sorted by score, then by ID."""
        if not isinstance(query, str):
            raise TypeError("query must be a string.")
        if len(query) > self.config.maximum_query_length:
            raise QueryLimitError(
                "query exceeds the maximum length of "
                f"{self.config.maximum_query_length} characters."
            )

        query_terms = list(dict.fromkeys(tokenize(query)))
        if len(query_terms) > self.config.maximum_unique_terms:
            raise QueryLimitError(
                "query exceeds the maximum of "
                f"{self.config.maximum_unique_terms} unique terms."
            )
        if not query_terms:
            return []

        postings = self.repository.get_postings_for_terms(query_terms)
        if not postings:
            return []

        postings_by_term_field: dict[str, dict[str, dict[int, int]]] = {}
        candidates: set[int] = set()
        for posting in postings:
            if posting.term not in query_terms:
                raise ValueError("Index repository returned an unexpected query term.")
            if posting.field not in INDEXED_FIELDS:
                raise ValueError(
                    f"Unknown indexed field {posting.field!r} in a posting."
                )
            if posting.term_frequency <= 0:
                raise ValueError(
                    f"Non-positive term frequency found for term {posting.term!r}."
                )

            field_postings = postings_by_term_field.setdefault(
                posting.term, {}
            ).setdefault(posting.field, {})
            if posting.document_id in field_postings:
                raise ValueError(
                    "Duplicate term/document/field posting found in the index."
                )
            field_postings[posting.document_id] = posting.term_frequency
            candidates.add(posting.document_id)

        collection_statistics = self.repository.get_field_collection_statistics()
        if set(collection_statistics) != set(INDEXED_FIELDS):
            raise ValueError("Index field statistics are incomplete.")

        document_counts = {
            statistics.document_count
            for statistics in collection_statistics.values()
        }
        if len(document_counts) != 1:
            raise ValueError("Indexed document counts differ between fields.")
        if not document_counts or next(iter(document_counts)) <= 0:
            raise ValueError("Postings exist without indexed field statistics.")

        field_lengths_by_document = self.repository.get_field_statistics_for_terms(
            query_terms
        )
        if set(field_lengths_by_document) != candidates:
            raise ValueError("Candidate postings have incomplete field statistics.")
        for document_id, field_lengths in field_lengths_by_document.items():
            if set(field_lengths) != set(INDEXED_FIELDS):
                raise ValueError(
                    f"Field statistics are incomplete for document {document_id}."
                )
            if any(length < 0 for length in field_lengths.values()):
                raise ValueError(
                    f"Negative field length found for document {document_id}."
                )

        scores = {document_id: 0.0 for document_id in candidates}
        matched_terms: dict[int, set[str]] = {
            document_id: set() for document_id in candidates
        }
        weights = self.config.field_weights

        for term in query_terms:
            for field, document_frequencies in postings_by_term_field.get(
                term, {}
            ).items():
                field_collection = collection_statistics[field]
                document_count = field_collection.document_count
                document_frequency = len(document_frequencies)
                if document_frequency > document_count:
                    raise ValueError(
                        f"Document frequency exceeds collection size for {term!r} "
                        f"in field {field!r}."
                    )

                average_length = (
                    field_collection.total_document_length / document_count
                )
                if average_length <= 0:
                    raise ValueError(
                        f"Non-positive average document length for field {field!r}."
                    )

                inverse_document_frequency = math.log1p(
                    (document_count - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                for document_id, term_frequency in document_frequencies.items():
                    contribution = self._score_term(
                        term_frequency=term_frequency,
                        document_length=field_lengths_by_document[document_id][field],
                        average_document_length=average_length,
                        inverse_document_frequency=inverse_document_frequency,
                    )
                    weighted_contribution = contribution * weights[field]
                    total_score = scores[document_id] + weighted_contribution
                    if not math.isfinite(total_score):
                        raise ValueError("BM25 produced a non-finite score.")
                    scores[document_id] = total_score
                    matched_terms[document_id].add(term)

        ranked = [
            RankedDocument(
                document_id=document_id,
                score=score,
                matched_terms=tuple(
                    term for term in query_terms if term in matched_terms[document_id]
                ),
            )
            for document_id, score in scores.items()
        ]
        return sorted(ranked, key=lambda result: (-result.score, result.document_id))

    def _score_term(
        self,
        *,
        term_frequency: int,
        document_length: int,
        average_document_length: float,
        inverse_document_frequency: float,
    ) -> float:
        if document_length < 0:
            raise ValueError("Document length cannot be negative.")
        if average_document_length <= 0:
            raise ValueError("Average document length must be positive.")

        k1 = self.config.k1
        b = self.config.b
        denominator = term_frequency + k1 * (
            1 - b + b * document_length / average_document_length
        )
        score = (
            inverse_document_frequency
            * term_frequency
            * (k1 + 1)
            / denominator
        )
        if not math.isfinite(score):
            raise ValueError("BM25 produced a non-finite term score.")
        return score
