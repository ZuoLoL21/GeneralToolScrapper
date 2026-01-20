# GeneralToolScrapper - Development Guide

## Project Overview

A tool aggregation system that discovers, evaluates, and catalogs useful development tools from multiple sources.

## Architecture

```
Scrapers/
├── DockerHub.py        # Docker Hub API scraper
├── HelmCharts.py       # Artifact Hub scraper
├── Github.py           # GitHub API scraper
└── BaseScraper.py      # Abstract base class defining scraper contract

Evaluators/
├── Popularity.py       # Downloads, stars, usage normalization
├── Security.py         # Vulnerability scoring, Trivy results
├── Maintenance.py      # Update frequency, recency scoring
├── Trust.py            # Publisher verification, community reputation
└── Registry.py         # Wires evaluators together, produces final scores

Storage/
├── FileManager.py      # JSON/filesystem persistence
└── DatabaseManagers/
    └── FalkorDB.py     # Graph DB support (future)

cli.py                  # Typer-based CLI orchestration
Models.py               # Pydantic models (Tool, Metrics, etc.)
config.toml             # Runtime configuration
```
General architecture (if no .py, then it means a directory)

**Why atomic evaluators?** Each evaluator is a pure function that can be:
- Run independently for partial evaluations
- Tested in isolation
- Swapped or weighted differently per user preference

Scrapers should return a uniform model defined in Models

The evaluators should therefore be able to easily process each scraped tool

### Data Separation (Conceptual)

The system conceptually separates:
1. **Raw scraped fields** - Direct data from APIs (downloads, stars, dates, tags)
2. **Derived metrics** - Computed values (scores, normalized metrics, categories)
3. **User overlays** (future) - Custom scoring weights, manual category overrides

## Data Model

### Tool Schema

```python
{
    # ─────────────────────────────────────────────────────────────────────────
    # IDENTIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    "id": str,
    # Unique identifier for this specific artifact.
    # Format: "{source}:{namespace}/{name}" (e.g., "docker_hub:library/postgres")

    "identity": {
        "canonical_name": str,
        # The normalized tool name used to group related artifacts.
        # Example: "postgres" groups docker_hub:library/postgres, github:postgres/postgres, helm:bitnami/postgresql

        "aliases": list[str],
        # Alternative names users might search for.
        # Example: ["postgresql", "psql", "pg"]

        "variants": list[str],
        # IDs of other artifacts representing the same tool from different sources.
        # Example: ["docker_hub:bitnami/postgresql", "helm:bitnami/postgresql"]
    },

    "name": str,
    # Display name as it appears on the source (e.g., "postgres", "nginx")

    "source": str,
    # Origin platform. One of: "docker_hub" | "github" | "helm" | "web"

    "source_url": str,
    # Direct link to the tool on its source platform.
    # Example: "https://hub.docker.com/_/postgres"

    "description": str,
    # Short description from the source. May be empty or truncated.

    # ─────────────────────────────────────────────────────────────────────────
    # MAINTAINER INFO
    # ─────────────────────────────────────────────────────────────────────────
    "maintainer": {
        "name": str,
        # Publisher name or organization (e.g., "Docker Official Images", "bitnami")

        "type": str,
        # Publisher classification. One of: "official" | "company" | "user"
        # - "official": Platform-verified official image (e.g., Docker Official Images)
        # - "company": Organization account (e.g., bitnami, hashicorp)
        # - "user": Individual contributor account

        "verified": bool,
        # Whether the publisher has platform verification badge.
        # True for Docker Verified Publishers, GitHub Verified orgs, etc.
    },

    # ─────────────────────────────────────────────────────────────────────────
    # RAW METRICS (always persisted for recomputation)
    # ─────────────────────────────────────────────────────────────────────────
    "metrics": {
        "downloads": int,
        # Total download count. Meaning varies by source:
        # - Docker Hub: total pulls
        # - GitHub: release download count or clone count
        # - Helm: install count from Artifact Hub

        "stars": int,
        # Community appreciation metric:
        # - Docker Hub: star count
        # - GitHub: stargazer count
        # - Helm: stars on Artifact Hub

        "usage_amount": int,
        # Secondary usage indicator:
        # - Docker Hub: pull count (same as downloads)
        # - GitHub: fork count
        # - Helm: not applicable (set to 0)
    },

    # ─────────────────────────────────────────────────────────────────────────
    # SECURITY
    # ─────────────────────────────────────────────────────────────────────────
    "security": {
        "status": str,
        # Current security posture. One of: "ok" | "vulnerable" | "unknown"
        # - "ok": Scanned, no critical/high vulnerabilities
        # - "vulnerable": Has critical or high severity CVEs
        # - "unknown": Not yet scanned (treated as light penalty, not zero)

        "trivy_scan_date": datetime | None,
        # When the last Trivy scan was performed. None if never scanned.

        "vulnerabilities": {
            "critical": int,  # CVSS 9.0-10.0 - Immediate action required
            "high": int,      # CVSS 7.0-8.9  - Should be addressed soon
            "medium": int,    # CVSS 4.0-6.9  - Address in normal cycle
            "low": int,       # CVSS 0.1-3.9  - Informational
        },

        "is_safe": bool,
        # Computed flag: True if status="ok" or (status="unknown" AND no known CVEs)
    },

    # ─────────────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ─────────────────────────────────────────────────────────────────────────
    "maintenance": {
        "created_at": datetime,
        # When the artifact was first published on the source platform.

        "last_updated": datetime,
        # Most recent update timestamp (image push, release, commit).

        "update_frequency_days": int,
        # Average days between updates (computed from release history).
        # Used to contextualize staleness: a tool that updates yearly
        # being 2 months stale is fine; one that updates daily is concerning.

        "is_deprecated": bool,
        # Explicitly marked as deprecated by maintainer or platform.
    },

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORIZATION
    # ─────────────────────────────────────────────────────────────────────────
    "tags": list[str],
    # Raw tags from source (Docker labels, GitHub topics, Helm keywords).
    # Preserved for re-categorization and search.

    "taxonomy_version": str,
    # Version of the categorization taxonomy used (e.g., "v1.0").
    # Allows re-running categorization when taxonomy evolves.

    "primary_category": str,
    # Top-level functional category.
    # Examples: "databases", "monitoring", "ci-cd", "networking", "security"

    "primary_subcategory": str,
    # Specific function within the category.
    # Examples: "relational", "document", "metrics", "logging", "service-mesh"

    "secondary_categories": list[str],
    # Additional categories for multi-purpose tools.
    # Example: Loki might be ["monitoring/logging", "observability/tracing"]

    "lifecycle": str,
    # Project maturity stage. One of: "experimental" | "active" | "stable" | "legacy"
    # - "experimental": Early stage, API may change
    # - "active": Under active development
    # - "stable": Production-ready, mature
    # - "legacy": Maintained but superseded by newer alternatives

    # ─────────────────────────────────────────────────────────────────────────
    # DERIVED SCORES (recomputed from raw metrics)
    # ─────────────────────────────────────────────────────────────────────────
    "quality_score": float,
    # Weighted composite score from 0-100. Higher is better.
    # Computed as weighted sum of component scores (see algorithm below).

    "score_breakdown": {
        "popularity": float,   # 0-100, relative to category peers
        "security": float,     # 0-100, based on vulnerability severity
        "maintenance": float,  # 0-100, based on update recency and frequency
        "trust": float,        # 0-100, based on publisher verification and reputation
    },

    "scraped_at": datetime,
    # When this record was last fetched from the source API.
}
```

