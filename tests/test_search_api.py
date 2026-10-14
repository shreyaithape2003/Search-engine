from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.search import get_search_service
from app.db.database import Base, create_database_engine, get_session, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.indexing.indexer import DocumentIndexer
from app.indexing.repository import IndexRepository
from app.main import app
from app.models.document import Document
from app.ranking.bm25 import BM25Ranker
from app.ranking.models import RankedDocument
from app.schemas.document import DocumentCreate
from app.services.search_service import SearchService


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'search_api.db').as_posix()}"
    )
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Iterator[Session]:
    initialize_database(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_search_service, None)


def add_document(
    session: Session,
    url: str,
    **fields: Any,
) -> Document:
    return DocumentRepository(session).create(DocumentCreate(url=url, **fields))


def index_documents(session: Session, *documents: Document) -> IndexRepository:
    repository = IndexRepository(session)
    indexer = DocumentIndexer(repository)
    for document in documents:
        indexer.index_document(document)
    return repository


def test_search_endpoint_returns_bm25_ranked_search_results(
    client: TestClient,
    session: Session,
) -> None:
    first = add_document(
        session,
        "https://search-one.edu/",
        title="python python programming",
        description="Programming lessons",
        body="Private full document body should not be returned.",
    )
    second = add_document(
        session,
        "https://search-two.edu/",
        title="python programming",
        description="Python material",
    )
    repository = index_documents(session, first, second)
    expected_ranking = BM25Ranker(repository).rank("Python")

    response = client.get("/api/v1/search", params={"q": "Python"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Python"
    assert payload["total"] == 2
    assert [result["document_id"] for result in payload["results"]] == [
        ranked.document_id for ranked in expected_ranking
    ]
    assert [result["score"] for result in payload["results"]] == pytest.approx(
        [ranked.score for ranked in expected_ranking]
    )
    assert payload["results"][0]["matched_terms"] == ["python"]
    assert set(payload["results"][0]) == {
        "document_id",
        "title",
        "url",
        "description",
        "snippet",
        "score",
        "matched_terms",
    }
    assert "body" not in payload["results"][0]
    assert "Private full document body" not in response.text


def test_search_response_includes_a_relevant_bounded_snippet(
    client: TestClient,
    session: Session,
) -> None:
    document = add_document(
        session,
        "https://snippet.edu/",
        title="Astronomy",
        description="An unrelated introduction.",
        headings=["Observing the night sky"],
        body="Astronomy studies stars, planets, and other objects in space. " * 8,
    )
    index_documents(session, document)

    response = client.get("/api/v1/search", params={"q": "astronomy"})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert "Astronomy" in result["snippet"]
    assert len(result["snippet"]) <= 240
    assert result["snippet"] != document.body
    assert result["description"] == document.description
    assert result["title"] == document.title
    assert "body" not in result
    assert result["score"] > 0
    assert result["matched_terms"] == ["astronomy"]


def test_search_snippet_keeps_script_like_content_as_json_text(
    client: TestClient,
    session: Session,
) -> None:
    document = add_document(
        session,
        "https://untrusted-snippet.edu/",
        title="Markup",
        body="<script>alert('unsafe')</script> lesson",
    )
    index_documents(session, document)

    response = client.get("/api/v1/search", params={"q": "lesson"})

    assert response.status_code == 200
    assert response.json()["results"][0]["snippet"] == document.body


def test_search_supports_multiword_query_and_preserves_query(
    client: TestClient,
    session: Session,
) -> None:
    document = add_document(
        session,
        "https://machine-learning.edu/",
        title="Machine Learning",
    )
    index_documents(session, document)

    response = client.get(
        "/api/v1/search",
        params={"q": "machine learning"},
    )

    assert response.status_code == 200
    assert response.json()["query"] == "machine learning"
    assert response.json()["results"][0]["matched_terms"] == [
        "machine",
        "learning",
    ]


def test_default_and_custom_limits_are_respected(
    client: TestClient,
    session: Session,
) -> None:
    documents = [
        add_document(
            session,
            f"https://limit-{number}.edu/",
            title="shared",
        )
        for number in range(12)
    ]
    index_documents(session, *documents)

    default_response = client.get("/api/v1/search", params={"q": "shared"})
    custom_response = client.get(
        "/api/v1/search",
        params={"q": "shared", "limit": 5},
    )

    assert default_response.status_code == 200
    assert len(default_response.json()["results"]) == 10
    assert default_response.json()["total"] == 10
    assert custom_response.status_code == 200
    assert len(custom_response.json()["results"]) == 5
    assert custom_response.json()["total"] == 5


@pytest.mark.parametrize("limit", [0, 51, -1])
def test_out_of_range_limit_is_rejected(
    client: TestClient,
    limit: int,
) -> None:
    response = client.get("/api/v1/search", params={"q": "python", "limit": limit})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "query",
    [
        "",
        " ",
        "\t",
        "\n",
        " \t\n ",
        "x" * 2001,
    ],
)
def test_empty_whitespace_and_overlong_queries_are_rejected(
    client: TestClient,
    query: str,
) -> None:
    response = client.get("/api/v1/search", params={"q": query})

    assert response.status_code == 422


def test_missing_query_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/search")

    assert response.status_code == 422


def test_ranker_unique_term_limit_is_returned_as_client_validation_error(
    client: TestClient,
) -> None:
    query = " ".join(f"term{number}" for number in range(101))

    response = client.get("/api/v1/search", params={"q": query})

    assert response.status_code == 422
    assert response.json()["detail"] == "Query exceeds supported search limits."


def test_unknown_query_returns_empty_success_response(
    client: TestClient,
    session: Session,
) -> None:
    document = add_document(session, "https://unknown.edu/", title="python")
    index_documents(session, document)

    response = client.get(
        "/api/v1/search",
        params={"q": "somethingthatdoesnotexist"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "somethingthatdoesnotexist",
        "results": [],
        "total": 0,
    }


def test_valid_query_with_no_indexed_documents_returns_empty_response(
    client: TestClient,
    session: Session,
) -> None:
    add_document(session, "https://not-indexed.edu/", title="python")

    response = client.get("/api/v1/search", params={"q": "python"})

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["total"] == 0


def test_search_bulk_fetches_only_top_limited_ids_once(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = [
        add_document(
            session,
            f"https://bulk-{number}.edu/",
            title="shared",
        )
        for number in range(8)
    ]
    index_documents(session, *documents)
    original_get_by_ids = DocumentRepository.get_by_ids
    calls: list[list[int]] = []

    def get_by_ids_spy(
        repository: DocumentRepository,
        document_ids: list[int],
    ) -> list[Document]:
        calls.append(document_ids)
        return original_get_by_ids(repository, document_ids)

    def disallow_list(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Search must not list or scan documents.")

    monkeypatch.setattr(DocumentRepository, "get_by_ids", get_by_ids_spy)
    monkeypatch.setattr(DocumentRepository, "list", disallow_list)

    response = client.get(
        "/api/v1/search",
        params={"q": "shared", "limit": 3},
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert len(calls[0]) == 3


def test_missing_ranked_document_is_skipped_safely(
    client: TestClient,
    session: Session,
) -> None:
    existing = add_document(
        session,
        "https://existing-ranked.edu/",
        title="python",
    )
    repository = DocumentRepository(session)
    fake_ranker = Mock()
    fake_ranker.rank.return_value = [
        RankedDocument(99999, 10.0, ("python",)),
        RankedDocument(existing.id, 5.0, ("python",)),
    ]
    app.dependency_overrides[get_search_service] = lambda: SearchService(
        fake_ranker,
        repository,
    )

    response = client.get("/api/v1/search", params={"q": "python"})

    assert response.status_code == 200
    assert [result["document_id"] for result in response.json()["results"]] == [
        existing.id
    ]
    assert response.json()["total"] == 1


def test_unindexed_and_deleted_documents_do_not_appear(
    client: TestClient,
    session: Session,
) -> None:
    indexed = add_document(
        session,
        "https://indexed.edu/",
        title="shared",
    )
    deleted = add_document(
        session,
        "https://deleted-indexed.edu/",
        title="shared",
    )
    not_indexed = add_document(
        session,
        "https://not-indexed.edu/",
        title="shared",
    )
    repository = index_documents(session, indexed, deleted)
    DocumentRepository(session).delete(deleted.id)

    response = client.get("/api/v1/search", params={"q": "shared"})

    assert response.status_code == 200
    result_ids = [result["document_id"] for result in response.json()["results"]]
    assert result_ids == [indexed.id]
    assert deleted.id not in result_ids
    assert not_indexed.id not in result_ids


def test_equal_scores_keep_deterministic_document_id_order(
    client: TestClient,
    session: Session,
) -> None:
    documents = [
        add_document(
            session,
            f"https://tie-api-{number}.edu/",
            title="identical term",
        )
        for number in range(3)
    ]
    index_documents(session, *documents)

    response = client.get("/api/v1/search", params={"q": "identical"})

    assert response.status_code == 200
    assert [result["document_id"] for result in response.json()["results"]] == sorted(
        document.id for document in documents
    )


def test_unexpected_internal_error_does_not_leak_details(client: TestClient) -> None:
    failing_service = Mock()
    failing_service.search.side_effect = RuntimeError(
        "sqlite:///private/files/secret.db"
    )
    app.dependency_overrides[get_search_service] = lambda: failing_service

    response = client.get("/api/v1/search", params={"q": "python"})

    assert response.status_code == 500
    assert "secret.db" not in response.text
    assert "RuntimeError" not in response.text


def test_search_does_not_require_document_title(
    client: TestClient,
    session: Session,
) -> None:
    document = add_document(
        session,
        "https://nullable-title.edu/",
        body="python",
    )
    index_documents(session, document)

    response = client.get("/api/v1/search", params={"q": "python"})

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] is None
    assert response.json()["results"][0]["url"] == document.url
