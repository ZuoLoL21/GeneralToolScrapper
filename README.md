# GeneralToolScraper

A tool aggregation system that discovers, evaluates, and catalogs useful development tools from multiple sources (Docker Hub, GitHub, Helm Charts).

## Primary Purpose

**GeneralToolScraper is a recommendation engine for infrastructure tooling.** It helps teams answer "what's the best tool for X?" by aggregating data from multiple sources, scoring tools on quality dimensions, and presenting context-aware recommendations.

While the data can serve research, compliance, or productivity use cases, the primary design goal is actionable recommendations with transparent scoring.

## Quick Start

```bash
# Clone and setup
cd GeneralToolScraper
uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Run (MVP mode - no LLM/Trivy required)
gts --help
```

## Docker Hub Namespace Configuration

By default, the scraper only processes official Docker Hub images (`library` namespace, ~177 images). You can configure which namespaces to scrape using three methods:

### 1. Default Behavior (Official Images Only)
```bash
# Scrapes only official Docker images (~177 tools)
gts scrape --source docker_hub
```

### 2. Environment Variable
Add to your `.env` file:
```bash
# Use the default preset (official images only)
DOCKER_HUB_NAMESPACES=default

# Use the popular preset (9 curated namespaces: library, bitnami, ubuntu, etc.)
DOCKER_HUB_NAMESPACES=popular

# Use the all preset (70+ well-known namespaces across all categories)
DOCKER_HUB_NAMESPACES=all

# Or specify custom comma-separated namespaces
DOCKER_HUB_NAMESPACES=library,bitnami,nginx,postgres
```

### 3. CLI Option (Overrides Environment)
```bash
# Use a preset (default, popular, or all)
gts scrape --source docker_hub --namespaces default
gts scrape --source docker_hub --namespaces popular
gts scrape --source docker_hub --namespaces all

# Or specify custom comma-separated namespaces
gts scrape --source docker_hub --namespaces "library,bitnami,ubuntu"
```

### Available Presets

- **`default`** (or `library`): Official Docker images only (~177 tools)
- **`popular`**: Curated list of 9 verified namespaces (library, bitnami, ubuntu, alpine, mysql, postgres, nginx, redis, mongo)
- **`all`**: Comprehensive list of 70+ well-known Docker Hub namespaces across all categories

### Available Namespaces by Category

The scraper supports any Docker Hub namespace. Below are the well-known namespaces included in the `all` preset:

#### Official and Verified Publishers
- **library** - Official Docker images (~177 images)
- **bitnami** - Bitnami verified publisher
- **ubuntu** - Ubuntu official
- **alpine** - Alpine Linux official
- **amazonlinux** - Amazon Linux official
- **fedora** - Fedora official
- **centos** - CentOS official
- **debian** - Debian official
- **oraclelinux** - Oracle Linux official

#### Databases
- **mysql** - MySQL official
- **postgres** - PostgreSQL official
- **mongo** - MongoDB official
- **redis** - Redis official
- **mariadb** - MariaDB official
- **elasticsearch** - Elasticsearch official
- **cassandra** - Apache Cassandra official
- **couchbase** - Couchbase official
- **influxdb** - InfluxDB official
- **neo4j** - Neo4j official

#### Web Servers and Proxies
- **nginx** - NGINX official
- **httpd** - Apache HTTP Server official
- **traefik** - Traefik official
- **haproxy** - HAProxy official
- **caddy** - Caddy official

#### Programming Languages
- **node** - Node.js official
- **python** - Python official
- **golang** - Go official
- **openjdk** - OpenJDK official
- **ruby** - Ruby official
- **php** - PHP official
- **rust** - Rust official
- **dotnet** - .NET official

#### DevOps and CI/CD
- **jenkins** - Jenkins official
- **gitlab** - GitLab official
- **sonarqube** - SonarQube official
- **nexus3** - Sonatype Nexus official

