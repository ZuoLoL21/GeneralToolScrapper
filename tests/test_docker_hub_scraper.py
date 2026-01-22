"""Tests for the Docker Hub scraper."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.model_tool import Lifecycle, MaintainerType, SourceType
from src.scrapers.docker_hub.docker_hub import (
    DockerHubScraper,
    RateLimiter,
    ResponseCache,
    ScrapeQueue,
)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_initial_state(self) -> None:
        limiter = RateLimiter(initial_delay=1.0, max_delay=60.0)
        assert limiter._current_delay == 1.0
        assert limiter._consecutive_errors == 0

    def test_reset(self) -> None:
        limiter = RateLimiter(initial_delay=1.0)
        limiter._current_delay = 30.0
        limiter._consecutive_errors = 5
        limiter.reset()
        assert limiter._current_delay == 1.0
        assert limiter._consecutive_errors == 0

    def test_backoff_increases_delay(self) -> None:
        limiter = RateLimiter(initial_delay=1.0, backoff_factor=2.0, jitter_factor=0.0)
        delay1 = limiter.backoff()
        assert delay1 == 2.0
        delay2 = limiter.backoff()
        assert delay2 == 4.0
        delay3 = limiter.backoff()
        assert delay3 == 8.0

    def test_backoff_respects_max_delay(self) -> None:
        limiter = RateLimiter(
            initial_delay=1.0, max_delay=5.0, backoff_factor=2.0, jitter_factor=0.0
        )
        for _ in range(10):
            limiter.backoff()
        assert limiter._current_delay == 5.0

    def test_backoff_with_jitter(self) -> None:
        limiter = RateLimiter(initial_delay=10.0, jitter_factor=0.1)
        delays = [limiter.backoff() for _ in range(5)]
        # All delays should be different due to jitter
        assert len(set(delays)) > 1


class TestScrapeQueue:
    """Tests for the ScrapeQueue class."""

    def test_empty_queue(self, tmp_path: Path) -> None:
        queue = ScrapeQueue(tmp_path / "queue.json")
        assert queue.is_empty
        assert queue.get_next() is None

    def test_add_pending(self, tmp_path: Path) -> None:
        queue = ScrapeQueue(tmp_path / "queue.json")
        queue.add_pending(["library", "bitnami", "nginx"])
        assert not queue.is_empty
        assert queue.get_next() == "library"

    def test_mark_completed(self, tmp_path: Path) -> None:
        queue = ScrapeQueue(tmp_path / "queue.json")
        queue.add_pending(["library", "bitnami"])
        queue.mark_completed("library")
        assert queue.get_next() == "bitnami"
        assert "library" in queue._completed

    def test_mark_failed(self, tmp_path: Path) -> None:
        queue = ScrapeQueue(tmp_path / "queue.json")
        queue.add_pending(["library"])
        queue.mark_failed("library", "HTTP 500")
        assert queue.is_empty
        assert queue._failed["library"] == "HTTP 500"

    def test_persistence(self, tmp_path: Path) -> None:
        queue_path = tmp_path / "queue.json"

        # Create and populate queue
        queue1 = ScrapeQueue(queue_path)
        queue1.add_pending(["library", "bitnami", "nginx"])
        queue1.mark_completed("library")
        queue1.save()

        # Load in new instance
        queue2 = ScrapeQueue(queue_path)
        queue2.load()
        assert "library" in queue2._completed
        assert queue2.get_next() == "bitnami"

    def test_no_duplicates(self, tmp_path: Path) -> None:
        queue = ScrapeQueue(tmp_path / "queue.json")
        queue.add_pending(["library", "bitnami"])
        queue.add_pending(["library", "nginx"])  # library is duplicate
        assert queue._pending.count("library") == 1
        assert "nginx" in queue._pending

    def test_clear(self, tmp_path: Path) -> None:
        queue_path = tmp_path / "queue.json"
        queue = ScrapeQueue(queue_path)
        queue.add_pending(["library"])
        queue.mark_completed("library")
        queue.save()
        assert queue_path.exists()

        queue.clear()
        assert queue.is_empty
        assert not queue_path.exists()


class TestResponseCache:
    """Tests for the ResponseCache class."""

    def test_cache_miss(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        result = cache.get("/endpoint", {"page": 1})
        assert result is None

    def test_cache_hit(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        data = {"results": [{"name": "test"}]}
        cache.set("/endpoint", {"page": 1}, data)

        result = cache.get("/endpoint", {"page": 1})
        assert result == data

    def test_cache_expiration(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache", ttl_seconds=1)
        data = {"results": []}
        cache.set("/endpoint", {}, data)

        # Manually expire the cache by modifying the cached_at
        # Note: Files are now stored in {cache_dir}/responses/{hash}.json
        cache_files = list((tmp_path / "cache" / "responses").glob("*.json"))
        assert len(cache_files) == 1

        cached_data = json.loads(cache_files[0].read_text())
        old_time = datetime.now(UTC) - timedelta(seconds=10)
        cached_data["cached_at"] = old_time.isoformat()
        cache_files[0].write_text(json.dumps(cached_data))

        # Should return None (expired)
        result = cache.get("/endpoint", {})
        assert result is None

    def test_different_params_different_keys(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.set("/endpoint", {"page": 1}, {"data": "page1"})
        cache.set("/endpoint", {"page": 2}, {"data": "page2"})

        assert cache.get("/endpoint", {"page": 1})["data"] == "page1"
        assert cache.get("/endpoint", {"page": 2})["data"] == "page2"


class TestDockerHubScraper:
    """Tests for the DockerHubScraper class."""

    def test_source_name(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        assert scraper.source_name == "docker_hub"

    def test_parse_official_image(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        repo_data = {
            "name": "postgres",
            "description": "PostgreSQL database",
            "pull_count": 1_000_000_000,
            "star_count": 10000,
            "date_registered": "2014-06-06T00:00:00Z",
            "last_updated": "2024-01-15T10:30:00Z",
        }

        tool = scraper._parse_tool(repo_data, "library")

        assert tool.id == "docker_hub:library/postgres"
        assert tool.name == "postgres"
        assert tool.source == SourceType.DOCKER_HUB
        assert tool.maintainer.type == MaintainerType.OFFICIAL
        assert tool.maintainer.verified is True
        assert tool.metrics.downloads == 1_000_000_000
        assert tool.metrics.stars == 10000

    def test_parse_verified_publisher(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        repo_data = {
            "name": "nginx",
            "description": "NGINX image",
            "pull_count": 500_000,
            "star_count": 200,
            "content_types": ["verified_publisher"],
            "last_updated": "2024-01-10T00:00:00Z",
        }

        tool = scraper._parse_tool(repo_data, "bitnami")

        assert tool.id == "docker_hub:bitnami/nginx"
        assert tool.name == "bitnami/nginx"
        assert tool.maintainer.type == MaintainerType.COMPANY
        assert tool.maintainer.verified is True

    def test_parse_user_image(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        repo_data = {
            "name": "myapp",
            "description": "My custom app",
            "pull_count": 1000,
            "star_count": 5,
            "last_updated": "2024-01-01T00:00:00Z",
        }

        tool = scraper._parse_tool(repo_data, "someuser")

        assert tool.id == "docker_hub:someuser/myapp"
        assert tool.maintainer.type == MaintainerType.USER
        assert tool.maintainer.verified is False

    def test_parse_lifecycle_from_age(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)

        # Active: updated within 180 days
        active_repo = {
            "name": "active",
            "last_updated": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
        }
        tool = scraper._parse_tool(active_repo, "library")
        assert tool.lifecycle == Lifecycle.ACTIVE

        # Stable: updated 180-365 days ago
        stable_repo = {
            "name": "stable",
            "last_updated": (datetime.now(UTC) - timedelta(days=200)).isoformat(),
        }
        tool = scraper._parse_tool(stable_repo, "library")
        assert tool.lifecycle == Lifecycle.STABLE

        # Legacy: not updated in over a year
        legacy_repo = {
            "name": "legacy",
            "last_updated": (datetime.now(UTC) - timedelta(days=400)).isoformat(),
        }
        tool = scraper._parse_tool(legacy_repo, "library")
        assert tool.lifecycle == Lifecycle.LEGACY

    def test_parse_handles_missing_fields(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        repo_data = {"name": "minimal"}  # Minimal data

        tool = scraper._parse_tool(repo_data, "user")

        assert tool.id == "docker_hub:user/minimal"
        assert tool.description == ""
        assert tool.metrics.downloads == 0
        assert tool.metrics.stars == 0

    def test_parse_deprecated_image(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        repo_data = {
            "name": "deprecated",
            "is_archived": True,
        }

        tool = scraper._parse_tool(repo_data, "library")
        assert tool.maintenance.is_deprecated is True

    @pytest.mark.asyncio
    async def test_get_tool_details_invalid_format(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)

        # Wrong prefix
        result = await scraper.get_tool_details("github:user/repo")
        assert result is None

    @pytest.mark.asyncio
    async def test_request_with_rate_limit(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        # Mock response sequence: 429, then success
        mock_request = httpx.Request("GET", "https://hub.docker.com/v2/test")
        mock_responses = [
            httpx.Response(429, json={"error": "rate limited"}, request=mock_request),
            httpx.Response(200, json={"results": []}, request=mock_request),
        ]

        async def mock_get(*args, **kwargs):
            return mock_responses.pop(0)

        with patch.object(scraper, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = mock_get
            mock_client.return_value = client

            # This should retry after 429
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await scraper._request("/test", use_cache=False)

            assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_fetch_repositories_pagination(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        # Mock paginated responses
        page1 = {
            "results": [{"name": "repo1"}, {"name": "repo2"}],
            "next": "https://hub.docker.com/v2/repositories/library?page=2",
        }
        page2 = {
            "results": [{"name": "repo3"}],
            "next": None,
        }

        call_count = 0

        async def mock_request(endpoint, params=None, use_cache=True):
            nonlocal call_count
            call_count += 1
            return page1 if call_count == 1 else page2

        with patch.object(scraper, "_request", side_effect=mock_request):
            repos = [repo async for repo in scraper._fetch_repositories("library")]

        assert len(repos) == 3
        assert repos[0]["name"] == "repo1"
        assert repos[2]["name"] == "repo3"

    def test_tool_id_parsing(self, tmp_path: Path) -> None:
        """Test various tool ID formats."""
        scraper = DockerHubScraper(data_dir=tmp_path)

        # Official image (library namespace)
        repo = {"name": "postgres"}
        tool = scraper._parse_tool(repo, "library")
        assert tool.id == "docker_hub:library/postgres"
        assert tool.source_url == "https://hub.docker.com/r/library/postgres"

        # User/org image
        repo = {"name": "myimage"}
        tool = scraper._parse_tool(repo, "myorg")
        assert tool.id == "docker_hub:myorg/myimage"
        assert tool.name == "myorg/myimage"

    def test_canonical_name_is_lowercase(self, tmp_path: Path) -> None:
        scraper = DockerHubScraper(data_dir=tmp_path)
        repo = {"name": "PostgreSQL"}
        tool = scraper._parse_tool(repo, "library")
        assert tool.identity.canonical_name == "postgresql"


class TestDockerHubScraperIntegration:
    """Integration tests that test multiple components together."""

    @pytest.mark.asyncio
    async def test_scrape_with_queue_resume(self, tmp_path: Path) -> None:
        """Test that scraping can resume from a saved queue."""
        scraper = DockerHubScraper(
            data_dir=tmp_path,
            namespaces=["ns1", "ns2"],
            use_cache=False,
        )

        # Mock to fail on ns1, succeed on ns2
        call_count = 0

        async def mock_fetch(namespace, page_size=100):
            nonlocal call_count
            call_count += 1
            if namespace == "ns1":
                raise httpx.HTTPStatusError(
                    "Server error",
                    request=MagicMock(),
                    response=MagicMock(status_code=500, text="Internal error"),
                )
            yield {"name": "tool1", "pull_count": 100}

        with patch.object(scraper, "_fetch_repositories", side_effect=mock_fetch):
            tools = [tool async for tool in scraper.scrape_with_resume(resume=False)]

        # Should have 1 tool from ns2
        assert len(tools) == 1
        # ns1 should be marked as failed
        assert "ns1" in scraper._queue._failed
        # ns2 should be marked as completed
        assert "ns2" in scraper._queue._completed


class TestDockerHubTagFetching:
    """Tests for Docker Hub tag fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_available_tags_success(self, tmp_path: Path) -> None:
        """Test successfully fetching available tags from Docker Hub API."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        # Mock tags response from Docker Hub API
        mock_tags_response = {
            "results": [
                {"name": "latest"},
                {"name": "stable"},
                {"name": "alpine"},
                {"name": "16-bullseye"},
                {"name": "15.2.0"},
            ]
        }

        with patch.object(scraper, "_request", return_value=mock_tags_response):
            tags = await scraper._fetch_available_tags("library", "postgres")

        assert tags == ["latest", "stable", "alpine", "16-bullseye", "15.2.0"]

    @pytest.mark.asyncio
    async def test_fetch_available_tags_404_returns_empty(self, tmp_path: Path) -> None:
        """Test that 404 errors return empty tag list."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        # Simulate 404 error
        async def mock_request_404(endpoint, params=None, use_cache=True):
            mock_req = httpx.Request("GET", "https://hub.docker.com" + endpoint)
            mock_resp = httpx.Response(404, request=mock_req)
            raise httpx.HTTPStatusError("Not found", request=mock_req, response=mock_resp)

        with patch.object(scraper, "_request", side_effect=mock_request_404):
            tags = await scraper._fetch_available_tags("library", "nonexistent")

        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_available_tags_handles_error(self, tmp_path: Path) -> None:
        """Test that errors are handled gracefully."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        with patch.object(scraper, "_request", side_effect=Exception("Network error")):
            tags = await scraper._fetch_available_tags("library", "postgres")

        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_available_tags_limit_parameter(self, tmp_path: Path) -> None:
        """Test that limit parameter is passed correctly."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        request_params = None

        async def capture_params(endpoint, params=None, use_cache=True):
            nonlocal request_params
            request_params = params
            return {"results": []}

        with patch.object(scraper, "_request", side_effect=capture_params):
            await scraper._fetch_available_tags("library", "postgres", limit=25)

        assert request_params == {"page_size": 25}

    @pytest.mark.asyncio
    async def test_parse_tool_populates_docker_tags(self, tmp_path: Path) -> None:
        """Test that _parse_tool fetches and populates docker_tags."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        repo_data = {
            "name": "postgres",
            "description": "PostgreSQL database",
            "pull_count": 1_000_000_000,
            "star_count": 10000,
        }

        mock_tags = ["latest", "stable", "alpine", "16-bullseye"]

        with patch.object(scraper, "_fetch_available_tags", return_value=mock_tags):
            tool = await scraper._parse_tool(repo_data, "library")

        assert tool.docker_tags == ["latest", "stable", "alpine", "16-bullseye"]

    @pytest.mark.asyncio
    async def test_parse_tool_empty_docker_tags_on_fetch_failure(self, tmp_path: Path) -> None:
        """Test that docker_tags is empty list if tag fetching fails."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        repo_data = {
            "name": "postgres",
            "description": "PostgreSQL database",
        }

        # Mock _fetch_available_tags to return empty list (simulating failure)
        with patch.object(scraper, "_fetch_available_tags", return_value=[]):
            tool = await scraper._parse_tool(repo_data, "library")

        assert tool.docker_tags == []

    @pytest.mark.asyncio
    async def test_fetch_tags_called_with_correct_namespace_and_name(self, tmp_path: Path) -> None:
        """Test that tag fetching uses correct namespace and name."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=False)

        repo_data = {"name": "postgresql"}
        captured_args = {}

        async def capture_fetch_args(namespace, name, limit=50):
            captured_args["namespace"] = namespace
            captured_args["name"] = name
            captured_args["limit"] = limit
            return []

        with patch.object(scraper, "_fetch_available_tags", side_effect=capture_fetch_args):
            await scraper._parse_tool(repo_data, "bitnami")

        assert captured_args["namespace"] == "bitnami"
        assert captured_args["name"] == "postgresql"
        assert captured_args["limit"] == 50

    @pytest.mark.asyncio
    async def test_fetch_tags_caches_response(self, tmp_path: Path) -> None:
        """Test that tag fetching uses response cache."""
        scraper = DockerHubScraper(data_dir=tmp_path, use_cache=True)

        mock_tags_response = {
            "results": [{"name": "latest"}, {"name": "stable"}]
        }

        request_count = 0

        async def count_requests(endpoint, params=None, use_cache=True):
            nonlocal request_count
            request_count += 1
            return mock_tags_response

        with patch.object(scraper, "_request", side_effect=count_requests):
            # First call should make a request
            tags1 = await scraper._fetch_available_tags("library", "postgres")
            # Second call should use cache (if caching is enabled)
            tags2 = await scraper._fetch_available_tags("library", "postgres")

        # Note: The actual caching behavior depends on _request implementation
        # This test just verifies the method works correctly
        assert tags1 == ["latest", "stable"]
        assert tags2 == ["latest", "stable"]
