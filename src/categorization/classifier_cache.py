"""Classification cache for storing LLM classification results.

Uses the centralized FileCache for storage while maintaining
backward-compatible API.
"""

import logging
from pathlib import Path

from src.models.model_classification import ClassificationCacheEntry
from src.storage.cache.file_caching import FileCache

logger = logging.getLogger(__name__)

# Category name for classification cache entries
CLASSIFICATION_CATEGORY = "classifications"


class ClassificationCache:
    """Classification cache keyed by canonical name.

    Uses FileCache internally for storage while providing a
    domain-specific API for classification entries.
    """

    def __init__(self, cache_path: Path | None = None, cache: FileCache | None = None):
        """Initialize ClassificationCache.

        Args:
            cache_path: Path to cache directory. Used to create FileCache if cache not provided.
                       For backward compatibility with existing code.
            cache: Optional FileCache instance to use. If provided, cache_path is ignored.
        """
        if cache is not None:
            self._cache = cache
        elif cache_path is not None:
            # For backward compatibility: cache_path was a file path, now we use directory
            cache_dir = cache_path.parent if cache_path.suffix == ".json" else cache_path
            self._cache = FileCache(cache_dir=cache_dir)
        else:
            # Use FileCache defaults for cache_dir and ttl
            self._cache = FileCache()

    def get(self, canonical_name: str) -> ClassificationCacheEntry | None:
        """Get cached classification by canonical name.

        Args:
            canonical_name: The canonical name of the tool.

        Returns:
            ClassificationCacheEntry if found, None otherwise.
        """
        data = self._cache.get(canonical_name, CLASSIFICATION_CATEGORY)
        if data is None:
            return None

        try:
            return ClassificationCacheEntry.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to parse cached classification for {canonical_name}: {e}")
            return None

    def set(self, canonical_name: str, entry: ClassificationCacheEntry) -> None:
        """Cache a classification.

        Args:
            canonical_name: The canonical name of the tool.
            entry: The classification entry to cache.
        """
        self._cache.put(
            canonical_name,
            entry.model_dump(mode="json"),
            CLASSIFICATION_CATEGORY,
        )

    def invalidate(self, canonical_name: str) -> None:
        """Remove a cached classification.

        Args:
            canonical_name: The canonical name of the tool to invalidate.
        """
        self._cache.delete(canonical_name, CLASSIFICATION_CATEGORY)

    def clear(self) -> None:
        """Clear all cached classifications."""
        self._cache.clear(CLASSIFICATION_CATEGORY)

    def list_cached(self) -> list[str]:
        """List all cached canonical names.

        Returns:
            List of canonical names with cached classifications.
        """
        return self._cache.list_keys(CLASSIFICATION_CATEGORY)

    def get_entries_by_source(self, source: str) -> list[tuple[str, ClassificationCacheEntry]]:
        """Get all cached entries with a specific source.

        Args:
            source: The source to filter by (e.g., "fallback", "heuristic", "override").

        Returns:
            List of (canonical_name, entry) tuples matching the source.
        """
        results = []
        for key in self._cache.list_keys(CLASSIFICATION_CATEGORY):
            entry = self.get(key)
            if entry and entry.source == source:
                results.append((key, entry))
        return results


def main() -> None:
    """Example usage of ClassificationCache."""
    from datetime import UTC, datetime

    from src.models.model_classification import Classification

    logging.basicConfig(level=logging.DEBUG)

    cache = ClassificationCache()

    print("=== ClassificationCache Example ===\n")

    # Create a sample classification entry
    classification = Classification(
        primary_category="databases",
        primary_subcategory="relational",
        secondary_categories=["storage/persistence"],
    )
    entry = ClassificationCacheEntry(
        classification=classification,
        classified_at=datetime.now(UTC),
        source="llm",
    )

    # Cache it
    print("1. Caching classification for 'postgres'...")
    cache.set("postgres", entry)

    # Retrieve it
    print("\n2. Retrieving cached classification...")
    cached = cache.get("postgres")
    if cached:
        print(
            f"   Category: {cached.classification.primary_category}/{cached.classification.primary_subcategory}"
        )
        print(f"   Source: {cached.source}")
        print(f"   Classified at: {cached.classified_at}")

    # List cached entries
    print("\n3. Listing cached entries...")
    entries = cache.list_cached()
    print(f"   Cached: {entries}")

    # Invalidate
    print("\n4. Invalidating 'postgres'...")
    cache.invalidate("postgres")
    print(f"   After invalidation: {cache.get('postgres')}")


if __name__ == "__main__":
    main()
