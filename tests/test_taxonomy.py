"""Tests for the taxonomy module."""

from src.categorization.human_maintained import TAXONOMY
from src.categorization.taxonomy import (
    get_all_categories,
    get_all_subcategories,
    get_category,
    is_valid_category,
    is_valid_subcategory,
    validate_classification,
)
from src.models.model_classification import (
    TAXONOMY_VERSION,
    Category,
    Subcategory,
)


class TestTaxonomyStructure:
    """Tests for taxonomy data structure."""

    def test_taxonomy_version_exists(self) -> None:
        assert TAXONOMY_VERSION is not None
        assert isinstance(TAXONOMY_VERSION, str)

    def test_taxonomy_has_categories(self) -> None:
        assert len(TAXONOMY) > 0
        assert all(isinstance(cat, Category) for cat in TAXONOMY)

    def test_all_categories_have_subcategories(self) -> None:
        for category in TAXONOMY:
            assert len(category.subcategories) > 0
            assert all(isinstance(sub, Subcategory) for sub in category.subcategories)

    def test_all_subcategories_have_keywords(self) -> None:
        for category in TAXONOMY:
            for subcategory in category.subcategories:
                assert len(subcategory.keywords) > 0
                assert all(isinstance(kw, str) for kw in subcategory.keywords)

    def test_expected_categories_exist(self) -> None:
        expected = [
            "databases",
            "monitoring",
            "web",
            "messaging",
            "ci-cd",
            "security",
            "storage",
            "networking",
            "runtime",
            "development",
        ]
        actual = get_all_categories()
        for cat in expected:
            assert cat in actual, f"Expected category '{cat}' not found"

    def test_databases_has_expected_subcategories(self) -> None:
        db = get_category("databases")
        assert db is not None
        subcats = [s.name for s in db.subcategories]
        assert "relational" in subcats
        assert "document" in subcats
        assert "key-value" in subcats
        assert "graph" in subcats
        assert "time-series" in subcats
        assert "search" in subcats


class TestCategoryClass:
    """Tests for Category dataclass."""

    def test_get_subcategory_found(self) -> None:
        db = get_category("databases")
        assert db is not None
        sub = db.get_subcategory("relational")
        assert sub is not None
        assert sub.name == "relational"

    def test_get_subcategory_not_found(self) -> None:
        db = get_category("databases")
        assert db is not None
        sub = db.get_subcategory("nonexistent")
        assert sub is None

    def test_has_subcategory_true(self) -> None:
        db = get_category("databases")
        assert db is not None
        assert db.has_subcategory("relational") is True

    def test_has_subcategory_false(self) -> None:
        db = get_category("databases")
        assert db is not None
        assert db.has_subcategory("nonexistent") is False


class TestGetCategory:
    """Tests for get_category function."""

    def test_get_existing_category(self) -> None:
        cat = get_category("databases")
        assert cat is not None
        assert cat.name == "databases"

    def test_get_nonexistent_category(self) -> None:
        cat = get_category("nonexistent")
        assert cat is None

    def test_get_all_categories_returns_list(self) -> None:
        categories = get_all_categories()
        assert isinstance(categories, list)
        assert len(categories) == len(TAXONOMY)


class TestGetAllSubcategories:
    """Tests for get_all_subcategories function."""

    def test_get_subcategories_for_databases(self) -> None:
        subs = get_all_subcategories("databases")
        assert len(subs) > 0
        assert "relational" in subs

    def test_get_subcategories_for_nonexistent(self) -> None:
        subs = get_all_subcategories("nonexistent")
        assert subs == []


class TestIsValidCategory:
    """Tests for is_valid_category function."""

    def test_valid_categories(self) -> None:
        assert is_valid_category("databases") is True
        assert is_valid_category("monitoring") is True
        assert is_valid_category("web") is True
        assert is_valid_category("security") is True

    def test_invalid_categories(self) -> None:
        assert is_valid_category("nonexistent") is False
        assert is_valid_category("") is False
        assert is_valid_category("DATABASES") is False  # Case sensitive


