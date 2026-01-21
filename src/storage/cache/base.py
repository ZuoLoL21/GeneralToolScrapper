"""Abstract base class for cache backends.

Caches provide temporary storage with optional TTL (time-to-live) support.
Data may be evicted based on TTL expiration or cache clearing operations.
"""

from abc import ABC, abstractmethod
from typing import Any


class Cache(ABC):
    """Abstract base class for cache implementations.

    Provides a consistent interface for caching data with category-based
    organization. Implementations may support TTL for automatic expiration.
    """

    @abstractmethod
    def get(self, key: str, category: str = "default") -> Any | None:
        """Get a value from the cache.

        Args:
            key: Unique identifier for the cached value.
            category: Category/namespace for organizing cached data.

        Returns:
            Cached value if found and not expired, None otherwise.
        """
        ...

    @abstractmethod
    def put(self, key: str, value: Any, category: str = "default", ttl: int | None = None) -> None:
        """Store a value in the cache.

        Args:
            key: Unique identifier for the cached value.
            value: Value to cache.
            category: Category/namespace for organizing cached data.
            ttl: Time-to-live in seconds. None uses the cache's default TTL.
        """
        ...

    @abstractmethod
    def delete(self, key: str, category: str = "default") -> bool:
        """Delete a value from the cache.

        Args:
            key: Unique identifier for the cached value.
            category: Category/namespace to look in.

        Returns:
            True if value was deleted, False if not found.
        """
        ...

    @abstractmethod
    def exists(self, key: str, category: str = "default") -> bool:
        """Check if a key exists in the cache and is not expired.

        Args:
            key: Unique identifier for the cached value.
            category: Category/namespace to look in.

        Returns:
            True if value exists and is valid, False otherwise.
        """
        ...

    @abstractmethod
    def clear(self, category: str | None = None) -> int:
        """Clear cached values.

        Args:
            category: If provided, only clear values in this category.
                     If None, clear all cached values.

        Returns:
            Number of entries cleared.
        """
        ...


def main() -> None:
    """Example demonstrating the Cache interface."""
    print("Cache is an abstract base class.")
    print("It defines the interface that cache implementations must follow:")
    print("  - get(key, category) -> Any | None")
    print("  - put(key, value, category, ttl) -> None")
    print("  - delete(key, category) -> bool")
    print("  - exists(key, category) -> bool")
    print("  - clear(category) -> int")
    print("\nSee FileCache for a concrete implementation.")


if __name__ == "__main__":
    main()
