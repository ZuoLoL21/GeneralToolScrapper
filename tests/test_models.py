"""Tests for Pydantic models."""  # noqa: N999

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

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


class TestIdentity:
    """Tests for the Identity model."""

    def test_basic_creation(self) -> None:
        identity = Identity(canonical_name="postgres")
        assert identity.canonical_name == "postgres"
        assert identity.aliases == []
        assert identity.variants == []

    def test_with_aliases_and_variants(self) -> None:
        identity = Identity(
            canonical_name="postgres",
            aliases=["postgresql", "pg"],
            variants=["docker_hub:library/postgres", "github:postgres/postgres"],
        )
        assert identity.canonical_name == "postgres"
        assert "postgresql" in identity.aliases
        assert len(identity.variants) == 2


class TestMaintainer:
    """Tests for the Maintainer model."""

    def test_basic_creation(self) -> None:
        maintainer = Maintainer(name="Docker", type=MaintainerType.OFFICIAL)
        assert maintainer.name == "Docker"
        assert maintainer.type == MaintainerType.OFFICIAL
        assert maintainer.verified is False

    def test_verified_maintainer(self) -> None:
        maintainer = Maintainer(name="Bitnami", type=MaintainerType.COMPANY, verified=True)
        assert maintainer.verified is True
        assert maintainer.type == MaintainerType.COMPANY


class TestMetrics:
    """Tests for the Metrics model."""

    def test_default_values(self) -> None:
        metrics = Metrics()
        assert metrics.downloads == 0
        assert metrics.stars == 0
        assert metrics.usage_amount == 0

    def test_with_values(self) -> None:
        metrics = Metrics(downloads=1_000_000, stars=5000, usage_amount=2000)
        assert metrics.downloads == 1_000_000
        assert metrics.stars == 5000
        assert metrics.usage_amount == 2000

    def test_negative_values_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Metrics(downloads=-1)


class TestVulnerabilities:
    """Tests for the Vulnerabilities model."""

    def test_default_values(self) -> None:
        vulns = Vulnerabilities()
        assert vulns.critical == 0
        assert vulns.high == 0
        assert vulns.medium == 0
        assert vulns.low == 0

    def test_with_vulnerabilities(self) -> None:
        vulns = Vulnerabilities(critical=1, high=3, medium=10, low=25)
        assert vulns.critical == 1
        assert vulns.high == 3


class TestSecurity:
    """Tests for the Security model."""

    def test_default_is_unknown(self) -> None:
        security = Security()
        assert security.status == SecurityStatus.UNKNOWN
        assert security.trivy_scan_date is None

    def test_is_safe_with_no_vulnerabilities(self) -> None:
        security = Security(status=SecurityStatus.OK, vulnerabilities=Vulnerabilities())
        assert security.is_safe is True

    def test_is_not_safe_with_critical_vuln(self) -> None:
        security = Security(
            status=SecurityStatus.VULNERABLE,
            vulnerabilities=Vulnerabilities(critical=1),
        )
        assert security.is_safe is False

    def test_is_not_safe_with_high_vuln(self) -> None:
        security = Security(
            status=SecurityStatus.OK,
            vulnerabilities=Vulnerabilities(high=2),
        )
        assert security.is_safe is False

    def test_safe_with_only_medium_low(self) -> None:
        security = Security(
            status=SecurityStatus.OK,
            vulnerabilities=Vulnerabilities(medium=5, low=10),
        )
        assert security.is_safe is True


class TestMaintenance:
    """Tests for the Maintenance model."""

    def test_default_values(self) -> None:
        maintenance = Maintenance()
        assert maintenance.created_at is None
        assert maintenance.last_updated is None
        assert maintenance.is_deprecated is False

    def test_with_dates(self) -> None:
        now = datetime.now(UTC)
        maintenance = Maintenance(
            created_at=now - timedelta(days=365),
            last_updated=now - timedelta(days=7),
            update_frequency_days=30,
        )
        assert maintenance.update_frequency_days == 30


class TestScoreBreakdown:
    """Tests for the ScoreBreakdown model."""

    def test_default_values(self) -> None:
        breakdown = ScoreBreakdown()
        assert breakdown.popularity == 0.0
        assert breakdown.security == 0.0
        assert breakdown.maintenance == 0.0
        assert breakdown.trust == 0.0

    def test_with_scores(self) -> None:
        breakdown = ScoreBreakdown(popularity=85.0, security=90.0, maintenance=75.0, trust=100.0)
        assert breakdown.popularity == 85.0
        assert breakdown.trust == 100.0

    def test_score_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScoreBreakdown(popularity=101.0)

        with pytest.raises(ValidationError):
            ScoreBreakdown(security=-1.0)


