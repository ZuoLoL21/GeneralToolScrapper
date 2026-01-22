"""Tests for TrivyScanner with scanned tag tracking."""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.model_scanner import ScanResult
from src.models.model_tool import Vulnerabilities
from src.scanner.trivy_scanner import TrivyScanner


class TestTrivyScanner:
    """Tests for TrivyScanner class."""

    @pytest.fixture
    def mock_trivy_output(self) -> str:
        """Sample Trivy JSON output."""
        return json.dumps(
            {
                "Results": [
                    {
                        "Vulnerabilities": [
                            {"Severity": "CRITICAL"},
                            {"Severity": "CRITICAL"},
                            {"Severity": "HIGH"},
                            {"Severity": "HIGH"},
                            {"Severity": "HIGH"},
                            {"Severity": "MEDIUM"},
                            {"Severity": "MEDIUM"},
                            {"Severity": "LOW"},
                        ]
                    }
                ]
            }
        )

    def test_parse_trivy_output(self, mock_trivy_output: str) -> None:
        """Test parsing Trivy JSON output."""
        scanner = TrivyScanner()
        vulnerabilities = scanner._parse_trivy_output(mock_trivy_output)

        assert vulnerabilities.critical == 2
        assert vulnerabilities.high == 3
        assert vulnerabilities.medium == 2
        assert vulnerabilities.low == 1

    def test_parse_trivy_output_empty(self) -> None:
        """Test parsing Trivy output with no vulnerabilities."""
        scanner = TrivyScanner()
        empty_output = json.dumps({"Results": []})
        vulnerabilities = scanner._parse_trivy_output(empty_output)

        assert vulnerabilities.critical == 0
        assert vulnerabilities.high == 0
        assert vulnerabilities.medium == 0
        assert vulnerabilities.low == 0

    def test_parse_trivy_output_invalid_json(self) -> None:
        """Test parsing invalid JSON returns empty vulnerabilities."""
        scanner = TrivyScanner()
        vulnerabilities = scanner._parse_trivy_output("not valid json")

        assert vulnerabilities.critical == 0
        assert vulnerabilities.high == 0
        assert vulnerabilities.medium == 0
        assert vulnerabilities.low == 0

    @pytest.mark.asyncio
    async def test_scan_image_extracts_tag_from_image_ref(self, mock_trivy_output: str) -> None:
        """Test that scan_image extracts tag from image reference."""
        scanner = TrivyScanner()

        # Mock the _scan_remote method to return success (without scanned_tag)
        # scan_image() will extract and set the tag
        async def mock_scan_remote(image_ref):
            return ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(critical=2, high=3, medium=2, low=1),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=5.0,
                image_ref=image_ref,
            )

        with patch.object(scanner, "_scan_remote", side_effect=mock_scan_remote):
            result = await scanner.scan_image("postgres:stable")

            assert result.success is True
            assert result.scanned_tag == "stable"
            assert result.image_ref == "postgres:stable"

    @pytest.mark.asyncio
    async def test_scan_image_extracts_tag_alpine(self, mock_trivy_output: str) -> None:
        """Test tag extraction for alpine variant."""
        scanner = TrivyScanner()

        async def mock_scan_remote(image_ref):
            return ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=3.0,
                image_ref=image_ref,
            )

        with patch.object(scanner, "_scan_remote", side_effect=mock_scan_remote):
            result = await scanner.scan_image("redis:alpine")

            assert result.scanned_tag == "alpine"

    @pytest.mark.asyncio
    async def test_scan_image_extracts_tag_versioned(self) -> None:
        """Test tag extraction for versioned tag."""
        scanner = TrivyScanner()

        async def mock_scan_remote(image_ref):
            return ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=4.0,
                image_ref=image_ref,
            )

        with patch.object(scanner, "_scan_remote", side_effect=mock_scan_remote):
            result = await scanner.scan_image("bitnami/postgresql:15.2.0")

            assert result.scanned_tag == "15.2.0"

    @pytest.mark.asyncio
    async def test_scan_image_no_tag_in_ref(self) -> None:
        """Test handling of image reference without tag."""
        scanner = TrivyScanner()

        mock_result = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=2.0,
            image_ref="nginx",
        )

        with patch.object(scanner, "_scan_remote", return_value=mock_result):
            result = await scanner.scan_image("nginx")

            # Should be None if no colon in image_ref
            assert result.scanned_tag is None

    @pytest.mark.asyncio
    async def test_scan_image_fallback_to_local_preserves_tag(self, mock_trivy_output: str) -> None:
        """Test that tag is preserved when falling back to local scan."""
        scanner = TrivyScanner()

        # Mock remote scan to fail
        mock_remote_fail = ScanResult(
            success=False,
            vulnerabilities=None,
            scan_date=datetime.now(UTC),
            error="Remote scan failed",
            scan_duration_seconds=1.0,
            image_ref="postgres:stable",
        )

        # Mock local scan to succeed
        mock_local_success = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(critical=1, high=2, medium=3, low=4),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=10.0,
            image_ref="postgres:stable",
        )

        with patch.object(scanner, "_scan_remote", return_value=mock_remote_fail), \
             patch.object(scanner, "_scan_local", return_value=mock_local_success):
            result = await scanner.scan_image("postgres:stable")

            assert result.success is True
            assert result.scanned_tag == "stable"
            assert result.image_ref == "postgres:stable"

    @pytest.mark.asyncio
    async def test_scan_image_error_preserves_tag(self) -> None:
        """Test that tag is preserved even when scan fails."""
        scanner = TrivyScanner()

        mock_fail = ScanResult(
            success=False,
            vulnerabilities=None,
            scan_date=datetime.now(UTC),
            error="Scan failed",
            scan_duration_seconds=1.0,
            image_ref="nonexistent:edge",
        )

        with patch.object(scanner, "_scan_remote", return_value=mock_fail), \
             patch.object(scanner, "_scan_local", return_value=mock_fail):
            result = await scanner.scan_image("nonexistent:edge")

            assert result.success is False
            assert result.scanned_tag == "edge"
            assert result.error == "Scan failed"

    @pytest.mark.asyncio
    async def test_scan_image_extracts_digest_from_image_ref(self) -> None:
        """Test that scan_image extracts digest from digest reference."""
        scanner = TrivyScanner()

        async def mock_scan_remote(image_ref):
            return ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(critical=1, high=2, medium=1, low=0),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=5.0,
                image_ref=image_ref,
            )

        with patch.object(scanner, "_scan_remote", side_effect=mock_scan_remote):
            result = await scanner.scan_image("postgres@sha256:abc123def456")

            assert result.success is True
            assert result.scanned_digest == "sha256:abc123def456"
            assert result.scanned_tag is None  # No tag when using digest
            assert result.image_ref == "postgres@sha256:abc123def456"

    @pytest.mark.asyncio
    async def test_scan_image_digest_with_namespace(self) -> None:
        """Test digest extraction for image with namespace."""
        scanner = TrivyScanner()

        async def mock_scan_remote(image_ref):
            return ScanResult(
                success=True,
                vulnerabilities=Vulnerabilities(),
                scan_date=datetime.now(UTC),
                error=None,
                scan_duration_seconds=3.0,
                image_ref=image_ref,
            )

        with patch.object(scanner, "_scan_remote", side_effect=mock_scan_remote):
            result = await scanner.scan_image("bitnami/postgresql@sha256:xyz789uvw321")

            assert result.scanned_digest == "sha256:xyz789uvw321"
            assert result.scanned_tag is None

    @pytest.mark.asyncio
    async def test_scan_image_fallback_to_local_preserves_digest(self) -> None:
        """Test that digest is preserved when falling back to local scan."""
        scanner = TrivyScanner()

        # Mock remote scan to fail
        mock_remote_fail = ScanResult(
            success=False,
            vulnerabilities=None,
            scan_date=datetime.now(UTC),
            error="Remote scan failed",
            scan_duration_seconds=1.0,
            image_ref="postgres@sha256:test123",
        )

        # Mock local scan to succeed
        mock_local_success = ScanResult(
            success=True,
            vulnerabilities=Vulnerabilities(critical=0, high=1, medium=2, low=3),
            scan_date=datetime.now(UTC),
            error=None,
            scan_duration_seconds=10.0,
            image_ref="postgres@sha256:test123",
        )

        with patch.object(scanner, "_scan_remote", return_value=mock_remote_fail), \
             patch.object(scanner, "_scan_local", return_value=mock_local_success):
            result = await scanner.scan_image("postgres@sha256:test123")

            assert result.success is True
            assert result.scanned_digest == "sha256:test123"
            assert result.scanned_tag is None
            assert result.image_ref == "postgres@sha256:test123"

    def test_is_trivy_installed(self) -> None:
        """Test Trivy installation check."""
        scanner = TrivyScanner(trivy_path="trivy")

        # Mock shutil.which
        with patch("shutil.which", return_value="/usr/bin/trivy"):
            assert scanner.is_trivy_installed() is True

        with patch("shutil.which", return_value=None):
            assert scanner.is_trivy_installed() is False
