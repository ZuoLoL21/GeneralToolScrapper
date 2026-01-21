"""Popularity evaluator using log-transform and Z-score normalization."""

import math

from scipy.stats import norm

from src.models.model_stats import CategoryStats, EvalContext
from src.models.model_tool import SourceType, Tool

# Source-specific weights from SCORING.md
SOURCE_WEIGHTS = {
    SourceType.DOCKER_HUB: {"downloads": 0.7, "stars": 0.3},
    SourceType.GITHUB: {"downloads": 0.4, "stars": 0.6},
    SourceType.HELM: {"downloads": 0.6, "stars": 0.4},
}

# Minimum sample size for category stats (fallback to global if below this)
MIN_CATEGORY_SAMPLE_SIZE = 10


class PopularityEvaluator:
    """Evaluates tools based on downloads and stars using Z-score normalization.

    Algorithm from SCORING.md:
    1. Get category stats (or global if sample_size < 10)
    2. Log-transform: log(value + 1)
    3. Compute Z-scores: (log_value - log_mean) / log_std
    4. Source-specific weighting of downloads/stars Z-scores
    5. Convert to 0-100 via CDF: norm.cdf(combined_z) * 100
    """

    def evaluate(self, tool: Tool, context: EvalContext) -> float:
        """Calculate popularity score based on downloads and stars.

        Args:
            tool: The tool to evaluate
            context: Evaluation context with global and category stats

        Returns:
            Popularity score between 0-100
        """
        # Step 1: Get appropriate stats (category or global fallback)
        stats = self._get_stats(tool, context)

        # Step 2: Log-transform
        log_downloads = math.log(tool.metrics.downloads + 1)
        log_stars = math.log(tool.metrics.stars + 1)

        # Step 3: Compute Z-scores
        # Handle edge case where std = 0 (all tools have same values)
        if stats.downloads.log_std == 0:
            downloads_z = 0.0
        else:
            downloads_z = (log_downloads - stats.downloads.log_mean) / stats.downloads.log_std

        if stats.stars.log_std == 0:
            stars_z = 0.0
        else:
            stars_z = (log_stars - stats.stars.log_mean) / stats.stars.log_std

        # Step 4: Source-specific weighting
        weights = SOURCE_WEIGHTS.get(
            tool.source, SOURCE_WEIGHTS[SourceType.DOCKER_HUB]  # Default to Docker Hub weights
        )
        combined_z = weights["downloads"] * downloads_z + weights["stars"] * stars_z

        # Step 5: Convert to 0-100 via CDF
        score = norm.cdf(combined_z) * 100

        return score

    def _get_stats(self, tool: Tool, context: EvalContext) -> CategoryStats:
        """Get category stats, falling back to global if sample size < 10.

        Args:
            tool: The tool being evaluated
            context: Evaluation context with stats

        Returns:
            CategoryStats to use for normalization
        """
        # Try to get category stats
        if tool.primary_category and tool.primary_subcategory:
            category_key = f"{tool.primary_category}/{tool.primary_subcategory}"
            category_stats = context.category_stats.get(category_key)

            # Use category stats if sample size is sufficient
            if category_stats and category_stats.sample_size >= MIN_CATEGORY_SAMPLE_SIZE:
                return category_stats

        # Fallback to global stats
        return CategoryStats(
            sample_size=context.global_stats.total_tools,
            downloads=context.global_stats.downloads,
            stars=context.global_stats.stars,
        )


