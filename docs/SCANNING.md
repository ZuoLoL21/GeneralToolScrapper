# Security Scanning with Trivy

This document explains the security scanning system, including smart tag selection, incremental saving, and crash recovery mechanisms.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Smart Tag Selection](#smart-tag-selection)
- [Incremental Saving](#incremental-saving)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)
- [Performance Considerations](#performance-considerations)
- [Testing](#testing)

## Overview

The security scanning system uses [Trivy](https://aquasecurity.github.io/trivy/) to scan Docker images for vulnerabilities. It features:

1. **Smart Tag Selection**: Intelligently selects the best available Docker tag to scan
2. **Tag Tracking**: Records which tag was scanned for reproducibility
3. **Incremental Saving**: Saves results after each scan to prevent data loss
4. **Crash Recovery**: Automatically resumes from last saved state
5. **Lazy Scanning**: Only scans tools with unknown or stale security status

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1: Scraping (ONE-TIME TAG FETCH)                         │
├─────────────────────────────────────────────────────────────────┤
│ DockerHubScraper                                                 │
│   └─> _parse_tool()                                             │
│        └─> _fetch_available_tags(namespace, name)              │
│             └─> GET /repositories/{ns}/{name}/tags              │
│                  └─> Store in tool.docker_tags                  │
│                       ["latest", "stable", "alpine", ...]       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 2: Scanning (NO API CALLS - Uses Pre-Fetched Tags)       │
├─────────────────────────────────────────────────────────────────┤
│ ScanOrchestrator.scan_batch()                                    │
│   └─> For each tool:                                            │
│        ├─> ImageResolver.resolve_image_ref(tool)                │
│        │    └─> _select_tag(tool.docker_tags, default_tag)     │
│        │         Priority: stable → latest → alpine → first     │
│        │         Returns: (image_ref, selected_tag)             │
│        │                                                         │
│        ├─> TrivyScanner.scan_image(image_ref)                   │
│        │    └─> Extract tag from image_ref                      │
│        │         Returns: ScanResult(scanned_tag=...)           │
│        │                                                         │
│        ├─> Update tool.security with scan results               │
│        │    └─> Set scanned_tag, vulnerabilities, status        │
│        │                                                         │
│        └─> FileManager.save_processed([tool], merge=True)       │
│             └─> Incremental save (crash-safe)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. DockerHubScraper (src/scrapers/docker_hub/docker_hub.py)

**Fetches available tags during scraping:**

```python
async def _fetch_available_tags(
    self,
    namespace: str,
    name: str,
    limit: int = 50,
) -> list[str]:
    """Fetch available Docker image tags for a repository.

    Called DURING SCRAPING to get available tags upfront.

    Returns:
        List of tag names (e.g., ["latest", "alpine", "1.0.5"])
    """
```

**Populates tool.docker_tags:**

```python
async def _parse_tool(self, repo: dict[str, Any], namespace: str) -> Tool:
    # ... existing parsing ...

    # Fetch available Docker image tags during scraping
    docker_tags = await self._fetch_available_tags(namespace, name)

    return Tool(
        # ... other fields ...
        docker_tags=docker_tags,  # Store fetched tags
    )
```

#### 2. ImageResolver (src/scanner/image_resolver.py)

**Smart tag selection from pre-fetched tags:**

```python
def _select_tag(self, available_tags: list[str], default: str) -> str:
    """Select best tag from pre-fetched options (NO API calls).

    Priority:
    1. stable
    2. latest
    3. alpine
    4. first available
    """
    if not available_tags:
        return default

    # Priority order
    for preferred in ["stable", "latest", "alpine"]:
        if preferred in available_tags:
            return preferred

    # Fall back to first available
    return available_tags[0]

def resolve_image_ref(self, tool: Tool) -> tuple[str, str] | None:
    """Convert tool ID to Docker image reference with smart tag selection.

    Uses tags already fetched during scraping (tool.docker_tags).
    NO API calls - just in-memory tag selection.

    Returns:
        Tuple of (image_ref, selected_tag) or None if not a Docker Hub tool
    """
    # ... parse namespace and name ...

    # Smart tag selection from pre-fetched tags
    selected_tag = self._select_tag(tool.docker_tags, self.default_tag)

    # Build image reference
    if namespace == "library":
        image_ref = f"{name}:{selected_tag}"
    else:
        image_ref = f"{namespace}/{name}:{selected_tag}"

    return (image_ref, selected_tag)
```

#### 3. TrivyScanner (src/scanner/trivy_scanner.py)

**Extracts and tracks scanned tag:**

```python
async def scan_image(
    self,
    image_ref: str,
    try_remote_first: bool | None = None,
) -> ScanResult:
    """Scan Docker image using Trivy.

    Extracts tag from image_ref and includes in result.
    """
    # Extract tag from image_ref (e.g., "postgres:stable" → "stable")
    scanned_tag = None
    if ":" in image_ref:
        scanned_tag = image_ref.split(":")[-1]

    # ... perform scan ...

    return ScanResult(
        success=result.success,
        vulnerabilities=result.vulnerabilities,
        scan_date=result.scan_date,
        error=result.error,
        scan_duration_seconds=duration,
        image_ref=image_ref,
        scanned_tag=scanned_tag,  # NEW: Track which tag was scanned
    )
```

#### 4. ScanOrchestrator (src/scanner/scan_orchestrator.py)

**Incremental saving after each scan:**

```python
async def scan_batch(
    self,
    tools: list[Tool],
    concurrency: int = 3,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ScanBatchResult:
    """Scan tools with concurrency control and incremental saving."""

    async def scan_one(tool: Tool) -> Tool | None:
        # Resolve image reference (returns tuple)
        result_tuple = self.resolver.resolve_image_ref(tool)
        if not result_tuple:
            return None

        image_ref, selected_tag = result_tuple

        # Scan
        result = await self.scanner.scan_image(image_ref)

        if result.success:
            # Update tool with scan results
            updated_tool = self.update_tool_security(tool, result)

            # Save immediately (incremental save)
            try:
                self.file_manager.save_processed([updated_tool], merge=True)
                logger.debug(f"Saved scan result for {tool.id}")
            except Exception as e:
                logger.warning(f"Failed to save {tool.id}: {e}")
                # Don't fail the scan if save fails

            return updated_tool
        else:
            # Cache failure
            return None

    # Run all scans concurrently
    results = await asyncio.gather(*[scan_one(tool) for tool in tools])

    return ScanBatchResult(...)
```

**Update tool security with scanned tag:**

```python
def update_tool_security(self, tool: Tool, scan_result: ScanResult) -> Tool:
    """Update tool.security with scan results.

    Sets scanned_tag, vulnerabilities, status, and scan_date.
    """
    new_security = tool.security.model_copy()
    new_security.vulnerabilities = scan_result.vulnerabilities
    new_security.trivy_scan_date = scan_result.scan_date
    new_security.scanned_tag = scan_result.scanned_tag  # NEW

    # Determine status based on vulnerabilities
    if scan_result.vulnerabilities.critical > 0 or scan_result.vulnerabilities.high > 0:
        new_security.status = SecurityStatus.VULNERABLE
    else:
        new_security.status = SecurityStatus.OK

    return tool.model_copy(update={"security": new_security})
```

## Smart Tag Selection

### Why Smart Tag Selection?

Many Docker images don't have a `latest` tag or use different tagging conventions:

- **Version-based**: `16-alpine`, `1.0.5`, `3.11.2`
- **Distribution-based**: `16-bullseye`, `alpine3.18`, `ubuntu-22.04`
- **Stability-based**: `stable`, `lts`, `edge`

Hardcoding `:latest` causes scans to fail for these images.

### Tag Selection Priority

The system uses this priority order to select the best available tag:

1. **`stable`** - Preferred for production-ready versions
2. **`latest`** - Most recent version
3. **`alpine`** - Lightweight variant, commonly available
4. **First available** - Falls back to first tag in list
5. **Configured default** - Uses `--tag` flag value if no tags available

### Examples

**Tool with stable tag:**
```json
{
  "id": "docker_hub:library/postgres",
  "docker_tags": ["latest", "stable", "alpine", "16-bullseye"]
}
```
→ Selects `stable` → Scans `postgres:stable`

**Tool without stable or latest:**
```json
{
  "id": "docker_hub:library/redis",
  "docker_tags": ["alpine", "7.0", "6.2"]
}
```
→ Selects `alpine` → Scans `redis:alpine`

**Tool with only versioned tags:**
```json
{
  "id": "docker_hub:bitnami/postgresql",
  "docker_tags": ["16.1.0", "15.5.0", "14.10.0"]
}
```
→ Selects `16.1.0` (first) → Scans `bitnami/postgresql:16.1.0`

**Tool with no docker_tags (backward compatibility):**
```json
{
  "id": "docker_hub:library/nginx",
  "docker_tags": []
}
```
→ Uses default tag → Scans `nginx:latest`

### Tag Fetching During Scraping

Tags are fetched **once during scraping** and stored for future scans:

```bash
# Scraping phase: Fetches and stores tags
gts scrape --source docker_hub --namespaces popular
# Output: For each tool, queries /repositories/{ns}/{name}/tags
#         Stores results in tool.docker_tags field

# Scanning phase: Uses pre-fetched tags (NO API calls)
gts scan
# Output: Reads tool.docker_tags from storage
#         Selects best tag using priority order
#         Scans selected tag
```

**Benefits:**
- No API calls during scanning (faster, more reliable)
- Tags cached with existing 24h TTL
- Consistent tag selection across scan runs
- Reproducible scans (tag is recorded in results)

## Incremental Saving

### Why Incremental Saving?

**Problem:** Original implementation saved all results at the end:
```
Scan 100 tools → All complete → Save once at end
                     ↓
              If crash here: Lose all progress!
```

**Solution:** Save after each successful scan:
```
Scan tool 1 → Save → Scan tool 2 → Save → ... → Scan tool 100 → Save
    ↓             ↓
If crash:    Already saved!
```

### How It Works

1. **After each successful scan:**
   ```python
   # Scan succeeds
   updated_tool = update_tool_security(tool, scan_result)

   # Save immediately with merge=True
   file_manager.save_processed([updated_tool], merge=True)
   ```

2. **Merge behavior:**
   ```python
   # FileManager.save_processed(tools, merge=True):
   # 1. Load existing tools.json
   # 2. Merge new tool by ID (update if exists, add if new)
   # 3. Write back to disk
   ```

3. **Error handling:**
   ```python
   try:
       file_manager.save_processed([updated_tool], merge=True)
   except Exception as e:
       logger.warning(f"Failed to save {tool.id}: {e}")
       # Don't fail the scan - continue with next tool
   ```

### Crash Recovery

**Scenario:** Scanning 100 tools, crashes after 50

```bash
# Start scan
gts scan --limit 100
# Progress: [====================          ] 50/100
# System crashes / user presses Ctrl+C

# Check saved data
cat data/processed/tools.json
# Contains 50 completed scans

# Resume scanning
gts scan --limit 100
# Progress: [                    ] 0/50 (skips first 50)
# Only scans remaining 50 tools
```

### Concurrency Safety

Incremental saves are safe with async concurrency:

- **Event Loop Serialization**: Async/await ensures sequential execution
- **File Locking**: Each `save_processed()` operation is atomic
- **Merge Strategy**: `merge=True` prevents data loss

```python
# Even with concurrency=5, saves are serialized:
async def scan_one(tool):
    result = await scanner.scan_image(...)  # Async (parallel)
    updated_tool = update_tool_security(...)
    file_manager.save_processed([updated_tool], merge=True)  # Sync (serial)
```

## Usage Examples

### Basic Scanning

```bash
# Scrape tools (fetches tags)
gts scrape --source docker_hub --namespaces popular

# Scan with smart tag selection
gts scan

# View results with scanned tag information
gts top --limit 20
```

### Dry Run Mode

```bash
# Preview which tags will be scanned
gts scan --dry-run

# Output:
# ┌────────────────────────────────┬──────────────────┬────────────┬──────────┐
# │ Tool ID                        │ Image Ref        │ Status     │ Last Scan│
# ├────────────────────────────────┼──────────────────┼────────────┼──────────┤
# │ docker_hub:library/postgres    │ postgres:stable  │ UNKNOWN    │ Never    │
# │ docker_hub:library/redis       │ redis:alpine     │ UNKNOWN    │ Never    │
# │ docker_hub:bitnami/postgresql  │ bitnami/post..   │ UNKNOWN    │ Never    │
# └────────────────────────────────┴──────────────────┴────────────┴──────────┘
```

### Crash Recovery Workflow

```bash
# Start large scan
gts scan --limit 500

# Interrupt after ~100 scans (Ctrl+C)
^C

# Check progress
cat data/processed/tools.json | jq '.tools[] | select(.security.scanned_tag != null) | .id' | wc -l
# Output: 100

# Resume - automatically skips already-scanned tools
gts scan --limit 500
# Scans remaining 400 tools
```

### Force Re-scan with Different Tag

```bash
# Re-scan all tools (ignores staleness)
gts scan --force

# Results will use newly selected tags based on current docker_tags
```

### Inspect Scanned Tags

```bash
# View scanned tags for all tools
cat data/processed/tools.json | jq '.tools[] | {id, scanned_tag: .security.scanned_tag}'

# Output:
# {
#   "id": "docker_hub:library/postgres",
#   "scanned_tag": "stable"
# }
# {
#   "id": "docker_hub:library/redis",
#   "scanned_tag": "alpine"
# }
```

## Error Handling

### Tag Fetching Errors

```python
# If tag fetching fails during scraping:
docker_tags = []  # Empty list (backward compatible)

# During scanning:
selected_tag = self._select_tag([], "latest")  # Uses default tag
```

### Scan Errors

```python
# Failed scans are cached (1 hour TTL):
scan_cache.mark_failed(tool.id, error_message)

# Skip on next scan:
if scan_cache.is_failed(tool.id):
    skipped += 1
    continue
```

### Save Errors

```python
# Save failures don't break scanning:
try:
    file_manager.save_processed([tool], merge=True)
except Exception as e:
    logger.warning(f"Failed to save {tool.id}: {e}")
    # Scan still succeeds, just not persisted immediately
```

## Performance Considerations

### Scraping Performance

**Impact:** ~5-10% slower

**Why:**
- One additional API call per repository (`/tags` endpoint)
- Mitigated by existing response cache (24h TTL)
- Limited to first 50 tags to keep responses small

**Example:**
```
Before: 100 repos × 1 API call = 100 requests
After:  100 repos × 2 API calls = 200 requests
Cache hit rate: ~90% on subsequent scrapes
```

### Scanning Performance

**Impact:** ~10-20% slower

**Why:**
- Incremental saves add I/O after each scan (~10-50ms per save)
- Trade-off: Crash resilience vs. speed

**Example:**
```
Before: Scan 100 tools (5 min) → Save once (0.5s) = 5m 0.5s
After:  Scan 100 tools (5 min) → Save 100 times (5s) = 5m 5s
```

**Mitigation:**
- Saves use merge mode (efficient JSON updates)
- Final batch save kept for backward compatibility

### Memory Usage

**No significant impact:**
- Tags stored as small string lists
- Average: ~10-20 tags per tool × ~20 bytes per tag = ~400 bytes per tool
- For 10,000 tools: ~4 MB additional memory

## Testing

### Test Coverage

**New Test Files:**

1. **tests/test_image_resolver.py** - Smart tag selection
   - Priority order (stable → latest → alpine → first)
   - Empty tag list handling
   - Malformed tool IDs
   - Custom default tags

2. **tests/test_trivy_scanner.py** - Scanned tag tracking
   - Tag extraction from image_ref
   - Handling images without tags
   - Tag preservation on errors
   - Fallback to local scan

3. **tests/test_scan_orchestrator.py** - Incremental saving
   - Save after each scan
   - Failed save doesn't break scan
   - Merge parameter verification
   - Crash recovery simulation

4. **tests/test_docker_hub_scraper.py** - Tag fetching
   - Successful tag fetching
   - 404 error handling
   - Network error handling
   - Tag population in _parse_tool()

### Running Tests

```bash
# Run all scanning tests
pytest tests/test_image_resolver.py
pytest tests/test_trivy_scanner.py
pytest tests/test_scan_orchestrator.py
pytest tests/test_docker_hub_scraper.py

# Run with coverage
pytest --cov=src/scanner --cov=src/scrapers/docker_hub tests/

# Run specific test
pytest tests/test_image_resolver.py::TestImageResolver::test_select_tag_with_stable -v
```

## Data Model Reference

### Tool.docker_tags

```python
docker_tags: list[str] = Field(
    default_factory=list,
    description="Available Docker image tags (versions) from Docker Hub"
)

# Example:
{
  "docker_tags": ["latest", "stable", "alpine", "16-bullseye", "15.2.0"]
}
```

### Security.scanned_tag

```python
scanned_tag: str | None = Field(
    default=None,
    description="Docker image tag that was scanned (e.g., 'latest', 'alpine', '1.0.5')"
)

# Example:
{
  "security": {
    "status": "ok",
    "scanned_tag": "stable",
    "trivy_scan_date": "2026-01-21T10:30:00Z",
    "vulnerabilities": {
      "critical": 0,
      "high": 1,
      "medium": 3,
      "low": 5
    }
  }
}
```

### ScanResult.scanned_tag

```python
@dataclass
class ScanResult:
    success: bool
    vulnerabilities: Vulnerabilities | None
    scan_date: datetime
    error: str | None
    scan_duration_seconds: float
    image_ref: str
    scanned_tag: str | None = None  # NEW
```

## Backward Compatibility

### Old Tools Without docker_tags

```python
# Tool loaded from old data:
{
  "id": "docker_hub:library/nginx",
  "docker_tags": []  # Field doesn't exist → defaults to empty list
}

# During scanning:
selected_tag = _select_tag([], "latest")  # Uses default tag
# → Scans "nginx:latest" (existing behavior)
```

### Old Tools Without scanned_tag

```python
# Tool loaded from old data:
{
  "security": {
    "status": "ok",
    # No scanned_tag field
  }
}

# Field is optional → loads successfully
# security.scanned_tag = None
```

### No Breaking Changes

- CLI interface unchanged
- Data structures extended (not modified)
- Existing workflows continue to work
- New features are additive