#### Monitoring and Observability
- **grafana** - Grafana official
- **prometheus** - Prometheus official
- **kibana** - Kibana official
- **logstash** - Logstash official
- **telegraf** - Telegraf official
- **fluentd** - Fluentd official

#### Message Queues and Streaming
- **rabbitmq** - RabbitMQ official
- **kafka** - Apache Kafka official
- **nats** - NATS official
- **memcached** - Memcached official

#### Security and Secrets Management
- **vault** - HashiCorp Vault official
- **consul** - HashiCorp Consul official

#### Content Management and Applications
- **wordpress** - WordPress official
- **ghost** - Ghost official
- **drupal** - Drupal official
- **joomla** - Joomla official
- **nextcloud** - Nextcloud official

#### Other Popular Namespaces
- **portainer** - Portainer
- **rancher** - Rancher
- **docker** - Docker official tools
- **circleci** - CircleCI

See `src/consts.py` for the complete list.

### Examples

```bash
# Quick test with official images only
gts scrape --source docker_hub --limit 50

# Use popular preset (9 verified namespaces)
gts scrape --source docker_hub --namespaces popular

# Use all preset (70+ well-known namespaces) - comprehensive scrape
gts scrape --source docker_hub --namespaces all

# Production scrape with popular namespaces via environment variable
export DOCKER_HUB_NAMESPACES=popular
gts scrape --source docker_hub

# Custom namespace selection
gts scrape --source docker_hub --namespaces "library,bitnami" --limit 500

# Override environment variable for a single run
DOCKER_HUB_NAMESPACES=popular gts scrape --source docker_hub --namespaces "library"

# Scrape specific categories
gts scrape --source docker_hub --namespaces "mysql,postgres,mongo,redis"  # Databases only
gts scrape --source docker_hub --namespaces "nginx,traefik,haproxy,caddy"  # Web servers only
```

### Data Persistence & Incremental Scraping

**The scraper automatically merges new data with existing tools instead of overwriting them.** This means:

- **First run**: Scrapes tools and stores them in `data/processed/tools.json`
- **Subsequent runs**:
  - Loads existing tools from storage
  - Scrapes new tools (or re-scrapes with updated data)
  - Merges based on tool ID (updates existing, adds new)
  - Preserves previously scraped tools that aren't in the current run

**Output includes two summary tables:**

1. **All Tools**: Complete dataset including previously scraped tools
2. **Newly Scraped Tools**: Only tools added or updated in the current run

**Example workflow:**

```bash
# First scrape: library namespace (177 tools)
gts scrape --source docker_hub --namespaces "library"
# Output: Total tools: 177 (177 new)

# Second scrape: bitnami namespace (different tools)
gts scrape --source docker_hub --namespaces "bitnami"
# Output: Total tools: 500 (323 new)
# Shows two tables: all 500 tools + the 323 newly added

# Re-scrape library to update existing data
gts scrape --source docker_hub --namespaces "library"
# Output: Total tools: 500 (0 new)
# Updates the 177 library tools with fresh data, preserves 323 bitnami tools
```

This design enables:
- **Incremental discovery**: Build your catalog across multiple scraping sessions
- **Data safety**: Previously scraped tools are never lost
- **Update flexibility**: Re-scrape specific namespaces to refresh data without losing others
- **Clear visibility**: See both your complete dataset and what changed in each run

## Security Scanning with Trivy

After scraping tools, you can scan Docker Hub images for vulnerabilities using Trivy:

```bash
# Scan tools with unknown or stale security status
gts scan

# Preview what would be scanned (dry run)
gts scan --dry-run

# Scan specific number of tools
gts scan --limit 50

# Force re-scan all Docker Hub tools (ignore staleness)
gts scan --force

# Customize scanning behavior
gts scan --concurrency 5 --timeout 600 --tag alpine
```

### How Security Scanning Works

