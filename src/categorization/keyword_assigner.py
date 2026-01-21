"""Keyword assigner for tool property classification.

Assigns property keywords to tools using the following flow:
1. Cache lookup (by canonical name)
2. Override check (by artifact ID)
3. Heuristic matching (tag/name/description against keyword taxonomy)
4. Fallback to empty keyword list

Keywords are metadata only - not scored, just displayed/exported for
search and filtering.
"""

import contextlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from src.categorization.keyword_assigner_cache import KeywordAssignmentCache
from src.categorization.keyword_taxonomy import (
    KEYWORD_TAXONOMY_VERSION,
    get_all_keywords,
    is_valid_keyword,
)
from src.consts import DEFAULT_DATA_DIR
from src.models.model_classification import (
    KeywordAssignment,
    KeywordAssignmentCacheEntry,
    KeywordAssignmentResult,
)

logger = logging.getLogger(__name__)

KEYWORD_CONFIDENCE_THRESHOLD: Final[float] = 0.6
MIN_MATCH_SCORE: Final[float] = 0.4


class KeywordAssigner:
    """Keyword assigner using heuristic matching.

    Assignment flow:
    1. Cache lookup by canonical name
    2. Override check by artifact ID
    3. Heuristic matching against keyword taxonomy
    4. Fallback to empty keyword list

    All applicable keywords above threshold are assigned (not just top match).
    """

    def __init__(
        self,
        data_dir: Path | None = None,
    ):
        """Initialize keyword assigner.

        Args:
            data_dir: Directory for cache and overrides.
                     If None, uses FileCache's default location.
        """
        self.data_dir = data_dir

        # Create keyword assignment cache
        if data_dir is not None:
            self._cache = KeywordAssignmentCache(cache_path=data_dir / "cache")
        else:
            # Use FileCache defaults
            self._cache = KeywordAssignmentCache()

        self._overrides: dict[str, list[str]] = {}
        self._load_overrides()

    def _load_overrides(self) -> None:
        """Load keyword overrides from file."""
        data_dir = self.data_dir if self.data_dir is not None else DEFAULT_DATA_DIR
        overrides_path = data_dir / "overrides.json"
        if overrides_path.exists():
            try:
                data = json.loads(overrides_path.read_text())
                keyword_overrides = data.get("keyword_overrides", {})
                for artifact_id, override_data in keyword_overrides.items():
                    self._overrides[artifact_id] = override_data.get("keywords", [])
                logger.info(f"Loaded {len(self._overrides)} keyword overrides")
            except Exception as e:
                logger.warning(f"Failed to load keyword overrides: {e}")

    def _match_keywords(
        self,
        tags: list[str],
        name: str,
        description: str,
    ) -> dict[str, float]:
        """Match keywords against tool metadata.

        Args:
            tags: Tags from the tool.
            name: Tool name.
            description: Tool description.

        Returns:
            Dict mapping keyword to confidence score (0.0-1.0).
        """
        keyword_scores: dict[str, float] = {}
        all_keywords = get_all_keywords()

        # Normalize inputs
        tags_lower = [t.lower() for t in tags]
        name_lower = name.lower()
        desc_lower = description.lower()

        for keyword in all_keywords:
            score = 0.0

            # Exact tag match (highest priority)
            if keyword in tags_lower:
                score = max(score, 0.9)

            # Name contains keyword (high priority)
            if keyword in name_lower:
                # Bonus for exact match
                if keyword == name_lower:
                    score = max(score, 0.95)
                else:
                    score = max(score, 0.8)

            # Description contains keyword (moderate priority)
            if keyword in desc_lower:
                score = max(score, 0.6)

            # Partial matches with word boundaries
            keyword_parts = keyword.split("-")
            if len(keyword_parts) > 1:
                # Check if all parts appear in name or description
                if all(part in name_lower for part in keyword_parts):
                    score = max(score, 0.75)
                elif all(part in desc_lower for part in keyword_parts):
                    score = max(score, 0.55)

            if score > MIN_MATCH_SCORE:
                keyword_scores[keyword] = score

        return keyword_scores

    def _calculate_overall_confidence(self, keyword_scores: dict[str, float]) -> float:
        """Calculate overall assignment confidence.

        Args:
            keyword_scores: Dict of keyword to confidence score.

        Returns:
            Overall confidence between 0.0 and 1.0.
        """
        if not keyword_scores:
            return 0.0

        # Use average of top scores as overall confidence
        top_scores = sorted(keyword_scores.values(), reverse=True)[:5]
        return sum(top_scores) / len(top_scores) if top_scores else 0.0

    def assign(
        self,
        artifact_id: str,
        name: str,
        tags: list[str],
        description: str = "",
        canonical_name: str | None = None,
        force: bool = False,
    ) -> KeywordAssignmentResult:
        """Assign keywords to a tool.

        Args:
            artifact_id: Full artifact ID (e.g., "docker_hub:library/postgres").
            name: Tool name.
            tags: Tags from the source.
            description: Tool description.
            canonical_name: Pre-resolved canonical name. If None, will be resolved.
            force: If True, bypass cache.

        Returns:
            KeywordAssignmentResult with keywords and metadata.
        """
        # Resolve canonical name if not provided
        if canonical_name is None:
            # Simple extraction from artifact_id
            parts = artifact_id.split(":")
            if len(parts) == 2:
                source, path = parts
                name_part = path.split("/")[-1]
                canonical_name = name_part.lower()
            else:
                canonical_name = name.lower()

        # 1. Check cache (by canonical name)
        if not force:
            cached = self._cache.get(canonical_name)
            if cached:
                logger.debug(f"Cache hit for keywords: {canonical_name}")
                return KeywordAssignmentResult(
                    assignment=cached.assignment,
                    confidence=1.0,  # Cached entries are trusted
                    source="cache",
                    cache_entry=cached,
                )

        # 2. Check overrides (by artifact ID)
        if artifact_id in self._overrides:
            override_keywords = self._overrides[artifact_id]
            assignment = KeywordAssignment(keywords=override_keywords)

            # Cache the override result
            cache_entry = KeywordAssignmentCacheEntry(
                assignment=assignment,
                assigned_at=datetime.now(UTC),
                source="override",
            )
            self._cache.set(canonical_name, cache_entry)

            logger.debug(f"Override applied for {artifact_id}: {len(override_keywords)} keywords")
            return KeywordAssignmentResult(
                assignment=assignment,
                confidence=1.0,
                source="override",
                cache_entry=cache_entry,
            )

        # 3. Heuristic matching
        keyword_scores = self._match_keywords(tags, name, description)

        # Filter by confidence threshold
        matched_keywords = [
            kw for kw, score in keyword_scores.items() if score >= KEYWORD_CONFIDENCE_THRESHOLD
        ]

        overall_confidence = self._calculate_overall_confidence(keyword_scores)

        if matched_keywords:
            # Sort keywords alphabetically for consistent output
            matched_keywords.sort()

            assignment = KeywordAssignment(keywords=matched_keywords)

            # Cache the result
            cache_entry = KeywordAssignmentCacheEntry(
                assignment=assignment,
                assigned_at=datetime.now(UTC),
                source="heuristic",
            )
            self._cache.set(canonical_name, cache_entry)

            logger.debug(
                f"Assigned {len(matched_keywords)} keywords to {name} "
                f"(confidence: {overall_confidence:.2f})"
            )
            return KeywordAssignmentResult(
                assignment=assignment,
                confidence=overall_confidence,
                source="heuristic",
                cache_entry=cache_entry,
            )

        # 4. Fallback to empty keyword list
        assignment = KeywordAssignment(keywords=[])

        # Cache with fallback source
        cache_entry = KeywordAssignmentCacheEntry(
            assignment=assignment,
            assigned_at=datetime.now(UTC),
            source="fallback",
        )
        self._cache.set(canonical_name, cache_entry)

        logger.debug(f"No keywords matched for {name} (fallback to empty)")
        return KeywordAssignmentResult(
            assignment=assignment,
            confidence=0.0,
            source="fallback",
            cache_entry=cache_entry,
        )

    def assign_tool(self, tool: "Tool", force: bool = False) -> KeywordAssignmentResult:  # noqa: F821
        """Assign keywords to a Tool object.

        Args:
            tool: Tool to assign keywords to.
            force: If True, bypass cache.

        Returns:
            KeywordAssignmentResult with keywords and metadata.
        """
        return self.assign(
            artifact_id=tool.id,
            name=tool.name,
            tags=tool.tags,
            description=tool.description,
            canonical_name=tool.identity.canonical_name,
            force=force,
        )

    def apply_keywords(self, tool: "Tool", force: bool = False) -> None:  # noqa: F821
        """Assign keywords to a tool and update its fields in place.

        Args:
            tool: Tool to assign keywords to and update.
            force: If True, bypass cache.
        """
        result = self.assign_tool(tool, force=force)

        # Update tool fields
        tool.keywords = result.assignment.keywords
        tool.keyword_version = KEYWORD_TAXONOMY_VERSION

    def add_override(
        self,
        artifact_id: str,
        keywords: list[str],
        reason: str,
    ) -> bool:
        """Add a keyword assignment override.

        Args:
            artifact_id: Full artifact ID to override.
            keywords: Keywords to assign.
            reason: Reason for the override.

        Returns:
            True if override was added, False if validation failed.
        """
        # Validate keywords
        invalid = [kw for kw in keywords if not is_valid_keyword(kw)]
        if invalid:
            logger.error(f"Invalid keywords: {invalid}")
            return False

        self._overrides[artifact_id] = keywords
        self._save_overrides(reason_map={artifact_id: reason})

        # Invalidate any cached assignment
        logger.info(f"Added keyword override for {artifact_id}: {keywords}")
        return True

    def _save_overrides(self, reason_map: dict[str, str] | None = None) -> None:
        """Save keyword overrides to file.

        Args:
            reason_map: Optional dict mapping artifact_id to reason.
        """
        data_dir = self.data_dir if self.data_dir is not None else DEFAULT_DATA_DIR
        overrides_path = data_dir / "overrides.json"
        overrides_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing to preserve other override types
        existing = {}
        if overrides_path.exists():
            with contextlib.suppress(Exception):
                existing = json.loads(overrides_path.read_text())

        # Build keyword overrides section
        keyword_overrides = {}
        for artifact_id, keywords in self._overrides.items():
            keyword_overrides[artifact_id] = {
                "keywords": keywords,
                "reason": (
                    reason_map.get(artifact_id, "Manual override")
                    if reason_map
                    else "Manual override"
                ),
            }

        existing["keyword_overrides"] = keyword_overrides
        overrides_path.write_text(json.dumps(existing, indent=2))

    def clear_cache(self) -> None:
        """Clear keyword assignment cache."""
        self._cache.clear()
        logger.info("Cleared keyword assignment cache")


