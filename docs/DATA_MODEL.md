# Data Model

This document defines all Pydantic models used in GeneralToolScraper, with design rationale for each field and structure.

## Design Principles

### Observed vs Inferred Separation

The data model explicitly separates:

| Category | Description | Examples |
|----------|-------------|----------|
| **Observed** | Data directly from source APIs | downloads, stars, last_updated, vulnerabilities |
| **Inferred** | Computed by our algorithms | lifecycle, trust_score, quality_score, is_safe |

This separation enables:

- **Auditing:** Know which data came from sources vs. algorithms
- **Debugging:** Trace score anomalies to source data
- **ML readiness:** Clean separation of features (observed) from labels (inferred)
- **Recomputation:** Change algorithms without re-scraping

### Immutability of Raw Data

Raw scraped data is never modified. All transformations create new processed data. This ensures:

- Reproducibility across algorithm changes
- Audit trail for debugging
- Ability to backfill new fields

## Core Models

### Tool

The main model representing a scraped tool artifact.

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class Tool(BaseModel):
    """
    A single artifact from a source (Docker image, GitHub repo, Helm chart).

    Design decisions:
    - `id` uses format "{source}:{namespace}/{name}" for global uniqueness
    - Observed and inferred data are explicitly separated
    - All optional fields have sensible defaults
    """

    # === IDENTIFICATION ===
    id: str = Field(
        description="Globally unique ID: {source}:{namespace}/{name}",
        examples=["docker_hub:library/postgres", "github:grafana/grafana"]
    )
    name: str = Field(description="Display name from source")
    source: Literal["docker_hub", "github", "helm"] = Field(
        description="Source platform identifier"
    )
    source_url: str = Field(description="Direct link to tool on source platform")
    description: str = Field(default="", description="Short description from source")

    # === NESTED MODELS ===
    identity: "Identity"
    maintainer: "Maintainer"
    observed: "ObservedData"
    inferred: "InferredData"

    # === CATEGORIZATION ===
    tags: list[str] = Field(default_factory=list, description="Raw tags from source")
    taxonomy_version: str = Field(
        default="v1",
        description="Version of taxonomy used for categorization"
    )
    primary_category: str = Field(default="uncategorized")
    primary_subcategory: str = Field(default="uncategorized")
    secondary_categories: list[str] = Field(
        default_factory=list,
        description="Additional categories in 'category/subcategory' format"
    )

    # === FILTERING ===
    filter_status: "FilterStatus"

    # === METADATA ===
    scraped_at: datetime
    schema_version: str = Field(default="1.0")
```

**Rationale for key decisions:**

| Decision | Rationale |
|----------|-----------|
| Composite `id` format | Ensures global uniqueness across sources; human-readable |
| Separate `identity` model | Identity resolution is complex enough to warrant its own namespace |
| `observed` / `inferred` split | Explicit separation prevents confusion about data provenance |
| `filter_status` as object | Machine-readable reasons enable automation and better UX |

### Identity

Manages canonical name resolution and artifact grouping.

```python
class Identity(BaseModel):
    """
    Canonical identity and variant tracking.

    Design decisions:
    - `canonical_name` groups related artifacts across sources
    - `resolution_source` tracks how the canonical name was determined
    - `resolution_confidence` enables filtering/warnings for uncertain mappings
    """

    canonical_name: str = Field(
        description="Normalized name grouping related artifacts (e.g., 'postgres')"
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative search names for this tool"
    )
    variants: list[str] = Field(
        default_factory=list,
        description="IDs of same tool from different sources"
    )

    # === RESOLUTION PROVENANCE ===
    resolution_source: Literal["official", "verified", "override", "fallback"] = Field(
        description="How the canonical name was determined"
    )
    resolution_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in canonical name assignment (1.0 = certain)"
    )
    identity_version: str = Field(
        default="v1",
        description="Version of identity resolution rules"
    )
