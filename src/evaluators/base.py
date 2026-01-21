"""Base evaluator protocol defining the contract for all evaluators."""

from typing import Protocol

from src.models.model_stats import EvalContext
from src.models.model_tool import Tool


class BaseEvaluator(Protocol):
    """Protocol defining the evaluator contract.

    All evaluators must implement this protocol to ensure consistent behavior.
    Evaluators are pure functions that take a Tool and EvalContext and return
    a score between 0-100.

    This stateless design enables:
    - Easy testing with mock contexts
    - Parallelizable evaluation
    - Reproducible scoring
    """

    def evaluate(self, tool: Tool, context: EvalContext) -> float:
        """Evaluate tool on this dimension.

        Args:
            tool: The tool to evaluate
            context: Evaluation context containing stats and configuration

        Returns:
            Score between 0-100 for this dimension
        """
        ...


def main() -> None:
    """Demonstrate the BaseEvaluator protocol contract."""
    print("BaseEvaluator Protocol Contract")
    print("=" * 50)
    print("\nAll evaluators must implement:")
    print("  def evaluate(self, tool: Tool, context: EvalContext) -> float")
    print("\nContract guarantees:")
    print("  - Stateless (pure function)")
    print("  - Returns score 0-100")
    print("  - Same inputs always produce same outputs")
    print("  - Never queries storage directly")
    print("\nThis enables:")
    print("  ✓ Easy testing with mock contexts")
    print("  ✓ Parallelizable evaluation")
    print("  ✓ Reproducible scoring")


if __name__ == "__main__":
    main()
