"""Tests for individual evaluators and composite scoring."""

from datetime import datetime, timedelta, timezone

import pytest

from src.evaluators.composite import analyze_score_dominance, calculate_quality_score
from src.evaluators.maintenance import MaintenanceEvaluator
from src.evaluators.popularity import PopularityEvaluator
from src.evaluators.registry import EvaluatorRegistry
from src.evaluators.security import SecurityEvaluator, get_blocking_status
from src.evaluators.trust import TrustEvaluator
from src.models.model_eval import ScoreWeights
from src.models.model_tool import (
    DominantDimension,
    Lifecycle,
    Maintenance,
    Maintainer,
    MaintainerType,
    Metrics,
    ScoreBreakdown,
    Security,
    SecurityStatus,
    SourceType,
    Tool,
    Vulnerabilities,
)


# Security Evaluator Tests
def test_security_no_vulnerabilities(sample_context):
    """Test security scoring with no vulnerabilities."""
    tool = Tool(
        id="test:safe/tool",
        name="safe-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        security=Security(status=SecurityStatus.OK, vulnerabilities=Vulnerabilities()),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = SecurityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 100.0
    assert not get_blocking_status(tool)


def test_security_unknown_status(sample_context):
    """Test security scoring with unknown status."""
    tool = Tool(
        id="test:unknown/tool",
        name="unknown-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        security=Security(status=SecurityStatus.UNKNOWN),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = SecurityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 70.0
    assert not get_blocking_status(tool)


def test_security_critical_vulnerability(sample_context):
    """Test security scoring with critical vulnerability."""
    tool = Tool(
        id="test:critical/tool",
        name="critical-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        security=Security(
            status=SecurityStatus.VULNERABLE,
            vulnerabilities=Vulnerabilities(critical=1),
        ),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = SecurityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 40.0  # 100 - 60
    assert get_blocking_status(tool)  # Critical should block


def test_security_mixed_vulnerabilities(sample_context):
    """Test security scoring with mixed vulnerabilities."""
    tool = Tool(
        id="test:mixed/tool",
        name="mixed-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        security=Security(
            status=SecurityStatus.VULNERABLE,
            vulnerabilities=Vulnerabilities(critical=0, high=2, medium=5, low=10),
        ),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = SecurityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    # 100 - (0*60 + 2*10 + 5*1 + 10*0.5) = 100 - 30 = 70
    assert score == 70.0
    assert not get_blocking_status(tool)


def test_security_floor_at_zero(sample_context):
    """Test that security score floors at 0."""
    tool = Tool(
        id="test:extreme/tool",
        name="extreme-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        security=Security(
            status=SecurityStatus.VULNERABLE,
            vulnerabilities=Vulnerabilities(critical=10, high=100),
        ),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = SecurityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 0.0


# Trust Evaluator Tests
def test_trust_official(sample_context):
    """Test trust scoring for official maintainer."""
    tool = Tool(
        id="test:official/tool",
        name="official-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintainer=Maintainer(name="Docker", type=MaintainerType.OFFICIAL, verified=True),
        metrics=Metrics(downloads=1000000, stars=1000),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = TrustEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 100.0


def test_trust_verified_company(sample_context):
    """Test trust scoring for verified company."""
    tool = Tool(
        id="test:company/tool",
        name="company-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintainer=Maintainer(name="Company", type=MaintainerType.COMPANY, verified=True),
        metrics=Metrics(downloads=100000, stars=500),
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = TrustEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 90.0


def test_trust_user_with_high_engagement(sample_context):
    """Test trust scoring for user with high engagement ratio."""
    tool = Tool(
        id="test:user/tool",
        name="user-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintainer=Maintainer(name="User", type=MaintainerType.USER, verified=False),
        metrics=Metrics(downloads=10000, stars=500),  # 5% engagement ratio
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = TrustEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    # Base 60 + 5 (high engagement) = 65
    assert score == 65.0


def test_trust_capped_at_100(sample_context):
    """Test that trust score is capped at 100."""
    tool = Tool(
        id="test:company/excellent",
        name="excellent",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintainer=Maintainer(name="Company", type=MaintainerType.COMPANY, verified=True),
        metrics=Metrics(downloads=1000, stars=500),  # 50% engagement ratio
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = TrustEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    # Would be 90 + 5 = 95, but capped at 100
    assert score <= 100.0


# Maintenance Evaluator Tests
def test_maintenance_up_to_date(sample_context):
    """Test maintenance scoring for up-to-date tool."""
    current_time = datetime.now(timezone.utc)
    tool = Tool(
        id="test:recent/tool",
        name="recent-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintenance=Maintenance(
            created_at=current_time - timedelta(days=365),
            last_updated=current_time - timedelta(days=5),
            update_frequency_days=30,
        ),
        lifecycle=Lifecycle.ACTIVE,
        scraped_at=current_time,
    )

    evaluator = MaintenanceEvaluator()
    score = evaluator.evaluate(tool, sample_context, current_time)

    assert score == 100.0


def test_maintenance_stale(sample_context):
    """Test maintenance scoring for stale tool."""
    current_time = datetime.now(timezone.utc)
    tool = Tool(
        id="test:stale/tool",
        name="stale-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintenance=Maintenance(
            created_at=current_time - timedelta(days=365),
            last_updated=current_time - timedelta(days=60),
            update_frequency_days=30,
        ),
        lifecycle=Lifecycle.ACTIVE,
        scraped_at=current_time,
    )

    evaluator = MaintenanceEvaluator()
    score = evaluator.evaluate(tool, sample_context, current_time)

    # staleness_ratio = 60/30 = 2
    # score = 100 - (2-1)*25 = 75
    assert score == 75.0


def test_maintenance_legacy_penalty(sample_context):
    """Test maintenance scoring with legacy lifecycle penalty."""
    current_time = datetime.now(timezone.utc)
    tool = Tool(
        id="test:legacy/tool",
        name="legacy-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintenance=Maintenance(
            created_at=current_time - timedelta(days=1000),
            last_updated=current_time - timedelta(days=30),
            update_frequency_days=30,
        ),
        lifecycle=Lifecycle.LEGACY,
        scraped_at=current_time,
    )

    evaluator = MaintenanceEvaluator()
    score = evaluator.evaluate(tool, sample_context, current_time)

    # Base score 100, minus legacy penalty -20 = 80
    assert score == 80.0


def test_maintenance_missing_last_updated(sample_context):
    """Test maintenance scoring with missing last_updated."""
    tool = Tool(
        id="test:missing/tool",
        name="missing-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintenance=Maintenance(
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
            last_updated=None,
            update_frequency_days=30,
        ),
        lifecycle=Lifecycle.ACTIVE,
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = MaintenanceEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    assert score == 0.0


# Popularity Evaluator Tests
def test_popularity_typical_tool(sample_context):
    """Test popularity scoring for typical tool."""
    tool = Tool(
        id="test:typical/tool",
        name="typical-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        metrics=Metrics(downloads=100000, stars=1000),
        primary_category="databases",
        primary_subcategory="relational",
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = PopularityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    # Score should be between 0 and 100
    assert 0 <= score <= 100


def test_popularity_zero_downloads(sample_context):
    """Test popularity scoring with zero downloads."""
    tool = Tool(
        id="test:zero/tool",
        name="zero-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        metrics=Metrics(downloads=0, stars=0),
        primary_category="databases",
        primary_subcategory="relational",
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = PopularityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    # Should still produce valid score (likely very low)
    assert 0 <= score <= 100


def test_popularity_small_category_fallback(sample_context):
    """Test popularity scoring falls back to global stats for small categories."""
    tool = Tool(
        id="test:small/tool",
        name="small-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        metrics=Metrics(downloads=50000, stars=500),
        primary_category="monitoring",
        primary_subcategory="visualization",  # Small category (5 tools)
        scraped_at=datetime.now(timezone.utc),
    )

    evaluator = PopularityEvaluator()
    score = evaluator.evaluate(tool, sample_context)

    # Should use global stats and produce valid score
    assert 0 <= score <= 100


# Composite Scoring Tests
def test_calculate_quality_score():
    """Test quality score calculation."""
    breakdown = ScoreBreakdown(
        popularity=80.0,
        security=90.0,
        maintenance=85.0,
        trust=70.0,
    )
    weights = ScoreWeights()  # Default weights

    quality_score = calculate_quality_score(breakdown, weights)

    # Manual calculation: 0.25*80 + 0.35*90 + 0.25*85 + 0.15*70
    expected = 0.25 * 80 + 0.35 * 90 + 0.25 * 85 + 0.15 * 70
    assert abs(quality_score - expected) < 0.01


def test_analyze_score_dominance_balanced():
    """Test score dominance analysis for balanced scores."""
    breakdown = ScoreBreakdown(
        popularity=85.0,
        security=88.0,
        maintenance=90.0,
        trust=87.0,
    )

    analysis = analyze_score_dominance(breakdown)

    assert analysis.dominant_dimension == DominantDimension.BALANCED
    assert analysis.dominance_ratio < 1.2


def test_analyze_score_dominance_single_dimension():
    """Test score dominance analysis for single dominant dimension."""
    breakdown = ScoreBreakdown(
        popularity=95.0,
        security=40.0,
        maintenance=35.0,
        trust=30.0,
    )

    analysis = analyze_score_dominance(breakdown)

    assert analysis.dominant_dimension == DominantDimension.POPULARITY
    assert analysis.dominance_ratio > 2.0


def test_analyze_score_dominance_all_zero():
    """Test score dominance analysis with all zeros."""
    breakdown = ScoreBreakdown(
        popularity=0.0,
        security=0.0,
        maintenance=0.0,
        trust=0.0,
    )

    analysis = analyze_score_dominance(breakdown)

    assert analysis.dominant_dimension == DominantDimension.BALANCED
    assert analysis.dominance_ratio == 1.0


# Evaluator Registry Tests
def test_registry_evaluate_tool(sample_context):
    """Test full evaluation pipeline through registry."""
    current_time = datetime.now(timezone.utc)
    tool = Tool(
        id="test:complete/tool",
        name="complete-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        maintainer=Maintainer(name="Company", type=MaintainerType.COMPANY, verified=True),
        metrics=Metrics(downloads=100000, stars=1000),
        security=Security(status=SecurityStatus.OK, vulnerabilities=Vulnerabilities()),
        maintenance=Maintenance(
            created_at=current_time - timedelta(days=365),
            last_updated=current_time - timedelta(days=10),
            update_frequency_days=30,
        ),
        primary_category="databases",
        primary_subcategory="relational",
        lifecycle=Lifecycle.ACTIVE,
        scraped_at=current_time,
    )

    registry = EvaluatorRegistry()
    scored_tool = registry.evaluate_tool(tool, sample_context, current_time)

    # Check that all scores were computed
    assert scored_tool.quality_score is not None
    assert 0 <= scored_tool.quality_score <= 100
    assert scored_tool.score_breakdown.popularity > 0
    assert scored_tool.score_breakdown.security > 0
    assert scored_tool.score_breakdown.maintenance > 0
    assert scored_tool.score_breakdown.trust > 0
    assert scored_tool.score_analysis is not None


def test_registry_blocking_status(sample_context):
    """Test that registry sets blocking status for critical vulnerabilities."""
    from src.models.model_tool import FilterReasons, FilterState

    tool = Tool(
        id="test:vulnerable/tool",
        name="vulnerable-tool",
        source=SourceType.DOCKER_HUB,
        source_url="https://example.com",
        security=Security(
            status=SecurityStatus.VULNERABLE,
            vulnerabilities=Vulnerabilities(critical=1),
        ),
        scraped_at=datetime.now(timezone.utc),
    )

    registry = EvaluatorRegistry()
    scored_tool = registry.evaluate_tool(tool, sample_context)

    # Should be marked as excluded due to critical vulnerability
    assert scored_tool.filter_status.state == FilterState.EXCLUDED
    assert FilterReasons.CRITICAL_VULNERABILITY in scored_tool.filter_status.reasons
