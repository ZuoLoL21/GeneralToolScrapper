"""Tool classifier with MVP tag-based heuristics.

Classifies tools into categories using the following flow:
1. Cache lookup (by canonical name)
2. Override check (by artifact ID)
3. Tag-based heuristics (MVP mode)
4. Fallback to 'uncategorized' with needs_review flag

In full mode (not implemented yet), step 3 uses LLM classification via Ollama.
"""

import contextlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from src.categorization.classifier_cache import ClassificationCache
from src.categorization.human_maintained import TAXONOMY
from src.categorization.identity import IdentityResolver
from src.categorization.taxonomy import validate_classification
from src.models.model_classification import (
    TAXONOMY_VERSION,
    Classification,
    ClassificationCacheEntry,
    ClassificationOverride,
    ClassificationResult,
    TagMatch,
)

logger = logging.getLogger(__name__)

MIN_CONFIDENCE_THRESHOLD: Final[float] = 0.7
UNCATEGORIZED: Final[str] = "uncategorized"


class Classifier:
    """Tool classifier using tag-based heuristics (MVP mode).

    Classification flow:
    1. Cache lookup by canonical name
    2. Override check by artifact ID
    3. Tag-based heuristics matching
    4. Fallback to uncategorized

    In full mode (future), step 3 would use LLM classification via Ollama.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        identity_resolver: IdentityResolver | None = None,
    ):
        """Initialize classifier.

        Args:
            data_dir: Directory for cache and overrides. Defaults to ./data.
            identity_resolver: Identity resolver instance. Created if not provided.
        """
        self.data_dir = data_dir or Path("data")
        self.identity_resolver = identity_resolver or IdentityResolver(
            overrides_path=self.data_dir / "overrides.json"
        )
        self._cache = ClassificationCache(self.data_dir / "cache" / "classifications.json")
        self._overrides: dict[str, ClassificationOverride] = {}
        self._load_overrides()

    def _load_overrides(self) -> None:
        """Load classification overrides from file."""
        overrides_path = self.data_dir / "overrides.json"
        if overrides_path.exists():
            try:
                data = json.loads(overrides_path.read_text())
                overrides = data.get("classification_overrides", {})
                for artifact_id, override_data in overrides.items():
                    self._overrides[artifact_id] = ClassificationOverride(**override_data)
                logger.info(f"Loaded {len(self._overrides)} classification overrides")
            except Exception as e:
                logger.warning(f"Failed to load overrides: {e}")

    def _match_tags(
        self,
        tags: list[str],
        name: str,
        description: str,
    ) -> list[TagMatch]:
        """Match tags against taxonomy keywords.

        Args:
            tags: Tags from the tool.
            name: Tool name.
            description: Tool description.

        Returns:
            List of TagMatch objects sorted by relevance.
        """
        matches: list[TagMatch] = []
        seen: set[tuple[str, str]] = set()  # (category, subcategory)

        # Normalize inputs
        tags_lower = [t.lower() for t in tags]
        name_lower = name.lower()
        desc_lower = description.lower()

        # Check each category/subcategory
        for category in TAXONOMY:
            for subcategory in category.subcategories:
                for keyword in subcategory.keywords:
                    key = (category.name, subcategory.name)
                    if key in seen:
                        continue

                    # Check for exact tag match
                    if keyword in tags_lower:
                        matches.append(
                            TagMatch(
                                tag=keyword,
                                category=category.name,
                                subcategory=subcategory.name,
                                is_exact=True,
                            )
                        )
                        seen.add(key)
                        continue

                    # Check in name (high priority)
                    if keyword in name_lower:
                        matches.append(
                            TagMatch(
                                tag=keyword,
                                category=category.name,
                                subcategory=subcategory.name,
                                is_exact=False,
                            )
                        )
                        seen.add(key)
                        continue

                    # Check in description (lower priority)
                    if keyword in desc_lower:
                        matches.append(
                            TagMatch(
                                tag=keyword,
                                category=category.name,
                                subcategory=subcategory.name,
                                is_exact=False,
                            )
                        )
                        seen.add(key)

        # Sort: exact matches first, then by category order in taxonomy
        category_order = {cat.name: i for i, cat in enumerate(TAXONOMY)}
        matches.sort(key=lambda m: (not m.is_exact, category_order.get(m.category, 99)))

        return matches

    def _calculate_confidence(self, matches: list[TagMatch]) -> float:
        """Calculate confidence score based on tag matches.

        Args:
            matches: List of tag matches.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not matches:
            return 0.0

        # Base confidence on match quality
        best_match = matches[0]

        if best_match.is_exact:
            # Exact tag match: high confidence
            base = 0.85
        else:
            # Name/description match: moderate confidence
            base = 0.70

        # Bonus for multiple matches to same category
        if len(matches) > 1 and matches[1].category == best_match.category:
            base = min(base + 0.05, 0.95)

        # Bonus for exact + name match together
        exact_count = sum(1 for m in matches if m.is_exact)
        if exact_count > 1:
            base = min(base + 0.05, 0.95)

        return base

    def classify(
        self,
        artifact_id: str,
        name: str,
        tags: list[str],
        description: str = "",
        canonical_name: str | None = None,
        force: bool = False,
    ) -> ClassificationResult:
        """Classify a tool into categories.

        Args:
            artifact_id: Full artifact ID (e.g., "docker_hub:library/postgres").
            name: Tool name.
            tags: Tags from the source.
            description: Tool description.
            canonical_name: Pre-resolved canonical name. If None, will be resolved.
            force: If True, bypass cache.

        Returns:
            ClassificationResult with classification and metadata.
        """
        # Resolve canonical name if not provided
        if canonical_name is None:
            # Simple extraction from artifact_id for now
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
                logger.debug(f"Cache hit for {canonical_name}")
                return ClassificationResult(
                    classification=cached.classification,
                    confidence=1.0,  # Cached entries are trusted
                    source="cache",
                    cache_entry=cached,
                )

        # 2. Check overrides (by artifact ID)
        if artifact_id in self._overrides:
            override = self._overrides[artifact_id]
            classification = Classification(
                primary_category=override.primary_category,
                primary_subcategory=override.primary_subcategory,
                secondary_categories=override.secondary_categories,
            )
            # Cache the override result
            cache_entry = ClassificationCacheEntry(
                classification=classification,
                classified_at=datetime.now(UTC),
                source="override",
            )
            self._cache.set(canonical_name, cache_entry)

            logger.debug(f"Override applied for {artifact_id}")
            return ClassificationResult(
                classification=classification,
                confidence=1.0,
                source="override",
                cache_entry=cache_entry,
            )

        # 3. Tag-based heuristics (MVP mode)
        matches = self._match_tags(tags, name, description)
        confidence = self._calculate_confidence(matches)

        if matches and confidence >= MIN_CONFIDENCE_THRESHOLD:
            # Use best match
            best = matches[0]
            primary_category = best.category
            primary_subcategory = best.subcategory

            # Collect secondary categories (different from primary)
            secondary = []
            for m in matches[1:3]:  # Up to 2 secondary categories
                sec = f"{m.category}/{m.subcategory}"
                if m.category != primary_category:
                    secondary.append(sec)

            classification = Classification(
                primary_category=primary_category,
                primary_subcategory=primary_subcategory,
                secondary_categories=secondary,
            )

            # Cache the result
            cache_entry = ClassificationCacheEntry(
                classification=classification,
                classified_at=datetime.now(UTC),
                source="heuristic",
            )
            self._cache.set(canonical_name, cache_entry)

            logger.debug(
                f"Classified {name} as {primary_category}/{primary_subcategory} "
                f"(confidence: {confidence:.2f})"
            )
            return ClassificationResult(
                classification=classification,
                confidence=confidence,
                source="heuristic",
                cache_entry=cache_entry,
            )

        # 4. Fallback to uncategorized
        classification = Classification(
            primary_category=UNCATEGORIZED,
            primary_subcategory=UNCATEGORIZED,
            secondary_categories=[],
        )

        # Cache with fallback source
        cache_entry = ClassificationCacheEntry(
            classification=classification,
            classified_at=datetime.now(UTC),
            source="fallback",
        )
        self._cache.set(canonical_name, cache_entry)

        logger.debug(f"Fallback to uncategorized for {name} (confidence: {confidence:.2f})")
        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            source="fallback",
            needs_review=True,
        )

    def classify_tool(self, tool: "Tool", force: bool = False) -> ClassificationResult:  # noqa: F821
        """Classify a Tool object.

        Args:
            tool: Tool to classify.
            force: If True, bypass cache.

        Returns:
            ClassificationResult with classification and metadata.
        """
        # Resolve identity first
        identity = self.identity_resolver.resolve_from_tool(tool)

        return self.classify(
            artifact_id=tool.id,
            name=tool.name,
            tags=tool.tags,
            description=tool.description,
            canonical_name=identity.canonical_name,
            force=force,
        )

    def apply_classification(self, tool: "Tool", force: bool = False) -> "Tool":  # noqa: F821
        """Classify a tool and update its fields in place.

        Args:
            tool: Tool to classify and update.
            force: If True, bypass cache.

        Returns:
            The same tool with updated classification fields.
        """
        result = self.classify_tool(tool, force=force)

        # Update tool fields
        tool.primary_category = result.classification.primary_category
        tool.primary_subcategory = result.classification.primary_subcategory
        tool.secondary_categories = result.classification.secondary_categories
        tool.taxonomy_version = TAXONOMY_VERSION

        # Update identity from resolution
        identity = self.identity_resolver.resolve_from_tool(tool)
        tool.identity.canonical_name = identity.canonical_name

        # Mark for review if needed
        if result.needs_review:
            from src.models.model_tool import FilterReasons, FilterState

            tool.filter_status.state = FilterState.HIDDEN
            if FilterReasons.NEEDS_REVIEW not in tool.filter_status.reasons:
                tool.filter_status.reasons.append(FilterReasons.NEEDS_REVIEW)

        return tool

    def add_override(
        self,
        artifact_id: str,
        primary_category: str,
        primary_subcategory: str,
        reason: str,
        secondary_categories: list[str] | None = None,
    ) -> bool:
        """Add a classification override.

        Args:
            artifact_id: Full artifact ID to override.
            primary_category: Category to assign.
            primary_subcategory: Subcategory to assign.
            reason: Reason for the override.
            secondary_categories: Optional secondary categories.

        Returns:
            True if override was added, False if validation failed.
        """
        # Validate against taxonomy
        is_valid, error = validate_classification(
            primary_category, primary_subcategory, secondary_categories
        )
        if not is_valid:
            logger.error(f"Invalid override: {error}")
            return False

        override = ClassificationOverride(
            primary_category=primary_category,
            primary_subcategory=primary_subcategory,
            secondary_categories=secondary_categories or [],
            reason=reason,
        )
        self._overrides[artifact_id] = override
        self._save_overrides()

        # Invalidate any cached classification
        # (would need to resolve canonical name to invalidate properly)
        logger.info(f"Added override for {artifact_id}")
        return True

    def _save_overrides(self) -> None:
        """Save overrides to file."""
        overrides_path = self.data_dir / "overrides.json"
        overrides_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing to preserve other override types
        existing = {}
        if overrides_path.exists():
            with contextlib.suppress(Exception):
                existing = json.loads(overrides_path.read_text())

        existing["classification_overrides"] = {
            k: v.model_dump() for k, v in self._overrides.items()
        }
        overrides_path.write_text(json.dumps(existing, indent=2))

    def clear_cache(self) -> None:
        """Clear classification cache."""
        self._cache.clear()
        logger.info("Cleared classification cache")

    def get_needs_review(self) -> list[str]:
        """Get list of canonical names that need review."""
        needs_review = []
        for canonical, entry in self._cache._cache.items():
            if entry.source == "fallback":
                needs_review.append(canonical)
        return needs_review


