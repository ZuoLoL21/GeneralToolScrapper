# GeneralToolScraper

A tool aggregation system that discovers, evaluates, and catalogs useful development tools from multiple sources (Docker Hub, GitHub, Helm Charts).

## Primary Purpose

**GeneralToolScraper is a recommendation engine for infrastructure tooling.** It helps teams answer "what's the best tool for X?" by aggregating data from multiple sources, scoring tools on quality dimensions, and presenting context-aware recommendations.

While the data can serve research, compliance, or productivity use cases, the primary design goal is actionable recommendations with transparent scoring.

## Quick Start

```bash
# Clone and setup
cd GeneralToolScraper
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Run (MVP mode - no LLM/Trivy required)
gts scrape --source docker_hub
gts search "postgres" --category databases
gts top --category monitoring --limit 10
gts export --format json --output tools.json
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

### Phase 1: Docker Hub MVP (Current)

- [x] Project scaffolding and data models
- [ ] Docker Hub scraper with resilience
- [ ] File-based storage layer
- [ ] Popularity and maintenance evaluators
- [ ] Basic CLI (scrape, search, top, export)
- [ ] Pre/post filtering logic

### Future Phases

- **Phase 2:** GitHub scraper integration
- **Phase 3:** Helm Charts (Artifact Hub) scraper
- **Phase 4:** Tool disambiguation and canonical grouping
- **Phase 5:** Web UI

## License

[MIT](LICENSE)
