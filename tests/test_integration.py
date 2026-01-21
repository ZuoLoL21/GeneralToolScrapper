"""Integration tests for end-to-end pipeline."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.model_tool import (
    FilterState,
    Lifecycle,
    Maintainer,
    MaintainerType,
    Maintenance,
    Metrics,
    SourceType,
    Tool,
)
from src.pipeline import load_processed_tools, run_scrape_pipeline
from src.storage.permanent_storage.file_manager import FileManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_scraper_tools() -> list[Tool]:
    """Create mock tools from scraper."""
    now = datetime.now(UTC)
    return [
        # Valid tool - should pass all filters
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL object-relational database system",
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000_000_000, stars=10_000),
            maintenance=Maintenance(
                last_updated=now - timedelta(days=7),
                is_deprecated=False,
            ),
            tags=["database", "sql", "postgres"],
            scraped_at=now,
        ),
        # Tool with spam in name - should be filtered in pre-filter
        Tool(
            id="docker_hub:user/test-image",
            name="test-image",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/test-image",
            description="A test image",
            metrics=Metrics(downloads=100, stars=0),
            tags=["test"],
            scraped_at=now,
        ),
        # Deprecated tool - should be filtered in pre-filter
        Tool(
            id="docker_hub:user/deprecated",
            name="deprecated-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/deprecated",
            description="Deprecated tool",
            metrics=Metrics(downloads=50_000, stars=100),
            maintenance=Maintenance(
                last_updated=now - timedelta(days=30),
                is_deprecated=True,
            ),
            tags=["old"],
            scraped_at=now,
        ),
        # Tool with low metrics but not spam - should pass pre-filter but might be hidden/excluded in post-filter
        Tool(
            id="docker_hub:user/lowmetrics",
            name="lowmetrics-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/lowmetrics",
            description="Tool with low metrics",
            metrics=Metrics(downloads=500, stars=50),
            maintenance=Maintenance(last_updated=now - timedelta(days=10)),
            tags=["utility"],
            scraped_at=now,
        ),
        # Valid tool with good metrics
        Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis in-memory data structure store",
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=500_000_000, stars=8_000),
            maintenance=Maintenance(
                last_updated=now - timedelta(days=3),
                is_deprecated=False,
            ),
            tags=["database", "cache", "redis"],
            scraped_at=now,
        ),
    ]


class TestPipelineIntegration:
    """Integration tests for complete pipeline."""

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_end_to_end(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test complete pipeline from scraping to storage."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline
        result_tools = run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=False,
            limit=None,
            data_dir=temp_dir,
        )

        # Verify scraper was called
        mock_scraper.scrape.assert_called_once()

        # Verify results
        assert len(result_tools) > 0

        # Verify files were created
        file_manager = FileManager(temp_dir)

        # Check raw data was saved
        raw_scrapes = file_manager.list_raw_scrapes(SourceType.DOCKER_HUB)
        assert len(raw_scrapes) == 1

        # Check processed data was saved
        processed_tools = file_manager.load_processed()
        assert processed_tools is not None
        assert len(processed_tools) > 0

        # Check stats were saved
        global_stats, category_stats = file_manager.load_stats()
        assert global_stats is not None
        assert category_stats is not None

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_filtering(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test that pipeline correctly filters tools."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline
        result_tools = run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=False,
            limit=None,
            data_dir=temp_dir,
        )

        # Load all processed tools
        file_manager = FileManager(temp_dir)
        all_tools = file_manager.load_processed()

        # Count filter states in processed tools
        excluded = [t for t in all_tools if t.filter_status.state == FilterState.EXCLUDED]
        hidden = [t for t in all_tools if t.filter_status.state == FilterState.HIDDEN]
        visible = [t for t in all_tools if t.filter_status.state == FilterState.VISIBLE]

        # Verify filtering happened:
        # - test-image and deprecated were removed in pre-filter (not in all_tools)
        # - lowmetrics tool got excluded in post-filter for low downloads
        # So we should have at least 1 excluded tool in processed data
        assert len(excluded) >= 1

        # Result should only contain visible + hidden tools (not excluded)
        assert len(result_tools) == len(visible) + len(hidden)

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_categorization(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test that pipeline categorizes tools."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline
        run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=False,
            limit=None,
            data_dir=temp_dir,
        )

        # Load processed tools
        file_manager = FileManager(temp_dir)
        all_tools = file_manager.load_processed()

        # Check that tools have categories assigned
        categorized = [t for t in all_tools if t.primary_category != "uncategorized"]
        assert len(categorized) > 0

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_keyword_assignment(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test that pipeline assigns keywords."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline
        run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=False,
            limit=None,
            data_dir=temp_dir,
        )

        # Load processed tools
        file_manager = FileManager(temp_dir)
        all_tools = file_manager.load_processed()

        # Check that tools have keywords assigned
        with_keywords = [t for t in all_tools if len(t.keywords) > 0]
        assert len(with_keywords) > 0

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_scoring(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test that pipeline scores tools."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline
        run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=False,
            limit=None,
            data_dir=temp_dir,
        )

        # Load processed tools
        file_manager = FileManager(temp_dir)
        all_tools = file_manager.load_processed()

        # Check that tools have quality scores
        scored_tools = [t for t in all_tools if t.quality_score is not None]
        assert len(scored_tools) > 0

        # Check that scores are in valid range
        for tool in scored_tools:
            assert 0 <= tool.quality_score <= 100

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_with_limit(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test pipeline with scrape limit."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools[:2]  # Return only 2 tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline with limit
        run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=False,
            limit=2,
            data_dir=temp_dir,
        )

        # Verify scraper was called with limit
        mock_scraper.scrape.assert_called_once_with(limit=2)

    @patch("src.pipeline.DockerHubScraper")
    def test_pipeline_force_refresh(
        self,
        mock_scraper_class: MagicMock,
        mock_scraper_tools: list[Tool],
        temp_dir: Path,
    ) -> None:
        """Test pipeline with force refresh."""
        # Setup mock scraper
        mock_scraper = MagicMock()
        mock_scraper.scrape.return_value = mock_scraper_tools
        mock_scraper_class.return_value = mock_scraper

        # Run pipeline with force refresh
        run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            force_refresh=True,
            limit=None,
            data_dir=temp_dir,
        )

        # This should bypass classifier/keyword caches
        # The main effect is on classifier.apply_classification and keyword_assigner.apply_keywords
        # which receive force=True parameter


class TestLoadProcessedTools:
    """Tests for load_processed_tools function."""

    def test_load_processed_tools_empty(self, temp_dir: Path) -> None:
        """Test loading when no processed tools exist."""
        tools = load_processed_tools(data_dir=temp_dir)
        assert tools == []

    def test_load_processed_tools_basic(
        self, temp_dir: Path, sample_tools_for_cli
    ) -> None:
        """Test basic loading of processed tools."""
        # Save some tools
        file_manager = FileManager(temp_dir)
        file_manager.save_processed(sample_tools_for_cli)

        # Load them
        tools = load_processed_tools(data_dir=temp_dir)
        # Should only return VISIBLE tools by default
        assert len(tools) == 3  # experimental is HIDDEN

    def test_load_processed_tools_with_category_filter(
        self, temp_dir: Path, sample_tools_for_cli
    ) -> None:
        """Test loading with category filter."""
        # Save tools
        file_manager = FileManager(temp_dir)
        file_manager.save_processed(sample_tools_for_cli)

        # Load only databases
        tools = load_processed_tools(category="databases", data_dir=temp_dir)
        assert all(t.primary_category == "databases" for t in tools)
        assert len(tools) == 2  # postgres and redis

    def test_load_processed_tools_include_hidden(
        self, temp_dir: Path, sample_tools_for_cli
    ) -> None:
        """Test loading with include_hidden."""
        # Save tools
        file_manager = FileManager(temp_dir)
        file_manager.save_processed(sample_tools_for_cli)

        # Load with hidden
        tools = load_processed_tools(include_hidden=True, data_dir=temp_dir)
        # Should include HIDDEN tools
        assert len(tools) == 4  # All tools including experimental

    def test_load_processed_tools_excludes_excluded(
        self, temp_dir: Path, sample_tools_for_cli
    ) -> None:
        """Test that EXCLUDED tools are never loaded."""
        # Mark one tool as EXCLUDED
        sample_tools_for_cli[0].filter_status.state = FilterState.EXCLUDED

        # Save tools
        file_manager = FileManager(temp_dir)
        file_manager.save_processed(sample_tools_for_cli)

        # Load with include_hidden
        tools = load_processed_tools(include_hidden=True, data_dir=temp_dir)
        # Should NOT include EXCLUDED tool
        assert len(tools) == 3
        assert all(t.id != sample_tools_for_cli[0].id for t in tools)


@pytest.fixture
def sample_tools_for_cli() -> list[Tool]:
    """Create sample tools for testing load_processed_tools."""
    tools = [
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL database",
            primary_category="databases",
            primary_subcategory="relational",
            quality_score=92.0,
            keywords=["database", "sql"],
        ),
        Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis cache",
            primary_category="databases",
            primary_subcategory="cache",
            quality_score=88.0,
            keywords=["cache", "keyvalue"],
        ),
        Tool(
            id="docker_hub:library/nginx",
            name="nginx",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/nginx",
            description="NGINX web server",
            primary_category="web",
            primary_subcategory="server",
            quality_score=95.0,
            keywords=["webserver"],
        ),
        Tool(
            id="docker_hub:user/experimental",
            name="experimental-tool",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/experimental",
            description="Experimental tool",
            primary_category="development",
            primary_subcategory="testing",
            lifecycle=Lifecycle.EXPERIMENTAL,
            quality_score=65.0,
            keywords=["testing"],
        ),
    ]

    # Mark experimental as HIDDEN
    tools[3].filter_status.state = FilterState.HIDDEN

    return tools


def test_pipeline_error_handling_invalid_source() -> None:
    """Test pipeline error handling for invalid source."""
    with pytest.raises(ValueError, match="is not a valid SourceType"):
        run_scrape_pipeline(source="invalid_source")
