# CLI Reference

This document describes all CLI commands for GeneralToolScraper.

## Installation

```bash
pip install -e ".[dev]"
```

After installation, the `gts` command is available.

## Global Options

These options apply to all commands:

```bash
gts [OPTIONS] COMMAND [ARGS]

Options:
  --verbose, -v       Enable debug logging
  --quiet, -q         Suppress info messages (warnings and errors only)
  --profile PROFILE   Use named configuration profile
  --help              Show help message
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `scrape` | Fetch tools from source APIs |
| `search` | Full-text search across tools |
| `top` | Show top-scoring tools |
| `list` | List tools with filtering |
| `basis` | Generate basis (one tool per subcategory) |
| `compare` | Compare tools side-by-side |
| `explain` | Show scoring details for a tool |
| `categorize` | Classify tools into categories |
| `categories` | Show category statistics |
| `identity` | Show identity resolution details |
| `scan` | Run security scan on a tool |
| `export` | Export data to file |
| `health` | Check external dependencies |
| `cache` | Manage caches |
| `config` | Show configuration |

## Scraping Commands

### `gts scrape`

Fetch tools from source APIs.

```bash
gts scrape [OPTIONS]

Options:
  --source SOURCE     Source to scrape: docker_hub, github, helm
  --all               Scrape all sources
  --force-refresh     Bypass cache, fetch fresh data
  --limit N           Maximum tools to scrape (for testing)
```

**Examples:**

```bash
# Scrape Docker Hub
gts scrape --source docker_hub

# Scrape all sources
gts scrape --all

# Force refresh (bypass cache)
gts scrape --source docker_hub --force-refresh

# Limit for testing
gts scrape --source docker_hub --limit 100
```

**Output:**

```
Scraping docker_hub...
  [████████████████████████████████] 1,234 tools
  Cached: 892, Fresh: 342

Pre-filtering...
  Removed: 156 (low downloads), 23 (deprecated), 12 (spam)
  Remaining: 1,043 tools

Categorizing...
  From cache: 980, LLM classified: 63, Needs review: 4

Computing stats...
  Categories: 10, Subcategories: 47

Scoring...
  Scored: 1,043 tools

Post-filtering...
  Excluded: 89 (low score), Hidden: 34 (experimental)
  Final: 920 visible tools

Saved to data/raw/docker_hub/2024-01-15_scrape.json
```

## Discovery Commands

### `gts search`

Full-text search across tools.

```bash
gts search QUERY [OPTIONS]

Options:
  --category CAT      Filter by category
  --subcategory SUB   Filter by subcategory
  --source SOURCE     Filter by source
  --limit N           Maximum results (default: 20)
  --include-hidden    Include hidden tools
```

**Searched fields (by weight):**

1. `canonical_name` — Highest weight, exact matches first
2. `name` — Display name
3. `aliases` — Alternative names
4. `description` — Tool description
5. `tags` — Source-provided tags

**Examples:**

```bash
# Basic search
gts search "postgres"

# Search within category
gts search "postgres" --category databases

# Exact phrase
gts search "time series" --category databases

# Include hidden tools
gts search "alpine" --include-hidden
```

**Output:**

```
Search results for "postgres" (12 matches)

  #  Score  Tool                              Category
  1  92     postgres                          databases/relational
            docker_hub:library/postgres
  2  88     postgresql                        databases/relational
            helm:bitnami/postgresql
  3  85     postgres-exporter                 monitoring/metrics
            docker_hub:prometheuscommunity/postgres-exporter
  ...
```

### `gts top`

Show top-scoring tools.

```bash
gts top [OPTIONS]

Options:
  --category CAT      Filter by category
  --subcategory SUB   Filter by subcategory
  --limit N           Number of results (default: 10)
  --include-hidden    Include hidden tools
  --modern            Enable time-decay for popularity
```

**Examples:**

```bash
# Top 10 overall
gts top --limit 10

# Top tools in a category
gts top --category databases --limit 5

# Top with time-decay (prefer newer tools)
gts top --category databases --modern

# With profile
gts top --category databases --profile production
```

### `gts list`

List tools with filtering.

```bash
gts list [OPTIONS]

