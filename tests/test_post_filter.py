"""Tests for post-filtering logic."""

from datetime import UTC, datetime, timedelta

import pytest

from src.filters.post_filter import PostFilter
from src.models.model_eval import FilterThresholds
from src.models.model_tool import (
    FilterReasons,
    FilterState,
    Lifecycle,
    Maintenance,
    Metrics,
    Security,
    SecurityStatus,
    SourceType,
    Tool,
    Vulnerabilities,
)


@pytest.fixture
def post_filter() -> PostFilter:
    """Create a PostFilter instance."""
    return PostFilter()


@pytest.fixture
def default_thresholds() -> FilterThresholds:
    """Create default filter thresholds."""
    return FilterThresholds(
        min_downloads=1000,
        min_stars=100,
        max_days_since_update=365,
        min_score=30.0,
    )


@pytest.fixture
def high_score_tool() -> Tool:
    """Create a high-scoring tool that should be visible."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:library/postgres",
        name="postgres",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/postgres",
        description="Official PostgreSQL image",
        metrics=Metrics(downloads=1_000_000_000, stars=10_000),
        maintenance=Maintenance(
            last_updated=now - timedelta(days=7),
            is_deprecated=False,
        ),
        lifecycle=Lifecycle.STABLE,
        quality_score=85.0,
        scraped_at=now,
    )


@pytest.fixture
def stale_tool() -> Tool:
    """Create a stale tool (not updated in over 365 days)."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:user/stale",
        name="stale-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/stale",
        description="Not updated in years",
        metrics=Metrics(downloads=100_000, stars=200),
        maintenance=Maintenance(last_updated=now - timedelta(days=500)),
        quality_score=60.0,
        scraped_at=now,
    )


@pytest.fixture
def low_downloads_tool() -> Tool:
    """Create a tool with low downloads."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:user/unpopular",
        name="unpopular-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/unpopular",
        description="Not many downloads",
        metrics=Metrics(downloads=500, stars=150),
        maintenance=Maintenance(last_updated=now - timedelta(days=10)),
        quality_score=55.0,
        scraped_at=now,
    )


@pytest.fixture
def low_stars_tool() -> Tool:
    """Create a tool with low stars."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:user/few-stars",
        name="few-stars-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/few-stars",
        description="Not many stars",
        metrics=Metrics(downloads=10_000, stars=50),
        maintenance=Maintenance(last_updated=now - timedelta(days=10)),
        quality_score=55.0,
        scraped_at=now,
    )


@pytest.fixture
def experimental_tool() -> Tool:
    """Create an experimental tool that should be hidden."""
    now = datetime.now(UTC)
    return Tool(
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
    )


@pytest.fixture
def legacy_tool() -> Tool:
    """Create a legacy tool that should be hidden."""
    now = datetime.now(UTC)
    return Tool(
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
    )


