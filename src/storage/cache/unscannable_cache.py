"""Cache for permanently unscannable images to prevent repeated scan attempts."""

import logging
from datetime import UTC, datetime

from src.consts import UNSCANNABLE_CACHE_TTL
from src.storage.cache.file_caching import FileCache

logger = logging.getLogger(__name__)


class UnscannableCache:
    """Caches permanently unscannable images (7-day TTL by default)."""

    def __init__(self, cache: FileCache, ttl: int = UNSCANNABLE_CACHE_TTL):
        """Initialize UnscannableCache.

        Args:
            cache: FileCache instance for storage
            ttl: Time-to-live for unscannable images in seconds (default: 7 days)
        """
        self.cache = cache
        self.ttl = ttl
        self.category = "unscannable_images"

    def mark_unscannable(self, tool_id: str, reason: str) -> None:
        """Mark an image as permanently unscannable.

        Args:
            tool_id: Tool ID to mark as unscannable
            reason: Reason why the image is unscannable
        """
        logger.info(f"Marking {tool_id} as unscannable: {reason}")
        self.cache.put(
            key=f"unscannable_{tool_id}",
            value={"reason": reason, "timestamp": datetime.now(UTC).isoformat()},
            category=self.category,
            ttl=self.ttl,
        )

    def is_unscannable(self, tool_id: str) -> bool:
        """Check if an image is marked as unscannable.

        Args:
            tool_id: Tool ID to check

        Returns:
            True if image is marked as unscannable, False otherwise
        """
        result = self.cache.get(f"unscannable_{tool_id}", self.category)
        if result:
            logger.debug(f"Found unscannable cache entry for {tool_id}")
            return True
        return False

    def get_unscannable_info(self, tool_id: str) -> dict | None:
        """Get information about why an image is unscannable.

        Args:
            tool_id: Tool ID to get info for

        Returns:
            Dictionary with reason and timestamp, or None if not found
        """
        return self.cache.get(f"unscannable_{tool_id}", self.category)

    def clear_unscannable(self, tool_id: str) -> None:
        """Remove unscannable marking for an image.

        Args:
            tool_id: Tool ID to clear
        """
        logger.info(f"Clearing unscannable marking for {tool_id}")
        self.cache.delete(f"unscannable_{tool_id}", self.category)


def main():
    """Example usage of UnscannableCache."""
    from pathlib import Path

    from src.consts import DEFAULT_DATA_DIR

    # Create cache
    cache_dir = Path(DEFAULT_DATA_DIR) / "cache"
    file_cache = FileCache(cache_dir=cache_dir, default_ttl=0)
    unscannable_cache = UnscannableCache(file_cache)

    # Test marking as unscannable
    tool_id = "docker_hub:library/scratch"
    reason = "Virtual base image, cannot be pulled or scanned"

    print(f"Marking {tool_id} as unscannable...")
    unscannable_cache.mark_unscannable(tool_id, reason)

    # Check if unscannable
    print(f"Is {tool_id} unscannable? {unscannable_cache.is_unscannable(tool_id)}")

    # Get info
    info = unscannable_cache.get_unscannable_info(tool_id)
    print(f"Info: {info}")

    # Clear
    print(f"Clearing unscannable marking for {tool_id}...")
    unscannable_cache.clear_unscannable(tool_id)

    # Check again
    print(f"Is {tool_id} unscannable after clearing? {unscannable_cache.is_unscannable(tool_id)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
