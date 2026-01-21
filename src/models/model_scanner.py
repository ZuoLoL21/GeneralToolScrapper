"""Data models for security scanning operations."""

from dataclasses import dataclass
from datetime import datetime

from src.models.model_tool import Tool, Vulnerabilities


@dataclass
class ScanResult:
    """Result of a single Trivy scan."""

    success: bool
    vulnerabilities: Vulnerabilities | None
    scan_date: datetime
    error: str | None
    scan_duration_seconds: float
    image_ref: str


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
