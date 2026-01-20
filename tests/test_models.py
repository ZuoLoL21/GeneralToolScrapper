"""Tests for Pydantic models."""  # noqa: N999

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.Models.model_tool import (
    Identity,
    Lifecycle,
    Maintainer,
    MaintainerType,
    Maintenance,
    Metrics,
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