def main() -> None:
    """Demonstrate popularity scoring with sample tools."""
    from datetime import datetime, timezone

    from src.evaluators.stats_generator import generate_all_stats
    from src.models.model_eval import ScoreWeights
    from src.models.model_stats import EvalContext
    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Metrics,
        SourceType,
    )

    print("Popularity Evaluator Demo")
    print("=" * 50)

    # Create sample tools with varying popularity
    sample_tools = [
        # Databases/Relational category
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
            id="docker_hub:library/mariadb",
            name="mariadb",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/mariadb",
            description="Official MariaDB image",
            identity=Identity(canonical_name="mariadb"),
            maintainer=Maintainer(name="Docker Official Images", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=500_000_000, stars=8000),
            primary_category="databases",
            primary_subcategory="relational",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="docker_hub:user/small-db",
            name="small-db",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/small-db",
            description="Small database tool",
            identity=Identity(canonical_name="small-db"),
            maintainer=Maintainer(name="User", type=MaintainerType.USER, verified=False),
            metrics=Metrics(downloads=10_000, stars=50),
            primary_category="databases",
            primary_subcategory="relational",
            scraped_at=datetime.now(timezone.utc),
        ),
        # Databases/Cache category
        Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Official Redis image",
            identity=Identity(canonical_name="redis"),
            maintainer=Maintainer(name="Docker Official Images", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=600_000_000, stars=10000),
            primary_category="databases",
            primary_subcategory="cache",
            scraped_at=datetime.now(timezone.utc),
        ),
        Tool(
            id="docker_hub:library/memcached",
            name="memcached",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/memcached",
            description="Official Memcached image",
            identity=Identity(canonical_name="memcached"),
            maintainer=Maintainer(name="Docker Official Images", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=200_000_000, stars=4000),
            primary_category="databases",
            primary_subcategory="cache",
            scraped_at=datetime.now(timezone.utc),
        ),
        # Monitoring category (small sample)
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
        # Add more tools to reach 10+ for databases/relational
        *[
            Tool(
                id=f"docker_hub:user/db{i}",
                name=f"db{i}",
                source=SourceType.DOCKER_HUB,
                source_url=f"https://hub.docker.com/r/user/db{i}",
                identity=Identity(canonical_name=f"db{i}"),
                maintainer=Maintainer(name="User", type=MaintainerType.USER),
                metrics=Metrics(downloads=50_000 + i * 10000, stars=100 + i * 10),
                primary_category="databases",
                primary_subcategory="relational",
                scraped_at=datetime.now(timezone.utc),
            )
            for i in range(10)
        ],
    ]

    # Generate statistics
    global_stats, category_stats = generate_all_stats(sample_tools)

    # Create context
    context = EvalContext(
        global_stats=global_stats,
        category_stats=category_stats,
        weights=ScoreWeights(),
    )

    evaluator = PopularityEvaluator()

    # Test with various tools
    test_tools = [
        sample_tools[0],  # postgres (mega-popular)
        sample_tools[3],  # small-db (low popularity)
        sample_tools[4],  # redis (different category)
        sample_tools[6],  # grafana (small category, should use global stats)
    ]

    print("\n## Category Statistics")
    for category_key, stats in sorted(category_stats.items()):
        print(f"\n{category_key}:")
        print(f"  Sample size: {stats.sample_size}")
        print(f"  Downloads log_mean: {stats.downloads.log_mean:.2f}, log_std: {stats.downloads.log_std:.2f}")
        print(f"  Stars log_mean: {stats.stars.log_mean:.2f}, log_std: {stats.stars.log_std:.2f}")

    print("\n## Test Cases")
    for tool in test_tools:
        score = evaluator.evaluate(tool, context)
        category_key = f"{tool.primary_category}/{tool.primary_subcategory}"
        cat_stats = category_stats.get(category_key)

        print(f"\n{tool.name}:")
        print(f"  Category: {category_key}")
        print(f"  Downloads: {tool.metrics.downloads:,}, Stars: {tool.metrics.stars:,}")
        if cat_stats and cat_stats.sample_size >= MIN_CATEGORY_SAMPLE_SIZE:
            print(f"  Using category stats (sample_size={cat_stats.sample_size})")
        else:
            print(f"  Using global stats (category too small)")
        print(f"  Score: {score:.1f}/100")

    print("\n## Scoring Algorithm")
    print("1. Get category stats (or global if sample_size < 10)")
    print("2. Log-transform: log(value + 1)")
    print("3. Compute Z-scores: (log_value - log_mean) / log_std")
    print("4. Source-specific weighting:")
    for source, weights in SOURCE_WEIGHTS.items():
        print(f"   {source.value}: downloads={weights['downloads']}, stars={weights['stars']}")
    print("5. Convert to 0-100 via CDF: norm.cdf(combined_z) * 100")


if __name__ == "__main__":
    main()