Options:
  --category CAT      Filter by category
  --subcategory SUB   Filter by subcategory
  --source SOURCE     Filter by source
  --lifecycle LIFE    Filter by lifecycle: experimental, active, stable, legacy
  --full              Show all tools (not just top per subcategory)
  --include-hidden    Include hidden tools
  --format FORMAT     Output format: table, json, csv
```

**Examples:**

```bash
# List all databases
gts list --category databases

# Full list with all alternatives
gts list --category databases --full

# Only stable tools
gts list --category databases --lifecycle stable

# JSON output
gts list --category databases --format json
```

### `gts basis`

Generate basis (one top tool per subcategory).

```bash
gts basis [OPTIONS]

Options:
  --category CAT      Limit to specific category
  --output FILE       Write to file (default: stdout)
  --format FORMAT     Output format: table, json
```

**Examples:**

```bash
# Generate full basis
gts basis --output basis.json

# Basis for specific category
gts basis --category databases

# With profile
gts basis --profile production --output prod-basis.json
```

**Output:**

```
Basis: One tool per subcategory

databases/relational:     postgres (92)
databases/document:       mongodb (90)
databases/key-value:      redis (95)
databases/graph:          neo4j (84)
databases/time-series:    influxdb (88)
databases/search:         elasticsearch (91)

monitoring/metrics:       prometheus (94)
monitoring/logging:       loki (87)
monitoring/visualization: grafana (96)
...

Total: 47 tools across 10 categories
```

### `gts compare`

Compare tools side-by-side.

```bash
gts compare TOOL1 TOOL2 [TOOL3...] [OPTIONS]

Options:
  --format FORMAT     Output format: table, json
```

**Examples:**

```bash
# Compare databases
gts compare postgres mysql mariadb

# Compare monitoring tools
gts compare prometheus influxdb
```

**Output:**

```
Comparing: postgres vs mysql vs mariadb

                    postgres        mysql           mariadb
────────────────────────────────────────────────────────────
Quality Score       92              88              85
├── Popularity      88              91              79
├── Security        95              82              88
├── Maintenance     98              90              92
└── Trust           100             85              80

Downloads           1.2B            890M            450M
Last Updated        3 days ago      12 days ago     8 days ago
Lifecycle           stable          stable          stable
Maintainer          official        official        company

Recommendation: postgres (highest overall, best security)
```

## Explainability Commands

### `gts explain`

Show scoring details for a tool.

```bash
gts explain TOOL [OPTIONS]

Options:
  --verbose           Show raw metrics and calculations
```

**Examples:**

```bash
gts explain postgres
gts explain postgres --verbose
```

**Output:**

```
postgres (docker_hub:library/postgres)
══════════════════════════════════════

Quality Score: 92/100
├── Popularity:  88 (z-score: +1.8 in databases/relational)
├── Security:    95 (0 critical, 1 high, 3 medium)
├── Maintenance: 98 (updated 3 days ago, typical: 14 days)
└── Trust:      100 (official image)

Score Analysis
  Dominant Factor: balanced (ratio: 1.1)
  Category Percentile: 94th in databases/relational

Identity
  Canonical Name: postgres
  Resolution: official (confidence: 0.95)
  Variants: 3 (docker_hub, github, helm)

Lifecycle: stable
  Age: 8 years
  Downloads: 1.2B
  Update Pattern: consistent (every 7-14 days)

Filter Status: visible
  No filter reasons applied

Canonical Group
  docker_hub:library/postgres (this)
  github:postgres/postgres
  helm:bitnami/postgresql
```

## Categorization Commands

### `gts categorize`

Classify tools into categories.

```bash
gts categorize [TOOL] [OPTIONS]

Options:
  --all               Categorize all uncategorized tools
  --force             Bypass cache, re-classify
  --dry-run           Show what would be classified without saving
```

**Examples:**

```bash
# Categorize specific tool
gts categorize postgres

# Categorize all uncategorized
gts categorize --all

# Re-classify (bypass cache)
gts categorize postgres --force
```

### `gts categories`

Show category statistics.

```bash
gts categories [OPTIONS]

Options:
  --stats             Show detailed statistics
  --needs-review      Show tools needing review
  --tree              Show as category tree