## Quality Scoring Algorithm

```
quality_score = (
    popularity_weight * popularity_score +
    security_weight * security_score +
    maintenance_weight * maintenance_score +
    trust_weight * trust_score
)

Where:
- popularity_score: Normalized downloads/stars relative to category average
    softmax with temperature modifier (reduce impact of popularity) rather than linear
    NOTE: Falls back to global normalization if category sample size < N (configurable)
- security_score: 100 - (critical*100 + high*10 + medium*1 + low*0.5), min 0
    NOTE: If status="unknown", apply light penalty (e.g., 70) rather than 0
- maintenance_score: Based on update frequency and last update recency
    last update within 2 weeks is fine, anything more will start losing points
    loss of points influenced by how often they update
        if they update every 6 months with a giant update -> a delay of 2 months is fine
        if they update every day -> a delay of 2 months is more important
- trust_score: official=100, verified_company=90, company=60, user=60
        company and user score can be increased if they are well established in the community
            eg high amount of total forks, stars, etc

IMPORTANT: Raw metrics are always persisted so scores can be recomputed later with different weights or algorithms.
```

### Suggested Weights (configurable)

| Weight | Value |
|--------|-------|
| popularity | 0.25 |
| security | 0.35 |
| maintenance | 0.25 |
| trust | 0.15 |

## API Requirements

### Docker Hub
- **Auth**: Optional (rate limits apply without)
- **Endpoint**: `https://hub.docker.com/v2/`
- **Rate Limit**: 100 pulls/6hr (anonymous), 200 pulls/6hr (authenticated)

### GitHub
- **Auth**: Personal Access Token recommended
- **Endpoint**: GitHub REST API v3 or GraphQL
- **Rate Limit**: 60 req/hr (anonymous), 5000 req/hr (authenticated)

### Helm Charts
- **Sources**: Artifact Hub API (`https://artifacthub.io/api/v1/`)
- **Auth**: Optional

## Environment Variables

```bash
# API Keys
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
DOCKER_HUB_USERNAME=your_username
DOCKER_HUB_TOKEN=your_token

# Storage
STORAGE_TYPE=sqlite          # sqlite | json | postgresql
DATABASE_URL=sqlite:///tools.db

# Scraping
SCRAPE_DELAY_MS=1000         # Delay between requests
MAX_CONCURRENT_REQUESTS=5

# Security Scanning
TRIVY_ENABLED=true
TRIVY_SEVERITY=CRITICAL,HIGH

# Thresholds
MIN_DOWNLOADS=1000           # Minimum downloads to consider
MIN_STARS=100                # Minimum stars to consider
MAX_DAYS_SINCE_UPDATE=365    # Max days since last update
```