- **Lazy scanning**: Only scans tools with `status=UNKNOWN` or scans older than 7 days
- **Scan strategy**: Tries remote scan first (fast), falls back to local pull if needed
- **Error handling**: Keeps `UNKNOWN` status on failure, logs warnings, caches failures (1 hour)
- **Non-destructive**: Failed scans don't overwrite existing security data
- **Progress tracking**: Real-time progress bar with vulnerability summary
- **Concurrency control**: Default concurrency is 1 to avoid Trivy cache lock conflicts
  - Higher concurrency (2-5) may cause "cache may be in use" errors
  - Use `--concurrency 1` if you encounter cache lock timeouts
  - Future versions may support per-process cache isolation

### Requirements

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

### Example Workflow

```bash
# 1. Scrape tools
gts scrape --source docker_hub --namespaces popular

# 2. Scan for vulnerabilities
gts scan

# 3. View top-rated tools (security affects quality score)
gts top --limit 20
```

## Operating Modes

The system supports two modes to balance simplicity with full functionality:

| Mode | Features | Dependencies |
|------|----------|--------------|
| **MVP** (`GTS_MODE=mvp`) | Docker Hub scraping, popularity + maintenance scoring, manual categorization fallback, basic CLI | Python, httpx |
| **Full** (`GTS_MODE=full`) | All sources, LLM categorization, Trivy security scanning, full scoring pipeline, profiles | + Ollama, Trivy |

MVP mode is the default. Start here to validate data quality and UX before enabling advanced features.

## Core Concepts

### Tool Disambiguation

Multiple artifacts may represent the same underlying tool (e.g., `docker_hub:library/postgres`, `helm:bitnami/postgresql`, `github:postgres/postgres`). The system assigns each artifact a unique ID and groups related artifacts under a `canonical_name`.

### Categorization Taxonomy

The system uses a comprehensive two-layer taxonomy for organizing and enriching tools:

#### Tool Categories (v1.0)
15 primary categories with 70 subcategories covering the complete infrastructure tooling landscape:

| Category | Subcategories | Coverage |
|----------|--------------|----------|
| **databases** | relational, document, key-value, graph, time-series, search, admin, migration, nosql | Data storage and retrieval systems |
| **monitoring** | metrics, logging, tracing, visualization, alerting, analytics | Observability and monitoring tools |
| **web** | server, proxy, load-balancer, application-server, cache, utilities | Web servers, proxies, and load balancers |
| **messaging** | queue, streaming, pubsub | Message queues and event streaming |
| **ci-cd** | build, deploy, registry | Continuous integration and deployment |
| **security** | secrets, auth, scanning | Security and access control |
| **storage** | object, file, backup | Data storage systems |
| **networking** | dns, vpn, service-mesh, api-gateway | Network infrastructure |
| **runtime** | container, serverless, orchestration | Container and orchestration runtimes |
| **development** | ide, testing, debugging, cli, sdk, build-tools, quality | Development tools and environments |
| **base-images** | linux, minimal | Base operating system images |
| **languages** | compiled, interpreted, functional, jvm, scientific, alternative | Programming language runtimes |
| **content** | cms, wiki, blog, collaboration, community | Content management platforms |
| **business** | erp, bpm, crm, project, document, integration, gis | Business and enterprise applications |
| **communication** | chat, voice, email | Communication and collaboration tools |

#### Keyword Taxonomy (v2.0)
15 keyword categories with 173 unique keywords for property-based classification:

| Category | Keywords | Purpose |
|----------|----------|---------|
| **platform** | 16 keywords | Deployment targets (cloud-native, jvm, cms-platform, self-hosted, etc.) |
| **architecture** | 10 keywords | System design patterns (distributed, microservices, event-driven, etc.) |
| **protocol** | 12 keywords | Communication protocols (rest-api, grpc, websocket, mqtt, etc.) |
| **optimization** | 8 keywords | Performance characteristics (lightweight, memory-efficient, high-performance) |
| **data** | 10 keywords | Data handling (structured, real-time, streaming, geospatial, etc.) |
| **persistence** | 9 keywords | Storage characteristics (persistent, in-memory, replicated, cached, etc.) |
| **deployment** | 8 keywords | Deployment models (containerized, kubernetes-native, stateless, etc.) |
| **security** | 10 keywords | Security features (encrypted, mtls, rbac, sso, compliance, etc.) |
| **integration** | 14 keywords | Integration capabilities (plugin-system, webhook, etl, workflow-engine, etc.) |
| **ecosystem** | 16 keywords | Technology ecosystems (java-ecosystem, php-ecosystem, wordpress-ecosystem, etc.) |
| **governance** | 8 keywords | Project governance (open-source, commercial, community-driven, etc.) |
| **maturity** | 9 keywords | Project maturity (production-ready, battle-tested, stable, etc.) |
| **application-type** | 18 keywords | Application categories (cms, blog, wiki, erp, crm, etc.) |
| **use-case** | 16 keywords | Common use cases (content-publishing, team-collaboration, api-management, etc.) |
| **license-type** | 8 keywords | License classifications (mit, apache-2, gpl, proprietary, etc.) |

**How it works:**
- **Automatic enrichment**: Tools are assigned category-based keywords and property keywords
- **Cached for performance**: All assignments are cached to minimize redundant processing
- **Search integration**: Keywords enhance search relevance and enable tag-based filtering
- **Validation**: Run `python -m src.categorization.human_maintained` or `python -m src.categorization.keyword_taxonomy` to view and validate

Example: `postgres` receives:
- Primary category: `databases/relational`
- Keywords: `database`, `sql`, `relational`, `acid`, `transactional`, `persistent`, `production-ready`

### Quality Scoring

Tools are scored on four dimensions with configurable weights:

| Dimension | Default Weight | What It Measures |
|-----------|----------------|------------------|
| Security | 0.35 | Vulnerability severity from Trivy scans |
| Popularity | 0.25 | Downloads/stars normalized within category |
| Maintenance | 0.25 | Update recency relative to update frequency |
| Trust | 0.15 | Publisher verification and community reputation |

Scores are **relative within categories**, not absolute. A score of 90 means "top ~10% within its category."

### Output Modes

- **Basis Mode** (`--basis`): One top-scoring tool per subcategory for quick recommendations
- **Full Mode** (`--full`): All qualified tools with scores for comparing alternatives

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, pipeline, code structure |
| [Scoring](docs/SCORING.md) | Scoring algorithms, normalization, interpretation |
| [Categorization](docs/CATEGORIZATION.md) | LLM classification, taxonomy, identity resolution |
| [Data Model](docs/DATA_MODEL.md) | All Pydantic models with design rationale |
| [Configuration](docs/CONFIGURATION.md) | Environment variables, profiles, caching |
| [CLI Reference](docs/CLI.md) | Commands and usage examples |
| [Design Decisions](docs/DECISIONS.md) | Trade-offs and rationale |
| [Contributing](CONTRIBUTING.md) | How to contribute, governance |

## Roadmap

### Phase 1: Docker Hub MVP (Complete)

- [x] Project scaffolding and data models
- [x] Docker Hub scraper with resilience
- [x] Multiple namespace support (env var + CLI configuration)
- [x] Categorization with keyword taxonomy
- [x] Keyword assignment system
- [x] File-based storage layer
- [x] Incremental scraping with automatic data merging
- [x] Centralized caching
- [x] Popularity and maintenance evaluators
- [x] Pre/post filtering logic
- [x] Basic CLI (scrape, search, top, export)
- [x] Trivy security scanner with lazy scanning (scan command)
- [x] Comprehensive test suite
- [x] Taxonomy extension (15 categories, 70 subcategories, 173 keywords)
- [x] Graceful handling of empty tool sets

### Future Phases

- **Phase 2:** GitHub scraper integration
- **Phase 3:** Helm Charts (Artifact Hub) scraper
- **Phase 4:** Tool disambiguation and canonical grouping
- **Phase 5:** Web UI

## Changelog

### 2026-01-21: Enhanced Trivy Scanning with Smart Tag Selection and Incremental Saving

