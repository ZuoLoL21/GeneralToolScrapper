"""Pipeline orchestration for the complete tool processing workflow.

This module coordinates all steps of the tool processing pipeline:
1. Scrape raw tools from source
2. Pre-filter (remove junk)
3. Classify (assign categories)
4. Assign keywords
5. Generate stats (global + category)
6. Evaluate/score tools
7. Post-filter (policy-based)
8. Store results
"""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.categorization.classifier import Classifier
from src.categorization.keyword_assigner import KeywordAssigner
from src.consts import DEFAULT_DATA_DIR
from src.evaluators.registry import EvaluatorRegistry
from src.evaluators.stats_generator import generate_all_stats
from src.filters.post_filter import PostFilter
from src.filters.pre_filter import PreFilter
from src.models.model_eval import FilterThresholds, ScoreWeights
from src.models.model_stats import EvalContext
from src.models.model_tool import SourceType, Tool
from src.scrapers import DockerHubScraper
from src.storage.permanent_storage.file_manager import FileManager

logger = logging.getLogger(__name__)


async def _scrape_async(scraper: DockerHubScraper, limit: int | None = None) -> list[Tool]:
    """Async helper to scrape tools with optional limit.

    Args:
        scraper: The scraper instance to use.
        limit: Optional limit on number of tools to scrape.

    Returns:
        List of scraped tools.
    """
    tools = []
    count = 0
    async for tool in scraper.scrape():
        tools.append(tool)
        count += 1
        if limit is not None and count >= limit:
            break
    return tools


def run_scrape_pipeline(
    source: SourceType | str,
    force_refresh: bool = False,
    limit: int | None = None,
    data_dir: Path | None = None,
    namespaces: list[str] | None = None,
) -> tuple[list[Tool], list[Tool]]:
    """Run full pipeline: scrape → pre-filter → classify → keywords → stats → evaluate → post-filter → store.

    Args:
        source: Source platform to scrape (docker_hub, github, helm).
        force_refresh: If True, bypass classifier/keyword caches.
        limit: Optional limit on number of tools to scrape.
        data_dir: Data directory path. Uses default if None.
        namespaces: Optional list of Docker Hub namespaces to scrape. None = use env or default.

    Returns:
        Tuple of (all_tools, new_tools) where:
        - all_tools: List of all tools after merging with existing data
        - new_tools: List of newly scraped tools in this run
    """
    logger.info(f"Starting pipeline for source: {source}")
    start_time = datetime.now(UTC)

    # Initialize components
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    file_manager = FileManager(data_dir)
    pre_filter = PreFilter()
    post_filter = PostFilter()
    classifier = Classifier(data_dir=data_dir)
    keyword_assigner = KeywordAssigner(data_dir=data_dir)
    evaluator_registry = EvaluatorRegistry()

    # Step 1: Scrape raw tools
    logger.info("Step 1/8: Scraping tools from source...")
    source_type = source if isinstance(source, SourceType) else SourceType(source)

    if source_type == SourceType.DOCKER_HUB:
        scraper = DockerHubScraper(namespaces=namespaces)
        raw_tools = asyncio.run(_scrape_async(scraper, limit))
    else:
        raise ValueError(f"Unsupported source: {source_type}")

    logger.info(f"Scraped {len(raw_tools)} tools from {source_type.value}")

    # Save raw data
    file_manager.save_raw(source_type, raw_tools)

    # Step 2: Pre-filter (remove junk)
    logger.info("Step 2/8: Pre-filtering junk tools...")
    filtered_tools = pre_filter.apply(raw_tools)
    logger.info(f"After pre-filter: {len(filtered_tools)} tools")

    # Early exit if no tools remain
    if not filtered_tools:
        logger.warning(
            "No tools passed pre-filtering. All tools were excluded as junk. "
            "Consider adjusting pre-filter criteria or scraping different namespaces."
        )
        file_manager.save_processed([], merge=True)
        # Load all existing tools to return
        all_tools = file_manager.load_processed() or []
        return all_tools, []

    # Step 3: Classify (assign categories)
    logger.info("Step 3/8: Classifying tools...")
    for tool in filtered_tools:
        classifier.apply_classification(tool, force=force_refresh)
    logger.info("Classification complete")

    # Step 4: Assign keywords
    logger.info("Step 4/8: Assigning keywords...")
    for tool in filtered_tools:
        keyword_assigner.apply_keywords(tool, force=force_refresh)
    logger.info("Keyword assignment complete")

    # Step 5: Generate stats (global + category)
    logger.info("Step 5/8: Computing statistics...")
    global_stats, category_stats = generate_all_stats(filtered_tools)
    logger.info(
        f"Generated stats for {global_stats.total_tools} tools "
        f"across {len(category_stats)} categories"
    )

    # Save stats
    file_manager.save_stats(global_stats, category_stats)

    # Step 6: Evaluate/score tools
    logger.info("Step 6/8: Evaluating and scoring tools...")
    weights = ScoreWeights()  # Use defaults
    eval_context = EvalContext(
        global_stats=global_stats,
        category_stats=category_stats,
        weights=weights,
        thresholds=FilterThresholds(),
        score_version="1.0",
    )

    current_time = datetime.now(UTC)
    evaluator_registry.evaluate_batch(filtered_tools, eval_context, current_time)
    logger.info("Scoring complete")

    # Step 7: Post-filter (policy-based)
    logger.info("Step 7/8: Post-filtering based on scores and policy...")
    thresholds = FilterThresholds()
    final_tools = post_filter.apply(filtered_tools, thresholds)
    logger.info(f"After post-filter: {len(final_tools)} tools")

    # Step 8: Store results
    logger.info("Step 8/8: Storing processed data...")
    _, new_count = file_manager.save_processed(filtered_tools, merge=True)  # Merge with existing

    # Load all tools (including previously scraped ones)
    all_tools = file_manager.load_processed() or []

    # Calculate duration
    duration = (datetime.now(UTC) - start_time).total_seconds()
    logger.info(
        f"Pipeline complete in {duration:.1f}s: "
        f"{len(all_tools)} total tools ({new_count} new), "
        f"{len(final_tools)} visible"
    )

    return all_tools, filtered_tools


