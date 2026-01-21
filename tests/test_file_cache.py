"""Tests for file-based cache implementation."""

import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.storage.cache.file_caching import FileCache


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_cache(temp_dir: Path) -> FileCache:
    """Create a FileCache with temporary directory."""
    return FileCache(cache_dir=temp_dir, default_ttl=0)


class TestFileCache:
    """Tests for FileCache class."""

    def test_put_and_get(self, file_cache: FileCache) -> None:
        """Test basic put and get operations."""
        file_cache.put("key1", "value1", "test")
        result = file_cache.get("key1", "test")
        assert result == "value1"

    def test_get_nonexistent(self, file_cache: FileCache) -> None:
        """Test getting nonexistent key."""
        result = file_cache.get("nonexistent", "test")
        assert result is None

    def test_put_complex_value(self, file_cache: FileCache) -> None:
        """Test putting complex JSON-serializable values."""
        value = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }
        file_cache.put("complex", value, "test")
        result = file_cache.get("complex", "test")
        assert result == value

    def test_exists(self, file_cache: FileCache) -> None:
        """Test exists check."""
        assert not file_cache.exists("key1", "test")

        file_cache.put("key1", "value1", "test")
        assert file_cache.exists("key1", "test")

    def test_delete(self, file_cache: FileCache) -> None:
        """Test delete operation."""
        file_cache.put("key1", "value1", "test")
        assert file_cache.exists("key1", "test")

        deleted = file_cache.delete("key1", "test")
        assert deleted
        assert not file_cache.exists("key1", "test")

    def test_delete_nonexistent(self, file_cache: FileCache) -> None:
        """Test deleting nonexistent key."""
        deleted = file_cache.delete("nonexistent", "test")
        assert not deleted

    def test_multiple_categories(self, file_cache: FileCache) -> None:
        """Test multiple cache categories."""
        file_cache.put("key1", "value1", "category1")
        file_cache.put("key1", "value2", "category2")

        # Same key in different categories should have different values
        assert file_cache.get("key1", "category1") == "value1"
        assert file_cache.get("key1", "category2") == "value2"

    def test_list_keys(self, file_cache: FileCache) -> None:
        """Test listing keys in a category."""
        file_cache.put("key1", "value1", "test")
        file_cache.put("key2", "value2", "test")
        file_cache.put("key3", "value3", "other")

        keys = file_cache.list_keys("test")
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" not in keys

    def test_list_keys_empty_category(self, file_cache: FileCache) -> None:
        """Test listing keys in nonexistent category."""
        keys = file_cache.list_keys("nonexistent")
        assert keys == []

    def test_clear_category(self, file_cache: FileCache) -> None:
        """Test clearing specific category."""
        file_cache.put("key1", "value1", "category1")
        file_cache.put("key2", "value2", "category1")
        file_cache.put("key3", "value3", "category2")

        cleared = file_cache.clear("category1")
        assert cleared == 2

        # category1 should be empty
        assert not file_cache.exists("key1", "category1")
        assert not file_cache.exists("key2", "category1")

        # category2 should still have data
        assert file_cache.exists("key3", "category2")

    def test_clear_all(self, file_cache: FileCache) -> None:
        """Test clearing all categories."""
        file_cache.put("key1", "value1", "category1")
        file_cache.put("key2", "value2", "category2")
        file_cache.put("key3", "value3", "category3")

        cleared = file_cache.clear()
        assert cleared == 3

        # All should be cleared
        assert not file_cache.exists("key1", "category1")
        assert not file_cache.exists("key2", "category2")
        assert not file_cache.exists("key3", "category3")

    def test_ttl_expiration(self, temp_dir: Path) -> None:
        """Test TTL expiration."""
        # Create cache with 1 second TTL
        cache = FileCache(cache_dir=temp_dir, default_ttl=1)

        cache.put("key1", "value1", "test")
        assert cache.exists("key1", "test")

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        assert not cache.exists("key1", "test")
        assert cache.get("key1", "test") is None

    def test_ttl_per_entry(self, temp_dir: Path) -> None:
        """Test per-entry TTL override."""
        cache = FileCache(cache_dir=temp_dir, default_ttl=10)

        # Store with short TTL
        cache.put("short", "value", "test", ttl=1)
        # Store with long TTL
        cache.put("long", "value", "test", ttl=100)

        # Wait for short TTL to expire
        time.sleep(1.5)

        # Short should be expired, long should still exist
        assert not cache.exists("short", "test")
        assert cache.exists("long", "test")

    def test_no_ttl(self, file_cache: FileCache) -> None:
        """Test entries with no TTL (ttl=0)."""
        file_cache.put("key1", "value1", "test", ttl=0)

        # Wait a bit
        time.sleep(0.5)

        # Should still exist (no expiration)
        assert file_cache.exists("key1", "test")
        assert file_cache.get("key1", "test") == "value1"

    def test_get_stats_empty(self, file_cache: FileCache) -> None:
        """Test get_stats with no data."""
        stats = file_cache.get_stats()
        assert "cache_dir" in stats
        assert "default_ttl" in stats
        assert "categories" in stats
        assert len(stats["categories"]) == 0

    def test_get_stats_with_data(self, file_cache: FileCache) -> None:
        """Test get_stats with data."""
        file_cache.put("key1", "value1", "category1")
        file_cache.put("key2", "value2", "category1")
        file_cache.put("key3", "value3", "category2")

        stats = file_cache.get_stats()
        assert len(stats["categories"]) == 2
        assert stats["categories"]["category1"]["total_entries"] == 2
        assert stats["categories"]["category2"]["total_entries"] == 1

    def test_get_stats_with_expired(self, temp_dir: Path) -> None:
        """Test get_stats includes expired entries."""
        cache = FileCache(cache_dir=temp_dir, default_ttl=10)

        cache.put("valid", "value", "test", ttl=10)
        cache.put("expired", "value", "test", ttl=0.5)

        # Wait for one to expire
        time.sleep(1.5)

        stats = cache.get_stats()
        # Should show 2 total, 1 expired, 1 valid
        assert stats["categories"]["test"]["total_entries"] == 2
        assert stats["categories"]["test"]["expired_entries"] == 1
        assert stats["categories"]["test"]["valid_entries"] == 1

    def test_hash_key_consistency(self, file_cache: FileCache) -> None:
        """Test that key hashing is consistent."""
        hash1 = file_cache._hash_key("test_key")
        hash2 = file_cache._hash_key("test_key")
        assert hash1 == hash2

        # Different keys should have different hashes
        hash3 = file_cache._hash_key("different_key")
        assert hash1 != hash3

    def test_hash_key_length(self, file_cache: FileCache) -> None:
        """Test that hash is truncated to 16 chars."""
        hash_val = file_cache._hash_key("any_key")
        assert len(hash_val) == 16

    def test_overwrite_existing(self, file_cache: FileCache) -> None:
        """Test overwriting existing cache entry."""
        file_cache.put("key1", "value1", "test")
        assert file_cache.get("key1", "test") == "value1"

        file_cache.put("key1", "value2", "test")
        assert file_cache.get("key1", "test") == "value2"

    def test_cache_metadata(self, file_cache: FileCache, temp_dir: Path) -> None:
        """Test that cache entries include metadata."""
        file_cache.put("key1", "value1", "test", ttl=100)

        # Read file directly to check metadata
        cache_path = file_cache._cache_path("key1", "test")
        data = json.loads(cache_path.read_text())

        assert "cached_at" in data
        assert "original_key" in data
        assert "ttl" in data
        assert "value" in data

        assert data["original_key"] == "key1"
        assert data["ttl"] == 100
        assert data["value"] == "value1"

        # Verify cached_at is valid datetime
        cached_at = datetime.fromisoformat(data["cached_at"])
        assert isinstance(cached_at, datetime)

    def test_invalid_json_handling(
        self, file_cache: FileCache, temp_dir: Path
    ) -> None:
        """Test handling of corrupted cache files."""
        # Create category directory
        category_dir = temp_dir / "test"
        category_dir.mkdir(parents=True)

        # Create invalid JSON file
        hash_key = file_cache._hash_key("corrupted")
        invalid_path = category_dir / f"{hash_key}.json"
        invalid_path.write_text("{ invalid json }")

        # Get should return None for corrupted file
        result = file_cache.get("corrupted", "test")
        assert result is None

        # Exists should return False for corrupted file
        exists = file_cache.exists("corrupted", "test")
        assert not exists

    def test_list_keys_ignores_expired(self, temp_dir: Path) -> None:
        """Test that list_keys filters out expired entries."""
        cache = FileCache(cache_dir=temp_dir, default_ttl=1)

        cache.put("valid", "value", "test", ttl=100)
        cache.put("expired", "value", "test", ttl=0.5)

        # Wait for one to expire
        time.sleep(1)

        keys = cache.list_keys("test")
        assert "valid" in keys
        assert "expired" not in keys

    def test_default_category(self, file_cache: FileCache) -> None:
        """Test using default category."""
        # When no category specified, should use 'default'
        file_cache.put("key1", "value1")
        result = file_cache.get("key1")
        assert result == "value1"

        # Should be stored in 'default' category
        assert file_cache.exists("key1", "default")

    def test_directory_structure(self, file_cache: FileCache, temp_dir: Path) -> None:
        """Test that cache creates proper directory structure."""
        file_cache.put("key1", "value1", "category1")

        # Check directory structure
        category_dir = temp_dir / "category1"
        assert category_dir.exists()
        assert category_dir.is_dir()

        # Check cache file exists
        files = list(category_dir.glob("*.json"))
        assert len(files) == 1

    def test_concurrent_categories(self, file_cache: FileCache) -> None:
        """Test handling multiple categories with same keys."""
        categories = ["cat1", "cat2", "cat3"]
        for cat in categories:
            file_cache.put("shared_key", f"value_for_{cat}", cat)

        # All should coexist
        for cat in categories:
            value = file_cache.get("shared_key", cat)
            assert value == f"value_for_{cat}"

    def test_get_removes_expired_file(
        self, file_cache: FileCache, temp_dir: Path
    ) -> None:
        """Test that get() removes expired cache files."""
        cache = FileCache(cache_dir=temp_dir, default_ttl=1)
        cache.put("key1", "value1", "test")

        cache_path = cache._cache_path("key1", "test")
        assert cache_path.exists()

        # Wait for expiration
        time.sleep(1.5)

        # Get should return None and remove file
        result = cache.get("key1", "test")
        assert result is None
        assert not cache_path.exists()

    def test_exists_removes_expired_file(
        self, file_cache: FileCache, temp_dir: Path
    ) -> None:
        """Test that exists() removes expired cache files."""
        cache = FileCache(cache_dir=temp_dir, default_ttl=1)
        cache.put("key1", "value1", "test")

        cache_path = cache._cache_path("key1", "test")
        assert cache_path.exists()

        # Wait for expiration
        time.sleep(1.5)

        # exists() should return False and remove file
        exists = cache.exists("key1", "test")
        assert not exists
        assert not cache_path.exists()

    def test_special_characters_in_key(self, file_cache: FileCache) -> None:
        """Test keys with special characters."""
        special_keys = [
            "key/with/slashes",
            "key:with:colons",
            "key with spaces",
            "key@with#symbols",
        ]

        for key in special_keys:
            file_cache.put(key, f"value_for_{key}", "test")
            result = file_cache.get(key, "test")
            assert result == f"value_for_{key}"


def test_file_cache_default_cache_dir() -> None:
    """Test FileCache with default cache directory."""
    from src.consts import DEFAULT_DATA_DIR

    cache = FileCache()
    assert cache.cache_dir == DEFAULT_DATA_DIR / "cache"


def test_file_cache_custom_default_ttl() -> None:
    """Test FileCache with custom default TTL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = FileCache(cache_dir=tmpdir, default_ttl=3600)
        assert cache.default_ttl == 3600

        # Put without TTL should use default
        cache.put("key1", "value1", "test")

        # Read metadata to verify TTL
        cache_path = cache._cache_path("key1", "test")
        data = json.loads(cache_path.read_text())
        assert data["ttl"] == 3600
