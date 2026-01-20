# GeneralToolScrapper - Development Guide

## Project Overview

A tool aggregation system that discovers, evaluates, and catalogs useful development tools from multiple sources.

## Architecture

```
Scrapers (source-specific scrapers)
- DockerHub
- HelmCharts
- Github
- BaseScraper.py (abstract base scraper)

Evaluators
- Popularity
- Security
- Maintenace
- Trust
- Evaluator.py (an evaluator strings the four evaluators together)

Storage
- FileManager.py
- DatabaseManagers
    - FalkorDB.py (problems for later)

cli.py
Models.py
config.toml
```
General architecture (if no .py, then it means a directory)

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
    "id": str,                    # Unique identifier
    "name": str,
    "source": str,                # "docker_hub" | "github" | "helm" | "web"
    "source_url": str,
    "description": str,
    "maintainer": {
        "name": str,
        "type": str,              # "official" | "company" | "user"
        "verified": bool
    },
    "metrics": {
        "downloads": int,
        "stars": int,             # Hearts/Stars/etc
        "usage_amount": int,      # Pull/Forks/Views/etc
    },
    "security": {
        "status": str,            # "ok" | "vulnerable" | "unknown"
        "trivy_scan_date": datetime | None,
        "vulnerabilities": {
            "critical": int,
            "high": int,
            "medium": int,
            "low": int
        },
        "is_safe": bool
    },
    "maintenance": {
        "created_at": datetime,
        "last_updated": datetime,
        "update_frequency_days": int,
        "is_deprecated": bool
    },
    "tags": list[str],
    "primary_category": str,          # e.g., "databases", "monitoring", "ci-cd"
    "primary_subcategory": str,       # e.g., "relational", "metrics", "logging"
    "secondary_categories": list[str], # For tools spanning multiple domains
    "lifecycle": str,                 # "active" | "stable" | "legacy" | "experimental"
    "quality_score": float,           # Computed score 0-100
    "score_breakdown": {
        "popularity": float,
        "security": float,
        "maintenance": float,
        "trust": float
    },
    "scraped_at": datetime
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