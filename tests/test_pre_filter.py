"""Tests for pre-filtering logic."""

from datetime import UTC, datetime

import pytest

from src.filters.pre_filter import PreFilter
from src.models.model_tool import (
    FilterReasons,
    FilterState,
    Maintainer,
    MaintainerType,
    Maintenance,
    Metrics,
    SourceType,
    Tool,
)


@pytest.fixture
def pre_filter() -> PreFilter:
    """Create a PreFilter instance."""
    return PreFilter()


@pytest.fixture
def valid_tool() -> Tool:
    """Create a valid tool that should pass pre-filtering."""
    return Tool(
        id="docker_hub:library/postgres",
        name="postgres",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/postgres",
        description="Official PostgreSQL image",
        maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
        metrics=Metrics(downloads=1_000_000_000, stars=10_000),
        maintenance=Maintenance(
            last_updated=datetime.now(UTC),
            is_deprecated=False,
        ),
        scraped_at=datetime.now(UTC),
    )


@pytest.fixture
def zero_metrics_tool() -> Tool:
    """Create a tool with zero metrics."""
    return Tool(
        id="docker_hub:user/abandoned",
        name="abandoned-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/abandoned",
        description="An abandoned tool with no usage",
        metrics=Metrics(downloads=0, stars=0),
        scraped_at=datetime.now(UTC),
    )


@pytest.fixture
def deprecated_tool() -> Tool:
    """Create a deprecated tool."""
    return Tool(
        id="docker_hub:user/legacy",
        name="legacy-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/legacy",
        description="A deprecated legacy tool",
        metrics=Metrics(downloads=50_000, stars=100),
        maintenance=Maintenance(
            last_updated=datetime.now(UTC),
            is_deprecated=True,
        ),
        scraped_at=datetime.now(UTC),
    )


@pytest.fixture
def spam_name_tool() -> Tool:
    """Create a tool with spam in name."""
    return Tool(
        id="docker_hub:user/test-image",
        name="test-image",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/test-image",
        description="Just a test image",
        metrics=Metrics(downloads=100, stars=0),
        scraped_at=datetime.now(UTC),
    )


@pytest.fixture
def spam_description_tool() -> Tool:
    """Create a tool with spam in description."""
    return Tool(
        id="docker_hub:user/myapp",
        name="myapp",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/myapp",
        description="This is a placeholder for my app",
        metrics=Metrics(downloads=50, stars=1),
        scraped_at=datetime.now(UTC),
    )


