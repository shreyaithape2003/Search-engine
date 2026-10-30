from pathlib import Path

import pytest

from app.evaluation.dataset import EVALUATION_QUERIES
from app.evaluation.runner import render_report, run_evaluation
from app.services.search_service import SearchService


def test_offline_evaluation_is_repeatable_and_report_is_readable(
    monkeypatch,
) -> None:
    database_urls: list[str] = []
    import app.evaluation.runner as runner

    original_create_engine = runner.create_database_engine

    def record_database_url(database_url: str):
        database_urls.append(database_url)
        return original_create_engine(database_url)

    monkeypatch.setattr(runner, "create_database_engine", record_database_url)

    first = run_evaluation()
    second = run_evaluation()

    assert first == second
    assert first.document_count == 20
    assert first.judgment_count == 48
    assert len(first.per_query) == len(EVALUATION_QUERIES)
    assert len(database_urls) == 2
    assert all("edusearch-evaluation-" in url for url in database_urls)
    assert all(url.endswith("evaluation.sqlite3") for url in database_urls)
    assert all(
        not Path(url.removeprefix("sqlite:///")).exists()
        for url in database_urls
    )

    report = render_report(first)
    assert "EduSearch - Search Quality Evaluation" in report
    assert "Queries evaluated: 24" in report
    assert "Documents available: 20" in report
    assert "Relevance judgments: 48" in report
    assert "Precision@5:" in report
    assert "Recall@10:" in report
    assert "NDCG@10:" in report
    assert "q24 | graduate-level number theory" in report
    assert "n/a" in report
    assert "excluded from mean Recall" in report
    assert "NDCG is n/a when ideal gain is zero" in report


def test_filtered_evaluation_query_limits_retrieved_results_to_filter(
    monkeypatch,
) -> None:
    original_search = SearchService.search
    filtered_text = next(
        query.text
        for query in EVALUATION_QUERIES
        if query.query_id == "q08"
    )

    def checked_search(service, query, limit, filters=None):
        response = original_search(service, query, limit, filters)
        if query == filtered_text:
            assert filters is not None
            assert filters.education_level == "Professional"
            for result in response.results:
                document = service.document_repository.get_by_id(result.document_id)
                assert document is not None
                assert document.education_level == "Professional"
        return response

    monkeypatch.setattr(SearchService, "search", checked_search)
    report = run_evaluation()
    filtered_query = next(
        metric
        for metric in report.per_query
        if metric.query_id == "q08"
    )

    assert filtered_query.relevant_count == 2
    assert filtered_query.retrieved_count < report.document_count


def test_cli_exits_with_clear_error_for_invalid_dataset(monkeypatch) -> None:
    import app.evaluation.run as command
    import app.evaluation.runner as runner

    def reject_dataset(*_args) -> None:
        raise ValueError("invalid test dataset")

    monkeypatch.setattr(runner, "validate_dataset", reject_dataset)

    with pytest.raises(SystemExit, match="Evaluation failed: invalid test dataset"):
        command.main()