@pytest.fixture
def low_score_tool() -> Tool:
    """Create a tool with low score (between min_score and min_score*1.5)."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:user/lowscore",
        name="lowscore-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/lowscore",
        description="Low quality score",
        metrics=Metrics(downloads=10_000, stars=150),
        maintenance=Maintenance(last_updated=now - timedelta(days=30)),
        lifecycle=Lifecycle.ACTIVE,
        quality_score=35.0,
        scraped_at=now,
    )


@pytest.fixture
def very_low_score_tool() -> Tool:
    """Create a tool with very low score (below min_score*0.5)."""
    now = datetime.now(UTC)
    return Tool(
        id="docker_hub:user/verylowscore",
        name="verylowscore-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/user/verylowscore",
        description="Very low quality score",
        metrics=Metrics(downloads=5_000, stars=120),
        maintenance=Maintenance(last_updated=now - timedelta(days=20)),
        lifecycle=Lifecycle.ACTIVE,
        quality_score=10.0,
        scraped_at=now,
    )


class TestPostFilter:
    """Tests for PostFilter class."""

    def test_high_score_tool_visible(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        high_score_tool: Tool,
    ) -> None:
        """Test that high-scoring tools remain visible."""
        result = post_filter.apply([high_score_tool], default_thresholds)
        assert len(result) == 1
        assert result[0].id == high_score_tool.id
        assert result[0].filter_status.state == FilterState.VISIBLE

    def test_stale_tool_excluded(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        stale_tool: Tool,
    ) -> None:
        """Test that stale tools are excluded."""
        result = post_filter.apply([stale_tool], default_thresholds)
        assert len(result) == 0
        assert stale_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.STALE in stale_tool.filter_status.reasons

    def test_low_downloads_excluded(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        low_downloads_tool: Tool,
    ) -> None:
        """Test that tools with low downloads are excluded."""
        result = post_filter.apply([low_downloads_tool], default_thresholds)
        assert len(result) == 0
        assert low_downloads_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.LOW_DOWNLOADS in low_downloads_tool.filter_status.reasons

    def test_low_stars_excluded(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        low_stars_tool: Tool,
    ) -> None:
        """Test that tools with low stars are excluded."""
        result = post_filter.apply([low_stars_tool], default_thresholds)
        assert len(result) == 0
        assert low_stars_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.LOW_DOWNLOADS in low_stars_tool.filter_status.reasons

    def test_experimental_tool_hidden(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        experimental_tool: Tool,
    ) -> None:
        """Test that experimental tools are hidden."""
        result = post_filter.apply([experimental_tool], default_thresholds)
        assert len(result) == 1
        assert result[0].filter_status.state == FilterState.HIDDEN
        assert FilterReasons.EXPERIMENTAL in result[0].filter_status.reasons

    def test_legacy_tool_hidden(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        legacy_tool: Tool,
    ) -> None:
        """Test that legacy tools are hidden."""
        result = post_filter.apply([legacy_tool], default_thresholds)
        assert len(result) == 1
        assert result[0].filter_status.state == FilterState.HIDDEN
        assert FilterReasons.LEGACY in result[0].filter_status.reasons

    def test_low_score_hidden(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        low_score_tool: Tool,
    ) -> None:
        """Test that low score tools are hidden."""
        result = post_filter.apply([low_score_tool], default_thresholds)
        assert len(result) == 1
        assert result[0].filter_status.state == FilterState.HIDDEN
        assert FilterReasons.LOW_SCORE in result[0].filter_status.reasons

    def test_very_low_score_excluded(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        very_low_score_tool: Tool,
    ) -> None:
        """Test that very low score tools are excluded."""
        result = post_filter.apply([very_low_score_tool], default_thresholds)
        assert len(result) == 0
        assert very_low_score_tool.filter_status.state == FilterState.EXCLUDED
        assert FilterReasons.LOW_SCORE in very_low_score_tool.filter_status.reasons

    def test_already_excluded_skipped(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
    ) -> None:
        """Test that already excluded tools are skipped."""
        now = datetime.now(UTC)
        tool = Tool(
            id="docker_hub:user/excluded",
            name="excluded",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/excluded",
            metrics=Metrics(downloads=10_000, stars=200),
            maintenance=Maintenance(last_updated=now),
            quality_score=80.0,
            scraped_at=now,
        )
        # Pre-mark as excluded
        tool.filter_status.state = FilterState.EXCLUDED
        tool.filter_status.reasons.append(FilterReasons.SPAM)

        result = post_filter.apply([tool], default_thresholds)
        # Should still be excluded
        assert len(result) == 0
        assert tool.filter_status.state == FilterState.EXCLUDED

    def test_no_last_updated_skips_staleness_check(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
    ) -> None:
        """Test that tools without last_updated skip staleness check."""
        now = datetime.now(UTC)
        tool = Tool(
            id="docker_hub:user/no-update-time",
            name="no-update-time",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/no-update-time",
            metrics=Metrics(downloads=10_000, stars=200),
            maintenance=Maintenance(last_updated=None),
            quality_score=70.0,
            scraped_at=now,
        )
        result = post_filter.apply([tool], default_thresholds)
        # Should pass (not excluded for staleness)
        assert len(result) == 1
        assert FilterReasons.STALE not in tool.filter_status.reasons

    def test_no_quality_score_skips_score_checks(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
    ) -> None:
        """Test that tools without quality_score skip score checks."""
        now = datetime.now(UTC)
        tool = Tool(
            id="docker_hub:user/no-score",
            name="no-score",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/no-score",
            metrics=Metrics(downloads=10_000, stars=200),
            maintenance=Maintenance(last_updated=now - timedelta(days=10)),
            quality_score=None,
            scraped_at=now,
        )
        result = post_filter.apply([tool], default_thresholds)
        # Should pass (not excluded for score)
        assert len(result) == 1
        assert FilterReasons.LOW_SCORE not in tool.filter_status.reasons

    def test_mixed_tools_filtering(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
        high_score_tool: Tool,
        stale_tool: Tool,
        experimental_tool: Tool,
    ) -> None:
        """Test filtering with mixed tools."""
        tools = [high_score_tool, stale_tool, experimental_tool]
        result = post_filter.apply(tools, default_thresholds)

        # high_score_tool should be visible
        # stale_tool should be excluded (not in result)
        # experimental_tool should be hidden (in result but marked HIDDEN)
        assert len(result) == 2

        visible = [t for t in result if t.filter_status.state == FilterState.VISIBLE]
        hidden = [t for t in result if t.filter_status.state == FilterState.HIDDEN]

        assert len(visible) == 1
        assert visible[0].id == high_score_tool.id
        assert len(hidden) == 1
        assert hidden[0].id == experimental_tool.id

    def test_custom_thresholds(self, post_filter: PostFilter) -> None:
        """Test with custom thresholds."""
        now = datetime.now(UTC)

        # First test with strict thresholds
        tool1 = Tool(
            id="docker_hub:user/custom1",
            name="custom1",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/custom1",
            metrics=Metrics(downloads=500, stars=50),
            maintenance=Maintenance(last_updated=now - timedelta(days=200)),
            quality_score=20.0,
            scraped_at=now,
        )

        # Strict thresholds - tool should be excluded
        strict = FilterThresholds(
            min_downloads=1000,
            min_stars=100,
            max_days_since_update=180,
            min_score=25.0,
        )
        result_strict = post_filter.apply([tool1], strict)
        assert len(result_strict) == 0

        # Second test with lenient thresholds (new tool instance)
        tool2 = Tool(
            id="docker_hub:user/custom2",
            name="custom2",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/custom2",
            metrics=Metrics(downloads=500, stars=50),
            maintenance=Maintenance(last_updated=now - timedelta(days=200)),
            quality_score=20.0,
            scraped_at=now,
        )

        # Lenient thresholds - tool should pass
        lenient = FilterThresholds(
            min_downloads=100,
            min_stars=10,
            max_days_since_update=400,
            min_score=10.0,
        )
        result_lenient = post_filter.apply([tool2], lenient)
        assert len(result_lenient) == 1

    def test_days_since_update_calculation(self, post_filter: PostFilter) -> None:
        """Test days since update calculation."""
        now = datetime.now(UTC)
        tool = Tool(
            id="docker_hub:user/test",
            name="test",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/test",
            metrics=Metrics(downloads=1000, stars=100),
            maintenance=Maintenance(last_updated=now - timedelta(days=100)),
            scraped_at=now,
        )

        days = post_filter._calculate_days_since_update(tool, current_time=now)
        assert days == 100

        # Test with None last_updated
        tool.maintenance.last_updated = None
        days = post_filter._calculate_days_since_update(tool)
        assert days is None

    def test_no_duplicate_reasons(
        self,
        post_filter: PostFilter,
        default_thresholds: FilterThresholds,
    ) -> None:
        """Test that filter reasons are not duplicated."""
        now = datetime.now(UTC)
        # Use good enough metrics to not trigger exclusion
        tool = Tool(
            id="docker_hub:user/experimental-good",
            name="experimental-good",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/experimental-good",
            metrics=Metrics(downloads=10_000, stars=200),
            maintenance=Maintenance(last_updated=now - timedelta(days=10)),
            lifecycle=Lifecycle.EXPERIMENTAL,
            quality_score=70.0,
            scraped_at=now,
        )

        # Apply multiple times (shouldn't happen in practice)
        post_filter.apply([tool], default_thresholds)
        post_filter.apply([tool], default_thresholds)

        # Should only have one EXPERIMENTAL reason
        assert tool.filter_status.reasons.count(FilterReasons.EXPERIMENTAL) == 1


def test_post_filter_empty_list() -> None:
    """Test post-filter with empty tool list."""
    post_filter = PostFilter()
    thresholds = FilterThresholds()
    result = post_filter.apply([], thresholds)
    assert len(result) == 0


def test_post_filter_all_visible() -> None:
    """Test post-filter where all tools remain visible."""
    post_filter = PostFilter()
    thresholds = FilterThresholds(
        min_downloads=100,
        min_stars=10,
        max_days_since_update=365,
        min_score=10.0,
    )
    now = datetime.now(UTC)
    tools = [
        Tool(
            id=f"docker_hub:library/tool{i}",
            name=f"tool{i}",
            source=SourceType.DOCKER_HUB,
            source_url=f"https://hub.docker.com/_/tool{i}",
            metrics=Metrics(downloads=10000, stars=100),
            maintenance=Maintenance(last_updated=now - timedelta(days=30)),
            lifecycle=Lifecycle.STABLE,
            quality_score=80.0,
            scraped_at=now,
        )
        for i in range(5)
    ]
    result = post_filter.apply(tools, thresholds)
    assert len(result) == 5
    assert all(t.filter_status.state == FilterState.VISIBLE for t in result)


def test_post_filter_all_excluded() -> None:
    """Test post-filter where all tools are excluded."""
    post_filter = PostFilter()
    thresholds = FilterThresholds(
        min_downloads=10000,
        min_stars=1000,
        max_days_since_update=30,
        min_score=80.0,
    )
    now = datetime.now(UTC)
    tools = [
        Tool(
            id=f"docker_hub:user/bad{i}",
            name=f"bad{i}",
            source=SourceType.DOCKER_HUB,
            source_url=f"https://hub.docker.com/r/user/bad{i}",
            metrics=Metrics(downloads=100, stars=10),
            maintenance=Maintenance(last_updated=now - timedelta(days=100)),
            quality_score=20.0,
            scraped_at=now,
        )
        for i in range(5)
    ]
    result = post_filter.apply(tools, thresholds)
    assert len(result) == 0
