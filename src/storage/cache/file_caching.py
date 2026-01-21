"""File-based cache implementation.

Stores cached data as JSON files organized by category directories.
Supports optional TTL (time-to-live) for automatic expiration.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.consts import DEFAULT_DATA_DIR
from src.storage.cache.base import Cache

logger = logging.getLogger(__name__)


class FileCache(Cache):
    """File-based cache implementation with TTL support.

    Stores data as JSON files in category-organized directories.
    Each cached entry includes metadata (cached_at, original_key, ttl).

    Directory structure:
        {cache_dir}/
        ├── {category}/
        │   ├── {hash}.json
        │   └── {hash}.json
        └── {category}/
            └── {hash}.json
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        default_ttl: int = 0,
    ):
        """Initialize FileCache.

        Args:
            cache_dir: Directory for cache files. Defaults to {DEFAULT_DATA_DIR}/cache.
            default_ttl: Default TTL in seconds. 0 means no expiration.
        """
        if cache_dir is None:
            cache_dir = DEFAULT_DATA_DIR / "cache"
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl

    def _hash_key(self, key: str) -> str:
        """Generate a safe filename from a key using SHA-256 hash."""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _category_dir(self, category: str) -> Path:
        """Get the directory for a category."""
        return self.cache_dir / category

    def _cache_path(self, key: str, category: str) -> Path:
        """Get the file path for a cached entry."""
        return self._category_dir(category) / f"{self._hash_key(key)}.json"

    def _is_expired(self, entry: dict[str, Any]) -> bool:
        """Check if a cache entry is expired."""
        ttl = entry.get("ttl", 0)
        if ttl == 0:
            return False

        cached_at = datetime.fromisoformat(entry["cached_at"])
        age = (datetime.now(UTC) - cached_at).total_seconds()
        return age > ttl

    def get(self, key: str, category: str = "default") -> Any | None:
        """Get a value from the cache.

        Args:
            key: Unique identifier for the cached value.
            category: Category/namespace for organizing cached data.

        Returns:
            Cached value if found and not expired, None otherwise.
        """
        path = self._cache_path(key, category)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if self._is_expired(data):
                logger.debug(f"Cache expired for key={key} in category={category}")
                path.unlink()
                return None
            return data.get("value")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to read cache entry: {e}")
            return None

    def put(
        self,
        key: str,
        value: Any,
        category: str = "default",
        ttl: int | None = None,
    ) -> None:
        """Store a value in the cache.

        Args:
            key: Unique identifier for the cached value.
            value: Value to cache (must be JSON-serializable).
            category: Category/namespace for organizing cached data.
            ttl: Time-to-live in seconds. None uses the cache's default TTL.
        """
        category_dir = self._category_dir(category)
        category_dir.mkdir(parents=True, exist_ok=True)

        effective_ttl = ttl if ttl is not None else self.default_ttl
        entry = {
            "cached_at": datetime.now(UTC).isoformat(),
            "original_key": key,
            "ttl": effective_ttl,
            "value": value,
        }

        path = self._cache_path(key, category)
        path.write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")
        logger.debug(f"Cached key={key} in category={category} (ttl={effective_ttl}s)")

    def delete(self, key: str, category: str = "default") -> bool:
        """Delete a value from the cache.

        Args:
            key: Unique identifier for the cached value.
            category: Category/namespace to look in.

        Returns:
            True if value was deleted, False if not found.
        """
        path = self._cache_path(key, category)
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted cache key={key} from category={category}")
            return True
        return False

    def exists(self, key: str, category: str = "default") -> bool:
        """Check if a key exists in the cache and is not expired.

        Args:
            key: Unique identifier for the cached value.
            category: Category/namespace to look in.

        Returns:
            True if value exists and is valid, False otherwise.
        """
        path = self._cache_path(key, category)
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if self._is_expired(data):
                path.unlink()
                return False
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def clear(self, category: str | None = None) -> int:
        """Clear cached values.

        Args:
            category: If provided, only clear values in this category.
                     If None, clear all cached values.

        Returns:
            Number of entries cleared.
        """
        count = 0

        if category is not None:
            category_dir = self._category_dir(category)
            if category_dir.exists():
                for path in category_dir.glob("*.json"):
                    path.unlink()
                    count += 1
                logger.info(f"Cleared {count} entries from category={category}")
        else:
            if self.cache_dir.exists():
                for category_dir in self.cache_dir.iterdir():
                    if category_dir.is_dir():
                        for path in category_dir.glob("*.json"):
                            path.unlink()
                            count += 1
                logger.info(f"Cleared {count} entries from all categories")

        return count

    def list_keys(self, category: str = "default") -> list[str]:
        """List all original keys in a category.

        Args:
            category: Category to list keys from.

        Returns:
            List of original keys (not hashed).
        """
        keys = []
        category_dir = self._category_dir(category)
        if not category_dir.exists():
            return keys

        for path in category_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not self._is_expired(data):
                    keys.append(data.get("original_key", path.stem))
            except (json.JSONDecodeError, KeyError):
                continue

        return keys

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats per category.
        """
        stats: dict[str, Any] = {
            "cache_dir": str(self.cache_dir),
            "default_ttl": self.default_ttl,
            "categories": {},
        }

        if not self.cache_dir.exists():
            return stats

        for category_dir in self.cache_dir.iterdir():
            if category_dir.is_dir():
                total = 0
                expired = 0
                for path in category_dir.glob("*.json"):
                    total += 1
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if self._is_expired(data):
                            expired += 1
                    except (json.JSONDecodeError, KeyError):
                        pass

                stats["categories"][category_dir.name] = {
                    "total_entries": total,
                    "expired_entries": expired,
                    "valid_entries": total - expired,
                }

        return stats


def main() -> None:
    """Example usage of FileCache."""
    import tempfile

    logging.basicConfig(level=logging.DEBUG)

    # Use temporary directory for example
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = FileCache(cache_dir=tmpdir, default_ttl=0)  # No default TTL

        print("=== FileCache Example ===\n")

        # Store some values
        print("1. Storing values in cache...")
        cache.put("user:123", {"name": "Alice", "email": "alice@example.com"}, "users")
        cache.put("user:456", {"name": "Bob", "email": "bob@example.com"}, "users")
        cache.put("config:app", {"debug": True, "version": "1.0"}, "config")
        print("   Stored 3 values in 2 categories")

        # Retrieve values
        print("\n2. Retrieving values...")
        user = cache.get("user:123", "users")
        print(f"   user:123 = {user}")

        config = cache.get("config:app", "config")
        print(f"   config:app = {config}")

        # Check existence
        print("\n3. Checking existence...")
        print(f"   user:123 exists: {cache.exists('user:123', 'users')}")
        print(f"   user:999 exists: {cache.exists('user:999', 'users')}")

        # List keys
        print("\n4. Listing keys in 'users' category...")
        keys = cache.list_keys("users")
        print(f"   Keys: {keys}")

        # Get stats
        print("\n5. Cache statistics...")
        stats = cache.get_stats()
        print(f"   {stats}")

        # Delete a value
        print("\n6. Deleting user:123...")
        deleted = cache.delete("user:123", "users")
        print(f"   Deleted: {deleted}")
        print(f"   user:123 exists after delete: {cache.exists('user:123', 'users')}")

        # Clear a category
        print("\n7. Clearing 'users' category...")
        cleared = cache.clear("users")
        print(f"   Cleared {cleared} entries")

        # Store with TTL
        print("\n8. Storing with TTL=1 second...")
        cache.put("temp:data", {"temporary": True}, "temp", ttl=1)
        print(f"   temp:data exists: {cache.exists('temp:data', 'temp')}")

        import time

        print("   Waiting 2 seconds for expiration...")
        time.sleep(2)
        print(f"   temp:data exists after 2s: {cache.exists('temp:data', 'temp')}")


if __name__ == "__main__":
    main()
