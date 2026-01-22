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

| Command | Description | Status |
|---------|-------------|--------|
| `scrape` | Fetch tools from source APIs | ✅ Implemented |
| `search` | Full-text search across tools | ✅ Implemented |
| `top` | Show top-rated tools | ✅ Implemented |
| `export` | Export data to file | ✅ Implemented |
| `scan` | Scan Docker Hub tools for vulnerabilities | ✅ Implemented |
| `list` | List tools with filtering | ⏳ Planned |
| `basis` | Generate basis (one tool per subcategory) | ⏳ Planned |
| `compare` | Compare tools side-by-side | ⏳ Planned |
| `explain` | Show scoring details for a tool | ⏳ Planned |
| `categorize` | Classify tools into categories | ⏳ Planned |
| `categories` | Show category statistics | ⏳ Planned |
| `identity` | Show identity resolution details | ⏳ Planned |
| `health` | Check external dependencies | ⏳ Planned |
| `cache` | Manage caches | ⏳ Planned |
| `config` | Show configuration | ⏳ Planned |

## Scraping Commands

### `gts scrape`

Fetch tools from source APIs.

```bash
gts scrape [OPTIONS]

Options:
  --source SOURCE       Source to scrape: docker_hub, github, helm
  --all                 Scrape all sources
  --force-refresh       Bypass cache, fetch fresh data
  --limit N             Maximum tools to scrape (for testing)
  --namespaces NS       Docker Hub namespaces: preset (default, popular, all) or custom list (overrides env)
```

**Examples:**

```bash
# Scrape Docker Hub (default: official images only)
gts scrape --source docker_hub

# Use presets for different scopes
gts scrape --source docker_hub --namespaces default      # Official images only (~177 tools)
gts scrape --source docker_hub --namespaces popular      # 9 verified namespaces
gts scrape --source docker_hub --namespaces all          # 70+ well-known namespaces

# Scrape specific custom namespaces
gts scrape --source docker_hub --namespaces "library,bitnami,ubuntu"

# Scrape all sources
gts scrape --all

# Force refresh (bypass cache)
gts scrape --source docker_hub --force-refresh

# Limit for testing
gts scrape --source docker_hub --limit 100

# Combine options
gts scrape --source docker_hub --namespaces "library,bitnami" --limit 500
```

**Docker Hub Namespace Configuration:**

By default, only official Docker images (`library` namespace, ~177 tools) are scraped. To scrape more:

1. **Via environment variable** (set in `.env`):
   ```bash
   DOCKER_HUB_NAMESPACES=default  # Official images only (~177 tools)
   DOCKER_HUB_NAMESPACES=popular  # 9 verified namespaces
   DOCKER_HUB_NAMESPACES=all      # 70+ well-known namespaces
   # or
   DOCKER_HUB_NAMESPACES=library,bitnami,nginx,postgres  # Custom list
   ```

2. **Via CLI option** (overrides environment):
   ```bash
   gts scrape --source docker_hub --namespaces default
   gts scrape --source docker_hub --namespaces popular
   gts scrape --source docker_hub --namespaces all
   gts scrape --source docker_hub --namespaces "library,bitnami,ubuntu"
   ```

**Available presets:**
- `default` (or `library`): Official Docker images only (~177 tools)
- `popular`: Curated list of 9 verified namespaces (library, bitnami, ubuntu, alpine, mysql, postgres, nginx, redis, mongo)
- `all`: Comprehensive list of 70+ well-known namespaces across all categories (see main README.md for complete list)

**Output:**

