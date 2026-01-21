"""Response cache for Docker Hub API responses.

Uses the centralized FileCache for storage while maintaining
backward-compatible API with TTL support.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from src.storage.cache.file_caching import FileCache

logger = logging.getLogger(__name__)

# Category name for API response cache entries
RESPONSE_CATEGORY = "responses"


class ResponseCache:
    """API response cache with TTL support.

    Uses FileCache internally for storage while providing a
    domain-specific API for caching API responses.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int | None = None,
        cache: FileCache | None = None,
    ):
        """Initialize ResponseCache.

        Args:
            cache_dir: Directory for cache files. Used to create FileCache if cache not provided.
            ttl_seconds: Time-to-live for cached responses in seconds.
                        If None, uses FileCache's default TTL.
            cache: Optional FileCache instance to use. If provided, cache_dir and ttl_seconds are ignored.
        """
        self.ttl_seconds = ttl_seconds

        if cache is not None:
            self._cache = cache
        elif cache_dir is not None and ttl_seconds is not None:
            self._cache = FileCache(cache_dir=cache_dir, default_ttl=ttl_seconds)
        elif cache_dir is not None:
            self._cache = FileCache(cache_dir=cache_dir)
        elif ttl_seconds is not None:
            self._cache = FileCache(default_ttl=ttl_seconds)
        else:
            # Use FileCache defaults for both cache_dir and ttl
            self._cache = FileCache()

    def _cache_key(self, endpoint: str, params: dict[str, Any]) -> str:
        """Generate cache key from endpoint and params.

        Args:
            endpoint: API endpoint.
            params: Request parameters.

        Returns:
            Hash-based cache key.
        """
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Get cached response if valid.

        Args:
            endpoint: API endpoint.
            params: Request parameters used to identify the cached response.

        Returns:
            Cached response data if found and not expired, None otherwise.
        """
        key = self._cache_key(endpoint, params)
        data = self._cache.get(key, RESPONSE_CATEGORY)

        if data is None:
            return None

        # The data stored is the full response object
        return data

    def set(self, endpoint: str, params: dict[str, Any], response: dict[str, Any]) -> None:
        """Cache a response.

        Args:
            endpoint: API endpoint.
            params: Request parameters.
            response: Response data to cache.
        """
        key = self._cache_key(endpoint, params)
        self._cache.put(key, response, RESPONSE_CATEGORY, ttl=self.ttl_seconds)

    def invalidate(self, endpoint: str, params: dict[str, Any]) -> bool:
        """Invalidate a cached response.

        Args:
            endpoint: API endpoint.
            params: Request parameters.

        Returns:
            True if entry was invalidated, False if not found.
        """
        key = self._cache_key(endpoint, params)
        return self._cache.delete(key, RESPONSE_CATEGORY)

    def clear(self) -> int:
        """Clear all cached responses.

        Returns:
            Number of entries cleared.
        """
        return self._cache.clear(RESPONSE_CATEGORY)


def main() -> None:
    """Example usage of ResponseCache."""
    logging.basicConfig(level=logging.DEBUG)

    cache = ResponseCache(ttl_seconds=3600)

    print("=== ResponseCache Example ===\n")

    # Cache a response
    print("1. Caching API response...")
    endpoint = "/v2/repositories/library/postgres"
    params = {"page": 1, "page_size": 25}
    response = {
        "name": "postgres",
        "namespace": "library",
        "description": "PostgreSQL database",
        "star_count": 10000,
        "pull_count": 1000000000,
    }
    cache.set(endpoint, params, response)
    print(f"   Cached response for {endpoint}")

    # Retrieve it
    print("\n2. Retrieving cached response...")
    cached = cache.get(endpoint, params)
    if cached:
        print(f"   Name: {cached['name']}")
        print(f"   Stars: {cached['star_count']}")

    # Check non-existent
    print("\n3. Checking non-cached endpoint...")
    missing = cache.get("/v2/repositories/library/redis", {"page": 1})
    print(f"   Found: {missing is not None}")

    # Invalidate
    print("\n4. Invalidating cached response...")
    invalidated = cache.invalidate(endpoint, params)
    print(f"   Invalidated: {invalidated}")
    print(f"   After invalidation: {cache.get(endpoint, params)}")


if __name__ == "__main__":
    main()
