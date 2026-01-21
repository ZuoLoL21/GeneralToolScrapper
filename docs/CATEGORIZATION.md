# Categorization

This document describes how tools are categorized, including LLM-based classification, the taxonomy, canonical identity resolution, and handling edge cases.

## Overview

Tools are automatically categorized using a local LLM (via Ollama) that classifies each tool into a fixed taxonomy based on its name, description, and tags.

## Why LLM-Based Classification?

| Approach | Pros | Cons |
|----------|------|------|
| **Static mappings** | Deterministic, no dependencies | Manual curation, doesn't scale |
| **Tag/keyword matching** | Simple, fast | Brittle, misses nuance |
| **LLM classification** | Handles nuance, scales to any tool | Requires local LLM |

LLM classification provides the best balance:

- **Handles tools the system has never seen before**
- **Understands context** (distinguishes "postgres" the database from "postgres-api" a REST wrapper)
- **Requires no manual curation** for new tools
- **Using Ollama keeps inference local and free**

### MVP Fallback

In MVP mode (`GTS_MODE=mvp`), LLM classification is disabled. Tools are categorized using:

1. Manual overrides (if present)
2. Tag-based heuristics (e.g., "database" tag → `databases` category)
3. Fallback to `uncategorized` with `needs_review: true`

## Taxonomy

The system uses a fixed two-level taxonomy. The LLM must select from this predefined list:

| Category | Subcategories |
|----------|---------------|
| **databases** | relational (postgres, mysql), document (mongodb, couchdb), key-value (redis, memcached), graph (neo4j, dgraph), time-series (influxdb, timescaledb), search (elasticsearch, meilisearch) |
| **monitoring** | metrics (prometheus, telegraf), logging (loki, fluentd), tracing (jaeger, zipkin), visualization (grafana, kibana), alerting (alertmanager) |
| **web** | server (nginx, apache, caddy), proxy (traefik, kong), load-balancer (haproxy, envoy) |
| **messaging** | queue (rabbitmq, activemq), streaming (kafka, redpanda), pubsub (nats, redis-pubsub) |
| **ci-cd** | build (jenkins, drone), deploy (argocd, flux), registry (harbor, nexus) |
| **security** | secrets (vault, sealed-secrets), auth (keycloak, oauth2-proxy), scanning (trivy, clair) |
| **storage** | object (minio, seaweedfs), file (nfs, glusterfs), backup (restic, velero) |
| **networking** | dns (coredns, pihole), vpn (wireguard, openvpn), service-mesh (istio, linkerd) |
| **runtime** | container (docker, containerd, podman), serverless (openfaas, knative), orchestration (kubernetes, nomad) |
| **development** | ide (code-server, jupyter), testing (selenium, playwright), debugging (delve, gdb), cli (kubectl, aws-cli), sdk (boto3, google-cloud-sdk) |

### Taxonomy Versioning

The taxonomy is versioned. When the taxonomy changes:

1. All tools get a new `taxonomy_version` field
2. Tools with outdated `taxonomy_version` are re-categorized
3. Cache entries for affected canonical names are invalidated

## Multiple Category Assignment

Tools can belong to multiple categories. Each tool has:

- **Primary category/subcategory**: The main classification
- **Secondary categories**: Additional relevant categories (optional)

### Example: Elasticsearch

- **Primary:** `databases/search` — It's fundamentally a search engine
- **Secondary:** `monitoring/logging` — Commonly used in logging stacks (ELK)

The LLM is prompted to identify both primary and secondary categories when applicable.

## Classification Flow

```
┌─────────────────┐
│ Tool to classify│
└────────┬────────┘
         ▼
┌─────────────────┐     Found
│ 1. Cache Lookup │────────────▶ Return cached classification
│ (by canonical)  │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐     Found
│ 2. Override     │────────────▶ Return override classification
│ (by artifact ID)│
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐     Success
│ 3. LLM Classify │────────────▶ Validate → Cache → Return
│ (via Ollama)    │
└────────┬────────┘
         │ Failure/Low Confidence
         ▼
┌─────────────────┐
│ 4. Route to     │
│ uncategorized   │
│ needs_review:   │
│ true            │
└─────────────────┘
```

### Step 1: Cache Lookup

Classifications are cached by `canonical_name` (e.g., "postgres"), not by artifact ID.

This means one classification covers all variants:

- `docker_hub:library/postgres`
- `github:postgres/postgres`
- `helm:bitnami/postgresql`

All share `canonical_name: "postgres"` and get the same cached classification.

### Step 2: Override Check

Manual overrides are checked by **full artifact ID**, allowing fine-grained corrections:

```json
{
  "docker_hub:someuser/postgres-api": {
    "primary_category": "web",
    "primary_subcategory": "server",
    "secondary_categories": ["databases/relational"],
    "reason": "REST API wrapper for PostgreSQL, not PostgreSQL itself"
  }
}
```

