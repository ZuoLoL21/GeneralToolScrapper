"""CLI interface for GeneralToolScraper."""

import csv
import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.models.model_tool import SourceType, Tool
from src.pipeline import load_processed_tools, run_scrape_pipeline

app = typer.Typer(
    name="gts",
    help="GeneralToolScraper - Discover, evaluate, and catalog development tools",
)

console = Console()


def _get_score_color(score: float) -> str:
    """Get color for score display."""
    if score >= 70:
        return "green"
    elif score >= 50:
        return "yellow"
    else:
        return "red"


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


@app.command()
def scrape(
    source: str = typer.Option(None, "--source", "-s", help="Source to scrape (docker_hub)"),
    all_sources: bool = typer.Option(False, "--all", help="Scrape all sources (not implemented)"),
    force_refresh: bool = typer.Option(False, "--force-refresh", help="Bypass cache"),
    limit: int = typer.Option(None, "--limit", help="Limit number of tools to scrape"),
    namespaces: str = typer.Option(
        None,
        "--namespaces",
        help="Comma-separated Docker Hub namespaces (e.g., 'library,bitnami,ubuntu')",
    ),
) -> None:
    """Scrape tools from sources and run full pipeline."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Validate source
    if all_sources:
        console.print("[red]Error:[/red] --all not yet implemented. Use --source instead.")
        raise typer.Exit(1)

    if not source:
        console.print("[red]Error:[/red] Must specify --source or --all")
        raise typer.Exit(1)

    # Validate source value
    try:
        source_type = SourceType(source)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid source '{source}'. Must be: docker_hub")
        raise typer.Exit(1)

    # Parse namespaces for Docker Hub
    namespace_list = None
    if namespaces:
        namespace_list = [ns.strip() for ns in namespaces.split(",") if ns.strip()]
        console.print(f"Using namespaces: {', '.join(namespace_list)}")

    # Run pipeline
    console.print(f"\n[bold]Scraping {source_type.value}...[/bold]\n")

    try:
        tools = run_scrape_pipeline(
            source=source_type,
            force_refresh=force_refresh,
            limit=limit,
            namespaces=namespace_list,
        )

        # Display summary
        console.print(f"\n[bold green]Pipeline complete![/bold green]")
        console.print(f"Processed {len(tools)} tools\n")

        # Create summary table
        table = Table(title="Summary by Category")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="magenta")
        table.add_column("Avg Score", justify="right", style="green")

        # Group by category
        categories: dict[str, list[Tool]] = {}
        for tool in tools:
            cat = tool.primary_category or "uncategorized"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tool)

        # Calculate stats and add rows
        for cat in sorted(categories.keys()):
            cat_tools = categories[cat]
            avg_score = sum(t.quality_score or 0 for t in cat_tools) / len(cat_tools)
            table.add_row(cat, str(len(cat_tools)), f"{avg_score:.1f}")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of results"),
    include_hidden: bool = typer.Option(False, "--include-hidden", help="Include hidden tools"),
) -> None:
    """Search for tools by name or description."""
    # Load tools
    tools = load_processed_tools(category=category, include_hidden=include_hidden)

    if not tools:
        console.print("[yellow]No tools found.[/yellow]")
        return

    # Search: canonical_name > name > description > tags
    query_lower = query.lower()
    matches: list[tuple[Tool, float]] = []

    for tool in tools:
        score = 0.0

        # Canonical name match (highest priority)
        if query_lower in tool.identity.canonical_name.lower():
            score += 10.0

        # Name match
        if query_lower in tool.name.lower():
            score += 8.0

        # Description match
        if query_lower in tool.description.lower():
            score += 5.0

        # Tags match
        for tag in tool.tags:
            if query_lower in tag.lower():
                score += 3.0
                break

        # Add quality score bonus
        if tool.quality_score:
            score += tool.quality_score / 100.0

        if score > 0:
            matches.append((tool, score))

    # Sort by relevance
    matches.sort(key=lambda x: x[1], reverse=True)

    # Limit results
    matches = matches[:limit]

    if not matches:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        return

    # Display results
    table = Table(title=f"Search Results for '{query}' ({len(matches)} matches)")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="blue")
    table.add_column("Score", justify="right")
    table.add_column("Keywords", style="dim")
    table.add_column("Description", style="dim")

    for tool, relevance in matches:
        category_str = f"{tool.primary_category}/{tool.primary_subcategory}"
        score_str = f"{tool.quality_score:.1f}" if tool.quality_score else "N/A"
        score_color = _get_score_color(tool.quality_score or 0)
        keywords_str = ", ".join(tool.keywords[:3]) if tool.keywords else ""
        desc_str = _truncate(tool.description, 40)

        table.add_row(
            tool.name,
            category_str,
            f"[{score_color}]{score_str}[/{score_color}]",
            keywords_str,
            desc_str,
        )

    console.print(table)


@app.command()
def top(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of results"),
    include_hidden: bool = typer.Option(False, "--include-hidden", help="Include hidden tools"),
) -> None:
    """Show top-rated tools."""
    # Load tools
    tools = load_processed_tools(category=category, include_hidden=include_hidden)

    if not tools:
        console.print("[yellow]No tools found.[/yellow]")
        return

    # Sort by quality score
    tools_with_scores = [t for t in tools if t.quality_score is not None]
    tools_with_scores.sort(key=lambda t: t.quality_score or 0, reverse=True)

    # Limit results
    top_tools = tools_with_scores[:limit]

    if not top_tools:
        console.print("[yellow]No scored tools found.[/yellow]")
        return

    # Display results
    title = f"Top {len(top_tools)} Tools"
    if category:
        title += f" in {category}"

    table = Table(title=title)
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Category", style="blue")
    table.add_column("Score", justify="right")
    table.add_column("Pop", justify="right", style="dim")
    table.add_column("Sec", justify="right", style="dim")
    table.add_column("Maint", justify="right", style="dim")
    table.add_column("Trust", justify="right", style="dim")
    table.add_column("Keywords", style="dim")

    for rank, tool in enumerate(top_tools, 1):
        category_str = f"{tool.primary_category}/{tool.primary_subcategory}"
        score = tool.quality_score or 0
        score_color = _get_score_color(score)
        keywords_str = ", ".join(tool.keywords[:3]) if tool.keywords else ""

        breakdown = tool.score_breakdown
        pop_str = f"{breakdown.popularity:.0f}"
        sec_str = f"{breakdown.security:.0f}"
        maint_str = f"{breakdown.maintenance:.0f}"
        trust_str = f"{breakdown.trust:.0f}"

        table.add_row(
            str(rank),
            tool.name,
            category_str,
            f"[{score_color}]{score:.1f}[/{score_color}]",
            pop_str,
            sec_str,
            maint_str,
            trust_str,
            keywords_str,
        )

    console.print(table)


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format (json, csv)"),
    output: str = typer.Option("tools.json", "--output", "-o", help="Output file path"),
    category: str = typer.Option(None, "--category", help="Filter by category"),
    include_hidden: bool = typer.Option(False, "--include-hidden", help="Include hidden tools"),
) -> None:
    """Export tools to a file."""
    # Load tools
    tools = load_processed_tools(category=category, include_hidden=include_hidden)

    if not tools:
        console.print("[yellow]No tools found to export.[/yellow]")
        return

    output_path = Path(output)

    # Export based on format
    try:
        if format == "json":
            # Use pydantic's model_dump for JSON serialization
            data = [tool.model_dump(mode="json") for tool in tools]
            output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        elif format == "csv":
            # Export flattened CSV
            with output_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "id",
                    "name",
                    "source",
                    "category",
                    "subcategory",
                    "quality_score",
                    "downloads",
                    "stars",
                    "keywords",
                    "description",
                ])

                # Data
                for tool in tools:
                    writer.writerow([
                        tool.id,
                        tool.name,
                        tool.source.value,
                        tool.primary_category or "",
                        tool.primary_subcategory or "",
                        tool.quality_score or "",
                        tool.metrics.downloads,
                        tool.metrics.stars,
                        "; ".join(tool.keywords),
                        tool.description,
                    ])

        else:
            console.print(f"[red]Error:[/red] Unsupported format '{format}'. Use 'json' or 'csv'.")
            raise typer.Exit(1)

        console.print(f"[green]Exported {len(tools)} tools to {output_path}[/green]")

    except Exception as e:
        console.print(f"[red]Error exporting:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
