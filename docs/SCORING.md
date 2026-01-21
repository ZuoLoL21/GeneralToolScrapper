# Scoring

This document describes the scoring algorithms, normalization approaches, and interpretation guidelines for GeneralToolScraper.

## Composite Score Formula

Tools are scored on four dimensions with configurable weights:

```
quality_score = (
    0.25 * popularity_score +
    0.35 * security_score +
    0.25 * maintenance_score +
    0.15 * trust_score
)
```

All dimension scores are 0-100. The composite score is also 0-100.

### Default Weights Rationale

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| Security | 0.35 | Highest weight because vulnerabilities have real consequences |
| Popularity | 0.25 | Community validation matters but can lag |
| Maintenance | 0.25 | Active maintenance indicates investment and responsiveness |
| Trust | 0.15 | Publisher reputation is signal but not determinative |

Weights are configurable via profiles (see [Configuration](CONFIGURATION.md)).

## Popularity Scoring

### The Problem

Raw popularity metrics have extreme distributions:

- PostgreSQL: 1B+ downloads
- Random tool: 5K downloads

Linear scaling would make all non-mega-popular tools score near zero.

### Solution: Log-Transform + Z-Score Normalization

**Step 1: Compute category statistics**

For each category/subcategory, calculate the mean and standard deviation of log-transformed downloads and stars.

```python
log_downloads = [log(d + 1) for d in category_downloads]
category_stats = {
    "log_mean": mean(log_downloads),
    "log_std": std(log_downloads),
    "sample_size": len(log_downloads)
}
```

Categories with fewer than 10 tools fall back to global stats.

**Step 2: Normalize each tool**

Apply log-transform, then compute z-score within the tool's category:

```python
log_value = log(tool.downloads + 1)
z_score = (log_value - category_stats.log_mean) / category_stats.log_std
```

This measures "how many standard deviations above/below average for this category."

**Step 3: Source-specific weighting**

Different sources emphasize different metrics:

| Source | Downloads Weight | Stars Weight |
|--------|-----------------|--------------|
| Docker Hub | 70% | 30% |
| GitHub | 40% | 60% |
| Helm Charts | 60% | 40% |

**Step 4: Convert to 0-100**

Use the cumulative distribution function (CDF) to map z-scores to a 0-100 scale:

```python
# z=0 → 50, z=2 → ~98, z=-2 → ~2
score = norm.cdf(z_score) * 100
```

### Algorithm Comparison

| Approach | Problem |
|----------|---------|
| Linear scaling | Outliers crush everyone else |
| Percentile ranking | Loses magnitude info (1M vs 900K both rank 95th) |
| Log scaling alone | Still needs reference point |
| **Log + Z-score** | Measures relative position within category distribution |

### Edge Cases

- Tools with 0 downloads use `log(1) = 0` and will score low
- New tools in popular categories naturally score lower (expected behavior)
- Categories with <10 tools fall back to global stats with a confidence penalty

### Time-Decay Mode (Optional)

By default, popularity is cumulative (total downloads). For contexts where recency matters, enable time-decay:

```python
effective_downloads = downloads * exp(-age_days / half_life)
```

Configure via:

```bash
POPULARITY_DECAY_HALFLIFE=730  # days (default: disabled)
```

Or use CLI flags:

```bash
gts top --modern          # Enable decay
gts top --greenfield      # Alias for --modern
```

**When to use time-decay:**

- Evaluating tools for a new project (no legacy constraints)
- Comparing recent alternatives to established tools
- Startup/greenfield contexts

**When NOT to use time-decay:**

- Existing stack compatibility matters
- Stability and ecosystem maturity are priorities

## Security Scoring

### Formula

```
security_score = 100 - (critical×60 + high×10 + medium×1 + low×0.5)
```

Minimum score is 0. Unknown status receives 70 (light penalty rather than 0).

### Severity Weights Rationale

| Severity | Penalty | Rationale |
|----------|---------|-----------|
| Critical | 60 | One critical vuln should dramatically impact score |
| High | 10 | Significant but less urgent |
| Medium | 1 | Minor impact on score |
| Low | 0.5 | Informational, minimal impact |

### Security Kill-Switch (`is_blocking`)

Artifacts with `is_blocking: true` are removed in post-filtering **regardless of their overall score**. This prevents security issues from being "averaged away" by high popularity or trust.

An artifact is blocking if:

- It has an exploitable critical vulnerability, OR
- A policy rule explicitly marks it as blocking

### Known Limitations

The current formula is a known simplification:

| Limitation | Impact |
|------------|--------|
| Treats all criticals equally | One critical ≠ always worse than ten highs |
| Ignores exploitability | CVSS severity ≠ real-world risk |
| Doesn't weight vulnerability age | Old vulns may be irrelevant |

### Planned Improvements

- Age weighting (newer vulnerabilities penalize more heavily)
- Exploit availability flag (if Trivy exposes it)
- Configurable hard-fail thresholds at artifact level

**Bottom line:** Treat security scores as directional indicators, not precise risk assessments.

## Maintenance Scoring

### Concept

Maintenance score measures update recency **relative to typical update frequency** for that tool.

A tool that updates yearly being 2 months stale is fine. A tool that updates daily being 2 months stale is concerning.

### Formula

