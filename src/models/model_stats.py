"""Statistics models for normalization and evaluation context."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.common import _utc_now
from src.models.model_eval import FilterThresholds, ScoreWeights


class DistributionStats(BaseModel):
    """Statistics for a single metric within a category.

    Used for Z-score normalization of popularity metrics.
    """

    min: int = Field(ge=0, description="Minimum value")
    max: int = Field(ge=0, description="Maximum value")
    median: float = Field(ge=0.0, description="Median value")
    p25: float = Field(ge=0.0, description="25th percentile")
    p75: float = Field(ge=0.0, description="75th percentile")
    log_mean: float = Field(description="Mean of log-transformed values")
    log_std: float = Field(ge=0.0, description="Std dev of log-transformed values")


class CategoryStats(BaseModel):
    """Statistics for a category/subcategory used in popularity normalization.

    When sample_size < 10, evaluators should fall back to global stats.
    """

    sample_size: int = Field(ge=0, description="Number of tools in category")
    downloads: DistributionStats
    stars: DistributionStats


class GlobalStats(BaseModel):
    """Global statistics across all tools.

    Used as fallback when category has insufficient sample size.
    """

    computed_at: datetime = Field(default_factory=_utc_now)
    total_tools: int = Field(ge=0, description="Total number of tools")
    downloads: DistributionStats
    stars: DistributionStats


class EvalContext(BaseModel):
    """Evaluation context for stateless evaluators.

    Evaluators are pure functions. All external data comes through this context.
    Evaluators never query storage directly. This enables:
    - Trivially testable evaluators (just pass mock context)
    - Parallelizable evaluation
    - Predictable, reproducible scoring
    """

    global_stats: GlobalStats
    category_stats: dict[str, CategoryStats] = Field(
        default_factory=dict, description="Key: 'category/subcategory'"
    )

    # Configuration
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    thresholds: FilterThresholds = Field(default_factory=FilterThresholds)

    # Score versioning
    score_version: str = Field(default="1.0", description="Hash of algorithm + weights")
