# Contributing to GeneralToolScraper

Thank you for your interest in contributing! This document provides guidelines to ensure productive collaboration.

## Getting Started

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/GeneralToolScraper.git
cd GeneralToolScraper

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env

# Run tests
pytest

# Run linters
ruff check .
ruff format .
mypy .
```

### Running in Development

```bash
# Run with verbose logging
gts --verbose scrape --source docker_hub --limit 10

# Run tests with coverage
pytest --cov=gts --cov-report=html
```

## What We Accept

### Good Contributions

- Bug fixes with tests
- Performance improvements with benchmarks
- New source scrapers following `BaseScraper` contract
- CLI improvements that follow existing patterns
- Documentation fixes and clarifications
- Test coverage improvements

### Contributions That Need Discussion First

Open an issue before working on:

- New scoring dimensions
- Changes to scoring weights or algorithms
- Taxonomy modifications
- New filtering rules
- Breaking changes to data models
- Major architectural changes

## What We Don't Accept

### Subjective Tool Preferences

This project does **not** encode opinions about which tools are "better."

**Don't:**
- Add hardcoded bonuses/penalties for specific tools
- Modify weights to favor tools you prefer
- Add filtering rules targeting specific vendors
- Submit overrides that reflect personal preference

**Do:**
- Improve scoring algorithms to be more objective
- Add data sources that provide objective signals
- Report classification errors with evidence

### Vendor Bias

The system must remain vendor-neutral.

**Don't:**
- Add special cases for specific companies
- Weight sources to favor commercial tools
- Add "partner" or "sponsored" flags

### Scope Creep

Keep contributions focused on the core mission: discovering, evaluating, and cataloging development tools.

**Out of scope:**
- Package management features
- Deployment automation
- Cost analysis
- License compliance (beyond basic detection)
- Usage analytics/telemetry

## How to Propose Changes

### For Bug Fixes

1. Check existing issues
2. Create an issue describing the bug
3. Submit a PR referencing the issue
4. Include tests that would have caught the bug

### For New Features

1. Open a discussion issue first
2. Describe the use case and proposed solution
3. Wait for maintainer feedback
4. Submit PR only after approval

### For Taxonomy Changes

Taxonomy changes affect all classifications and require careful consideration.

**Process:**

1. Open an issue with:
   - Proposed change (add/rename/remove/restructure)
   - Justification with examples
   - Impact analysis (how many tools affected)

2. Allow 7 days for community feedback

3. If approved:
   - Increment `taxonomy_version`
   - Update taxonomy definition
   - Add migration notes
   - Update tests

**Examples of acceptable taxonomy changes:**

- Adding subcategory for clear cluster of tools (e.g., `databases/vector`)
- Splitting subcategory that grew too large
- Renaming for clarity (with alias for backward compatibility)

**Examples of rejected taxonomy changes:**

- Adding category for a single tool
- Restructuring "because it feels better"
- Changes that would require classifying >50% of tools

### For Scoring Algorithm Changes

Scoring changes affect all rankings and require justification.

**Process:**

1. Open an issue with:
   - Proposed change
   - Mathematical justification
   - Before/after examples (show impact on 10+ tools)
   - Edge case analysis

2. Allow 7 days for review

3. If approved:
   - Increment `score_version`
   - Update documentation
   - Add tests for new behavior

### For New Scoring Dimensions

Adding a new scoring dimension is a significant change.

**Requirements:**

- Clear definition of what it measures
- Objective data source (not subjective opinion)
- Demonstrated value (improves rankings for real use cases)
- Implementation of stateless evaluator

**Process:**

1. Open RFC issue with full proposal
2. Provide prototype implementation
3. Show before/after analysis
4. Allow 14 days for review

## Code Standards

### Style

- Python 3.11+
- Type hints on all functions
- Docstrings for public functions
- Ruff for formatting and linting
- Mypy for type checking

### Testing

- Unit tests for all new functions
- Integration tests for API interactions (mocked)
- E2E tests for critical paths
- Minimum 80% coverage for new code

### Commit Messages

```
<type>: <short description>

<body - what and why>

<footer - breaking changes, issue references>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Example:
```
feat: add time-decay option for popularity scoring

Adds optional exponential decay to popularity scores to favor
newer tools. Useful for greenfield projects where legacy
ecosystem doesn't matter.

Configurable via POPULARITY_DECAY_HALFLIFE env var.

Closes #42
```

### Pull Requests

- One logical change per PR
- Reference related issues
- Include tests
- Update documentation if behavior changes
- Add entry to CHANGELOG if user-facing

## Decision Making

### Design Decisions

Major decisions are recorded in [DECISIONS.md](docs/DECISIONS.md). Before proposing changes that contradict existing decisions:

1. Read the relevant decision record
2. Understand the rationale and alternatives considered
3. If you still disagree, open an issue explaining:
   - What's changed since the decision
   - New information that wasn't available
   - Concrete problems caused by current approach

### Governance

This project uses a benevolent dictator model. The maintainer(s) have final say on:

- What gets merged
- Roadmap priorities
- Architectural direction

Contributions are welcome, but not all will be accepted. This is normal and not personal.

## Communication

### Issues

- Search existing issues before creating new ones
- Use issue templates when available
- Provide reproduction steps for bugs
- Be specific about versions and environment

### Discussions

- Use GitHub Discussions for questions and ideas
- Be respectful and constructive
- Stay on topic

### Code Review

- Respond to feedback within 7 days
- Be open to suggestions
- Ask for clarification if needed
- Don't take feedback personally

## Release Process

1. Maintainer creates release branch
2. Version bump in `pyproject.toml`
3. Update CHANGELOG
4. Tag release
5. Publish to PyPI

Contributors don't need to worry about releases; maintainers handle this.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors are recognized in:

- Git history
- CHANGELOG entries
- Release notes

Thank you for contributing!
