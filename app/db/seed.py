from app.db.database import SessionLocal, initialize_database
from app.db.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentCreate
from sqlalchemy.orm import Session

SAMPLE_DOCUMENTS = (
    DocumentCreate(
        url="https://ocw.mit.edu/courses/intro-to-algorithms/",
        canonical_url="https://ocw.mit.edu/courses/intro-to-algorithms/",
        title="Introduction to Algorithms",
        description="Sample university course resource for development.",
        body="Sample text about algorithms, data structures, and course material.",
        headings=["Course overview", "Lecture topics", "Assignments"],
        publisher="MIT OpenCourseWare",
        language="en",
        source_type="university_course",
        subject="Computer Science",
        education_level="University",
        content_type="course",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://docs.python.org/3/tutorial/",
        title="The Python Tutorial",
        description="Sample technical documentation resource for development.",
        body="Sample text introducing Python syntax and programming concepts.",
        headings=["Whetting Your Appetite", "Using the Python Interpreter"],
        publisher="Python Software Foundation",
        language="en",
        source_type="technical_documentation",
        subject="Programming",
        education_level="Professional",
        content_type="documentation",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://science.nasa.gov/learn/",
        title="NASA Science Learning Resources",
        description="Sample science education resource for development.",
        body="Sample text about exploring science and the solar system.",
        headings=["Explore science", "Learning resources"],
        publisher="NASA",
        language="en",
        source_type="educational_resource",
        subject="Science",
        education_level="General",
        content_type="learning_resource",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://learn.microsoft.com/en-us/training/",
        title="Microsoft Learn",
        description="Sample professional learning resource for development.",
        body="Sample text about guided technical learning and training modules.",
        headings=["Learning paths", "Modules", "Credentials"],
        publisher="Microsoft",
        language="en",
        source_type="professional_learning",
        subject="Technology",
        education_level="Professional",
        content_type="training",
        difficulty="intermediate",
    ),
)


def seed_sample_documents(session: Session) -> int:
    """Insert missing development examples and return the number inserted."""
    inserted = 0
    repository = DocumentRepository(session)
    for sample in SAMPLE_DOCUMENTS:
        if repository.get_by_url(sample.url) is None:
            repository.create(sample)
            inserted += 1
    return inserted


def main() -> None:
    initialize_database()
    with SessionLocal() as session:
        inserted = seed_sample_documents(session)
    print(f"Inserted {inserted} development sample document(s).")


if __name__ == "__main__":
    main()
