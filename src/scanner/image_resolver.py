"""Image reference resolver for Docker Hub tools."""

import logging

from src.models.model_tool import SourceType, Tool

logger = logging.getLogger(__name__)


class ImageResolver:
    """Converts Tool IDs to scannable Docker image references."""

    def __init__(self, default_tag: str = "latest"):
        """Initialize ImageResolver.

        Args:
            default_tag: Default tag to use for images (default: "latest")
        """
        self.default_tag = default_tag

    def resolve_image_ref(self, tool: Tool) -> str | None:
        """Convert tool ID to Docker image reference.

        Examples:
            docker_hub:library/postgres → postgres:latest
            docker_hub:bitnami/postgresql → bitnami/postgresql:latest
            github:postgres/postgres → None (skip non-Docker)

        Args:
            tool: Tool to resolve image reference for

        Returns:
            Docker image reference string, or None if not a Docker Hub tool
        """
        # Only handle Docker Hub tools
        if tool.source != SourceType.DOCKER_HUB:
            logger.debug(f"Skipping non-Docker Hub tool: {tool.id}")
            return None

        # Parse tool ID format: docker_hub:namespace/name
        try:
            _, image_path = tool.id.split(":", 1)
            namespace, name = image_path.split("/", 1)

            # Special case: library namespace → just image name
            if namespace == "library":
                image_ref = f"{name}:{self.default_tag}"
            else:
                image_ref = f"{namespace}/{name}:{self.default_tag}"

            logger.debug(f"Resolved {tool.id} → {image_ref}")
            return image_ref

        except ValueError as e:
            logger.warning(f"Failed to parse tool ID '{tool.id}': {e}")
            return None


def main():
    """Example usage of ImageResolver."""
    from src.models.model_tool import Identity, Maintainer, MaintainerType, Metrics, Security

    # Test cases
    resolver = ImageResolver()

    # Test 1: Official image (library namespace)
    tool1 = Tool(
        id="docker_hub:library/postgres",
        name="postgres",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/_/postgres",
        description="PostgreSQL database",
        identity=Identity(canonical_name="postgres"),
        maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL),
        metrics=Metrics(),
        security=Security(),
    )
    print(f"Tool: {tool1.id}")
    print(f"Image ref: {resolver.resolve_image_ref(tool1)}")
    print()

    # Test 2: Custom namespace
    tool2 = Tool(
        id="docker_hub:bitnami/postgresql",
        name="postgresql",
        source=SourceType.DOCKER_HUB,
        source_url="https://hub.docker.com/r/bitnami/postgresql",
        description="Bitnami PostgreSQL",
        identity=Identity(canonical_name="postgresql"),
        maintainer=Maintainer(name="Bitnami", type=MaintainerType.COMPANY),
        metrics=Metrics(),
        security=Security(),
    )
    print(f"Tool: {tool2.id}")
    print(f"Image ref: {resolver.resolve_image_ref(tool2)}")
    print()

    # Test 3: Non-Docker Hub tool
    tool3 = Tool(
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
    print(f"Tool: {tool3.id}")
    print(f"Image ref: {resolver.resolve_image_ref(tool3)}")
    print()

    # Test 4: Custom tag
    resolver_custom = ImageResolver(default_tag="16-alpine")
    print(f"Tool: {tool1.id} (with custom tag)")
    print(f"Image ref: {resolver_custom.resolve_image_ref(tool1)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