```python
expected_gap = tool.update_frequency_days  # Typical gap between updates
actual_gap = days_since_last_update

if actual_gap <= expected_gap:
    maintenance_score = 100
else:
    staleness_ratio = actual_gap / expected_gap
    maintenance_score = max(0, 100 - (staleness_ratio - 1) * 25)
```

### Lifecycle Integration

Maintenance signals feed into lifecycle inference, but the relationship is strictly one-directional:

1. **Maintenance metrics** (update recency, frequency) → **infer lifecycle**
2. **Lifecycle** → **presentation bias** (sort order, visibility), not raw scores

The only exception: `legacy` lifecycle applies a score penalty since it indicates abandonment.

| Lifecycle | Maintenance Effect |
|-----------|-------------------|
| `experimental` | No score effect |
| `active` | No score effect |
| `stable` | No score effect |
| `legacy` | -20 penalty |

## Trust Scoring

### Base Scores by Publisher Type

| Publisher Type | Base Score | Description |
|---------------|------------|-------------|
| Official | 100 | Docker `library/*`, org-owned GitHub repos |
| Verified company | 90 | Verified Publisher badge, GitHub verified org |
| Company/Org | 70 | Known company without verification |
| User | 60 | Individual contributor |

### Community Reputation Bonus

User-maintained tools can earn bonus points based on:

- Consistent update history (+5 to +15)
- High engagement ratio (stars/downloads) (+5)
- Multiple maintainers listed (+5)

Maximum trust score is capped at 100.

### Cross-Source Trust Normalization

"Official" and "verified" mean different things across sources:

| Source | "Official" Meaning | "Verified" Meaning |
|--------|-------------------|-------------------|
| Docker Hub | `library/*` namespace (Docker-curated) | Verified Publisher badge |
| GitHub | Org-owned repo matching tool name | GitHub verified org badge |
| Artifact Hub | Official Helm chart designation | Verified publisher |

Trust scores are **source-relative**, not absolute. Cross-source trust comparisons are approximate.

When aggregating scores across sources for the same canonical tool, trust scores are averaged rather than compared directly.

## Score Analysis & Interpretation

### Score Ranges

Scores are **comparative within categories**, not absolute measures of quality.

| Score Range | Interpretation |
|-------------|----------------|
| 90-100 | Top tier within category |
| 70-89 | Above average |
| 50-69 | Average |
| 30-49 | Below average |
| 0-29 | Poor (likely filtered out) |

### Dominant Factor Detection

A tool with score 92 might be:

- Amazing across all dimensions, OR
- Mediocre everywhere except popularity

To surface this, each score includes dominant factor analysis:

```python
score_analysis = {
    "dominant_dimension": "popularity",
    "dominance_ratio": 1.8  # highest / second_highest
}
```

**Interpretation:**

| Dominance Ratio | Meaning |
|-----------------|---------|
| < 1.2 | Balanced across dimensions |
| 1.2 - 1.5 | Slight emphasis on one dimension |
| 1.5 - 2.0 | Notable skew |
| > 2.0 | Score dominated by single dimension |

When dominance ratio > 1.5, `gts explain` shows a warning:

```
⚠ Ranked highly primarily due to popularity; security score is below category median.
```

### Cross-Category Comparison

**Scores are NOT comparable across categories.**

A postgres score of 92 and a grafana score of 96 are NOT directly comparable:

- Different peer groups
- Different metric distributions
- Different category sizes

Only compare scores within the same category and scoring version.

### Score Versioning

Each score includes a `score_version` identifier (hash of algorithm + weights).

| Change | Scores Comparable? |
|--------|-------------------|
| Re-scrape same raw data | Yes |
| New tools added to catalog | Mostly (relative rankings may shift) |
| Weight changes | No |
| Taxonomy changes | No |
| Identity rules change | No |

When comparing results across runs:

- Same `score_version` → comparable
- Different `score_version` → treat as incompatible

### Deterministic Tie-Breakers

When scores are close (within 2 points), results are further sorted by:

1. Canonical tool rank > artifact rank
2. Official > verified > user
3. Stable > active > experimental
4. Alphabetical by name (final fallback)

This prevents "random feeling" results when multiple tools have similar scores.

## The `gts explain` Command

For transparency, use `gts explain <tool>` to see scoring details:

```bash
gts explain postgres
```

Output includes:

- **Score breakdown** by dimension (popularity, security, maintenance, trust)
- **Raw metrics** used for each dimension
- **Category context** (where tool falls in distribution)
- **Dominant factor** warning if applicable
- **Variant selection** (which artifact was used)
- **Lifecycle** classification and reasoning
- **Filters applied** (hidden, excluded, blocking reasons)
- **Canonical grouping** information

Example output:

```
postgres (docker_hub:library/postgres)
══════════════════════════════════════

Quality Score: 92/100
├── Popularity:  88 (z-score: +1.8 in databases/relational)
├── Security:    95 (0 critical, 1 high, 3 medium)
├── Maintenance: 98 (updated 3 days ago, typical: 14 days)
└── Trust:      100 (official image)

Analysis: Balanced score across all dimensions.
Lifecycle: stable (>2yr old, consistent updates, 1B+ downloads)
Canonical: postgres (3 variants across sources)
```
