"""Tests for file-based storage manager."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.models.model_eval import ScoreWeights
from src.models.model_stats import CategoryStats, DistributionStats, GlobalStats
from src.models.model_storage import RawScrapeFile, ScoresFile, ToolScore
from src.models.model_tool import ScoreBreakdown, SourceType, Tool
from src.storage.permanent_storage.file_manager import FileManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_manager(temp_dir: Path) -> FileManager:
    """Create a FileManager with temporary directory."""
    return FileManager(data_dir=temp_dir)


@pytest.fixture
def sample_tools() -> list[Tool]:
    """Create sample tools for testing."""
    return [
        Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL database",
        ),
        Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis key-value store",
        ),
    ]


class TestFileManager:
    """Tests for FileManager class."""

    def test_save_raw(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test saving raw scrape data."""
        path = file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)

        # Check file was created
        assert path.exists()
        assert path.parent.name == "docker_hub"

        # Check latest.json was created
        latest_path = path.parent / "latest.json"
        assert latest_path.exists()

        # Verify content
        scrape_file = RawScrapeFile.model_validate_json(path.read_text())
        assert scrape_file.source == SourceType.DOCKER_HUB
        assert len(scrape_file.tools) == 2

    def test_load_raw_latest(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test loading latest raw scrape."""
        # Save first
        file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)

        # Load latest
        scrape_file = file_manager.load_raw(SourceType.DOCKER_HUB)
        assert scrape_file is not None
        assert scrape_file.source == SourceType.DOCKER_HUB
        assert len(scrape_file.tools) == 2

    def test_load_raw_specific_date(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test loading raw scrape by date."""
        # Save
        path = file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)

        # Extract date from filename
        date_str = path.stem.replace("_scrape", "")

        # Load by date
        scrape_file = file_manager.load_raw(SourceType.DOCKER_HUB, date=date_str)
        assert scrape_file is not None
        assert len(scrape_file.tools) == 2

    def test_load_raw_nonexistent(self, file_manager: FileManager) -> None:
        """Test loading nonexistent raw scrape."""
        scrape_file = file_manager.load_raw(SourceType.DOCKER_HUB)
        assert scrape_file is None

    def test_list_raw_scrapes(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test listing available raw scrapes."""
        # Initially empty
        scrapes = file_manager.list_raw_scrapes(SourceType.DOCKER_HUB)
        assert len(scrapes) == 0

        # Save one
        file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)
        scrapes = file_manager.list_raw_scrapes(SourceType.DOCKER_HUB)
        assert len(scrapes) == 1

        # Save another (simulate later scrape)
        import time

        time.sleep(1.0)  # Ensure different timestamp (1 second should be enough)
        file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)
        scrapes = file_manager.list_raw_scrapes(SourceType.DOCKER_HUB)
        assert len(scrapes) == 2

        # Should be sorted descending (newest first)
        assert scrapes[0] > scrapes[1]

    def test_save_processed(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test saving processed tools."""
        path = file_manager.save_processed(sample_tools)

        assert path.exists()
        assert path.name == "tools.json"

        # Verify content
        data = json.loads(path.read_text())
        assert data["version"] == "1.0"
        assert data["total_tools"] == 2
        assert len(data["tools"]) == 2

    def test_load_processed(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test loading processed tools."""
        # Save first
        file_manager.save_processed(sample_tools)

        # Load
        tools = file_manager.load_processed()
        assert tools is not None
        assert len(tools) == 2
        assert all(isinstance(t, Tool) for t in tools)

    def test_load_processed_nonexistent(self, file_manager: FileManager) -> None:
        """Test loading nonexistent processed tools."""
        tools = file_manager.load_processed()
        assert tools is None

    def test_save_scores(self, file_manager: FileManager) -> None:
        """Test saving scores."""
        scores_file = ScoresFile(
            version="1.0",
            computed_at=datetime.now(UTC),
            score_version="test_v1",
            weights=ScoreWeights(),
            scores={
                "docker_hub:library/postgres": ToolScore(
                    quality_score=85.0,
                    breakdown=ScoreBreakdown(
                        popularity=80.0,
                        security=90.0,
                        maintenance=85.0,
                        trust=95.0,
                    ),
                )
            },
        )

        path = file_manager.save_scores(scores_file)
        assert path.exists()
        assert path.name == "scores.json"

        # Verify content
        loaded = ScoresFile.model_validate_json(path.read_text())
        assert loaded.version == "1.0"
        assert len(loaded.scores) == 1

    def test_load_scores(self, file_manager: FileManager) -> None:
        """Test loading scores."""
        # Save first
        scores_file = ScoresFile(
            version="1.0",
            computed_at=datetime.now(UTC),
            score_version="test_v1",
            weights=ScoreWeights(),
            scores={},
        )
        file_manager.save_scores(scores_file)

        # Load
        loaded = file_manager.load_scores()
        assert loaded is not None
        assert isinstance(loaded, ScoresFile)

    def test_load_scores_nonexistent(self, file_manager: FileManager) -> None:
        """Test loading nonexistent scores."""
        scores = file_manager.load_scores()
        assert scores is None

    def test_save_stats(self, file_manager: FileManager, sample_stats) -> None:
        """Test saving statistics."""
        global_stats, category_stats = sample_stats

        global_path, category_path = file_manager.save_stats(
            global_stats, category_stats
        )

        assert global_path.exists()
        assert category_path.exists()

        # Verify global stats
        loaded_global = GlobalStats.model_validate_json(global_path.read_text())
        assert loaded_global.total_tools == global_stats.total_tools

        # Verify category stats
        data = json.loads(category_path.read_text())
        assert len(data["categories"]) == len(category_stats)

    def test_load_stats(self, file_manager: FileManager, sample_stats) -> None:
        """Test loading statistics."""
        global_stats, category_stats = sample_stats

        # Save first
        file_manager.save_stats(global_stats, category_stats)

        # Load
        loaded_global, loaded_category = file_manager.load_stats()
        assert loaded_global is not None
        assert loaded_category is not None
        assert isinstance(loaded_global, GlobalStats)
        assert isinstance(loaded_category, dict)
        assert len(loaded_category) == len(category_stats)

    def test_load_stats_nonexistent(self, file_manager: FileManager) -> None:
        """Test loading nonexistent stats."""
        global_stats, category_stats = file_manager.load_stats()
        assert global_stats is None
        assert category_stats is None

    def test_save_overrides(self, file_manager: FileManager) -> None:
        """Test saving overrides."""
        overrides = {
            "docker_hub:user/tool": {
                "primary_category": "databases",
                "reason": "Test override",
            }
        }

        path = file_manager.save_overrides(overrides)
        assert path.exists()
        assert path.name == "overrides.json"

        # Verify content
        data = json.loads(path.read_text())
        assert len(data["overrides"]) == 1

    def test_load_overrides(self, file_manager: FileManager) -> None:
        """Test loading overrides."""
        overrides = {"tool1": {"key": "value"}}

        # Save first
        file_manager.save_overrides(overrides)

        # Load
        loaded = file_manager.load_overrides()
        assert loaded == overrides

    def test_load_overrides_nonexistent(self, file_manager: FileManager) -> None:
        """Test loading nonexistent overrides."""
        overrides = file_manager.load_overrides()
        assert overrides == {}

    def test_generic_save_load(self, file_manager: FileManager) -> None:
        """Test generic save/load interface."""
        data = {"setting": "value", "enabled": True}

        # Save
        path = file_manager.save("config_v1", data, "configs")
        assert path.exists()

        # Load
        loaded = file_manager.load("config_v1", "configs")
        assert loaded == data

        # Exists
        assert file_manager.exists("config_v1", "configs")
        assert not file_manager.exists("nonexistent", "configs")

        # List keys
        keys = file_manager.list_keys("configs")
        assert "config_v1" in keys

        # Delete
        deleted = file_manager.delete("config_v1", "configs")
        assert deleted
        assert not file_manager.exists("config_v1", "configs")

        # Delete nonexistent
        deleted = file_manager.delete("nonexistent", "configs")
        assert not deleted

    def test_generic_load_nonexistent(self, file_manager: FileManager) -> None:
        """Test loading nonexistent generic data."""
        loaded = file_manager.load("nonexistent", "category")
        assert loaded is None

    def test_list_keys_empty_category(self, file_manager: FileManager) -> None:
        """Test listing keys in nonexistent category."""
        keys = file_manager.list_keys("nonexistent_category")
        assert keys == []

    def test_get_data_summary_empty(self, file_manager: FileManager) -> None:
        """Test data summary with no data."""
        summary = file_manager.get_data_summary()
        assert "raw_scrapes" in summary
        assert "processed" in summary
        assert "scores" in summary
        assert "stats" in summary
        assert "overrides" in summary

        assert summary["processed"]["exists"] is False
        assert summary["scores"]["exists"] is False

    def test_get_data_summary_with_data(
        self, file_manager: FileManager, sample_tools: list[Tool], sample_stats
    ) -> None:
        """Test data summary with data."""
        # Add some data
        file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)
        file_manager.save_processed(sample_tools)

        global_stats, category_stats = sample_stats
        file_manager.save_stats(global_stats, category_stats)

        summary = file_manager.get_data_summary()

        # Check raw scrapes
        assert "docker_hub" in summary["raw_scrapes"]
        assert summary["raw_scrapes"]["docker_hub"]["count"] == 1

        # Check processed
        assert summary["processed"]["exists"] is True
        assert summary["processed"]["tool_count"] == 2

        # Check stats
        assert summary["stats"]["global_exists"] is True
        assert summary["stats"]["category_count"] == len(category_stats)

    def test_source_dir_with_enum(self, file_manager: FileManager) -> None:
        """Test _source_dir with SourceType enum."""
        source_dir = file_manager._source_dir(SourceType.DOCKER_HUB)
        assert source_dir.name == "docker_hub"

    def test_source_dir_with_string(self, file_manager: FileManager) -> None:
        """Test _source_dir with string."""
        source_dir = file_manager._source_dir("github")
        assert source_dir.name == "github"

    def test_save_raw_with_string_source(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test save_raw with string source."""
        path = file_manager.save_raw("docker_hub", sample_tools)
        assert path.exists()

        # Verify source type is correctly converted
        scrape_file = RawScrapeFile.model_validate_json(path.read_text())
        assert scrape_file.source == SourceType.DOCKER_HUB

    def test_multiple_sources(
        self, file_manager: FileManager, sample_tools: list[Tool]
    ) -> None:
        """Test saving data from multiple sources."""
        # Save Docker Hub data
        file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)

        # Save GitHub data
        github_tools = [
            Tool(
                id="github:postgres/postgres",
                name="postgres",
                source=SourceType.GITHUB,
                source_url="https://github.com/postgres/postgres",
                description="PostgreSQL source code",
            )
        ]
        file_manager.save_raw(SourceType.GITHUB, github_tools)

        # Verify both sources exist
        docker_scrapes = file_manager.list_raw_scrapes(SourceType.DOCKER_HUB)
        github_scrapes = file_manager.list_raw_scrapes(SourceType.GITHUB)

        assert len(docker_scrapes) == 1
        assert len(github_scrapes) == 1

    def test_directory_creation(self, temp_dir: Path) -> None:
        """Test that FileManager creates necessary directories."""
        # Create FileManager but don't save anything yet
        file_manager = FileManager(data_dir=temp_dir)

        # Directories shouldn't exist yet
        assert not (temp_dir / "raw").exists()
        assert not (temp_dir / "processed").exists()

        # Save data - should create directories
        sample_tools = [
            Tool(
                id="docker_hub:library/test",
                name="test",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/_/test",
            )
        ]
        file_manager.save_raw(SourceType.DOCKER_HUB, sample_tools)

        # Now raw/docker_hub should exist
        assert (temp_dir / "raw" / "docker_hub").exists()

    def test_invalid_json_handling(
        self, file_manager: FileManager, temp_dir: Path
    ) -> None:
        """Test handling of invalid JSON in generic load."""
        # Create invalid JSON file
        category_dir = temp_dir / "test_category"
        category_dir.mkdir(parents=True, exist_ok=True)
        invalid_path = category_dir / "invalid.json"
        invalid_path.write_text("{ invalid json }")

        # Should return None for invalid JSON
        loaded = file_manager.load("invalid", "test_category")
        assert loaded is None


def test_file_manager_default_dir() -> None:
    """Test FileManager with default directory."""
    from src.consts import DEFAULT_DATA_DIR

    file_manager = FileManager()
    assert file_manager.data_dir == DEFAULT_DATA_DIR