```
Scraping docker_hub...

Step 1/8: Scraping tools from source...
Step 2/8: Pre-filtering junk tools...
Step 3/8: Classifying tools...
Step 4/8: Assigning keywords...
Step 5/8: Computing statistics...
Step 6/8: Evaluating and scoring tools...
Step 7/8: Post-filtering based on scores and policy...
Step 8/8: Storing processed data...

Pipeline complete!
Processed 920 tools

                 Summary by Category
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Category   ┃ Count ┃ Avg Score ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ databases  │   234 │      78.5 │
│ monitoring │   187 │      75.2 │
│ web        │   156 │      82.1 │
│ messaging  │    89 │      71.3 │
│ ...        │   ... │       ... │
└────────────┴───────┴───────────┘
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
              Search Results for 'postgres' (3 matches)
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name              ┃ Category             ┃ Score ┃ Keywords               ┃ Description                            ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ postgres          │ databases/relational │  92.0 │ database, sql, rela... │ PostgreSQL object-relational databa... │
│ postgres-exporter │ monitoring/metrics   │  85.0 │ prometheus, expor...   │ Prometheus exporter for PostgreSQL ... │
│ postgrest         │ web/server           │  78.5 │ api, rest, postgr...   │ REST API for PostgreSQL databases      │
└───────────────────┴──────────────────────┴───────┴────────────────────────┴────────────────────────────────────────┘
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
                          Top 10 Tools
┏━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━┳━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Rank ┃ Name            ┃ Category             ┃ Score ┃ Pop┃ Sec┃ Maint┃ Trust ┃ Keywords              ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━╇━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│    1 │ nginx           │ web/server           │  95.0 │  92│  98│  95  │  100  │ webserver, proxy, ... │
│    2 │ postgres        │ databases/relational │  92.0 │  88│  95│  98  │  100  │ database, sql, rel... │
│    3 │ redis           │ databases/cache      │  90.5 │  95│  85│  92  │  100  │ cache, keyvalue, i... │
│    4 │ grafana         │ monitoring/visual... │  89.2 │  78│  90│  95  │   95  │ visualization, das... │
│    5 │ prometheus      │ monitoring/metrics   │  88.7 │  85│  88│  91  │   95  │ metrics, timeserie... │
│  ... │ ...             │ ...                  │   ... │ ...│ ...│  ... │  ...  │ ...                   │
└──────┴─────────────────┴──────────────────────┴───────┴────┴────┴──────┴───────┴───────────────────────┘
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

Scan Docker Hub tools for vulnerabilities using Trivy.

**Overview:**

The `scan` command performs lazy security scanning of Docker Hub tools using Trivy. It only scans tools with `status=UNKNOWN` or scans older than 7 days, making it efficient for regular security audits.

**Requirements:**

Trivy must be installed separately:

```bash
# macOS
brew install trivy

# Linux
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Windows
choco install trivy
```

See [Trivy installation guide](https://aquasecurity.github.io/trivy/latest/getting-started/installation/) for more options.

**Command:**

```bash
gts scan [OPTIONS]

Options:
  -l, --limit INTEGER         Limit tools to scan
  --force                     Re-scan all (ignore staleness)
  --tag TEXT                  Docker image tag fallback (default: latest)
                               Note: Scanner uses smart tag selection from pre-fetched tags
  --concurrency INTEGER       Max concurrent scans [default: 3]
  --timeout INTEGER           Scan timeout (seconds) [default: 300]
  --dry-run                   Preview without scanning
```

**New in v2.0: Smart Tag Selection & Incremental Saving**

The scanner now features intelligent tag selection and crash-resilient incremental saving:

1. **Smart Tag Selection**: Automatically selects the best available Docker tag
   - Tags are pre-fetched during scraping (no API calls during scanning)
   - Priority: `stable` → `latest` → `alpine` → first available
   - Falls back to `--tag` value if no tags available
   - Handles images without `latest` tag

2. **Scanned Tag Tracking**: Records which tag was scanned
   - Stored in `security.scanned_tag` field
   - Enables reproducibility and version-specific vulnerability tracking
   - Visible in scan results and tool details

3. **Incremental Saving**: Results saved after each scan
   - If process crashes, completed scans are preserved
   - Can safely interrupt and resume scanning
   - Progress is never lost

**Examples:**

```bash
# Scan tools with unknown or stale security status
gts scan

# Preview what would be scanned (no actual scanning)
gts scan --dry-run

# Scan specific number of tools
gts scan --limit 50

# Force re-scan all Docker Hub tools (ignore staleness)
gts scan --force

# Customize scanning behavior
gts scan --concurrency 5 --timeout 600 --tag alpine

# Scan with specific tag and limit
gts scan --tag 16-alpine --limit 20
```

**Scanning Strategy:**

1. **Lazy scanning**: Only scans tools needing updates:
   - Tools with `status=UNKNOWN`
   - Tools never scanned (no `trivy_scan_date`)
   - Tools with scans older than 7 days
   - Skips tools with cached failures (1-hour cache)

2. **Remote-first approach**:
   - First tries remote scan (fast, no image pull required)
   - Falls back to local scan (`docker pull` + scan) if remote fails
   - Handles timeouts, network issues, and rate limits gracefully

3. **Non-destructive updates**:
   - Failed scans don't overwrite existing security data
   - Maintains `UNKNOWN` status on failure
   - Caches failures for 1 hour to prevent hammering

**Output Example:**

```bash
$ gts scan --limit 10

Scanning 10 tools...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 10/10

Saved 8 updated tools

Scan complete!

           Scan Summary
