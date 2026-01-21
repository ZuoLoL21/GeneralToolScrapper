"""CLI interface for GeneralToolScraper."""

import asyncio
import csv
import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
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
        help="Docker Hub namespaces: preset ('default', 'popular', 'all') or comma-separated list (e.g., 'library,bitnami,ubuntu')",
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
        from src.consts import DOCKER_HUB_NAMESPACE_PRESETS

        # Check if it's a preset (default, popular, all)
        if namespaces.lower() in DOCKER_HUB_NAMESPACE_PRESETS:
            namespace_list = DOCKER_HUB_NAMESPACE_PRESETS[namespaces.lower()]
            console.print(f"Using '{namespaces}' preset with {len(namespace_list)} namespaces")
        else:
            # Parse as comma-separated list
            namespace_list = [ns.strip() for ns in namespaces.split(",") if ns.strip()]
            console.print(f"Using namespaces: {', '.join(namespace_list)}")

    # Run pipeline
    console.print(f"\n[bold]Scraping {source_type.value}...[/bold]\n")

    try:
        all_tools, new_tools = run_scrape_pipeline(
            source=source_type,
            force_refresh=force_refresh,
            limit=limit,
            namespaces=namespace_list,
        )

        # Display summary
        console.print(f"\n[bold green]Pipeline complete![/bold green]")
        console.print(f"Total tools: {len(all_tools)} ({len(new_tools)} new)\n")

        # Create summary table for ALL tools
        table_all = Table(title="Summary of All Tools by Category")
        table_all.add_column("Category", style="cyan")
        table_all.add_column("Count", justify="right", style="magenta")
        table_all.add_column("Avg Score", justify="right", style="green")

        # Group all tools by category
        categories_all: dict[str, list[Tool]] = {}
        for tool in all_tools:
            cat = tool.primary_category or "uncategorized"
            if cat not in categories_all:
                categories_all[cat] = []
            categories_all[cat].append(tool)

        # Calculate stats and add rows
        for cat in sorted(categories_all.keys()):
            cat_tools = categories_all[cat]
            avg_score = sum(t.quality_score or 0 for t in cat_tools) / len(cat_tools)
            table_all.add_row(cat, str(len(cat_tools)), f"{avg_score:.1f}")

        console.print(table_all)

        # Create summary table for NEW tools (only if there are new tools)
        if new_tools:
            console.print()  # Add spacing
            table_new = Table(title="Summary of Newly Scraped Tools by Category")
            table_new.add_column("Category", style="cyan")
            table_new.add_column("Count", justify="right", style="magenta")
            table_new.add_column("Avg Score", justify="right", style="green")

            # Group new tools by category
            categories_new: dict[str, list[Tool]] = {}
            for tool in new_tools:
                cat = tool.primary_category or "uncategorized"
                if cat not in categories_new:
                    categories_new[cat] = []
                categories_new[cat].append(tool)

            # Calculate stats and add rows
            for cat in sorted(categories_new.keys()):
                cat_tools = categories_new[cat]
                avg_score = sum(t.quality_score or 0 for t in cat_tools) / len(cat_tools)
                table_new.add_row(cat, str(len(cat_tools)), f"{avg_score:.1f}")

            console.print(table_new)
        else:
            console.print("\n[yellow]No new tools were scraped in this run.[/yellow]")

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


