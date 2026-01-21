"""Docker Hub scraper with resilience patterns.

Implements scraping from Docker Hub API with:
- Exponential backoff on rate limits (429)
- Jitter to prevent thundering herd
- Queue persistence for resume across restarts
- Configurable delays between requests
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.consts import DEFAULT_DATA_DIR
from src.models.model_tool import (
    Identity,
    Lifecycle,
    Maintainer,
    MaintainerType,
    Maintenance,
    Metrics,
    SourceType,
    Tool,
)
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.docker_hub.rate_limiter import RateLimiter
from src.scrapers.docker_hub.response_cache import ResponseCache
from src.scrapers.docker_hub.scrape_queue import ScrapeQueue

logger = logging.getLogger(__name__)


def _extract_tags(repo: dict[str, Any]) -> list[str]:
    """Extract tags from repository data, handling different API formats."""
    categories = repo.get("categories", []) or []
    tags: list[str] = []
    for cat in categories:
        if isinstance(cat, str):
            tags.append(cat)
        elif isinstance(cat, dict) and "name" in cat:
            tags.append(cat["name"])
    return tags


class DockerHubScraper(BaseScraper):
    """Docker Hub scraper with resilience patterns.

    Resilience features:
    - Exponential backoff with jitter on rate limits
    - Request caching to reduce API calls
    - Queue persistence for resume across restarts
    - Configurable delay between requests
    """

    BASE_URL = "https://hub.docker.com/v2"

    def __init__(
        self,
        data_dir: Path | None = None,
        request_delay_ms: int = 100,
        use_cache: bool = True,
        cache_ttl_seconds: int = 86400,
        namespaces: list[str] | None = None,
    ):
        """Initialize Docker Hub scraper.

        Args:
            data_dir: Directory for cache and queue files. Defaults to ./data.
            request_delay_ms: Delay between requests in milliseconds.
            use_cache: Whether to cache API responses.
            cache_ttl_seconds: Cache TTL in seconds (default 24h).
            namespaces: List of namespaces to scrape.
                       None = read from env (DOCKER_HUB_NAMESPACES)
        """
        import os

        from src.consts import DOCKER_HUB_DEFAULT_NAMESPACES, DOCKER_HUB_POPULAR_NAMESPACES

        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.request_delay_ms = request_delay_ms
        self.use_cache = use_cache

        # Namespace resolution: explicit param > env var > default
        if namespaces is not None:
            self.namespaces = namespaces
        else:
            env_namespaces = os.getenv("DOCKER_HUB_NAMESPACES", "").strip()
            if env_namespaces:
                if env_namespaces.lower() == "popular":
                    self.namespaces = DOCKER_HUB_POPULAR_NAMESPACES
                else:
                    self.namespaces = [ns.strip() for ns in env_namespaces.split(",") if ns.strip()]
            else:
                self.namespaces = DOCKER_HUB_DEFAULT_NAMESPACES

        logger.info(f"Docker Hub scraper: {len(self.namespaces)} namespaces: {self.namespaces}")

        self._rate_limiter = RateLimiter()
        self._queue = ScrapeQueue(self.data_dir / "cache" / "docker_hub_queue.json")
        self._cache = ResponseCache(
            self.data_dir / "cache" / "docker_hub",
            ttl_seconds=cache_ttl_seconds,
        )
        self._client: httpx.AsyncClient | None = None

    @property
    def source_name(self) -> str:
        """Return source identifier."""
        return "docker_hub"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(30.0),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any] | None:
        """Make API request with rate limiting and caching.

        Args:
            endpoint: API endpoint (relative to base URL).
            params: Query parameters.
            use_cache: Whether to use cache for this request.

        Returns:
            JSON response as dictionary.

        Raises:
            httpx.HTTPStatusError: On non-retryable HTTP errors.
        """
        params = params or {}

        # Check cache first
        if use_cache and self.use_cache:
            cached = self._cache.get(endpoint, params)
            if cached is not None:
                logger.debug(f"Cache hit: {endpoint}")
                return cached

        client = await self._get_client()

        while True:
            # Apply request delay
            await asyncio.sleep(self.request_delay_ms / 1000)

            try:
                response = await client.get(endpoint, params=params)

                if response.status_code == 429:
                    # Rate limited - backoff and retry
                    delay = self._rate_limiter.backoff()
                    logger.warning(f"Rate limited (429), retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                self._rate_limiter.reset()

                data = response.json()

                # Cache successful response
                if use_cache and self.use_cache:
                    self._cache.set(endpoint, params, data)

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (500, 502, 503, 504):
                    # Server error - backoff and retry
                    delay = self._rate_limiter.backoff()
                    logger.warning(
                        f"Server error ({e.response.status_code}), retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

    async def _fetch_repositories(
        self,
        namespace: str,
        page_size: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        """Fetch repositories for a namespace with pagination.

        Args:
            namespace: Docker Hub namespace (e.g., 'library', 'bitnami').
            page_size: Number of results per page.

        Yields:
            Repository data dictionaries.
        """
        endpoint = f"/repositories/{namespace}"
        params = {"page_size": page_size, "page": 1}

        while True:
            data = await self._request(endpoint, params)

            for repo in data.get("results", []):
                yield repo

            # Check for next page
            next_url = data.get("next")
            if not next_url:
                break

            params["page"] += 1

    async def _fetch_repository_details(
        self,
        namespace: str,
        name: str,
    ) -> dict[str, Any] | None:
        """Fetch detailed repository information.

        Args:
            namespace: Repository namespace.
            name: Repository name.

        Returns:
            Repository details or None if not found.
        """
        try:
            return await self._request(f"/repositories/{namespace}/{name}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def _parse_tool(self, repo: dict[str, Any], namespace: str) -> Tool:
        """Parse Docker Hub repository data into Tool model.

        Args:
            repo: Repository data from API.
            namespace: Repository namespace.

        Returns:
            Parsed Tool object.
        """
        name = repo.get("name", "")
        full_name = f"{namespace}/{name}" if namespace != "library" else name

        # Determine maintainer type
        if namespace == "library" or repo.get("is_official", False):
            maintainer_type = MaintainerType.OFFICIAL
            verified = True
        else:
            # Check for verified publisher badge
            content_types = repo.get("content_types", [])
            verified = "verified_publisher" in content_types
            maintainer_type = MaintainerType.COMPANY if verified else MaintainerType.USER

        # Parse timestamps
        created_at = None
        last_updated = None
        if repo.get("date_registered"):
            with contextlib.suppress(ValueError, TypeError):
                created_at = datetime.fromisoformat(repo["date_registered"].replace("Z", "+00:00"))
        if repo.get("last_updated"):
            with contextlib.suppress(ValueError, TypeError):
                last_updated = datetime.fromisoformat(repo["last_updated"].replace("Z", "+00:00"))

        # Determine lifecycle based on age and activity
        lifecycle = Lifecycle.ACTIVE
        if last_updated:
            days_since_update = (datetime.now(UTC) - last_updated).days
            if days_since_update > 365:
                lifecycle = Lifecycle.LEGACY
            elif days_since_update > 180:
                lifecycle = Lifecycle.STABLE

        return Tool(
            id=f"docker_hub:{namespace}/{name}",
            name=full_name,
            source=SourceType.DOCKER_HUB,
            source_url=f"https://hub.docker.com/r/{namespace}/{name}",
            description=repo.get("description", "") or "",
            identity=Identity(
                canonical_name=name.lower(),
                aliases=[full_name.lower()] if namespace != "library" else [],
            ),
            maintainer=Maintainer(
                name=namespace,
                type=maintainer_type,
                verified=verified,
            ),
            metrics=Metrics(
                downloads=repo.get("pull_count", 0) or 0,
                stars=repo.get("star_count", 0) or 0,
            ),
            maintenance=Maintenance(
                created_at=created_at,
                last_updated=last_updated,
                is_deprecated=repo.get("is_archived", False),
            ),
            lifecycle=lifecycle,
            tags=_extract_tags(repo),
        )

    async def scrape(self) -> AsyncIterator[Tool]:
        """Scrape tools from Docker Hub.

        Yields:
            Tool objects normalized to the common data model.

        Note:
            Use scrape_with_resume(resume=True/False) to control resume behavior.
            This method always attempts to resume by default.
        """
        async for tool in self.scrape_with_resume(resume=True):
            yield tool

    async def scrape_with_resume(self, resume: bool = True) -> AsyncIterator[Tool]:
        """Scrape tools from Docker Hub with resume control.

        Args:
            resume: Whether to resume from previous scrape state.

        Yields:
            Tool objects normalized to the common data model.
        """
        if resume:
            self._queue.load()

        # If queue is empty, populate with namespaces
        if self._queue.is_empty:
            self._queue.add_pending(self.namespaces)

        try:
            while not self._queue.is_empty:
                namespace = self._queue.get_next()
                if namespace is None:
                    break

                logger.info(f"Scraping namespace: {namespace}")

                try:
                    async for repo in self._fetch_repositories(namespace):
                        tool = self._parse_tool(repo, namespace)
                        yield tool

                    self._queue.mark_completed(namespace)

                except httpx.HTTPStatusError as e:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
                    logger.error(f"Failed to scrape {namespace}: {error_msg}")
                    self._queue.mark_failed(namespace, error_msg)

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Failed to scrape {namespace}: {error_msg}")
                    self._queue.mark_failed(namespace, error_msg)

        finally:
            if self._client:
                await self._client.aclose()

    async def get_tool_details(self, tool_id: str) -> Tool | None:
        """Fetch detailed information for a specific tool.

        Args:
            tool_id: Tool identifier in format 'docker_hub:{namespace}/{name}'.

        Returns:
            Tool object with full details, or None if not found.
        """
        if not tool_id.startswith("docker_hub:"):
            return None

        # Parse namespace/name from ID
        path = tool_id.replace("docker_hub:", "")
        parts = path.split("/")

        if len(parts) == 1:
            # Official image (library namespace)
            namespace = "library"
            name = parts[0]
        elif len(parts) == 2:
            namespace, name = parts
        else:
            logger.warning(f"Invalid tool ID format: {tool_id}")
            return None

        try:
            repo = await self._fetch_repository_details(namespace, name)
            if repo is None:
                return None

            return self._parse_tool(repo, namespace)

        finally:
            if self._client:
                await self._client.aclose()

    async def clear_cache(self) -> None:
        """Clear all cached data."""
        import shutil

        cache_dir = self.data_dir / "cache" / "docker_hub"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("Cleared Docker Hub cache")

    async def clear_queue(self) -> None:
        """Clear scrape queue (start fresh)."""
        self._queue.clear()
        logger.info("Cleared Docker Hub scrape queue")


async def main1() -> None:
    # Create scraper for official Docker images
    scraper = DockerHubScraper(
        request_delay_ms=100,
        use_cache=True,
        namespaces=["library"],  # Official images only
    )

    print("=== Docker Hub Scraper Example ===\n")

    # Example 1: Fetch details for a specific tool
    print("1. Fetching details for 'postgres'...")
    tool = await scraper.get_tool_details("docker_hub:library/postgres")
    if tool:
        print(tool.model_dump_json(indent=4))
    print()


async def main2() -> None:
    # Example 2: Scrape first 5 tools from a namespace
    print("2. Scraping first 100 official images...")
    scraper2 = DockerHubScraper(
        namespaces=["library"],
    )

    count = 0
    async for tool in scraper2.scrape_with_resume(resume=False):
        count += 1
        print(f"   [{count}] {tool.name}: {tool.metrics.downloads:,} downloads")
        if count >= 100:
            break

    # Clean up the client
    if scraper2._client:
        await scraper2._client.aclose()

    print("\nDone!")


async def main_multiple_namespaces() -> None:
    """Example: Scrape from multiple namespaces."""
    print("\n3. Scraping from multiple namespaces (library, bitnami)...")
    scraper = DockerHubScraper(
        namespaces=["library", "bitnami"],
        request_delay_ms=100,
    )

    count = 0
    async for tool in scraper.scrape_with_resume(resume=False):
        namespace = tool.id.split(":")[1].split("/")[0]
        print(f"   [{count+1}] {tool.name} (namespace: {namespace})")
        count += 1
        if count >= 10:
            break

    # Clean up the client
    if scraper._client:
        await scraper._client.aclose()

    print("Successfully scraped from multiple namespaces")


if __name__ == "__main__":
    # Configure logging to see what's happening
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main1())
    asyncio.run(main2())
    asyncio.run(main_multiple_namespaces())
