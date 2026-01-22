"""Tests for CLI interface."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.models.model_tool import FilterState, Lifecycle, SourceType, Tool

runner = CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_tools_for_cli() -> list[Tool]:
    """Create sample tools for CLI testing."""
    tools = [
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL object-relational database system",
            primary_category="databases",
            primary_subcategory="relational",
            quality_score=92.0,
            keywords=["database", "sql", "relational"],
        ),
        Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis in-memory data structure store",
            primary_category="databases",
            primary_subcategory="cache",
            quality_score=88.0,
            keywords=["cache", "keyvalue", "inmemory"],
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
            keywords=["webserver", "proxy", "reverseproxy"],
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
            keywords=["experimental", "testing"],
        ),
    ]

    # Mark experimental tool as HIDDEN
    tools[3].filter_status.state = FilterState.HIDDEN

    return tools


class TestScrapeCLI:
    """Tests for scrape command."""

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_no_source(self, mock_pipeline: MagicMock) -> None:
        """Test scrape command without source."""
        result = runner.invoke(app, ["scrape"])
        assert result.exit_code == 1
        assert "Must specify --source or --all" in result.stdout

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_all_not_implemented(self, mock_pipeline: MagicMock) -> None:
        """Test scrape command with --all flag."""
        result = runner.invoke(app, ["scrape", "--all"])
        assert result.exit_code == 1
        assert "not yet implemented" in result.stdout

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_invalid_source(self, mock_pipeline: MagicMock) -> None:
        """Test scrape command with invalid source."""
        result = runner.invoke(app, ["scrape", "--source", "invalid"])
        assert result.exit_code == 1
        assert "Invalid source" in result.stdout

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_success(
        self, mock_pipeline: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test successful scrape command."""
        # run_scrape_pipeline returns (all_tools, new_tools)
        mock_pipeline.return_value = (sample_tools_for_cli, sample_tools_for_cli)

        result = runner.invoke(app, ["scrape", "--source", "docker_hub"])
        assert result.exit_code == 0
        assert "Pipeline complete" in result.stdout
        assert "Total tools: 4" in result.stdout

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_with_limit(self, mock_pipeline: MagicMock) -> None:
        """Test scrape command with limit."""
        # run_scrape_pipeline returns (all_tools, new_tools)
        mock_pipeline.return_value = ([], [])

        result = runner.invoke(app, ["scrape", "--source", "docker_hub", "--limit", "10"])
        assert result.exit_code == 0

        # Verify limit was passed to pipeline
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args.kwargs
        assert call_kwargs["limit"] == 10

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_with_force_refresh(self, mock_pipeline: MagicMock) -> None:
        """Test scrape command with force refresh."""
        # run_scrape_pipeline returns (all_tools, new_tools)
        mock_pipeline.return_value = ([], [])

        result = runner.invoke(app, ["scrape", "--source", "docker_hub", "--force-refresh"])
        assert result.exit_code == 0

        # Verify force_refresh was passed to pipeline
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args.kwargs
        assert call_kwargs["force_refresh"] is True

    @patch("src.cli.run_scrape_pipeline")
    def test_scrape_error_handling(self, mock_pipeline: MagicMock) -> None:
        """Test scrape command error handling."""
        mock_pipeline.side_effect = Exception("Test error")

        result = runner.invoke(app, ["scrape", "--source", "docker_hub"])
        assert result.exit_code == 1
        assert "Error" in result.stdout


