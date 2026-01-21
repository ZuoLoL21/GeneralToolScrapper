# Design Decisions

This document records key design decisions, their rationale, and alternatives considered. It serves as a reference for contributors and prevents rehashing settled debates.

## Decision Record Format

Each decision includes:

- **Context:** The situation that led to the decision
- **Decision:** What we decided
- **Rationale:** Why we chose this approach
- **Alternatives Considered:** What else we evaluated
- **Consequences:** Trade-offs and implications

---

## D001: Relative Scoring (Not Absolute)

### Context

Users want to compare tools and understand "how good" a tool is. We need a scoring system.

### Decision

Scores are **relative within categories**, not absolute measures of quality.

- A score of 90 means "top ~10% within its category"
- Scores are NOT comparable across categories
- Cross-run comparisons require matching `score_version`

### Rationale

1. **Categories have different distributions.** A database with 10M downloads is average; a niche DNS tool with 10M downloads is exceptional.

2. **Absolute scores create false precision.** Saying "postgres is 92% good" implies a universal standard that doesn't exist.

3. **Relative scores are actionable.** "Top 10% in databases/relational" is meaningful for decision-making.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Absolute 0-100 scale | No meaningful definition of "100% good" |
| Letter grades (A-F) | Loses granularity, still needs relative thresholds |
| Percentile-only | Loses magnitude info (1M vs 900K both rank 95th) |

### Consequences

- Users must be educated that cross-category comparisons are invalid
- Documentation must emphasize relative interpretation
- `score_version` is required for reproducibility

---

## D002: No "Best Tool" Globally

### Context

Users ask "what's the best database?" We need to decide how to answer.

### Decision

The system **does not pick a single best tool** per category. Instead:

- **Basis Mode:** One top-scoring tool per *subcategory*
- **Full Mode:** All qualified tools with scores for comparison

### Rationale

1. **"Best" depends on context.** Postgres vs MySQL has real trade-offs (JSONB support, licensing, ecosystem, team experience).

2. **Picking winners loses information.** If we only show Postgres, users never learn about valid alternatives.

3. **Context varies by user.** A startup greenfield project has different needs than enterprise migration.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Single winner per category | Loses valid alternatives, imposes opinion |
| User-defined weights only | Puts burden on users who want quick answers |
| No recommendations at all | Fails the primary use case |

### Consequences

- Basis mode provides quick recommendations without false precision
- Full mode enables informed comparison
- Profiles allow context-specific weighting

---

## D003: LLM-Based Classification

### Context

Tools need to be categorized into a taxonomy for organization and comparison. We need a classification approach.

### Decision

Use a **local LLM (Ollama)** for classification with:

- Fixed taxonomy (LLM selects from predefined categories)
- Confidence thresholds (reject low-confidence results)
- Cache by canonical name
- Manual override capability

### Rationale

1. **Scales to unknown tools.** Unlike static mappings, LLM can classify tools it's never seen.

2. **Understands context.** Distinguishes "postgres" (database) from "postgres-api" (REST wrapper).

3. **No manual curation required.** Adding new tools doesn't require updating classification rules.

4. **Local and free.** Ollama runs locally, no API costs or data sharing.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Static mappings | Doesn't scale, requires constant maintenance |
| Tag/keyword matching | Brittle, misses nuance, high false positive rate |
| Cloud LLM API | Cost, latency, data privacy concerns |
| Manual classification | Doesn't scale, bottleneck on contributors |

### Consequences

- Requires Ollama installation for full mode
- MVP mode needs fallback (tag-based heuristics)
- Classification reproducibility requires prompt hashing
- Low-confidence results need human review

---

## D004: Observed vs Inferred Data Separation

### Context

The data model needs to store both raw data from sources and computed/derived data. We need to decide how to structure this.

### Decision

Explicitly separate data into:

- **Observed:** Data directly from source APIs (downloads, stars, vulnerabilities)
- **Inferred:** Data computed by our algorithms (scores, lifecycle, is_safe)

### Rationale

1. **Auditing.** Know exactly which data came from sources vs. our algorithms.

2. **Debugging.** When a score seems wrong, trace it to source data.

3. **ML readiness.** Clean separation of features (observed) from labels (inferred).

4. **Recomputation.** Change algorithms without re-scraping.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Flat structure | Unclear provenance, harder to debug |
| Separate tables/files | Adds complexity, harder to query |
| Prefix naming (`raw_*`, `computed_*`) | Verbose, easy to forget |

### Consequences

- Data model has `observed` and `inferred` namespaces
- Storage preserves raw data immutably
- Algorithm changes only require re-running inference

---

## D005: Two-Phase Filtering

### Context

We need to filter out low-quality tools, but filtering affects statistics which affect scoring.

### Decision

Use **two distinct filtering phases**:

1. **Pre-stat filtering:** After scrape, before categorization. Removes obvious junk.
2. **Post-score filtering:** After scoring. Removes policy violations using scores.

### Rationale

1. **Garbage affects statistics.** If spam tools are included in category stats, popularity normalization is polluted.

2. **Some filters need scores.** "Below minimum score" can only be applied after scoring.

3. **Clear separation of concerns.** Pre-filter is "is this even data?" Post-filter is "does this pass quality bar?"

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Single filter pass | Either pollutes stats or can't use score-based filters |
| Filter after everything | Spam/junk pollutes statistics |
| No filtering | Too much noise for users |

### Consequences

- Pre-filter must be conservative (only remove obvious junk)
- Stats are computed on pre-filtered data
- Post-filter can be aggressive (using score thresholds)

---

## D006: Canonical Name as Grouping Key

### Context

The same tool appears across multiple sources (Docker, GitHub, Helm). We need to group related artifacts.

