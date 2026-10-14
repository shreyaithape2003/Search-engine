import ipaddress
import unicodedata
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.ranking.bm25 import QueryLimitError
from app.schemas.search import (
    SearchFilters,
    SearchResponse,
    SearchSuggestionsResponse,
)
from app.services.search_service import SearchService, create_search_service

router = APIRouter(prefix="/api/v1", tags=["search"])


def get_search_service(
    session: Annotated[Session, Depends(get_session)],
) -> SearchService:
    return create_search_service(session)


@router.get("/search", response_model=SearchResponse)
def search(
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=2000,
            pattern=r"(?s).*\S.*",
        ),
    ],
    service: Annotated[SearchService, Depends(get_search_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    education_level: Annotated[str | None, Query(max_length=100)] = None,
    subject: Annotated[str | None, Query(max_length=200)] = None,
    content_type: Annotated[str | None, Query(max_length=100)] = None,
    language: Annotated[str | None, Query(max_length=35)] = None,
    domain: Annotated[str | None, Query(max_length=253)] = None,
    difficulty: Annotated[str | None, Query(max_length=50)] = None,
) -> SearchResponse:
    filters = _build_filters(
        education_level=education_level,
        subject=subject,
        content_type=content_type,
        language=language,
        domain=domain,
        difficulty=difficulty,
    )
    try:
        return service.search(q, limit, filters)
    except QueryLimitError as error:
        raise HTTPException(
            status_code=422,
            detail="Query exceeds supported search limits.",
        ) from error


@router.get("/search/suggestions", response_model=SearchSuggestionsResponse)
def search_suggestions(
    q: Annotated[str, Query(max_length=200)],
    service: Annotated[SearchService, Depends(get_search_service)],
    limit: Annotated[int, Query(ge=1, le=10)] = 6,
) -> SearchSuggestionsResponse:
    return service.suggest(q, limit)


def _build_filters(
    *,
    education_level: str | None,
    subject: str | None,
    content_type: str | None,
    language: str | None,
    domain: str | None,
    difficulty: str | None,
) -> SearchFilters | None:
    values: dict[str, str] = {}
    for name, value in (
        ("education_level", education_level),
        ("subject", subject),
        ("content_type", content_type),
        ("language", language),
        ("domain", domain),
        ("difficulty", difficulty),
    ):
        if value is None:
            continue
        normalized = value.strip()
        if not normalized:
            continue
        if any(unicodedata.category(character) == "Cc" for character in normalized):
            raise HTTPException(
                status_code=422,
                detail=f"{name} cannot contain control characters.",
            )
        if name == "domain":
            normalized = _normalize_domain_filter(normalized)
        values[name] = normalized
    return SearchFilters(**values) if values else None


def _normalize_domain_filter(value: str) -> str:
    try:
        parsed = urlsplit(f"//{value}")
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="domain must be a hostname without a scheme, path, or port.",
        ) from error

    if (
        hostname is None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="domain must be a hostname without a scheme, path, or port.",
        )

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii").removesuffix(
                "."
            )
        except UnicodeError as error:
            raise HTTPException(
                status_code=422,
                detail="domain must be a valid hostname.",
            ) from error
        labels = ascii_hostname.split(".")
        if (
            not ascii_hostname
            or len(ascii_hostname) > 253
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not label.isascii()
                or not label.replace("-", "").isalnum()
                for label in labels
            )
        ):
            raise HTTPException(
                status_code=422,
                detail="domain must be a valid hostname.",
            )
        hostname = ascii_hostname
    return hostname.casefold()
