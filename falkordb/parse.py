import json
from datetime import datetime

from falkordb import FalkorDB
from src.models import Tool

# Constants
FALKOR_DB_URL = "falkor://localhost:6379"
GRAPH_NAME = "Tool Search"


def serialize_datetime(dt: datetime | None) -> str | None:
    """Convert datetime to ISO format string."""
    return dt.isoformat() if dt else None


def get_or_create_source_node(graph, source: str) -> str:
    """Get or create a Source node."""
    query = """
    MERGE (s:Source {name: $source})
    RETURN s
    """
    graph.query(query, {"source": source})
    return source


def get_or_create_lifecycle_node(graph, lifecycle: str) -> str:
    """Get or create a Lifecycle node."""
    query = """
    MERGE (l:Lifecycle {name: $lifecycle})
    RETURN l
    """
    graph.query(query, {"lifecycle": lifecycle})
    return lifecycle


def get_or_create_maintainer_node(
    graph, maintainer_name: str, maintainer_type: str, verified: bool
) -> str:
    """Get or create a Maintainer node."""
    query = """
    MERGE (m:Maintainer {name: $name, type: $type, verified: $verified})
    RETURN m
    """
    graph.query(query, {"name": maintainer_name, "type": maintainer_type, "verified": verified})
    return maintainer_name


def get_or_create_identity_node(
    graph, canonical_name: str, aliases: list[str], variants: list[str]
) -> str:
    """Get or create an Identity node."""
    query = """
    MERGE (i:Identity {name: $name})
    ON CREATE SET i.aliases = $aliases, i.variants = $variants
    ON MATCH SET i.aliases = $aliases, i.variants = $variants
    RETURN i
    """
    graph.query(
        query,
        {
            "name": canonical_name,
            "aliases": json.dumps(aliases),
            "variants": json.dumps(variants),
        },
    )
    return canonical_name


def get_or_create_tag_node(graph, tag: str) -> str:
    """Get or create a Tag node."""
    query = """
    MERGE (t:Tag {name: $tag})
    RETURN t
    """
    graph.query(query, {"tag": tag})
    return tag


def get_or_create_category_node(graph, category: str) -> str:
    """Get or create a Category node."""
    query = """
    MERGE (c:Category {name: $category})
    RETURN c
    """
    graph.query(query, {"category": category})
    return category


def get_or_create_subcategory_node(graph, subcategory: str, parent_category: str) -> str:
    """Get or create a Subcategory node and link it to its parent Category."""
    # Ensure parent category exists first
    get_or_create_category_node(graph, parent_category)

    # Create subcategory and relationship in a single atomic query
    query = """
    MERGE (c:Category {name: $parent_category})
    MERGE (sc:Subcategory {name: $subcategory})
    MERGE (sc)-[:BELONGS_TO]->(c)
    RETURN sc, c
    """
    graph.query(query, {"subcategory": subcategory, "parent_category": parent_category})

    return subcategory


