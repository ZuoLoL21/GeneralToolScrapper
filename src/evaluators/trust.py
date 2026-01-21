"""Trust evaluator for publisher reputation scoring."""

from src.models.model_stats import EvalContext
from src.models.model_tool import MaintainerType, Tool

# Base scores by maintainer type
BASE_OFFICIAL = 100
BASE_VERIFIED_COMPANY = 90
BASE_COMPANY = 70
BASE_USER = 60

# Community bonus limits
MAX_COMMUNITY_BONUS = 25


class TrustEvaluator:
    """Evaluates tools based on publisher reputation and community signals.

    Base scores by publisher type:
    - Official: 100 (Docker library/*, org-owned GitHub repos)
    - Verified company: 90 (Verified Publisher badge)
    - Company/Org: 70 (Known company without verification)
    - User: 60 (Individual contributor)

    Community reputation bonuses (for non-official, max +25):
    - Consistent updates: +5 to +15 (future)
    - High engagement ratio (stars/downloads): +5
    - Multiple maintainers: +5 (future, return 0 for now)
    """

    def evaluate(self, tool: Tool, context: EvalContext) -> float:
        """Calculate trust score based on publisher type and community signals.

        Args:
            tool: The tool to evaluate
            context: Evaluation context (unused for trust scoring currently)

        Returns:
            Trust score between 0-100
        """
        # Determine base score
        base_score = self._get_base_score(tool)

        # For official, return maximum (no community bonus needed)
        if tool.maintainer.type == MaintainerType.OFFICIAL:
            return base_score

        # Calculate community bonus for non-official tools
        community_bonus = self._calculate_community_bonus(tool)

        # Total score capped at 100
        return min(100.0, base_score + community_bonus)

    def _get_base_score(self, tool: Tool) -> float:
        """Get base score based on maintainer type and verification."""
        if tool.maintainer.type == MaintainerType.OFFICIAL:
            return BASE_OFFICIAL

        if tool.maintainer.type == MaintainerType.COMPANY:
            if tool.maintainer.verified:
                return BASE_VERIFIED_COMPANY
            return BASE_COMPANY

        # USER type
        return BASE_USER

    def _calculate_community_bonus(self, tool: Tool) -> float:
        """Calculate community reputation bonus (max +25).

        Currently implements:
        - High engagement ratio (stars/downloads): +5

        Future implementations:
        - Consistent updates: +5 to +15
        - Multiple maintainers: +5
        """
        bonus = 0.0

        # High engagement ratio bonus
        # If stars/downloads ratio is high, it indicates strong community appreciation
        if tool.metrics.downloads > 0:
            engagement_ratio = tool.metrics.stars / tool.metrics.downloads

            # Threshold: if ratio > 0.01 (1 star per 100 downloads), give bonus
            if engagement_ratio > 0.01:
                bonus += 5.0

        # Cap at maximum
        return min(bonus, MAX_COMMUNITY_BONUS)


def main() -> None:
    """Demonstrate trust scoring with sample tools."""
    from datetime import datetime, timezone

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
        Metrics,
        SourceType,
    )

    print("Trust Evaluator Demo")
    print("=" * 50)

    # Create mock context
    mock_global_stats = GlobalStats(
        total_tools=1000,
        downloads=DistributionStats(
            min=100,
            max=1_000_000_000,
            median=50_000,
            p25=10_000,
            p75=200_000,
            log_mean=10.5,
            log_std=2.0,
        ),
        stars=DistributionStats(
            min=10,
            max=100_000,
            median=500,
            p25=100,
            p75=2_000,
            log_mean=6.2,
            log_std=1.5,
        ),
    )
    context = EvalContext(global_stats=mock_global_stats, weights=ScoreWeights())

    evaluator = TrustEvaluator()

    # Test cases
    test_cases = [
        (
            "Official (Docker library/*)",
            Tool(
                id="docker_hub:library/postgres",
                name="postgres",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/_/postgres",
                maintainer=Maintainer(name="Docker Official Images", type=MaintainerType.OFFICIAL, verified=True),
                metrics=Metrics(downloads=1_000_000_000, stars=15000),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Verified company",
            Tool(
                id="docker_hub:bitnami/redis",
                name="redis",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/bitnami/redis",
                maintainer=Maintainer(name="Bitnami", type=MaintainerType.COMPANY, verified=True),
                metrics=Metrics(downloads=500_000_000, stars=8000),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Company (not verified)",
            Tool(
                id="docker_hub:company/tool",
                name="tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/company/tool",
                maintainer=Maintainer(name="Some Company", type=MaintainerType.COMPANY, verified=False),
                metrics=Metrics(downloads=100_000, stars=500),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "User with low engagement",
            Tool(
                id="docker_hub:user/tool",
                name="tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/user/tool",
                maintainer=Maintainer(name="Individual", type=MaintainerType.USER, verified=False),
                metrics=Metrics(downloads=10_000, stars=50),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "User with high engagement (bonus)",
            Tool(
                id="docker_hub:user/popular",
                name="popular",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/user/popular",
                maintainer=Maintainer(name="Individual", type=MaintainerType.USER, verified=False),
                metrics=Metrics(downloads=10_000, stars=500),  # 5% engagement ratio
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Company with high engagement (bonus + verified)",
            Tool(
                id="docker_hub:company/excellent",
                name="excellent",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/company/excellent",
                maintainer=Maintainer(name="Great Company", type=MaintainerType.COMPANY, verified=True),
                metrics=Metrics(downloads=50_000, stars=2000),  # 4% engagement ratio
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
    ]

    print("\n## Test Cases")
    for description, tool in test_cases:
        score = evaluator.evaluate(tool, context)

        print(f"\n{description}:")
        print(f"  Type: {tool.maintainer.type.value}, Verified: {tool.maintainer.verified}")
        print(f"  Downloads: {tool.metrics.downloads:,}, Stars: {tool.metrics.stars:,}")
        engagement = tool.metrics.stars / tool.metrics.downloads if tool.metrics.downloads > 0 else 0
        print(f"  Engagement ratio: {engagement:.4f}")
        print(f"  Score: {score:.1f}/100")

    print("\n## Scoring Logic")
    print("Base Scores:")
    print(f"  Official: {BASE_OFFICIAL}")
    print(f"  Verified company: {BASE_VERIFIED_COMPANY}")
    print(f"  Company/Org: {BASE_COMPANY}")
    print(f"  User: {BASE_USER}")
    print("\nCommunity Bonus (non-official, max +25):")
    print("  High engagement ratio (>0.01): +5")
    print("  Consistent updates: +5 to +15 (future)")
    print("  Multiple maintainers: +5 (future)")


if __name__ == "__main__":
    main()
