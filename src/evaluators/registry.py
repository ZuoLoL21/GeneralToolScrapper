"""Evaluator registry for orchestrating all dimension evaluators."""

from datetime import datetime

from src.evaluators.composite import analyze_score_dominance, calculate_quality_score
from src.evaluators.maintenance import MaintenanceEvaluator
from src.evaluators.popularity import PopularityEvaluator
from src.evaluators.security import SecurityEvaluator, get_blocking_status
from src.evaluators.trust import TrustEvaluator
from src.models.model_stats import EvalContext
from src.models.model_tool import FilterReasons, FilterState, ScoreBreakdown, Tool


class EvaluatorRegistry:
    """Orchestrates all evaluators to score tools.

    This registry manages all dimension evaluators and provides a unified
    interface for scoring tools. It handles:
    - Running all dimension evaluators
    - Calculating composite scores
    - Analyzing score dominance
    - Updating filter status based on blocking conditions
    """

    def __init__(self) -> None:
        """Initialize registry with all evaluators."""
        self.evaluators = {
            "popularity": PopularityEvaluator(),
            "security": SecurityEvaluator(),
            "maintenance": MaintenanceEvaluator(),
            "trust": TrustEvaluator(),
        }

    def evaluate_tool(
        self,
        tool: Tool,
        context: EvalContext,
        current_time: datetime | None = None,
    ) -> Tool:
        """Evaluate tool and update score fields in-place.

        Args:
            tool: The tool to evaluate (modified in-place)
            context: Evaluation context with stats and weights
            current_time: Current time for maintenance scoring (defaults to now)

        Returns:
            The same tool instance with updated scores
        """
        # 1. Evaluate each dimension
        breakdown = ScoreBreakdown(
            popularity=self.evaluators["popularity"].evaluate(tool, context),
            security=self.evaluators["security"].evaluate(tool, context),
            maintenance=self.evaluators["maintenance"].evaluate(tool, context, current_time),
            trust=self.evaluators["trust"].evaluate(tool, context),
        )

        # 2. Calculate composite score
        quality_score = calculate_quality_score(breakdown, context.weights)

        # 3. Analyze score dominance
        analysis = analyze_score_dominance(breakdown)

        # 4. Update tool
        tool.quality_score = quality_score
        tool.score_breakdown = breakdown
        tool.score_analysis = analysis

        # 5. Check blocking status
        if get_blocking_status(tool):
            tool.filter_status.state = FilterState.EXCLUDED
            if FilterReasons.CRITICAL_VULNERABILITY not in tool.filter_status.reasons:
                tool.filter_status.reasons.append(FilterReasons.CRITICAL_VULNERABILITY)

        return tool

    def evaluate_batch(
        self,
        tools: list[Tool],
        context: EvalContext,
        current_time: datetime | None = None,
    ) -> list[Tool]:
        """Evaluate multiple tools.

        Args:
            tools: List of tools to evaluate (modified in-place)
            context: Evaluation context with stats and weights
            current_time: Current time for maintenance scoring (defaults to now)

        Returns:
            The same list of tools with updated scores
        """
        return [self.evaluate_tool(tool, context, current_time) for tool in tools]