```

**Confidence heuristics:**

| Resolution Source | Typical Confidence |
|------------------|-------------------|
| override | 1.0 |
| official | 0.95 |
| verified | 0.85 |
| fallback | 0.6 |

### Maintainer

Publisher/maintainer information.

```python
class Maintainer(BaseModel):
    """
    Publisher information and trust signals.

    Design decisions:
    - `type` uses fixed enum to ensure consistent trust scoring
    - `verified` is source-specific (Docker verified publisher vs GitHub org badge)
    """

    name: str = Field(description="Publisher name or organization")
    type: Literal["official", "company", "user"] = Field(
        description="Publisher tier for trust scoring"
    )
    verified: bool = Field(
        default=False,
        description="Platform verification badge present"
    )
```

### ObservedData

Raw data directly from source APIs.

```python
class ObservedData(BaseModel):
    """
    Data observed directly from source APIs.

    Design principle: This model contains ONLY data that came from external sources.
    Nothing here is computed or inferred by our system.
    """

    # === POPULARITY METRICS ===
    downloads: int = Field(default=0, ge=0, description="Total download/pull count")
    stars: int = Field(default=0, ge=0, description="Community appreciation metric")
    forks: int = Field(default=0, ge=0, description="Fork count (GitHub)")

    # === MAINTENANCE ===
    created_at: datetime | None = Field(default=None)
    last_updated: datetime | None = Field(default=None)
    update_frequency_days: int | None = Field(
        default=None,
        description="Typical days between updates (computed from history)"
    )
    is_deprecated: bool = Field(default=False)

    # === SECURITY ===
    security: "SecurityObserved"
```

**Rationale:** Keeping observed data pure enables:
- Re-running inference algorithms without re-scraping
- Debugging score anomalies by examining source data
- Training ML models with clean feature/label separation

### SecurityObserved

Raw security scan results.

```python
class SecurityObserved(BaseModel):
    """
    Raw security scan data from Trivy.

    Design decisions:
    - Separate from inferred `is_safe` / `is_blocking` flags
    - Unknown status is explicit (not just missing data)
    - Scan metadata included for cache invalidation
    """

    status: Literal["ok", "vulnerable", "unknown"] = Field(default="unknown")
    trivy_scan_date: datetime | None = Field(default=None)
    vulnerabilities: "VulnerabilityCounts" = Field(default_factory=lambda: VulnerabilityCounts())


class VulnerabilityCounts(BaseModel):
    """Vulnerability counts by severity level."""

    critical: int = Field(default=0, ge=0, description="CVSS 9.0-10.0")
    high: int = Field(default=0, ge=0, description="CVSS 7.0-8.9")
    medium: int = Field(default=0, ge=0, description="CVSS 4.0-6.9")
    low: int = Field(default=0, ge=0, description="CVSS 0.1-3.9")
```

### InferredData

Computed/derived data from our algorithms.

```python
class InferredData(BaseModel):
    """
    Data computed by our algorithms from observed data.

    Design principle: Everything here is derived and can be recomputed.
    Changes to algorithms only require re-running inference, not re-scraping.
    """

    # === LIFECYCLE ===
    lifecycle: Literal["experimental", "active", "stable", "legacy"] = Field(
        default="active"
    )

    # === SECURITY (DERIVED) ===
    is_safe: bool = Field(
        default=True,
        description="Computed safety flag based on vulnerability thresholds"
    )
    is_blocking: bool = Field(
        default=False,
        description="Hard block: exploitable critical or policy violation"
    )

    # === SCORES ===
    quality_score: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Weighted composite score"
    )
    score_breakdown: "ScoreBreakdown" = Field(default_factory=lambda: ScoreBreakdown())
    score_analysis: "ScoreAnalysis" = Field(default_factory=lambda: ScoreAnalysis())
    score_version: str = Field(
        default="",
        description="Hash of scoring algorithm + weights for comparability"
    )