┏━━━━━━━━━━┳━━━━━━━┓
┃ Metric   ┃ Count ┃
┡━━━━━━━━━━╇━━━━━━━┩
│ Total    │    10 │
│ Succeeded│     8 │
│ Failed   │     2 │
│ Skipped  │     0 │
│ Duration │  45.3s│
└──────────┴───────┘

    Vulnerability Summary
┏━━━━━━━━━━┳━━━━━━━┓
┃ Severity ┃ Count ┃
┡━━━━━━━━━━╇━━━━━━━┩
│ Critical │     3 │
│ High     │    12 │
│ Medium   │    45 │
│ Low      │    89 │
└──────────┴───────┘

Failed scans (2):
  docker_hub:bitnami/unknown-image: Image not found
  docker_hub:library/test: Scan timeout (300s)
```

**Dry Run Output:**

```bash
$ gts scan --dry-run

           Tools to Scan (Dry Run) - 23 tools
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Tool ID                        ┃ Image Ref         ┃ Current Status┃ Last Scan  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ docker_hub:library/postgres    │ postgres:stable   │ unknown       │ Never      │
│ docker_hub:library/nginx       │ nginx:alpine      │ ok            │ 2026-01-14 │
│ docker_hub:bitnami/postgresql  │ bitnami/post...   │ unknown       │ Never      │
│ docker_hub:library/redis       │ redis:alpine      │ unknown       │ Never      │
│ ...                            │ ...               │ ...           │ ...        │
└────────────────────────────────┴───────────────────┴───────────────┴────────────┘

Note: Smart tag selection active (stable → latest → alpine → first)

Run without --dry-run to perform actual scanning
```

**How It Works:**

1. **Filter tools**: Load all tools, filter to Docker Hub tools needing scan
2. **Apply limit**: If `--limit` specified, scan only first N tools
3. **Concurrent scanning**: Scan up to `--concurrency` tools in parallel (default: 3)
4. **Progress tracking**: Real-time progress bar shows scan progress
5. **Update tools**: Successful scans update tool security data
6. **Save data**: Merge updated tools back into storage (preserves existing tools)
7. **Display summary**: Show scan statistics and vulnerability counts

**Security Data Updated:**

For each successful scan, updates:
- `security.vulnerabilities`: Counts by severity (critical, high, medium, low)
- `security.trivy_scan_date`: Timestamp of scan
- `security.scanned_tag`: Docker tag that was scanned (e.g., 'stable', 'alpine', '1.0.5')
- `security.status`: Set to `ok` (no critical/high) or `vulnerable` (has critical/high)

**Example Updated Security Data:**

```json
{
  "security": {
    "status": "ok",
    "trivy_scan_date": "2026-01-21T10:30:00Z",
    "scanned_tag": "stable",
    "vulnerabilities": {
      "critical": 0,
      "high": 1,
      "medium": 3,
      "low": 5
    }
  }
}
```

**Integration with Quality Scoring:**

Security data from scans affects the overall quality score:
- Security dimension contributes 35% to quality score (default weight)
- Tools with critical/high vulnerabilities receive lower security scores
- Regular scanning keeps security data fresh for accurate recommendations

**Common Workflows:**

```bash
# After scraping, scan all unknown tools
gts scrape --source docker_hub --namespaces popular
gts scan

# Weekly security audit (re-scans tools older than 7 days)
gts scan

# Emergency re-scan after vulnerability disclosure
gts scan --force

# Quick spot check of top tools
gts top --limit 20
gts scan --limit 20

# Crash recovery: Resume interrupted scan
gts scan --limit 100
# Press Ctrl+C after ~50 scans complete
# Check progress: cat data/processed/tools.json
gts scan --limit 100
# Automatically skips first 50, continues with remaining 50

# View which tags were scanned
cat data/processed/tools.json | jq '.tools[] | {id, scanned_tag: .security.scanned_tag}'
```

**Performance Expectations:**

| Scenario | Tools | Estimated Time |
|----------|-------|----------------|
| Remote scan (no pull) | 100 | 15-20 minutes |
| Local scan (with pull) | 100 | 45-60 minutes |
| Mixed (80% remote, 20% local) | 100 | 25-30 minutes |

Concurrency default of 3 balances speed vs resource usage. Increase for faster scans on powerful machines.

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

# 2. Health check (when implemented)
# gts health

# 3. Initial scrape
gts scrape --source docker_hub

# 4. Security scan (requires Trivy)
gts scan

# 5. Explore
gts top --limit 10
gts search postgres
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
# Check security of all tools
gts scan

# View top-rated tools (security affects quality score)
gts top --limit 20

# Export for review
gts export --format json --output audit.json

# Re-scan specific high-priority tools
gts scan --force --limit 50
```
