"""Classification and categorization models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final

from pydantic import BaseModel, Field

from src.models.common import _utc_now

# Version constants
IDENTITY_VERSION: Final[str] = "1.0"
TAXONOMY_VERSION: Final[str] = "1.0"


# === Pydantic Models (for serialization/validation) ===


class Classification(BaseModel):
    """The result of classifying a tool (from LLM or cache)."""

    primary_category: str
    primary_subcategory: str
    secondary_categories: list[str] = Field(default_factory=list)


class ClassificationOverride(BaseModel):
    """Manual override entry with reason for correcting misclassifications."""

    primary_category: str
    primary_subcategory: str
    secondary_categories: list[str] = Field(default_factory=list)
    reason: str = Field(description="Explanation for the override")


class ClassificationCacheEntry(BaseModel):
    """Cache entry wrapping a classification with metadata."""

    classification: Classification
    classified_at: datetime = Field(default_factory=_utc_now)
    source: str = Field(description="'llm' | 'override' | 'heuristic' | 'fallback'")


class KeywordAssignment(BaseModel):
    """Keyword assignment result (property classification)."""

    keywords: list[str] = Field(
        default_factory=list, description="Assigned property keywords"
    )


class KeywordAssignmentCacheEntry(BaseModel):
    """Cache entry for keyword assignments."""

    assignment: KeywordAssignment
    assigned_at: datetime = Field(default_factory=_utc_now)
    source: str = Field(description="'cache' | 'override' | 'heuristic' | 'fallback'")


# === Enums ===


class ResolutionSource(str, Enum):
    """How the canonical name was determined."""

    OVERRIDE = "override"  # Manual override in overrides.json
    OFFICIAL = "official"  # Official Docker image or org-owned repo
    VERIFIED = "verified"  # Verified publisher matching known canonical
    FALLBACK = "fallback"  # Default: use artifact slug


# === Dataclasses (lightweight internal types) ===


@dataclass
class ClassificationResult:
    """Result of classifying a tool."""

    classification: Classification
    confidence: float
    source: str  # "cache" | "override" | "heuristic" | "fallback"
    needs_review: bool = False
    cache_entry: ClassificationCacheEntry | None = None


@dataclass
class TagMatch:
    """A matched tag with its category/subcategory."""

    tag: str
    category: str
    subcategory: str
    is_exact: bool = False  # Exact keyword match vs partial


@dataclass
class IdentityResolution:
    """Result of resolving a tool's canonical identity."""

    canonical_name: str
    resolution_source: ResolutionSource
    resolution_confidence: float
    identity_version: str = IDENTITY_VERSION


@dataclass
class KeywordAssignmentResult:
    """Result of keyword assignment with metadata."""

    assignment: KeywordAssignment
    confidence: float
    source: str  # "cache" | "override" | "heuristic" | "fallback"
    cache_entry: KeywordAssignmentCacheEntry | None = None


# === Taxonomy Dataclasses ===


@dataclass(frozen=True)
class Subcategory:
    """A subcategory within a category."""

    name: str
    description: str
    keywords: tuple[str, ...]  # Keywords for tag-based matching


@dataclass(frozen=True)
class Category:
    """A top-level category containing subcategories."""

    name: str
    description: str
    subcategories: tuple[Subcategory, ...]

    def get_subcategory(self, name: str) -> Subcategory | None:
        """Get subcategory by name."""
        for sub in self.subcategories:
            if sub.name == name:
                return sub
        return None

    def has_subcategory(self, name: str) -> bool:
        """Check if subcategory exists."""
        return self.get_subcategory(name) is not None
