"""Tests for the keyword taxonomy module."""

from src.categorization.keyword_taxonomy import (
    KEYWORD_CATEGORIES,
    KEYWORD_TAXONOMY_VERSION,
    get_all_categories,
    get_all_keywords,
    get_keyword_category,
    get_keywords_by_category,
    is_valid_category,
    is_valid_keyword,
)


class TestKeywordTaxonomyStructure:
    """Tests for keyword taxonomy data structure."""

    def test_taxonomy_version_exists(self) -> None:
        assert KEYWORD_TAXONOMY_VERSION is not None
        assert isinstance(KEYWORD_TAXONOMY_VERSION, str)

    def test_taxonomy_has_categories(self) -> None:
        assert len(KEYWORD_CATEGORIES) > 0
        assert isinstance(KEYWORD_CATEGORIES, dict)

    def test_all_categories_have_keywords(self) -> None:
        for category, keywords in KEYWORD_CATEGORIES.items():
            assert isinstance(category, str)
            assert isinstance(keywords, tuple)
            assert len(keywords) > 0
            assert all(isinstance(kw, str) for kw in keywords)

    def test_expected_categories_exist(self) -> None:
        expected = [
            "platform",
            "architecture",
            "protocol",
            "optimization",
            "data",
            "persistence",
            "deployment",
            "security",
            "integration",
            "ecosystem",
            "governance",
            "maturity",
        ]
        actual = get_all_categories()
        assert len(actual) == 12, f"Expected 12 categories, got {len(actual)}"
        for cat in expected:
            assert cat in actual, f"Expected category '{cat}' not found"

    def test_keyword_count(self) -> None:
        """Test that we have approximately 100 keywords as specified."""
        all_keywords = get_all_keywords()
        # Plan specifies ~100 keywords
        assert len(all_keywords) >= 90, f"Expected ~100 keywords, got {len(all_keywords)}"
        assert len(all_keywords) <= 130, f"Expected ~100 keywords, got {len(all_keywords)}"

    def test_keywords_are_unique(self) -> None:
        """Test that keywords are unique across all categories."""
        all_keywords = get_all_keywords()
        assert len(all_keywords) == len(set(all_keywords)), "Keywords are not unique"

    def test_keywords_are_lowercase_with_hyphens(self) -> None:
        """Test that keywords follow naming convention (lowercase with hyphens)."""
        all_keywords = get_all_keywords()
        for keyword in all_keywords:
            assert keyword == keyword.lower(), f"Keyword '{keyword}' not lowercase"
            assert " " not in keyword, f"Keyword '{keyword}' contains spaces"


class TestGetAllKeywords:
    """Tests for get_all_keywords function."""

    def test_returns_list(self) -> None:
        keywords = get_all_keywords()
        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_includes_platform_keywords(self) -> None:
        keywords = get_all_keywords()
        assert "cloud-native" in keywords
        assert "web" in keywords
        assert "cli" in keywords

    def test_includes_protocol_keywords(self) -> None:
        keywords = get_all_keywords()
        assert "rest-api" in keywords
        assert "grpc" in keywords
        assert "websocket" in keywords


class TestGetAllCategories:
    """Tests for get_all_categories function."""

    def test_returns_list(self) -> None:
        categories = get_all_categories()
        assert isinstance(categories, list)
        assert len(categories) == 12

    def test_includes_expected_categories(self) -> None:
        categories = get_all_categories()
        assert "platform" in categories
        assert "architecture" in categories
        assert "protocol" in categories
        assert "security" in categories


class TestGetKeywordsByCategory:
    """Tests for get_keywords_by_category function."""

    def test_get_platform_keywords(self) -> None:
        keywords = get_keywords_by_category("platform")
        assert len(keywords) > 0
        assert "desktop" in keywords
        assert "mobile" in keywords
        assert "web" in keywords
        assert "cli" in keywords

    def test_get_architecture_keywords(self) -> None:
        keywords = get_keywords_by_category("architecture")
        assert len(keywords) > 0
        assert "distributed" in keywords
        assert "centralized" in keywords
        assert "high-throughput" in keywords

    def test_get_protocol_keywords(self) -> None:
        keywords = get_keywords_by_category("protocol")
        assert len(keywords) > 0
        assert "rest-api" in keywords
        assert "graphql" in keywords
        assert "grpc" in keywords

    def test_get_deployment_keywords(self) -> None:
        keywords = get_keywords_by_category("deployment")
        assert len(keywords) > 0
        assert "containerized" in keywords
        assert "kubernetes-native" in keywords
        assert "stateless" in keywords

    def test_get_nonexistent_category(self) -> None:
        keywords = get_keywords_by_category("nonexistent")
        assert keywords == []