```

**Examples:**

```bash
# Category tree
gts categories --tree

# Detailed stats
gts categories --stats

# Needs review
gts categories --needs-review
```

**Output (tree):**

```
Category Distribution

databases (234 tools)
├── relational (89)
├── document (45)
├── key-value (32)
├── graph (18)
├── time-series (28)
└── search (22)

monitoring (187 tools)
├── metrics (56)
├── logging (48)
├── tracing (23)
├── visualization (34)
└── alerting (26)
...

uncategorized (12 tools, needs_review: 8)
```

### `gts identity`

Show identity resolution details.

```bash
gts identity [OPTIONS]

Options:
  --low-confidence    Show tools with confidence < 0.8
  --show-variants     Group by canonical name with variants
```

**Examples:**

```bash
# Show low-confidence resolutions
gts identity --low-confidence

# Show variant groupings
gts identity --show-variants
```

## Security Commands

### `gts scan`

Run security scan on a tool.

```bash
gts scan TOOL [OPTIONS]

Options:
  --force             Force rescan (bypass cache)
  --severity LEVELS   Severity levels: CRITICAL,HIGH,MEDIUM,LOW
```

**Examples:**

```bash
# Scan specific tool
gts scan nginx

# Force rescan
gts scan nginx --force

# Only critical/high
gts scan nginx --severity CRITICAL,HIGH
```

## Export Commands

### `gts export`

Export data to file.

```bash
gts export [OPTIONS]

Options:
  --format FORMAT     Output format: json, csv
  --output FILE       Output file path
  --category CAT      Filter by category
  --include-hidden    Include hidden tools
  --include-scores    Include score breakdowns
```

**Examples:**

```bash
# Export all as JSON
gts export --format json --output tools.json

# Export with scores
gts export --format json --output tools.json --include-scores

# Export specific category as CSV
gts export --format csv --output databases.csv --category databases
```

## Utility Commands

### `gts health`

Check external dependencies.

```bash
gts health [OPTIONS]

Options:
  --service SERVICE   Check specific service: docker_hub, github, ollama, trivy
```

**Examples:**

```bash
# Check all
gts health

# Check specific
gts health --service ollama
```

**Output:**

```
Health Check

  Docker Hub API    ✓ OK (authenticated, 180/200 requests remaining)
  GitHub API        ✓ OK (authenticated, 4,892/5,000 requests remaining)
  Ollama            ✓ OK (llama3 loaded, 2.1s response time)
  Trivy             ✓ OK (v0.48.0 installed)

All services healthy.
```

### `gts cache`

Manage caches.

```bash
gts cache COMMAND [OPTIONS]

Commands:
  stats               Show cache statistics
  clear               Clear caches

Options for clear:
  --type TYPE         Cache type: api, security, classification, all
  --confirm           Skip confirmation prompt
```

**Examples:**

```bash
# Show stats
gts cache stats

# Clear all
gts cache clear --type all --confirm

# Clear only API cache
gts cache clear --type api
```

### `gts config`

Show configuration.

```bash
gts config [OPTIONS]

Options:
  --show-mode         Show operating mode details
  --profile PROFILE   Show profile settings
  --env               Show resolved environment variables
```

**Examples:**

```bash
# Show mode
gts config --show-mode

# Show profile
gts config --profile production
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial success (some tools failed, others succeeded) |
| 2 | Complete failure (no tools processed) |
| 3 | Configuration error (missing API keys, invalid config) |

## Common Workflows

### Initial Setup

```bash
# 1. Configure
cp .env.example .env
# Edit .env with API keys

# 2. Health check
gts health

# 3. Initial scrape
gts scrape --source docker_hub

# 4. Explore
gts categories --tree
gts top --limit 10
```

### Finding Tools

```bash
# Search by name
gts search "message queue"

# Browse category
gts list --category messaging

# Get recommendation
gts basis --category messaging

# Compare options
gts compare rabbitmq kafka nats

# Deep dive
gts explain kafka
```

### Production Audit

```bash
# Use production profile
gts top --profile production --category databases

# Check security
gts scan postgres
gts scan nginx

# Export for review
gts export --format json --output audit.json --include-scores
```
