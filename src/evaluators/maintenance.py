"""Maintenance evaluator for update recency scoring."""

from datetime import datetime, timezone

from src.models.model_stats import EvalContext
from src.models.model_tool import Lifecycle, Tool

# Default update frequency if not specified (90 days)
DEFAULT_UPDATE_FREQUENCY_DAYS = 90

# Lifecycle penalty
LEGACY_PENALTY = 20


class MaintenanceEvaluator:
    """Evaluates tools based on update recency relative to update frequency.

    Algorithm from SCORING.md:
        expected_gap = tool.update_frequency_days
        actual_gap = days_since_last_update

        if actual_gap <= expected_gap:
            score = 100
        else:
            staleness_ratio = actual_gap / expected_gap
            score = max(0, 100 - (staleness_ratio - 1) * 25)

    Lifecycle penalty:
        - Legacy lifecycle: -20 penalty
    """

    def evaluate(
        self, tool: Tool, context: EvalContext, current_time: datetime | None = None
    ) -> float:
        """Calculate maintenance score based on update recency.

        Args:
            tool: The tool to evaluate
            context: Evaluation context (unused for maintenance scoring)
            current_time: Current time for calculating staleness (defaults to now)

        Returns:
            Maintenance score between 0-100
        """
        # Default to current time if not provided
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Missing last_updated: return 0
        if tool.maintenance.last_updated is None:
            return 0.0

        # Calculate actual gap (days since last update)
        actual_gap = (current_time - tool.maintenance.last_updated).days

        # Get expected gap (use default if not specified)
        expected_gap = tool.maintenance.update_frequency_days
        if expected_gap is None:
            expected_gap = DEFAULT_UPDATE_FREQUENCY_DAYS

        # Calculate base score
        if actual_gap <= expected_gap:
            score = 100.0
        else:
            staleness_ratio = actual_gap / expected_gap
            score = max(0.0, 100 - (staleness_ratio - 1) * 25)

        # Apply lifecycle penalty
        if tool.lifecycle == Lifecycle.LEGACY:
            score = max(0.0, score - LEGACY_PENALTY)

        return score


def main() -> None:
    """Demonstrate maintenance scoring with sample tools."""
    from datetime import timedelta

    from src.models.model_eval import ScoreWeights
    from src.models.model_stats import (
        CategoryStats,
        DistributionStats,
        EvalContext,
        GlobalStats,
    )
    from src.models.model_tool import (
        Identity,
        Lifecycle,
        Maintenance,
        Maintainer,
        MaintainerType,
        Metrics,
        SourceType,
    )

    print("Maintenance Evaluator Demo")
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

    evaluator = MaintenanceEvaluator()

    # Fixed current time for reproducible results
    current_time = datetime.now(timezone.utc)

    # Test cases
    test_cases = [
        (
            "Up-to-date (updated 3 days ago, typical: 14 days)",
            Tool(
                id="test:recent/tool",
                name="recent-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=current_time - timedelta(days=3),
                    update_frequency_days=14,
                ),
                lifecycle=Lifecycle.ACTIVE,
                scraped_at=current_time,
            ),
        ),
        (
            "Exactly on schedule (updated 30 days ago, typical: 30 days)",
            Tool(
                id="test:ontime/tool",
                name="ontime-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=current_time - timedelta(days=30),
                    update_frequency_days=30,
                ),
                lifecycle=Lifecycle.STABLE,
                scraped_at=current_time,
            ),
        ),
        (
            "Slightly stale (updated 60 days ago, typical: 30 days)",
            Tool(
                id="test:stale/tool",
                name="stale-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=current_time - timedelta(days=60),
                    update_frequency_days=30,
                ),
                lifecycle=Lifecycle.ACTIVE,
                scraped_at=current_time,
            ),
        ),
        (
            "Very stale (updated 180 days ago, typical: 30 days)",
            Tool(
                id="test:verystale/tool",
                name="verystale-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=current_time - timedelta(days=180),
                    update_frequency_days=30,
                ),
                lifecycle=Lifecycle.ACTIVE,
                scraped_at=current_time,
            ),
        ),
        (
            "Legacy lifecycle (gets -20 penalty)",
            Tool(
                id="test:legacy/tool",
                name="legacy-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=1000),
                    last_updated=current_time - timedelta(days=30),
                    update_frequency_days=30,
                ),
                lifecycle=Lifecycle.LEGACY,
                scraped_at=current_time,
            ),
        ),
        (
            "Missing last_updated (returns 0)",
            Tool(
                id="test:missing/tool",
                name="missing-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=None,
                    update_frequency_days=30,
                ),
                lifecycle=Lifecycle.ACTIVE,
                scraped_at=current_time,
            ),
        ),
        (
            "Default frequency (no update_frequency_days specified)",
            Tool(
                id="test:default/tool",
                name="default-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=current_time - timedelta(days=45),
                    update_frequency_days=None,
                ),
                lifecycle=Lifecycle.ACTIVE,
                scraped_at=current_time,
            ),
        ),
    ]

    print("\n## Test Cases")
    for description, tool in test_cases:
        score = evaluator.evaluate(tool, context, current_time)

        print(f"\n{description}:")
        if tool.maintenance.last_updated:
            actual_gap = (current_time - tool.maintenance.last_updated).days
            print(f"  Actual gap: {actual_gap} days")
        else:
            print(f"  Actual gap: N/A (no last_updated)")
        expected_gap = tool.maintenance.update_frequency_days or DEFAULT_UPDATE_FREQUENCY_DAYS
        print(f"  Expected gap: {expected_gap} days")
        print(f"  Lifecycle: {tool.lifecycle.value}")
        print(f"  Score: {score:.1f}/100")

    print("\n## Scoring Formula")
    print("if actual_gap <= expected_gap:")
    print("    score = 100")
    print("else:")
    print("    staleness_ratio = actual_gap / expected_gap")
    print("    score = max(0, 100 - (staleness_ratio - 1) * 25)")
    print("\nLifecycle penalty:")
    print(f"  Legacy: -{LEGACY_PENALTY}")
    print(f"\nDefault update frequency: {DEFAULT_UPDATE_FREQUENCY_DAYS} days")


if __name__ == "__main__":
    main()
