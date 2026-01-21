"""Tests for statistics generator."""

import math
from datetime import datetime, timezone

import pytest

from src.evaluators.stats_generator import (
    _compute_distribution_stats,
    compute_category_stats,
    compute_global_stats,
    generate_all_stats,
)
from src.models.model_tool import (
    Identity,
    Maintainer,
    MaintainerType,
    Metrics,
    SourceType,
    Tool,
)


def test_compute_distribution_stats():
    """Test distribution statistics calculation."""
    values = [100, 1000, 10000, 100000, 1000000]

    stats = _compute_distribution_stats(values)

    # Check raw percentiles
    assert stats.min == 100
    assert stats.max == 1000000
    assert stats.median == 10000

    # Check log-transformed values
    log_values = [math.log(v + 1) for v in values]
    expected_log_mean = sum(log_values) / len(log_values)
    assert abs(stats.log_mean - expected_log_mean) < 0.01

    # Std should be positive
    assert stats.log_std > 0


def test_compute_distribution_stats_empty():
    """Test that empty values list raises error."""
    with pytest.raises(ValueError, match="Cannot compute stats from empty values list"):
        _compute_distribution_stats([])


def test_compute_global_stats(sample_tool):
    """Test global statistics computation."""
    # Create sample tools with varying metrics
    tools = [
        Tool(
            id=f"test:{i}/tool",
            name=f"tool{i}",
            source=SourceType.DOCKER_HUB,
            source_url=f"https://example.com/{i}",
            metrics=Metrics(downloads=1000 * (i + 1), stars=100 * (i + 1)),
            scraped_at=datetime.now(timezone.utc),
        )
        for i in range(10)
    ]

    global_stats = compute_global_stats(tools)

    # Check total tools
    assert global_stats.total_tools == 10

    # Check downloads stats
    assert global_stats.downloads.min == 1000
    assert global_stats.downloads.max == 10000

    # Check stars stats
    assert global_stats.stars.min == 100
    assert global_stats.stars.max == 1000


def test_compute_global_stats_empty():
    """Test that empty tools list returns sentinel stats."""
    global_stats = compute_global_stats([])
    assert global_stats.total_tools == 0
    assert global_stats.downloads.log_mean == 0.0
    assert global_stats.downloads.log_std == 1.0
    assert global_stats.stars.log_mean == 0.0
    assert global_stats.stars.log_std == 1.0


def test_compute_category_stats():
    """Test category-level statistics computation."""
    # Create tools in multiple categories
    tools = []
    for i in range(15):
        # First 10 in databases/relational
        if i < 10:
            category = "databases"
            subcategory = "relational"
            downloads = 10000 * (i + 1)
        # Next 5 in databases/cache
        else:
            category = "databases"
            subcategory = "cache"
            downloads = 5000 * (i + 1)

        tools.append(
            Tool(
                id=f"test:{i}/tool",
                name=f"tool{i}",
                source=SourceType.DOCKER_HUB,
                source_url=f"https://example.com/{i}",
                metrics=Metrics(downloads=downloads, stars=100 * (i + 1)),
                primary_category=category,
                primary_subcategory=subcategory,
                scraped_at=datetime.now(timezone.utc),
            )
        )

    category_stats = compute_category_stats(tools)

    # Should have 2 categories
    assert len(category_stats) == 2
    assert "databases/relational" in category_stats
    assert "databases/cache" in category_stats

    # Check sample sizes
    assert category_stats["databases/relational"].sample_size == 10
    assert category_stats["databases/cache"].sample_size == 5

    # Check that stats were computed
    assert category_stats["databases/relational"].downloads.min == 10000
    assert category_stats["databases/relational"].downloads.max == 100000


def test_compute_category_stats_skip_uncategorized():
    """Test that tools without categorization are skipped."""
    tools = [
        Tool(
            id="test:1/categorized",
            name="categorized",
            source=SourceType.DOCKER_HUB,
            source_url="https://example.com/1",
            metrics=Metrics(downloads=10000, stars=100),
            primary_category="databases",
            primary_subcategory="relational",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="test:2/uncategorized",
            name="uncategorized",
            source=SourceType.DOCKER_HUB,
            source_url="https://example.com/2",
            metrics=Metrics(downloads=20000, stars=200),
            primary_category=None,  # No category
            primary_subcategory=None,
            scraped_at=datetime.now(timezone.utc),
        ),
    ]

    category_stats = compute_category_stats(tools)

    # Should only have 1 category (uncategorized tool skipped)
    # But wait, we only have 1 tool in the category, so no categories meet the minimum
    # Actually, we compute stats for all categories regardless of size
    assert len(category_stats) == 1
    assert "databases/relational" in category_stats
    assert category_stats["databases/relational"].sample_size == 1


def test_compute_category_stats_empty():
    """Test that empty tools list returns empty dict."""
    category_stats = compute_category_stats([])
    assert category_stats == {}


def test_generate_all_stats():
    """Test generating both global and category stats."""
    tools = []
    for i in range(20):
        category = "databases" if i < 15 else "monitoring"
        subcategory = "relational" if i < 10 else ("cache" if i < 15 else "metrics")

        tools.append(
            Tool(
                id=f"test:{i}/tool",
                name=f"tool{i}",
                source=SourceType.DOCKER_HUB,
                source_url=f"https://example.com/{i}",
                metrics=Metrics(downloads=1000 * (i + 1), stars=100 * (i + 1)),
                primary_category=category,
                primary_subcategory=subcategory,
                scraped_at=datetime.now(timezone.utc),
            )
        )

    global_stats, category_stats = generate_all_stats(tools)

    # Check global stats
    assert global_stats.total_tools == 20

    # Check category stats
    assert len(category_stats) == 3
    assert category_stats["databases/relational"].sample_size == 10
    assert category_stats["databases/cache"].sample_size == 5
    assert category_stats["monitoring/metrics"].sample_size == 5


def test_small_category_handling():
    """Test that small categories still compute stats."""
    tools = [
        Tool(
            id=f"test:{i}/tool",
            name=f"tool{i}",
            source=SourceType.DOCKER_HUB,
            source_url=f"https://example.com/{i}",
            metrics=Metrics(downloads=1000 * (i + 1), stars=100),
            primary_category="small",
            primary_subcategory="category",
            scraped_at=datetime.now(timezone.utc),
        )
        for i in range(3)  # Only 3 tools
    ]

    category_stats = compute_category_stats(tools)

    # Stats should still be computed even for small categories
    assert "small/category" in category_stats
    assert category_stats["small/category"].sample_size == 3

    # Stats should be valid
    assert category_stats["small/category"].downloads.min == 1000
    assert category_stats["small/category"].downloads.max == 3000