def main() -> None:
    """Example usage of classifier."""
    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Metrics,
        SourceType,
        Tool,
    )

    print("=== Classifier Example ===\n")

    classifier = Classifier(data_dir=Path("data"))

    # Example 1: Classify by tags
    print("1. Classify 'postgres' by tags:")
    result = classifier.classify(
        artifact_id="docker_hub:library/postgres",
        name="postgres",
        tags=["database", "sql", "postgresql"],
        description="The PostgreSQL object-relational database system",
    )
    print(
        f"   Category: {result.classification.primary_category}/{result.classification.primary_subcategory}"
    )
    print(f"   Confidence: {result.confidence:.2f}")
    print(f"   Source: {result.source}")
    print()

    # Example 2: Classify with name match
    print("2. Classify 'grafana' by name:")
    result = classifier.classify(
        artifact_id="docker_hub:grafana/grafana",
        name="grafana",
        tags=["monitoring"],
        description="The open-source platform for monitoring and observability",
    )
    print(
        f"   Category: {result.classification.primary_category}/{result.classification.primary_subcategory}"
    )
    print(f"   Confidence: {result.confidence:.2f}")
    print()

    # Example 3: Classify unknown tool (fallback)
    print("3. Classify unknown tool (fallback):")
    result = classifier.classify(
        artifact_id="docker_hub:someuser/myapp",
        name="myapp",
        tags=["app", "custom"],
        description="My custom application",
    )
    print(
        f"   Category: {result.classification.primary_category}/{result.classification.primary_subcategory}"
    )
    print(f"   Confidence: {result.confidence:.2f}")
    print(f"   Needs review: {result.needs_review}")
    print()

    # Example 4: Classify Tool object
    print("4. Classify Tool object:")
    tool = Tool(
        id="docker_hub:library/redis",
        name="redis",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/redis",
        description="Redis is an open source key-value store",
        tags=["redis", "database", "cache", "key-value"],
        identity=Identity(canonical_name=""),
        maintainer=Maintainer(
            name="library",
            type=MaintainerType.OFFICIAL,
            verified=True,
        ),
        metrics=Metrics(downloads=1_000_000_000),
    )
    result = classifier.classify_tool(tool)
    print(f"   Tool: {tool.name}")
    print(
        f"   Category: {result.classification.primary_category}/{result.classification.primary_subcategory}"
    )
    print(f"   Secondary: {result.classification.secondary_categories}")
    print()

    # Example 5: Apply classification to tool
    print("5. Apply classification to tool (in-place):")
    classifier.apply_classification(tool, force=True)
    print(f"   Tool category: {tool.primary_category}/{tool.primary_subcategory}")
    print(f"   Canonical name: {tool.identity.canonical_name}")
    print()

    # Show items needing review
    print("6. Items needing review:")
    needs_review = classifier.get_needs_review()
    if needs_review:
        for name in needs_review[:5]:
            print(f"   - {name}")
    else:
        print("   None")
    print()

    print("Done!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
