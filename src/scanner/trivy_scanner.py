"""Trivy CLI wrapper for Docker image vulnerability scanning."""

import asyncio
import json
import logging
import os
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from src.consts import (
    TRIVY_CACHE_CLEANUP_THRESHOLD_SECONDS,
    TRIVY_MAX_CACHE_LOCK_RETRIES,
    TRIVY_RETRY_BASE_DELAY,
)
from src.models.model_scanner import ScanErrorType, ScanResult
from src.models.model_tool import Vulnerabilities

logger = logging.getLogger(__name__)


class TrivyScanner:
    """Wraps Trivy CLI for scanning Docker images."""

    def __init__(
        self,
        trivy_path: str = "trivy",
        timeout: int = 300,
        try_remote_first: bool = True,
        cache_dir: Path | str | None = None,
    ):
        """Initialize TrivyScanner.

        Args:
            trivy_path: Path to trivy executable (default: "trivy")
            timeout: Scan timeout in seconds (default: 300)
            try_remote_first: Whether to try remote scan before local (default: True)
            cache_dir: Custom cache directory for Trivy (default: None, uses Trivy's default)
                      Setting this enables cache isolation to prevent lock conflicts
        """
        self.trivy_path = trivy_path
        self.timeout = timeout
        self.try_remote_first = try_remote_first
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def is_trivy_installed(self) -> bool:
        """Check if Trivy is installed and accessible.

        Returns:
            True if Trivy is installed, False otherwise
        """
        return shutil.which(self.trivy_path) is not None

    def _classify_error(self, error_msg: str, returncode: int) -> ScanErrorType:
        """Classify error type based on Trivy stderr output.

        Args:
            error_msg: Error message from stderr
            returncode: Process return code

        Returns:
            ScanErrorType classification
        """
        error_lower = error_msg.lower()

        # Cache lock errors
        if "cache" in error_lower and "lock" in error_lower:
            return ScanErrorType.CACHE_LOCK
        if "timeout" in error_lower and "lock" in error_lower:
            return ScanErrorType.CACHE_LOCK

        # Manifest/image not found errors
        if re.search(r"manifest.*not found", error_lower):
            return ScanErrorType.MANIFEST_UNKNOWN
        if re.search(r"manifest.*unknown", error_lower):
            return ScanErrorType.MANIFEST_UNKNOWN
        if "not found" in error_lower and ("image" in error_lower or "repository" in error_lower):
            return ScanErrorType.IMAGE_NOT_FOUND

        # Network errors
        if "timeout" in error_lower or "timed out" in error_lower:
            return ScanErrorType.NETWORK_TIMEOUT
        if "network" in error_lower or "connection" in error_lower:
            return ScanErrorType.NETWORK_TIMEOUT

        # Rate limiting
        if "rate limit" in error_lower or "too many requests" in error_lower:
            return ScanErrorType.RATE_LIMIT

        # Authorization errors
        if "unauthorized" in error_lower or "forbidden" in error_lower:
            return ScanErrorType.UNAUTHORIZED

        # Unscannable images
        if "unsupported" in error_lower or "cannot scan" in error_lower:
            return ScanErrorType.UNSCANNABLE_IMAGE

        # Trivy crash (non-zero exit without clear error)
        if returncode != 0 and not error_msg.strip():
            return ScanErrorType.TRIVY_CRASH

        return ScanErrorType.UNKNOWN

    def _cleanup_stale_locks(self) -> None:
        """Clean up stale Trivy cache lock files.

        Removes lock files older than TRIVY_CACHE_CLEANUP_THRESHOLD_SECONDS.
        Only works with custom cache_dir (not Trivy's global cache).
        """
        if not self.cache_dir:
            logger.debug("No custom cache_dir set, skipping lock cleanup")
            return

        try:
            # Look for lock files in cache directory
            cache_path = Path(self.cache_dir)
            if not cache_path.exists():
                return

            lock_files = list(cache_path.rglob("*.lock"))
            now = time.time()

            for lock_file in lock_files:
                try:
                    # Check file age
                    file_age = now - lock_file.stat().st_mtime
                    if file_age > TRIVY_CACHE_CLEANUP_THRESHOLD_SECONDS:
                        logger.info(f"Removing stale lock file: {lock_file} (age: {file_age:.0f}s)")
                        lock_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove lock file {lock_file}: {e}")

        except Exception as e:
            logger.warning(f"Failed to cleanup stale locks: {e}")

    async def _retry_with_backoff(
        self,
        image_ref: str,
        scan_func,
        max_retries: int = TRIVY_MAX_CACHE_LOCK_RETRIES,
    ) -> ScanResult:
        """Retry scan with exponential backoff on transient errors.

        Args:
            image_ref: Docker image reference
            scan_func: Async function to call for scanning
            max_retries: Maximum retry attempts

        Returns:
            ScanResult from successful scan or final failure
        """
        retry_count = 0

        while retry_count <= max_retries:
            result = await scan_func(image_ref)

            # Success - return immediately
            if result.success:
                return result

            # Classify error
            error_type = self._classify_error(result.error or "", 0)

            # Only retry on transient errors
            if error_type not in [
                ScanErrorType.CACHE_LOCK,
                ScanErrorType.NETWORK_TIMEOUT,
                ScanErrorType.RATE_LIMIT,
            ]:
                # Permanent error - don't retry
                logger.debug(f"Non-retriable error type: {error_type.value}, giving up")
                return result

            # Check if we've exhausted retries
            if retry_count >= max_retries:
                logger.warning(
                    f"Max retries ({max_retries}) reached for {image_ref}, error: {error_type.value}"
                )
                return result

            # Calculate backoff delay
            delay = TRIVY_RETRY_BASE_DELAY * (2**retry_count)
            logger.info(
                f"Retry {retry_count + 1}/{max_retries} for {image_ref} "
                f"after {delay:.1f}s (error: {error_type.value})"
            )

            # Wait before retry
            await asyncio.sleep(delay)

            # Cleanup stale locks before retry (for cache lock errors)
            if error_type == ScanErrorType.CACHE_LOCK:
                self._cleanup_stale_locks()

            retry_count += 1

        # Should not reach here, but return last result
        return result

    async def scan_image(
        self,
        image_ref: str,
        try_remote_first: bool | None = None,
    ) -> ScanResult:
        """Scan Docker image using Trivy with retry logic.

        Supports both digest and tag references:
        - Digest: postgres@sha256:abc123...
        - Tag: postgres:latest

        Strategy:
        1. Try remote: trivy image --scanners vuln <image>
        2. If fails with transient error: retry with exponential backoff
        3. If fails permanently or remote doesn't work: docker pull + trivy image <image>
        4. Parse JSON output → Vulnerabilities

        Args:
            image_ref: Docker image reference (e.g., "postgres:latest" or "postgres@sha256:...")
            try_remote_first: Override instance setting for remote-first strategy

        Returns:
            ScanResult with success status and vulnerability data
        """
        start_time = time.time()
        use_remote = try_remote_first if try_remote_first is not None else self.try_remote_first

        # Extract digest or tag from image_ref
        scanned_tag = None
        scanned_digest = None

        if "@sha256:" in image_ref:
            # Digest reference
            scanned_digest = image_ref.split("@")[-1]
        elif ":" in image_ref:
            # Tag reference
            scanned_tag = image_ref.split(":")[-1]

        logger.info(f"Scanning image: {image_ref}")

        # Cleanup stale locks before starting
        self._cleanup_stale_locks()

        # Try remote scan first if enabled (with retry)
        if use_remote:
            logger.debug(f"Attempting remote scan for {image_ref}")
            result = await self._retry_with_backoff(image_ref, self._scan_remote)
            if result.success:
                # Update duration and add scanned_tag/digest
                duration = time.time() - start_time
                return ScanResult(
                    success=result.success,
                    vulnerabilities=result.vulnerabilities,
                    scan_date=result.scan_date,
                    error=result.error,
                    scan_duration_seconds=duration,
                    image_ref=image_ref,
                    scanned_tag=scanned_tag,
                    scanned_digest=scanned_digest,
                    error_type=result.error_type,
                    retry_count=result.retry_count,
                )
            # logger.warning(f"Remote scan failed for {image_ref}, falling back to local")

        # Fallback to local scan (with retry)
        logger.debug(f"Attempting local scan for {image_ref}")
        result = await self._retry_with_backoff(image_ref, self._scan_local)

        # Update duration and add scanned_tag/digest
        duration = time.time() - start_time
        return ScanResult(
            success=result.success,
            vulnerabilities=result.vulnerabilities,
            scan_date=result.scan_date,
            error=result.error,
            scan_duration_seconds=duration,
            image_ref=image_ref,
            scanned_tag=scanned_tag,
            scanned_digest=scanned_digest,
            error_type=result.error_type,
            retry_count=result.retry_count,
        )

    async def _scan_remote(self, image_ref: str) -> ScanResult:
        """Try scanning without pulling the image (remote scan).

        Args:
            image_ref: Docker image reference

        Returns:
            ScanResult with error classification
        """
        try:
            # Run Trivy with remote scanning (no pull)
            cmd = [
                self.trivy_path,
                "image",
                "--format",
                "json",
                "--severity",
                "CRITICAL,HIGH,MEDIUM,LOW",
                "--scanners",
                "vuln",
                image_ref,
            ]

            logger.debug(f"Running: {' '.join(cmd)}")

            # Set custom cache dir if configured
            env = os.environ.copy()
            if self.cache_dir:
                env["TRIVY_CACHE_DIR"] = str(self.cache_dir)
                logger.debug(f"Using custom cache dir: {self.cache_dir}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Scan timeout ({self.timeout}s)",
                    scan_duration_seconds=self.timeout,
                    image_ref=image_ref,
                    error_type=ScanErrorType.NETWORK_TIMEOUT,
                )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                error_type = self._classify_error(error_msg, process.returncode)
                logger.debug(f"Remote scan failed ({error_type.value}): {error_msg}")
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Trivy error (code {process.returncode}): {error_msg[:1000]}",
                    scan_duration_seconds=0,
                    image_ref=image_ref,
                    error_type=error_type,
                )

            # Parse output
            output = stdout.decode("utf-8", errors="replace")
            vulnerabilities = self._parse_trivy_output(output)

            return ScanResult(
                success=True,
                vulnerabilities=vulnerabilities,
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=0,
                image_ref=image_ref,
            )

        except Exception as e:
            logger.debug(f"Remote scan exception: {e}")
            error_type = self._classify_error(str(e), 0)
            return ScanResult(
                success=False,
                vulnerabilities=None,
                scan_date=datetime.now(UTC),
                error=f"Remote scan error: {str(e)[:1000]}",
                scan_duration_seconds=0,
                image_ref=image_ref,
                error_type=error_type,
            )

    async def _scan_local(self, image_ref: str) -> ScanResult:
        """Pull image and scan locally.

        Args:
            image_ref: Docker image reference

        Returns:
            ScanResult with error classification
        """
        try:
            # Pull image first
            logger.debug(f"Pulling image: {image_ref}")
            pull_cmd = ["docker", "pull", image_ref]

            pull_process = await asyncio.create_subprocess_exec(
                *pull_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    pull_process.communicate(),
                    timeout=self.timeout,
                )
            except TimeoutError:
                pull_process.kill()
                await pull_process.wait()
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Docker pull timeout ({self.timeout}s)",
                    scan_duration_seconds=self.timeout,
                    image_ref=image_ref,
                    error_type=ScanErrorType.NETWORK_TIMEOUT,
                )

            if pull_process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                error_type = self._classify_error(error_msg, pull_process.returncode)
                logger.debug(f"Docker pull failed ({error_type.value}): {error_msg}")
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Docker pull error: {error_msg[:1000]}",
                    scan_duration_seconds=0,
                    image_ref=image_ref,
                    error_type=ScanErrorType.DOCKER_PULL_FAILED,
                )

            # Now scan locally
            cmd = [
                self.trivy_path,
                "image",
                "--format",
                "json",
                "--severity",
                "CRITICAL,HIGH,MEDIUM,LOW",
                image_ref,
            ]

            logger.debug(f"Running: {' '.join(cmd)}")

            # Set custom cache dir if configured
            env = os.environ.copy()
            if self.cache_dir:
                env["TRIVY_CACHE_DIR"] = str(self.cache_dir)
                logger.debug(f"Using custom cache dir: {self.cache_dir}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Scan timeout ({self.timeout}s)",
                    scan_duration_seconds=self.timeout,
                    image_ref=image_ref,
                    error_type=ScanErrorType.NETWORK_TIMEOUT,
                )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                error_type = self._classify_error(error_msg, process.returncode)
                logger.debug(f"Local scan failed ({error_type.value}): {error_msg}")
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Trivy error (code {process.returncode}): {error_msg[:1000]}",
                    scan_duration_seconds=0,
                    image_ref=image_ref,
                    error_type=error_type,
                )

            # Parse output
            output = stdout.decode("utf-8", errors="replace")
            vulnerabilities = self._parse_trivy_output(output)

            return ScanResult(
                success=True,
                vulnerabilities=vulnerabilities,
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=0,
                image_ref=image_ref,
            )

        except Exception as e:
            logger.debug(f"Local scan exception: {e}")
            error_type = self._classify_error(str(e), 0)
            return ScanResult(
                success=False,
                vulnerabilities=None,
                scan_date=datetime.now(UTC),
                error=f"Local scan error: {str(e)[:1000]}",
                scan_duration_seconds=0,
                image_ref=image_ref,
                error_type=error_type,
            )

    def _parse_trivy_output(self, json_output: str) -> Vulnerabilities:
        """Parse Trivy JSON output to extract vulnerability counts.

        Args:
            json_output: JSON output from Trivy

        Returns:
            Vulnerabilities object with counts by severity
        """
        try:
            data = json.loads(json_output)
            counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

            # Trivy output structure: {"Results": [{"Vulnerabilities": [...]}]}
            for result in data.get("Results", []):
                for vuln in result.get("Vulnerabilities", []):
                    severity = vuln.get("Severity", "UNKNOWN")
                    if severity in counts:
                        counts[severity] += 1

            return Vulnerabilities(
                critical=counts["CRITICAL"],
                high=counts["HIGH"],
                medium=counts["MEDIUM"],
                low=counts["LOW"],
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Trivy JSON output: {e}")
            # Return empty vulnerabilities on parse error
            return Vulnerabilities()
        except Exception as e:
            logger.error(f"Unexpected error parsing Trivy output: {e}")
            return Vulnerabilities()


async def main():
    """Example usage of TrivyScanner."""
    scanner = TrivyScanner()

    # Check if Trivy is installed
    if not scanner.is_trivy_installed():
        print("Error: Trivy is not installed")
        print(
            "Install from: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        )
        return

    print("Trivy is installed\n")

    # Scan a test image
    test_image = "alpine:latest"
    print(f"Scanning {test_image}...")

    result = await scanner.scan_image(test_image)

    print("\nScan result:")
    print(f"  Success: {result.success}")
    print(f"  Duration: {result.scan_duration_seconds:.2f}s")

    if result.success and result.vulnerabilities:
        print("  Vulnerabilities:")
        print(f"    Critical: {result.vulnerabilities.critical}")
        print(f"    High: {result.vulnerabilities.high}")
        print(f"    Medium: {result.vulnerabilities.medium}")
        print(f"    Low: {result.vulnerabilities.low}")
    elif result.error:
        print(f"  Error: {result.error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
