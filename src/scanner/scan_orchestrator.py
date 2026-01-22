"""Orchestrates batch scanning with filtering, concurrency, and progress tracking."""

import asyncio
import logging
import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.consts import DEFAULT_DATA_DIR, TRIVY_CONCURRENCY, TRIVY_UNSCANNABLE_IMAGES
from src.models.model_scanner import ScanBatchResult, ScanErrorType
from src.models.model_tool import SecurityStatus, SourceType, Tool
from src.scanner.image_resolver import ImageResolver
from src.scanner.scan_cache import ScanCache
from src.scanner.trivy_scanner import TrivyScanner
from src.storage.permanent_storage.file_manager import FileManager

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    """Orchestrates batch scanning with filtering and progress tracking."""

    def __init__(
        self,
        scanner: TrivyScanner,
        resolver: ImageResolver,
        scan_cache: ScanCache,
        file_manager: FileManager,
        staleness_days: int = 7,
    ):
        """Initialize ScanOrchestrator.

        Args:
            scanner: TrivyScanner instance
            resolver: ImageResolver instance
            scan_cache: ScanCache instance
            file_manager: FileManager instance for incremental saving
            staleness_days: Days after which to re-scan (default: 7)
        """
        self.scanner = scanner
        self.resolver = resolver
        self.scan_cache = scan_cache
        self.file_manager = file_manager
        self.staleness_days = staleness_days

    def _get_cache_ttl_for_error(self, error_type: ScanErrorType) -> int:
        """Determine cache TTL based on error type.

        Permanent errors (manifest not found, image not found) get longer TTL (7 days).
        Transient errors (network, rate limit, cache lock) get shorter TTL (1 hour).

        Args:
            error_type: The classified error type

        Returns:
            TTL in seconds
        """
        # Permanent errors - cache for 7 days
        if error_type in [
            ScanErrorType.IMAGE_NOT_FOUND,
            ScanErrorType.MANIFEST_UNKNOWN,
            ScanErrorType.UNSCANNABLE_IMAGE,
            ScanErrorType.UNAUTHORIZED,
        ]:
            return 7 * 24 * 3600  # 7 days

        # Transient errors - cache for 1 hour (default)
        return 3600  # 1 hour

    def _create_temp_cache_dir(self) -> Path:
        """Create a temporary cache directory for this scan batch.

        Creates: data/cache/trivy_cache_{timestamp}

        Returns:
            Path to the created cache directory
        """
        timestamp = int(time.time())
        cache_dir = Path(DEFAULT_DATA_DIR) / "cache" / f"trivy_cache_{timestamp}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created temporary Trivy cache directory: {cache_dir}")
        return cache_dir

    def _cleanup_cache_dir(self, cache_dir: Path) -> None:
        """Clean up temporary cache directory after scanning.

        Args:
            cache_dir: Path to cache directory to remove
        """
        try:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                logger.info(f"Cleaned up cache directory: {cache_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup cache directory {cache_dir}: {e}")

    def filter_tools_needing_scan(
        self,
        tools: list[Tool],
        force: bool = False,
    ) -> list[Tool]:
        """Filter to tools needing scan.

        Criteria:
        - Docker Hub tools only
        - security.status == UNKNOWN, OR
        - security.trivy_scan_date is None, OR
        - trivy_scan_date older than staleness_days, AND
        - Not in failed scan cache

        Args:
            tools: List of tools to filter
            force: If True, re-scan all Docker Hub tools regardless of staleness

        Returns:
            Filtered list of tools needing scan
        """
        if force:
            # Force mode: scan all Docker Hub tools
            filtered = [t for t in tools if t.source == SourceType.DOCKER_HUB]
            logger.info(f"Force mode: {len(filtered)} Docker Hub tools to scan")
            return filtered

        now = datetime.now(UTC)
        staleness_threshold = now - timedelta(days=self.staleness_days)
        needs_scan = []

        for tool in tools:
            # Only Docker Hub tools
            if tool.source != SourceType.DOCKER_HUB:
                continue

            # Skip unscannable images (e.g., scratch)
            if tool.id in TRIVY_UNSCANNABLE_IMAGES:
                logger.debug(f"Skipping {tool.id} (unscannable image)")
                continue

            # Skip deprecated image formats (manifest schema v1)
            if tool.is_deprecated_image_format:
                logger.debug(f"Skipping {tool.id} (deprecated manifest schema v1)")
                continue

            # Skip if in failure cache
            if self.scan_cache.is_failed(tool.id):
                logger.debug(f"Skipping {tool.id} (cached failure)")
                continue

            # Check if needs scan
            if tool.security.status == SecurityStatus.UNKNOWN:
                needs_scan.append(tool)
                logger.debug(f"Adding {tool.id} (status UNKNOWN)")
            elif tool.security.trivy_scan_date is None:
                needs_scan.append(tool)
                logger.debug(f"Adding {tool.id} (never scanned)")
            elif tool.security.trivy_scan_date < staleness_threshold:
                needs_scan.append(tool)
                logger.debug(f"Adding {tool.id} (stale scan)")

        logger.info(f"Filtered {len(needs_scan)} tools needing scan from {len(tools)} total")
        return needs_scan

    async def scan_batch(
        self,
        tools: list[Tool],
        concurrency: int = TRIVY_CONCURRENCY,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ScanBatchResult:
        """Scan tools with concurrency control and isolated cache.

        Uses asyncio.Semaphore to limit parallel scans.
        Calls progress_callback(current, total) for CLI updates.
        Creates temporary cache directory to avoid lock conflicts.

        Args:
            tools: List of tools to scan
            concurrency: Maximum concurrent scans
            progress_callback: Optional callback for progress updates (current, total)

        Returns:
            ScanBatchResult with aggregated results
        """
        start_time = time.time()

        # Create temporary cache directory for this batch
        cache_dir = self._create_temp_cache_dir()

        # Set cache directory on scanner
        original_cache_dir = self.scanner.cache_dir
        self.scanner.cache_dir = cache_dir

        try:
            semaphore = asyncio.Semaphore(concurrency)
            updated_tools: list[Tool] = []
            failures: dict[str, str] = {}
            succeeded = 0
            failed = 0
            skipped = 0
            completed = 0

            async def scan_one(tool: Tool) -> Tool | None:
                """Scan a single tool."""
                nonlocal completed, succeeded, failed, skipped

                async with semaphore:
                    # Check failure cache
                    if self.scan_cache.is_failed(tool.id):
                        logger.debug(f"Skipping {tool.id} (cached failure)")
                        skipped += 1
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, len(tools))
                        return None

                    # Resolve image reference
                    result_tuple = self.resolver.resolve_image_ref(tool)
                    if not result_tuple:
                        logger.warning(f"Could not resolve image for {tool.id}")
                        failures[tool.id] = "Could not resolve image reference"
                        failed += 1
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, len(tools))
                        return None

                    image_ref, selected_tag = result_tuple

                    # Scan
                    logger.info(f"Scanning {tool.id} ({image_ref}, tag={selected_tag})...")
                    result = await self.scanner.scan_image(image_ref)

                    # Update or cache failure
                    if result.success:
                        updated_tool = self.update_tool_security(tool, result)
                        logger.info(
                            f"✓ {tool.id}: {result.vulnerabilities.critical}C "
                            f"{result.vulnerabilities.high}H {result.vulnerabilities.medium}M "
                            f"{result.vulnerabilities.low}L"
                        )

                        # Save immediately (incremental save)
                        try:
                            self.file_manager.save_processed([updated_tool], merge=True)
                            logger.debug(f"Saved scan result for {tool.id}")
                        except Exception as e:
                            logger.warning(f"Failed to save {tool.id}: {e}")
                            # Don't fail the scan if save fails

                        succeeded += 1
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, len(tools))
                        return updated_tool
                    else:
                        # Determine cache TTL based on error type
                        cache_ttl = self._get_cache_ttl_for_error(result.error_type)
                        self.scan_cache.mark_failed(
                            tool.id, result.error or "Unknown error", ttl=cache_ttl
                        )
                        failures[tool.id] = result.error or "Unknown error"
                        logger.warning(f"✗ {tool.id}: {result.error} (type: {result.error_type.value})")
                        failed += 1
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, len(tools))
                        return None

            # Run all scans concurrently
            results = await asyncio.gather(*[scan_one(tool) for tool in tools])

            # Filter out None results
            updated_tools = [r for r in results if r is not None]

            duration = time.time() - start_time

            return ScanBatchResult(
                total=len(tools),
                succeeded=succeeded,
                failed=failed,
                skipped=skipped,
                updated_tools=updated_tools,
                failures=failures,
                duration_seconds=duration,
            )

        finally:
            # Restore original cache dir and cleanup
            self.scanner.cache_dir = original_cache_dir
            self._cleanup_cache_dir(cache_dir)

    def update_tool_security(self, tool: Tool, scan_result) -> Tool:
        """Update tool.security with scan results.

        On success:
        - Set vulnerabilities counts
        - Set status (OK if no critical/high, VULNERABLE otherwise)
        - Set trivy_scan_date to now
        - Set scanned_tag to the tag that was scanned

        On failure:
        - Keep existing status (don't overwrite)
        - Don't update trivy_scan_date
        - Cache failure via ScanCache

        Args:
            tool: Tool to update
            scan_result: ScanResult from Trivy scan

        Returns:
            Updated Tool (new instance via model_copy)
        """
        # Create updated security object
        new_security = tool.security.model_copy()
        new_security.vulnerabilities = scan_result.vulnerabilities
        new_security.trivy_scan_date = scan_result.scan_date
        new_security.scanned_tag = scan_result.scanned_tag
        new_security.scanned_digest = scan_result.scanned_digest

        # Determine status based on vulnerabilities
        if scan_result.vulnerabilities.critical > 0 or scan_result.vulnerabilities.high > 0:
            new_security.status = SecurityStatus.VULNERABLE
        else:
            new_security.status = SecurityStatus.OK

        # Return updated tool
        return tool.model_copy(update={"security": new_security})


