"""Pytest configuration and fixtures."""

from datetime import UTC, datetime, timedelta

import pytest

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
