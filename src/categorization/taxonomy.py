"""Category taxonomy definitions for tool classification.

Defines the fixed two-level taxonomy used for classifying tools.
The LLM (in full mode) or tag-based heuristics (in MVP mode) must
select from this predefined list.
"""

from src.categorization.human_maintained import TAXONOMY
from src.models.model_classification import Category


def get_category(name: str) -> Category | None:
    """Get category by name."""
    for cat in TAXONOMY:
        if cat.name == name:
            return cat
    return None


def get_all_categories() -> list[str]:
    """Get list of all category names."""
    return [cat.name for cat in TAXONOMY]


def get_all_subcategories(category_name: str) -> list[str]:
    """Get list of all subcategory names for a category."""
    cat = get_category(category_name)
    if cat is None:
        return []
    return [sub.name for sub in cat.subcategories]


def is_valid_category(category: str) -> bool:
    """Check if category name is valid."""
    return get_category(category) is not None


def is_valid_subcategory(category: str, subcategory: str) -> bool:
    """Check if category/subcategory pair is valid."""
    cat = get_category(category)
    if cat is None:
        return False
    return cat.has_subcategory(subcategory)


def validate_classification(
    primary_category: str,
    primary_subcategory: str,
    secondary_categories: list[str] | None = None,
) -> tuple[bool, str]:
    """Validate a classification against the taxonomy.

    Args:
        primary_category: Primary category name.
        primary_subcategory: Primary subcategory name.
        secondary_categories: Optional list of secondary categories in "category/subcategory" format.

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    # Validate primary category
    if not is_valid_category(primary_category):
        return False, f"Invalid category: {primary_category}"

    # Validate primary subcategory
    if not is_valid_subcategory(primary_category, primary_subcategory):
        valid_subs = get_all_subcategories(primary_category)
        return (
            False,
            f"Invalid subcategory '{primary_subcategory}' for category '{primary_category}'. Valid: {valid_subs}",
        )

    # Validate secondary categories
    if secondary_categories:
        for sec in secondary_categories:
            if "/" not in sec:
                return False, f"Secondary category must be 'category/subcategory' format: {sec}"
            parts = sec.split("/", 1)
            if len(parts) != 2:
                return False, f"Invalid secondary category format: {sec}"
            sec_cat, sec_sub = parts
            if not is_valid_subcategory(sec_cat, sec_sub):
                return False, f"Invalid secondary category: {sec}"

    return True, ""


def main() -> None:
    """Example usage of taxonomy module."""
    print("=== Taxonomy Module Example ===\n")

    # List all categories
    print("1. All categories:")
    for cat in TAXONOMY:
        print(f"   - {cat.name}: {cat.description}")
        for sub in cat.subcategories:
            print(f"      - {sub.name}: {sub.description}")
            print(f"        Keywords: {', '.join(sub.keywords[:3])}...")
    print()

    # Validate classifications
    print("2. Validate classifications:")
    test_cases = [
        ("databases", "relational", None),
        ("databases", "invalid", None),
        ("invalid", "relational", None),
        ("databases", "relational", ["monitoring/metrics", "web/server"]),
        ("databases", "relational", ["invalid"]),
    ]

    for cat, sub, secondary in test_cases:
        is_valid, error = validate_classification(cat, sub, secondary)
        status = "VALID" if is_valid else f"INVALID: {error}"
        print(f"   ({cat}/{sub}, {secondary}) -> {status}")
    print()

    # Get category info
    print("3. Get category info:")
    cat = get_category("databases")
    if cat:
        print(f"   Category: {cat.name}")
        print(f"   Subcategories: {[s.name for s in cat.subcategories]}")
    print()

    print("Done!")


if __name__ == "__main__":
    main()