def add_to_falkordb(graph, tool_dict):
    """Add tool to graph."""
    tool: Tool = Tool.model_validate(tool_dict)

    # Create Tool node with all properties
    tool_properties = {
        "id": tool.id,
        "name": tool.name,
        "source": tool.source.value,
        "source_url": tool.source_url,
        "description": tool.description,
        # Metrics
        "downloads": tool.metrics.downloads,
        "stars": tool.metrics.stars,
        "usage_amount": tool.metrics.usage_amount,
        # Security
        "security_status": tool.security.status.value,
        "trivy_scan_date": serialize_datetime(tool.security.trivy_scan_date),
        "scanned_tag": tool.security.scanned_tag,
        "scanned_digest": tool.security.scanned_digest,
        "is_safe": tool.security.is_safe,
        "vuln_critical": tool.security.vulnerabilities.critical,
        "vuln_high": tool.security.vulnerabilities.high,
        "vuln_medium": tool.security.vulnerabilities.medium,
        "vuln_low": tool.security.vulnerabilities.low,
        # Maintenance
        "created_at": serialize_datetime(tool.maintenance.created_at),
        "last_updated": serialize_datetime(tool.maintenance.last_updated),
        "update_frequency_days": tool.maintenance.update_frequency_days,
        "is_deprecated": tool.maintenance.is_deprecated,
        # Docker/Tags
        "selected_image_tag": tool.selected_image_tag,
        "selected_image_digest": tool.selected_image_digest,
        "digest_fetch_date": serialize_datetime(tool.digest_fetch_date),
        "docker_tags": json.dumps(tool.docker_tags),
        "digest_fetch_status": tool.digest_fetch_status,
        "digest_fetch_error": tool.digest_fetch_error,
        "digest_fetch_attempts": tool.digest_fetch_attempts,
        "tag_extraction_status": tool.tag_extraction_status,
        "is_deprecated_image_format": tool.is_deprecated_image_format,
        # Categories
        "taxonomy_version": tool.taxonomy_version,
        "primary_category": tool.primary_category,
        "primary_subcategory": tool.primary_subcategory,
        "secondary_categories": json.dumps(tool.secondary_categories),
        # Keywords
        "keyword_version": tool.keyword_version,
        # Scores
        "quality_score": tool.quality_score,
        "score_popularity": tool.score_breakdown.popularity,
        "score_security": tool.score_breakdown.security,
        "score_maintenance": tool.score_breakdown.maintenance,
        "score_trust": tool.score_breakdown.trust,
        "score_dominant_dimension": tool.score_analysis.dominant_dimension.value,
        "score_dominance_ratio": tool.score_analysis.dominance_ratio,
        # Filter
        "filter_state": tool.filter_status.state.value,
        "filter_reasons": json.dumps(tool.filter_status.reasons),
        # Metadata
        "scraped_at": serialize_datetime(tool.scraped_at),
        "schema_version": tool.schema_version,
    }

    # Create Tool node
    create_tool_query = """
    MERGE (t:Tool {id: $id})
    SET t = $properties
    RETURN t
    """
    graph.query(create_tool_query, {"id": tool.id, "properties": tool_properties})

    # Create and connect Source node
    get_or_create_source_node(graph, tool.source.value)
    graph.query(
        """
        MATCH (t:Tool {id: $tool_id})
        MATCH (s:Source {name: $source})
        MERGE (t)-[:FROM_SOURCE]->(s)
    """,
        {"tool_id": tool.id, "source": tool.source.value},
    )

    # Create and connect Lifecycle node
    get_or_create_lifecycle_node(graph, tool.lifecycle.value)
    graph.query(
        """
        MATCH (t:Tool {id: $tool_id})
        MATCH (l:Lifecycle {name: $lifecycle})
        MERGE (t)-[:IN_LIFECYCLE]->(l)
    """,
        {"tool_id": tool.id, "lifecycle": tool.lifecycle.value},
    )

    # Create and connect Maintainer node
    get_or_create_maintainer_node(
        graph, tool.maintainer.name, tool.maintainer.type.value, tool.maintainer.verified
    )
    graph.query(
        """
        MATCH (t:Tool {id: $tool_id})
        MATCH (m:Maintainer {name: $maintainer_name, type: $maintainer_type, verified: $verified})
        MERGE (t)-[:MAINTAINED_BY]->(m)
    """,
        {
            "tool_id": tool.id,
            "maintainer_name": tool.maintainer.name,
            "maintainer_type": tool.maintainer.type.value,
            "verified": tool.maintainer.verified,
        },
    )

    # Create and connect Identity node
    get_or_create_identity_node(
        graph, tool.identity.canonical_name, tool.identity.aliases, tool.identity.variants
    )
    graph.query(
        """
        MATCH (t:Tool {id: $tool_id})
        MATCH (i:Identity {name: $canonical_name})
        MERGE (t)-[:HAS_IDENTITY]->(i)
    """,
        {"tool_id": tool.id, "canonical_name": tool.identity.canonical_name},
    )

    # Create and connect Tag nodes (from both tags and keywords)
    all_tags = list(set(tool.tags + tool.keywords))
    if all_tags:
        for tag in all_tags:
            if tag:  # Skip empty tags
                get_or_create_tag_node(graph, tag)
                graph.query(
                    """
                    MATCH (t:Tool {id: $tool_id})
                    MATCH (tag:Tag {name: $tag_name})
                    MERGE (t)-[:HAS_TAG]->(tag)
                """,
                    {"tool_id": tool.id, "tag_name": tag},
                )

    # Create and connect Category and Subcategory nodes
    if tool.primary_category:
        # Create and connect to Category
        get_or_create_category_node(graph, tool.primary_category)
        graph.query(
            """
            MATCH (t:Tool {id: $tool_id})
            MATCH (c:Category {name: $category_name})
            MERGE (t)-[:IN_CATEGORY {is_primary: true}]->(c)
        """,
            {"tool_id": tool.id, "category_name": tool.primary_category},
        )

        # Create and connect to Subcategory if exists
        if tool.primary_subcategory:
            get_or_create_subcategory_node(graph, tool.primary_subcategory, tool.primary_category)
            graph.query(
                """
                MATCH (t:Tool {id: $tool_id})
                MATCH (sc:Subcategory {name: $subcategory_name})
                MERGE (t)-[:IN_SUBCATEGORY {is_primary: true}]->(sc)
            """,
                {"tool_id": tool.id, "subcategory_name": tool.primary_subcategory},
            )

    for secondary_category in tool.secondary_categories:
        ret = secondary_category.split("/")
        category = ret[0]
        subcategory = ret[1]

        get_or_create_category_node(graph, category)
        get_or_create_subcategory_node(graph, subcategory, category)

        graph.query(
            """
            MATCH (t:Tool {id: $tool_id})
            MATCH (c:Category {name: $category_name})
            MERGE (t)-[:IN_CATEGORY {is_primary: false}]->(c)
        """,
            {"tool_id": tool.id, "category_name": category},
        )
        graph.query(
            """
                MATCH (t:Tool {id: $tool_id})
                MATCH (sc:Subcategory {name: $subcategory_name})
                MERGE (t)-[:IN_SUBCATEGORY {is_primary: true}]->(sc)
            """,
            {"tool_id": tool.id, "subcategory_name": subcategory},
        )


def get_tools():
    with open("tools.json") as f:
        dict_tools = json.load(f)["tools"]

    return [Tool.model_validate(dict_tool) for dict_tool in dict_tools]


def main():
    tools = get_tools()
    print(f"Processing {len(tools)} tools...")

    # Connect to FalkorDB once
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph(GRAPH_NAME)

    for i, tool in enumerate(tools):
        try:
            print(f"\n[{i + 1}/{len(tools)}] Adding tool: {tool.id}")
            print(f"  - Tags: {len(tool.tags)}, Keywords: {len(tool.keywords)}")
            print(f"  - Primary category: {tool.primary_category}/{tool.primary_subcategory}")
            print(f"  - Secondary categories: {tool.secondary_categories}")
            print(f"  - Identity: {tool.identity.canonical_name}")

            add_to_falkordb(graph, tool.model_dump())
            print("  ✓ Successfully added")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback

            traceback.print_exc()
    print("\n=== Done! ===")


if __name__ == "__main__":
    main()
