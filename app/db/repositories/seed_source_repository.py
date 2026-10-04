from typing import Any
from urllib.parse import urlsplit

from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.seed_source import SeedSource
from app.schemas.seed_source import SeedSourceCreate, SeedSourceUpdate


class DuplicateSeedSourceError(ValueError):
    """Raised when a seed source start URL already exists."""


class SeedSourceRepository:
    """Database operations for curated educational seed sources."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, source_data: SeedSourceCreate) -> SeedSource:
        values = self._serialize_urls(source_data.model_dump())
        values["domain"] = self._domain_from_url(source_data.start_url)
        source = SeedSource(**values)
        try:
            self.session.add(source)
            self.session.commit()
            self.session.refresh(source)
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateSeedSourceError(
                "A seed source with this start URL already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise
        return source

    def get_by_id(self, source_id: int) -> SeedSource | None:
        return self.session.get(SeedSource, source_id)

    def get_by_start_url(self, start_url: str | HttpUrl) -> SeedSource | None:
        normalized_url = str(HttpUrl(str(start_url)))
        statement = select(SeedSource).where(SeedSource.start_url == normalized_url)
        return self.session.scalar(statement)

    def list(self, limit: int = 100, offset: int = 0) -> list[SeedSource]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        if offset < 0:
            raise ValueError("offset cannot be negative.")

        statement = select(SeedSource).order_by(SeedSource.id).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def update(
        self,
        source_id: int,
        source_data: SeedSourceUpdate,
    ) -> SeedSource | None:
        source = self.get_by_id(source_id)
        if source is None:
            return None

        values = self._serialize_urls(source_data.model_dump(exclude_unset=True))
        if source_data.start_url is not None:
            values["domain"] = self._domain_from_url(source_data.start_url)

        try:
            for field, value in values.items():
                setattr(source, field, value)
            self.session.commit()
            self.session.refresh(source)
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateSeedSourceError(
                "A seed source with this start URL already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise
        return source

    def delete(self, source_id: int) -> bool:
        source = self.get_by_id(source_id)
        if source is None:
            return False

        try:
            self.session.delete(source)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return True

    @staticmethod
    def _domain_from_url(url: HttpUrl) -> str:
        domain = urlsplit(str(url)).hostname
        if domain is None:
            raise ValueError("The seed source start URL must include a hostname.")
        return domain.lower()

    @staticmethod
    def _serialize_urls(values: dict[str, Any]) -> dict[str, Any]:
        for field in ("start_url",):
            value = values.get(field)
            if value is not None:
                values[field] = str(value)
        if "allowed_url_prefixes" in values and values["allowed_url_prefixes"] is not None:
            values["allowed_url_prefixes"] = [
                str(prefix) for prefix in values["allowed_url_prefixes"]
            ]
        return values
