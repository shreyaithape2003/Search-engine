from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypeAlias

from sqlalchemy.orm import sessionmaker

from app.db.build_index import build_development_index
from app.db.database import create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.evaluation.dataset import (
    EVALUATION_QUERIES,
    FIXTURE_DOCUMENTS,
    EvaluationQuery,
    relevance_by_key,
    validate_dataset,
)
from app.evaluation.metrics import (
    AggregateMetrics,
    QueryMetrics,
    calculate_aggregate_metrics,
    calculate_query_metrics,
)
from app.schemas.document import DocumentCreate
from app.services.search_service import create_search_service

RankingCallable: TypeAlias = Callable[[EvaluationQuery], Sequence[str]]


@dataclass(frozen=True)
class EvaluationReport:
    document_count: int
    judgment_count: int
    per_query: tuple[QueryMetrics, ...]
    aggregate: AggregateMetrics


def evaluate_queries(
    queries: Sequence[EvaluationQuery],
    search: RankingCallable,
) -> tuple[QueryMetrics, ...]:
    """Evaluate rankings returned by an adapter without owning ranking logic."""
    return tuple(
        calculate_query_metrics(
            query.query_id,
            search(query),
            relevance_by_key(query),
        )
        for query in queries
    )


def run_evaluation(
    queries: Sequence[EvaluationQuery] = EVALUATION_QUERIES,
    fixture_documents: dict[str, DocumentCreate] = FIXTURE_DOCUMENTS,
) -> EvaluationReport:
    """Build and evaluate a fresh temporary database without touching local data."""
    validate_dataset(list(queries), fixture_documents)
    if not fixture_documents:
        raise ValueError("Evaluation fixture corpus must contain documents.")

    with TemporaryDirectory(prefix="edusearch-evaluation-") as directory:
        database_path = Path(directory) / "evaluation.sqlite3"
        database_url = f"sqlite:///{database_path.as_posix()}"
        engine = create_database_engine(database_url)
        try:
            initialize_database(engine)
            session_factory = sessionmaker(
                bind=engine,
                autoflush=False,
                expire_on_commit=False,
            )
            with session_factory() as session:
                repository = DocumentRepository(session)
                fixture_id_to_key: dict[int, str] = {}
                for fixture_key, document_data in fixture_documents.items():
                    document = repository.create(document_data)
                    if document.id is None:
                        raise RuntimeError(
                            f"Evaluation fixture {fixture_key!r} was not persisted."
                        )
                    fixture_id_to_key[document.id] = fixture_key

                build_development_index(session)
                search_service = create_search_service(session)
                limit = len(fixture_documents)

                def search(query: EvaluationQuery) -> Sequence[str]:
                    response = search_service.search(
                        query.text,
                        limit,
                        query.filters,
                    )
                    ranked_keys: list[str] = []
                    for result in response.results:
                        fixture_key = fixture_id_to_key.get(result.document_id)
                        if fixture_key is None:
                            raise RuntimeError(
                                "Search returned a document outside the evaluation "
                                f"fixture: {result.document_id}."
                            )
                        ranked_keys.append(fixture_key)
                    return tuple(ranked_keys)

                per_query = evaluate_queries(queries, search)
                aggregate = calculate_aggregate_metrics(per_query)
                judgment_count = sum(len(query.judgments) for query in queries)
                return EvaluationReport(
                    document_count=len(fixture_documents),
                    judgment_count=judgment_count,
                    per_query=per_query,
                    aggregate=aggregate,
                )
        finally:
            engine.dispose()


def _metric_text(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def render_report(
    report: EvaluationReport,
    queries: Sequence[EvaluationQuery] = EVALUATION_QUERIES,
) -> str:
    """Render a deterministic plain-text summary and per-query report."""
    query_by_id = {query.query_id: query for query in queries}
    aggregate = report.aggregate
    lines = [
        "EduSearch - Search Quality Evaluation",
        "",
        "Dataset:",
        f"- Queries evaluated: {aggregate.query_count}",
        f"- Documents available: {report.document_count}",
        f"- Relevance judgments: {report.judgment_count}",
        "",
        "Aggregate metrics:",
        f"- Precision@5: {aggregate.precision_at_5:.4f}",
        f"- Precision@10: {aggregate.precision_at_10:.4f}",
        (
            f"- Recall@5: {_metric_text(aggregate.recall_at_5)} "
            f"(mean over {aggregate.recall_query_count} queries with relevant judgments)"
        ),
        (
            f"- Recall@10: {_metric_text(aggregate.recall_at_10)} "
            f"(mean over {aggregate.recall_query_count} queries with relevant judgments)"
        ),
        f"- MRR: {aggregate.mean_reciprocal_rank:.4f}",
        (
            f"- NDCG@5: {_metric_text(aggregate.ndcg_at_5)} "
            f"(mean over {aggregate.ndcg_query_count} queries with positive ideal gain)"
        ),
        (
            f"- NDCG@10: {_metric_text(aggregate.ndcg_at_10)} "
            f"(mean over {aggregate.ndcg_query_count} queries with positive ideal gain)"
        ),
        "",
        "Per-query results:",
        (
            "ID | Query | Retrieved | Relevant | P@5 | P@10 | Recall@5 | "
            "Recall@10 | RR | NDCG@5 | NDCG@10"
        ),
        "---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:",
    ]

    for metric in report.per_query:
        query = query_by_id[metric.query_id]
        lines.append(
            " | ".join(
                (
                    metric.query_id,
                    query.text,
                    str(metric.retrieved_count),
                    str(metric.relevant_count),
                    f"{metric.precision_at_5:.4f}",
                    f"{metric.precision_at_10:.4f}",
                    _metric_text(metric.recall_at_5),
                    _metric_text(metric.recall_at_10),
                    f"{metric.reciprocal_rank:.4f}",
                    _metric_text(metric.ndcg_at_5),
                    _metric_text(metric.ndcg_at_10),
                )
            )
        )
    lines.extend(
        (
            "",
            "P@K uses K as its denominator even when fewer results are returned.",
            "Queries with no binary relevant judgments score zero for P@K and MRR",
            "and are excluded from mean Recall; NDCG is n/a when ideal gain is zero.",
        )
    )
    return "\n".join(lines)
