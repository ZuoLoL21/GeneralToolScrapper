"""Base scraper abstract class defining the scraper contract."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.Models.model_tool import Tool


class BaseScraper(ABC):
    """Abstract base class for all tool scrapers.

    All scrapers must implement the scrape method which yields Tool objects.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source identifier (e.g., 'docker_hub', 'github')."""
        ...

    @abstractmethod
    async def scrape(self) -> AsyncIterator[Tool]:
        """Scrape tools from the source.

        Yields:
            Tool objects normalized to the common data model.
        """
        ...

    @abstractmethod
    async def get_tool_details(self, tool_id: str) -> Tool | None:
        """Fetch detailed information for a specific tool.

        Args:
            tool_id: The tool identifier in the format '{source}:{namespace}/{name}'

        Returns:
            Tool object with full details, or None if not found.
        """
        ...