class TestSearchCLI:
    """Tests for search command."""

    @patch("src.cli.load_processed_tools")
    def test_search_no_tools(self, mock_load: MagicMock) -> None:
        """Test search with no tools loaded."""
        mock_load.return_value = []

        result = runner.invoke(app, ["search", "postgres"])
        assert result.exit_code == 0
        assert "No tools found" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_search_basic(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test basic search functionality."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["search", "postgres"])
        assert result.exit_code == 0
        assert "postgres" in result.stdout.lower()
        assert "Search Results" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_search_no_results(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test search with no matching results."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["search", "xyznonexistent"])
        assert result.exit_code == 0
        assert "No results found" in result.stdout or "matches" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_search_with_category_filter(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test search with category filter."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["search", "database", "--category", "databases"])
        assert result.exit_code == 0

        # Verify category was passed to load_processed_tools
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["category"] == "databases"

    @patch("src.cli.load_processed_tools")
    def test_search_with_limit(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test search with result limit."""
        # Create more tools than limit
        mock_load.return_value = sample_tools_for_cli * 10

        result = runner.invoke(app, ["search", "tool", "--limit", "5"])
        assert result.exit_code == 0
        # The table should show at most 5 results

    @patch("src.cli.load_processed_tools")
    def test_search_include_hidden(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test search with include-hidden flag."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["search", "tool", "--include-hidden"])
        assert result.exit_code == 0

        # Verify include_hidden was passed
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["include_hidden"] is True


class TestTopCLI:
    """Tests for top command."""

    @patch("src.cli.load_processed_tools")
    def test_top_no_tools(self, mock_load: MagicMock) -> None:
        """Test top with no tools loaded."""
        mock_load.return_value = []

        result = runner.invoke(app, ["top"])
        assert result.exit_code == 0
        assert "No tools found" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_top_basic(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test basic top command."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["top"])
        assert result.exit_code == 0
        assert "Top" in result.stdout
        # nginx should be first (highest score 95.0)
        assert "nginx" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_top_with_category(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test top with category filter."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["top", "--category", "databases"])
        assert result.exit_code == 0
        assert "databases" in result.stdout

        # Verify category was passed
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["category"] == "databases"

    @patch("src.cli.load_processed_tools")
    def test_top_with_limit(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test top with custom limit."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["top", "--limit", "2"])
        assert result.exit_code == 0
        assert "Top 2" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_top_include_hidden(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool]
    ) -> None:
        """Test top with include-hidden flag."""
        mock_load.return_value = sample_tools_for_cli

        result = runner.invoke(app, ["top", "--include-hidden"])
        assert result.exit_code == 0

        # Verify include_hidden was passed
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["include_hidden"] is True

    @patch("src.cli.load_processed_tools")
    def test_top_no_scored_tools(self, mock_load: MagicMock) -> None:
        """Test top with tools that have no scores."""
        tools = [
            Tool(
                id="docker_hub:library/test",
                name="test",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/_/test",
                quality_score=None,  # No score
            )
        ]
        mock_load.return_value = tools

        result = runner.invoke(app, ["top"])
        assert result.exit_code == 0
        assert "No scored tools found" in result.stdout


class TestExportCLI:
    """Tests for export command."""

    @patch("src.cli.load_processed_tools")
    def test_export_no_tools(self, mock_load: MagicMock, temp_dir: Path) -> None:
        """Test export with no tools."""
        mock_load.return_value = []
        output = temp_dir / "test.json"

        result = runner.invoke(app, ["export", "--output", str(output)])
        assert result.exit_code == 0
        assert "No tools found to export" in result.stdout
        assert not output.exists()

    @patch("src.cli.load_processed_tools")
    def test_export_json(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool], temp_dir: Path
    ) -> None:
        """Test JSON export."""
        mock_load.return_value = sample_tools_for_cli
        output = temp_dir / "test.json"

        result = runner.invoke(app, [
            "export",
            "--format", "json",
            "--output", str(output),
        ])
        assert result.exit_code == 0
        assert "Exported 4 tools" in result.stdout
        assert output.exists()

        # Verify JSON content
        data = json.loads(output.read_text())
        assert len(data) == 4
        assert data[0]["name"] == "postgres"

    @patch("src.cli.load_processed_tools")
    def test_export_csv(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool], temp_dir: Path
    ) -> None:
        """Test CSV export."""
        mock_load.return_value = sample_tools_for_cli
        output = temp_dir / "test.csv"

        result = runner.invoke(app, [
            "export",
            "--format", "csv",
            "--output", str(output),
        ])
        assert result.exit_code == 0
        assert "Exported 4 tools" in result.stdout
        assert output.exists()

        # Verify CSV content
        content = output.read_text()
        assert "id,name,source,category" in content
        assert "postgres" in content
        assert "redis" in content

    @patch("src.cli.load_processed_tools")
    def test_export_invalid_format(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool], temp_dir: Path
    ) -> None:
        """Test export with invalid format."""
        mock_load.return_value = sample_tools_for_cli
        output = temp_dir / "test.xml"

        result = runner.invoke(app, [
            "export",
            "--format", "xml",
            "--output", str(output),
        ])
        assert result.exit_code == 1
        assert "Unsupported format" in result.stdout

    @patch("src.cli.load_processed_tools")
    def test_export_with_category(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool], temp_dir: Path
    ) -> None:
        """Test export with category filter."""
        mock_load.return_value = sample_tools_for_cli
        output = temp_dir / "test.json"

        result = runner.invoke(app, [
            "export",
            "--format", "json",
            "--output", str(output),
            "--category", "databases",
        ])
        assert result.exit_code == 0

        # Verify category was passed
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["category"] == "databases"

    @patch("src.cli.load_processed_tools")
    def test_export_include_hidden(
        self, mock_load: MagicMock, sample_tools_for_cli: list[Tool], temp_dir: Path
    ) -> None:
        """Test export with include-hidden flag."""
        mock_load.return_value = sample_tools_for_cli
        output = temp_dir / "test.json"

        result = runner.invoke(app, [
            "export",
            "--output", str(output),
            "--include-hidden",
        ])
        assert result.exit_code == 0

        # Verify include_hidden was passed
        mock_load.assert_called_once()
        call_kwargs = mock_load.call_args.kwargs
        assert call_kwargs["include_hidden"] is True


class TestCLIHelpers:
    """Tests for CLI helper functions."""

    def test_get_score_color(self) -> None:
        """Test score color helper."""
        from src.cli import _get_score_color

        assert _get_score_color(80.0) == "green"
        assert _get_score_color(60.0) == "yellow"
        assert _get_score_color(40.0) == "red"

    def test_truncate(self) -> None:
        """Test truncate helper."""
        from src.cli import _truncate

        short_text = "short"
        assert _truncate(short_text, 10) == "short"

        long_text = "a" * 100
        truncated = _truncate(long_text, 60)
        assert len(truncated) == 60
        assert truncated.endswith("...")


def test_cli_app_help() -> None:
    """Test CLI app help message."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "GeneralToolScraper" in result.stdout
    assert "scrape" in result.stdout
    assert "search" in result.stdout
    assert "top" in result.stdout
    assert "export" in result.stdout


def test_scrape_command_help() -> None:
    """Test scrape command help."""
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    assert "source" in result.stdout.lower()
    assert "force-refresh" in result.stdout.lower()


def test_search_command_help() -> None:
    """Test search command help."""
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
    assert "query" in result.stdout.lower()
    assert "category" in result.stdout.lower()


def test_top_command_help() -> None:
    """Test top command help."""
    result = runner.invoke(app, ["top", "--help"])
    assert result.exit_code == 0
    assert "category" in result.stdout.lower()
    assert "limit" in result.stdout.lower()


def test_export_command_help() -> None:
    """Test export command help."""
    result = runner.invoke(app, ["export", "--help"])
    assert result.exit_code == 0
    assert "format" in result.stdout.lower()
    assert "output" in result.stdout.lower()
