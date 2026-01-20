# GeneralToolScraper

A tool aggregation system that discovers, evaluates, and catalogs useful development tools from multiple sources (Docker Hub, GitHub, Helm Charts).

## Quick Start

```bash
# Clone and setup
cd GeneralToolScrapper
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Run
gts scrape --source docker_hub
gts search "postgres" --category databases
```

## Core Concepts

### Tool Disambiguation

Multiple artifacts may represent the same underlying tool (e.g., `docker_hub:library/postgres`, `helm:bitnami/postgresql`, `github:postgres/postgres`). The system handles this by:

1. Assigning each artifact a unique ID: `{source}:{namespace}/{name}`
2. Grouping related artifacts under a `canonical_name` (e.g., "postgres")
3. Preferring official/verified images when recommending
4. Tracking all variants for comparison

### Quality Scoring Philosophy

Tools are scored on four dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Security | 0.35 | Vulnerability severity from Trivy scans |
| Popularity | 0.25 | Downloads/stars normalized within category |
| Maintenance | 0.25 | Update recency relative to update frequency |
| Trust | 0.15 | Publisher verification and community reputation |

Raw metrics are always persisted, allowing scores to be recomputed with different weights or algorithms.

### Tool Basis Strategy

The system stores all quality tools but groups them by function—it doesn't pick arbitrary winners.

**Why not pick one winner per category?**
- Tools like Postgres vs MySQL have real trade-offs (JSONB support, licensing, ecosystem)
- "Best" depends on context (existing stack, team experience, cost)
- Picking one loses valuable alternatives

**Output Modes:**
- **Basis Mode** (`--basis`): One top-scoring tool per subcategory for quick recommendations
- **Full Mode** (`--full`): All qualified tools with scores for comparing alternatives

**Example Functional Grouping:**
```
databases/
├── relational/    → postgres (92), mysql (88), mariadb (85)
├── document/      → mongodb (90), couchdb (78)
└── key-value/     → redis (95), memcached (82)

monitoring/
├── metrics/       → prometheus (94), influxdb (86)
├── visualization/ → grafana (96), kibana (88)
└── logging/       → elasticsearch (90), loki (85)
```

### Auto-Categorization

Categories are generated from:
1. Tags from Docker Hub / GitHub topics
2. Keyword matching in descriptions
3. Known tool mappings (curated seed list)

Fallback when tags are missing: curated mappings → keyword extraction → manual override file.

## Architecture

```
GeneralToolScrapper/
├── Scrapers/
│   ├── BaseScraper.py      # Abstract base class defining scraper contract
│   ├── DockerHub.py        # Docker Hub API scraper 
│   ├── Github.py           # GitHub API scraper
│   └── HelmCharts.py       # Artifact Hub scraper
│
├── Evaluators/
│   ├── Registry.py         # Wires evaluators together, produces final scores
│   ├── BaseEvaluator.py    # Abstract base class defining evaluator contract
│   └── Implementations/
│       ├── Popularity.py       # Downloads, stars, usage normalization
│       ├── Security.py         # Vulnerability scoring, Trivy results
│       ├── Maintenance.py      # Update frequency, recency scoring
│       └── Trust.py            # Publisher verification, community reputation
│
├── Storage/
│   ├── FileManager.py      # JSON/filesystem persistence
│   └── DatabaseManagers/   # Possible database persistence later
│
├── cli.py                  # Typer-based CLI orchestration
├── Models.py               # Pydantic models (Tool, Metrics, etc.)
└── config.toml             # Runtime configuration
```

### Design Principles

**Stateless Evaluators:** Evaluators are pure functions with no hidden state. The contract enforces this:

```python
class Evaluator(Protocol):
    def evaluate(self, tool: Tool, context: EvalContext) -> float: ...
```

Where `EvalContext` provides all external data needed for evaluation:
- Category statistics (for relative scoring)
- Global distributions (for normalization)
- Config thresholds (user preferences)

This prevents evaluators from querying storage directly or accumulating hidden state, making them trivially testable and parallelizable.

