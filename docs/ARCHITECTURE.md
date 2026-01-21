# Architecture

This document describes the system architecture, code structure, data flow, and design principles of GeneralToolScraper.

## System Overview

GeneralToolScraper is a pipeline-based system that:

1. **Scrapes** tool metadata from multiple sources (Docker Hub, GitHub, Helm Charts)
2. **Filters** obvious junk before processing
3. **Categorizes** tools using LLM classification (or manual fallback)
4. **Computes statistics** for normalization
5. **Scores** tools on quality dimensions
6. **Filters** again based on policy and scores
7. **Stores** results for querying and export

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Scrape    │───▶│ Pre-Filter  │───▶│ Categorize  │───▶│ Compute     │
│   Sources   │    │ (junk)      │    │ (LLM/manual)│    │ Stats       │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                │
                                                                ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Export    │◀───│ Post-Filter │◀───│   Score     │◀───│   Store     │
│   / Query   │    │ (policy)    │    │ (evaluate)  │    │   Raw       │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Code Structure

```
GeneralToolScraper/
├── gts/
│   ├── __init__.py
│   ├── cli.py                    # Typer-based CLI orchestration
│   ├── config.py                 # Configuration loading and validation
│   │
│   ├── models/                   # Pydantic data models
│   │   ├── __init__.py
│   │   ├── tool.py               # Tool, Metrics, Security, Maintainer, Identity
│   │   ├── classification.py    # Classification, ClassificationOverride
│   │   ├── scoring.py            # EvalContext, ScoreBreakdown, ToolScore
│   │   └── storage.py            # DistributionStats, CategoryStats, GlobalStats
│   │
│   ├── scrapers/                 # API clients for each source
│   │   ├── __init__.py
│   │   ├── base.py               # BaseScraper abstract class
│   │   ├── docker_hub.py         # Docker Hub API client
│   │   ├── github.py             # GitHub API client (Phase 2)
│   │   └── helm.py               # Artifact Hub API client (Phase 3)
│   │
│   ├── evaluators/               # Stateless scoring functions
│   │   ├── __init__.py
│   │   ├── base.py               # BaseEvaluator protocol
│   │   ├── registry.py           # Wires evaluators, produces final scores
│   │   ├── popularity.py         # Log-transform + Z-score normalization
│   │   ├── security.py           # Vulnerability severity weighting
│   │   ├── maintenance.py        # Update recency vs frequency
│   │   ├── trust.py              # Publisher verification tiers
│   │   └── stats_generator.py    # Computes category/global statistics
│   │
│   ├── categorization/           # Tool classification
│   │   ├── __init__.py
│   │   ├── classifier.py         # Main classification orchestrator
│   │   ├── llm_client.py         # Ollama integration
│   │   ├── taxonomy.py           # Category/subcategory definitions
│   │   └── identity.py           # Canonical name resolution
│   │
│   ├── storage/                  # Data persistence
│   │   ├── __init__.py
│   │   ├── file_manager.py       # JSON file operations
│   │   └── cache.py              # TTL-based caching
│   │
│   └── filters/                  # Pre and post filtering
│       ├── __init__.py
│       ├── pre_filter.py         # Junk removal before stats
│       └── post_filter.py        # Policy-based filtering after scoring
│
├── data/                         # Runtime data (gitignored except examples)
│   ├── raw/                      # Immutable scrape results
│   ├── processed/                # Derived data (tools.json, scores.json)
│   ├── cache/                    # Ephemeral caches
│   └── overrides.json            # Manual classification overrides
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                         # Documentation
├── pyproject.toml
├── .env.example
└── README.md
```

## Data Storage

The system separates raw scraped data from derived computations:

### Directory Structure

| Path | Purpose | Mutability |
|------|---------|------------|
| `data/raw/{source}/{date}_scrape.json` | Immutable scrape results with timestamps | Append-only |
| `data/raw/{source}/latest.json` | Symlink to most recent scrape | Updated on scrape |
| `data/processed/tools.json` | Unified tool catalog merging all sources | Regenerable |
| `data/processed/scores.json` | Computed quality scores with breakdowns | Regenerable |
| `data/processed/stats/global_stats.json` | Cross-category statistics | Regenerable |
| `data/processed/stats/category_stats.json` | Per-category statistics | Regenerable |
| `data/cache/` | LLM classifications, Trivy scans, API responses | Ephemeral |
| `data/overrides.json` | Manual classification overrides | User-managed |