Major improvements to Trivy security scanning with smart Docker tag selection, scanned tag tracking, and crash-resilient incremental saving.

**New Features:**

**1. Smart Tag Selection from Pre-Fetched Docker Tags**
- **Tag Fetching During Scraping**: Docker Hub scraper now fetches available image tags during the scraping phase
  - New `_fetch_available_tags()` method queries Docker Hub tags API
  - Tags stored in `tool.docker_tags` field for later use during scanning
  - Cached using existing response cache (24h TTL)
  - Limits to first 50 tags per image to keep responses manageable

- **Priority-Based Tag Selection**: Scanner intelligently selects best available tag
  - Priority order: `stable` → `latest` → `alpine` → first available
  - Falls back to configured default tag if no tags available (backward compatible)
  - NO API calls during scanning - uses pre-fetched tags from scraping phase
  - Handles images without `latest` tag (e.g., versioned tags like `16-alpine`, `1.0.5`)

- **Scanned Tag Tracking**: Results now record which tag was scanned
  - New `scanned_tag` field in `Security` model tracks the Docker tag scanned
  - Stored alongside vulnerability counts and scan date
  - Enables reproducibility and version-specific vulnerability tracking

**2. Incremental Saving for Crash Resilience**
- **Save After Each Scan**: Results are saved immediately after each successful scan
  - Uses `FileManager.save_processed(merge=True)` for safe concurrent updates
  - If process crashes, already-completed scans are preserved
  - Progress is never lost - can resume from where it left off
  - Minimal performance impact (~10-20% slower due to incremental I/O)

- **Crash Recovery**: Scanning can be interrupted safely
  - Completed scans are already saved to `data/processed/tools.json`
  - Failed scans cached for 1 hour to prevent retry loops
  - Resume by running `gts scan` again - skips already-scanned tools

**3. Updated CLI Behavior**
- **Dry Run Mode**: `gts scan --dry-run` now shows selected Docker tag for each tool
- **Tag Override**: `--tag` flag now serves as fallback when no tags available
- **Final Save**: Kept for backward compatibility - acts as final flush

**Data Model Changes:**
- `Tool.docker_tags: list[str]` - Available Docker image tags from Docker Hub
- `Security.scanned_tag: str | None` - Docker image tag that was scanned
- `ScanResult.scanned_tag: str | None` - Tag information in scan results

**Modified Modules:**
- `src/models/model_tool.py`: Added `docker_tags` and `scanned_tag` fields
- `src/models/model_scanner.py`: Added `scanned_tag` to `ScanResult`
- `src/scrapers/docker_hub/docker_hub.py`: Tag fetching during scraping
- `src/scanner/image_resolver.py`: Smart tag selection from pre-fetched tags
- `src/scanner/trivy_scanner.py`: Extract and track scanned tag
- `src/scanner/scan_orchestrator.py`: Incremental saving after each scan
- `src/cli.py`: Updated to handle tuple return from resolver

**Test Coverage:**
- `tests/test_image_resolver.py`: Smart tag selection tests
- `tests/test_trivy_scanner.py`: Scanned tag tracking tests
- `tests/test_scan_orchestrator.py`: Incremental saving and crash recovery tests
- `tests/test_docker_hub_scraper.py`: Tag fetching tests

**Example Workflow:**
```bash
# 1. Scrape tools (fetches available tags upfront)
gts scrape --source docker_hub --namespaces popular

# 2. Scan with smart tag selection (uses pre-fetched tags)
gts scan --limit 50

# 3. View results (includes scanned_tag information)
gts top --limit 20

# 4. Interrupt and resume safely
gts scan --limit 100
# Press Ctrl+C after ~10 scans complete
# Check data/processed/tools.json - first 10 scans are saved

# Resume where it left off
gts scan --limit 100
# Skips the 10 already-scanned tools, continues with remaining
```