async def main():
    """Example usage of ScanOrchestrator."""
    from pathlib import Path

    from src.consts import DEFAULT_DATA_DIR
    from src.models.model_tool import Identity, Maintainer, MaintainerType, Metrics, Security
    from src.storage.cache.file_caching import FileCache

    # Setup
    cache_dir = Path(DEFAULT_DATA_DIR) / "cache"
    file_cache = FileCache(cache_dir=cache_dir, default_ttl=0)
    scan_cache = ScanCache(file_cache, failed_scan_ttl=3600)
    resolver = ImageResolver()
    scanner = TrivyScanner()
    file_manager = FileManager()
    orchestrator = ScanOrchestrator(scanner, resolver, scan_cache, file_manager, staleness_days=7)

    # Check Trivy
    if not scanner.is_trivy_installed():
        print("Error: Trivy is not installed")
        return

    # Create test tools
    test_tools = [
        Tool(
            id="docker_hub:library/alpine",
            name="alpine",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/alpine",
            description="Alpine Linux",
            identity=Identity(canonical_name="alpine"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
        ),
        Tool(
            id="docker_hub:library/busybox",
            name="busybox",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/busybox",
            description="BusyBox",
            identity=Identity(canonical_name="busybox"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
        ),
    ]

    # Filter tools needing scan
    print(f"Total tools: {len(test_tools)}")
    tools_to_scan = orchestrator.filter_tools_needing_scan(test_tools)
    print(f"Tools needing scan: {len(tools_to_scan)}\n")

    # Progress callback
    def on_progress(current: int, total: int):
        print(f"Progress: {current}/{total}")

    # Scan batch
    print("Starting batch scan...\n")
    result = await orchestrator.scan_batch(
        tools_to_scan,
        concurrency=2,
        progress_callback=on_progress,
    )

    # Display results
    print(f"\n{'=' * 60}")
    print("Scan Complete")
    print(f"{'=' * 60}")
    print(f"Total: {result.total}")
    print(f"Succeeded: {result.succeeded}")
    print(f"Failed: {result.failed}")
    print(f"Skipped: {result.skipped}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.failures:
        print("\nFailures:")
        for tool_id, error in result.failures.items():
            print(f"  {tool_id}: {error}")

    print(f"\nUpdated tools: {len(result.updated_tools)}")
    for tool in result.updated_tools:
        vulns = tool.security.vulnerabilities
        print(
            f"  {tool.name}: {vulns.critical}C {vulns.high}H "
            f"{vulns.medium}M {vulns.low}L - {tool.security.status.value}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
