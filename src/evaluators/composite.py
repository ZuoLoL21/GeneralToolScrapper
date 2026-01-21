"""Composite scoring functions for combining dimension scores."""

from src.models.model_eval import ScoreWeights
from src.models.model_tool import DominantDimension, ScoreAnalysis, ScoreBreakdown


def calculate_quality_score(breakdown: ScoreBreakdown, weights: ScoreWeights) -> float:
    """Calculate weighted composite quality score.

    Args:
        breakdown: Individual dimension scores (0-100 each)
        weights: Dimension weights (must sum to 1.0)

    Returns:
        Weighted composite score between 0-100
    """
    return (
        weights.popularity * breakdown.popularity
        + weights.security * breakdown.security
        + weights.maintenance * breakdown.maintenance
        + weights.trust * breakdown.trust
    )


def analyze_score_dominance(breakdown: ScoreBreakdown) -> ScoreAnalysis:
    """Analyze which dimension dominates the score.

    Determines if the score is balanced or driven primarily by one dimension.
    This helps users understand what makes a tool score high/low.

    Dominance ratio interpretation (from SCORING.md):
    - < 1.2: Balanced across dimensions
    - 1.2 - 1.5: Slight emphasis on one dimension
    - 1.5 - 2.0: Notable skew
    - > 2.0: Score dominated by single dimension

    Args:
        breakdown: Individual dimension scores

    Returns:
        ScoreAnalysis with dominant dimension and dominance ratio
    """
    # Get all dimension scores
    scores = [
        (DominantDimension.POPULARITY, breakdown.popularity),
        (DominantDimension.SECURITY, breakdown.security),
        (DominantDimension.MAINTENANCE, breakdown.maintenance),
        (DominantDimension.TRUST, breakdown.trust),
    ]

    # Sort by score descending
    sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)

    # Get highest and second-highest
    highest_dim, highest_score = sorted_scores[0]
    second_highest_score = sorted_scores[1][1]

    # Calculate dominance ratio (handle divide by zero)
    if second_highest_score == 0:
        # If second-highest is 0, either all are 0 or only one is non-zero
        if highest_score == 0:
            # All scores are 0 - call it balanced
            return ScoreAnalysis(
                dominant_dimension=DominantDimension.BALANCED,
                dominance_ratio=1.0,
            )
        else:
            # Only one dimension has score - very dominated
            return ScoreAnalysis(
                dominant_dimension=highest_dim,
                dominance_ratio=999.0,  # Effectively infinite
            )

    dominance_ratio = highest_score / second_highest_score

    # Determine if balanced or dominated
    if dominance_ratio < 1.2:
        dominant_dimension = DominantDimension.BALANCED
    else:
        dominant_dimension = highest_dim

    return ScoreAnalysis(
        dominant_dimension=dominant_dimension,
        dominance_ratio=dominance_ratio,
    )


def main() -> None:
    """Demonstrate composite scoring and dominance analysis."""
    from src.models.model_eval import ScoreWeights

    print("Composite Scoring Demo")
    print("=" * 50)

    # Test cases with different score profiles
    test_cases = [
        (
            "Balanced - All dimensions similar",
            ScoreBreakdown(popularity=85.0, security=88.0, maintenance=90.0, trust=87.0),
        ),
        (
            "Popularity-dominated - High popularity, mediocre others",
            ScoreBreakdown(popularity=95.0, security=45.0, maintenance=50.0, trust=40.0),
        ),
        (
            "Security-focused - Excellent security, low popularity",
            ScoreBreakdown(popularity=30.0, security=98.0, maintenance=85.0, trust=90.0),
        ),
        (
            "Mixed - Two dimensions high, two low",
            ScoreBreakdown(popularity=90.0, security=25.0, maintenance=88.0, trust=30.0),
        ),
        (
            "All low - Poor across the board",
            ScoreBreakdown(popularity=20.0, security=15.0, maintenance=18.0, trust=22.0),
        ),
        (
            "Single dimension (edge case)",
            ScoreBreakdown(popularity=85.0, security=0.0, maintenance=0.0, trust=0.0),
        ),
    ]

    # Use default weights
    weights = ScoreWeights()

    print("\n## Default Weights")
    print(f"  Popularity:  {weights.popularity:.2f}")
    print(f"  Security:    {weights.security:.2f}")
    print(f"  Maintenance: {weights.maintenance:.2f}")
    print(f"  Trust:       {weights.trust:.2f}")

    print("\n## Test Cases")
    for description, breakdown in test_cases:
        quality_score = calculate_quality_score(breakdown, weights)
        analysis = analyze_score_dominance(breakdown)

        print(f"\n{description}:")
        print(f"  Breakdown: P={breakdown.popularity:.0f}, S={breakdown.security:.0f}, "
              f"M={breakdown.maintenance:.0f}, T={breakdown.trust:.0f}")
        print(f"  Quality Score: {quality_score:.1f}/100")
        print(f"  Dominant Dimension: {analysis.dominant_dimension.value}")
        print(f"  Dominance Ratio: {analysis.dominance_ratio:.2f}")

        # Interpret dominance
        if analysis.dominance_ratio < 1.2:
            interpretation = "Balanced"
        elif analysis.dominance_ratio < 1.5:
            interpretation = "Slight emphasis"
        elif analysis.dominance_ratio < 2.0:
            interpretation = "Notable skew"
        else:
            interpretation = "Dominated by single dimension"
        print(f"  Interpretation: {interpretation}")

    print("\n## Dominance Ratio Guide")
    print("  < 1.2:       Balanced across dimensions")
    print("  1.2 - 1.5:   Slight emphasis on one dimension")
    print("  1.5 - 2.0:   Notable skew")
    print("  > 2.0:       Dominated by single dimension")


if __name__ == "__main__":
    main()
