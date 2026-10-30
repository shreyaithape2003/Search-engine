from dataclasses import dataclass

from app.classification.taxonomy import (
    DIFFICULTY_LEVELS,
    EDUCATION_LEVELS,
    RESOURCE_TYPES,
    SUBJECTS,
)
from app.db.seed import SAMPLE_DOCUMENTS
from app.schemas.document import DocumentCreate
from app.schemas.search import SearchFilters

SAMPLE_URLS_BY_KEY = {
    "mit_algorithms": "https://ocw.mit.edu/courses/intro-to-algorithms/",
    "python_tutorial": "https://docs.python.org/3/tutorial/",
    "nasa_science": "https://science.nasa.gov/learn/",
    "microsoft_learning": "https://learn.microsoft.com/en-us/training/",
    "microsoft_python_tutorial": (
        "https://learn.microsoft.com/en-us/training/modules/python-fundamentals/"
    ),
    "school_algebra": "https://math-school.example.edu/algebra/",
    "python_reference": "https://computer-science.example.edu/python/reference/",
    "classical_mechanics": "https://physics.example.edu/mechanics/",
    "cell_biology_research": "https://biology-research.example.edu/cells/",
    "data_science_python": "https://data-science.example.edu/python/",
    "engineering_design": "https://engineering.example.edu/design/",
    "organic_chemistry": "https://chemistry.example.edu/organic/tutorial/",
    "school_waves": "https://physics-school.example.edu/waves/",
    "school_ecology": "https://biology-school.example.edu/ecology/",
    "business_management": "https://business.example.edu/management/lecture/",
    "microeconomics": "https://economics.example.edu/microeconomics/",
    "world_history": "https://humanities.example.edu/history/lecture/",
    "social_science_research": "https://social-science.example.edu/research/blog/",
    "human_anatomy": "https://medicine.example.edu/anatomy/",
    "specialized_research": "https://specialized.example.edu/interdisciplinary/",
}

_samples_by_url = {str(document.url): document for document in SAMPLE_DOCUMENTS}
FIXTURE_DOCUMENTS: dict[str, DocumentCreate] = {}
for _fixture_key, _sample_url in SAMPLE_URLS_BY_KEY.items():
    if _sample_url not in _samples_by_url:
        raise RuntimeError(f"Evaluation fixture {_fixture_key!r} has no sample document.")
    FIXTURE_DOCUMENTS[_fixture_key] = _samples_by_url[_sample_url]


@dataclass(frozen=True)
class RelevanceJudgment:
    document_key: str
    grade: int


@dataclass(frozen=True)
class EvaluationQuery:
    query_id: str
    text: str
    information_need: str
    judgments: tuple[RelevanceJudgment, ...]
    filters: SearchFilters | None = None


def _judgments(*items: tuple[str, int]) -> tuple[RelevanceJudgment, ...]:
    return tuple(RelevanceJudgment(document_key=key, grade=grade) for key, grade in items)


