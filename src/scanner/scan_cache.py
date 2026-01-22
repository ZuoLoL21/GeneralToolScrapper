"""Failed scan caching to prevent repeated scanning of problematic images."""

import logging
from datetime import UTC, datetime

from src.storage.cache.file_caching import FileCache

logger = logging.getLogger(__name__)


class ScanCache:
    """Caches failed scans temporarily to prevent repeated scanning."""

    def __init__(self, cache: FileCache, failed_scan_ttl: int = 3600):
        """Initialize ScanCache.

        Args:
            cache: FileCache instance for storage
            failed_scan_ttl: Time-to-live for failed scans in seconds (default: 1 hour)
        """
        self.cache = cache
        self.failed_scan_ttl = failed_scan_ttl
        self.category = "security_scan_failures"

    def mark_failed(self, tool_id: str, error: str, ttl: int | None = None) -> None:
        """Cache failed scan with custom or default TTL.

        Args:
            tool_id: Tool ID that failed to scan
            error: Error message from the failed scan
            ttl: Custom TTL in seconds (default: use self.failed_scan_ttl)
        """
        cache_ttl = ttl if ttl is not None else self.failed_scan_ttl
        logger.debug(f"Caching failed scan for {tool_id} (TTL: {cache_ttl}s): {error}")
        self.cache.put(
            key=f"failed_{tool_id}",
            value={"error": error, "timestamp": datetime.now(UTC).isoformat()},
            category=self.category,
            ttl=cache_ttl,
        )

    def is_failed(self, tool_id: str) -> bool:
        """Check if tool recently failed scanning.

        Args:
            tool_id: Tool ID to check

        Returns:
            True if tool has a cached failure, False otherwise
        """
        result = self.cache.get(f"failed_{tool_id}", self.category)
        if result:
            logger.debug(f"Found cached failure for {tool_id}")
            return True
        return False

    def get_failure_info(self, tool_id: str) -> dict | None:
        """Get failure information for a tool.

        Args:
            tool_id: Tool ID to get failure info for

        Returns:
            Dictionary with error and timestamp, or None if not found
        """
        return self.cache.get(f"failed_{tool_id}", self.category)

    def clear_failure(self, tool_id: str) -> None:
        """Clear cached failure for a tool.

        Args:
            tool_id: Tool ID to clear failure for
        """
        logger.debug(f"Clearing cached failure for {tool_id}")
        self.cache.delete(f"failed_{tool_id}", self.category)


def main():
    """Example usage of ScanCache."""
    from pathlib import Path
    from src.consts import DEFAULT_DATA_DIR

    # Create cache
    cache_dir = Path(DEFAULT_DATA_DIR) / "cache"
    file_cache = FileCache(cache_dir=cache_dir, default_ttl=0)
    scan_cache = ScanCache(file_cache, failed_scan_ttl=3600)

    # Test marking a failure
    tool_id = "docker_hub:library/test-image"
    error = "Image not found"

    print(f"Marking {tool_id} as failed...")
    scan_cache.mark_failed(tool_id, error)

    # Check if failed
    print(f"Is {tool_id} failed? {scan_cache.is_failed(tool_id)}")

    # Get failure info
    info = scan_cache.get_failure_info(tool_id)
    print(f"Failure info: {info}")

    # Clear failure
    print(f"Clearing failure for {tool_id}...")
    scan_cache.clear_failure(tool_id)

    # Check again
    print(f"Is {tool_id} failed after clearing? {scan_cache.is_failed(tool_id)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
