from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.ranking.bm25 import QueryLimitError
from app.schemas.search import SearchResponse
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
) -> SearchResponse:
    try:
        return service.search(q, limit)
    except QueryLimitError as error:
        raise HTTPException(
            status_code=422,
            detail="Query exceeds supported search limits.",
        ) from error
