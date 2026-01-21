"""Trivy CLI wrapper for Docker image vulnerability scanning."""

import asyncio
import json
import logging
import shutil
import time
from datetime import UTC, datetime

from src.models.model_scanner import ScanResult
from src.models.model_tool import Vulnerabilities

logger = logging.getLogger(__name__)


class TrivyScanner:
    """Wraps Trivy CLI for scanning Docker images."""

    def __init__(
        self,
        trivy_path: str = "trivy",
        timeout: int = 300,
        try_remote_first: bool = True,
    ):
        """Initialize TrivyScanner.

        Args:
            trivy_path: Path to trivy executable (default: "trivy")
            timeout: Scan timeout in seconds (default: 300)
            try_remote_first: Whether to try remote scan before local (default: True)
        """
        self.trivy_path = trivy_path
        self.timeout = timeout
        self.try_remote_first = try_remote_first

    def is_trivy_installed(self) -> bool:
        """Check if Trivy is installed and accessible.

        Returns:
            True if Trivy is installed, False otherwise
        """
        return shutil.which(self.trivy_path) is not None

    async def scan_image(
        self,
        image_ref: str,
        try_remote_first: bool | None = None,
    ) -> ScanResult:
        """Scan Docker image using Trivy.

        Strategy:
        1. Try remote: trivy image --scanners vuln <image>
        2. If fails: docker pull + trivy image <image>
        3. Parse JSON output → Vulnerabilities

        Args:
            image_ref: Docker image reference (e.g., "postgres:latest")
            try_remote_first: Override instance setting for remote-first strategy

        Returns:
            ScanResult with success status and vulnerability data
        """
        start_time = time.time()
        use_remote = try_remote_first if try_remote_first is not None else self.try_remote_first

        logger.info(f"Scanning image: {image_ref}")

        # Try remote scan first if enabled
        if use_remote:
            logger.debug(f"Attempting remote scan for {image_ref}")
            result = await self._scan_remote(image_ref)
            if result.success:
                return result
            logger.warning(f"Remote scan failed for {image_ref}, falling back to local")

        # Fallback to local scan
        logger.debug(f"Attempting local scan for {image_ref}")
        result = await self._scan_local(image_ref)

        # Update duration
        duration = time.time() - start_time
        return ScanResult(
            success=result.success,
            vulnerabilities=result.vulnerabilities,
            scan_date=result.scan_date,
            error=result.error,
            scan_duration_seconds=duration,
            image_ref=image_ref,
        )

    async def _scan_remote(self, image_ref: str) -> ScanResult:
        """Try scanning without pulling the image (remote scan).

        Args:
            image_ref: Docker image reference

        Returns:
            ScanResult
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

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Scan timeout ({self.timeout}s)",
                    scan_duration_seconds=self.timeout,
                    image_ref=image_ref,
                )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.debug(f"Remote scan failed: {error_msg}")
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Trivy error (code {process.returncode}): {error_msg[:200]}",
                    scan_duration_seconds=0,
                    image_ref=image_ref,
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
            return ScanResult(
                success=False,
                vulnerabilities=None,
                scan_date=datetime.now(UTC),
                error=f"Remote scan error: {str(e)[:200]}",
                scan_duration_seconds=0,
                image_ref=image_ref,
            )

    async def _scan_local(self, image_ref: str) -> ScanResult:
        """Pull image and scan locally.

        Args:
            image_ref: Docker image reference

        Returns:
            ScanResult
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
            except asyncio.TimeoutError:
                pull_process.kill()
                await pull_process.wait()
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Docker pull timeout ({self.timeout}s)",
                    scan_duration_seconds=self.timeout,
                    image_ref=image_ref,
                )

            if pull_process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.debug(f"Docker pull failed: {error_msg}")
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Docker pull error: {error_msg[:200]}",
                    scan_duration_seconds=0,
                    image_ref=image_ref,
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

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Scan timeout ({self.timeout}s)",
                    scan_duration_seconds=self.timeout,
                    image_ref=image_ref,
                )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.debug(f"Local scan failed: {error_msg}")
                return ScanResult(
                    success=False,
                    vulnerabilities=None,
                    scan_date=datetime.now(UTC),
                    error=f"Trivy error (code {process.returncode}): {error_msg[:200]}",
                    scan_duration_seconds=0,
                    image_ref=image_ref,
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
            return ScanResult(
                success=False,
                vulnerabilities=None,
                scan_date=datetime.now(UTC),
                error=f"Local scan error: {str(e)[:200]}",
                scan_duration_seconds=0,
                image_ref=image_ref,
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
        print("Install from: https://aquasecurity.github.io/trivy/latest/getting-started/installation/")
        return

    print("Trivy is installed\n")

    # Scan a test image
    test_image = "alpine:latest"
    print(f"Scanning {test_image}...")

    result = await scanner.scan_image(test_image)

    print(f"\nScan result:")
    print(f"  Success: {result.success}")
    print(f"  Duration: {result.scan_duration_seconds:.2f}s")

    if result.success and result.vulnerabilities:
        print(f"  Vulnerabilities:")
        print(f"    Critical: {result.vulnerabilities.critical}")
        print(f"    High: {result.vulnerabilities.high}")
        print(f"    Medium: {result.vulnerabilities.medium}")
        print(f"    Low: {result.vulnerabilities.low}")
    elif result.error:
        print(f"  Error: {result.error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
