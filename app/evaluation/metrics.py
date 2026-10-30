import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

RELEVANT_GRADE = 2


@dataclass(frozen=True)
class QueryMetrics:
    query_id: str
    retrieved_count: int
    relevant_count: int
    precision_at_5: float
    precision_at_10: float
    recall_at_5: float | None
    recall_at_10: float | None
    reciprocal_rank: float
    ndcg_at_5: float | None
    ndcg_at_10: float | None


@dataclass(frozen=True)
class AggregateMetrics:
    query_count: int
    precision_at_5: float
    precision_at_10: float
    recall_at_5: float | None
    recall_at_10: float | None
    mean_reciprocal_rank: float
    ndcg_at_5: float | None
    ndcg_at_10: float | None
    recall_query_count: int
    ndcg_query_count: int


def _validate_k(k: int) -> None:
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer.")


def precision_at_k(
    retrieved: Sequence[str],
    relevance: Mapping[str, int],
    k: int,
) -> float:
    """Precision uses K as denominator, including when fewer than K are retrieved."""
    _validate_k(k)
    relevant_retrieved = sum(
        relevance.get(document_key, 0) >= RELEVANT_GRADE
        for document_key in retrieved[:k]
    )
    return relevant_retrieved / k


def recall_at_k(
    retrieved: Sequence[str],
    relevance: Mapping[str, int],
    k: int,
) -> float | None:
    """Return None when the query has no known relevant judgments."""
    _validate_k(k)
    relevant_total = sum(grade >= RELEVANT_GRADE for grade in relevance.values())
    if relevant_total == 0:
        return None
    relevant_retrieved = sum(
        relevance.get(document_key, 0) >= RELEVANT_GRADE
        for document_key in retrieved[:k]
    )
    return relevant_retrieved / relevant_total


def reciprocal_rank(
    retrieved: Sequence[str],
    relevance: Mapping[str, int],
) -> float:
    """Return reciprocal rank of the first grade-2-or-better result."""
    for rank, document_key in enumerate(retrieved, start=1):
        if relevance.get(document_key, 0) >= RELEVANT_GRADE:
            return 1 / rank
    return 0.0


def ndcg_at_k(
    retrieved: Sequence[str],
    relevance: Mapping[str, int],
    k: int,
) -> float | None:
    """Compute graded NDCG; return None if no positive ideal gain exists."""
    _validate_k(k)
    ideal_grades = sorted(
        (grade for grade in relevance.values() if grade > 0),
        reverse=True,
    )[:k]
    ideal_dcg = _discounted_gain(ideal_grades)
    if ideal_dcg == 0:
        return None

    retrieved_grades = [
        relevance.get(document_key, 0) for document_key in retrieved[:k]
    ]
    return _discounted_gain(retrieved_grades) / ideal_dcg


def _discounted_gain(grades: Sequence[int]) -> float:
    return sum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(grades, start=1)
    )


def calculate_query_metrics(
    query_id: str,
    retrieved: Sequence[str],
    relevance: Mapping[str, int],
) -> QueryMetrics:
    """Calculate all per-query benchmark metrics."""
    relevant_count = sum(grade >= RELEVANT_GRADE for grade in relevance.values())
    return QueryMetrics(
        query_id=query_id,
        retrieved_count=len(retrieved),
        relevant_count=relevant_count,
        precision_at_5=precision_at_k(retrieved, relevance, 5),
        precision_at_10=precision_at_k(retrieved, relevance, 10),
        recall_at_5=recall_at_k(retrieved, relevance, 5),
        recall_at_10=recall_at_k(retrieved, relevance, 10),
        reciprocal_rank=reciprocal_rank(retrieved, relevance),
        ndcg_at_5=ndcg_at_k(retrieved, relevance, 5),
        ndcg_at_10=ndcg_at_k(retrieved, relevance, 10),
    )


def calculate_aggregate_metrics(
    metrics: Sequence[QueryMetrics],
) -> AggregateMetrics:
    """Average P and MRR over all queries; omit undefined recall and NDCG cases."""
    if not metrics:
        raise ValueError("At least one query metric is required.")

    recall_5 = [metric.recall_at_5 for metric in metrics if metric.recall_at_5 is not None]
    recall_10 = [
        metric.recall_at_10
        for metric in metrics
        if metric.recall_at_10 is not None
    ]
    ndcg_5 = [metric.ndcg_at_5 for metric in metrics if metric.ndcg_at_5 is not None]
    ndcg_10 = [
        metric.ndcg_at_10
        for metric in metrics
        if metric.ndcg_at_10 is not None
    ]

    return AggregateMetrics(
        query_count=len(metrics),
        precision_at_5=_mean(metric.precision_at_5 for metric in metrics),
        precision_at_10=_mean(metric.precision_at_10 for metric in metrics),
        recall_at_5=_mean_optional(recall_5),
        recall_at_10=_mean_optional(recall_10),
        mean_reciprocal_rank=_mean(metric.reciprocal_rank for metric in metrics),
        ndcg_at_5=_mean_optional(ndcg_5),
        ndcg_at_10=_mean_optional(ndcg_10),
        recall_query_count=len(recall_5),
        ndcg_query_count=len(ndcg_5),
    )


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else 0.0


def _mean_optional(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else None
