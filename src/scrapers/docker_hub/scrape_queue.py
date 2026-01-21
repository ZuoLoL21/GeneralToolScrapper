import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ScrapeQueue:
    """Persistent queue for tracking scrape progress."""

    def __init__(self, queue_path: Path):
        self.queue_path = queue_path
        self._pending: list[str] = []
        self._completed: set[str] = set()
        self._failed: dict[str, str] = {}  # namespace -> error message

    def load(self) -> None:
        """Load queue state from disk."""
        if self.queue_path.exists():
            data = json.loads(self.queue_path.read_text())
            self._pending = data.get("pending", [])
            self._completed = set(data.get("completed", []))
            self._failed = data.get("failed", {})
            logger.info(
                f"Resumed queue: {len(self._pending)} pending, "
                f"{len(self._completed)} completed, {len(self._failed)} failed"
            )

    def save(self) -> None:
        """Persist queue state to disk."""
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "pending": self._pending,
            "completed": list(self._completed),
            "failed": self._failed,
        }
        self.queue_path.write_text(json.dumps(data, indent=2))

    def add_pending(self, items: list[str]) -> None:
        """Add items to pending queue (skipping already completed)."""
        for item in items:
            if item not in self._completed and item not in self._pending:
                self._pending.append(item)

    def get_next(self) -> str | None:
        """Get next pending item."""
        return self._pending[0] if self._pending else None

    def mark_completed(self, item: str) -> None:
        """Mark item as completed."""
        if item in self._pending:
            self._pending.remove(item)
        self._completed.add(item)
        self.save()

    def mark_failed(self, item: str, error: str) -> None:
        """Mark item as failed with error message."""
        if item in self._pending:
            self._pending.remove(item)
        self._failed[item] = error
        self.save()

    def clear(self) -> None:
        """Clear all queue state."""
        self._pending = []
        self._completed = set()
        self._failed = {}
        if self.queue_path.exists():
            self.queue_path.unlink()

    @property
    def is_empty(self) -> bool:
        """Check if queue has no pending items."""
        return len(self._pending) == 0
