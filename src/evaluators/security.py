"""Security evaluator for vulnerability-based scoring."""

from src.models.model_stats import EvalContext
from src.models.model_tool import SecurityStatus, Tool

# Penalty weights from SCORING.md
PENALTY_CRITICAL = 60
PENALTY_HIGH = 10
PENALTY_MEDIUM = 1
PENALTY_LOW = 0.5
UNKNOWN_SCORE = 70


class SecurityEvaluator:
    """Evaluates tools based on vulnerability severity.

    Algorithm from SCORING.md:
        security_score = 100 - (critical×60 + high×10 + medium×1 + low×0.5)
        Minimum: 0
        Unknown status: 70
    """

    def evaluate(self, tool: Tool, context: EvalContext) -> float:
        """Calculate security score based on vulnerabilities.

        Args:
            tool: The tool to evaluate
            context: Evaluation context (unused for security scoring)

        Returns:
            Security score between 0-100
        """
        # Unknown status receives a light penalty
        if tool.security.status == SecurityStatus.UNKNOWN:
            return UNKNOWN_SCORE

        # Calculate penalty from vulnerabilities
        vulns = tool.security.vulnerabilities
        penalty = (
            vulns.critical * PENALTY_CRITICAL
            + vulns.high * PENALTY_HIGH
            + vulns.medium * PENALTY_MEDIUM
            + vulns.low * PENALTY_LOW
        )

        # Score starts at 100 and decreases by penalty
        score = 100 - penalty

        # Clamp to minimum 0
        return max(0.0, score)


def get_blocking_status(tool: Tool) -> bool:
    """Determine if tool should be blocked due to security issues.

    Args:
        tool: The tool to check

    Returns:
        True if tool has blocking security issues (any critical vulnerability)
    """
    return tool.security.vulnerabilities.critical > 0


def main() -> None:
    """Demonstrate security scoring with sample tools."""
    from datetime import datetime, timezone

    from src.models.model_eval import ScoreWeights
    from src.models.model_stats import (
        CategoryStats,
        DistributionStats,
        EvalContext,
        GlobalStats,
    )
    from src.models.model_tool import (
        Identity,
        Maintainer,
        MaintainerType,
        Metrics,
        Security,
        SourceType,
        Vulnerabilities,
    )

    print("Security Evaluator Demo")
    print("=" * 50)

    # Create mock context (not used for security scoring)
    mock_global_stats = GlobalStats(
        total_tools=1000,
        downloads=DistributionStats(
            min=100,
            max=1_000_000_000,
            median=50_000,
            p25=10_000,
            p75=200_000,
            log_mean=10.5,
            log_std=2.0,
        ),
        stars=DistributionStats(
            min=10,
            max=100_000,
            median=500,
            p25=100,
            p75=2_000,
            log_mean=6.2,
            log_std=1.5,
        ),
    )
    context = EvalContext(global_stats=mock_global_stats, weights=ScoreWeights())

    evaluator = SecurityEvaluator()

    # Test cases
    test_cases = [
        (
            "Perfect - No vulnerabilities",
            Tool(
                id="test:safe/tool",
                name="safe-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                security=Security(status=SecurityStatus.OK, vulnerabilities=Vulnerabilities()),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Unknown status",
            Tool(
                id="test:unknown/tool",
                name="unknown-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                security=Security(status=SecurityStatus.UNKNOWN),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "One critical vulnerability",
            Tool(
                id="test:critical/tool",
                name="critical-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                security=Security(
                    status=SecurityStatus.VULNERABLE,
                    vulnerabilities=Vulnerabilities(critical=1),
                ),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Multiple high vulnerabilities",
            Tool(
                id="test:high/tool",
                name="high-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                security=Security(
                    status=SecurityStatus.VULNERABLE,
                    vulnerabilities=Vulnerabilities(high=5),
                ),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Mixed vulnerabilities",
            Tool(
                id="test:mixed/tool",
                name="mixed-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                security=Security(
                    status=SecurityStatus.VULNERABLE,
                    vulnerabilities=Vulnerabilities(critical=0, high=1, medium=3, low=5),
                ),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
        (
            "Extremely vulnerable (score floors at 0)",
            Tool(
                id="test:extreme/tool",
                name="extreme-tool",
                source=SourceType.DOCKER_HUB,
                source_url="https://example.com",
                security=Security(
                    status=SecurityStatus.VULNERABLE,
                    vulnerabilities=Vulnerabilities(critical=10, high=20, medium=50, low=100),
                ),
                scraped_at=datetime.now(timezone.utc),
            ),
        ),
    ]

    print("\n## Test Cases")
    for description, tool in test_cases:
        score = evaluator.evaluate(tool, context)
        is_blocking = get_blocking_status(tool)

        print(f"\n{description}:")
        vulns = tool.security.vulnerabilities
        print(f"  Vulnerabilities: C={vulns.critical}, H={vulns.high}, M={vulns.medium}, L={vulns.low}")
        print(f"  Score: {score:.1f}/100")
        print(f"  Blocking: {'YES' if is_blocking else 'NO'}")

    print("\n## Scoring Formula")
    print("security_score = 100 - (critical×60 + high×10 + medium×1 + low×0.5)")
    print("Minimum: 0")
    print("Unknown status: 70")
    print("\n## Blocking Logic")
    print("Any critical vulnerability → is_blocking = True")


if __name__ == "__main__":
    main()
