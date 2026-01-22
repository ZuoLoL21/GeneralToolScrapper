"""Data models for security scanning operations."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.models.model_tool import Tool, Vulnerabilities


class ScanErrorType(Enum):
    """Classification of scan error types for intelligent retry logic."""

    # Transient errors - retry immediately with exponential backoff
    NETWORK_TIMEOUT = "network_timeout"
    RATE_LIMIT = "rate_limit"
    CACHE_LOCK = "cache_lock"

    # Permanent errors - skip permanently, longer cache TTL
    IMAGE_NOT_FOUND = "image_not_found"
    MANIFEST_UNKNOWN = "manifest_unknown"
    UNSCANNABLE_IMAGE = "unscannable_image"
    UNAUTHORIZED = "unauthorized"

    # Infrastructure errors - special handling
    TRIVY_CRASH = "trivy_crash"
    DOCKER_PULL_FAILED = "docker_pull_failed"

    # Unknown/generic error
    UNKNOWN = "unknown"


@dataclass
class ScanResult:
    """Result of a single Trivy scan."""

    success: bool
    vulnerabilities: Vulnerabilities | None
    scan_date: datetime
    error: str | None
    scan_duration_seconds: float
    image_ref: str
    scanned_tag: str | None = None
    scanned_digest: str | None = None
    error_type: ScanErrorType = ScanErrorType.UNKNOWN
    retry_count: int = 0


@dataclass
class ScanBatchResult:
    """Result of scanning multiple tools."""

    total: int
    succeeded: int
    failed: int
    skipped: int
    updated_tools: list[Tool]
    failures: dict[str, str]  # tool_id → error
    duration_seconds: float