EVALUATION_QUERIES = (
    EvaluationQuery(
        "q01",
        "Introduction to Algorithms",
        "Find an introductory algorithm course.",
        _judgments(("mit_algorithms", 3), ("python_reference", 0)),
    ),
    EvaluationQuery(
        "q02",
        "algorithms course",
        "Find a course that teaches algorithms.",
        _judgments(("mit_algorithms", 3), ("engineering_design", 1)),
    ),
    EvaluationQuery(
        "q03",
        "organic chemistry reaction mechanisms",
        "Learn common organic chemistry reactions.",
        _judgments(("organic_chemistry", 3), ("human_anatomy", 0)),
        SearchFilters(subject="Chemistry"),
    ),
    EvaluationQuery(
        "q04",
        "linear equations and variables",
        "Find school-level algebra instruction.",
        _judgments(("school_algebra", 3), ("microeconomics", 0)),
        SearchFilters(education_level="School", subject="Mathematics"),
    ),
    EvaluationQuery(
        "q05",
        "Python expressions standard library",
        "Find reference documentation for Python.",
        _judgments(("python_reference", 3), ("python_tutorial", 2)),
        SearchFilters(content_type="documentation"),
    ),
    EvaluationQuery(
        "q06",
        "school ecosystems food webs",
        "Study school-level ecology and ecosystems.",
        _judgments(("school_ecology", 3), ("school_waves", 2)),
        SearchFilters(education_level="School"),
    ),
    EvaluationQuery(
        "q07",
        "engineering design prototyping",
        "Learn university engineering design methods.",
        _judgments(("engineering_design", 3), ("classical_mechanics", 1)),
        SearchFilters(education_level="University", subject="Engineering"),
    ),
    EvaluationQuery(
        "q08",
        "Python fundamentals practical exercises",
        "Find professional Python training with practice.",
        _judgments(("microsoft_python_tutorial", 3), ("python_tutorial", 2)),
        SearchFilters(education_level="Professional"),
    ),
    EvaluationQuery(
        "q09",
        "cell biology cellular membranes",
        "Find research-level cell biology material.",
        _judgments(("cell_biology_research", 3), ("specialized_research", 0)),
        SearchFilters(education_level="Research", subject="Biology"),
    ),
    EvaluationQuery(
        "q10",
        "motion forces energy momentum",
        "Study mechanics concepts and their relationships.",
        _judgments(("classical_mechanics", 3), ("school_waves", 1)),
        SearchFilters(subject="Physics"),
    ),
    EvaluationQuery(
        "q11",
        "historical primary sources context",
        "Learn to interpret historical evidence.",
        _judgments(("world_history", 3), ("school_ecology", 0)),
        SearchFilters(subject="Humanities"),
    ),
    EvaluationQuery(
        "q12",
        "PYTHON, FUNCTIONS!",
        "Find Python lessons about functions.",
        _judgments(("microsoft_python_tutorial", 3), ("python_tutorial", 2)),
    ),
    EvaluationQuery(
        "q13",
        "quasar spectroscopy",
        "Find material about quasar spectroscopy.",
        _judgments(("cell_biology_research", 0), ("mit_algorithms", 0)),
    ),
    EvaluationQuery(
        "q14",
        "python variables functions programming",
        "Learn practical Python programming concepts.",
        _judgments(("microsoft_python_tutorial", 3), ("python_reference", 2)),
    ),
    EvaluationQuery(
        "q15",
        "rotational motion force",
        "Understand mechanics beyond an exact title match.",
        _judgments(("classical_mechanics", 3), ("engineering_design", 1)),
    ),
    EvaluationQuery(
        "q16",
        "bonding functional groups reactions",
        "Study foundational chemistry reactions.",
        _judgments(("organic_chemistry", 3), ("human_anatomy", 0)),
        SearchFilters(subject="Chemistry", content_type="tutorial"),
    ),
    EvaluationQuery(
        "q17",
        "clinical anatomy body systems",
        "Find medical reference material about anatomy.",
        _judgments(("human_anatomy", 3), ("python_reference", 0)),
        SearchFilters(
            education_level="University",
            content_type="documentation",
        ),
    ),
    EvaluationQuery(
        "q18",
        "data cleaning visualization notebooks",
        "Find professional data science learning material.",
        _judgments(("data_science_python", 3), ("microsoft_learning", 1)),
        SearchFilters(education_level="Professional"),
    ),
    EvaluationQuery(
        "q19",
        "supply demand markets incentives",
        "Understand how supply and demand shape markets.",
        _judgments(("microeconomics", 3), ("business_management", 1)),
        SearchFilters(subject="Economics"),
    ),
    EvaluationQuery(
        "q20",
        "research questions evidence surveys",
        "Learn about social science research methods.",
        _judgments(("social_science_research", 3), ("cell_biology_research", 1)),
        SearchFilters(
            education_level="Professional",
            content_type="blog",
        ),
    ),
    EvaluationQuery(
        "q21",
        "solar system science learning",
        "Find introductory science learning resources.",
        _judgments(("nasa_science", 3), ("classical_mechanics", 1)),
    ),
    EvaluationQuery(
        "q22",
        "the data structures and algorithms",
        "Find material about algorithms and data structures.",
        _judgments(("mit_algorithms", 3), ("python_reference", 2)),
    ),
    EvaluationQuery(
        "q23",
        "business strategy decision making",
        "Learn business management and strategy.",
        _judgments(("business_management", 3), ("microeconomics", 1)),
        SearchFilters(subject="Business / MBA"),
    ),
    EvaluationQuery(
        "q24",
        "graduate-level number theory",
        "Find graduate number theory material.",
        _judgments(("specialized_research", 0), ("classical_mechanics", 0)),
    ),
)


