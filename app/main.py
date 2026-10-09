import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.v1.search import router as search_router
from app.core.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting %s", settings.service_name)
    yield
    logger.info("Stopping %s", settings.service_name)


app = FastAPI(
    title=settings.service_name,
    description="A specialized search engine for publicly accessible educational resources.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["GET"],
    allow_headers=[],
)
app.include_router(search_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", service=settings.service_name)
