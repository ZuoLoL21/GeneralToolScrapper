"""Pre-filtering logic to remove obvious junk before statistics computation.

This filter runs BEFORE stats and scoring to prevent spam/junk tools from
polluting category distributions and Z-score normalization.
"""

import logging
import re

from src.models.model_tool import FilterReasons, FilterState, Tool

logger = logging.getLogger(__name__)


class PreFilter:
    """Filter out obvious junk before stats computation.

    Removes tools that are clearly spam, deprecated, or have zero metrics
    before they can affect category distributions and normalization.
    """

    # Spam patterns for name/description matching
    SPAM_PATTERNS = [
        r"\btest\b",
        r"\bdemo\b",
        r"\bexample\b",
        r"\bplaceholder\b",
        r"\bsample\b",
        r"\btodo\b",
        r"\bwip\b",
        r"^test-",
        r"^demo-",
        r"^example-",
    ]

    def __init__(self) -> None:
        """Initialize pre-filter with compiled regex patterns."""
        self.spam_regex = re.compile("|".join(self.SPAM_PATTERNS), re.IGNORECASE)

    def apply(self, tools: list[Tool]) -> list[Tool]:
        """Filter out obvious junk before stats computation.

        Args:
            tools: List of tools to filter

        Returns:
            List of tools that pass pre-filtering
        """
        filtered = []
        excluded_count = 0

        for tool in tools:
            if self._should_exclude_pre(tool):
                excluded_count += 1
                logger.debug(
                    f"Pre-filter excluded {tool.id}: {tool.filter_status.reasons}"
                )
            else:
                filtered.append(tool)

        logger.info(
            f"Pre-filter: {len(filtered)}/{len(tools)} tools passed "
            f"({excluded_count} excluded)"
        )

        return filtered

    def _should_exclude_pre(self, tool: Tool) -> bool:
        """Check if tool should be excluded in pre-filtering.

        Args:
            tool: Tool to check

        Returns:
            True if tool should be excluded
        """
        # Check 1: Zero downloads/metrics
        if self._is_zero_metrics(tool):
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.LOW_DOWNLOADS)
            return True

        # Check 2: Deprecated
        if self._is_deprecated(tool):
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.DEPRECATED)
            return True

        # Check 3: Deprecated image format (Docker manifest schema v1)
        if self._is_deprecated_image_format(tool):
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.DEPRECATED)
            return True

        # Check 4: Spam patterns
        if self._is_spam(tool):
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.SPAM)
            return True

        # Check 5: Forks (GitHub only)
        if self._is_fork(tool):
            tool.filter_status.state = FilterState.EXCLUDED
            self._add_filter_reason(tool, FilterReasons.SPAM)
            return True

        return False

    def _is_zero_metrics(self, tool: Tool) -> bool:
        """Check if tool has zero downloads AND zero stars.

        Args:
            tool: Tool to check

        Returns:
            True if both downloads and stars are zero
        """
        return tool.metrics.downloads == 0 and tool.metrics.stars == 0

    def _is_deprecated(self, tool: Tool) -> bool:
        """Check if tool is marked as deprecated.

        Args:
            tool: Tool to check

        Returns:
            True if tool is deprecated
        """
        return tool.maintenance.is_deprecated

    def _is_deprecated_image_format(self, tool: Tool) -> bool:
        """Check if Docker image uses deprecated manifest schema v1.

        These images cannot be scanned by modern tools like Trivy.

        Args:
            tool: Tool to check

        Returns:
            True if tool uses deprecated Docker manifest schema v1
        """
        return tool.is_deprecated_image_format

    def _is_spam(self, tool: Tool) -> bool:
        """Check if tool name or description matches spam patterns.

        Args:
            tool: Tool to check

        Returns:
            True if spam patterns detected
        """
        # Check name
        if self.spam_regex.search(tool.name):
            return True

        # Check description
        if tool.description and self.spam_regex.search(tool.description):
            return True

        return False

    def _is_fork(self, tool: Tool) -> bool:
        """Check if GitHub tool is a low-activity fork.

        For now, this is a placeholder since we need fork metadata
        from the GitHub scraper. Will be implemented when GitHub
        source is available.

        Args:
            tool: Tool to check

        Returns:
            True if tool is a low-activity fork
        """
        # TODO: Implement when GitHub scraper provides fork metadata
        # Check if source is GitHub and has fork flag + low original activity
        return False

    def _add_filter_reason(self, tool: Tool, reason: str) -> None:
        """Add reason to filter status if not already present.

        Args:
            tool: Tool to update
            reason: Filter reason code from FilterReasons
        """
        if reason not in tool.filter_status.reasons:
            tool.filter_status.reasons.append(reason)