def main() -> None:
    """Example usage of keyword assigner."""
    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Metrics,
        SourceType,
        Tool,
    )

    print("=== KeywordAssigner Example ===\n")

    assigner = KeywordAssigner()

    # Example 1: Assign keywords by tags
    print("1. Assign keywords to 'postgres' by tags:")
    result = assigner.assign(
        artifact_id="docker_hub:library/postgres",
        name="postgres",
        tags=["database", "sql", "postgresql", "relational"],
        description="The PostgreSQL object-relational database system provides reliability and data integrity.",
    )
    print(f"   Keywords: {', '.join(result.assignment.keywords)}")
    print(f"   Confidence: {result.confidence:.2f}")
    print(f"   Source: {result.source}")
    print()

    # Example 2: Assign keywords with name match
    print("2. Assign keywords to 'kubernetes' by name/description:")
    result = assigner.assign(
        artifact_id="docker_hub:kubernetes/kubectl",
        name="kubectl",
        tags=["kubernetes", "cli", "k8s"],
        description="Kubernetes command-line tool for cluster management",
    )
    print(f"   Keywords: {', '.join(result.assignment.keywords)}")
    print(f"   Confidence: {result.confidence:.2f}")
    print()

    # Example 3: Assign to unknown tool (fallback)
    print("3. Assign keywords to unknown tool (fallback):")
    result = assigner.assign(
        artifact_id="docker_hub:someuser/myapp",
        name="myapp",
        tags=["app", "custom"],
        description="My custom application",
    )
    print(f"   Keywords: {result.assignment.keywords if result.assignment.keywords else '(none)'}")
    print(f"   Confidence: {result.confidence:.2f}")
    print()

    # Example 4: Assign keywords to Tool object
    print("4. Assign keywords to Tool object (Redis):")
    tool = Tool(
        id="docker_hub:library/redis",
        name="redis",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/redis",
        description="Redis is an open source in-memory data structure store, used as a database, cache, and message broker",
        tags=["redis", "database", "cache", "key-value", "in-memory"],
        identity=Identity(canonical_name="redis"),
        maintainer=Maintainer(
            name="library",
            type=MaintainerType.OFFICIAL,
            verified=True,
        ),
        metrics=Metrics(downloads=1_000_000_000),
    )
    result = assigner.assign_tool(tool)
    print(f"   Tool: {tool.name}")
    print(f"   Keywords: {', '.join(result.assignment.keywords)}")
    print()

    # Example 5: Apply keywords to tool (in-place)
    print("5. Apply keywords to tool (in-place):")
    assigner.apply_keywords(tool, force=True)
    print(f"   Tool keywords: {', '.join(tool.keywords)}")
    print(f"   Keyword version: {tool.keyword_version}")
    print()

    # Example 6: Add override
    print("6. Add keyword override:")
    success = assigner.add_override(
        artifact_id="docker_hub:library/test",
        keywords=["cloud-native", "containerized", "production-ready"],
        reason="Test override for demonstration",
    )
    print(f"   Override added: {success}")
    print()

    print("Done!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
