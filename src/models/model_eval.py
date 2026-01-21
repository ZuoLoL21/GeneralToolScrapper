"""Evaluation context models for scoring tools."""

from pydantic import BaseModel, Field, model_validator


class ScoreWeights(BaseModel):
    """Configurable dimension weights for scoring.

    All weights must sum to 1.0 for proper score calculation.
    """

    popularity: float = Field(default=0.25, ge=0.0, le=1.0)
    security: float = Field(default=0.35, ge=0.0, le=1.0)
    maintenance: float = Field(default=0.25, ge=0.0, le=1.0)
    trust: float = Field(default=0.15, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "ScoreWeights":
        """Validate that weights sum to 1.0."""
        total = self.popularity + self.security + self.maintenance + self.trust
        if abs(total - 1.0) > 0.001:
            msg = f"Weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self


class FilterThresholds(BaseModel):
    """Configurable filtering thresholds for tool visibility."""

    min_downloads: int = Field(default=1000, ge=0, description="Minimum download count")
    min_stars: int = Field(default=100, ge=0, description="Minimum star count")
    max_days_since_update: int = Field(
        default=365, ge=0, description="Maximum days since last update"
    )
    min_score: float = Field(
        default=30.0, ge=0.0, le=100.0, description="Minimum quality score to be visible"
    )