class TestTool:
    """Tests for the Tool model."""

    def test_minimal_creation(self) -> None:
        tool = Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
        )
        assert tool.id == "docker_hub:library/postgres"
        assert tool.name == "postgres"
        assert tool.source == SourceType.DOCKER_HUB
        assert tool.identity.canonical_name == "postgres"

    def test_full_creation(self) -> None:
        now = datetime.now(UTC)
        tool = Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="The PostgreSQL object-relational database system",
            identity=Identity(
                canonical_name="postgres",
                aliases=["postgresql"],
                variants=["github:postgres/postgres"],
            ),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000_000_000, stars=10000),
            security=Security(status=SecurityStatus.OK),
            maintenance=Maintenance(
                created_at=now - timedelta(days=3650),
                last_updated=now - timedelta(days=7),
            ),
            tags=["database", "sql", "relational"],
            primary_category="databases",
            primary_subcategory="relational",
            lifecycle=Lifecycle.STABLE,
            quality_score=94.5,
            score_breakdown=ScoreBreakdown(
                popularity=92.0, security=100.0, maintenance=90.0, trust=100.0
            ),
        )
        assert tool.description == "The PostgreSQL object-relational database system"
        assert tool.maintainer.verified is True
        assert tool.metrics.downloads == 1_000_000_000
        assert tool.quality_score == 94.5
        assert tool.lifecycle == Lifecycle.STABLE

    def test_canonical_name_defaults_to_name(self) -> None:
        tool = Tool(
            id="docker_hub:library/nginx",
            name="NGINX",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/nginx",
        )
        assert tool.identity.canonical_name == "nginx"

    def test_serialization_round_trip(self) -> None:
        tool = Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            metrics=Metrics(downloads=500_000_000, stars=8000),
        )

        # Serialize to JSON
        json_str = tool.model_dump_json()
        assert "redis" in json_str
        assert "500000000" in json_str

        # Deserialize back
        restored = Tool.model_validate_json(json_str)
        assert restored.id == tool.id
        assert restored.metrics.downloads == tool.metrics.downloads

    def test_serialization_to_dict(self) -> None:
        tool = Tool(
            id="github:prometheus/prometheus",
            name="prometheus",
            source=SourceType.GITHUB,
            source_url="https://github.com/prometheus/prometheus",
        )
        data = tool.model_dump()
        assert data["id"] == "github:prometheus/prometheus"
        assert data["source"] == "github"


class TestScoreAnalysis:
    """Tests for the ScoreAnalysis model."""

    def test_default_values(self) -> None:
        analysis = ScoreAnalysis()
        assert analysis.dominant_dimension == DominantDimension.BALANCED
        assert analysis.dominance_ratio == 1.0

    def test_with_dominant_dimension(self) -> None:
        analysis = ScoreAnalysis(
            dominant_dimension=DominantDimension.SECURITY,
            dominance_ratio=2.5,
        )
        assert analysis.dominant_dimension == DominantDimension.SECURITY
        assert analysis.dominance_ratio == 2.5


class TestFilterStatus:
    """Tests for the FilterStatus model."""

    def test_default_is_visible(self) -> None:
        status = FilterStatus()
        assert status.state == FilterState.VISIBLE
        assert status.reasons == []

    def test_excluded_with_reasons(self) -> None:
        status = FilterStatus(
            state=FilterState.EXCLUDED,
            reasons=[FilterReasons.CRITICAL_VULNERABILITY, FilterReasons.STALE],
        )
        assert status.state == FilterState.EXCLUDED
        assert FilterReasons.CRITICAL_VULNERABILITY in status.reasons

    def test_hidden_with_reason(self) -> None:
        status = FilterStatus(
            state=FilterState.HIDDEN,
            reasons=[FilterReasons.EXPERIMENTAL],
        )
        assert status.state == FilterState.HIDDEN


class TestScoreWeights:
    """Tests for the ScoreWeights model."""

    def test_default_weights_sum_to_one(self) -> None:
        weights = ScoreWeights()
        total = weights.popularity + weights.security + weights.maintenance + weights.trust
        assert abs(total - 1.0) < 0.001

    def test_custom_weights_valid(self) -> None:
        weights = ScoreWeights(
            popularity=0.4,
            security=0.3,
            maintenance=0.2,
            trust=0.1,
        )
        assert weights.popularity == 0.4
        assert weights.trust == 0.1

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValidationError):
            ScoreWeights(popularity=0.5, security=0.5, maintenance=0.5, trust=0.5)


