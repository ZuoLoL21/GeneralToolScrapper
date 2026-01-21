"""Storage backends for persisting tool data.

This module provides:
- PermanentStorage: Abstract base class for persistent storage
- FileManager: File-based persistent storage implementation
- Cache: Abstract base class for caching
- FileCache: File-based cache with TTL support
"""

from src.storage.cache.base import Cache
from src.storage.cache.file_caching import FileCache
from src.storage.permanent_storage.base import PermanentStorage
from src.storage.permanent_storage.file_manager import FileManager

__all__ = [
    "Cache",
    "FileCache",
    "FileManager",
    "PermanentStorage",
]
