from app.db.database import initialize_database


def main() -> None:
    initialize_database()
    print("EduSearch database initialized.")


if __name__ == "__main__":
    main()
