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

        from src.consts import DOCKER_HUB_NAMESPACE_PRESETS

        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.request_delay_ms = request_delay_ms
        self.use_cache = use_cache

        # Namespace resolution: explicit param > env var > default
        if namespaces is not None:
            self.namespaces = namespaces
        else:
            env_namespaces = os.getenv("DOCKER_HUB_NAMESPACES", "").strip()
            if env_namespaces:
                # Check if it's a preset (default, popular, all)
                if env_namespaces.lower() in DOCKER_HUB_NAMESPACE_PRESETS:
                    self.namespaces = DOCKER_HUB_NAMESPACE_PRESETS[env_namespaces.lower()]
                else:
                    # Parse as comma-separated list
                    self.namespaces = [ns.strip() for ns in env_namespaces.split(",") if ns.strip()]
            else:
                # Default to library namespace
                self.namespaces = DOCKER_HUB_NAMESPACE_PRESETS["default"]

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

    async def _fetch_available_tags(
        self,
        namespace: str,
        name: str,
        limit: int = 50,
    ) -> list[str]:
        """Fetch available Docker image tags for a repository.

        Called DURING SCRAPING to get available tags upfront.

        Args:
            namespace: Repository namespace.
            name: Repository name.
            limit: Max tags to fetch (default: 50).

        Returns:
            List of tag names (e.g., ["latest", "alpine", "1.0.5", "16-bullseye"]).
        """
        try:
            endpoint = f"/repositories/{namespace}/{name}/tags"
            data = await self._request(endpoint, params={"page_size": limit})

            if not data:
                return []

            # Extract tag names from results
            tags = []
            for tag_obj in data.get("results", []):
                if isinstance(tag_obj, dict) and "name" in tag_obj:
                    tags.append(tag_obj["name"])

            logger.debug(f"Fetched {len(tags)} tags for {namespace}/{name}")
            return tags

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"No tags found for {namespace}/{name}")
                return []
            logger.warning(f"Failed to fetch tags for {namespace}/{name}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error fetching tags for {namespace}/{name}: {e}")
            return []

    def _select_tag_for_digest(self, available_tags: list[str]) -> str | None:
        """Select best tag for digest retrieval with enhanced priority.

        Priority (based on production stability and availability):
        1. 'stable' - explicitly marked stable version
        2. 'latest' - most recent stable version (most common)
        3. 'lts' - long-term support version
        4. 'alpine' - lightweight variant (very common)
        5. Semantic versions - highest stable version (e.g., '16.1.12' > '16.0.4')
        6. First available - fallback

        Args:
            available_tags: List of available tag names

        Returns:
            Selected tag name or None if no tags available
        """
        if not available_tags:
            return None

        # Priority 1-4: Named stability tags
        for preferred in ["stable", "latest", "lts", "alpine"]:
            if preferred in available_tags:
                logger.debug(f"Selected tag '{preferred}' from {len(available_tags)} available tags")
                return preferred

        # Priority 5: Semantic versions (16.1.12, 3.11.5, 20.4, etc.)
        semantic_versions = self._extract_semantic_versions(available_tags)
        if semantic_versions:
            selected = semantic_versions[0]  # Already sorted by version descending
            logger.debug(
                f"Selected semantic version '{selected}' from {len(semantic_versions)} "
                f"version tags out of {len(available_tags)} total"
            )
            return selected

        # Priority 6: First available tag as fallback
        selected = available_tags[0]
        logger.debug(f"Selected first available tag '{selected}' from {len(available_tags)} tags")
        return selected

    def _extract_semantic_versions(self, tags: list[str]) -> list[str]:
        """Extract and sort semantic version tags.

        Matches: 16, 16.1, 16.1.12, 3.11.5, etc.
        Sorts by version number descending (highest first).
        """
        import re

        version_pattern = re.compile(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?$')
        versions = []

        for tag in tags:
            match = version_pattern.match(tag)
            if match:
                # Parse into tuple of ints for proper sorting
                major = int(match.group(1))
                minor = int(match.group(2)) if match.group(2) else 0
                patch = int(match.group(3)) if match.group(3) else 0
                versions.append((tag, (major, minor, patch)))

        # Sort by version tuple descending
        versions.sort(key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in versions]

    async def _get_registry_token(self, namespace: str, name: str) -> str | None:
        """Get Docker Registry API authentication token.

        Tokens are valid for ~5 minutes, cache them.
        """
        try:
            url = "https://auth.docker.io/token"
            params = {
                "scope": f"repository:{namespace}/{name}:pull",
                "service": "registry.docker.io"
            }

            # Use a simple cache key
            cache_key = f"registry_token_{namespace}_{name}"

            # Check cache first (5-minute TTL)
            if hasattr(self, '_token_cache'):
                cached = self._token_cache.get(cache_key)
                if cached:
                    return cached

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                token = data.get("token")

                # Cache the token
                if not hasattr(self, '_token_cache'):
                    self._token_cache = {}
                self._token_cache[cache_key] = token

                return token

        except Exception as e:
            logger.warning(f"Failed to get registry token for {namespace}/{name}: {e}")
            return None

    async def _fetch_tag_digest(
        self, namespace: str, name: str, tag: str, max_retries: int = 3
    ) -> str | None:
        """Fetch digest for a specific Docker image tag with retry logic.

        Retries on network errors with exponential backoff.
        Does not retry on permanent errors (404, 401).

        Args:
            namespace: Docker Hub namespace
            name: Repository name
            tag: Tag to fetch digest for
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Digest string like 'sha256:abc123...' or None on failure.
        """
        retry_count = 0
        base_delay = 1.0

        while retry_count <= max_retries:
            try:
                # Get authentication token
                token = await self._get_registry_token(namespace, name)
                if not token:
                    logger.warning(f"No auth token for {namespace}/{name}:{tag}")
                    return None

                # Request manifest to get digest
                url = f"https://registry-1.docker.io/v2/{namespace}/{name}/manifests/{tag}"
                headers = {
                    "Accept": "application/vnd.docker.distribution.manifest.v2+json",
                    "Authorization": f"Bearer {token}",
                }

                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, timeout=10.0)

                    # Handle HTTP errors
                    if response.status_code in (401, 403, 404):
                        # Permanent errors - don't retry
                        logger.debug(
                            f"Digest fetch failed ({response.status_code}) for {namespace}/{name}:{tag}"
                        )
                        return None

                    response.raise_for_status()

                    # Extract digest from response header
                    digest = response.headers.get("Docker-Content-Digest")
                    if digest:
                        logger.debug(f"Fetched digest for {namespace}/{name}:{tag} → {digest[:19]}...")
                        return digest
                    else:
                        logger.warning(f"No digest header for {namespace}/{name}:{tag}")
                        return None

            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
                # Transient network errors - retry with backoff
                if retry_count < max_retries:
                    delay = base_delay * (2**retry_count)
                    logger.debug(
                        f"Network error fetching digest for {namespace}/{name}:{tag}, "
                        f"retry {retry_count + 1}/{max_retries} after {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    retry_count += 1
                else:
                    logger.warning(
                        f"Failed to fetch digest for {namespace}/{name}:{tag} "
                        f"after {max_retries} retries: {e}"
                    )
                    return None

            except httpx.HTTPStatusError as e:
                # HTTP errors other than 401/403/404 - retry with backoff
                if e.response.status_code in (500, 502, 503, 504) and retry_count < max_retries:
                    delay = base_delay * (2**retry_count)
                    logger.debug(
                        f"Server error ({e.response.status_code}) fetching digest for "
                        f"{namespace}/{name}:{tag}, retry {retry_count + 1}/{max_retries} "
                        f"after {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    retry_count += 1
                else:
                    logger.warning(f"HTTP error fetching digest for {namespace}/{name}:{tag}: {e}")
                    return None

            except Exception as e:
                logger.warning(f"Unexpected error fetching digest for {namespace}/{name}:{tag}: {e}")
                return None

        return None

    async def _parse_tool(self, repo: dict[str, Any], namespace: str) -> Tool:
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

        # Fetch available tags and select best tag for digest retrieval
        available_tags = await self._fetch_available_tags(namespace, name)

        # Select best tag based on priority
        selected_tag = self._select_tag_for_digest(available_tags)

        # Fetch digest for selected tag with fallback logic
        selected_digest = None
        tool_id = f"docker_hub:{namespace}/{name}"

        if selected_tag:
            selected_digest = await self._fetch_tag_digest(namespace, name, selected_tag)

            # If primary tag fails, try fallback tags
            if not selected_digest and available_tags:
                logger.info(f"Primary tag '{selected_tag}' failed for {tool_id}, trying fallbacks")

                # Define fallback sequence
                fallback_tags = ["stable", "latest", "lts", "alpine"]
                # Remove the already-tried tag and tags not in available_tags
                fallback_tags = [
                    tag for tag in fallback_tags if tag in available_tags and tag != selected_tag
                ]

                # Try fallback tags
                for fallback_tag in fallback_tags:
                    logger.debug(f"Trying fallback tag '{fallback_tag}' for {tool_id}")
                    selected_digest = await self._fetch_tag_digest(namespace, name, fallback_tag)
                    if selected_digest:
                        selected_tag = fallback_tag
                        logger.info(f"Fallback tag '{fallback_tag}' succeeded for {tool_id}")
                        break

            if not selected_digest:
                logger.warning(
                    f"Failed to fetch digest for {tool_id} after trying "
                    f"tag: {selected_tag} and fallbacks"
                )
        else:
            logger.warning(f"No tags available for {tool_id}")

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
            selected_image_tag=selected_tag,
            selected_image_digest=selected_digest,
            digest_fetch_date=datetime.now(UTC) if selected_digest else None,
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
                        tool = await self._parse_tool(repo, namespace)
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

            return await self._parse_tool(repo, namespace)

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