### Security Scanning Strategy

Trivy scanning is resource-intensive. Options:
- `TRIVY_MODE=lazy` - Only scan on-demand or top-N per category
- `TRIVY_MODE=eager` - Scan all discovered tools (slower)

## Caching Strategy

API responses are cached aggressively to reduce rate limit impact and improve day-to-day usability.

```
Cache Structure:
- Location: Filesystem cache with configurable TTL
- Key: (source, endpoint, params) tuple
- TTL: Configurable per source (default 24h for metadata, 7d for security scans)
- Force refresh: --force-refresh flag bypasses cache
```

Benefits:
- Reduces API calls during development/testing
- Enables offline browsing of previously scraped data
- Allows incremental updates (only fetch changed data)

### Rate Limit Handling

- Exponential backoff on 429 responses
- Persist scrape queue to disk for recovery across restarts
- Track per-source rate limit state in config/state file

## Development Setup

```bash
# Clone and enter directory
cd GeneralToolScrapper

# Create virtual environment (Python 3.13+)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Run tests
pytest

# Run linting
ruff check .
ruff format .
```

## Suggested Dependencies

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

## CLI Usage (Planned)

```bash
# Scrape all sources
gts scrape --all

# Scrape specific source
gts scrape --source docker_hub

# Search tools
gts search "postgres" --category databases

# List top tools by category
gts top --category monitoring --limit 10

# Get basis (one tool per subcategory)
gts basis --output basis.json

# Get basis for specific category
gts basis --category databases

# Get full list with all alternatives
gts list --full --category databases

# Compare tools in same subcategory
gts compare postgres mysql

# Export results
gts export --format json --output tools.json

# Run security scan on specific tool
gts scan --tool nginx
```

## Filtering Logic

### Exclusion Criteria (auto-filtered)
- Downloads < MIN_DOWNLOADS threshold
- No updates in > MAX_DAYS_SINCE_UPDATE
- Marked as deprecated
- Critical security vulnerabilities (configurable)

### Inclusion Priority
1. Official images/repos
2. Verified publishers
3. Company-maintained with high activity
4. User-maintained with exceptional metrics

## Testing Strategy

- **Unit tests**: Individual scraper parsing, scoring algorithms
- **Integration tests**: API calls with mocked responses
- **E2E tests**: Full scrape-evaluate-store pipeline

## Phase 1 Milestones (Docker Hub)

- [ ] Basic Docker Hub API client
- [ ] Search and pagination handling
- [ ] Rate limiting implementation
- [ ] Data model and storage (JSON initially)
- [ ] Basic CLI for scraping
- [ ] Trivy integration for security scanning
- [ ] Quality score calculation
- [ ] Filtering and ranking

## Open Questions

1. Should we cache API responses locally to reduce rate limit impact?
   1. Yes

2. How often should we re-scrape and update tool information?
   1. Currently, is just a tool, later on every 1-6 months

3. Should we support user-defined categories or use a fixed taxonomy?
   1. I prefer if we could auto-generate the basis

4. Do we want a web UI eventually, or CLI-only?
   1. Currently CLI

### Tool Disambiguation Strategy

Multiple images/repos may exist for the same tool (e.g., `nginx`, `postgres`). Resolution:
1. Prefer official images (verified publisher)
2. Group by canonical tool name, track all publishers
3. Store `canonical_name` field linking variants to the same underlying tool


## Tool Basis Strategy

Store all quality tools but group them by function - don't pick winners arbitrarily.

### Why Not Pick One Winner Per Category

- Tools like Postgres vs MySQL have real trade-offs (JSONB support, licensing, ecosystem, hosting)
- "Best" depends on user context (existing stack, team experience, cost constraints)
- Picking one loses valuable alternatives

### Functional Grouping Structure

```
databases/
├── relational/
│   ├── postgres (score: 92)
│   ├── mysql (score: 88)
│   └── mariadb (score: 85)
├── document/
│   ├── mongodb (score: 90)
│   └── couchdb (score: 78)
└── key-value/
    ├── redis (score: 95)
    └── memcached (score: 82)

monitoring/
├── metrics/
│   ├── prometheus (score: 94)
│   └── influxdb (score: 86)
├── visualization/
│   ├── grafana (score: 96)
│   └── kibana (score: 88)
└── logging/
    ├── elasticsearch (score: 90)
    └── loki (score: 85)
```

### Output Modes

1. **Basis Mode** (`--basis`) - One top-scoring tool per functional subcategory
   - Quick recommendations for starting a new project
   - Minimal decision fatigue

2. **Full Mode** (`--full`) - All qualified tools with scores
   - For users comparing alternatives
   - Shows trade-offs between similar tools

### Auto-Categorization

Categories are auto-generated using:
1. Tags from Docker Hub / GitHub topics
2. Keyword matching in descriptions
3. Known tool mappings (curated list of common tools)

Tools are grouped into functional subcategories based on what problem they solve, not their implementation details.

Fallback strategy when tags are missing/unreliable:
- Curated seed list mapping known tools to categories
- Keyword extraction from description
- Manual override file (user-defined mappings)