class TestIsValidSubcategory:
    """Tests for is_valid_subcategory function."""

    def test_valid_subcategories(self) -> None:
        assert is_valid_subcategory("databases", "relational") is True
        assert is_valid_subcategory("databases", "document") is True
        assert is_valid_subcategory("monitoring", "metrics") is True
        assert is_valid_subcategory("web", "server") is True

    def test_invalid_subcategory(self) -> None:
        assert is_valid_subcategory("databases", "nonexistent") is False

    def test_subcategory_wrong_category(self) -> None:
        # "metrics" is a monitoring subcategory, not databases
        assert is_valid_subcategory("databases", "metrics") is False

    def test_invalid_category(self) -> None:
        assert is_valid_subcategory("nonexistent", "relational") is False


class TestValidateClassification:
    """Tests for validate_classification function."""

    def test_valid_primary_only(self) -> None:
        is_valid, error = validate_classification("databases", "relational")
        assert is_valid is True
        assert error == ""

    def test_valid_with_secondary(self) -> None:
        is_valid, error = validate_classification(
            "databases",
            "relational",
            ["monitoring/metrics", "web/server"],
        )
        assert is_valid is True
        assert error == ""

    def test_invalid_primary_category(self) -> None:
        is_valid, error = validate_classification("invalid", "relational")
        assert is_valid is False
        assert "Invalid category" in error

    def test_invalid_primary_subcategory(self) -> None:
        is_valid, error = validate_classification("databases", "invalid")
        assert is_valid is False
        assert "Invalid subcategory" in error

    def test_invalid_secondary_no_slash(self) -> None:
        is_valid, error = validate_classification(
            "databases",
            "relational",
            ["invalid"],
        )
        assert is_valid is False
        assert "category/subcategory" in error

    def test_invalid_secondary_bad_category(self) -> None:
        is_valid, error = validate_classification(
            "databases",
            "relational",
            ["invalid/metrics"],
        )
        assert is_valid is False
        assert "Invalid secondary category" in error

    def test_invalid_secondary_bad_subcategory(self) -> None:
        is_valid, error = validate_classification(
            "databases",
            "relational",
            ["monitoring/invalid"],
        )
        assert is_valid is False
        assert "Invalid secondary category" in error

    def test_empty_secondary_categories(self) -> None:
        is_valid, error = validate_classification("databases", "relational", [])
        assert is_valid is True


class TestKeywordCoverage:
    """Tests to ensure keywords match expected tools."""

    def test_postgres_keywords(self) -> None:
        db = get_category("databases")
        assert db is not None
        relational = db.get_subcategory("relational")
        assert relational is not None
        assert "postgres" in relational.keywords
        assert "postgresql" in relational.keywords
        assert "mysql" in relational.keywords

    def test_redis_keywords(self) -> None:
        db = get_category("databases")
        assert db is not None
        kv = db.get_subcategory("key-value")
        assert kv is not None
        assert "redis" in kv.keywords
        assert "memcached" in kv.keywords

    def test_grafana_keywords(self) -> None:
        mon = get_category("monitoring")
        assert mon is not None
        viz = mon.get_subcategory("visualization")
        assert viz is not None
        assert "grafana" in viz.keywords
        assert "kibana" in viz.keywords

    def test_nginx_keywords(self) -> None:
        web = get_category("web")
        assert web is not None
        server = web.get_subcategory("server")
        assert server is not None
        assert "nginx" in server.keywords
        assert "apache" in server.keywords

    def test_kafka_keywords(self) -> None:
        msg = get_category("messaging")
        assert msg is not None
        streaming = msg.get_subcategory("streaming")
        assert streaming is not None
        assert "kafka" in streaming.keywords
        assert "redpanda" in streaming.keywords