**Uniform Data Model:** Scrapers return a uniform model defined in `Models.py`, allowing evaluators to process tools from any source identically.

**Data Separation:** The system separates:
1. **Raw scraped fields** — Direct API data (downloads, stars, dates, tags)
2. **Derived metrics** — Computed values (scores, normalized metrics)
3. **User overlays** (future) — Custom weights, manual category overrides

**Artifact Scores vs Tool Scores (Future):** Currently, scores are artifact-centric—each Docker image, GitHub repo, or Helm chart gets its own score. Eventually, a canonical tool may aggregate scores from multiple artifacts:

```
postgres (tool score: 93)
├── docker_hub:library/postgres  → 94
├── github:postgres/postgres     → 91
└── helm:bitnami/postgresql      → 89
```

The aggregation strategy (max, weighted average, source preference) remains configurable. For now, artifacts are scored independently, but the data model supports grouping via `canonical_name` and `variants`.

## CLI Usage

```bash
# Scraping
gts scrape --all                          # Scrape all sources
gts scrape --source docker_hub            # Scrape specific source

# Discovery
gts search "postgres" --category databases
gts top --category monitoring --limit 10
gts compare postgres mysql                # Compare tools in same subcategory

# Basis Generation
gts basis --output basis.json             # One tool per subcategory
gts basis --category databases            # Basis for specific category
gts list --full --category databases      # Full list with alternatives

# Security
gts scan --tool nginx                     # Run Trivy scan on specific tool

# Export
gts export --format json --output tools.json
```

### Filtering Logic

**Auto-Excluded:**
- Downloads below `MIN_DOWNLOADS` threshold
- No updates in > `MAX_DAYS_SINCE_UPDATE` days
- Marked as deprecated
- Critical security vulnerabilities (configurable)

**Inclusion Priority:**
1. Official images/repos
2. Verified publishers
3. Company-maintained with high activity
4. User-maintained with exceptional metrics

## Configuration

### Environment Variables

```bash
# API Keys
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
DOCKER_HUB_USERNAME=your_username
DOCKER_HUB_TOKEN=your_token

# Storage
STORAGE_TYPE=sqlite              # sqlite | json | postgresql
DATABASE_URL=sqlite:///tools.db

# Scraping Behavior
SCRAPE_DELAY_MS=1000             # Delay between requests
MAX_CONCURRENT_REQUESTS=5

# Filtering Thresholds
MIN_DOWNLOADS=1000               # Minimum downloads to consider
MIN_STARS=100                    # Minimum stars to consider
MAX_DAYS_SINCE_UPDATE=365        # Max days since last update

# Security Scanning
TRIVY_ENABLED=true
TRIVY_SEVERITY=CRITICAL,HIGH
TRIVY_MODE=lazy                  # lazy: on-demand/top-N | eager: scan all
```

### Caching

API responses are cached aggressively to reduce rate limit impact:

- **Location:** Filesystem cache with configurable TTL
- **Key:** `(source, endpoint, params)` tuple
- **TTL:** 24h for metadata, 7d for security scans (configurable)
- **Bypass:** `--force-refresh` flag

### Rate Limit Handling

- Exponential backoff on 429 responses
- Scrape queue persisted to disk for recovery across restarts
- Per-source rate limit state tracked in config

## API Sources

### Docker Hub
- **Endpoint:** `https://hub.docker.com/v2/`
- **Auth:** Optional (improves rate limits)
- **Rate Limit:** 100 pulls/6hr (anon), 200 pulls/6hr (auth)

### GitHub
- **Endpoint:** REST API v3 or GraphQL
- **Auth:** Personal Access Token recommended
- **Rate Limit:** 60 req/hr (anon), 5000 req/hr (auth)

### Helm Charts (Artifact Hub)
- **Endpoint:** `https://artifacthub.io/api/v1/`
- **Auth:** Optional

## Data Model

<details>
<summary>Tool Schema (click to expand)</summary>

