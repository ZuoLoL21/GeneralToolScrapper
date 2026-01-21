# Configuration

This document describes all configuration options for GeneralToolScraper.

## Operating Modes

The system supports two operating modes:

| Mode | Environment Variable | Features |
|------|---------------------|----------|
| **MVP** | `GTS_MODE=mvp` (default) | Docker Hub only, popularity + maintenance scoring, manual categorization fallback |
| **Full** | `GTS_MODE=full` | All sources, LLM categorization, Trivy security scanning, full scoring pipeline |

Start with MVP mode to validate data quality and UX before enabling advanced features.

## Environment Variables

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

### Core Settings

```bash
# Operating mode
GTS_MODE=mvp                          # mvp | full

# Storage
STORAGE_TYPE=json                     # json | sqlite | postgresql (future)
DATA_DIR=data                         # Base directory for all data
```

### API Keys

```bash
# GitHub (recommended for higher rate limits)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Docker Hub (optional, improves rate limits)
DOCKER_HUB_USERNAME=your_username
DOCKER_HUB_TOKEN=your_token
```

### Scraping Behavior

```bash
# Docker Hub namespaces
DOCKER_HUB_NAMESPACES=default         # Presets: default, popular, all
                                      # Default: Official images only (~177 tools)
                                      # Popular: 9 curated verified namespaces
                                      # All: 70+ well-known namespaces
                                      # Or use custom comma-separated list

# Rate limiting
SCRAPE_DELAY_MS=1000                  # Delay between requests (ms)
MAX_CONCURRENT_REQUESTS=5             # Parallel requests per source

# Retry behavior
MAX_RETRIES=3                         # Retries on transient failures
RETRY_BACKOFF_BASE=2                  # Exponential backoff base (seconds)
RETRY_BACKOFF_MAX=60                  # Maximum backoff (seconds)
```

**Docker Hub Namespace Options:**

- **`default`** (or `library`): Official Docker images only (~177 tools). Best for quick start and testing.
- **`popular`**: Curated list of 9 verified namespaces (library, bitnami, ubuntu, alpine, mysql, postgres, nginx, redis, mongo). Recommended for production use.
- **`all`**: Comprehensive list of 70+ well-known namespaces across all categories (official publishers, databases, web servers, programming languages, DevOps tools, monitoring, messaging, security, CMS, and more). Best for comprehensive scraping and research.
- **Custom list**: Comma-separated namespaces like `library,bitnami,nginx`. Use for targeted scraping.

For a complete list of all available namespaces in the `all` preset, see the main README.md or `src/consts.py`.

### Filtering Thresholds

```bash
# Pre-filter thresholds (removes before stats computation)
MIN_DOWNLOADS=1000                    # Minimum downloads to consider
MIN_STARS=100                         # Minimum stars to consider
MAX_DAYS_SINCE_UPDATE=365             # Max days since last update

# Post-filter thresholds (removes after scoring)
MIN_SCORE=30                          # Minimum quality score to include
```

### Scoring Weights

```bash
# Default weights (must sum to 1.0)
WEIGHT_POPULARITY=0.25
WEIGHT_SECURITY=0.35
WEIGHT_MAINTENANCE=0.25
WEIGHT_TRUST=0.15

# Optional: time-decay for popularity
POPULARITY_DECAY_HALFLIFE=0           # 0 = disabled, >0 = half-life in days
```

### Security Scanning

```bash
# Trivy integration (Full mode only)
TRIVY_ENABLED=true                    # Enable/disable security scanning
TRIVY_SEVERITY=CRITICAL,HIGH          # Severity levels to report
TRIVY_MODE=lazy                       # lazy: on-demand | eager: scan all
TRIVY_TIMEOUT=300                     # Scan timeout (seconds)
```

### LLM Classification

```bash
# Ollama settings (Full mode only)
OLLAMA_MODEL=llama3                   # Model for classification
OLLAMA_HOST=http://localhost:11434    # Ollama endpoint
OLLAMA_TIMEOUT=30                     # Request timeout (seconds)

# Classification behavior
MIN_CONFIDENCE_THRESHOLD=0.7          # Reject below this confidence
CATEGORY_CACHE_PATH=data/cache/categories.json
CATEGORY_OVERRIDES_PATH=data/overrides.json
```

### Caching

