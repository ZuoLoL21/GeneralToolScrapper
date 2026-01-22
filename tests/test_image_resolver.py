"""Tests for ImageResolver with smart tag selection."""

import pytest

from src.models.model_tool import (
    Identity,
    Maintainer,
    MaintainerType,
    Metrics,
    Security,
    SourceType,
    Tool,
)
from src.scanner.image_resolver import ImageResolver


class TestImageResolver:
    """Tests for ImageResolver class."""

    def test_select_tag_with_stable(self) -> None:
        """Test tag selection prefers 'stable' when available."""
        resolver = ImageResolver()
        available_tags = ["latest", "stable", "alpine", "1.0.0"]
        selected = resolver._select_tag(available_tags, "latest")
        assert selected == "stable"

    def test_select_tag_with_latest_no_stable(self) -> None:
        """Test tag selection falls back to 'latest' when 'stable' is unavailable."""
        resolver = ImageResolver()
        available_tags = ["latest", "alpine", "1.0.0"]
        selected = resolver._select_tag(available_tags, "latest")
        assert selected == "latest"

    def test_select_tag_with_alpine_no_stable_or_latest(self) -> None:
        """Test tag selection falls back to 'alpine' when 'stable' and 'latest' are unavailable."""
        resolver = ImageResolver()
        available_tags = ["alpine", "1.0.0", "16-bullseye"]
        selected = resolver._select_tag(available_tags, "latest")
        assert selected == "alpine"

    def test_select_tag_fallback_to_first(self) -> None:
        """Test tag selection falls back to first available tag when no preferred tags exist."""
        resolver = ImageResolver()
        available_tags = ["16-bullseye", "1.0.0", "edge"]
        selected = resolver._select_tag(available_tags, "latest")
        assert selected == "16-bullseye"

    def test_select_tag_empty_list_uses_default(self) -> None:
        """Test tag selection uses default when no tags are available."""
        resolver = ImageResolver()
        selected = resolver._select_tag([], "latest")
        assert selected == "latest"

    def test_resolve_image_ref_official_with_stable(self) -> None:
        """Test resolving official image with stable tag."""
        resolver = ImageResolver()
        tool = Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL",
            identity=Identity(canonical_name="postgres"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            docker_tags=["latest", "stable", "alpine", "16-bullseye"],
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, selected_tag = result
        assert image_ref == "postgres:stable"
        assert selected_tag == "stable"

    def test_resolve_image_ref_official_with_alpine(self) -> None:
        """Test resolving official image falls back to alpine."""
        resolver = ImageResolver()
        tool = Tool(
            id="docker_hub:library/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/redis",
            description="Redis",
            identity=Identity(canonical_name="redis"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            docker_tags=["alpine", "7.0", "6.2"],
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, selected_tag = result
        assert image_ref == "redis:alpine"
        assert selected_tag == "alpine"

    def test_resolve_image_ref_custom_namespace(self) -> None:
        """Test resolving image from custom namespace."""
        resolver = ImageResolver()
        tool = Tool(
            id="docker_hub:bitnami/postgresql",
            name="postgresql",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/bitnami/postgresql",
            description="Bitnami PostgreSQL",
            identity=Identity(canonical_name="postgresql"),
            maintainer=Maintainer(name="Bitnami", type=MaintainerType.COMPANY),
            metrics=Metrics(),
            security=Security(),
            docker_tags=["latest", "15.2.0", "14.7.0"],
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, selected_tag = result
        assert image_ref == "bitnami/postgresql:latest"
        assert selected_tag == "latest"

    def test_resolve_image_ref_no_docker_tags_uses_default(self) -> None:
        """Test resolving image without docker_tags uses default tag."""
        resolver = ImageResolver(default_tag="latest")
        tool = Tool(
            id="docker_hub:library/nginx",
            name="nginx",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/nginx",
            description="NGINX",
            identity=Identity(canonical_name="nginx"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            docker_tags=[],  # Empty list
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, selected_tag = result
        assert image_ref == "nginx:latest"
        assert selected_tag == "latest"

    def test_resolve_image_ref_non_docker_hub_returns_none(self) -> None:
        """Test resolving non-Docker Hub tool returns None."""
        resolver = ImageResolver()
        tool = Tool(
            id="github:postgres/postgres",
            name="postgres",
            source=SourceType.GITHUB,
            source_url="https://github.com/postgres/postgres",
            description="PostgreSQL on GitHub",
            identity=Identity(canonical_name="postgres"),
            maintainer=Maintainer(name="PostgreSQL", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
        )
        result = resolver.resolve_image_ref(tool)
        assert result is None

    def test_resolve_image_ref_custom_default_tag(self) -> None:
        """Test resolver with custom default tag."""
        resolver = ImageResolver(default_tag="16-alpine")
        tool = Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL",
            identity=Identity(canonical_name="postgres"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            docker_tags=[],  # No tags available
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, selected_tag = result
        assert image_ref == "postgres:16-alpine"
        assert selected_tag == "16-alpine"

    def test_resolve_image_ref_priority_order(self) -> None:
        """Test that tag selection follows correct priority order."""
        resolver = ImageResolver()
        tool = Tool(
            id="docker_hub:library/postgres",
            name="postgres",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/postgres",
            description="PostgreSQL",
            identity=Identity(canonical_name="postgres"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            docker_tags=["16-bullseye", "alpine", "edge", "1.0.0"],
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, selected_tag = result
        # Should select 'alpine' since 'stable' and 'latest' are not available
        assert image_ref == "postgres:alpine"
        assert selected_tag == "alpine"

    def test_resolve_image_ref_malformed_tool_id(self) -> None:
        """Test resolver handles malformed tool ID gracefully."""
        resolver = ImageResolver()
        tool = Tool(
            id="malformed_id_without_colon_or_slash",
            name="malformed",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/malformed",
            description="Malformed tool",
            identity=Identity(canonical_name="malformed"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            docker_tags=["latest"],
        )
        result = resolver.resolve_image_ref(tool)
        # Should return None for malformed ID
        assert result is None
