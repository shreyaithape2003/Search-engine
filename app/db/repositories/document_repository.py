from typing import Any

from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate


class DuplicateDocumentError(ValueError):
    """Raised when a document URL or canonical URL already exists."""


class DocumentRepository:
    """Database operations for educational documents."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, document_data: DocumentCreate) -> Document:
        values = self._serialize_urls(document_data.model_dump())
        values["domain"] = document_data.url.host
        document = Document(**values)
        try:
            self.session.add(document)
            self.session.commit()
            self.session.refresh(document)
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateDocumentError(
                "A document with this URL or canonical URL already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise
        return document

    def get_by_id(self, document_id: int) -> Document | None:
        return self.session.get(Document, document_id)

    def get_by_url(self, url: str | HttpUrl) -> Document | None:
        normalized_url = str(HttpUrl(str(url)))
        statement = select(Document).where(Document.url == normalized_url)
        return self.session.scalar(statement)

    def get_by_canonical_url(self, url: str | HttpUrl) -> Document | None:
        normalized_url = str(HttpUrl(str(url)))
        statement = select(Document).where(Document.canonical_url == normalized_url)
        return self.session.scalar(statement)

    def list(self, limit: int = 100, offset: int = 0) -> list[Document]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        if offset < 0:
            raise ValueError("offset cannot be negative.")

        statement = select(Document).order_by(Document.id).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def update(
        self,
        document_id: int,
        document_data: DocumentUpdate,
    ) -> Document | None:
        document = self.get_by_id(document_id)
        if document is None:
            return None

        values = self._serialize_urls(
            document_data.model_dump(exclude_unset=True)
        )
        if document_data.url is not None:
            values["domain"] = document_data.url.host

        try:
            for field, value in values.items():
                setattr(document, field, value)
            self.session.commit()
            self.session.refresh(document)
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateDocumentError(
                "A document with this URL or canonical URL already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise
        return document

    def delete(self, document_id: int) -> bool:
        document = self.get_by_id(document_id)
        if document is None:
            return False

        try:
            self.session.delete(document)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return True

    @staticmethod
    def _serialize_urls(values: dict[str, Any]) -> dict[str, Any]:
        for field in ("url", "canonical_url"):
            value = values.get(field)
            if value is not None:
                values[field] = str(value)
        return values