```

### ScoreBreakdown

Per-dimension scores.

```python
class ScoreBreakdown(BaseModel):
    """
    Individual dimension scores (all 0-100).

    Design decisions:
    - Each dimension is independently 0-100 for interpretability
    - Weights are applied at composite score level, not here
    """

    popularity: float = Field(default=0.0, ge=0.0, le=100.0)
    security: float = Field(default=0.0, ge=0.0, le=100.0)
    maintenance: float = Field(default=0.0, ge=0.0, le=100.0)
    trust: float = Field(default=0.0, ge=0.0, le=100.0)
```

### ScoreAnalysis

Interpretability metadata for scores.

```python
class ScoreAnalysis(BaseModel):
    """
    Metadata for interpreting and explaining scores.

    Design decisions:
    - `dominant_dimension` surfaces when one factor is driving the score
    - `dominance_ratio` quantifies how skewed the score is
    - Used by `gts explain` to generate warnings
    """

    dominant_dimension: Literal["popularity", "security", "maintenance", "trust", "balanced"] = Field(
        default="balanced"
    )
    dominance_ratio: float = Field(
        default=1.0,
        description="Ratio of highest to second-highest dimension score"
    )

    # Future: could add percentile_in_category, comparison_to_canonical_peers, etc.
```

### FilterStatus

Machine-readable filtering state.

```python
class FilterStatus(BaseModel):
    """
    Filtering state with reason codes for transparency.

    Design decisions:
    - `state` is the final visibility decision
    - `reasons` are machine-readable codes for automation/UI
    - Enables `gts explain` to show why tools are hidden/excluded
    """

    state: Literal["visible", "hidden", "excluded"] = Field(default="visible")
    reasons: list[str] = Field(
        default_factory=list,
        description="Machine-readable reason codes"
    )

# Reason code constants
class FilterReasons:
    """Standard filter reason codes."""

    # Exclusion reasons (never shown)
    LOW_DOWNLOADS = "LOW_DOWNLOADS"
    STALE = "STALE"
    DEPRECATED = "DEPRECATED"
    CRITICAL_VULNERABILITY = "CRITICAL_VULNERABILITY"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    SPAM = "SPAM"

    # Hidden reasons (shown with --include-hidden)
    EXPERIMENTAL = "EXPERIMENTAL"
    LEGACY = "LEGACY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    LOW_SCORE = "LOW_SCORE"
```

**State semantics:**

| State | Behavior | Use Cases |
|-------|----------|-----------|
| `visible` | Shown by default | Quality tools that pass all filters |
| `hidden` | Not shown by default, visible with `--include-hidden` | Experimental, legacy but widely-used |
| `excluded` | Never shown in any output | Spam, malicious, policy violations |

## Classification Models

All classification-related models are in `src/models/model_classification.py`.

### Taxonomy Models

```python
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

    def get_subcategory(self, name: str) -> Subcategory | None: ...
    def has_subcategory(self, name: str) -> bool: ...
```

### Classification

Result of classifying a tool.

```python
class Classification(BaseModel):
    """
    Classification result from LLM or cache.

    Design decisions:
    - Matches taxonomy structure exactly
    - `secondary_categories` use "category/subcategory" format for consistency
    """

    primary_category: str
    primary_subcategory: str
    secondary_categories: list[str] = Field(default_factory=list)
```

### ClassificationResult

Classifier output with metadata.

```python
@dataclass
class ClassificationResult:
    """Result of classifying a tool."""
    classification: Classification
    confidence: float
    source: str  # "cache" | "override" | "heuristic" | "fallback"
    needs_review: bool = False
    cache_entry: ClassificationCacheEntry | None = None
```

### TagMatch

Tag matching for heuristic classification.

```python
@dataclass
class TagMatch:
    """A matched tag with its category/subcategory."""
    tag: str
    category: str
    subcategory: str
    is_exact: bool = False  # Exact keyword match vs partial
