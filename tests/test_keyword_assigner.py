"""Tests for the keyword assigner module."""

import json
from pathlib import Path

from src.categorization.keyword_assigner import (
    KEYWORD_CONFIDENCE_THRESHOLD,
    KeywordAssigner,
)
from src.categorization.keyword_assigner_cache import KeywordAssignmentCache
from src.categorization.keyword_taxonomy import KEYWORD_TAXONOMY_VERSION
from src.models.model_classification import (
    KeywordAssignment,
    KeywordAssignmentCacheEntry,
)
from src.models.model_tool import Identity, Maintainer, MaintainerType, Metrics, SourceType, Tool


class TestKeywordAssignmentCache:
    """Tests for KeywordAssignmentCache class."""

    def test_empty_cache_miss(self, tmp_path: Path) -> None:
        cache = KeywordAssignmentCache(tmp_path / "cache.json")
        result = cache.get("postgres")
        assert result is None

    def test_cache_set_and_get(self, tmp_path: Path) -> None:
        cache = KeywordAssignmentCache(tmp_path / "cache.json")
        entry = KeywordAssignmentCacheEntry(
            assignment=KeywordAssignment(keywords=["cloud-native", "distributed"]),
            source="heuristic",
        )
        cache.set("postgres", entry)

        result = cache.get("postgres")
        assert result is not None
        assert len(result.assignment.keywords) == 2
        assert "cloud-native" in result.assignment.keywords
        assert result.source == "heuristic"

    def test_cache_persistence(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"

        # Write to cache
        cache1 = KeywordAssignmentCache(cache_path)
        entry = KeywordAssignmentCacheEntry(
            assignment=KeywordAssignment(keywords=["grpc", "containerized"]),
            source="heuristic",
        )
        cache1.set("kubernetes", entry)

        # Read from new cache instance
        cache2 = KeywordAssignmentCache(cache_path)
        result = cache2.get("kubernetes")
        assert result is not None
        assert len(result.assignment.keywords) == 2

    def test_cache_invalidate(self, tmp_path: Path) -> None:
        cache = KeywordAssignmentCache(tmp_path / "cache.json")
        entry = KeywordAssignmentCacheEntry(
            assignment=KeywordAssignment(keywords=["in-memory"]),
            source="heuristic",
        )
        cache.set("redis", entry)
        assert cache.get("redis") is not None

        cache.invalidate("redis")
        assert cache.get("redis") is None

    def test_cache_clear(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache = KeywordAssignmentCache(cache_path)

        entry = KeywordAssignmentCacheEntry(
            assignment=KeywordAssignment(keywords=["cloud-native"]),
            source="heuristic",
        )
        cache.set("postgres", entry)
        cache.set("mysql", entry)

        cache.clear()
        assert cache.get("postgres") is None
        assert cache.get("mysql") is None

    def test_get_all_entries(self, tmp_path: Path) -> None:
        cache = KeywordAssignmentCache(tmp_path / "cache.json")
        entry1 = KeywordAssignmentCacheEntry(
            assignment=KeywordAssignment(keywords=["cloud-native"]),
            source="heuristic",
        )
        entry2 = KeywordAssignmentCacheEntry(
            assignment=KeywordAssignment(keywords=["in-memory"]),
            source="override",
        )
        cache.set("postgres", entry1)
        cache.set("redis", entry2)

        entries = cache.get_all_entries()
        assert len(entries) == 2
        assert any(name == "postgres" for name, _ in entries)
        assert any(name == "redis" for name, _ in entries)


class TestKeywordAssigner:
    """Tests for KeywordAssigner class."""

    def test_assign_by_exact_tag(self, tmp_path: Path) -> None:
        """Test assignment when keyword matches exact tag."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli", "grpc"],
            description="A test tool",
        )
        # Should match "cli" and "grpc" from tags
        assert "cli" in result.assignment.keywords
        assert "grpc" in result.assignment.keywords
        assert result.source == "heuristic"

    def test_assign_by_name_match(self, tmp_path: Path) -> None:
        """Test assignment when keyword appears in name."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="cli-tool",
            tags=[],
            description="A command line tool",
        )
        # Should match "cli" from name
        assert "cli" in result.assignment.keywords
        assert result.source == "heuristic"

    def test_assign_by_description_match(self, tmp_path: Path) -> None:
        """Test assignment when keyword appears in description."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=[],
            description="A cloud-native application with grpc support",
        )
        # Should match "cloud-native" and "grpc" from description
        assert "cloud-native" in result.assignment.keywords
        assert "grpc" in result.assignment.keywords
        assert result.source == "heuristic"

    def test_assign_no_match_fallback(self, tmp_path: Path) -> None:
        """Test fallback to empty list when no keywords match."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="myapp",
            tags=["custom"],
            description="My custom application",
        )
        assert len(result.assignment.keywords) == 0
        assert result.source == "fallback"
        assert result.confidence == 0.0

    def test_assign_from_cache(self, tmp_path: Path) -> None:
        """Test that cached assignments are returned."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        # First call should use heuristic
        result1 = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="A CLI tool",
        )
        assert result1.source == "heuristic"

        # Second call should use cache
        result2 = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="A CLI tool",
        )
        assert result2.source == "cache"
        assert result2.confidence == 1.0  # Cached entries have confidence 1.0

    def test_assign_with_force_bypass_cache(self, tmp_path: Path) -> None:
        """Test that force=True bypasses cache."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        # First call caches result
        result1 = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="A CLI tool",
        )
        assert result1.source == "heuristic"

        # Second call with force should not use cache
        result2 = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="A CLI tool",
            force=True,
        )
        assert result2.source == "heuristic"  # Not from cache

    def test_assign_tool_object(self, tmp_path: Path) -> None:
        """Test assigning keywords to a Tool object."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        tool = Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis is an in-memory data structure store",
            tags=["redis", "cache", "in-memory"],
            identity=Identity(canonical_name="redis"),
            maintainer=Maintainer(name="library", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000_000),
        )

        result = assigner.assign_tool(tool)
        # Should match "in-memory" from tags and description
        assert "in-memory" in result.assignment.keywords
        assert result.source == "heuristic"

    def test_apply_keywords_to_tool(self, tmp_path: Path) -> None:
        """Test applying keywords to a tool updates its fields."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        tool = Tool(
            id="docker_hub:library/test",
            name="test",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/test",
            description="A cloud-native application",
            tags=["cli"],
            identity=Identity(canonical_name="test"),
            maintainer=Maintainer(name="library", type=MaintainerType.OFFICIAL, verified=True),
            metrics=Metrics(downloads=1_000),
        )

        # Apply keywords
        assigner.apply_keywords(tool)

        # Check that tool was updated
        assert "cli" in tool.keywords
        assert "cloud-native" in tool.keywords
        assert tool.keyword_version == KEYWORD_TAXONOMY_VERSION

    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        """Test that overrides take precedence over heuristics."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        # Add override
        success = assigner.add_override(
            artifact_id="docker_hub:library/test",
            keywords=["custom-keyword-1", "custom-keyword-2"],
            reason="Test override",
        )
        assert success is False  # Custom keywords should be invalid

        # Add valid override
        success = assigner.add_override(
            artifact_id="docker_hub:library/test",
            keywords=["cloud-native", "containerized"],
            reason="Test override",
        )
        assert success is True

        # Assign should use override
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="A CLI tool",
        )
        assert result.source == "override"
        assert "cloud-native" in result.assignment.keywords
        assert "containerized" in result.assignment.keywords
        # Should NOT have "cli" even though it's in tags
        assert "cli" not in result.assignment.keywords

    def test_add_override_with_invalid_keywords(self, tmp_path: Path) -> None:
        """Test that adding override with invalid keywords fails."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        success = assigner.add_override(
            artifact_id="docker_hub:library/test",
            keywords=["invalid-keyword", "also-invalid"],
            reason="Test override",
        )
        assert success is False

    def test_add_override_with_mixed_valid_invalid(self, tmp_path: Path) -> None:
        """Test that adding override with mixed valid/invalid keywords fails."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        success = assigner.add_override(
            artifact_id="docker_hub:library/test",
            keywords=["cloud-native", "invalid-keyword"],
            reason="Test override",
        )
        assert success is False  # Should fail if any keyword is invalid

    def test_override_persists_across_instances(self, tmp_path: Path) -> None:
        """Test that overrides persist to disk and work across instances."""
        # Create assigner and add override
        assigner1 = KeywordAssigner(data_dir=tmp_path)
        assigner1.add_override(
            artifact_id="docker_hub:library/test",
            keywords=["cloud-native"],
            reason="Test override",
        )

        # Create new assigner instance
        assigner2 = KeywordAssigner(data_dir=tmp_path)

        # Should load override from disk
        result = assigner2.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=[],
            description="",
        )
        assert result.source == "override"
        assert "cloud-native" in result.assignment.keywords

    def test_multiple_keywords_matched(self, tmp_path: Path) -> None:
        """Test that all applicable keywords above threshold are assigned."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="kubernetes-cli",
            tags=["cli", "containerized"],
            description="Cloud-native kubernetes tool using grpc and rest-api",
        )
        # Should match multiple keywords
        assert "cli" in result.assignment.keywords
        assert "containerized" in result.assignment.keywords
        assert "cloud-native" in result.assignment.keywords
        assert "grpc" in result.assignment.keywords
        assert "rest-api" in result.assignment.keywords
        assert result.source == "heuristic"

    def test_keywords_sorted_alphabetically(self, tmp_path: Path) -> None:
        """Test that assigned keywords are sorted alphabetically."""
        assigner = KeywordAssigner(data_dir=tmp_path)
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["grpc", "cli", "containerized"],
            description="",
        )
        # Keywords should be sorted
        keywords = result.assignment.keywords
        assert keywords == sorted(keywords)

    def test_confidence_calculation(self, tmp_path: Path) -> None:
        """Test that confidence is calculated based on match quality."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        # Exact tag match should have high confidence
        result1 = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli", "grpc"],
            description="",
        )
        assert result1.confidence > 0.8

        # Description match should have lower confidence
        result2 = assigner.assign(
            artifact_id="docker_hub:library/test2",
            name="test2",
            tags=[],
            description="Uses cli interface",
        )
        assert result2.confidence >= KEYWORD_CONFIDENCE_THRESHOLD
        assert result2.confidence < result1.confidence

    def test_clear_cache(self, tmp_path: Path) -> None:
        """Test clearing the keyword assignment cache."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        # Assign and cache
        assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="",
        )

        # Clear cache
        assigner.clear_cache()

        # Next call should not use cache
        result = assigner.assign(
            artifact_id="docker_hub:library/test",
            name="test",
            tags=["cli"],
            description="",
        )
        assert result.source == "heuristic"  # Not from cache

    def test_canonical_name_resolution(self, tmp_path: Path) -> None:
        """Test that canonical name is used for cache lookup."""
        assigner = KeywordAssigner(data_dir=tmp_path)

        # Assign with explicit canonical name
        result1 = assigner.assign(
            artifact_id="docker_hub:library/postgres",
            name="postgres",
            tags=["cli"],
            description="",
            canonical_name="postgres",
        )
        assert result1.source == "heuristic"

        # Assign different artifact with same canonical name
        result2 = assigner.assign(
            artifact_id="docker_hub:bitnami/postgresql",
            name="postgresql",
            tags=["cli"],
            description="",
            canonical_name="postgres",  # Same canonical name
        )
        # Should use cache because canonical name matches
        assert result2.source == "cache"
