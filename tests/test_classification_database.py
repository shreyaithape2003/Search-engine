from pathlib import Path

from sqlalchemy import inspect

from app.db.database import create_database_engine, initialize_database


def test_database_initialization_adds_provenance_to_existing_schema(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    )
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE documents (id INTEGER PRIMARY KEY)"
            )

        initialize_database(engine)
        initialize_database(engine)

        column_names = {
            column["name"]
            for column in inspect(engine).get_columns("documents")
        }
        assert "classification_provenance" in column_names
    finally:
        engine.dispose()