**Backward Compatibility:**
- Tools without `docker_tags` field use default tag (existing behavior)
- Tools without `scanned_tag` field load correctly (optional field)
- Incremental saving is additive - final batch save still happens
- No breaking changes to CLI interface or data structures

**Performance Impact:**
- Scraping: ~5-10% slower (one-time API call per repository to fetch tags)
- Scanning: ~10-20% slower (incremental saves add I/O overhead)
- Trade-off: Much better reliability and reproducibility

### 2026-01-21: Trivy Security Scanner Implementation

Implemented standalone Trivy security scanning capability via new `gts scan` CLI command.

**New Features:**
- **`gts scan` command**: Scan Docker Hub tools for vulnerabilities using Trivy
  - `--limit`: Limit number of tools to scan
  - `--force`: Re-scan all tools (ignore staleness)
  - `--tag`: Docker image tag to scan (default: latest)
  - `--concurrency`: Max concurrent scans (default: 3)
  - `--timeout`: Scan timeout in seconds (default: 300)
  - `--dry-run`: Preview without scanning

**New Modules:**
- `src/scanner/trivy_scanner.py`: Trivy CLI wrapper with async subprocess calls
  - Remote-first scan strategy (fast, no pull)
  - Automatic fallback to local pull if remote fails
  - JSON output parsing to extract vulnerability counts by severity
  - Timeout handling and comprehensive error recovery

- `src/scanner/scan_orchestrator.py`: Batch scanning orchestration
  - Lazy scanning: only scans tools with `status=UNKNOWN` or scans older than 7 days
  - Concurrency control with `asyncio.Semaphore` (default: 3 concurrent scans)
  - Progress tracking callbacks for CLI integration
  - Non-destructive updates (failed scans don't overwrite existing data)

- `src/scanner/image_resolver.py`: Tool ID to Docker image reference converter
  - Handles `library` namespace special case (e.g., `docker_hub:library/postgres` → `postgres:latest`)
  - Supports custom namespaces (e.g., `docker_hub:bitnami/postgresql` → `bitnami/postgresql:latest`)
  - Configurable default tag (via `--tag` flag)

- `src/scanner/scan_cache.py`: Failed scan caching (1-hour TTL)
  - Prevents repeated scanning of problematic images
  - Built on existing `FileCache` infrastructure
  - Automatic expiration after 1 hour allows retry

**New Data Models:**
- `src/models/model_scanner.py`:
  - `ScanResult`: Result of a single Trivy scan
  - `ScanBatchResult`: Aggregated results of scanning multiple tools

**Configuration:**
- Added Trivy constants to `src/consts.py`:
  - `TRIVY_DEFAULT_TIMEOUT = 300` (5 minutes)
  - `TRIVY_DEFAULT_TAG = "latest"`
  - `TRIVY_STALENESS_DAYS = 7` (re-scan after 7 days)
  - `TRIVY_CONCURRENCY = 3` (max concurrent scans)
  - `TRIVY_FAILED_SCAN_TTL = 3600` (1 hour cache for failed scans)

**Key Characteristics:**
- **Separate from pipeline**: Runs as standalone `gts scan` command (not integrated into scrape pipeline)
- **Lazy scanning**: Only scans when needed (unknown status or stale data)
- **Smart strategy**: Remote scan first (fast), local pull fallback (thorough)
- **Error resilient**: Non-destructive failure handling, temporary caching prevents hammering
- **Real-time feedback**: Progress bars and vulnerability summary tables via Rich

**Example Workflow:**
```bash
# Scrape tools
gts scrape --source docker_hub --namespaces popular

# Preview what would be scanned
gts scan --dry-run

# Scan for vulnerabilities
gts scan --limit 50

# Force re-scan all tools
gts scan --force

# View top-rated tools (security affects quality score)
gts top --limit 20
```

**Requirements:**
- Trivy must be installed separately (see [installation guide](https://aquasecurity.github.io/trivy/latest/getting-started/installation/))
- No changes to existing scraping or evaluation pipeline
- Fully backward compatible with existing tool data

## License

[MIT](LICENSE)