Overrides always take precedence and have confidence 1.0.

### Step 3: LLM Classification

On cache miss with no override, the tool is sent to Ollama:

```
Classify this development tool into categories from the provided taxonomy.

Tool: elasticsearch
Description: Open Source, Distributed, RESTful Search Engine
Tags: ["search", "elasticsearch", "database", "logging", "analytics"]

Respond in JSON format:
{
  "primary_category": "...",
  "primary_subcategory": "...",
  "secondary_categories": ["category/subcategory", ...],  // optional
  "confidence": 0.0-1.0
}

[Full taxonomy provided in prompt]
```

### Step 4: Validation & Caching

LLM outputs are validated before acceptance:

1. **JSON schema validation** — Response must match expected structure
2. **Enum enforcement** — `primary_category` must exist in taxonomy
3. **Subcategory validation** — `primary_subcategory` must be valid for the given category
4. **Secondary category format** — Each entry must be `"category/subcategory"` format

If any validation fails, the classification is rejected and routed to `uncategorized`.

## Classification Confidence & Rejection

### Confidence Thresholds

| Confidence | Action |
|------------|--------|
| ≥ 0.7 | Accept classification |
| < 0.7 | Reject, route to `uncategorized` with `needs_review: true` |

Surface problematic classifications via:

```bash
gts categories --needs-review
```

### Edge Cases

| Tool Type | Handling |
|-----------|----------|
| CLIs (`kubectl`, `aws-cli`) | Categorize under `development/cli` |
| SDKs and libraries | Categorize under `development/sdk` or exclude if not infrastructure |
| Meta-tools that don't fit | Route to `uncategorized`, flag for review |

## LLM Reproducibility

LLM classification is non-deterministic and model-version dependent. To ensure reproducibility:

### Prompt Hashing

Store a hash of the classification prompt:

```python
classification_cache_entry = {
    "classification": {...},
    "prompt_hash": "sha256:abc123...",
    "model": "llama3",
    "model_version": "8b-instruct",
    "classified_at": "2024-01-15T10:30:00Z"
}
```

If any of these change, force reclassification:

- Prompt template changes
- Taxonomy changes
- Model changes

### Raw Output Storage (Debug Only)

For debugging, raw LLM responses are stored in `data/cache/llm/`:

```json
{
  "canonical_name": "elasticsearch",
  "model": "llama3",
  "raw_response": "{\n  \"primary_category\": \"databases\"...",
  "tokens": 312,
  "latency_ms": 1250
}
```

This is ephemeral cache data, not processed data.

## Canonical Identity Resolution

The `canonical_name` is the linchpin of:

- Classification caching
- Variant grouping
- Collision avoidance
- Future score aggregation

### Assignment Rules (in order of precedence)

1. **Manual overrides always win** — If `overrides.json` specifies a canonical name, use it
2. **Official sources** — Docker `library/*` images, org-owned GitHub repos use the normalized tool name (e.g., `library/postgres` → `postgres`)
3. **Verified publisher match** — If a verified publisher's artifact matches a known canonical name, join that group
4. **Fallback** — Otherwise, `canonical_name` = artifact slug (e.g., `someuser/postgres-api` stays as `someuser/postgres-api`)

### Resolution Algorithm

```python
def resolve_canonical(artifact: Artifact) -> str:
    if artifact.id in manual_overrides:
        return manual_overrides[artifact.id].canonical_name
    if artifact.is_official:
        return normalize(artifact.name)
    if artifact.verified and matches_known_canonical(artifact):
        return find_matching_canonical(artifact)
    return artifact.slug
```

### Identity Confidence & Provenance

Each identity resolution includes confidence metadata:

```python
identity = {
    "canonical_name": "postgres",
    "resolution_source": "official",  # official | verified | override | fallback
    "resolution_confidence": 0.95,
    "identity_version": "v1"
}
```

**Confidence heuristics:**

| Resolution Source | Confidence |
|------------------|------------|
| Manual override | 1.0 |
| Official source | 0.95 |
| Verified org match | 0.85 |
| Fallback slug | 0.6 |

**Use confidence for:**

- Warnings in `gts explain`
- Filtering before aggregation
- Surfacing identity risks early

```bash
gts identity --low-confidence  # Show tools with resolution_confidence < 0.8
```

### Canonical Identity Invariants

These guarantees ensure cache safety, reproducibility, and contributor clarity:

| Invariant | Description |
|-----------|-------------|
| **One-to-one artifact mapping** | Each artifact maps to exactly one `canonical_name` |
| **Many-to-one grouping** | One `canonical_name` may have ≥1 artifacts |
| **Cross-run stability** | Canonical names are immutable across runs unless `identity_version` changes |
| **Override precedence** | Manual overrides always win and break ties deterministically |

## Handling Name Collisions

Different tools can share the same name:

- `docker_hub:library/postgres` — Actual PostgreSQL database
- `docker_hub:someuser/postgres` — Maybe a REST API wrapper
- `docker_hub:anotheruser/postgres` — Something completely unrelated

