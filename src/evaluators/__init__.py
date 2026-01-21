"""Evaluators module for scoring tools across multiple dimensions.

This module provides the scoring system for GeneralToolScraper. Tools are
evaluated on four dimensions:
- Popularity (downloads/stars normalized by category)
- Security (vulnerability severity)
- Maintenance (update recency relative to frequency)
- Trust (publisher reputation)

All evaluators are stateless pure functions that take Tool + EvalContext → score.
"""

from src.evaluators.base import BaseEvaluator
from src.evaluators.composite import analyze_score_dominance, calculate_quality_score
from src.evaluators.maintenance import MaintenanceEvaluator
from src.evaluators.popularity import PopularityEvaluator
from src.evaluators.registry import EvaluatorRegistry
from src.evaluators.security import SecurityEvaluator, get_blocking_status
from src.evaluators.stats_generator import (
    compute_category_stats,
    compute_global_stats,
    generate_all_stats,
)
from src.evaluators.trust import TrustEvaluator

__all__ = [
    # Protocol
    "BaseEvaluator",
    # Individual evaluators
    "PopularityEvaluator",
    "SecurityEvaluator",
    "MaintenanceEvaluator",
    "TrustEvaluator",
    # Orchestration
    "EvaluatorRegistry",
    # Statistics
    "compute_global_stats",
    "compute_category_stats",
    "generate_all_stats",
    # Composite scoring
    "calculate_quality_score",
    "analyze_score_dominance",
    # Utilities
    "get_blocking_status",
]