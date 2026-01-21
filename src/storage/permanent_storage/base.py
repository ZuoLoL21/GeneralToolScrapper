"""Abstract base class for permanent storage backends.

Permanent storage is for long-term data persistence with category-based
organization. Unlike cache, data in permanent storage does not expire.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class PermanentStorage(ABC):
    """Abstract base class for permanent storage implementations.

    Provides a consistent interface for storing and retrieving data
    organized by categories. Implementations may use files, databases,
    or other storage backends.
    """

    @abstractmethod
    def save(self, key: str, data: Any, category: str) -> Path:
        """Save data to permanent storage.

        Args:
            key: Unique identifier for the data within the category.
            data: Data to store (implementation determines serialization).
            category: Category/namespace for organizing data.

        Returns:
            Path or identifier where data was stored.
        """
        ...

    @abstractmethod
    def load(self, key: str, category: str) -> Any | None:
        """Load data from permanent storage.

        Args:
            key: Unique identifier for the data.
            category: Category/namespace to look in.

        Returns:
            Stored data if found, None otherwise.
        """
        ...

    @abstractmethod
    def delete(self, key: str, category: str) -> bool:
        """Delete data from permanent storage.

        Args:
            key: Unique identifier for the data.
            category: Category/namespace to look in.

        Returns:
            True if data was deleted, False if not found.
        """
        ...

    @abstractmethod
    def exists(self, key: str, category: str) -> bool:
        """Check if data exists in permanent storage.

        Args:
            key: Unique identifier for the data.
            category: Category/namespace to look in.

        Returns:
            True if data exists, False otherwise.
        """
        ...

    @abstractmethod
    def list_keys(self, category: str) -> list[str]:
        """List all keys in a category.

        Args:
            category: Category/namespace to list keys from.

        Returns:
            List of keys in the category.
        """
        ...


def main() -> None:
    """Example demonstrating the PermanentStorage interface."""
    print("PermanentStorage is an abstract base class.")
    print("It defines the interface that storage implementations must follow:")
    print("  - save(key, data, category) -> Path")
    print("  - load(key, category) -> Any | None")
    print("  - delete(key, category) -> bool")
    print("  - exists(key, category) -> bool")
    print("  - list_keys(category) -> list[str]")
    print("\nSee FileManager for a concrete implementation.")


if __name__ == "__main__":
    main()
