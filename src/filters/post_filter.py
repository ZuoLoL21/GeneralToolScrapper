"""Post-filtering logic to apply policy-based filtering after scoring.

This filter runs AFTER scoring to determine tool visibility based on
quality scores, lifecycle stage, and policy thresholds.
"""

import logging
from datetime import UTC, datetime

from src.models.model_eval import FilterThresholds
from src.models.model_tool import FilterReasons, FilterState, Lifecycle, Tool

logger = logging.getLogger(__name__)


class PostFilter:
    """Apply policy-based filtering after scoring.

    Uses computed quality scores and thresholds to determine which tools
    should be visible, hidden, or excluded from results.
    """

    def apply(self, tools: list[Tool], thresholds: FilterThresholds) -> list[Tool]:
        """Apply policy-based filtering after scoring.

        Args:
            tools: List of scored tools to filter
            thresholds: Filtering thresholds from configuration

        Returns:
            List of tools that should be visible (includes HIDDEN tools)
        """
        filtered = []
        excluded_count = 0
        hidden_count = 0

        for tool in tools:
            # Skip already excluded tools from pre-filter
            if tool.filter_status.state == FilterState.EXCLUDED:
                excluded_count += 1
                continue

            # Check exclusion conditions
            if self._should_exclude_post(tool, thresholds):
                excluded_count += 1
                logger.debug(
                    f"Post-filter excluded {tool.id}: {tool.filter_status.reasons}"
                )
                continue

            # Check hidden conditions
            if self._should_hide(tool, thresholds):
                hidden_count += 1
                logger.debug(
                    f"Post-filter hid {tool.id}: {tool.filter_status.reasons}"
                )

            filtered.append(tool)

        logger.info(
            f"Post-filter: {len(filtered)}/{len(tools)} tools visible "
            f"({hidden_count} hidden, {excluded_count} excluded)"
        )

        return filtered

    def _should_exclude_post(self, tool: Tool, thresholds: FilterThresholds) -> bool:
        """Check if tool should be excluded in post-filtering.

        Args:
            tool: Tool to check
            thresholds: Filtering thresholds

        Returns:
            True if tool should be excluded
        """
        # Critical vulnerabilities already handled by SecurityEvaluator in registry
        # which sets FilterState.EXCLUDED directly

        # Check 1: Staleness
        days_since_update = self._calculate_days_since_update(tool)
        if days_since_update is not None and days_since_update > thresholds.max_days_since_update:
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.STALE)
            return True

        # Check 2: Low downloads
        if tool.metrics.downloads < thresholds.min_downloads:
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.LOW_DOWNLOADS)
            return True

        # Check 3: Low stars
        if tool.metrics.stars < thresholds.min_stars:
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.LOW_DOWNLOADS)
            return True

        # Check 4: Very low score (below half of minimum acceptable)
        if tool.quality_score is not None:
            very_low_threshold = thresholds.min_score * 0.5
            if tool.quality_score < very_low_threshold:
                tool.filter_status.state = FilterState.EXCLUDED
                self._add_filter_reason(tool, FilterReasons.LOW_SCORE)
                return True

        return False

    def _should_hide(self, tool: Tool, thresholds: FilterThresholds) -> bool:
        """Check if tool should be hidden (but not excluded).

        Args:
            tool: Tool to check
            thresholds: Filtering thresholds

        Returns:
            True if tool should be hidden
        """
        # Check 1: Experimental lifecycle
        if tool.lifecycle == Lifecycle.EXPERIMENTAL:
            tool.filter_status.state = FilterState.HIDDEN
            self._add_filter_reason(tool, FilterReasons.EXPERIMENTAL)
            return True

        # Check 2: Legacy lifecycle
        if tool.lifecycle == Lifecycle.LEGACY:
            tool.filter_status.state = FilterState.HIDDEN
            self._add_filter_reason(tool, FilterReasons.LEGACY)
            return True

        # Check 3: Low score (but not very low)
        if tool.quality_score is not None:
            low_threshold = thresholds.min_score * 1.5
            if thresholds.min_score <= tool.quality_score < low_threshold:
                tool.filter_status.state = FilterState.HIDDEN
                self._add_filter_reason(tool, FilterReasons.LOW_SCORE)
                return True

        return False

    def _calculate_days_since_update(
        self, tool: Tool, current_time: datetime | None = None
    ) -> int | None:
        """Calculate days since last update.

        Args:
            tool: Tool to check
            current_time: Current time (defaults to now)

        Returns:
            Number of days since last update, or None if no update time
        """
        if tool.maintenance.last_updated is None:
            return None

        if current_time is None:
            current_time = datetime.now(UTC)

        return (current_time - tool.maintenance.last_updated).days

    def _add_filter_reason(self, tool: Tool, reason: str) -> None:
        """Add reason to filter status if not already present.

        Args:
            tool: Tool to update
            reason: Filter reason code from FilterReasons
        """
        if reason not in tool.filter_status.reasons:
            tool.filter_status.reasons.append(reason)


