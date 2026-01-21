import logging
import random

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff and jitter."""

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter_factor: float = 0.1,
    ):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter_factor = jitter_factor
        self._current_delay = initial_delay
        self._consecutive_errors = 0

    def reset(self) -> None:
        """Reset delay after successful request."""
        self._current_delay = self.initial_delay
        self._consecutive_errors = 0

    def backoff(self) -> float:
        """Calculate next delay with exponential backoff and jitter."""
        self._consecutive_errors += 1
        self._current_delay = min(
            self._current_delay * self.backoff_factor,
            self.max_delay,
        )
        # Add jitter: +/- jitter_factor of the delay
        jitter = self._current_delay * self.jitter_factor * (2 * random.random() - 1)
        return self._current_delay + jitter

    @property
    def current_delay(self) -> float:
        """Get current delay with jitter applied."""
        jitter = self._current_delay * self.jitter_factor * (2 * random.random() - 1)
        return self._current_delay + jitter
