from dataclasses import replace

import pytest

from app.evaluation.dataset import (
    EVALUATION_QUERIES,
    FIXTURE_DOCUMENTS,
    EvaluationQuery,
    RelevanceJudgment,
    validate_dataset,
)
from app.evaluation.metrics import (
    QueryMetrics,
    calculate_aggregate_metrics,
    calculate_query_metrics,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.schemas.search import SearchFilters


def test_precision_at_k_uses_k_denominator_for_short_and_empty_lists() -> None:
    labels = {"relevant": 3, "weak": 1}

    assert precision_at_k(["relevant", "weak"], labels, 5) == pytest.approx(0.2)
    assert precision_at_k(["relevant"], labels, 1) == 1
    assert precision_at_k(["weak"], labels, 5) == 0
    assert precision_at_k([], labels, 5) == 0


def test_recall_at_k_and_zero_relevant_behavior() -> None:
    labels = {"first": 2, "second": 3, "weak": 1}

    assert recall_at_k(["weak", "second"], labels, 2) == pytest.approx(0.5)
    assert recall_at_k(["first", "second"], labels, 2) == 1
    assert recall_at_k([], {"weak": 1}, 5) is None


def test_reciprocal_rank_handles_first_later_and_missing_relevant() -> None:
    labels = {"first": 2, "second": 3}

    assert reciprocal_rank(["first", "second"], labels) == 1
    assert reciprocal_rank(["other", "second"], labels) == pytest.approx(0.5)
    assert reciprocal_rank(["other"], labels) == 0
    assert reciprocal_rank([], labels) == 0


def test_ndcg_ideal_reversed_partial_and_zero_gain_rankings() -> None:
    labels = {"high": 3, "medium": 2, "weak": 1}

    assert ndcg_at_k(["high", "medium", "weak"], labels, 3) == pytest.approx(1)
    assert ndcg_at_k(["medium", "high", "weak"], labels, 3) < 1
    assert ndcg_at_k(["high", "irrelevant"], labels, 2) == pytest.approx(
        7 / (7 + 3 / 1.584962500721156)
    )
    assert ndcg_at_k(["irrelevant"], {"irrelevant": 0}, 5) is None
    assert ndcg_at_k([], {}, 5) is None


def test_query_and_aggregate_metrics_keep_zero_relevance_queries_visible() -> None:
    relevant = calculate_query_metrics(
        "q1",
        ["doc-a", "doc-b"],
        {"doc-a": 3, "doc-b": 0},
    )
    no_relevant = calculate_query_metrics("q2", [], {})
    aggregate = calculate_aggregate_metrics([relevant, no_relevant])

    assert relevant.precision_at_5 == pytest.approx(0.2)
    assert relevant.recall_at_5 == 1
    assert relevant.ndcg_at_5 == 1
    assert no_relevant.precision_at_5 == 0
    assert no_relevant.recall_at_5 is None
    assert no_relevant.reciprocal_rank == 0
    assert no_relevant.ndcg_at_5 is None
    assert aggregate.query_count == 2
    assert aggregate.precision_at_5 == pytest.approx(0.1)
    assert aggregate.recall_at_5 == 1
    assert aggregate.mean_reciprocal_rank == pytest.approx(0.5)
    assert aggregate.recall_query_count == 1
    assert aggregate.ndcg_query_count == 1


def test_aggregate_requires_at_least_one_query_metric() -> None:
    with pytest.raises(ValueError, match="At least one"):
        calculate_aggregate_metrics([])


def test_aggregate_reports_undefined_metrics_when_all_queries_are_unjudged() -> None:
    aggregate = calculate_aggregate_metrics(
        [calculate_query_metrics("q1", [], {})]
    )

    assert aggregate.recall_at_5 is None
    assert aggregate.ndcg_at_5 is None
    assert aggregate.recall_query_count == 0
    assert aggregate.ndcg_query_count == 0


def test_metrics_reject_nonpositive_or_noninteger_cutoffs() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        precision_at_k([], {}, 0)
    with pytest.raises(ValueError, match="positive integer"):
        recall_at_k([], {}, True)


def test_benchmark_dataset_has_24_queries_and_48_judgments() -> None:
    validate_dataset()

    assert len(EVALUATION_QUERIES) == 24
    assert sum(len(query.judgments) for query in EVALUATION_QUERIES) == 48
    assert len(FIXTURE_DOCUMENTS) == 20
    assert any(not any(j.grade >= 2 for j in q.judgments) for q in EVALUATION_QUERIES)


@pytest.mark.parametrize(
    ("modified", "message"),
    [
        (
            lambda query: query,
            "Duplicate evaluation query ID",
        ),
        (
            lambda query: replace(query, text=" \t "),
            "empty query text",
        ),
        (
            lambda query: replace(
                query,
                judgments=(RelevanceJudgment("mit_algorithms", 4),),
            ),
            "invalid relevance grade",
        ),
        (
            lambda query: replace(
                query,
                judgments=(RelevanceJudgment("unknown_fixture", 3),),
            ),
            "unknown fixture document key",
        ),
        (
            lambda query: replace(
                query,
                judgments=(
                    RelevanceJudgment("mit_algorithms", 3),
                    RelevanceJudgment("mit_algorithms", 1),
                ),
            ),
            "duplicate judgment",
        ),
        (
            lambda query: replace(
                query,
                filters=SearchFilters(education_level="General"),
            ),
            "non-canonical education_level",
        ),
    ],
)
def test_dataset_validation_rejects_invalid_cases(
    modified,
    message: str,
) -> None:
    queries = list(EVALUATION_QUERIES)
    if message == "Duplicate evaluation query ID":
        queries[1] = replace(
            queries[1],
            query_id=EVALUATION_QUERIES[0].query_id,
        )
    else:
        queries[0] = modified(queries[0])

    with pytest.raises(ValueError, match=message):
        validate_dataset(queries)


def test_dataset_validation_rejects_missing_education_level_coverage() -> None:
    queries = [
        query for query in EVALUATION_QUERIES
        if query.filters is None or query.filters.education_level != "Research"
    ]

    with pytest.raises(ValueError, match="Research"):
        validate_dataset(queries)


def test_dataset_validation_accepts_queries_with_no_relevant_judgments() -> None:
    validate_dataset()
    no_relevant = [
        query
        for query in EVALUATION_QUERIES
        if not any(judgment.grade >= 2 for judgment in query.judgments)
    ]

    assert len(no_relevant) >= 2