def validate_dataset(
    queries: tuple[EvaluationQuery, ...] | list[EvaluationQuery] = EVALUATION_QUERIES,
    documents: dict[str, DocumentCreate] = FIXTURE_DOCUMENTS,
) -> None:
    """Validate benchmark IDs, labels, filters, and required coverage."""
    if not queries:
        raise ValueError("Evaluation dataset must contain at least one query.")

    query_ids: set[str] = set()
    has_relevant = False
    has_no_relevant = False
    education_coverage: set[str] = set()

    for query in queries:
        if not query.query_id.strip():
            raise ValueError("Evaluation query IDs must be non-empty.")
        if query.query_id in query_ids:
            raise ValueError(f"Duplicate evaluation query ID: {query.query_id!r}.")
        query_ids.add(query.query_id)

        if not query.text.strip():
            raise ValueError(f"Query {query.query_id!r} has empty query text.")
        if not query.information_need.strip():
            raise ValueError(f"Query {query.query_id!r} has no information need.")

        seen_document_keys: set[str] = set()
        relevant_keys: list[str] = []
        for judgment in query.judgments:
            if judgment.document_key not in documents:
                raise ValueError(
                    f"Query {query.query_id!r} references unknown fixture "
                    f"document key {judgment.document_key!r}."
                )
            if judgment.document_key in seen_document_keys:
                raise ValueError(
                    f"Query {query.query_id!r} has duplicate judgment for "
                    f"{judgment.document_key!r}."
                )
            seen_document_keys.add(judgment.document_key)
            if type(judgment.grade) is not int or judgment.grade not in range(4):
                raise ValueError(
                    f"Query {query.query_id!r} has invalid relevance grade "
                    f"{judgment.grade!r}; expected an integer from 0 to 3."
                )
            if judgment.grade >= 2:
                has_relevant = True
                relevant_keys.append(judgment.document_key)

        if not relevant_keys:
            has_no_relevant = True

        if query.filters is not None:
            for field, allowed_values in (
                ("education_level", EDUCATION_LEVELS),
                ("subject", SUBJECTS),
                ("content_type", RESOURCE_TYPES),
                ("difficulty", DIFFICULTY_LEVELS),
            ):
                value = getattr(query.filters, field)
                if value is not None and value not in allowed_values:
                    raise ValueError(
                        f"Query {query.query_id!r} has non-canonical "
                        f"{field} filter {value!r}."
                    )

            level = query.filters.education_level
            if level is not None and any(
                documents[key].education_level == level for key in relevant_keys
            ):
                education_coverage.add(level)

    if not has_relevant:
        raise ValueError("Evaluation dataset must include relevant judgments.")
    if not has_no_relevant:
        raise ValueError(
            "Evaluation dataset must include a query with no relevant judgments."
        )
    missing_levels = set(EDUCATION_LEVELS) - education_coverage
    if missing_levels:
        raise ValueError(
            "Evaluation dataset lacks meaningful filtered query coverage for "
            f"education levels: {', '.join(sorted(missing_levels))}."
        )


def relevance_by_key(query: EvaluationQuery) -> dict[str, int]:
    """Return one query's validated stable-key relevance labels."""
    return {judgment.document_key: judgment.grade for judgment in query.judgments}

