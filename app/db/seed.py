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
    DocumentCreate(
        url="https://learn.microsoft.com/en-us/training/modules/python-fundamentals/",
        title="Microsoft Learn Python Fundamentals Tutorial",
        description="Sample tutorial introducing Python fundamentals for professional learners.",
        body=(
            "This development sample covers Python syntax, variables, functions, "
            "and practical programming exercises."
        ),
        headings=["Python basics", "Functions and modules", "Practice exercises"],
        publisher="Microsoft Learn",
        language="en",
        source_type="professional_learning",
        subject="Computer Science",
        education_level="Professional",
        content_type="tutorial",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://math-school.example.edu/algebra/",
        title="Algebra Foundations for School Students",
        description="Sample school-level article introducing equations and algebraic reasoning.",
        body=(
            "Learn how to solve linear equations, work with variables, and check "
            "solutions using clear worked examples."
        ),
        headings=["Variables", "Linear equations", "Worked examples"],
        language="en",
        source_type="school_resource",
        subject="Mathematics",
        education_level="School",
        content_type="article",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://computer-science.example.edu/python/reference/",
        title="Python Language Reference for University Students",
        description="Sample computer science documentation for university study.",
        body=(
            "This reference sample explains Python expressions, data types, "
            "control flow, and standard library concepts."
        ),
        headings=["Expressions", "Data types", "Control flow"],
        language="en",
        source_type="university_documentation",
        subject="Computer Science",
        education_level="University",
        content_type="documentation",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://physics.example.edu/mechanics/",
        title="Classical Mechanics: An Introductory Course",
        description="Sample university physics course covering motion and forces.",
        body=(
            "Explore vectors, Newton's laws, energy, momentum, and rotational "
            "motion through conceptual lessons and practice problems."
        ),
        headings=["Motion", "Forces", "Energy and momentum"],
        language="en",
        source_type="university_course",
        subject="Physics",
        education_level="University",
        content_type="course",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://biology-research.example.edu/cells/",
        title="Cell Biology Research Paper: A Sample Review",
        description="Sample research paper summary about cell structure and function.",
        body=(
            "This development text reviews cellular membranes, organelles, "
            "signaling, and current questions in cell biology."
        ),
        headings=["Cell structure", "Signaling", "Open research questions"],
        language="en",
        source_type="research_publication",
        subject="Biology",
        education_level="Research",
        content_type="research paper",
        difficulty="advanced",
    ),
    DocumentCreate(
        url="https://data-science.example.edu/python/",
        title="Practical Data Science with Python",
        description="Sample professional guide to data analysis with Python.",
        body=(
            "Work through data cleaning, exploratory analysis, visualization, "
            "and reproducible notebooks using sample datasets."
        ),
        headings=["Preparing data", "Exploratory analysis", "Visualization"],
        language="en",
        source_type="professional_guide",
        subject="Other / Specialized",
        education_level="Professional",
        content_type="study material",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://engineering.example.edu/design/",
        title="Engineering Design Principles",
        description="Sample university course introducing engineering design.",
        body=(
            "Study requirements, prototyping, testing, and responsible design "
            "through a structured engineering project."
        ),
        headings=["Requirements", "Prototyping", "Testing"],
        language="en",
        source_type="university_course",
        subject="Engineering",
        education_level="University",
        content_type="course",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://chemistry.example.edu/organic/tutorial/",
        title="Organic Chemistry Reactions Tutorial",
        description="Sample tutorial on foundational organic chemistry reactions.",
        body=(
            "Review bonding, reaction mechanisms, functional groups, and "
            "worked examples for common organic reactions."
        ),
        headings=["Functional groups", "Reaction mechanisms", "Examples"],
        language="en",
        source_type="educational_tutorial",
        subject="Chemistry",
        education_level="University",
        content_type="tutorial",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://physics-school.example.edu/waves/",
        title="Waves and Light for School Science",
        description="Sample school-level article about waves, sound, and light.",
        body=(
            "Explore wave properties, sound, reflection, and refraction with "
            "short explanations and simple examples."
        ),
        headings=["Wave properties", "Sound", "Light"],
        language="en",
        source_type="school_resource",
        subject="Physics",
        education_level="School",
        content_type="article",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://biology-school.example.edu/ecology/",
        title="Ecology Study Material for School",
        description="Sample study material on ecosystems and biodiversity.",
        body=(
            "Review food webs, habitats, energy flow, and biodiversity with "
            "concise notes and revision questions."
        ),
        headings=["Ecosystems", "Food webs", "Biodiversity"],
        language="en",
        source_type="school_resource",
        subject="Biology",
        education_level="School",
        content_type="study material",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://business.example.edu/management/lecture/",
        title="Business Management: Sample Lecture",
        description="Sample lecture introducing management and business strategy.",
        body=(
            "Consider organizational goals, decision-making, markets, and "
            "business strategy in this introductory lecture sample."
        ),
        headings=["Organizations", "Decision-making", "Strategy"],
        language="en",
        source_type="business_education",
        subject="Business / MBA",
        education_level="University",
        content_type="lecture",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://economics.example.edu/microeconomics/",
        title="Microeconomics: A Beginner Article",
        description="Sample article explaining supply, demand, and markets.",
        body=(
            "Learn how choices, incentives, supply, and demand shape markets "
            "through simple economic examples."
        ),
        headings=["Choices and incentives", "Supply", "Demand"],
        language="en",
        source_type="educational_article",
        subject="Economics",
        education_level="University",
        content_type="article",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://humanities.example.edu/history/lecture/",
        title="World History: Sources and Perspectives",
        description="Sample school lecture on interpreting historical sources.",
        body=(
            "Explore primary sources, historical context, and differing "
            "perspectives in a short world history lesson."
        ),
        headings=["Primary sources", "Context", "Perspectives"],
        language="en",
        source_type="school_resource",
        subject="Humanities",
        education_level="School",
        content_type="lecture",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://social-science.example.edu/research/blog/",
        title="Reading Social Science Research",
        description="Sample blog article about evidence and research methods.",
        body=(
            "A short educational blog sample describing research questions, "
            "evidence, surveys, and responsible interpretation."
        ),
        headings=["Questions", "Evidence", "Interpretation"],
        language="en",
        source_type="educational_blog",
        subject="Social Sciences",
        education_level="Professional",
        content_type="blog",
        difficulty="beginner",
    ),
    DocumentCreate(
        url="https://medicine.example.edu/anatomy/",
        title="Human Anatomy Reference for Medical Study",
        description="Sample reference resource for introductory medical study.",
        body=(
            "Review major body systems, anatomical terminology, and the "
            "organization of a clinical anatomy reference."
        ),
        headings=["Body systems", "Anatomical terms", "Reference guide"],
        language="en",
        source_type="medical_education",
        subject="Medicine",
        education_level="University",
        content_type="documentation",
        difficulty="intermediate",
    ),
    DocumentCreate(
        url="https://specialized.example.edu/interdisciplinary/",
        title="Specialized Interdisciplinary Learning Resource",
        description=(
            "Sample resource demonstrating specialized subject and resource "
            "classifications."
        ),
        body=(
            "This sample combines ideas from several disciplines and illustrates "
            "how a specialized educational resource can be cataloged."
        ),
        headings=["Interdisciplinary overview", "Specialized topics"],
        language="en",
        source_type="specialized_education",
        subject="Other / Specialized",
        education_level="Research",
        content_type="Other / Specialized",
        difficulty="advanced",
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
