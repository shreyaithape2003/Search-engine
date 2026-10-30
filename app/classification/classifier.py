"""Bounded, deterministic rules for educational document metadata."""

import re
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

from app.classification.models import (
    ClassificationEvidence,
    ClassificationInput,
    ClassificationMethod,
    ClassificationResult,
    ConfidenceLevel,
)
from app.classification.taxonomy import (
    UNKNOWN_DIFFICULTY,
    normalize_difficulty,
    normalize_education_level,
    normalize_resource_type,
    normalize_subject,
)

MAX_BODY_CHARS = 100_000
MAX_HEADING_CHARS = 20_000
WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)

_SUBJECT_CUES: dict[str, tuple[str, ...]] = {
    "Computer Science": (
        "computer science",
        "programming",
        "python",
        "algorithm",
        "data structure",
        "software development",
        "web development",
        "database",
        "operating system",
        "javascript",
        "computer network",
    ),
    "Engineering": (
        "engineering",
        "mechanical design",
        "electrical circuit",
        "civil engineering",
        "engineering design",
        "prototyping",
    ),
    "Mathematics": (
        "mathematics",
        "mathematical",
        "algebra",
        "calculus",
        "geometry",
        "theorem",
        "equation",
        "linear algebra",
    ),
    "Physics": (
        "physics",
        "mechanics",
        "newton law",
        "electromagnetism",
        "quantum mechanics",
        "thermodynamics",
    ),
    "Chemistry": (
        "chemistry",
        "chemical reaction",
        "organic chemistry",
        "molecule",
        "periodic table",
    ),
    "Biology": (
        "biology",
        "cell biology",
        "genetics",
        "ecology",
        "organism",
        "molecular biology",
    ),
    "Medicine": (
        "medicine",
        "medical education",
        "anatomy",
        "clinical practice",
        "patient care",
        "medical",
    ),
    "Business / MBA": (
        "business administration",
        "mba",
        "business",
        "management",
        "marketing",
        "accounting",
    ),
    "Economics": (
        "economics",
        "economic theory",
        "microeconomics",
        "macroeconomics",
    ),
    "Humanities": (
        "humanities",
        "literature",
        "philosophy",
        "linguistics",
        "art history",
    ),
    "Social Sciences": (
        "social sciences",
        "sociology",
        "political science",
        "anthropology",
        "social research",
    ),
}

_RESOURCE_CUES: dict[str, tuple[str, ...]] = {
    "course": ("course", "coursework", "training module"),
    "documentation": ("documentation", "reference manual", "api reference"),
    "article": ("article", "articles"),
    "tutorial": ("tutorial", "tutorials", "step by step guide"),
    "research paper": ("research paper", "academic paper", "peer reviewed paper"),
    "lecture": ("lecture", "lectures"),
    "blog": ("blog", "blog post", "weblog"),
    "study material": (
        "study material",
        "textbook",
        "worksheet",
        "lesson notes",
    ),
}

_SOURCE_RESOURCE_TYPES = {
    "university_course": "course",
    "technical_documentation": "documentation",
    "research": "research paper",
}


def _tokens(value: str | None, max_chars: int) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        token.casefold()
        for token in WORD_PATTERN.findall(value[:max_chars])
    )


def _phrase_tokens(phrase: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in WORD_PATTERN.findall(phrase))


def _bounded_headings(headings: list[str]) -> str:
    parts: list[str] = []
    remaining = MAX_HEADING_CHARS
    for heading in headings:
        if remaining <= 0:
            break
        part = heading[:remaining]
        parts.append(part)
        remaining -= len(part) + 1
    return " ".join(parts)


def _contains_phrase(tokens: tuple[str, ...], phrase: str) -> bool:
    phrase_tokens = _phrase_tokens(phrase)
    width = len(phrase_tokens)
    return bool(width) and any(
        tokens[index:index + width] == phrase_tokens
        for index in range(len(tokens) - width + 1)
    )


def _normalized_candidates(
    values: Iterable[str],
    normalizer: Callable[[str | None], str | None],
) -> tuple[set[str], bool]:
    candidates: set[str] = set()
    all_values_recognized = True
    for value in values:
        normalized = normalizer(value)
        if normalized is not None:
            candidates.add(normalized)
        elif value.strip():
            all_values_recognized = False
    return candidates, all_values_recognized


def _evidence(
    method: ClassificationMethod,
    confidence: ConfidenceLevel,
    *reasons: str,
) -> ClassificationEvidence:
    return ClassificationEvidence(
        method=method,
        confidence=confidence,
        reasons=list(reasons[:3]),
    )