@app.command()
def scan(
    limit: int = typer.Option(None, "--limit", "-l", help="Limit tools to scan"),
    force: bool = typer.Option(False, "--force", help="Re-scan all (ignore staleness)"),
    tag: str = typer.Option("latest", "--tag", help="Docker image tag to scan"),
    concurrency: int = typer.Option(3, "--concurrency", help="Max concurrent scans"),
    timeout: int = typer.Option(300, "--timeout", help="Scan timeout (seconds)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without scanning"),
) -> None:
    """Scan Docker Hub tools for vulnerabilities using Trivy."""
    from src.consts import DEFAULT_DATA_DIR, TRIVY_FAILED_SCAN_TTL, TRIVY_STALENESS_DAYS
    from src.scanner import ImageResolver, ScanCache, ScanOrchestrator, TrivyScanner
    from src.storage.cache.file_caching import FileCache
    from src.storage.permanent_storage.file_manager import FileManager

    # Configure logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Check Trivy installed
    scanner = TrivyScanner(timeout=timeout)
    if not scanner.is_trivy_installed():
        console.print("[red]Error: Trivy not installed[/red]")
        console.print(
            "\nInstall Trivy from: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        )
        console.print("\nQuick install:")
        console.print("  macOS:   brew install trivy")
        console.print("  Linux:   curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin")
        console.print("  Windows: choco install trivy")
        raise typer.Exit(1)

    # Load processed tools
    file_manager = FileManager(DEFAULT_DATA_DIR)
    all_tools = file_manager.load_processed()

    if not all_tools:
        console.print("[yellow]No tools found. Run 'gts scrape' first.[/yellow]")
        raise typer.Exit(1)

    # Setup scanner components
    cache_dir = Path(DEFAULT_DATA_DIR) / "cache"
    file_cache = FileCache(cache_dir=cache_dir, default_ttl=0)
    scan_cache = ScanCache(file_cache, failed_scan_ttl=TRIVY_FAILED_SCAN_TTL)
    resolver = ImageResolver(default_tag=tag)
    orchestrator = ScanOrchestrator(
        scanner=scanner,
        resolver=resolver,
        scan_cache=scan_cache,
        staleness_days=TRIVY_STALENESS_DAYS,
    )

    # Filter tools needing scan
    tools_to_scan = orchestrator.filter_tools_needing_scan(all_tools, force=force)

    if not tools_to_scan:
        console.print("[green]All tools are up to date![/green]")
        console.print("\nUse --force to re-scan all tools")
        return

    # Apply limit
    if limit:
        tools_to_scan = tools_to_scan[:limit]

    # Dry run mode
    if dry_run:
        table = Table(title=f"Tools to Scan (Dry Run) - {len(tools_to_scan)} tools")
        table.add_column("Tool ID", style="cyan")
        table.add_column("Image Ref", style="blue")
        table.add_column("Current Status", style="yellow")
        table.add_column("Last Scan", style="dim")

        for tool in tools_to_scan:
            image_ref = resolver.resolve_image_ref(tool) or "N/A"
            last_scan = (
                tool.security.trivy_scan_date.strftime("%Y-%m-%d")
                if tool.security.trivy_scan_date
                else "Never"
            )
            table.add_row(
                tool.id,
                image_ref,
                tool.security.status.value,
                last_scan,
            )

        console.print(table)
        console.print(f"\n[dim]Run without --dry-run to perform actual scanning[/dim]")
        return

    # Run scans with progress bar
    console.print(f"\n[bold]Scanning {len(tools_to_scan)} tools...[/bold]\n")

    async def run_scans():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning...", total=len(tools_to_scan))

            def on_progress(current: int, total: int):
                progress.update(task, completed=current)

            result = await orchestrator.scan_batch(
                tools_to_scan,
                concurrency=concurrency,
                progress_callback=on_progress,
            )

            return result

    # Run async scans
    result = asyncio.run(run_scans())

    # Save updated tools (merge mode)
    if result.updated_tools:
        file_manager.save_processed(result.updated_tools, merge=True)
        console.print(f"\n[green]Saved {len(result.updated_tools)} updated tools[/green]")

    # Display summary
    console.print(f"\n[bold green]Scan complete![/bold green]")
    summary_table = Table(title="Scan Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", justify="right", style="magenta")

    summary_table.add_row("Total", str(result.total))
    summary_table.add_row("Succeeded", str(result.succeeded))
    summary_table.add_row("Failed", str(result.failed))
    summary_table.add_row("Skipped", str(result.skipped))
    summary_table.add_row("Duration", f"{result.duration_seconds:.1f}s")

    console.print(summary_table)

    # Vulnerability summary table (only if we have updated tools)
    if result.updated_tools:
        console.print()
        vuln_table = Table(title="Vulnerability Summary")
        vuln_table.add_column("Severity", style="cyan")
        vuln_table.add_column("Count", justify="right")

        # Aggregate vulnerability counts
        total_vulns = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for tool in result.updated_tools:
            total_vulns["critical"] += tool.security.vulnerabilities.critical
            total_vulns["high"] += tool.security.vulnerabilities.high
            total_vulns["medium"] += tool.security.vulnerabilities.medium
            total_vulns["low"] += tool.security.vulnerabilities.low

        vuln_table.add_row("Critical", f"[red]{total_vulns['critical']}[/red]")
        vuln_table.add_row("High", f"[orange1]{total_vulns['high']}[/orange1]")
        vuln_table.add_row("Medium", f"[yellow]{total_vulns['medium']}[/yellow]")
        vuln_table.add_row("Low", f"[dim]{total_vulns['low']}[/dim]")

        console.print(vuln_table)

    # Show failures if any
    if result.failures:
        console.print(f"\n[yellow]Failed scans ({len(result.failures)}):[/yellow]")
        for tool_id, error in list(result.failures.items())[:5]:
            console.print(f"  [dim]{tool_id}:[/dim] {error[:80]}")
        if len(result.failures) > 5:
            console.print(f"  [dim]... and {len(result.failures) - 5} more[/dim]")


if __name__ == "__main__":
    app()
