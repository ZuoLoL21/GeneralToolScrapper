"""Tests for ImageResolver with digest-based resolution."""

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

    def test_resolve_image_ref_with_digest_official(self) -> None:
        """Test resolving official image with digest."""
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
            selected_image_tag="latest",
            selected_image_digest="sha256:abc123def456",
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, identifier = result
        assert image_ref == "postgres@sha256:abc123def456"
        assert identifier == "sha256:abc123def456"

    def test_resolve_image_ref_with_digest_custom_namespace(self) -> None:
        """Test resolving custom namespace image with digest."""
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
            selected_image_tag="alpine",
            selected_image_digest="sha256:xyz789uvw321",
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, identifier = result
        assert image_ref == "bitnami/postgresql@sha256:xyz789uvw321"
        assert identifier == "sha256:xyz789uvw321"

    def test_resolve_image_ref_fallback_to_default_tag(self) -> None:
        """Test fallback to default tag when no digest available."""
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
            selected_image_tag=None,
            selected_image_digest=None,
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, identifier = result
        assert image_ref == "nginx:latest"
        assert identifier == "latest"

    def test_resolve_image_ref_fallback_custom_namespace(self) -> None:
        """Test fallback to default tag for custom namespace."""
        resolver = ImageResolver(default_tag="stable")
        tool = Tool(
            id="docker_hub:bitnami/redis",
            name="redis",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/r/bitnami/redis",
            description="Bitnami Redis",
            identity=Identity(canonical_name="redis"),
            maintainer=Maintainer(name="Bitnami", type=MaintainerType.COMPANY),
            metrics=Metrics(),
            security=Security(),
            selected_image_tag=None,
            selected_image_digest=None,
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, identifier = result
        assert image_ref == "bitnami/redis:stable"
        assert identifier == "stable"

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
            selected_image_tag=None,
            selected_image_digest=None,
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, identifier = result
        assert image_ref == "postgres:16-alpine"
        assert identifier == "16-alpine"

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
            selected_image_tag="latest",
            selected_image_digest="sha256:test123",
        )
        result = resolver.resolve_image_ref(tool)
        # Should return None for malformed ID
        assert result is None

    def test_resolve_image_ref_backward_compatibility(self) -> None:
        """Test backward compatibility with tools that don't have digest."""
        resolver = ImageResolver()
        tool = Tool(
            id="docker_hub:library/alpine",
            name="alpine",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/alpine",
            description="Alpine Linux",
            identity=Identity(canonical_name="alpine"),
            maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
            metrics=Metrics(),
            security=Security(),
            # Old tools may not have these fields
            selected_image_tag=None,
            selected_image_digest=None,
        )
        result = resolver.resolve_image_ref(tool)
        assert result is not None
        image_ref, identifier = result
        # Should fall back to default tag
        assert image_ref == "alpine:latest"
        assert identifier == "latest"