```bash
# Cache TTLs (seconds)
CACHE_TTL_METADATA=86400              # 24 hours for API metadata
CACHE_TTL_SECURITY=604800             # 7 days for security scans
CACHE_TTL_CLASSIFICATION=0            # 0 = permanent (until prompt/taxonomy changes)

# Cache location
CACHE_DIR=data/cache
```

## Profiles

Profiles provide named configuration overlays for common use cases. They simplify CLI usage by bundling related settings.

### Defining Profiles

Profiles are defined in `config/profiles.yaml`:

```yaml
profiles:
  # Production/enterprise focus: security-first, stable tools only
  production:
    weights:
      popularity: 0.20
      security: 0.45
      maintenance: 0.25
      trust: 0.10
    filters:
      allow_experimental: false
      allow_legacy: false
      min_score: 50

  # Security-first: maximum security weight
  security-first:
    weights:
      popularity: 0.15
      security: 0.55
      maintenance: 0.20
      trust: 0.10
    filters:
      require_scanned: true
      max_critical_vulns: 0
      max_high_vulns: 2

  # Startup/greenfield: prefer newer tools, accept experimental
  startup:
    weights:
      popularity: 0.30
      security: 0.30
      maintenance: 0.25
      trust: 0.15
    filters:
      allow_experimental: true
      popularity_decay_halflife: 730
    flags:
      modern: true

  # Research: include everything, no filtering
  research:
    weights:
      popularity: 0.25
      security: 0.35
      maintenance: 0.25
      trust: 0.15
    filters:
      min_score: 0
      include_hidden: true
      include_needs_review: true

  # Balanced: default settings (explicit)
  balanced:
    weights:
      popularity: 0.25
      security: 0.35
      maintenance: 0.25
      trust: 0.15
    filters:
      allow_experimental: true
      allow_legacy: true
```

### Using Profiles

```bash
# Use a profile
gts top --profile production
gts basis --profile security-first
gts search "database" --profile startup

# Override profile settings with flags
gts top --profile production --include-hidden

# Show profile settings
gts config --profile production
```

### Profile Precedence

Settings are resolved in order (later overrides earlier):

1. Default values (hardcoded)
2. Environment variables
3. Profile settings
4. CLI flags

## Caching Details

### Cache Structure

```
data/cache/
├── api/                      # API response cache
│   ├── docker_hub/
│   │   └── {hash}.json       # Keyed by (endpoint, params) hash
│   ├── github/
│   └── helm/
├── security/                 # Trivy scan results
│   └── {image_hash}.json     # Keyed by image digest
├── classification/           # LLM classification cache
│   └── categories.json       # Keyed by canonical_name
└── llm/                      # Raw LLM responses (debug only)
    └── {canonical_name}.json
```

### Cache Behavior

| Cache Type | Default TTL | Key | Invalidation |
|------------|-------------|-----|--------------|
| API metadata | 24h | `(source, endpoint, params)` hash | TTL expiry, `--force-refresh` |
| Security scans | 7d | Image digest | TTL expiry, `--force-refresh` |
| Classifications | Permanent | `canonical_name` | Prompt/taxonomy/model change |
| LLM raw responses | Permanent | `canonical_name` | Manual deletion |

### Cache Bypass

```bash
# Bypass all caches for a single run
gts scrape --force-refresh

# Clear specific cache types
gts cache clear --type api
gts cache clear --type security
gts cache clear --type classification
gts cache clear --all

# Show cache statistics
gts cache stats
```

## Rate Limit Handling

### Per-Source Limits

| Source | Anonymous | Authenticated |
|--------|-----------|---------------|
| Docker Hub | 100 pulls/6hr | 200 pulls/6hr |
| GitHub | 60 req/hr | 5000 req/hr |
| Artifact Hub | 100 req/hr | 100 req/hr |

### Backoff Strategy

On 429 (rate limited) responses:

1. Initial wait: 1 second
2. Exponential backoff: `min(base^attempt, max_backoff)`
3. Jitter: ±20% randomization to prevent thundering herd
4. Max attempts: 5 before failing

```python
wait_time = min(RETRY_BACKOFF_BASE ** attempt, RETRY_BACKOFF_MAX)
wait_time *= random.uniform(0.8, 1.2)  # jitter
```

### Queue Persistence

The scrape queue is persisted to disk for recovery:

```
data/cache/scrape_queue.json
```

