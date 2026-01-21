"""Canonical identity resolution for tool artifacts.

Resolves the canonical name for tool artifacts, grouping related artifacts
across sources under a single identity. For example:
- docker_hub:library/postgres
- github:postgres/postgres
- helm:bitnami/postgresql

All share canonical_name: "postgres"
"""

import json
import logging
import re
from pathlib import Path
from typing import Final

from src.categorization.human_maintained import KNOWN_CANONICALS
from src.models.model_classification import IDENTITY_VERSION, IdentityResolution, ResolutionSource

logger = logging.getLogger(__name__)


# Confidence levels for each resolution source
RESOLUTION_CONFIDENCE: Final[dict[ResolutionSource, float]] = {
    ResolutionSource.OVERRIDE: 1.0,
    ResolutionSource.OFFICIAL: 0.95,
    ResolutionSource.VERIFIED: 0.85,
    ResolutionSource.FALLBACK: 0.6,
}


def _normalize_name(name: str) -> str:
    """Normalize a tool name for matching.

    - Lowercase
    - Remove common suffixes (-db, -server, -alpine, etc.)
    - Remove version numbers
    """
    name = name.lower().strip()

    # Remove common suffixes
    suffixes = [
        "-alpine",
        "-slim",
        "-buster",
        "-bullseye",
        "-db",
        "-server",
        "-client",
        "-official",
        "-docker",
        "-image",
        "-container",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    # Remove version patterns at the end (e.g., "-14", "-v2", "-3.0")
    name = re.sub(r"[-_]v?\d+(\.\d+)*$", "", name)

    return name


def _find_matching_canonical(name: str) -> str | None:
    """Find a matching canonical name from known canonicals."""
    normalized = _normalize_name(name)

    for canonical, variants in KNOWN_CANONICALS.items():
        if normalized == canonical or normalized in variants:
            return canonical

    return None


class IdentityResolver:
    """Resolves canonical identity for tool artifacts.

    Resolution order (first match wins):
    1. Manual overrides from overrides.json
    2. Official sources (Docker library/*, org-owned GitHub repos)
    3. Verified publisher matching known canonical
    4. Fallback to artifact slug
    """

    def __init__(self, overrides_path: Path | None = None):
        """Initialize identity resolver.

        Args:
            overrides_path: Path to overrides.json. Defaults to data/overrides.json.
        """
        self.overrides_path = overrides_path or Path("data/overrides.json")
        self._overrides: dict[str, dict] = {}
        self._load_overrides()

    def _load_overrides(self) -> None:
        """Load manual overrides from file."""
        if self.overrides_path.exists():
            try:
                data = json.loads(self.overrides_path.read_text())
                self._overrides = data.get("identity_overrides", {})
                logger.info(f"Loaded {len(self._overrides)} identity overrides")
            except Exception as e:
                logger.warning(f"Failed to load overrides: {e}")
                self._overrides = {}

    def resolve(
        self,
        artifact_id: str,
        name: str,
        is_official: bool = False,
        is_verified: bool = False,
        publisher: str = "",
    ) -> IdentityResolution:
        """Resolve canonical identity for an artifact.

        Args:
            artifact_id: Full artifact ID (e.g., "docker_hub:library/postgres").
            name: Tool name from the artifact.
            is_official: Whether this is an official source (Docker library, etc.).
            is_verified: Whether the publisher is verified.
            publisher: Publisher/namespace name.

        Returns:
            IdentityResolution with canonical name and provenance.
        """
        # 1. Check manual overrides (by full artifact ID)
        if artifact_id in self._overrides:
            override = self._overrides[artifact_id]
            canonical = override.get("canonical_name", _normalize_name(name))
            return IdentityResolution(
                canonical_name=canonical,
                resolution_source=ResolutionSource.OVERRIDE,
                resolution_confidence=RESOLUTION_CONFIDENCE[ResolutionSource.OVERRIDE],
            )

        # 2. Official sources use normalized tool name
        if is_official:
            return IdentityResolution(
                canonical_name=_normalize_name(name),
                resolution_source=ResolutionSource.OFFICIAL,
                resolution_confidence=RESOLUTION_CONFIDENCE[ResolutionSource.OFFICIAL],
            )

        # 3. Verified publisher - try to match known canonical
        if is_verified:
            matching = _find_matching_canonical(name)
            if matching:
                return IdentityResolution(
                    canonical_name=matching,
                    resolution_source=ResolutionSource.VERIFIED,
                    resolution_confidence=RESOLUTION_CONFIDENCE[ResolutionSource.VERIFIED],
                )

        # 4. Fallback - use artifact slug (publisher/name or just name)
        if publisher and publisher != "library":
            slug = f"{publisher}/{name}".lower()
        else:
            slug = name.lower()

        return IdentityResolution(
            canonical_name=slug,
            resolution_source=ResolutionSource.FALLBACK,
            resolution_confidence=RESOLUTION_CONFIDENCE[ResolutionSource.FALLBACK],
        )

    def resolve_from_tool(self, tool: "Tool") -> IdentityResolution:  # noqa: F821
        """Resolve identity from a Tool object.

        Args:
            tool: Tool object to resolve identity for.

        Returns:
            IdentityResolution with canonical name and provenance.
        """
        from src.models.model_tool import MaintainerType

        is_official = tool.maintainer.type == MaintainerType.OFFICIAL
        is_verified = tool.maintainer.verified

        return self.resolve(
            artifact_id=tool.id,
            name=tool.name,
            is_official=is_official,
            is_verified=is_verified,
            publisher=tool.maintainer.name,
        )

    def add_override(self, artifact_id: str, canonical_name: str, reason: str) -> None:
        """Add or update an identity override.

        Args:
            artifact_id: Full artifact ID to override.
            canonical_name: Canonical name to assign.
            reason: Reason for the override.
        """
        self._overrides[artifact_id] = {
            "canonical_name": canonical_name,
            "reason": reason,
        }
        self._save_overrides()

    def _save_overrides(self) -> None:
        """Save overrides to file."""
        self.overrides_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing file to preserve other override types
        existing = {}
        if self.overrides_path.exists():
            try:
                existing = json.loads(self.overrides_path.read_text())
            except Exception:
                pass

        existing["identity_overrides"] = self._overrides
        self.overrides_path.write_text(json.dumps(existing, indent=2))


def main() -> None:
    """Example usage of identity resolver."""
    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Metrics,
        SourceType,
        Tool,
    )

    print("=== Identity Resolver Example ===\n")

    resolver = IdentityResolver()

    # Example 1: Official Docker image
    print("1. Official Docker image (postgres):")
    result = resolver.resolve(
        artifact_id="docker_hub:library/postgres",
        name="postgres",
        is_official=True,
        is_verified=True,
        publisher="library",
    )
    print(f"   Canonical: {result.canonical_name}")
    print(f"   Source: {result.resolution_source.value}")
    print(f"   Confidence: {result.resolution_confidence}")
    print()

    # Example 2: Verified publisher
    print("2. Verified publisher (bitnami/postgresql):")
    result = resolver.resolve(
        artifact_id="docker_hub:bitnami/postgresql",
        name="postgresql",
        is_official=False,
        is_verified=True,
        publisher="bitnami",
    )
    print(f"   Canonical: {result.canonical_name}")
    print(f"   Source: {result.resolution_source.value}")
    print(f"   Confidence: {result.resolution_confidence}")
    print()

    # Example 3: Unknown user image
    print("3. Unknown user (someuser/postgres-api):")
    result = resolver.resolve(
        artifact_id="docker_hub:someuser/postgres-api",
        name="postgres-api",
        is_official=False,
        is_verified=False,
        publisher="someuser",
    )
    print(f"   Canonical: {result.canonical_name}")
    print(f"   Source: {result.resolution_source.value}")
    print(f"   Confidence: {result.resolution_confidence}")
    print()

    # Example 4: Resolve from Tool object
    print("4. Resolve from Tool object:")
    tool = Tool(
        id="docker_hub:library/nginx",
        name="nginx",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/nginx",
        identity=Identity(canonical_name=""),
        maintainer=Maintainer(
            name="library",
            type=MaintainerType.OFFICIAL,
            verified=True,
        ),
        metrics=Metrics(downloads=1_000_000_000),
    )
    result = resolver.resolve_from_tool(tool)
    print(f"   Tool: {tool.id}")
    print(f"   Canonical: {result.canonical_name}")
    print(f"   Source: {result.resolution_source.value}")
    print()

    print("Done!")


if __name__ == "__main__":
    main()
