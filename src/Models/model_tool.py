from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field

from src.Models.common import _utc_now


class SourceType(str, Enum):
    """Supported tool sources."""

    DOCKER_HUB = "docker_hub"
    GITHUB = "github"
    HELM = "helm"
    WEB = "web"


class MaintainerType(str, Enum):
    """Types of tool maintainers."""

    OFFICIAL = "official"
    COMPANY = "company"
    USER = "user"


class SecurityStatus(str, Enum):
    """Security scan status."""

    OK = "ok"
    VULNERABLE = "vulnerable"
    UNKNOWN = "unknown"


class Lifecycle(str, Enum):
    """Tool lifecycle stages."""

    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    STABLE = "stable"
    LEGACY = "legacy"


class Identity(BaseModel):
    """Tool identity information for grouping related artifacts."""

    canonical_name: str = Field(description="Normalized name grouping related artifacts")
    aliases: list[str] = Field(default_factory=list, description="Alternative search names")
    variants: list[str] = Field(
        default_factory=list, description="IDs of same tool from different sources"
    )


class Maintainer(BaseModel):
    """Information about the tool maintainer."""

    name: str = Field(description="Publisher name or organization")
    type: MaintainerType = Field(description="Type of maintainer")
    verified: bool = Field(default=False, description="Platform verification badge")


class Metrics(BaseModel):
    """Raw metrics from the source platform."""

    downloads: int = Field(default=0, ge=0, description="Total download/pull count")
    stars: int = Field(default=0, ge=0, description="Community appreciation metric")
    usage_amount: int = Field(default=0, ge=0, description="Secondary usage (forks, etc.)")


class Vulnerabilities(BaseModel):
    """Vulnerability counts by severity."""

    critical: int = Field(default=0, ge=0, description="CVSS 9.0-10.0")
    high: int = Field(default=0, ge=0, description="CVSS 7.0-8.9")
    medium: int = Field(default=0, ge=0, description="CVSS 4.0-6.9")
    low: int = Field(default=0, ge=0, description="CVSS 0.1-3.9")


class Security(BaseModel):
    """Security information from vulnerability scans."""

    status: SecurityStatus = Field(
        default=SecurityStatus.UNKNOWN, description="Overall security status"
    )
    trivy_scan_date: datetime | None = Field(default=None, description="Date of last Trivy scan")
    vulnerabilities: Vulnerabilities = Field(
        default_factory=Vulnerabilities, description="Vulnerability counts by severity"
    )

    @computed_field
    @property
    def is_safe(self) -> bool:
        """Computed safety flag based on vulnerabilities."""
        return (
            self.vulnerabilities.critical == 0
            and self.vulnerabilities.high == 0
            and self.status != SecurityStatus.VULNERABLE
        )


class Maintenance(BaseModel):
    """Maintenance and update information."""

    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    last_updated: datetime | None = Field(default=None, description="Last update timestamp")
    update_frequency_days: int | None = Field(
        default=None, ge=0, description="Average days between updates"
    )
    is_deprecated: bool = Field(default=False, description="Whether the tool is deprecated")


class ScoreBreakdown(BaseModel):
    """Breakdown of quality score by dimension."""

    popularity: float = Field(default=0.0, ge=0.0, le=100.0)
    security: float = Field(default=0.0, ge=0.0, le=100.0)
    maintenance: float = Field(default=0.0, ge=0.0, le=100.0)
    trust: float = Field(default=0.0, ge=0.0, le=100.0)


class Tool(BaseModel):
    """Main tool model representing a scraped artifact."""

    # Identification
    id: str = Field(description="Unique ID in format '{source}:{namespace}/{name}'")
    name: str = Field(description="Display name from source")
    source: SourceType = Field(description="Source platform")
    source_url: str = Field(description="Direct link to tool on source platform")
    description: str = Field(default="", description="Short description from source")

    # Identity grouping
    identity: Identity = Field(default_factory=lambda: Identity(canonical_name=""))

    # Maintainer info
    maintainer: Maintainer = Field(
        default_factory=lambda: Maintainer(name="unknown", type=MaintainerType.USER)
    )

    # Raw metrics
    metrics: Metrics = Field(default_factory=Metrics)

    # Security
    security: Security = Field(default_factory=Security)

    # Maintenance
    maintenance: Maintenance = Field(default_factory=Maintenance)

    # Categorization
    tags: list[str] = Field(default_factory=list, description="Raw tags from source")
    taxonomy_version: str = Field(default="1.0", description="Categorization version for re-runs")
    primary_category: str | None = Field(
        default=None, description="Primary category (databases, monitoring, etc.)"
    )
    primary_subcategory: str | None = Field(
        default=None, description="Primary subcategory (relational, metrics, etc.)"
    )
    secondary_categories: list[str] = Field(
        default_factory=list, description="Additional categories"
    )
    lifecycle: Lifecycle = Field(default=Lifecycle.ACTIVE, description="Tool lifecycle stage")

    # Derived scores
    quality_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Weighted composite score 0-100"
    )
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)

    # Metadata
    scraped_at: datetime = Field(default_factory=_utc_now, description="Scrape timestamp")

    def model_post_init(self, __context: object) -> None:
        """Set canonical name to tool name if not provided."""
        if not self.identity.canonical_name:
            self.identity.canonical_name = self.name.lower()
