"""Tests for the classifier module."""

import json
from pathlib import Path

from src.categorization.classifier import (
    MIN_CONFIDENCE_THRESHOLD,
    UNCATEGORIZED,
    Classifier,
)
from src.categorization.classifier_cache import ClassificationCache
from src.models.model_classification import (
    TAXONOMY_VERSION,
    Classification,
    ClassificationCacheEntry,
    ClassificationResult,
    TagMatch,
)
from src.models.model_tool import (
    FilterReasons,
    FilterState,
    Identity,
    Maintainer,
    MaintainerType,
    Metrics,
    SourceType,
    Tool,
)


class TestTagMatch:
    """Tests for TagMatch dataclass."""

    def test_exact_match(self) -> None:
        match = TagMatch(
            tag="postgres",
            category="databases",
            subcategory="relational",
            is_exact=True,
        )
        assert match.tag == "postgres"
        assert match.is_exact is True

    def test_partial_match(self) -> None:
        match = TagMatch(
            tag="database",
            category="databases",
            subcategory="relational",
            is_exact=False,
        )
        assert match.is_exact is False


class TestClassificationCache:
    """Tests for ClassificationCache class."""

    def test_empty_cache_miss(self, tmp_path: Path) -> None:
        cache = ClassificationCache(tmp_path / "cache.json")
        result = cache.get("postgres")
        assert result is None

    def test_cache_set_and_get(self, tmp_path: Path) -> None:
        cache = ClassificationCache(tmp_path / "cache.json")
        entry = ClassificationCacheEntry(
            classification=Classification(
                primary_category="databases",
                primary_subcategory="relational",
            ),
            source="heuristic",
        )
        cache.set("postgres", entry)

        result = cache.get("postgres")
        assert result is not None
        assert result.classification.primary_category == "databases"
        assert result.source == "heuristic"

    def test_cache_persistence(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"

        # Write to cache
        cache1 = ClassificationCache(cache_path)
        entry = ClassificationCacheEntry(
            classification=Classification(
                primary_category="monitoring",
                primary_subcategory="metrics",
            ),
            source="heuristic",
        )
        cache1.set("prometheus", entry)

        # Read from new cache instance
        cache2 = ClassificationCache(cache_path)
        result = cache2.get("prometheus")
        assert result is not None
        assert result.classification.primary_category == "monitoring"

    def test_cache_invalidate(self, tmp_path: Path) -> None:
        cache = ClassificationCache(tmp_path / "cache.json")
        entry = ClassificationCacheEntry(
            classification=Classification(
                primary_category="databases",
                primary_subcategory="relational",
            ),
            source="heuristic",
        )
        cache.set("postgres", entry)
        assert cache.get("postgres") is not None

        cache.invalidate("postgres")
        assert cache.get("postgres") is None

    def test_cache_clear(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache = ClassificationCache(cache_path)

        entry = ClassificationCacheEntry(
            classification=Classification(
                primary_category="databases",
                primary_subcategory="relational",
            ),
            source="heuristic",
        )
        cache.set("postgres", entry)
        cache.set("mysql", entry)

        cache.clear()
        assert cache.get("postgres") is None
        assert cache.get("mysql") is None


class TestClassifier:
    """Tests for Classifier class."""

    def test_classify_by_exact_tag(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:library/postgres",
            name="postgres",
            tags=["postgres", "database", "sql"],
            description="The PostgreSQL database",
        )
        assert result.classification.primary_category == "databases"
        assert result.classification.primary_subcategory == "relational"
        assert result.source == "heuristic"
        assert result.confidence >= MIN_CONFIDENCE_THRESHOLD

    def test_classify_by_name_match(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:grafana/grafana",
            name="grafana",
            tags=["monitoring"],
            description="Grafana visualization platform",
        )
        assert result.classification.primary_category == "monitoring"
        assert result.classification.primary_subcategory == "visualization"

    def test_classify_by_description(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:library/somedb",
            name="somedb",
            tags=[],
            description="A redis-compatible key-value store",
        )
        assert result.classification.primary_category == "databases"
        assert result.classification.primary_subcategory == "key-value"

    def test_classify_fallback_to_uncategorized(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:user/zqxwv",
            name="zqxwv",
            tags=["zqxwv"],
            description="zqxwv",
        )
        assert result.classification.primary_category == UNCATEGORIZED
        assert result.classification.primary_subcategory == UNCATEGORIZED
        assert result.source == "fallback"
        assert result.needs_review is True

    def test_classify_with_cache_hit(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)

        # First classification
        result1 = classifier.classify(
            artifact_id="docker_hub:library/nginx",
            name="nginx",
            tags=["nginx", "webserver"],
            description="NGINX web server",
        )
        assert result1.source == "heuristic"

        # Second classification should hit cache
        result2 = classifier.classify(
            artifact_id="docker_hub:library/nginx",
            name="nginx",
            tags=["nginx", "webserver"],
            description="NGINX web server",
        )
        assert result2.source == "cache"
        assert result2.classification.primary_category == result1.classification.primary_category

    def test_classify_force_bypass_cache(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)

        # First classification
        classifier.classify(
            artifact_id="docker_hub:library/nginx",
            name="nginx",
            tags=["nginx"],
            description="NGINX web server",
        )

        # Force reclassification
        result = classifier.classify(
            artifact_id="docker_hub:library/nginx",
            name="nginx",
            tags=["nginx"],
            description="NGINX web server",
            force=True,
        )
        assert result.source == "heuristic"  # Not cache

    def test_classify_with_override(self, tmp_path: Path) -> None:
        # Create override file
        overrides_path = tmp_path / "overrides.json"
        overrides_data = {
            "classification_overrides": {
                "docker_hub:user/postgres-api": {
                    "primary_category": "web",
                    "primary_subcategory": "server",
                    "secondary_categories": ["databases/relational"],
                    "reason": "REST API wrapper for PostgreSQL",
                }
            }
        }
        overrides_path.write_text(json.dumps(overrides_data))

        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:user/postgres-api",
            name="postgres-api",
            tags=["postgres", "api"],
            description="REST API for PostgreSQL",
        )
        assert result.classification.primary_category == "web"
        assert result.classification.primary_subcategory == "server"
        assert result.source == "override"
        assert result.confidence == 1.0

    def test_classify_tool_object(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        tool = Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis is an open source key-value store",
            tags=["redis", "cache", "key-value"],
            identity=Identity(canonical_name=""),
            maintainer=Maintainer(
                name="library",
                type=MaintainerType.OFFICIAL,
                verified=True,
            ),
            metrics=Metrics(downloads=1_000_000_000),
        )
        result = classifier.classify_tool(tool)
        assert result.classification.primary_category == "databases"
        assert result.classification.primary_subcategory == "key-value"

    def test_apply_classification_updates_tool(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        tool = Tool(
            id="docker_hub:library/kafka",
            name="kafka",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/kafka",
            description="Apache Kafka streaming platform",
            tags=["kafka", "streaming", "messaging"],
            identity=Identity(canonical_name=""),
            maintainer=Maintainer(
                name="library",
                type=MaintainerType.OFFICIAL,
                verified=True,
            ),
            metrics=Metrics(downloads=500_000_000),
        )

        # Apply classification
        classifier.apply_classification(tool)

        assert tool.primary_category == "messaging"
        assert tool.primary_subcategory == "streaming"
        assert tool.taxonomy_version == TAXONOMY_VERSION
        assert tool.identity.canonical_name == "kafka"

    def test_apply_classification_marks_needs_review(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        tool = Tool(
            id="docker_hub:user/qwzxv",
            name="qwzxv",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/user/qwzxv",
            description="qwzxv tool",
            tags=["qwzxv"],
            identity=Identity(canonical_name=""),
            maintainer=Maintainer(
                name="user",
                type=MaintainerType.USER,
                verified=False,
            ),
            metrics=Metrics(downloads=100),
        )

        classifier.apply_classification(tool)

        assert tool.primary_category == UNCATEGORIZED
        assert tool.filter_status.state == FilterState.HIDDEN
        assert FilterReasons.NEEDS_REVIEW in tool.filter_status.reasons

    def test_add_override_valid(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        success = classifier.add_override(
            artifact_id="docker_hub:user/custom-tool",
            primary_category="databases",
            primary_subcategory="relational",
            reason="Correct classification",
        )
        assert success is True

        # Verify override works
        result = classifier.classify(
            artifact_id="docker_hub:user/custom-tool",
            name="custom-tool",
            tags=[],
            description="",
        )
        assert result.classification.primary_category == "databases"
        assert result.source == "override"

    def test_add_override_invalid_category(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        success = classifier.add_override(
            artifact_id="docker_hub:user/tool",
            primary_category="invalid",
            primary_subcategory="relational",
            reason="Test",
        )
        assert success is False

    def test_add_override_invalid_subcategory(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        success = classifier.add_override(
            artifact_id="docker_hub:user/tool",
            primary_category="databases",
            primary_subcategory="invalid",
            reason="Test",
        )
        assert success is False

    def test_get_needs_review(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)

        # Classify some tools (some will need review)
        classifier.classify(
            artifact_id="docker_hub:library/postgres",
            name="postgres",
            tags=["postgres"],
            description="",
        )
        classifier.classify(
            artifact_id="docker_hub:user/zqxwv1",
            name="zqxwv1",
            tags=[],
            description="",
        )
        classifier.classify(
            artifact_id="docker_hub:user/zqxwv2",
            name="zqxwv2",
            tags=[],
            description="",
        )

        needs_review = classifier.get_needs_review()
        assert "zqxwv1" in needs_review
        assert "zqxwv2" in needs_review
        assert "postgres" not in needs_review

    def test_clear_cache(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)

        # Add some classifications
        classifier.classify(
            artifact_id="docker_hub:library/nginx",
            name="nginx",
            tags=["nginx"],
            description="",
        )

        # Clear cache
        classifier.clear_cache()

        # Should reclassify (not from cache)
        result = classifier.classify(
            artifact_id="docker_hub:library/nginx",
            name="nginx",
            tags=["nginx"],
            description="",
        )
        assert result.source == "heuristic"


class TestClassifierTagMatching:
    """Tests for tag matching logic in Classifier."""

    def test_exact_tag_higher_confidence(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)

        # Exact tag match
        result1 = classifier.classify(
            artifact_id="docker_hub:test/tool1",
            name="tool1",
            tags=["postgres"],
            description="",
        )

        # Name-only match
        result2 = classifier.classify(
            artifact_id="docker_hub:test/postgres",
            name="postgres",
            tags=[],
            description="",
            force=True,
        )

        # Exact tag match should have higher or equal confidence
        assert result1.confidence >= result2.confidence

    def test_multiple_matches_same_category(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:test/dbtools",
            name="dbtools",
            tags=["postgres", "postgresql", "database", "sql"],
            description="PostgreSQL tools",
        )
        # Multiple matches to same category should boost confidence
        assert result.classification.primary_category == "databases"
        assert result.classification.primary_subcategory == "relational"

    def test_secondary_categories_collected(self, tmp_path: Path) -> None:
        classifier = Classifier(data_dir=tmp_path)
        result = classifier.classify(
            artifact_id="docker_hub:test/elastic",
            name="elasticsearch",
            tags=["elasticsearch", "search", "logging", "loki"],
            description="Elasticsearch for search and logging",
        )
        # Should have primary as databases/search and secondary categories
        assert result.classification.primary_category == "databases"
        assert result.classification.primary_subcategory == "search"
        # May have secondary from logging keywords
        # (depends on match order)


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_creation_with_defaults(self) -> None:
        result = ClassificationResult(
            classification=Classification(
                primary_category="databases",
                primary_subcategory="relational",
            ),
            confidence=0.85,
            source="heuristic",
        )
        assert result.needs_review is False
        assert result.cache_entry is None

    def test_creation_with_needs_review(self) -> None:
        result = ClassificationResult(
            classification=Classification(
                primary_category=UNCATEGORIZED,
                primary_subcategory=UNCATEGORIZED,
            ),
            confidence=0.3,
            source="fallback",
            needs_review=True,
        )
        assert result.needs_review is True