### Design Rationale

| Decision | Rationale |
|----------|-----------|
| Separate raw from processed | Raw data is immutable audit trail; scores can be recomputed with different algorithms |
| Timestamped scrapes | Enables diffing, trend analysis, rollback to previous state |
| Stats in separate files | Loaded once for scoring all tools; avoids repeated computation |
| Cache is ephemeral | Can be deleted without data loss; rebuilt on demand |

## Pipeline Details

### Two-Phase Filtering

The pipeline uses two distinct filtering phases to ensure clean statistics:

| Phase | When | What's Removed | Why |
|-------|------|----------------|-----|
| **Pre-stat filtering** | After scrape, before categorization | Obvious junk: 0 downloads, deprecated, forks, spam | Prevents garbage from polluting category statistics |
| **Post-score filtering** | After scoring | Policy-based: security failures, staleness, low scores | Uses scores to make informed decisions |

**Why this ordering matters:**

1. Categorization must happen before stats (stats are per-category)
2. Stats must exist before scoring (popularity is category-relative)
3. Post-filtering uses scores, so must come last

### Pipeline Steps (Detailed)

```python
# 1. Scrape: Fetch raw data from source APIs
raw_tools = scraper.scrape(source="docker_hub")
storage.save_raw(source, raw_tools)

# 2. Pre-filter: Remove obvious junk
filtered_tools = pre_filter.apply(raw_tools)
# Removes: 0 downloads, deprecated, forks, spam patterns

# 3. Categorize: Assign categories via LLM or fallback
for tool in filtered_tools:
    tool.classification = classifier.classify(tool)
# Uses cache, then overrides, then LLM, then fallback

# 4. Compute stats: Calculate distributions for normalization
global_stats = stats_generator.compute_global(filtered_tools)
category_stats = stats_generator.compute_by_category(filtered_tools)
storage.save_stats(global_stats, category_stats)

# 5. Score: Evaluate each tool
context = EvalContext(global_stats, category_stats, config)
for tool in filtered_tools:
    tool.scores = registry.evaluate(tool, context)

# 6. Post-filter: Apply policy-based filtering
final_tools = post_filter.apply(filtered_tools)
# Removes: critical vulns, stale tools, below-threshold scores
# Marks: hidden (experimental, legacy), excluded (policy violations)

# 7. Store: Persist processed data
storage.save_processed(final_tools)
storage.save_scores(scores)
```

## Design Principles

### Stateless Evaluators

Evaluators are pure functions with no hidden state. This makes them trivially testable and parallelizable.

```python
class Evaluator(Protocol):
    def evaluate(self, tool: Tool, context: EvalContext) -> float:
        """
        Pure function: same inputs always produce same outputs.
        All external data comes through EvalContext.
        """
        ...
```

The `EvalContext` provides all external data needed for evaluation:

- Category statistics (for relative scoring)
- Global distributions (for normalization)
- Config thresholds (user preferences)

**Why this matters:**

- Evaluators never query storage directly
- No hidden state means predictable behavior
- Easy to test with mock contexts
- Can parallelize evaluation across tools

### Uniform Data Model

All scrapers return a uniform `Tool` model defined in `models/tool.py`. This allows evaluators to process tools from any source identically.

```python
# Scraper contract
class BaseScraper(ABC):
    @abstractmethod
    def scrape(self) -> list[Tool]:
        """Return normalized Tool objects regardless of source."""
        ...
```

### Data Separation

The system explicitly separates three data categories:

| Category | Examples | Storage |
|----------|----------|---------|
| **Observed** | downloads, stars, last_updated, vulnerabilities | `tool.observed` namespace |
| **Inferred** | lifecycle, trust_score, quality_score, is_safe | `tool.inferred` namespace |
| **User overlays** | manual overrides, custom weights | `overrides.json`, config |