On restart, scraping resumes from the last successful item.

## Overrides File

Manual overrides are stored in `data/overrides.json`:

```json
{
  "docker_hub:someuser/postgres-api": {
    "primary_category": "web",
    "primary_subcategory": "server",
    "secondary_categories": ["databases/relational"],
    "reason": "REST API wrapper for PostgreSQL, not PostgreSQL itself",
    "canonical_name": "postgres-rest-api"
  },
  "docker_hub:library/alpine": {
    "lifecycle": "stable",
    "reason": "Intentionally minimal update frequency"
  }
}
```

### Override Fields

| Field | Description |
|-------|-------------|
| `primary_category` | Override category |
| `primary_subcategory` | Override subcategory |
| `secondary_categories` | Override secondary categories |
| `canonical_name` | Override canonical grouping |
| `lifecycle` | Override lifecycle inference |
| `reason` | **Required** explanation for the override |

Overrides always take precedence and have confidence 1.0.

## Feature Gates (MVP vs Full)

Feature availability by mode:

| Feature | MVP | Full |
|---------|-----|------|
| Docker Hub scraping | Yes | Yes |
| GitHub scraping | No | Yes |
| Helm Charts scraping | No | Yes |
| Popularity scoring | Yes | Yes |
| Maintenance scoring | Yes | Yes |
| Security scoring | Placeholder (70) | Trivy-based |
| Trust scoring | Basic | Full |
| LLM categorization | No (fallback) | Yes |
| Lifecycle inference | Basic | Full |
| Profiles | Yes | Yes |
| Canonical grouping | Simple | Full resolver |

### Enabling Full Mode

```bash
# In .env
GTS_MODE=full

# Or per-command
GTS_MODE=full gts scrape --all
```

### Checking Mode

```bash
gts config --show-mode
# Output: Operating mode: mvp
#         LLM: disabled
#         Trivy: disabled
```

## Complete .env.example

```bash
# =============================================================================
# GeneralToolScraper Configuration
# =============================================================================

# Operating Mode
# mvp: Docker Hub only, no LLM/Trivy dependencies
# full: All features enabled
GTS_MODE=mvp

# -----------------------------------------------------------------------------
# API Keys
# -----------------------------------------------------------------------------

# GitHub Personal Access Token (recommended)
# Create at: https://github.com/settings/tokens
# Required scopes: public_repo (read-only)
GITHUB_TOKEN=

# Docker Hub credentials (optional, improves rate limits)
DOCKER_HUB_USERNAME=
DOCKER_HUB_TOKEN=

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------

STORAGE_TYPE=json
DATA_DIR=data

# -----------------------------------------------------------------------------
# Scraping
# -----------------------------------------------------------------------------

SCRAPE_DELAY_MS=1000
MAX_CONCURRENT_REQUESTS=5
MAX_RETRIES=3
RETRY_BACKOFF_BASE=2
RETRY_BACKOFF_MAX=60

# -----------------------------------------------------------------------------
# Filtering
# -----------------------------------------------------------------------------

MIN_DOWNLOADS=1000
MIN_STARS=100
MAX_DAYS_SINCE_UPDATE=365
MIN_SCORE=30

# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------

WEIGHT_POPULARITY=0.25
WEIGHT_SECURITY=0.35
WEIGHT_MAINTENANCE=0.25
WEIGHT_TRUST=0.15

# Optional: time-decay for popularity (0 = disabled)
POPULARITY_DECAY_HALFLIFE=0

# -----------------------------------------------------------------------------
# Security (Full mode only)
# -----------------------------------------------------------------------------

TRIVY_ENABLED=true
TRIVY_SEVERITY=CRITICAL,HIGH
TRIVY_MODE=lazy
TRIVY_TIMEOUT=300

# -----------------------------------------------------------------------------
# LLM Classification (Full mode only)
# -----------------------------------------------------------------------------

OLLAMA_MODEL=llama3
OLLAMA_HOST=http://localhost:11434
OLLAMA_TIMEOUT=30
MIN_CONFIDENCE_THRESHOLD=0.7

# -----------------------------------------------------------------------------
# Caching
# -----------------------------------------------------------------------------

CACHE_DIR=data/cache
CACHE_TTL_METADATA=86400
CACHE_TTL_SECURITY=604800
CACHE_TTL_CLASSIFICATION=0
```
