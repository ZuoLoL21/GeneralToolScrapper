import json
import logging
from datetime import datetime
from pathlib import Path

from src.models.model_classification import (
    ClassificationCacheEntry,
)

logger = logging.getLogger(__name__)


class ClassificationCache:
    """Simple file-based classification cache keyed by canonical name."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self._cache: dict[str, ClassificationCacheEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text())
                for key, entry in data.items():
                    # Parse datetime
                    if "classified_at" in entry:
                        entry["classified_at"] = datetime.fromisoformat(entry["classified_at"])
                    self._cache[key] = ClassificationCacheEntry(**entry)
                logger.debug(f"Loaded {len(self._cache)} cached classifications")
            except Exception as e:
                logger.warning(f"Failed to load classification cache: {e}")
                self._cache = {}

    def _save(self) -> None:
        """Save cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, entry in self._cache.items():
            entry_dict = entry.model_dump()
            entry_dict["classified_at"] = entry.classified_at.isoformat()
            data[key] = entry_dict
        self.cache_path.write_text(json.dumps(data, indent=2))

    def get(self, canonical_name: str) -> ClassificationCacheEntry | None:
        """Get cached classification by canonical name."""
        return self._cache.get(canonical_name)

    def set(self, canonical_name: str, entry: ClassificationCacheEntry) -> None:
        """Cache a classification."""
        self._cache[canonical_name] = entry
        self._save()

    def invalidate(self, canonical_name: str) -> None:
        """Remove a cached classification."""
        if canonical_name in self._cache:
            del self._cache[canonical_name]
            self._save()

    def clear(self) -> None:
        """Clear all cached classifications."""
        self._cache = {}
        if self.cache_path.exists():
            self.cache_path.unlink()