```

### ClassificationOverride

Manual override entry.

```python
class ClassificationOverride(BaseModel):
    """
    Manual classification override with explanation.

    Design decisions:
    - `reason` is required to document why the override exists
    - Keyed by artifact ID in overrides.json
    """

    primary_category: str
    primary_subcategory: str
    secondary_categories: list[str] = Field(default_factory=list)
    reason: str = Field(description="Explanation for the override")

    # Optional: override canonical name too
    canonical_name: str | None = Field(default=None)
    lifecycle: Literal["experimental", "active", "stable", "legacy"] | None = Field(default=None)
```

### ClassificationCacheEntry

Cache wrapper with metadata.

```python
class ClassificationCacheEntry(BaseModel):
    """
    Cache entry wrapping classification with provenance.

    Design decisions:
    - `source` tracks how the classification was determined
    - Enables cache invalidation and audit trails
    """

    classification: Classification
    classified_at: datetime
    source: str  # "llm" | "override" | "heuristic" | "fallback"
```

### Identity Resolution Models

```python
class ResolutionSource(str, Enum):
    """How the canonical name was determined."""
    OVERRIDE = "override"  # Manual override in overrides.json
    OFFICIAL = "official"  # Official Docker image or org-owned repo
    VERIFIED = "verified"  # Verified publisher matching known canonical
    FALLBACK = "fallback"  # Default: use artifact slug


@dataclass
class IdentityResolution:
    """Result of resolving a tool's canonical identity."""
    canonical_name: str
    resolution_source: ResolutionSource
    resolution_confidence: float
    identity_version: str = IDENTITY_VERSION
```

**Confidence heuristics:**

| Resolution Source | Typical Confidence |
|------------------|-------------------|
| OVERRIDE | 1.0 |
| OFFICIAL | 0.95 |
| VERIFIED | 0.85 |
| FALLBACK | 0.6 |

### Version Constants

```python
IDENTITY_VERSION: Final[str] = "1.0"
TAXONOMY_VERSION: Final[str] = "1.0"
```

## Scoring Context Models

### EvalContext

Context passed to evaluators.

```python
class EvalContext(BaseModel):
    """
    Evaluation context for stateless evaluators.

    Design principle: Evaluators are pure functions. All external data
    comes through this context. Evaluators never query storage directly.

    This enables:
    - Trivially testable evaluators (just pass mock context)
    - Parallelizable evaluation
    - Predictable, reproducible scoring
    """

    global_stats: "GlobalStats"
    category_stats: dict[str, "CategoryStats"]  # key: "category/subcategory"

    # Configuration
    weights: "ScoreWeights"
    thresholds: "FilterThresholds"

    # Score versioning
    score_version: str = Field(description="Hash of algorithm + weights")


class ScoreWeights(BaseModel):
    """Configurable dimension weights."""

    popularity: float = Field(default=0.25, ge=0.0, le=1.0)
    security: float = Field(default=0.35, ge=0.0, le=1.0)
    maintenance: float = Field(default=0.25, ge=0.0, le=1.0)
    trust: float = Field(default=0.15, ge=0.0, le=1.0)

    def __post_init__(self):
        total = self.popularity + self.security + self.maintenance + self.trust
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


class FilterThresholds(BaseModel):
    """Configurable filtering thresholds."""

    min_downloads: int = Field(default=1000)
    min_stars: int = Field(default=100)
    max_days_since_update: int = Field(default=365)
    min_score: float = Field(default=30.0)
```

## Storage Models

### DistributionStats

Statistics for a single metric.

```python
class DistributionStats(BaseModel):
    """
    Statistics for a single metric (downloads or stars) within a category.

    Design decisions:
    - Log-transformed stats (log_mean, log_std) for Z-score normalization
    - Percentiles for alternative ranking methods
    """

    min: int
    max: int
    median: float
    p25: float = Field(description="25th percentile")
    p75: float = Field(description="75th percentile")
    log_mean: float = Field(description="Mean of log-transformed values")
    log_std: float = Field(description="Std dev of log-transformed values")