```python
{
    # IDENTIFICATION
    "id": str,                    # "{source}:{namespace}/{name}"
    "name": str,                  # Display name from source
    "source": str,                # "docker_hub" | "github" | "helm" | "web"
    "source_url": str,            # Direct link to tool on source platform
    "description": str,           # Short description from source

    "identity": {
        "canonical_name": str,    # Normalized name grouping related artifacts
        "aliases": list[str],     # Alternative search names
        "variants": list[str],    # IDs of same tool from different sources
    },

    # MAINTAINER INFO
    "maintainer": {
        "name": str,              # Publisher name or organization
        "type": str,              # "official" | "company" | "user"
        "verified": bool,         # Platform verification badge
    },

    # RAW METRICS
    "metrics": {
        "downloads": int,         # Total download/pull count
        "stars": int,             # Community appreciation metric
        "usage_amount": int,      # Secondary usage (forks, etc.)
    },

    # SECURITY
    "security": {
        "status": str,            # "ok" | "vulnerable" | "unknown"
        "trivy_scan_date": datetime | None,
        "vulnerabilities": {
            "critical": int,      # CVSS 9.0-10.0
            "high": int,          # CVSS 7.0-8.9
            "medium": int,        # CVSS 4.0-6.9
            "low": int,           # CVSS 0.1-3.9
        },
        "is_safe": bool,          # Computed safety flag
    },

    # MAINTENANCE
    "maintenance": {
        "created_at": datetime,
        "last_updated": datetime,
        "update_frequency_days": int,
        "is_deprecated": bool,
    },

    # CATEGORIZATION
    "tags": list[str],            # Raw tags from source
    "taxonomy_version": str,      # Categorization version for re-runs
    "primary_category": str,      # "databases", "monitoring", etc.
    "primary_subcategory": str,   # "relational", "metrics", etc.
    "secondary_categories": list[str],
    "lifecycle": str,             # "experimental" | "active" | "stable" | "legacy"

    # DERIVED SCORES
    "quality_score": float,       # Weighted composite 0-100
    "score_breakdown": {
        "popularity": float,
        "security": float,
        "maintenance": float,
        "trust": float,
    },
    "scraped_at": datetime,
}
```

</details>

### Scoring Algorithm Details

```
quality_score = (
    0.25 * popularity_score +
    0.35 * security_score +
    0.25 * maintenance_score +
    0.15 * trust_score
)
```

**Popularity:** Softmax normalization (reduces impact of outliers) relative to category average. Falls back to global normalization if category sample size is too small.

**Security:** `100 - (critical×60 + high×10 + medium×1 + low×0.5)`, minimum 0. Unknown status receives a light penalty (70) rather than 0.

**Maintenance:** Based on update recency relative to typical update frequency. A tool that updates yearly being 2 months stale is fine; one that updates daily being 2 months stale is concerning.

**Trust:**
- Official: 100
- Verified company: 90
- Company/User: 60 (can increase with community reputation)

## Development

### Setup

```bash
cd GeneralToolScrapper
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -e ".[dev]"
cp .env.example .env       # Configure API keys

# Verify setup
pytest
ruff check .
ruff format .
```

### Dependencies

```toml
[project]
dependencies = [
    "httpx>=0.27",           # Async HTTP client
    "pydantic>=2.0",         # Data validation
    "sqlalchemy>=2.0",       # Database ORM
    "typer>=0.12",           # CLI framework
    "rich>=13.0",            # Terminal formatting
    "python-dotenv>=1.0",    # Environment management
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
]
```

### Testing Strategy

- **Unit tests:** Scraper parsing, scoring algorithms
- **Integration tests:** API calls with mocked responses
- **E2E tests:** Full scrape-evaluate-store pipeline

## Roadmap

### Phase 1: Docker Hub MVP

#### 1. Foundation

- [ ] **Project scaffolding**
  - [ ] Set up `pyproject.toml` with dependencies (httpx, pydantic, typer, rich)
  - [ ] Configure ruff/mypy for linting and type checking
  - [ ] Create `.env.example` with all configuration variables
  - [ ] Set up pytest with async support

- [ ] **Data model (`Models.py`)**
  - [ ] Define `Tool` pydantic model matching the schema in README
  - [ ] Define `Metrics`, `Security`, `Maintainer`, `Identity` sub-models
  - [ ] Define `EvalContext` for stateless evaluator pattern
  - [ ] Add model validation and serialization tests

