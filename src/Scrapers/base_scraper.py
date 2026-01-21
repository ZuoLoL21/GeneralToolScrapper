"""Base scraper abstract class defining the scraper contract."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

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

    def scrape(self) -> AsyncGenerator[Tool, None]:
        """Scrape tools from the source.

        Yields:
            Tool objects normalized to the common data model.

        Note:
            Subclasses must override this method. Not marked abstract
            due to Python ABC limitations with async generators.
        """
        raise NotImplementedError("Subclasses must implement scrape()")

    async def get_tool_details(self, tool_id: str) -> Tool | None:
        """Fetch detailed information for a specific tool.

        Args:
            tool_id: The tool identifier in the format '{source}:{namespace}/{name}'

        Returns:
            Tool object with full details, or None if not found.

        Note:
            Subclasses must override this method.
        """
        raise NotImplementedError("Subclasses must implement get_tool_details()")