### Decision

Use `canonical_name` as the grouping key:

- Assigned by deterministic resolution rules
- Cached classifications use canonical name as key
- All variants share the same classification

### Rationale

1. **Reduces redundant work.** Classify once, apply to all variants.

2. **Enables future aggregation.** Can compute canonical tool scores from variants.

3. **Improves search.** Users search for "postgres", get all variants.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| No grouping (artifact-only) | Redundant classification, poor UX |
| Group by name only | Name collisions (different tools, same name) |
| User-defined groupings | Doesn't scale, maintenance burden |

### Consequences

- Need robust canonical name resolution rules
- Collisions handled via precedence (official > verified > fallback)
- Override file for edge cases

---

## D007: MVP Mode with Feature Gates

### Context

The full system has many dependencies (Ollama, Trivy). This creates a high barrier to entry.

### Decision

Implement **MVP mode** that works with minimal dependencies:

- Docker Hub scraping only
- Popularity + maintenance scoring (no Trivy, no LLM)
- Basic categorization fallback
- Full CLI surface

### Rationale

1. **Faster time-to-value.** Users can validate data quality and UX immediately.

2. **Easier debugging.** Fewer moving parts means clearer error attribution.

3. **Gradual adoption.** Add features incrementally as needed.

4. **Lower barrier to entry.** Don't require Ollama/Trivy for first experience.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Full features only | High barrier, slow first experience |
| Separate tools | Fragmented UX, harder to upgrade |
| Optional features via flags | Too many combinations to test |

### Consequences

- Feature gates by mode (`GTS_MODE=mvp` vs `full`)
- Security scoring uses placeholder (70) in MVP mode
- Categorization falls back to tag heuristics in MVP mode
- Clear documentation of mode differences

---

## D008: Profiles for Context-Aware Defaults

### Context

Users have different contexts (production, startup, research) with different priorities. Flags are cumbersome.

### Decision

Implement **named profiles** that bundle configuration:

- Weights, filters, and flags in one name
- Defined in `config/profiles.yaml`
- Override with CLI flags as needed

### Rationale

1. **Reduces cognitive load.** `--profile production` vs remembering 6 flags.

2. **Encodes best practices.** Production profile enforces security-first, no experimental.

3. **Aligns with philosophy.** "Best depends on context" is now actionable.

4. **Shareable.** Teams can define custom profiles.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Flags only | Too many to remember, easy to forget |
| Preset commands (`gts-prod`) | Harder to customize, pollutes namespace |
| Config file only | Less discoverable, no quick switching |

### Consequences

- Profiles defined in YAML
- CLI `--profile` flag
- Flags override profile settings
- Built-in profiles for common cases

---

## D009: Security Score as Kill-Switch, Not Average

### Context

A tool might have high popularity but critical vulnerabilities. How should security affect the final score?

### Decision

Security has **two effects**:

1. **Score component** (35% weight by default)
2. **Kill-switch** (`is_blocking`) that removes tool regardless of score

### Rationale

1. **Averaging is dangerous.** A tool with 1 critical vuln shouldn't be saved by high popularity.

2. **But not all vulns are blocking.** Medium/low vulns should reduce score, not exclude.

3. **Policy should be explicit.** `is_blocking` makes the decision visible.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Security as just another weight | Critical vulns can be averaged away |
| Any vuln = exclusion | Too aggressive, most tools have some vulns |
| User decides per-tool | Doesn't scale, burden on user |

### Consequences

- `is_blocking` flag in data model
- Post-filter removes blocking tools
- Users can see why in `gts explain`
- Configurable blocking thresholds

---

## D010: Stateless Evaluators

### Context

Evaluators need context (category stats, config) to compute scores. We need to decide how they access this data.

### Decision

Evaluators are **pure functions** that receive all context as a parameter:

```python
def evaluate(self, tool: Tool, context: EvalContext) -> float
```

They never query storage directly or maintain hidden state.

### Rationale

1. **Testable.** Pass mock context, get predictable output.

2. **Parallelizable.** No shared state means trivial parallel execution.

3. **Reproducible.** Same inputs always produce same outputs.

4. **Debuggable.** All inputs are visible in the function call.

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Evaluators query storage | Hidden dependencies, hard to test |
| Global config object | Implicit state, hard to trace |
| Dependency injection | Overkill for this use case |

### Consequences

- `EvalContext` must be constructed before evaluation
- Stats generation is a separate, explicit step
- Evaluators are trivially testable
- Easy to parallelize scoring

---

## Pending Decisions

These are open questions for future resolution:

### P001: Score Aggregation Across Sources

When a canonical tool has variants from Docker, GitHub, and Helm, how do we compute a single score?

Options:
- Use best variant's score
- Average across variants
- Weight by source reliability
- Let user choose

### P002: Taxonomy Evolution

When should new categories/subcategories be added? What's the governance process?

### P003: Multi-Language Support

Should tool descriptions be translated? How to handle non-English sources?

---

## Decision Log

| ID | Decision | Date | Status |
|----|----------|------|--------|
| D001 | Relative Scoring | 2024-01 | Accepted |
| D002 | No Best Tool | 2024-01 | Accepted |
| D003 | LLM Classification | 2024-01 | Accepted |
| D004 | Observed/Inferred Split | 2024-01 | Accepted |
| D005 | Two-Phase Filtering | 2024-01 | Accepted |
| D006 | Canonical Name Grouping | 2024-01 | Accepted |
| D007 | MVP Mode | 2024-01 | Accepted |
| D008 | Profiles | 2024-01 | Accepted |
| D009 | Security Kill-Switch | 2024-01 | Accepted |
| D010 | Stateless Evaluators | 2024-01 | Accepted |
