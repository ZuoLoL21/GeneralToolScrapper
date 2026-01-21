"""Categorization module for tool classification."""

from src.categorization.classifier import Classifier
from src.categorization.human_maintained import TAXONOMY
from src.categorization.identity import IdentityResolver
from src.categorization.taxonomy import get_all_categories
from src.models.model_classification import (
    Category,
    ClassificationResult,
    ResolutionSource,
    Subcategory,
)

__all__ = [
    # Taxonomy
    "TAXONOMY",
    "Category",
    "Subcategory",
    "get_all_categories",
    # Identity
    "IdentityResolver",
    "ResolutionSource",
    # Classifier
    "Classifier",
    "ClassificationResult",
]