class EducationalClassifier:
    """Classify missing educational metadata using canonical values only."""

    def classify(self, data: ClassificationInput) -> ClassificationResult:
        path_segments = tuple(
            segment.casefold()
            for segment in urlsplit(data.url).path.split("/")
            if segment
        )
        title_tokens = _tokens(data.title, 500)
        heading_text = _bounded_headings(data.headings)
        heading_tokens = _tokens(heading_text, MAX_HEADING_CHARS)
        description_tokens = _tokens(data.description, 5000)
        body_tokens = _tokens(data.body, MAX_BODY_CHARS)
        evidence = {
            "title": title_tokens,
            "headings": heading_tokens,
            "description": description_tokens,
            "body": body_tokens,
        }

        education_level, education_evidence = self._classify_education(
            data,
            path_segments,
            evidence,
        )
        subject, subject_evidence = self._classify_subject(data, evidence)
        content_type, content_evidence = self._classify_resource_type(
            data,
            path_segments,
            evidence,
        )
        difficulty, difficulty_evidence = self._classify_difficulty(data, evidence)

        return ClassificationResult(
            education_level=education_level,
            subject=subject,
            content_type=content_type,
            difficulty=difficulty,
            provenance={
                "education_level": education_evidence,
                "subject": subject_evidence,
                "content_type": content_evidence,
                "difficulty": difficulty_evidence,
            },
        )

    @staticmethod
    def _classify_education(
        data: ClassificationInput,
        path_segments: tuple[str, ...],
        evidence: dict[str, tuple[str, ...]],
    ) -> tuple[str | None, ClassificationEvidence]:
        explicit = normalize_education_level(data.document_education_level)
        if explicit is not None:
            return explicit, _evidence(
                "explicit_metadata",
                "High",
                "document metadata provides a recognized education level",
            )

        source_levels, source_levels_are_canonical = _normalized_candidates(
            data.seed_education_levels,
            normalize_education_level,
        )
        if len(source_levels) == 1 and source_levels_are_canonical:
            return next(iter(source_levels)), _evidence(
                "seed_source",
                "Medium",
                "curated seed source provides one canonical education level",
            )

        rule_level, rule_confidence, rule_reasons = _education_rule(
            path_segments,
            evidence,
        )
        if rule_level is not None:
            if rule_confidence == "Medium" and rule_level in source_levels:
                rule_confidence = "High"
                rule_reasons = (*rule_reasons, "seed source supports the same level")
            return rule_level, _evidence(
                "rule_based",
                rule_confidence,
                *rule_reasons,
            )
        return None, _evidence(
            "unknown",
            "Low",
            "education-level evidence is missing or ambiguous",
        )

    @staticmethod
    def _classify_subject(
        data: ClassificationInput,
        evidence: dict[str, tuple[str, ...]],
    ) -> tuple[str | None, ClassificationEvidence]:
        explicit = normalize_subject(data.document_subject)
        if explicit is not None:
            return explicit, _evidence(
                "explicit_metadata",
                "High",
                "document metadata provides a recognized subject",
            )

        source_subjects, source_subjects_are_canonical = _normalized_candidates(
            data.seed_subjects,
            normalize_subject,
        )
        if len(source_subjects) == 1 and source_subjects_are_canonical:
            return next(iter(source_subjects)), _evidence(
                "seed_source",
                "Medium",
                "curated seed source provides one canonical subject",
            )

        ranked: list[tuple[int, str, set[str]]] = []
        weights = {"title": 3, "headings": 2, "description": 1, "body": 1}
        for subject, cues in _SUBJECT_CUES.items():
            score = 0
            matched_zones: set[str] = set()
            matched_cues: set[str] = set()
            for zone, tokens in evidence.items():
                zone_matches = {
                    cue for cue in cues if _contains_phrase(tokens, cue)
                }
                if zone_matches:
                    score += weights[zone] * min(len(zone_matches), 2)
                    matched_zones.add(zone)
                    matched_cues.update(zone_matches)
            if score >= 3:
                ranked.append((score, subject, matched_zones | matched_cues))

        ranked.sort(key=lambda result: (-result[0], result[1]))
        if ranked and (
            len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 2
        ):
            _, subject, cues = ranked[0]
            if (
                source_subjects_are_canonical
                and source_subjects
                and subject not in source_subjects
            ):
                return None, _evidence(
                    "unknown",
                    "Low",
                    "page evidence conflicts with the curated source subjects",
                )
            zones = cues.intersection(evidence)
            confidence = "High" if len(zones) >= 2 else "Medium"
            reasons = ["subject-specific terms appear in page metadata"]
            if len(zones) >= 2:
                reasons.append("multiple page fields corroborate the subject")
            return subject, _evidence("rule_based", confidence, *reasons)

        return None, _evidence(
            "unknown",
            "Low",
            "subject evidence is missing or ambiguous",
        )

    @staticmethod
    def _classify_resource_type(
        data: ClassificationInput,
        path_segments: tuple[str, ...],
        evidence: dict[str, tuple[str, ...]],
    ) -> tuple[str | None, ClassificationEvidence]:
        explicit = normalize_resource_type(data.document_content_type)
        if explicit is not None:
            return explicit, _evidence(
                "explicit_metadata",
                "High",
                "document metadata provides a recognized resource type",
            )

        title_and_heading = evidence["title"] + evidence["headings"]
        rule_type = _resource_from_signals(path_segments, title_and_heading)
        if rule_type is not None:
            return rule_type, _evidence(
                "rule_based",
                (
                    "High"
                    if _has_resource_corroboration(
                        rule_type,
                        path_segments,
                        title_and_heading,
                    )
                    else "Medium"
                ),
                "title, headings, or URL path contains a resource-type indicator",
            )

        source_type = (data.seed_source_type or "")[:100].strip().casefold()
        source_resource_type = _SOURCE_RESOURCE_TYPES.get(source_type)
        if source_resource_type is not None:
            return source_resource_type, _evidence(
                "seed_source",
                "Medium",
                "curated seed source type indicates this resource format",
            )
        return None, _evidence(
            "unknown",
            "Low",
            "resource-type evidence is missing or ambiguous",
        )

    @staticmethod
    def _classify_difficulty(
        data: ClassificationInput,
        evidence: dict[str, tuple[str, ...]],
    ) -> tuple[str, ClassificationEvidence]:
        explicit = normalize_difficulty(data.document_difficulty)
        if explicit is not None:
            return explicit, _evidence(
                "explicit_metadata",
                "High",
                "document metadata provides a recognized difficulty",
            )

        title_and_headings = evidence["title"] + evidence["headings"]
        for label, cues in (
            (
                "Beginner",
                ("beginner", "beginners", "introductory", "fundamentals", "basics"),
            ),
            ("Intermediate", ("intermediate",)),
            ("Advanced", ("advanced", "expert level")),
        ):
            if any(_contains_phrase(title_and_headings, cue) for cue in cues):
                return label, _evidence(
                    "rule_based",
                    "Medium",
                    "title or heading explicitly signals difficulty",
                )
        return UNKNOWN_DIFFICULTY, _evidence(
            "unknown",
            "Low",
            "difficulty is not explicitly stated",
        )


