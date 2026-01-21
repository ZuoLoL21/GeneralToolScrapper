"""Statistics generator for computing global and category-level statistics.

This module provides functions to compute distribution statistics needed for
popularity score normalization. Statistics are computed once per evaluation run
and passed to evaluators via EvalContext.
"""

import math
from collections import defaultdict

from src.models.model_stats import CategoryStats, DistributionStats, GlobalStats
from src.models.model_tool import Tool


def _compute_distribution_stats(values: list[int]) -> DistributionStats:
    """Compute distribution statistics for a list of values.

    Args:
        values: List of raw metric values (downloads or stars)

    Returns:
        DistributionStats with percentiles and log-transformed mean/std

    Raises:
        ValueError: If values list is empty
    """
    if not values:
        raise ValueError("Cannot compute stats from empty values list")

    # Sort for percentile calculations
    sorted_values = sorted(values)
    n = len(sorted_values)

    # Raw percentiles
    min_val = sorted_values[0]
    max_val = sorted_values[-1]
    median = sorted_values[n // 2] if n % 2 == 1 else (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    p25 = sorted_values[n // 4]
    p75 = sorted_values[(3 * n) // 4]

    # Log-transform: log(value + 1) to handle zeros
    log_values = [math.log(v + 1) for v in values]

    # Compute mean and std of log-transformed values
    log_mean = sum(log_values) / len(log_values)
    variance = sum((x - log_mean) ** 2 for x in log_values) / len(log_values)
    log_std = math.sqrt(variance)

    return DistributionStats(
        min=min_val,
        max=max_val,
        median=median,
        p25=p25,
        p75=p75,
        log_mean=log_mean,
        log_std=log_std,
    )


def compute_global_stats(tools: list[Tool]) -> GlobalStats:
    """Compute global statistics across all tools.

    Args:
        tools: List of all tools in the catalog

    Returns:
        GlobalStats with download and star distributions

    Raises:
        ValueError: If tools list is empty
    """
    if not tools:
        raise ValueError("Cannot compute global stats from empty tools list")

    # Extract all downloads and stars
    downloads = [tool.metrics.downloads for tool in tools]
    stars = [tool.metrics.stars for tool in tools]

    # Compute distribution stats
    downloads_stats = _compute_distribution_stats(downloads)
    stars_stats = _compute_distribution_stats(stars)

    return GlobalStats(
        total_tools=len(tools),
        downloads=downloads_stats,
        stars=stars_stats,
    )


def compute_category_stats(tools: list[Tool]) -> dict[str, CategoryStats]:
    """Compute category-level statistics for each category/subcategory.

    Categories with fewer than 10 tools are still computed but should be
    flagged for fallback to global stats by evaluators.

    Args:
        tools: List of all tools in the catalog

    Returns:
        Dictionary mapping 'category/subcategory' to CategoryStats
    """
    if not tools:
        return {}

    # Group tools by category/subcategory
    category_groups: dict[str, list[Tool]] = defaultdict(list)

    for tool in tools:
        # Skip tools without categorization
        if not tool.primary_category or not tool.primary_subcategory:
            continue

        category_key = f"{tool.primary_category}/{tool.primary_subcategory}"
        category_groups[category_key].append(tool)

    # Compute stats for each category
    category_stats = {}

    for category_key, category_tools in category_groups.items():
        # Extract downloads and stars
        downloads = [tool.metrics.downloads for tool in category_tools]
        stars = [tool.metrics.stars for tool in category_tools]

        # Compute distribution stats (even for small categories)
        downloads_stats = _compute_distribution_stats(downloads)
        stars_stats = _compute_distribution_stats(stars)

        category_stats[category_key] = CategoryStats(
            sample_size=len(category_tools),
            downloads=downloads_stats,
            stars=stars_stats,
        )

    return category_stats


def generate_all_stats(tools: list[Tool]) -> tuple[GlobalStats, dict[str, CategoryStats]]:
    """Generate both global and category statistics.

    Convenience function to compute all statistics in one call.

    Args:
        tools: List of all tools in the catalog

    Returns:
        Tuple of (GlobalStats, category_stats_dict)

    Raises:
        ValueError: If tools list is empty
    """
    global_stats = compute_global_stats(tools)
    category_stats = compute_category_stats(tools)
    return global_stats, category_stats


def main() -> None:
    """Demonstrate statistics generation with sample data."""
    from datetime import datetime, timezone

    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Metrics,
        SourceType,
    )

    print("Statistics Generator Demo")
    print("=" * 50)

    # Create sample tools
    sample_tools = [
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="Official PostgreSQL image",
            identity=Identity(canonical_name="postgres"),
            maintainer=Maintainer(name="Docker Official Images", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000_000_000, stars=15000),
            primary_category="databases",
            primary_subcategory="relational",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="docker_hub:library/mysql",
            name="mysql",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/mysql",
            description="Official MySQL image",
            identity=Identity(canonical_name="mysql"),
            maintainer=Maintainer(name="Docker Official Images", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=800_000_000, stars=12000),
            primary_category="databases",
            primary_subcategory="relational",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="docker_hub:bitnami/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/bitnami/redis",
            description="Bitnami Redis image",
            identity=Identity(canonical_name="redis"),
            maintainer=Maintainer(name="Bitnami", type=MaintainerType.COMPANY, verified=True),
            metrics=Metrics(downloads=500_000_000, stars=8000),
            primary_category="databases",
            primary_subcategory="cache",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="docker_hub:grafana/grafana",
            name="grafana",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/grafana/grafana",
            description="Grafana monitoring",
            identity=Identity(canonical_name="grafana"),
            maintainer=Maintainer(name="Grafana", type=MaintainerType.COMPANY, verified=True),
            metrics=Metrics(downloads=300_000_000, stars=6000),
            primary_category="monitoring",
            primary_subcategory="visualization",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="docker_hub:prom/prometheus",
            name="prometheus",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/prom/prometheus",
            description="Prometheus monitoring",
            identity=Identity(canonical_name="prometheus"),
            maintainer=Maintainer(name="Prometheus", type=MaintainerType.COMPANY, verified=True),
            metrics=Metrics(downloads=200_000_000, stars=5000),
            primary_category="monitoring",
            primary_subcategory="metrics",
            scraped_at=datetime.now(timezone.utc),
        ),
    ]

    # Generate statistics
    global_stats, category_stats = generate_all_stats(sample_tools)

    # Display results
    print("\n## Global Statistics")
    print(f"Total tools: {global_stats.total_tools}")
    print(f"\nDownloads:")
    print(f"  Min: {global_stats.downloads.min:,}")
    print(f"  Max: {global_stats.downloads.max:,}")
    print(f"  Median: {global_stats.downloads.median:,.0f}")
    print(f"  Log mean: {global_stats.downloads.log_mean:.2f}")
    print(f"  Log std: {global_stats.downloads.log_std:.2f}")
    print(f"\nStars:")
    print(f"  Min: {global_stats.stars.min:,}")
    print(f"  Max: {global_stats.stars.max:,}")
    print(f"  Median: {global_stats.stars.median:,.0f}")
    print(f"  Log mean: {global_stats.stars.log_mean:.2f}")
    print(f"  Log std: {global_stats.stars.log_std:.2f}")

    print("\n## Category Statistics")
    for category_key, stats in sorted(category_stats.items()):
        print(f"\n{category_key}:")
        print(f"  Sample size: {stats.sample_size}")
        print(f"  Downloads log_mean: {stats.downloads.log_mean:.2f}")
        print(f"  Stars log_mean: {stats.stars.log_mean:.2f}")

    # Demonstrate edge case handling
    print("\n## Edge Case: Small Category")
    small_category = next((k for k, v in category_stats.items() if v.sample_size < 10), None)
    if small_category:
        print(f"{small_category} has {category_stats[small_category].sample_size} tools")
        print("Evaluators should fall back to global stats for categories with < 10 tools")
    else:
        print("All categories have >= 10 tools in this sample")


if __name__ == "__main__":
    main()