**Why separate observed from inferred:**

- Auditing: Know which data came from sources vs. algorithms
- Debugging: Trace score anomalies to source data
- ML readiness: Clean separation of features (observed) from labels (inferred)

## Schema Evolution & Versioning

Multiple schemas evolve independently and require version tracking:

| Schema | Version Field | Location | Migration Strategy |
|--------|--------------|----------|-------------------|
| Raw scrape | `version` | Each scrape file | Transform on load |
| Tool model | `schema_version` | `tools.json` | Re-process from raw |
| Taxonomy | `taxonomy_version` | Tool records | Re-categorize affected tools |
| Score algorithm | `score_version` | `scores.json` | Re-score all tools |
| Identity rules | `identity_version` | Config | Re-resolve canonical names |

### Principles

- **Raw data is immutable** — Never modify raw scrape files; transform on load
- **Processed data is regenerable** — Can always be rebuilt from raw + current algorithms
- **Version changes trigger re-computation** — Changing taxonomy version re-categorizes; changing score algorithm re-scores
- **Backwards compatibility not guaranteed** — Old exports may not match new runs (use `score_version` to detect)

### Version Check Example

```python
if loaded_scores.score_version != current_score_version():
    logger.warning("Score version mismatch - results may differ from previous runs")
```

## Failure Modes & Observability

### External Service Failures

| Service | Failure Mode | Handling | CLI Feedback |
|---------|-------------|----------|--------------|
| Docker Hub API | Schema change | Log warning, skip unparseable fields | `WARNING: Unexpected field in response` |
| Docker Hub API | Rate limit (429) | Exponential backoff, resume from queue | `INFO: Rate limited, retrying in Xs` |
| Trivy | Not installed | Skip security scoring, use `status: unknown` | `WARNING: Trivy not found, security scores unavailable` |
| Trivy | Output format change | Log warning, fall back to unknown | `WARNING: Could not parse Trivy output` |
| Ollama | Unavailable | Route to `uncategorized`, flag for review | `WARNING: Ollama unavailable, skipping classification` |
| Ollama | Timeout | Retry once, then route to uncategorized | `WARNING: Classification timeout for {tool}` |

### CLI Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial success (some tools failed, others succeeded) |
| 2 | Complete failure (no tools processed) |
| 3 | Configuration error (missing API keys, invalid config) |

### Logging

- Default: `INFO` level to stderr
- `--verbose` / `-v`: `DEBUG` level with detailed API responses
- `--quiet` / `-q`: `WARNING` and above only
- All logs include timestamps and component tags (e.g., `[scraper:docker_hub]`)

### Health Checks

```bash
gts health              # Check all external dependencies
gts health --service ollama   # Check specific service
```

Returns status of: Docker Hub API, GitHub API, Ollama, Trivy installation.

## Resilience Patterns

### Rate Limiting

- Exponential backoff on 429 responses (initial: 1s, max: 60s)
- Jitter to prevent thundering herd
- Per-source rate limit state tracked in config

### Request Caching

- Location: `data/cache/` filesystem with configurable TTL
- Key: `(source, endpoint, params)` tuple hash
- TTL: 24h for metadata, 7d for security scans (configurable)
- Bypass: `--force-refresh` flag

### Scrape Queue Persistence

- Queue persisted to disk for recovery across restarts
- Resume from last successful item on restart
- Configurable delay between requests (`SCRAPE_DELAY_MS`)

## API Sources

### Docker Hub

- **Endpoint:** `https://hub.docker.com/v2/`
- **Auth:** Optional (improves rate limits)
- **Rate Limit:** 100 pulls/6hr (anon), 200 pulls/6hr (auth)
- **Pagination:** Cursor-based

### GitHub

- **Endpoint:** REST API v3 or GraphQL
- **Auth:** Personal Access Token recommended
- **Rate Limit:** 60 req/hr (anon), 5000 req/hr (auth)

### Helm Charts (Artifact Hub)

- **Endpoint:** `https://artifacthub.io/api/v1/`
- **Auth:** Optional