class TestFilterThresholds:
    """Tests for the FilterThresholds model."""

    def test_default_values(self) -> None:
        thresholds = FilterThresholds()
        assert thresholds.min_downloads == 1000
        assert thresholds.min_stars == 100
        assert thresholds.max_days_since_update == 365
        assert thresholds.min_score == 30.0

    def test_custom_thresholds(self) -> None:
        thresholds = FilterThresholds(
            min_downloads=5000,
            min_stars=500,
            max_days_since_update=180,
            min_score=50.0,
        )
        assert thresholds.min_downloads == 5000
        assert thresholds.min_score == 50.0


class TestDistributionStats:
    """Tests for the DistributionStats model."""

    def test_creation(self) -> None:
        stats = DistributionStats(
            min=0,
            max=1000000,
            median=5000.0,
            p25=1000.0,
            p75=20000.0,
            log_mean=8.5,
            log_std=2.1,
        )
        assert stats.min == 0
        assert stats.max == 1000000
        assert stats.median == 5000.0


class TestCategoryStats:
    """Tests for the CategoryStats model."""

    def test_creation(self) -> None:
        dist_stats = DistributionStats(
            min=0,
            max=1000000,
            median=5000.0,
            p25=1000.0,
            p75=20000.0,
            log_mean=8.5,
            log_std=2.1,
        )
        category = CategoryStats(
            sample_size=50,
            downloads=dist_stats,
            stars=dist_stats,
        )
        assert category.sample_size == 50
        assert category.downloads.median == 5000.0


class TestGlobalStats:
    """Tests for the GlobalStats model."""

    def test_creation(self) -> None:
        dist_stats = DistributionStats(
            min=0,
            max=1000000,
            median=5000.0,
            p25=1000.0,
            p75=20000.0,
            log_mean=8.5,
            log_std=2.1,
        )
        global_stats = GlobalStats(
            total_tools=1000,
            downloads=dist_stats,
            stars=dist_stats,
        )
        assert global_stats.total_tools == 1000
        assert global_stats.computed_at is not None


class TestEvalContext:
    """Tests for the EvalContext model."""

    def test_creation(self) -> None:
        dist_stats = DistributionStats(
            min=0,
            max=1000000,
            median=5000.0,
            p25=1000.0,
            p75=20000.0,
            log_mean=8.5,
            log_std=2.1,
        )
        global_stats = GlobalStats(
            total_tools=1000,
            downloads=dist_stats,
            stars=dist_stats,
        )
        context = EvalContext(global_stats=global_stats)
        assert context.global_stats.total_tools == 1000
        assert context.weights.security == 0.35
        assert context.thresholds.min_downloads == 1000


class TestClassification:
    """Tests for the Classification model."""

    def test_basic_creation(self) -> None:
        classification = Classification(
            primary_category="databases",
            primary_subcategory="relational",
        )
        assert classification.primary_category == "databases"
        assert classification.secondary_categories == []

    def test_with_secondary_categories(self) -> None:
        classification = Classification(
            primary_category="databases",
            primary_subcategory="relational",
            secondary_categories=["storage/data", "infrastructure/backend"],
        )
        assert len(classification.secondary_categories) == 2


class TestClassificationOverride:
    """Tests for the ClassificationOverride model."""

    def test_creation(self) -> None:
        override = ClassificationOverride(
            primary_category="databases",
            primary_subcategory="relational",
            reason="Correcting misclassification from document store to relational",
        )
        assert override.reason is not None


class TestClassificationCacheEntry:
    """Tests for the ClassificationCacheEntry model."""

    def test_creation(self) -> None:
        classification = Classification(
            primary_category="monitoring",
            primary_subcategory="metrics",
        )
        entry = ClassificationCacheEntry(
            classification=classification,
            source="llm",
        )
        assert entry.source == "llm"
        assert entry.classified_at is not None


class TestRawScrapeFile:
    """Tests for the RawScrapeFile model."""

    def test_creation(self) -> None:
        tool = Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
        )
        scrape_file = RawScrapeFile(
            source=SourceType.DOCKER_HUB,
            tools=[tool],
        )
        assert len(scrape_file.tools) == 1
        assert scrape_file.version == "1.0"


class TestToolScore:
    """Tests for the ToolScore model."""

    def test_creation(self) -> None:
        score = ToolScore(
            quality_score=85.0,
            breakdown=ScoreBreakdown(
                popularity=80.0,
                security=95.0,
                maintenance=75.0,
                trust=90.0,
            ),
        )
        assert score.quality_score == 85.0
        assert score.breakdown.security == 95.0


class TestScoresFile:
    """Tests for the ScoresFile model."""

    def test_creation(self) -> None:
        score = ToolScore(
            quality_score=85.0,
            breakdown=ScoreBreakdown(),
        )
        scores_file = ScoresFile(
            score_version="abc123",
            weights=ScoreWeights(),
            scores={"docker_hub:library/redis": score},
        )
        assert "docker_hub:library/redis" in scores_file.scores
        assert scores_file.score_version == "abc123"
