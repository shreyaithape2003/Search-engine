from collections.abc import Iterator
from math import isfinite, log
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, create_database_engine, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.indexing.indexer import DocumentIndexer
from app.indexing.models import (
    DocumentFieldStatistics,
    FieldCollectionStatistics,
    IndexPosting,
)
from app.indexing.repository import IndexRepository
from app.models.document import Document
from app.ranking.bm25 import BM25Ranker
from app.ranking.models import BM25Config
from app.schemas.document import DocumentCreate, DocumentUpdate


@pytest.fixture
def test_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'bm25.db').as_posix()}")
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Iterator[Session]:
    initialize_database(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


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


def test_bm25_configuration_defaults_and_custom_values() -> None:
    defaults = BM25Config()
    assert defaults.k1 == 1.2
    assert defaults.b == 0.75
    assert defaults.field_weights == {
        "title": 4.0,
        "headings": 2.5,
        "description": 2.0,
        "body": 1.0,
    }

    custom = BM25Config(
        k1=1.8,
        b=0.4,
        title_weight=5,
        headings_weight=3,
        description_weight=1.5,
        body_weight=0.5,
    )
    assert custom.k1 == 1.8
    assert custom.b == 0.4
    assert custom.field_weights["title"] == 5
    assert custom.field_weights["body"] == 0.5


@pytest.mark.parametrize(
    "configuration",
    [
        {"k1": 0},
        {"k1": -1},
        {"k1": float("inf")},
        {"b": -0.01},
        {"b": 1.01},
        {"b": float("nan")},
        {"title_weight": -0.01},
        {"headings_weight": -1},
        {"description_weight": float("inf")},
        {"body_weight": -0.5},
        {"maximum_query_length": 0},
        {"maximum_unique_terms": 0},
    ],
)
def test_invalid_bm25_configuration_is_rejected(
    configuration: dict[str, float | int],
) -> None:
    with pytest.raises(ValidationError):
        BM25Config(**configuration)


def test_empty_and_unknown_queries_return_no_results(session: Session) -> None:
    document = add_document(session, "https://empty-query.edu/", title="python")
    repository = index_documents(session, document)
    ranker = BM25Ranker(repository)

    assert ranker.rank(" \n\t ") == []
    assert ranker.rank("absent") == []


def test_query_size_and_unique_term_limits_are_explicit(session: Session) -> None:
    ranker = BM25Ranker(
        IndexRepository(session),
        BM25Config(maximum_query_length=20, maximum_unique_terms=2),
    )

    with pytest.raises(ValueError, match="maximum length"):
        ranker.rank("a" * 21)
    with pytest.raises(ValueError, match="unique terms"):
        ranker.rank("alpha beta gamma")


def test_single_term_ranking_matches_hand_calculated_bm25(session: Session) -> None:
    first = add_document(
        session,
        "https://single-one.edu/",
        title="alpha alpha",
    )
    second = add_document(
        session,
        "https://single-two.edu/",
        title="alpha",
    )
    ranker = BM25Ranker(index_documents(session, first, second))

    results = ranker.rank("ALPHA!")

    expected_idf = log(1 + (2 - 2 + 0.5) / (2 + 0.5))
    expected_first = expected_idf * (2 * (1.2 + 1)) / (
        2 + 1.2 * (1 - 0.75 + 0.75 * 2 / 1.5)
    )
    assert [result.document_id for result in results] == [first.id, second.id]
    assert results[0].score == pytest.approx(expected_first * 4.0)
    assert results[0].matched_terms == ("alpha",)


def test_rare_terms_receive_higher_idf_than_common_terms(session: Session) -> None:
    rare_document = add_document(
        session,
        "https://rare.edu/",
        title="common rare",
    )
    common_documents = [
        add_document(
            session,
            f"https://common-{number}.edu/",
            title="common",
        )
        for number in range(2)
    ]
    ranker = BM25Ranker(index_documents(session, rare_document, *common_documents))

    rare_score = ranker.rank("rare")[0].score
    common_score = next(
        result.score
        for result in ranker.rank("common")
        if result.document_id == rare_document.id
    )

    assert rare_score > common_score


def test_term_frequency_saturates_instead_of_growing_linearly(
    session: Session,
) -> None:
    document = add_document(session, "https://saturation.edu/", title="topic")
    repository = index_documents(session, document)
    ranker = BM25Ranker(repository)
    document_repository = DocumentRepository(session)

    score_at_one = ranker.rank("topic")[0].score
    for frequency in (10, 40):
        updated = document_repository.update(
            document.id,
            DocumentUpdate(title=" ".join(["topic"] * frequency)),
        )
        assert updated is not None
        DocumentIndexer(repository).index_document(updated)
        if frequency == 10:
            score_at_ten = ranker.rank("topic")[0].score
    score_at_forty = ranker.rank("topic")[0].score

    assert score_at_ten > score_at_one
    assert score_at_forty > score_at_ten
    assert score_at_ten - score_at_one > score_at_forty - score_at_ten


def test_length_normalization_prefers_shorter_document_for_equal_frequency(
    session: Session,
) -> None:
    short = add_document(session, "https://short.edu/", title="python")
    long = add_document(
        session,
        "https://long.edu/",
        title="python " + " ".join(["filler"] * 9),
    )
    results = BM25Ranker(index_documents(session, short, long)).rank("python")

    assert [result.document_id for result in results] == [short.id, long.id]
    assert results[0].score > results[1].score


def test_field_weights_determine_relative_field_match_ranking(
    session: Session,
) -> None:
    documents = [
        add_document(session, "https://title.edu/", title="shared"),
        add_document(session, "https://headings.edu/", headings=["shared"]),
        add_document(session, "https://description.edu/", description="shared"),
        add_document(session, "https://body.edu/", body="shared"),
    ]
    results = BM25Ranker(index_documents(session, *documents)).rank("shared")

    assert [result.document_id for result in results] == [
        documents[0].id,
        documents[1].id,
        documents[2].id,
        documents[3].id,
    ]


def test_multi_term_scores_accumulate_and_repeated_query_terms_do_not(
    session: Session,
) -> None:
    document = add_document(
        session,
        "https://multi-term.edu/",
        title="alpha beta",
    )
    ranker = BM25Ranker(index_documents(session, document))

    alpha = ranker.rank("alpha")[0]
    both = ranker.rank("alpha beta")[0]
    repeated = ranker.rank("alpha alpha alpha")[0]

    assert both.score == pytest.approx(alpha.score * 2)
    assert repeated.score == pytest.approx(alpha.score)
    assert both.matched_terms == ("alpha", "beta")


def test_empty_fields_and_all_document_terms_are_safe(session: Session) -> None:
    empty = add_document(session, "https://no-content.edu/")
    documents = [
        add_document(
            session,
            f"https://common-term-{number}.edu/",
            title="shared",
        )
        for number in range(2)
    ]
    repository = index_documents(session, empty, *documents)

    results = BM25Ranker(repository).rank("shared")

    assert {result.document_id for result in results} == {
        document.id for document in documents
    }
    assert all(isfinite(result.score) and result.score > 0 for result in results)


def test_equal_scores_use_ascending_document_id(session: Session) -> None:
    documents = [
        add_document(
            session,
            f"https://tie-{number}.edu/",
            title="equal score",
        )
        for number in range(3)
    ]
    results = BM25Ranker(index_documents(session, *documents)).rank("equal")

    assert [result.document_id for result in results] == sorted(
        document.id for document in documents
    )


def test_reindexing_changes_results_and_removes_deleted_index_data(
    session: Session,
) -> None:
    document = add_document(
        session,
        "https://refresh-index.edu/",
        title="python",
    )
    repository = index_documents(session, document)
    ranker = BM25Ranker(repository)

    assert [result.document_id for result in ranker.rank("python")] == [document.id]
    changed = DocumentRepository(session).update(
        document.id,
        DocumentUpdate(title="java"),
    )
    assert changed is not None
    DocumentIndexer(repository).index_document(changed)

    assert ranker.rank("python") == []
    assert [result.document_id for result in ranker.rank("java")] == [document.id]

    repository.delete_document_index(document.id)
    assert ranker.rank("java") == []


def test_ranker_gets_candidates_from_postings_without_document_repository() -> None:
    repository = Mock(spec=IndexRepository)
    repository.get_postings_for_terms.return_value = [
        IndexPosting(
            id=1,
            term="python",
            document_id=7,
            field="title",
            term_frequency=1,
            positions=[0],
        )
    ]
    repository.get_field_collection_statistics.return_value = {
        field: FieldCollectionStatistics(
            field=field,
            document_count=1,
            total_document_length=1 if field == "title" else 0,
        )
        for field in ("title", "headings", "description", "body")
    }
    repository.get_field_statistics_for_terms.return_value = {
        7: {"title": 1, "headings": 0, "description": 0, "body": 0}
    }

    results = BM25Ranker(repository).rank("python")

    assert [result.document_id for result in results] == [7]
    repository.get_postings_for_terms.assert_called_once_with(["python"])
    assert not hasattr(repository, "list")


def test_malformed_negative_posting_frequency_fails_clearly(
    session: Session,
) -> None:
    document = add_document(session, "https://corrupt-posting.edu/", title="term")
    repository = index_documents(session, document)
    session.execute(
        update(IndexPosting).where(IndexPosting.term == "term").values(term_frequency=-1)
    )
    session.commit()

    with pytest.raises(ValueError, match="Non-positive term frequency"):
        BM25Ranker(repository).rank("term")


def test_malformed_negative_field_length_fails_clearly(session: Session) -> None:
    document = add_document(session, "https://corrupt-length.edu/", title="term")
    repository = index_documents(session, document)
    session.execute(
        update(DocumentFieldStatistics)
        .where(
            DocumentFieldStatistics.document_id == document.id,
            DocumentFieldStatistics.field == "title",
        )
        .values(document_length=-1)
    )
    session.commit()

    with pytest.raises(ValueError, match="Negative document length"):
        BM25Ranker(repository).rank("term")