def main() -> None:
    """Demonstrate post-filtering with sample scored tools."""
    from datetime import datetime, timedelta, timezone

    from src.models.model_eval import FilterThresholds
    from src.models.model_tool import (
        Maintainer,
        MaintainerType,
        Maintenance,
        Metrics,
        Security,
        SecurityStatus,
        SourceType,
        Vulnerabilities,
    )

    print("Post-Filter Demo")
    print("=" * 60)

    # Create thresholds
    thresholds = FilterThresholds(
        min_downloads=1000,
        min_stars=100,
        max_days_since_update=365,
        min_score=30.0,
    )

    print(f"\n## Thresholds")
    print(f"Min downloads: {thresholds.min_downloads}")
    print(f"Min stars: {thresholds.min_stars}")
    print(f"Max days since update: {thresholds.max_days_since_update}")
    print(f"Min score: {thresholds.min_score}")
    print(f"Low score threshold: {thresholds.min_score * 1.5}")
    print(f"Very low score threshold: {thresholds.min_score * 0.5}")

    now = datetime.now(timezone.utc)

    # Create sample tools with various scores and states
    tools = [
        # High score, should be visible
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="Official PostgreSQL image",
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000_000_000, stars=10_000),
            maintenance=Maintenance(
                last_updated=now - timedelta(days=7),
                is_deprecated=False,
            ),
            lifecycle=Lifecycle.STABLE,
            quality_score=85.0,
            scraped_at=now,
        ),
        # Critical vulnerability (should already be excluded by registry)
        Tool(
            id="docker_hub:user/vulnerable",
            name="vulnerable-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/vulnerable",
            description="Tool with critical vulnerabilities",
            metrics=Metrics(downloads=50_000, stars=500),
            maintenance=Maintenance(last_updated=now - timedelta(days=30)),
            security=Security(
                status=SecurityStatus.VULNERABLE,
                vulnerabilities=Vulnerabilities(critical=1),
            ),
            quality_score=40.0,
            scraped_at=now,
        ),
        # Stale tool (over 365 days since update)
        Tool(
            id="docker_hub:user/stale",
            name="stale-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/stale",
            description="Not updated in years",
            metrics=Metrics(downloads=100_000, stars=200),
            maintenance=Maintenance(last_updated=now - timedelta(days=500)),
            quality_score=60.0,
            scraped_at=now,
        ),
        # Low downloads
        Tool(
            id="docker_hub:user/unpopular",
            name="unpopular-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/unpopular",
            description="Not many downloads",
            metrics=Metrics(downloads=500, stars=150),  # Below min_downloads
            maintenance=Maintenance(last_updated=now - timedelta(days=10)),
            quality_score=55.0,
            scraped_at=now,
        ),
        # Experimental lifecycle (should be hidden)
        Tool(
            id="docker_hub:user/experimental",
            name="experimental-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/experimental",
            description="Still in experimental phase",
            metrics=Metrics(downloads=50_000, stars=300),
            maintenance=Maintenance(last_updated=now - timedelta(days=5)),
            lifecycle=Lifecycle.EXPERIMENTAL,
            quality_score=70.0,
            scraped_at=now,
        ),
        # Legacy lifecycle (should be hidden)
        Tool(
            id="docker_hub:user/legacy",
            name="legacy-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/legacy",
            description="Legacy but still maintained",
            metrics=Metrics(downloads=200_000, stars=500),
            maintenance=Maintenance(last_updated=now - timedelta(days=60)),
            lifecycle=Lifecycle.LEGACY,
            quality_score=65.0,
            scraped_at=now,
        ),
        # Low score (should be hidden)
        Tool(
            id="docker_hub:user/lowscore",
            name="lowscore-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/lowscore",
            description="Low quality score",
            metrics=Metrics(downloads=10_000, stars=150),
            maintenance=Maintenance(last_updated=now - timedelta(days=30)),
            lifecycle=Lifecycle.ACTIVE,
            quality_score=35.0,  # Between min_score and min_score*1.5
            scraped_at=now,
        ),
        # Very low score (should be excluded)
        Tool(
            id="docker_hub:user/verylowscore",
            name="verylowscore-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/verylowscore",
            description="Very low quality score",
            metrics=Metrics(downloads=5_000, stars=120),
            maintenance=Maintenance(last_updated=now - timedelta(days=20)),
            lifecycle=Lifecycle.ACTIVE,
            quality_score=10.0,  # Below min_score*0.5
            scraped_at=now,
        ),
    ]

    print(f"\n## Before Post-Filtering")
    print(f"Total tools: {len(tools)}\n")

    # Apply post-filter
    post_filter = PostFilter()
    filtered = post_filter.apply(tools, thresholds)

    print(f"\n## After Post-Filtering")
    visible_count = sum(
        1 for t in filtered if t.filter_status.state == FilterState.VISIBLE
    )
    hidden_count = sum(
        1 for t in filtered if t.filter_status.state == FilterState.HIDDEN
    )
    excluded_count = len(tools) - len(filtered)
    print(f"Visible: {visible_count} tools")
    print(f"Hidden: {hidden_count} tools (shown with --include-hidden)")
    print(f"Excluded: {excluded_count} tools (never shown)\n")

    print("## Detailed Results")
    for tool in tools:
        status = tool.filter_status.state.value
        reasons = ", ".join(tool.filter_status.reasons) if tool.filter_status.reasons else "N/A"
        score = f"{tool.quality_score:.1f}" if tool.quality_score else "N/A"
        days = post_filter._calculate_days_since_update(tool)
        days_str = str(days) if days is not None else "N/A"

        print(f"\n{tool.name} ({tool.id}):")
        print(f"  Status: {status}")
        print(f"  Reasons: {reasons}")
        print(f"  Score: {score}")
        print(f"  Lifecycle: {tool.lifecycle.value}")
        print(f"  Days since update: {days_str}")
        print(f"  Metrics: downloads={tool.metrics.downloads}, stars={tool.metrics.stars}")

    print("\n## Summary")
    print("Post-filter applies policy-based filtering AFTER scoring:")
    print("\nEXCLUDED (never shown):")
    print("- Stale tools (>365 days since update)")
    print("- Low downloads (<1000) or low stars (<100)")
    print("- Very low score (<15.0, half of min_score)")
    print("\nHIDDEN (shown with --include-hidden):")
    print("- Experimental lifecycle")
    print("- Legacy lifecycle")
    print("- Low score (30.0 <= score < 45.0)")


if __name__ == "__main__":
    main()
