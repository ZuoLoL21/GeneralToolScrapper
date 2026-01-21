"""Storage file models for persisting scraped data and scores."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.common import _utc_now
from src.models.model_eval import ScoreWeights
from src.models.model_tool import (
    ScoreAnalysis,
    ScoreBreakdown,
    SourceType,
    Tool,
)


class RawScrapeFile(BaseModel):
    """Raw scrape file stored in data/raw/{source}/{date}_scrape.json.

    Immutable once written. Version field enables schema migrations on load.
    """

    scraped_at: datetime = Field(default_factory=_utc_now)
    source: SourceType
    version: str = Field(default="1.0", description="Schema version for migrations")
    tools: list[Tool]


class ToolScore(BaseModel):
    """Score entry for a single tool."""

    quality_score: float = Field(ge=0.0, le=100.0)
    breakdown: ScoreBreakdown
    analysis: ScoreAnalysis = Field(default_factory=ScoreAnalysis)


class ScoresFile(BaseModel):
    """Scores file stored in data/processed/scores.json.

    Contains computed scores with metadata for reproducibility.
    """

    version: str = Field(default="1.0")
    computed_at: datetime = Field(default_factory=_utc_now)
    score_version: str = Field(description="Hash of algorithm + weights")
    weights: ScoreWeights
    scores: dict[str, ToolScore] = Field(default_factory=dict, description="Key: tool ID")
