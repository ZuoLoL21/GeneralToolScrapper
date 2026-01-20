from datetime import datetime

from pydantic import BaseModel, Field

from src.Models.common import _utc_now


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
    source: str = Field(description="'llm' | 'override' | 'manual'")
