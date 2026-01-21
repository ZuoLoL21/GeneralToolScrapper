"""Pytest configuration and fixtures."""

from datetime import UTC, datetime, timedelta

import pytest

from src.models.model_eval import ScoreWeights
from src.models.model_stats import (
    CategoryStats,
    DistributionStats,
    EvalContext,
    GlobalStats,
)
from src.models.model_tool import (
    Identity,
    Maintainer,
    MaintainerType,
    Maintenance,
    Metrics,
    Security,
    SecurityStatus,
    SourceType,
    Tool,
)


@pytest.fixture
def sample_tool() -> Tool:
    """Create a sample tool for testing."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:library/postgres",
        name="postgres",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/postgres",
        description="The PostgreSQL object-relational database system",
        identity=Identity(
            canonical_name="postgres",
            aliases=["postgresql", "pg"],
            variants=["github:postgres/postgres"],
        ),
        maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
        metrics=Metrics(downloads=1_000_000_000, stars=10000, usage_amount=5000),
        security=Security(status=SecurityStatus.OK),
        maintenance=Maintenance(
            created_at=now - timedelta(days=3650),
            last_updated=now - timedelta(days=7),
            update_frequency_days=14,
        ),
        tags=["database", "sql", "relational", "postgres"],
        primary_category="databases",
        primary_subcategory="relational",
    )


@pytest.fixture
def sample_stats() -> tuple[GlobalStats, dict[str, CategoryStats]]:
    """Create sample statistics for testing evaluators."""
    # Global statistics
    downloads_dist = DistributionStats(
        min=100,
        max=1_000_000_000,
        median=50_000,
        p25=10_000,
        p75=200_000,
        log_mean=10.5,
        log_std=2.0,
    )
    stars_dist = DistributionStats(
        min=10,
        max=100_000,
        median=500,
        p25=100,
        p75=2_000,
        log_mean=6.2,
        log_std=1.5,
    )
    global_stats = GlobalStats(
        total_tools=1000,
        downloads=downloads_dist,
        stars=stars_dist,
    )

    # Category statistics
    category_stats = {
        "databases/relational": CategoryStats(
            sample_size=50,
            downloads=DistributionStats(
                min=1_000,
                max=1_000_000_000,
                median=100_000,
                p25=20_000,
                p75=500_000,
                log_mean=11.5,
                log_std=1.8,
            ),
            stars=DistributionStats(
                min=50,
                max=50_000,
                median=1_000,
                p25=300,
                p75=5_000,
                log_mean=7.0,
                log_std=1.3,
            ),
        ),
        "databases/cache": CategoryStats(
            sample_size=25,
            downloads=DistributionStats(
                min=5_000,
                max=600_000_000,
                median=80_000,
                p25=15_000,
                p75=400_000,
                log_mean=11.0,
                log_std=1.6,
            ),
            stars=DistributionStats(
                min=100,
                max=20_000,
                median=800,
                p25=250,
                p75=3_000,
                log_mean=6.5,
                log_std=1.2,
            ),
        ),
        "monitoring/visualization": CategoryStats(
            sample_size=5,  # Small category - should trigger fallback
            downloads=DistributionStats(
                min=10_000,
                max=300_000_000,
                median=50_000,
                p25=20_000,
                p75=100_000,
                log_mean=10.8,
                log_std=1.5,
            ),
            stars=DistributionStats(
                min=200,
                max=10_000,
                median=1_000,
                p25=400,
                p75=3_000,
                log_mean=6.8,
                log_std=1.1,
            ),
        ),
    }

    return global_stats, category_stats


@pytest.fixture
def sample_context(sample_stats) -> EvalContext:
    """Create sample evaluation context for testing evaluators."""
    global_stats, category_stats = sample_stats
    return EvalContext(
        global_stats=global_stats,
        category_stats=category_stats,
        weights=ScoreWeights(),
        score_version="1.0",
    )