def main() -> None:
    """Demonstrate full evaluation pipeline."""
    from datetime import datetime, timedelta, timezone

    from src.evaluators.stats_generator import generate_all_stats
    from src.models.model_eval import ScoreWeights
    from src.models.model_stats import EvalContext
    from src.models.model_tool import (
        Identity,
        Lifecycle,
        Maintenance,
        Maintainer,
        MaintainerType,
        Metrics,
        Security,
        SecurityStatus,
        SourceType,
        Vulnerabilities,
    )

    print("Evaluator Registry Demo")
    print("=" * 50)

    # Create sample tools
    current_time = datetime.now(timezone.utc)

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
            security=Security(status=SecurityStatus.OK, vulnerabilities=Vulnerabilities()),
            maintenance=Maintenance(
                created_at=current_time - timedelta(days=2000),
                last_updated=current_time - timedelta(days=3),
                update_frequency_days=14,
            ),
            primary_category="databases",
            primary_subcategory="relational",
            lifecycle=Lifecycle.STABLE,
            scraped_at=current_time,
        ),
        Tool(
            id="docker_hub:user/popular-but-vulnerable",
            name="popular-but-vulnerable",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/popular-but-vulnerable",
            description="Popular but has critical vulnerability",
            identity=Identity(canonical_name="popular-but-vulnerable"),
            maintainer=Maintainer(name="User", type=MaintainerType.USER, verified=False),
            metrics=Metrics(downloads=50_000_000, stars=5000),
            security=Security(
                status=SecurityStatus.VULNERABLE,
                vulnerabilities=Vulnerabilities(critical=1, high=2),
            ),
            maintenance=Maintenance(
                created_at=current_time - timedelta(days=365),
                last_updated=current_time - timedelta(days=5),
                update_frequency_days=30,
            ),
            primary_category="databases",
            primary_subcategory="relational",
            lifecycle=Lifecycle.ACTIVE,
            scraped_at=current_time,
        ),
        Tool(
            id="docker_hub:user/small-tool",
            name="small-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/small-tool",
            description="Small tool with low popularity",
            identity=Identity(canonical_name="small-tool"),
            maintainer=Maintainer(name="User", type=MaintainerType.USER, verified=False),
            metrics=Metrics(downloads=5_000, stars=25),
            security=Security(status=SecurityStatus.OK, vulnerabilities=Vulnerabilities()),
            maintenance=Maintenance(
                created_at=current_time - timedelta(days=180),
                last_updated=current_time - timedelta(days=10),
                update_frequency_days=30,
            ),
            primary_category="databases",
            primary_subcategory="relational",
            lifecycle=Lifecycle.EXPERIMENTAL,
            scraped_at=current_time,
        ),
        # Add more tools to get enough for stats
        *[
            Tool(
                id=f"docker_hub:user/db{i}",
                name=f"db{i}",
                source=SourceType.DOCKER_HUB,
                source_url=f"https://hub.docker.com/r/user/db{i}",
                identity=Identity(canonical_name=f"db{i}"),
                maintainer=Maintainer(name="User", type=MaintainerType.USER),
                metrics=Metrics(downloads=50_000 + i * 10000, stars=100 + i * 10),
                security=Security(status=SecurityStatus.OK),
                maintenance=Maintenance(
                    created_at=current_time - timedelta(days=365),
                    last_updated=current_time - timedelta(days=15),
                    update_frequency_days=30,
                ),
                primary_category="databases",
                primary_subcategory="relational",
                lifecycle=Lifecycle.ACTIVE,
                scraped_at=current_time,
            )
            for i in range(10)
        ],
    ]

    # Generate statistics
    print("\n## Generating Statistics")
    global_stats, category_stats = generate_all_stats(sample_tools)
    print(f"Total tools: {global_stats.total_tools}")
    print(f"Categories: {len(category_stats)}")

    # Create evaluation context
    context = EvalContext(
        global_stats=global_stats,
        category_stats=category_stats,
        weights=ScoreWeights(),
        score_version="1.0",
    )

    # Initialize registry
    registry = EvaluatorRegistry()

    # Evaluate all tools
    print("\n## Evaluating Tools")
    scored_tools = registry.evaluate_batch(sample_tools, context, current_time)

    # Display results for sample tools
    print("\n## Results")
    for tool in scored_tools[:3]:  # Show first 3 tools
        print(f"\n{tool.name}:")
        print(f"  Quality Score: {tool.quality_score:.1f}/100")
        breakdown = tool.score_breakdown
        print(f"  Breakdown:")
        print(f"    Popularity:  {breakdown.popularity:.1f}")
        print(f"    Security:    {breakdown.security:.1f}")
        print(f"    Maintenance: {breakdown.maintenance:.1f}")
        print(f"    Trust:       {breakdown.trust:.1f}")
        analysis = tool.score_analysis
        print(f"  Analysis:")
        print(f"    Dominant: {analysis.dominant_dimension.value}")
        print(f"    Ratio: {analysis.dominance_ratio:.2f}")
        print(f"  Filter Status: {tool.filter_status.state.value}")
        if tool.filter_status.reasons:
            print(f"  Filter Reasons: {', '.join(tool.filter_status.reasons)}")

    # Show statistics
    print("\n## Score Statistics")
    scores = [t.quality_score for t in scored_tools if t.quality_score is not None]
    if scores:
        print(f"  Average: {sum(scores) / len(scores):.1f}")
        print(f"  Min: {min(scores):.1f}")
        print(f"  Max: {max(scores):.1f}")

    # Show blocking status
    blocked = [t for t in scored_tools if t.filter_status.state == FilterState.EXCLUDED]
    print(f"\n## Blocked Tools: {len(blocked)}")
    for tool in blocked:
        print(f"  {tool.name}: {', '.join(tool.filter_status.reasons)}")


if __name__ == "__main__":
    main()