```

### CategoryStats

Statistics for a category/subcategory.

```python
class CategoryStats(BaseModel):
    """
    Statistics for a category/subcategory used in popularity normalization.

    Design decisions:
    - `sample_size` for fallback logic (< 10 tools uses global stats)
    - Separate distributions for downloads and stars
    """

    sample_size: int = Field(description="Number of tools in category")
    downloads: DistributionStats
    stars: DistributionStats


class GlobalStats(BaseModel):
    """
    Global statistics across all tools.

    Used as fallback when category has insufficient sample size.
    """

    computed_at: datetime
    total_tools: int
    downloads: DistributionStats
    stars: DistributionStats
```

### Storage File Models

```python
class RawScrapeFile(BaseModel):
    """
    Raw scrape file stored in data/raw/{source}/{date}_scrape.json.

    Design decisions:
    - `version` for schema migrations on load
    - Immutable once written
    """

    scraped_at: datetime
    source: Literal["docker_hub", "github", "helm"]
    version: str = Field(description="Schema version for migrations")
    tools: list[Tool]


class ScoresFile(BaseModel):
    """
    Scores file stored in data/processed/scores.json.

    Design decisions:
    - `score_version` for comparability checks
    - `weights` recorded for reproducibility
    """

    version: str
    computed_at: datetime
    score_version: str = Field(description="Hash of algorithm + weights")
    weights: ScoreWeights
    scores: dict[str, "ToolScore"]  # key: tool ID


class ToolScore(BaseModel):
    """Score entry for a single tool."""

    quality_score: float
    breakdown: ScoreBreakdown
    analysis: ScoreAnalysis
```

## Canonical Tool Model

While artifacts are stored individually, the system conceptually groups them under canonical tools.

```python
class CanonicalTool(BaseModel):
    """
    Virtual model representing a canonical tool across sources.

    Design decisions:
    - Not persisted separately (derived from artifacts)
    - Defines aggregation contract for future cross-source scoring
    - Clarifies which fields are shared vs artifact-specific

    Shared across variants:
    - canonical_name, primary_category, lifecycle

    Artifact-specific:
    - downloads, security, individual scores
    """

    canonical_name: str
    variants: list[str] = Field(description="Artifact IDs belonging to this canonical tool")

    # Shared classification
    primary_category: str
    primary_subcategory: str
    secondary_categories: list[str]
    lifecycle: Literal["experimental", "active", "stable", "legacy"]

    # Future: aggregated scores from variants
    # aggregated_score: float
    # best_variant_id: str
```

**Why define this explicitly:**

- Makes future score aggregation intentional, not accidental
- Prevents arbitrary "pick first variant" logic
- Clarifies which fields are shared (category, lifecycle) vs artifact-specific (downloads, security)
- Enables cross-source comparisons (Docker postgres vs GitHub postgres vs Helm postgresql)

## Model Relationships

```
Tool (main artifact model)
├── identity: Identity
│   └── resolution_source, resolution_confidence
├── maintainer: Maintainer
├── observed: ObservedData
│   └── security: SecurityObserved
│       └── vulnerabilities: VulnerabilityCounts
├── inferred: InferredData
│   ├── score_breakdown: ScoreBreakdown
│   └── score_analysis: ScoreAnalysis
└── filter_status: FilterStatus

EvalContext (scoring context)
├── global_stats: GlobalStats
├── category_stats: dict[str, CategoryStats]
├── weights: ScoreWeights
└── thresholds: FilterThresholds

Classification (category assignment)
└── ClassificationCacheEntry (cache wrapper)

CanonicalTool (virtual grouping)
└── variants: list[Tool.id]
```