def load_processed_tools(
    category: str | None = None,
    include_hidden: bool = False,
    data_dir: Path | None = None,
) -> list[Tool]:
    """Load processed tools with optional filtering.

    Args:
        category: Optional category filter (e.g., "databases").
        include_hidden: If True, include hidden tools. Excluded tools are never included.
        data_dir: Data directory path. Uses default if None.

    Returns:
        List of tools matching filters.
    """
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    file_manager = FileManager(data_dir)

    # Load all processed tools
    tools = file_manager.load_processed()
    if not tools:
        logger.warning("No processed tools found")
        return []

    logger.info(f"Loaded {len(tools)} processed tools")

    # Filter by category
    if category:
        tools = [t for t in tools if t.primary_category == category]
        logger.info(f"After category filter ({category}): {len(tools)} tools")

    # Filter by visibility
    from src.models.model_tool import FilterState

    if not include_hidden:
        tools = [t for t in tools if t.filter_status.state == FilterState.VISIBLE]
        logger.info(f"After visibility filter: {len(tools)} tools")
    else:
        # Still exclude EXCLUDED tools even with --include-hidden
        tools = [t for t in tools if t.filter_status.state != FilterState.EXCLUDED]
        logger.info(f"After excluding excluded tools: {len(tools)} tools")

    return tools


def main() -> None:
    """Example pipeline execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=== Pipeline Orchestration Example ===\n")

    # Example 1: Run pipeline for Docker Hub (limited)
    print("1. Running pipeline for Docker Hub (limit 20 tools)...")
    try:
        all_tools, new_tools = run_scrape_pipeline(
            source=SourceType.DOCKER_HUB,
            limit=20,
            force_refresh=False,
        )
        print(f"   Pipeline complete: {len(all_tools)} total tools, {len(new_tools)} new\n")

        # Show sample results
        if new_tools:
            print("   Sample new results:")
            for tool in new_tools[:3]:
                print(f"   - {tool.name}")
                print(f"     Category: {tool.primary_category}/{tool.primary_subcategory}")
                print(f"     Keywords: {', '.join(tool.keywords[:5]) if tool.keywords else '(none)'}")
                print(f"     Score: {tool.quality_score:.1f}/100")
                print()
    except Exception as e:
        print(f"   Error: {e}\n")

    # Example 2: Load processed tools
    print("2. Loading processed tools (visible only)...")
    try:
        loaded_tools = load_processed_tools(include_hidden=False)
        print(f"   Loaded {len(loaded_tools)} visible tools\n")

        # Show stats
        if loaded_tools:
            categories = {}
            for tool in loaded_tools:
                cat = tool.primary_category or "uncategorized"
                categories[cat] = categories.get(cat, 0) + 1

            print("   Tools by category:")
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {cat}: {count}")
            print()
    except Exception as e:
        print(f"   Error: {e}\n")

    # Example 3: Load tools from specific category
    print("3. Loading tools from 'databases' category...")
    try:
        db_tools = load_processed_tools(category="databases", include_hidden=True)
        print(f"   Loaded {len(db_tools)} database tools\n")

        if db_tools:
            # Sort by score
            db_tools.sort(key=lambda t: t.quality_score or 0, reverse=True)
            print("   Top 3 database tools:")
            for tool in db_tools[:3]:
                print(f"   - {tool.name}: {tool.quality_score:.1f}/100")
            print()
    except Exception as e:
        print(f"   Error: {e}\n")

    print("Done!")


if __name__ == "__main__":
    main()
