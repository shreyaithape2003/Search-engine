"""Educational metadata taxonomy and deterministic classification."""

from app.classification.classifier import EducationalClassifier
from app.classification.models import (
    ClassificationEvidence,
    ClassificationInput,
    ClassificationResult,
)

__all__ = [
    "ClassificationEvidence",
    "ClassificationInput",
    "ClassificationResult",
    "EducationalClassifier",
]