def _education_rule(
    path_segments: tuple[str, ...],
    evidence: dict[str, tuple[str, ...]],
) -> tuple[str | None, ConfidenceLevel, tuple[str, ...]]:
    page_tokens = evidence["title"] + evidence["headings"] + evidence["description"]
    segments = set(path_segments)
    grade_number = any(
        token == "grade"
        and index + 1 < len(page_tokens)
        and page_tokens[index + 1].isdigit()
        for index, token in enumerate(page_tokens)
    )
    if (
        {"school", "schools", "k-12", "high-school"} & segments
        or _contains_phrase(page_tokens, "high school")
        or _contains_phrase(page_tokens, "primary school")
        or _contains_phrase(page_tokens, "secondary school")
        or grade_number
    ):
        return "School", "Medium", ("school-level URL or page indicators are present",)
    if (
        {"research", "papers", "paper"} & segments
        or _contains_phrase(page_tokens, "research paper")
        or _contains_phrase(page_tokens, "peer reviewed")
    ):
        return "Research", "Medium", ("research-specific page indicators are present",)
    if (
        {"training", "certification", "certifications"} & segments
        or _contains_phrase(page_tokens, "professional training")
        or _contains_phrase(page_tokens, "career development")
    ):
        return "Professional", "Medium", ("professional-learning indicators are present",)
    if (
        {"university", "universities", "college", "colleges"} & segments
        or _contains_phrase(page_tokens, "university course")
        or _contains_phrase(page_tokens, "undergraduate course")
        or _contains_phrase(page_tokens, "graduate course")
    ):
        return "University", "Medium", ("university-level page indicators are present",)
    return None, "Low", ()


def _resource_from_signals(
    path_segments: tuple[str, ...],
    title_and_heading: tuple[str, ...],
) -> str | None:
    segment_aliases = {
        "courses": "course",
        "course": "course",
        "docs": "documentation",
        "documentation": "documentation",
        "reference": "documentation",
        "articles": "article",
        "article": "article",
        "tutorials": "tutorial",
        "tutorial": "tutorial",
        "papers": "research paper",
        "paper": "research paper",
        "lectures": "lecture",
        "lecture": "lecture",
        "blog": "blog",
        "blogs": "blog",
        "lessons": "study material",
        "textbooks": "study material",
    }
    path_matches = {
        resource_type
        for segment in path_segments
        if (resource_type := segment_aliases.get(segment)) is not None
    }
    title_matches = {
        resource_type
        for resource_type, cues in _RESOURCE_CUES.items()
        if any(_contains_phrase(title_and_heading, cue) for cue in cues)
    }
    if path_matches:
        if len(path_matches) == 1 and (
            not title_matches or title_matches == path_matches
        ):
            return next(iter(path_matches))
        return None
    return next(iter(title_matches)) if len(title_matches) == 1 else None


def _has_resource_corroboration(
    resource_type: str,
    path_segments: tuple[str, ...],
    title_and_heading: tuple[str, ...],
) -> bool:
    path_resource = _resource_from_signals(path_segments, ())
    title_matches = {
        candidate
        for candidate, cues in _RESOURCE_CUES.items()
        if any(
            _contains_phrase(title_and_heading, cue)
            for cue in cues
        )
    }
    return path_resource == resource_type and resource_type in title_matches
