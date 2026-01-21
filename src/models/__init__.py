"""Pydantic models for GeneralToolScraper."""

from src.models.model_classification import (
    Classification,
    ClassificationCacheEntry,
    ClassificationOverride,
)
from src.models.model_eval import (
    FilterThresholds,
    ScoreWeights,
)
from src.models.model_stats import (
    CategoryStats,
    DistributionStats,
    EvalContext,
    GlobalStats,
)
from src.models.model_storage import (
    RawScrapeFile,
    ScoresFile,
    ToolScore,
)
from src.models.model_tool import (
    DominantDimension,
    FilterReasons,
    FilterState,
    FilterStatus,
    Identity,
    Lifecycle,
    Maintainer,
    MaintainerType,
    Maintenance,
    Metrics,
    ScoreAnalysis,
    ScoreBreakdown,
    Security,
    SecurityStatus,
    SourceType,
    Tool,
    Vulnerabilities,
)

__all__ = [
    # Tool models
    "DominantDimension",
    "FilterReasons",
    "FilterState",
    "FilterStatus",
    "Identity",
    "Lifecycle",
    "Maintainer",
    "MaintainerType",
    "Maintenance",
    "Metrics",
    "ScoreAnalysis",
    "ScoreBreakdown",
    "Security",
    "SecurityStatus",
    "SourceType",
    "Tool",
    "Vulnerabilities",
    # Classification models
    "Classification",
    "ClassificationCacheEntry",
    "ClassificationOverride",
    # Evaluation models
    "FilterThresholds",
    "ScoreWeights",
    # Statistics models
    "CategoryStats",
    "DistributionStats",
    "EvalContext",
    "GlobalStats",
    # Storage models
    "RawScrapeFile",
    "ScoresFile",
    "ToolScore",
]
