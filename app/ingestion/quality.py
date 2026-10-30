import re

from app.ingestion.models import ExtractedDocument

MINIMUM_EDUCATIONAL_TEXT_LENGTH = 160
MINIMUM_BODY_TEXT_LENGTH = 100
NON_CONTENT_TITLE = re.compile(
    r"^(?:404(?:\s+not\s+found)?|403(?:\s+forbidden)?|page not found|not found|"
    r"access denied|page unavailable|just a moment|verify you are human|"
    r"cookie (?:notice|policy|settings)|consent required)"
    r"(?:\s*[-|:].*)?$",
    re.IGNORECASE,
)


def educational_content_skip_reason(document: ExtractedDocument) -> str | None:
    """Reject obvious error pages and pages with too little substantive text."""
    title = (document.title or "").strip()
    if not title:
        return "Page has no extracted title."
    if NON_CONTENT_TITLE.match(title):
        return "Page title indicates an error or access gate."

    body = (document.body or "").strip()
    if len(body) < MINIMUM_BODY_TEXT_LENGTH:
        return "Page contains insufficient body text."

    text = " ".join(
        value.strip()
        for value in (document.description, *document.headings, document.body)
        if value and value.strip()
    )
    if len(text) < MINIMUM_EDUCATIONAL_TEXT_LENGTH:
        return "Page contains insufficient educational text."
    return None
