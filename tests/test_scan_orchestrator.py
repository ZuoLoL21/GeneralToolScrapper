"""Tests for ScanOrchestrator with incremental saving."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.model_scanner import ScanResult
from src.models.model_tool import (
    Identity,
    Maintainer,
    MaintainerType,
    Metrics,
    Security,
    SecurityStatus,
    SourceType,
    Tool,
    Vulnerabilities,
)
from src.scanner.image_resolver import ImageResolver
from src.scanner.scan_cache import ScanCache
from src.scanner.scan_orchestrator import ScanOrchestrator
from src.scanner.trivy_scanner import TrivyScanner
from src.storage.cache.file_caching import FileCache
from src.storage.permanent_storage.file_manager import FileManager


class TestScanOrchestrator:
    """Tests for ScanOrchestrator class."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create temporary data directory for tests."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def file_manager(self, temp_data_dir: Path) -> FileManager:
        """Create FileManager with temp directory."""
        return FileManager(data_dir=temp_data_dir)

    @pytest.fixture
    def scan_cache(self, temp_data_dir: Path) -> ScanCache:
        """Create ScanCache with temp directory."""
        cache_dir = temp_data_dir / "cache"
        file_cache = FileCache(cache_dir=cache_dir, default_ttl=0)
        return ScanCache(file_cache, failed_scan_ttl=3600)

    @pytest.fixture
    def sample_tools(self) -> list[Tool]:
        """Create sample tools for testing."""
        return [
            Tool(
                id="docker_hub:library/postgres",
                name="postgres",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/_/postgres",
                description="PostgreSQL",
                identity=Identity(canonical_name="postgres"),
                maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
                metrics=Metrics(),
                security=Security(),
                docker_tags=["latest", "stable", "alpine"],
            ),
            Tool(
                id="docker_hub:library/redis",
                name="redis",
                source=SourceType.DOCKER_HUB,
                source_url="https://hub.docker.com/_/redis",
                description="Redis",
                identity=Identity(canonical_name="redis"),
                maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
                metrics=Metrics(),
                security=Security(),
                docker_tags=["latest", "alpine"],
            ),
        ]

    @pytest.mark.asyncio
    async def test_scan_batch_incremental_saving(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that scan_batch saves after each successful scan."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        # Mock successful scans
        scan_results = [
            ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(critical=1, high=2, medium=3, low=4),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=5.0,
                image_ref="postgres:stable",
                scanned_tag="stable",
            ),
            ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(critical=0, high=1, medium=2, low=3),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=4.0,
                image_ref="redis:alpine",
                scanned_tag="alpine",
            ),
        ]

        # Track save calls
        save_calls = []
        original_save = file_manager.save_processed

        def mock_save(tools, merge=True):
            save_calls.append(tools)
            return original_save(tools, merge=merge)

        with patch.object(file_manager, "save_processed", side_effect=mock_save), \
             patch.object(scanner, "scan_image", side_effect=scan_results):
            result = await orchestrator.scan_batch(sample_tools, concurrency=1)

            # Should have saved twice (once for each successful scan)
            assert len(save_calls) == 2
            assert result.succeeded == 2
            assert result.failed == 0

            # Each save should be a single tool
            assert len(save_calls[0]) == 1
            assert len(save_calls[1]) == 1

            # Verify scanned_tag was set
            assert save_calls[0][0].security.scanned_tag == "stable"
            assert save_calls[1][0].security.scanned_tag == "alpine"

    @pytest.mark.asyncio
    async def test_scan_batch_failed_save_doesnt_break_scan(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that failed save doesn't break the scan process."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        scan_result = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=3.0,
            image_ref="postgres:stable",
            scanned_tag="stable",
        )

        # Mock save_processed to raise exception
        with patch.object(file_manager, "save_processed", side_effect=Exception("Save failed")), \
             patch.object(scanner, "scan_image", return_value=scan_result):
            result = await orchestrator.scan_batch([sample_tools[0]], concurrency=1)

            # Scan should still succeed even though save failed
            assert result.succeeded == 1
            assert result.failed == 0
            assert len(result.updated_tools) == 1

    @pytest.mark.asyncio
    async def test_scan_batch_saves_with_merge_true(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that incremental saves use merge=True."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        scan_result = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=3.0,
            image_ref="postgres:stable",
            scanned_tag="stable",
        )

        # Capture merge parameter
        merge_values = []

        def capture_merge(tools, merge=True):
            merge_values.append(merge)
            return Path("/tmp/tools.json"), 0

        with patch.object(file_manager, "save_processed", side_effect=capture_merge), \
             patch.object(scanner, "scan_image", return_value=scan_result):
            await orchestrator.scan_batch([sample_tools[0]], concurrency=1)

            # Should have been called with merge=True
            assert len(merge_values) == 1
            assert merge_values[0] is True

    @pytest.mark.asyncio
    async def test_update_tool_security_sets_scanned_tag(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that update_tool_security sets scanned_tag."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        tool = sample_tools[0]
        scan_result = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(critical=2, high=3, medium=1, low=0),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=5.0,
            image_ref="postgres:stable",
            scanned_tag="stable",
        )

        updated_tool = orchestrator.update_tool_security(tool, scan_result)

        assert updated_tool.security.scanned_tag == "stable"
        assert updated_tool.security.status == SecurityStatus.VULNERABLE
        assert updated_tool.security.vulnerabilities.critical == 2
        assert updated_tool.security.vulnerabilities.high == 3

    @pytest.mark.asyncio
    async def test_scan_batch_crash_recovery(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that completed scans are saved before crash."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        # First scan succeeds, second scan crashes
        def mock_scan_image(image_ref):
            if "postgres" in image_ref:
                return ScanResult(
                    success=True,
                    vulnerabilities=Vulnerabilities(),
                    scan_date=datetime.now(UTC),
                    error=None,
                    scan_duration_seconds=3.0,
                    image_ref=image_ref,
                    scanned_tag="stable",
                )
            # Simulate crash on second scan
            raise Exception("Simulated crash")

        with patch.object(scanner, "scan_image", side_effect=mock_scan_image):
            try:
                await orchestrator.scan_batch(sample_tools, concurrency=1)
            except Exception:
                pass  # Expected to crash

            # First tool should have been saved before crash
            saved_tools = file_manager.load_processed()
            assert saved_tools is not None
            assert len(saved_tools) == 1
            assert saved_tools[0].id == "docker_hub:library/postgres"
            assert saved_tools[0].security.scanned_tag == "stable"

    @pytest.mark.asyncio
    async def test_scan_one_handles_tuple_from_resolver(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that scan_one properly unpacks tuple from resolve_image_ref."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        scan_result = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=3.0,
            image_ref="postgres:stable",
            scanned_tag="stable",
        )

        with patch.object(scanner, "scan_image", return_value=scan_result):
            result = await orchestrator.scan_batch([sample_tools[0]], concurrency=1)

            assert result.succeeded == 1
            assert len(result.updated_tools) == 1
            # Verify the tag was used from resolve_image_ref
            assert result.updated_tools[0].security.scanned_tag == "stable"

    def test_filter_tools_needing_scan(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test filtering tools that need scanning."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        # All tools have UNKNOWN status, should need scanning
        filtered = orchestrator.filter_tools_needing_scan(sample_tools)
        assert len(filtered) == 2

        # Mark one tool as scanned recently
        sample_tools[0].security.status = SecurityStatus.OK
        sample_tools[0].security.trivy_scan_date = datetime.now(UTC)

        filtered = orchestrator.filter_tools_needing_scan(sample_tools)
        # Only the unscanned tool should be filtered
        assert len(filtered) == 1
        assert filtered[0].id == "docker_hub:library/redis"

    def test_filter_tools_with_force_flag(
        self,
        file_manager: FileManager,
        scan_cache: ScanCache,
        sample_tools: list[Tool],
    ) -> None:
        """Test that force flag rescans all tools."""
        scanner = TrivyScanner()
        resolver = ImageResolver()
        orchestrator = ScanOrchestrator(
            scanner=scanner,
            resolver=resolver,
            scan_cache=scan_cache,
            file_manager=file_manager,
            staleness_days=7,
        )

        # Mark both tools as recently scanned
        for tool in sample_tools:
            tool.security.status = SecurityStatus.OK
            tool.security.trivy_scan_date = datetime.now(UTC)

        # Without force, should get 0 tools
        filtered = orchestrator.filter_tools_needing_scan(sample_tools, force=False)
        assert len(filtered) == 0

        # With force, should get all Docker Hub tools
        filtered = orchestrator.filter_tools_needing_scan(sample_tools, force=True)
        assert len(filtered) == 2
