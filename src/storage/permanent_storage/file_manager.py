"""File-based storage layer for tool data persistence.

Provides operations for:
- Raw scrape data (immutable, timestamped)
- Processed tool catalog (unified, regenerable)
- Computed scores (versioned)
- Statistics (global and per-category)
- Generic key-value storage by category
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.consts import DEFAULT_DATA_DIR
from src.models.model_stats import CategoryStats, GlobalStats
from src.models.model_storage import RawScrapeFile, ScoresFile
from src.models.model_tool import SourceType, Tool
from src.storage.permanent_storage.base import PermanentStorage

logger = logging.getLogger(__name__)


class FileManager(PermanentStorage):
    """File-based storage manager for tool data.

    Directory structure:
        data/
        ├── raw/{source}/{date}_scrape.json    # Immutable scrape results
        ├── raw/{source}/latest.json           # Most recent scrape
        ├── processed/tools.json               # Unified tool catalog
        ├── processed/scores.json              # Computed quality scores
        ├── processed/stats/global_stats.json  # Cross-category statistics
        ├── processed/stats/category_stats.json# Per-category statistics
        └── overrides.json                     # Manual classification overrides
    """

    def __init__(self, data_dir: Path | str = DEFAULT_DATA_DIR):
        """Initialize FileManager with data directory.

        Args:
            data_dir: Root directory for all data files.
        """
        self.data_dir = Path(data_dir)
        self._raw_dir = self.data_dir / "raw"
        self._processed_dir = self.data_dir / "processed"
        self._stats_dir = self._processed_dir / "stats"
        self._cache_dir = self.data_dir / "cache"

    def _ensure_dirs(self, *dirs: Path) -> None:
        """Create directories if they don't exist."""
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _source_dir(self, source: SourceType | str) -> Path:
        """Get directory for a specific source."""
        source_name = source.value if isinstance(source, SourceType) else source
        return self._raw_dir / source_name

    # === RAW SCRAPE OPERATIONS ===

    def save_raw(self, source: SourceType | str, tools: list[Tool]) -> Path:
        """Save raw scrape data with timestamp.

        Raw data is immutable once written. Creates timestamped file
        and updates latest.json to point to it.

        Args:
            source: Source platform (docker_hub, github, helm).
            tools: List of scraped tools.

        Returns:
            Path to the saved scrape file.
        """
        source_dir = self._source_dir(source)
        self._ensure_dirs(source_dir)

        source_type = source if isinstance(source, SourceType) else SourceType(source)
        now = datetime.now(UTC)
        date_str = now.strftime("%Y%m%d_%H%M%S")

        scrape_file = RawScrapeFile(
            scraped_at=now,
            source=source_type,
            tools=tools,
        )

        # Save timestamped file
        filename = f"{date_str}_scrape.json"
        scrape_path = source_dir / filename
        scrape_path.write_text(
            scrape_file.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info(f"Saved raw scrape: {scrape_path} ({len(tools)} tools)")

        # Update latest.json
        latest_path = source_dir / "latest.json"
        latest_path.write_text(
            scrape_file.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.debug(f"Updated latest.json for {source_type.value}")

        return scrape_path

    def load_raw(
        self,
        source: SourceType | str,
        date: str | None = None,
    ) -> RawScrapeFile | None:
        """Load raw scrape data.

        Args:
            source: Source platform.
            date: Optional date string (YYYYMMDD_HHMMSS). If None, loads latest.

        Returns:
            RawScrapeFile if found, None otherwise.
        """
        source_dir = self._source_dir(source)

        if date:
            path = source_dir / f"{date}_scrape.json"
        else:
            path = source_dir / "latest.json"

        if not path.exists():
            logger.warning(f"Raw scrape not found: {path}")
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        return RawScrapeFile.model_validate(data)

    def list_raw_scrapes(self, source: SourceType | str) -> list[str]:
        """List available raw scrape dates for a source.

        Args:
            source: Source platform.

        Returns:
            List of date strings (YYYYMMDD_HHMMSS), sorted descending.
        """
        source_dir = self._source_dir(source)
        if not source_dir.exists():
            return []

        dates = []
        for f in source_dir.glob("*_scrape.json"):
            date_part = f.stem.replace("_scrape", "")
            dates.append(date_part)

        return sorted(dates, reverse=True)

    # === PROCESSED DATA OPERATIONS ===

    def save_processed(self, tools: list[Tool]) -> Path:
        """Save unified tool catalog.

        This is the merged result from all sources after filtering
        and categorization.

        Args:
            tools: List of processed tools.

        Returns:
            Path to the saved file.
        """
        self._ensure_dirs(self._processed_dir)
        path = self._processed_dir / "tools.json"

        data = {
            "version": "1.0",
            "updated_at": datetime.now(UTC).isoformat(),
            "total_tools": len(tools),
            "tools": [tool.model_dump(mode="json") for tool in tools],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Saved processed tools: {path} ({len(tools)} tools)")
        return path

    def load_processed(self) -> list[Tool] | None:
        """Load unified tool catalog.

        Returns:
            List of tools if found, None otherwise.
        """
        path = self._processed_dir / "tools.json"
        if not path.exists():
            logger.warning(f"Processed tools not found: {path}")
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        return [Tool.model_validate(t) for t in data.get("tools", [])]

    # === SCORES OPERATIONS ===

    def save_scores(self, scores_file: ScoresFile) -> Path:
        """Save computed quality scores.

        Args:
            scores_file: ScoresFile containing all tool scores.

        Returns:
            Path to the saved file.
        """
        self._ensure_dirs(self._processed_dir)
        path = self._processed_dir / "scores.json"

        path.write_text(
            scores_file.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info(f"Saved scores: {path} ({len(scores_file.scores)} tools)")
        return path

    def load_scores(self) -> ScoresFile | None:
        """Load computed quality scores.

        Returns:
            ScoresFile if found, None otherwise.
        """
        path = self._processed_dir / "scores.json"
        if not path.exists():
            logger.warning(f"Scores not found: {path}")
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        return ScoresFile.model_validate(data)

    # === STATISTICS OPERATIONS ===

    def save_stats(
        self,
        global_stats: GlobalStats,
        category_stats: dict[str, CategoryStats],
    ) -> tuple[Path, Path]:
        """Save statistics for scoring normalization.

        Args:
            global_stats: Cross-category statistics.
            category_stats: Per-category statistics keyed by "category/subcategory".

        Returns:
            Tuple of paths (global_stats.json, category_stats.json).
        """
        self._ensure_dirs(self._stats_dir)

        global_path = self._stats_dir / "global_stats.json"
        global_path.write_text(
            global_stats.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info(f"Saved global stats: {global_path}")

        category_path = self._stats_dir / "category_stats.json"
        category_data = {
            "version": "1.0",
            "updated_at": datetime.now(UTC).isoformat(),
            "categories": {k: v.model_dump(mode="json") for k, v in category_stats.items()},
        }
        category_path.write_text(
            json.dumps(category_data, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Saved category stats: {category_path} ({len(category_stats)} categories)")

        return global_path, category_path

    def load_stats(self) -> tuple[GlobalStats | None, dict[str, CategoryStats] | None]:
        """Load statistics for scoring normalization.

        Returns:
            Tuple of (GlobalStats, dict[str, CategoryStats]) or (None, None) if not found.
        """
        global_path = self._stats_dir / "global_stats.json"
        category_path = self._stats_dir / "category_stats.json"

        global_stats = None
        category_stats = None

        if global_path.exists():
            data = json.loads(global_path.read_text(encoding="utf-8"))
            global_stats = GlobalStats.model_validate(data)
        else:
            logger.warning(f"Global stats not found: {global_path}")

        if category_path.exists():
            data = json.loads(category_path.read_text(encoding="utf-8"))
            category_stats = {
                k: CategoryStats.model_validate(v) for k, v in data.get("categories", {}).items()
            }
        else:
            logger.warning(f"Category stats not found: {category_path}")

        return global_stats, category_stats

    # === OVERRIDES OPERATIONS ===

    def load_overrides(self) -> dict[str, Any]:
        """Load manual classification overrides.

        Returns:
            Dict of overrides keyed by tool ID, or empty dict if not found.
        """
        path = self.data_dir / "overrides.json"
        if not path.exists():
            return {}

        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("overrides", {})

    def save_overrides(self, overrides: dict[str, Any]) -> Path:
        """Save manual classification overrides.

        Args:
            overrides: Dict of overrides keyed by tool ID.

        Returns:
            Path to the saved file.
        """
        path = self.data_dir / "overrides.json"
        self._ensure_dirs(self.data_dir)

        data = {
            "version": "1.0",
            "updated_at": datetime.now(UTC).isoformat(),
            "overrides": overrides,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Saved overrides: {path} ({len(overrides)} entries)")
        return path

    # === UTILITY METHODS ===

    def get_data_summary(self) -> dict[str, Any]:
        """Get summary of stored data.

        Returns:
            Dict with counts and metadata about stored data.
        """
        summary: dict[str, Any] = {
            "raw_scrapes": {},
            "processed": {"exists": False, "tool_count": 0},
            "scores": {"exists": False, "tool_count": 0},
            "stats": {"global_exists": False, "category_count": 0},
            "overrides": {"exists": False, "count": 0},
        }

        # Raw scrapes per source
        for source in SourceType:
            scrapes = self.list_raw_scrapes(source)
            if scrapes:
                summary["raw_scrapes"][source.value] = {
                    "count": len(scrapes),
                    "latest": scrapes[0] if scrapes else None,
                }

        # Processed tools
        processed_path = self._processed_dir / "tools.json"
        if processed_path.exists():
            data = json.loads(processed_path.read_text(encoding="utf-8"))
            summary["processed"] = {
                "exists": True,
                "tool_count": data.get("total_tools", 0),
                "updated_at": data.get("updated_at"),
            }

        # Scores
        scores_path = self._processed_dir / "scores.json"
        if scores_path.exists():
            data = json.loads(scores_path.read_text(encoding="utf-8"))
            summary["scores"] = {
                "exists": True,
                "tool_count": len(data.get("scores", {})),
                "computed_at": data.get("computed_at"),
            }

        # Stats
        global_path = self._stats_dir / "global_stats.json"
        category_path = self._stats_dir / "category_stats.json"
        summary["stats"]["global_exists"] = global_path.exists()
        if category_path.exists():
            data = json.loads(category_path.read_text(encoding="utf-8"))
            summary["stats"]["category_count"] = len(data.get("categories", {}))

        # Overrides
        overrides_path = self.data_dir / "overrides.json"
        if overrides_path.exists():
            data = json.loads(overrides_path.read_text(encoding="utf-8"))
            summary["overrides"] = {
                "exists": True,
                "count": len(data.get("overrides", {})),
            }

        return summary

    # === GENERIC PERMANENT STORAGE OPERATIONS ===
    # These implement the PermanentStorage abstract base class interface

    def save(self, key: str, data: Any, category: str) -> Path:
        """Save data to permanent storage.

        Args:
            key: Unique identifier for the data within the category.
            data: Data to store (must be JSON-serializable).
            category: Category/namespace for organizing data.

        Returns:
            Path where data was stored.
        """
        category_dir = self.data_dir / category
        self._ensure_dirs(category_dir)

        path = category_dir / f"{key}.json"
        content = {
            "key": key,
            "category": category,
            "saved_at": datetime.now(UTC).isoformat(),
            "data": data,
        }
        path.write_text(json.dumps(content, indent=2, default=str), encoding="utf-8")
        logger.debug(f"Saved {key} in category={category}")
        return path

    def load(self, key: str, category: str) -> Any | None:
        """Load data from permanent storage.

        Args:
            key: Unique identifier for the data.
            category: Category/namespace to look in.

        Returns:
            Stored data if found, None otherwise.
        """
        path = self.data_dir / category / f"{key}.json"
        if not path.exists():
            return None

        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            return content.get("data")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load {key} from {category}: {e}")
            return None

    def delete(self, key: str, category: str) -> bool:
        """Delete data from permanent storage.

        Args:
            key: Unique identifier for the data.
            category: Category/namespace to look in.

        Returns:
            True if data was deleted, False if not found.
        """
        path = self.data_dir / category / f"{key}.json"
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted {key} from category={category}")
            return True
        return False

    def exists(self, key: str, category: str) -> bool:
        """Check if data exists in permanent storage.

        Args:
            key: Unique identifier for the data.
            category: Category/namespace to look in.

        Returns:
            True if data exists, False otherwise.
        """
        path = self.data_dir / category / f"{key}.json"
        return path.exists()

    def list_keys(self, category: str) -> list[str]:
        """List all keys in a category.

        Args:
            category: Category/namespace to list keys from.

        Returns:
            List of keys in the category.
        """
        category_dir = self.data_dir / category
        if not category_dir.exists():
            return []

        keys = []
        for path in category_dir.glob("*.json"):
            keys.append(path.stem)
        return sorted(keys)


def main() -> None:
    """Example usage of FileManager."""
    import tempfile

    logging.basicConfig(level=logging.INFO)

    # Use temporary directory for example
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = FileManager(data_dir=tmpdir)

        print("=== FileManager Example ===\n")

        # Create sample tools
        sample_tools = [
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

        # Save raw scrape
        print("1. Saving raw scrape...")
        raw_path = storage.save_raw(SourceType.DOCKER_HUB, sample_tools)
        print(f"   Saved to: {raw_path}")

        # List available scrapes
        print("\n2. Listing raw scrapes...")
        scrapes = storage.list_raw_scrapes(SourceType.DOCKER_HUB)
        print(f"   Available scrapes: {scrapes}")

        # Load raw scrape
        print("\n3. Loading raw scrape...")
        loaded_raw = storage.load_raw(SourceType.DOCKER_HUB)
        if loaded_raw:
            print(f"   Loaded {len(loaded_raw.tools)} tools from {loaded_raw.source}")

        # Save processed data
        print("\n4. Saving processed data...")
        processed_path = storage.save_processed(sample_tools)
        print(f"   Saved to: {processed_path}")

        # Load processed data
        print("\n5. Loading processed data...")
        loaded_processed = storage.load_processed()
        if loaded_processed:
            print(f"   Loaded {len(loaded_processed)} processed tools")

        # Test generic save/load (PermanentStorage interface)
        print("\n6. Testing generic PermanentStorage interface...")
        storage.save("config_v1", {"setting": "value", "enabled": True}, "configs")
        print("   Saved config_v1 to 'configs' category")

        loaded_config = storage.load("config_v1", "configs")
        print(f"   Loaded config: {loaded_config}")

        print(f"   config_v1 exists: {storage.exists('config_v1', 'configs')}")
        print(f"   Keys in 'configs': {storage.list_keys('configs')}")

        storage.delete("config_v1", "configs")
        print(f"   config_v1 exists after delete: {storage.exists('config_v1', 'configs')}")

        # Get data summary
        print("\n7. Data summary...")
        summary = storage.get_data_summary()
        print(f"   {json.dumps(summary, indent=2, default=str)}")


if __name__ == "__main__":
    main()