### Why It's Not a Big Problem

**1. Unique IDs prevent artifact-level collision**

Each artifact has a unique ID. They're never confused at the storage level.

**2. Canonical name assignment isn't just name-based**

Only official/verified publishers contribute to shared `canonical_name`. A random user's image would get its own canonical name.

**3. Official/verified images get priority**

Random user images would:

- Not share the same `canonical_name` (wrong publisher)
- Get categorized by their own description (which would say "REST API" not "database")
- Likely get filtered out anyway (low downloads, unverified)

**4. Override file for edge cases**

Misclassified artifacts can be corrected individually by their full artifact ID.

### Bottom Line

The collision risk is low because:

- Cache lookup is by `canonical_name`, not raw artifact name
- Canonical name grouping is intentional (publisher-verified), not automatic
- Fallback LLM classification uses description/tags (which differ for wrappers)
- Override file handles remaining edge cases

## Keyword Assignment

After classification, tools receive structured keywords to improve discoverability and enable rich filtering.

### Why Keywords Matter

| Use Case | How Keywords Help |
|----------|------------------|
| **Search** | Keywords enhance search relevance beyond just name/description matching |
| **Filtering** | Enable tag-based filtering (e.g., "show me all SQL databases") |
| **Discovery** | Expose cross-cutting concerns (e.g., "cloud-native", "self-hosted") |
| **Recommendations** | Power similarity-based recommendations via keyword overlap |

### Keyword Taxonomy

Keywords are organized hierarchically:

```
Category Keywords (shared across all subcategories)
    ↓
Subcategory Keywords (specific to subcategory)
    ↓
Cross-cutting Keywords (optional, span categories)
```

### Keyword Assignment Flow

```
┌─────────────────┐
│ Classified Tool │ (category/subcategory assigned)
└────────┬────────┘
         ▼
┌─────────────────┐     Found
│ 1. Cache Lookup │────────────▶ Return cached keywords
│ (by canonical)  │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ 2. Taxonomy     │
│    Lookup       │
│                 │
│ Collect:        │
│ - Category kws  │ ← Shared keywords (e.g., "database", "persistence")
│ - Subcat kws    │ ← Specific keywords (e.g., "sql", "acid")
│ - Cross-cutting │ ← Optional (e.g., "cloud-native")
└────────┬────────┘
         │
         ▼
      Cache → Return
```

### Example: `postgres`

**Inputs:**
- Category: `databases`
- Subcategory: `relational`

**Keywords assigned:**
- From category: `database`, `datastore`, `persistence`
- From subcategory: `sql`, `acid`, `transaction`, `query`, `schema`

**Final keywords:**
```
["database", "datastore", "persistence", "sql", "acid", "transaction", "query", "schema"]
```

### Keyword Caching

Like classifications, keyword assignments are cached by `canonical_name`:

```json
{
  "postgres": {
    "keywords": ["database", "sql", "relational", "acid", "postgresql"],
    "assigned_at": "2024-01-15T10:30:00Z",
    "taxonomy_version": "1.0"
  }
}
```

**Cache invalidation:**
- `taxonomy_version` changes
- `force=True` flag passed to keyword assigner
- Manual cache deletion

### Keyword Taxonomy Versioning

The keyword taxonomy is versioned independently of the category taxonomy:

| Version | Change Description |
|---------|-------------------|
| `1.0` | Initial keyword taxonomy with core infrastructure categories |

When the taxonomy changes:
1. `KEYWORD_TAXONOMY_VERSION` is incremented
2. Cached keyword assignments are invalidated
3. Tools are reassigned keywords on next pipeline run

### Fallback Behavior

If a category/subcategory is not in the keyword taxonomy:

1. Use category name as keyword (e.g., `"databases"`)
2. Use subcategory name as keyword (e.g., `"relational"`)
3. Log warning for manual taxonomy expansion

This ensures all tools get at least basic keywords.

## Configuration

```bash
# .env
OLLAMA_MODEL=llama3                      # Model for classification
OLLAMA_HOST=http://localhost:11434       # Ollama endpoint
CATEGORY_CACHE_PATH=data/cache/categories.json
CATEGORY_OVERRIDES_PATH=data/overrides.json
KEYWORD_CACHE_PATH=data/cache/keywords.json
MIN_CONFIDENCE_THRESHOLD=0.7             # Reject classifications below this
KEYWORD_TAXONOMY_VERSION=1.0             # Current keyword taxonomy version
```

## CLI Commands

```bash
# Categorize a specific tool
gts categorize postgres

# Bulk categorize all uncategorized tools
gts categorize --all

# Re-categorize (bypass cache)
gts categorize postgres --force

# Show category distribution
gts categories --stats

# Show tools needing review
gts categories --needs-review

# Show low-confidence identity resolutions
gts identity --low-confidence
```