class TestIsValidKeyword:
    """Tests for is_valid_keyword function."""

    def test_valid_keywords(self) -> None:
        assert is_valid_keyword("cloud-native") is True
        assert is_valid_keyword("distributed") is True
        assert is_valid_keyword("grpc") is True
        assert is_valid_keyword("containerized") is True
        assert is_valid_keyword("in-memory") is True

    def test_invalid_keywords(self) -> None:
        assert is_valid_keyword("nonexistent") is False
        assert is_valid_keyword("") is False
        assert is_valid_keyword("CLOUD-NATIVE") is False  # Case sensitive


class TestIsValidCategory:
    """Tests for is_valid_category function."""

    def test_valid_categories(self) -> None:
        assert is_valid_category("platform") is True
        assert is_valid_category("architecture") is True
        assert is_valid_category("protocol") is True
        assert is_valid_category("security") is True

    def test_invalid_categories(self) -> None:
        assert is_valid_category("nonexistent") is False
        assert is_valid_category("") is False
        assert is_valid_category("PLATFORM") is False  # Case sensitive


class TestGetKeywordCategory:
    """Tests for get_keyword_category function."""

    def test_get_category_for_platform_keyword(self) -> None:
        assert get_keyword_category("cloud-native") == "platform"
        assert get_keyword_category("cli") == "platform"
        assert get_keyword_category("web") == "platform"

    def test_get_category_for_architecture_keyword(self) -> None:
        assert get_keyword_category("distributed") == "architecture"
        assert get_keyword_category("high-throughput") == "architecture"

    def test_get_category_for_protocol_keyword(self) -> None:
        assert get_keyword_category("rest-api") == "protocol"
        assert get_keyword_category("grpc") == "protocol"
        assert get_keyword_category("websocket") == "protocol"

    def test_get_category_for_nonexistent_keyword(self) -> None:
        assert get_keyword_category("nonexistent") is None


class TestCategoryKeywordCounts:
    """Tests to verify keyword distribution across categories."""

    def test_platform_has_expected_keywords(self) -> None:
        keywords = get_keywords_by_category("platform")
        assert len(keywords) >= 8, f"Expected at least 8 platform keywords, got {len(keywords)}"

    def test_architecture_has_expected_keywords(self) -> None:
        keywords = get_keywords_by_category("architecture")
        assert (
            len(keywords) >= 8
        ), f"Expected at least 8 architecture keywords, got {len(keywords)}"

    def test_protocol_has_expected_keywords(self) -> None:
        keywords = get_keywords_by_category("protocol")
        assert len(keywords) >= 8, f"Expected at least 8 protocol keywords, got {len(keywords)}"

    def test_security_has_expected_keywords(self) -> None:
        keywords = get_keywords_by_category("security")
        assert len(keywords) >= 8, f"Expected at least 8 security keywords, got {len(keywords)}"


class TestKeywordCoverage:
    """Tests to ensure keywords cover expected properties."""

    def test_platform_coverage(self) -> None:
        """Test platform category covers expected platforms."""
        keywords = get_keywords_by_category("platform")
        expected = ["desktop", "mobile", "web", "cli", "cloud-native", "serverless"]
        for kw in expected:
            assert kw in keywords, f"Expected platform keyword '{kw}' not found"

    def test_architecture_coverage(self) -> None:
        """Test architecture category covers expected architectures."""
        keywords = get_keywords_by_category("architecture")
        expected = ["distributed", "centralized", "high-throughput", "microservices"]
        for kw in expected:
            assert kw in keywords, f"Expected architecture keyword '{kw}' not found"

    def test_protocol_coverage(self) -> None:
        """Test protocol category covers expected protocols."""
        keywords = get_keywords_by_category("protocol")
        expected = ["rest-api", "graphql", "grpc", "websocket", "http"]
        for kw in expected:
            assert kw in keywords, f"Expected protocol keyword '{kw}' not found"

    def test_deployment_coverage(self) -> None:
        """Test deployment category covers expected deployment types."""
        keywords = get_keywords_by_category("deployment")
        expected = ["containerized", "kubernetes-native", "docker", "stateless", "stateful"]
        for kw in expected:
            assert kw in keywords, f"Expected deployment keyword '{kw}' not found"

    def test_data_coverage(self) -> None:
        """Test data category covers expected data types."""
        keywords = get_keywords_by_category("data")
        expected = ["structured", "unstructured", "real-time", "streaming", "time-series"]
        for kw in expected:
            assert kw in keywords, f"Expected data keyword '{kw}' not found"

    def test_persistence_coverage(self) -> None:
        """Test persistence category covers expected persistence types."""
        keywords = get_keywords_by_category("persistence")
        expected = ["persistent", "ephemeral", "in-memory", "disk-based"]
        for kw in expected:
            assert kw in keywords, f"Expected persistence keyword '{kw}' not found"
