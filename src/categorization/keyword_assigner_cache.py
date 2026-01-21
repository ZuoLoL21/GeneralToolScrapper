"""Keyword assignment cache for storing keyword assignment results.

Uses the centralized FileCache for storage while maintaining
domain-specific API.
"""

import logging
from pathlib import Path

from src.models.model_classification import KeywordAssignmentCacheEntry
from src.storage.cache.file_caching import FileCache

logger = logging.getLogger(__name__)

# Category name for keyword assignment cache entries
KEYWORD_ASSIGNMENT_CATEGORY = "keyword_assignments"


class KeywordAssignmentCache:
    """Keyword assignment cache keyed by canonical name.

    Uses FileCache internally for storage while providing a
    domain-specific API for keyword assignment entries.
    """

    def __init__(self, cache_path: Path | None = None, cache: FileCache | None = None):
        """Initialize KeywordAssignmentCache.

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

    def get(self, canonical_name: str) -> KeywordAssignmentCacheEntry | None:
        """Get cached keyword assignment by canonical name.

        Args:
            canonical_name: The canonical name of the tool.

        Returns:
            KeywordAssignmentCacheEntry if found, None otherwise.
        """
        data = self._cache.get(canonical_name, KEYWORD_ASSIGNMENT_CATEGORY)
        if data is None:
            return None

        try:
            return KeywordAssignmentCacheEntry.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to parse cached keyword assignment for {canonical_name}: {e}")
            return None

    def set(self, canonical_name: str, entry: KeywordAssignmentCacheEntry) -> None:
        """Cache a keyword assignment.

        Args:
            canonical_name: The canonical name of the tool.
            entry: The keyword assignment entry to cache.
        """
        self._cache.put(
            canonical_name,
            entry.model_dump(mode="json"),
            KEYWORD_ASSIGNMENT_CATEGORY,
        )

    def invalidate(self, canonical_name: str) -> None:
        """Remove a cached keyword assignment.

        Args:
            canonical_name: The canonical name of the tool to invalidate.
        """
        self._cache.delete(canonical_name, KEYWORD_ASSIGNMENT_CATEGORY)

    def clear(self) -> None:
        """Clear all cached keyword assignments."""
        self._cache.clear(KEYWORD_ASSIGNMENT_CATEGORY)

    def list_cached(self) -> list[str]:
        """List all cached canonical names.

        Returns:
            List of canonical names with cached keyword assignments.
        """
        return self._cache.list_keys(KEYWORD_ASSIGNMENT_CATEGORY)

    def get_all_entries(self) -> list[tuple[str, KeywordAssignmentCacheEntry]]:
        """Get all cached keyword assignment entries.

        Returns:
            List of (canonical_name, entry) tuples for all cached entries.
        """
        results = []
        for key in self._cache.list_keys(KEYWORD_ASSIGNMENT_CATEGORY):
            entry = self.get(key)
            if entry:
                results.append((key, entry))
        return results

    def get_entries_by_source(self, source: str) -> list[tuple[str, KeywordAssignmentCacheEntry]]:
        """Get all cached entries with a specific source.

        Args:
            source: The source to filter by (e.g., "fallback", "heuristic", "override").

        Returns:
            List of (canonical_name, entry) tuples matching the source.
        """
        results = []
        for key in self._cache.list_keys(KEYWORD_ASSIGNMENT_CATEGORY):
            entry = self.get(key)
            if entry and entry.source == source:
                results.append((key, entry))
        return results


def main() -> None:
    """Example usage of KeywordAssignmentCache."""
    from datetime import UTC, datetime

    from src.models.model_classification import KeywordAssignment

    logging.basicConfig(level=logging.DEBUG)

    cache = KeywordAssignmentCache()

    print("=== KeywordAssignmentCache Example ===\n")

    # Create a sample keyword assignment entry
    assignment = KeywordAssignment(
        keywords=["cloud-native", "distributed", "containerized", "grpc"],
    )
    entry = KeywordAssignmentCacheEntry(
        assignment=assignment,
        assigned_at=datetime.now(UTC),
        source="heuristic",
    )

    # Cache it
    print("1. Caching keyword assignment for 'postgres'...")
    cache.set("postgres", entry)

    # Retrieve it
    print("\n2. Retrieving cached keyword assignment...")
    cached = cache.get("postgres")
    if cached:
        print(f"   Keywords: {', '.join(cached.assignment.keywords)}")
        print(f"   Source: {cached.source}")
        print(f"   Assigned at: {cached.assigned_at}")

    # List cached entries
    print("\n3. Listing cached entries...")
    entries = cache.list_cached()
    print(f"   Cached: {entries}")

    # Get all entries
    print("\n4. Getting all entries...")
    all_entries = cache.get_all_entries()
    for name, entry in all_entries:
        print(f"   {name}: {len(entry.assignment.keywords)} keywords")

    # Invalidate
    print("\n5. Invalidating 'postgres'...")
    cache.invalidate("postgres")
    print(f"   After invalidation: {cache.get('postgres')}")


if __name__ == "__main__":
    main()
