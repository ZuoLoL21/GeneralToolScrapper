"""Pytest configuration and fixtures."""

from datetime import UTC, datetime, timedelta

import pytest

from src.models import (
    EvalContext,
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
def sample_eval_context() -> EvalContext:
    """Create a sample evaluation context for testing."""
    return EvalContext(
        min_downloads=1000,
        min_stars=100,
        max_days_since_update=365,
        weight_popularity=0.25,
        weight_security=0.35,
        weight_maintenance=0.25,
        weight_trust=0.15,
    )