class TestPreFilter:
    """Tests for PreFilter class."""

    def test_valid_tool_passes(self, pre_filter: PreFilter, valid_tool: Tool) -> None:
        """Test that valid tools pass pre-filtering."""
        result = pre_filter.apply([valid_tool])
        assert len(result) == 1
        assert result[0].id == valid_tool.id
        assert result[0].filter_status.state == FilterState.VISIBLE

    def test_zero_metrics_excluded(
        self, pre_filter: PreFilter, zero_metrics_tool: Tool
    ) -> None:
        """Test that tools with zero downloads AND stars are excluded."""
        result = pre_filter.apply([zero_metrics_tool])
        assert len(result) == 0
        assert zero_metrics_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.LOW_DOWNLOADS in zero_metrics_tool.filter_status.reasons

    def test_deprecated_excluded(
        self, pre_filter: PreFilter, deprecated_tool: Tool
    ) -> None:
        """Test that deprecated tools are excluded."""
        result = pre_filter.apply([deprecated_tool])
        assert len(result) == 0
        assert deprecated_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.DEPRECATED in deprecated_tool.filter_status.reasons

    def test_spam_name_excluded(
        self, pre_filter: PreFilter, spam_name_tool: Tool
    ) -> None:
        """Test that tools with spam in name are excluded."""
        result = pre_filter.apply([spam_name_tool])
        assert len(result) == 0
        assert spam_name_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.SPAM in spam_name_tool.filter_status.reasons

    def test_spam_description_excluded(
        self, pre_filter: PreFilter, spam_description_tool: Tool
    ) -> None:
        """Test that tools with spam in description are excluded."""
        result = pre_filter.apply([spam_description_tool])
        assert len(result) == 0
        assert spam_description_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.SPAM in spam_description_tool.filter_status.reasons

    def test_nonzero_downloads_passes(self, pre_filter: PreFilter) -> None:
        """Test that tools with downloads but no stars pass."""
        tool = Tool(
            id="docker_hub:user/downloaded",
            name="downloaded",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/downloaded",
            description="Tool with downloads but no stars",
            metrics=Metrics(downloads=1000, stars=0),
            scraped_at=datetime.now(UTC),
        )
        result = pre_filter.apply([tool])
        assert len(result) == 1

    def test_nonzero_stars_passes(self, pre_filter: PreFilter) -> None:
        """Test that tools with stars but no downloads pass."""
        tool = Tool(
            id="github:user/starred",
            name="starred",
            source=SourceType.GITHUB,
            source_url="https://github.com/user/starred",
            description="Tool with stars but no downloads",
            metrics=Metrics(downloads=0, stars=100),
            scraped_at=datetime.now(UTC),
        )
        result = pre_filter.apply([tool])
        assert len(result) == 1

    def test_multiple_tools_mixed(
        self,
        pre_filter: PreFilter,
        valid_tool: Tool,
        zero_metrics_tool: Tool,
        deprecated_tool: Tool,
    ) -> None:
        """Test filtering with mixed valid and invalid tools."""
        tools = [valid_tool, zero_metrics_tool, deprecated_tool]
        result = pre_filter.apply(tools)
        assert len(result) == 1
        assert result[0].id == valid_tool.id

    def test_spam_patterns_case_insensitive(self, pre_filter: PreFilter) -> None:
        """Test that spam patterns are case-insensitive."""
        tool = Tool(
            id="docker_hub:user/TEST-image",
            name="TEST-image",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/TEST-image",
            description="An IMAGE for TESTING",
            metrics=Metrics(downloads=100, stars=0),
            scraped_at=datetime.now(UTC),
        )
        result = pre_filter.apply([tool])
        assert len(result) == 0
        assert tool.filter_status.state == FilterState.EXCLUDED

    def test_spam_patterns_word_boundary(self, pre_filter: PreFilter) -> None:
        """Test that spam patterns respect word boundaries."""
        # "test" as substring shouldn't trigger (e.g., "latest" or "fastest")
        tool = Tool(
            id="docker_hub:user/latest-version",
            name="latest-version",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/latest-version",
            description="The latest version of the tool",
            metrics=Metrics(downloads=1000, stars=10),
            scraped_at=datetime.now(UTC),
        )
        result = pre_filter.apply([tool])
        # Should pass since "test" in "latest" is not a word boundary match
        assert len(result) == 1

    def test_prefix_spam_patterns(self, pre_filter: PreFilter) -> None:
        """Test prefix spam patterns like 'test-', 'demo-'."""
        tools = [
            Tool(
                id="docker_hub:user/test-app",
                name="test-app",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/user/test-app",
                metrics=Metrics(downloads=100, stars=0),
                scraped_at=datetime.now(UTC),
            ),
            Tool(
                id="docker_hub:user/demo-service",
                name="demo-service",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/r/user/demo-service",
                metrics=Metrics(downloads=100, stars=0),
                scraped_at=datetime.now(UTC),
            ),
        ]
        result = pre_filter.apply(tools)
        assert len(result) == 0

    def test_no_duplicate_reasons(self, pre_filter: PreFilter) -> None:
        """Test that filter reasons are not duplicated."""
        tool = Tool(
            id="docker_hub:user/bad",
            name="bad",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/bad",
            description="bad",
            metrics=Metrics(downloads=0, stars=0),
            scraped_at=datetime.now(UTC),
        )
        # Apply twice (shouldn't happen in practice, but test robustness)
        pre_filter.apply([tool])
        pre_filter.apply([tool])
        # Should only have one LOW_DOWNLOADS reason
        assert tool.filter_status.reasons.count(FilterReasons.LOW_DOWNLOADS) == 1

    def test_fork_detection_placeholder(self, pre_filter: PreFilter) -> None:
        """Test fork detection placeholder (not yet implemented)."""
        # For now, fork detection returns False
        # This test documents the expected behavior when implemented
        tool = Tool(
            id="github:user/forked-repo",
            name="forked-repo",
            source=SourceType.GITHUB,
            source_url="https://github.com/user/forked-repo",
            description="A forked repository",
            metrics=Metrics(downloads=100, stars=10),
            scraped_at=datetime.now(UTC),
        )
        result = pre_filter.apply([tool])
        # Should pass for now since fork detection is not implemented
        assert len(result) == 1


def test_pre_filter_empty_list() -> None:
    """Test pre-filter with empty tool list."""
    pre_filter = PreFilter()
    result = pre_filter.apply([])
    assert len(result) == 0


def test_pre_filter_all_pass() -> None:
    """Test pre-filter where all tools pass."""
    pre_filter = PreFilter()
    tools = [
        Tool(
            id=f"docker_hub:library/tool{i}",
            name=f"tool{i}",
            source=SourceType.DOCKER_HUB,
            source_url=f"https://hub.docker.com/_/tool{i}",
            description=f"Tool {i}",
            metrics=Metrics(downloads=10000, stars=100),
            scraped_at=datetime.now(UTC),
        )
        for i in range(5)
    ]
    result = pre_filter.apply(tools)
    assert len(result) == 5


def test_pre_filter_all_excluded() -> None:
    """Test pre-filter where all tools are excluded."""
    pre_filter = PreFilter()
    tools = [
        Tool(
            id=f"docker_hub:user/test{i}",
            name=f"test{i}",
            source=SourceType.DOCKER_HUB,
            source_url=f"https://hub.docker.com/r/user/test{i}",
            description="test",
            metrics=Metrics(downloads=0, stars=0),
            scraped_at=datetime.now(UTC),
        )
        for i in range(5)
    ]
    result = pre_filter.apply(tools)
    assert len(result) == 0
