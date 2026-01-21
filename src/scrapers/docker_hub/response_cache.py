import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ResponseCache:
    """Simple file-based response cache with TTL."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 86400):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds

    def _cache_key(self, endpoint: str, params: dict[str, Any]) -> str:
        """Generate cache key from endpoint and params."""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        return self.cache_dir / f"{key}.json"

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Get cached response if valid."""
        key = self._cache_key(endpoint, params)
        path = self._cache_path(key)

        if not path.exists():
            return None

        data = json.loads(path.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        age = (datetime.now(UTC) - cached_at).total_seconds()

        if age > self.ttl_seconds:
            path.unlink()
            return None

        return data["response"]

    def set(self, endpoint: str, params: dict[str, Any], response: dict[str, Any]) -> None:
        """Cache response."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = self._cache_key(endpoint, params)
        path = self._cache_path(key)

        data = {
            "cached_at": datetime.now(UTC).isoformat(),
            "endpoint": endpoint,
            "params": params,
            "response": response,
        }
        path.write_text(json.dumps(data))
