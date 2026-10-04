from sqlalchemy.orm import Session

from app.db.database import SessionLocal, initialize_database
from app.db.repositories.seed_source_repository import SeedSourceRepository
from app.schemas.seed_source import SeedSourceCreate

CURATED_SEED_SOURCES = (
    SeedSourceCreate(
        name="MIT OpenCourseWare",
        start_url="https://ocw.mit.edu/",
        description="Free course materials from MIT courses across many disciplines.",
        source_type="university_course",
        education_levels=["University"],
        subjects=[
            "Computer Science",
            "Mathematics",
            "Engineering",
            "Science",
            "Business",
        ],
        allowed_url_prefixes=["https://ocw.mit.edu/courses/"],
        priority=10,
    ),
    SeedSourceCreate(
        name="OpenLearn",
        start_url="https://www.open.edu/openlearn/",
        description="Free online learning resources from The Open University.",
        source_type="open_education",
        education_levels=["School", "University", "General"],
        subjects=["Arts", "Business", "Education", "Health", "Science"],
        allowed_url_prefixes=["https://www.open.edu/openlearn/"],
        priority=30,
    ),
    SeedSourceCreate(
        name="OpenStax",
        start_url="https://openstax.org/",
        description="Free, peer-reviewed, openly licensed college textbooks.",
        source_type="open_education",
        education_levels=["High School", "University"],
        subjects=["Biology", "Physics", "Mathematics", "Economics", "Social Science"],
        allowed_url_prefixes=[
            "https://openstax.org/books/",
            "https://openstax.org/subjects/",
        ],
        priority=20,
    ),
    SeedSourceCreate(
        name="Khan Academy",
        start_url="https://www.khanacademy.org/",
        description="Free lessons and practice in school and introductory subjects.",
        source_type="school_education",
        education_levels=["School", "University", "General"],
        subjects=["Mathematics", "Science", "Computing", "Economics", "Humanities"],
        allowed_url_prefixes=[
            "https://www.khanacademy.org/math/",
            "https://www.khanacademy.org/science/",
            "https://www.khanacademy.org/computing/",
        ],
        priority=20,
    ),
    SeedSourceCreate(
        name="NASA Science",
        start_url="https://science.nasa.gov/",
        description="Educational and public science resources from NASA.",
        source_type="science_education",
        education_levels=["School", "University", "General"],
        subjects=["Science", "Earth Science", "Space Science", "Astronomy"],
        allowed_url_prefixes=[
            "https://science.nasa.gov/earth/",
            "https://science.nasa.gov/solar-system/",
            "https://science.nasa.gov/universe/",
        ],
        priority=30,
    ),
    SeedSourceCreate(
        name="NCBI Bookshelf",
        start_url="https://www.ncbi.nlm.nih.gov/books/",
        description="Books and documents in life sciences and healthcare from NCBI.",
        source_type="medical_reference",
        education_levels=["University", "Professional"],
        subjects=["Medicine", "Biology", "Health Sciences", "Life Sciences"],
        allowed_url_prefixes=["https://www.ncbi.nlm.nih.gov/books/"],
        priority=20,
    ),
    SeedSourceCreate(
        name="PubMed Central",
        start_url="https://pmc.ncbi.nlm.nih.gov/",
        description="Free full-text archive of biomedical and life sciences literature.",
        source_type="research",
        education_levels=["University", "Professional"],
        subjects=["Medicine", "Biology", "Public Health", "Life Sciences"],
        allowed_url_prefixes=["https://pmc.ncbi.nlm.nih.gov/articles/"],
        priority=20,
    ),
    SeedSourceCreate(
        name="arXiv",
        start_url="https://arxiv.org/",
        description="Open archive of scholarly articles in science and technology.",
        source_type="research",
        education_levels=["University", "Professional"],
        subjects=[
            "Physics",
            "Mathematics",
            "Computer Science",
            "Statistics",
            "Quantitative Biology",
        ],
        allowed_url_prefixes=["https://arxiv.org/abs/", "https://arxiv.org/html/"],
        priority=30,
    ),
    SeedSourceCreate(
        name="Python Documentation",
        start_url="https://docs.python.org/3/",
        description="Official Python language and standard-library documentation.",
        source_type="technical_documentation",
        education_levels=["University", "Professional"],
        subjects=["Programming", "Computer Science"],
        allowed_url_prefixes=["https://docs.python.org/3/"],
        priority=10,
    ),
    SeedSourceCreate(
        name="MDN Web Docs",
        start_url="https://developer.mozilla.org/",
        description="Open documentation and learning resources for web technologies.",
        source_type="technical_documentation",
        education_levels=["University", "Professional"],
        subjects=["Web Development", "Programming", "Computer Science"],
        allowed_url_prefixes=[
            "https://developer.mozilla.org/en-US/docs/",
            "https://developer.mozilla.org/en-US/learn/",
        ],
        priority=10,
    ),
    SeedSourceCreate(
        name="Microsoft Learn",
        start_url="https://learn.microsoft.com/",
        description="Technical training and documentation for Microsoft technologies.",
        source_type="professional_learning",
        education_levels=["University", "Professional"],
        subjects=["Cloud Computing", "Software Development", "Data", "IT"],
        allowed_url_prefixes=[
            "https://learn.microsoft.com/training/",
            "https://learn.microsoft.com/docs/",
        ],
        priority=20,
    ),
    SeedSourceCreate(
        name="AWS Documentation",
        start_url="https://docs.aws.amazon.com/",
        description="Official technical documentation for Amazon Web Services.",
        source_type="technical_documentation",
        education_levels=["University", "Professional"],
        subjects=["Cloud Computing", "IT", "Software Development", "Networking"],
        allowed_url_prefixes=["https://docs.aws.amazon.com/"],
        priority=20,
    ),
)


def seed_curated_sources(session: Session) -> int:
    """Insert missing curated sources and return the number inserted."""
    inserted = 0
    repository = SeedSourceRepository(session)
    for source in CURATED_SEED_SOURCES:
        if repository.get_by_start_url(source.start_url) is None:
            repository.create(source)
            inserted += 1
    return inserted


def main() -> None:
    initialize_database()
    with SessionLocal() as session:
        inserted = seed_curated_sources(session)
    print(f"Inserted {inserted} seed source(s).")


if __name__ == "__main__":
    main()
