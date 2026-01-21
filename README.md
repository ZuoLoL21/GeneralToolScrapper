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
- [x] Categorization with keyword taxonomy
- [x] Keyword assignment system
- [x] File-based storage layer
- [x] Centralized caching
- [x] Popularity and maintenance evaluators
- [x] Pre/post filtering logic
- [x] Basic CLI (scrape, search, top, export)
- [x] Comprehensive test suite
- [x] Taxonomy extension (15 categories, 70 subcategories, 173 keywords)

### Future Phases

- **Phase 2:** GitHub scraper integration
- **Phase 3:** Helm Charts (Artifact Hub) scraper
- **Phase 4:** Tool disambiguation and canonical grouping
- **Phase 5:** Web UI

## License

[MIT](LICENSE)