#### 2. Docker Hub Scraper

- [ ] **API client (`Scrapers/DockerHub.py`)**
  - [ ] Implement `BaseScraper` abstract class with uniform contract
  - [ ] Docker Hub search endpoint integration
  - [ ] Pagination handling (cursor-based)
  - [ ] Image details fetching (tags, description, metrics)
  - [ ] Parse and normalize response to `Tool` model

- [ ] **Resilience**
  - [ ] Rate limiting with exponential backoff on 429s
  - [ ] Request caching with configurable TTL (24h default)
  - [ ] Scrape queue persistence for recovery across restarts
  - [ ] Configurable delay between requests (`SCRAPE_DELAY_MS`)

#### 3. Storage Layer

- [ ] **File-based storage (`Storage/FileManager.py`)**
  - [ ] JSON persistence for scraped tools
  - [ ] Separate raw data from derived scores
  - [ ] Load/save with atomic writes
  - [ ] Query by ID, category, canonical name

#### 4. Evaluators

- [ ] **Evaluator framework**
  - [ ] Implement `BaseEvaluator` protocol (stateless, pure functions)
  - [ ] Create `Registry.py` to wire evaluators and produce final scores

- [ ] **Individual evaluators**
  - [ ] `Popularity.py` — Softmax normalization, category-relative scoring
  - [ ] `Maintenance.py` — Update recency vs frequency logic
  - [ ] `Trust.py` — Official/verified/company/user tier scoring
  - [ ] `Security.py` — Vulnerability severity weighting (placeholder until Trivy)

- [ ] **Composite scoring**
  - [ ] Implement weighted score formula (0.25/0.35/0.25/0.15)
  - [ ] Support score recalculation with different weights

#### 5. Security Scanning

- [ ] **Trivy integration**
  - [ ] Subprocess wrapper for Trivy CLI
  - [ ] Parse JSON output into `Security` model
  - [ ] Lazy mode: scan on-demand or top-N tools
  - [ ] Cache scan results with 7-day TTL
  - [ ] Handle missing/unavailable Trivy gracefully

#### 6. CLI (`cli.py`)

- [ ] **Scrape commands**
  - [ ] `gts scrape --source docker_hub`
  - [ ] `--force-refresh` to bypass cache
  - [ ] Progress bar with rich

- [ ] **Query commands**
  - [ ] `gts search <query>` — Full-text search
  - [ ] `gts top --category <cat> --limit N`
  - [ ] `gts list --full` — All tools with scores

- [ ] **Export**
  - [ ] `gts export --format json --output <file>`

#### 7. Filtering & Ranking

- [ ] **Auto-exclusion logic**
  - [ ] Below `MIN_DOWNLOADS` threshold
  - [ ] Stale beyond `MAX_DAYS_SINCE_UPDATE`
  - [ ] Deprecated flag detection
  - [ ] Critical vulnerability filter (configurable)

- [ ] **Inclusion priority**
  - [ ] Prefer official images
  - [ ] Prefer verified publishers
  - [ ] Rank by quality score within category

#### 8. Testing & Validation

- [ ] Unit tests for scraper parsing logic
- [ ] Unit tests for each evaluator
- [ ] Integration tests with mocked Docker Hub responses
- [ ] E2E test: scrape → evaluate → store → query pipeline

#### MVP Checkpoint

Phase 1 is complete when you can run:
```bash
gts scrape --source docker_hub
gts top --category databases --limit 5
gts export --format json --output tools.json
```

And get scored, filtered results with security data for top tools.

---

### Future Phases

- **Phase 2:** GitHub scraper integration
- **Phase 3:** Helm Charts (Artifact Hub) scraper
- **Phase 4:** Tool disambiguation and canonical grouping
- **Phase 5:** Web UI

### Future Considerations

- **Re-scrape frequency:** Currently manual; future automation every 1-6 months
- **Web UI:** CLI-only for now; web interface may come later
- **Graph database:** FalkorDB support for relationship queries
