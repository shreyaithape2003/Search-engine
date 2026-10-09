from sqlalchemy.orm import Session

from app.db.database import SessionLocal, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.indexing.indexer import DocumentIndexer
from app.indexing.repository import IndexRepository

DOCUMENT_BATCH_SIZE = 500


def build_development_index(session: Session) -> int:
    """Rebuild index entries for every persisted document."""
    document_repository = DocumentRepository(session)
    document_indexer = DocumentIndexer(IndexRepository(session))
    indexed_count = 0
    offset = 0

    while True:
        documents = document_repository.list(
            limit=DOCUMENT_BATCH_SIZE,
            offset=offset,
        )
        for document in documents:
            document_indexer.index_document(document)
            indexed_count += 1

        if len(documents) < DOCUMENT_BATCH_SIZE:
            return indexed_count
        offset += len(documents)


def main() -> None:
    initialize_database()
    with SessionLocal() as session:
        indexed_count = build_development_index(session)

    if indexed_count == 0:
        print("No Documents found; development index is empty.")
    else:
        print(f"Indexed {indexed_count} development Document(s).")


if __name__ == "__main__":
    main()
