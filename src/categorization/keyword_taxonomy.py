"""Keyword taxonomy definitions for tool property classification.

Defines fixed keyword categories used for classifying tools by their
technical properties (platform, architecture, protocol, etc.).
Keywords are metadata only - not scored, just displayed/exported for
search and filtering.
"""

from typing import Final

# Keyword taxonomy version for cache invalidation
KEYWORD_TAXONOMY_VERSION: Final[str] = "1.0"

# Define all keyword categories with keywords
KEYWORD_CATEGORIES: Final[dict[str, tuple[str, ...]]] = {
    "platform": (
        "desktop",
        "mobile",
        "web",
        "cli",
        "gui",
        "cloud-native",
        "on-premise",
        "serverless",
        "edge",
        "embedded",
    ),
    "architecture": (
        "distributed",
        "centralized",
        "high-throughput",
        "low-latency",
        "eventually-consistent",
        "horizontally-scalable",
        "vertically-scalable",
        "microservices",
        "monolithic",
        "event-driven",
    ),
    "protocol": (
        "rest-api",
        "graphql",
        "grpc",
        "protobuf",
        "websocket",
        "http",
        "https",
        "tcp",
        "udp",
        "mqtt",
        "amqp",
        "stomp",
    ),
    "optimization": (
        "optimized",
        "highly-optimized",
        "memory-efficient",
        "cpu-efficient",
        "lightweight",
        "resource-intensive",
        "high-performance",
        "minimal",
    ),
    "data": (
        "structured",
        "unstructured",
        "semi-structured",
        "real-time",
        "batch",
        "streaming",
        "transactional",
        "analytical",
        "time-series",
        "geospatial",
    ),
    "persistence": (
        "persistent",
        "ephemeral",
        "in-memory",
        "disk-based",
        "replicated",
        "sharded",
        "cached",
        "durable",
        "volatile",
    ),
    "deployment": (
        "containerized",
        "kubernetes-native",
        "docker",
        "helm-chart",
        "operator",
        "stateless",
        "stateful",
        "daemonset",
    ),
    "security": (
        "encrypted",
        "authenticated",
        "authorized",
        "audited",
        "compliance",
        "zero-trust",
        "mtls",
        "tls",
        "rbac",
        "sso",
    ),
    "integration": (
        "plugin-system",
        "extensible",
        "webhook",
        "modular",
        "message-queue",
        "api-gateway",
        "middleware",
        "adapter",
    ),
    "ecosystem": (
        "polyglot",
        "java-ecosystem",
        "python-ecosystem",
        "node-ecosystem",
        "go-ecosystem",
        "rust-ecosystem",
        "dotnet-ecosystem",
        "cncf",
    ),
    "governance": (
        "open-source",
        "commercial",
        "community-driven",
        "vendor-backed",
        "foundation-hosted",
        "apache-foundation",
        "linux-foundation",
        "enterprise",
    ),
    "maturity": (
        "production-ready",
        "battle-tested",
        "proven-scale",
        "emerging",
        "innovative",
        "mature",
        "stable",
        "alpha",
        "beta",
    ),
}


def get_all_keywords() -> list[str]:
    """Get list of all keywords across all categories."""
    all_keywords = []
    for keywords in KEYWORD_CATEGORIES.values():
        all_keywords.extend(keywords)
    return all_keywords


def get_all_categories() -> list[str]:
    """Get list of all keyword category names."""
    return list(KEYWORD_CATEGORIES.keys())


def get_keywords_by_category(category: str) -> list[str]:
    """Get list of keywords for a specific category.

    Args:
        category: Category name (e.g., "platform", "architecture").

    Returns:
        List of keywords in the category, or empty list if category not found.
    """
    return list(KEYWORD_CATEGORIES.get(category, ()))


def is_valid_keyword(keyword: str) -> bool:
    """Check if a keyword exists in the taxonomy.

    Args:
        keyword: The keyword to validate.

    Returns:
        True if the keyword exists in any category, False otherwise.
    """
    all_keywords = get_all_keywords()
    return keyword in all_keywords


def is_valid_category(category: str) -> bool:
    """Check if a keyword category exists.

    Args:
        category: The category name to validate.

    Returns:
        True if the category exists, False otherwise.
    """
    return category in KEYWORD_CATEGORIES


def get_keyword_category(keyword: str) -> str | None:
    """Get the category that contains a keyword.

    Args:
        keyword: The keyword to look up.

    Returns:
        The category name containing the keyword, or None if not found.
    """
    for category, keywords in KEYWORD_CATEGORIES.items():
        if keyword in keywords:
            return category
    return None


def main() -> None:
    """Example usage of keyword taxonomy module."""
    print("=== Keyword Taxonomy Module Example ===\n")

    # Show taxonomy overview
    print("1. Keyword taxonomy overview:")
    total_keywords = 0
    for category, keywords in KEYWORD_CATEGORIES.items():
        print(f"   - {category}: {len(keywords)} keywords")
        print(f"      Examples: {', '.join(keywords[:3])}...")
        total_keywords += len(keywords)
    print(f"\n   Total keywords: {total_keywords}")
    print(f"   Total categories: {len(KEYWORD_CATEGORIES)}")
    print(f"   Taxonomy version: {KEYWORD_TAXONOMY_VERSION}\n")

    # Validate keywords
    print("2. Validate keywords:")
    test_keywords = [
        "cloud-native",
        "distributed",
        "grpc",
        "invalid-keyword",
        "containerized",
    ]
    for kw in test_keywords:
        is_valid = is_valid_keyword(kw)
        category = get_keyword_category(kw) if is_valid else "N/A"
        status = f"VALID ({category})" if is_valid else "INVALID"
        print(f"   '{kw}' -> {status}")
    print()

    # Get keywords by category
    print("3. Get keywords by category:")
    test_categories = ["platform", "protocol", "invalid-category"]
    for cat in test_categories:
        keywords = get_keywords_by_category(cat)
        if keywords:
            print(f"   {cat}: {', '.join(keywords[:5])}...")
        else:
            print(f"   {cat}: NOT FOUND")
    print()

    print("Done!")


if __name__ == "__main__":
    main()