def main() -> None:
    """Demonstrate pre-filtering with sample tools."""
    from datetime import datetime, timezone

    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Maintenance,
        Metrics,
        SourceType,
    )

    print("Pre-Filter Demo")
    print("=" * 60)

    # Create sample tools with various issues
    tools = [
        # Valid tool
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="Official PostgreSQL image",
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000_000_000, stars=10_000),
            maintenance=Maintenance(
                last_updated=datetime.now(timezone.utc),
                is_deprecated=False,
            ),
            scraped_at=datetime.now(timezone.utc),
        ),
        # Zero metrics
        Tool(
            id="docker_hub:user/abandoned",
            name="abandoned-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/abandoned",
            description="An abandoned tool with no usage",
            metrics=Metrics(downloads=0, stars=0),
            scraped_at=datetime.now(timezone.utc),
        ),
        # Deprecated
        Tool(
            id="docker_hub:user/legacy",
            name="legacy-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/legacy",
            description="A deprecated legacy tool",
            metrics=Metrics(downloads=50_000, stars=100),
            maintenance=Maintenance(
                last_updated=datetime.now(timezone.utc),
                is_deprecated=True,
            ),
            scraped_at=datetime.now(timezone.utc),
        ),
        # Spam in name
        Tool(
            id="docker_hub:user/test-image",
            name="test-image",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/test-image",
            description="Just a test image",
            metrics=Metrics(downloads=100, stars=0),
            scraped_at=datetime.now(timezone.utc),
        ),
        # Spam in description
        Tool(
            id="docker_hub:user/myapp",
            name="myapp",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/myapp",
            description="This is a placeholder for my app",
            metrics=Metrics(downloads=50, stars=1),
            scraped_at=datetime.now(timezone.utc),
        ),
        # Another valid tool
        Tool(
            id="docker_hub:library/nginx",
            name="nginx",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/nginx",
            description="Official NGINX reverse proxy",
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=5_000_000_000, stars=15_000),
            maintenance=Maintenance(
                last_updated=datetime.now(timezone.utc),
                is_deprecated=False,
            ),
            scraped_at=datetime.now(timezone.utc),
        ),
    ]

    print(f"\n## Before Pre-Filtering")
    print(f"Total tools: {len(tools)}\n")

    # Apply pre-filter
    pre_filter = PreFilter()
    filtered = pre_filter.apply(tools)

    print(f"\n## After Pre-Filtering")
    print(f"Passed: {len(filtered)} tools")
    print(f"Excluded: {len(tools) - len(filtered)} tools\n")

    print("## Detailed Results")
    for tool in tools:
        status = tool.filter_status.state.value
        reasons = ", ".join(tool.filter_status.reasons) if tool.filter_status.reasons else "N/A"
        print(f"\n{tool.name} ({tool.id}):")
        print(f"  Status: {status}")
        print(f"  Reasons: {reasons}")
        print(f"  Metrics: downloads={tool.metrics.downloads}, stars={tool.metrics.stars}")
        print(f"  Deprecated: {tool.maintenance.is_deprecated}")

    print("\n## Summary")
    print("Pre-filter removes obvious junk BEFORE stats computation:")
    print("- Tools with zero downloads AND zero stars")
    print("- Deprecated tools")
    print("- Spam patterns in name/description")
    print("- Low-activity forks (GitHub only, not yet implemented)")


if __name__ == "__main__":
    main()
