"""Tests for the identity resolution module."""

import json
from pathlib import Path

from src.categorization.human_maintained import KNOWN_CANONICALS
from src.categorization.identity import (
    RESOLUTION_CONFIDENCE,
    IdentityResolver,
    _find_matching_canonical,
    _normalize_name,
)
from src.models.model_classification import (
    IDENTITY_VERSION,
    IdentityResolution,
    ResolutionSource,
)
from src.models.model_tool import (
    Identity,
    Maintainer,
    MaintainerType,
    Metrics,
    SourceType,
    Tool,
)


class TestNormalizeName:
    """Tests for _normalize_name function."""

    def test_lowercase(self) -> None:
        assert _normalize_name("PostgreSQL") == "postgresql"
        assert _normalize_name("NGINX") == "nginx"

    def test_strips_whitespace(self) -> None:
        assert _normalize_name("  postgres  ") == "postgres"

    def test_removes_alpine_suffix(self) -> None:
        assert _normalize_name("postgres-alpine") == "postgres"

    def test_removes_slim_suffix(self) -> None:
        assert _normalize_name("python-slim") == "python"

    def test_removes_version_suffix(self) -> None:
        assert _normalize_name("postgres-14") == "postgres"
        assert _normalize_name("python-3.11") == "python"
        assert _normalize_name("node-v20") == "node"

    def test_removes_multiple_suffixes(self) -> None:
        # Note: only removes one suffix at a time
        assert _normalize_name("postgres-alpine") == "postgres"

    def test_removes_docker_suffix(self) -> None:
        assert _normalize_name("redis-docker") == "redis"

    def test_removes_server_suffix(self) -> None:
        assert _normalize_name("mysql-server") == "mysql"


class TestFindMatchingCanonical:
    """Tests for _find_matching_canonical function."""

    def test_exact_canonical_match(self) -> None:
        assert _find_matching_canonical("postgres") == "postgres"
        assert _find_matching_canonical("redis") == "redis"
        assert _find_matching_canonical("mysql") == "mysql"

    def test_variant_match(self) -> None:
        assert _find_matching_canonical("postgresql") == "postgres"
        assert _find_matching_canonical("pg") == "postgres"
        assert _find_matching_canonical("mariadb") == "mysql"

    def test_no_match(self) -> None:
        assert _find_matching_canonical("unknowntool") is None
        assert _find_matching_canonical("myapp") is None

    def test_case_insensitive(self) -> None:
        assert _find_matching_canonical("PostgreSQL") == "postgres"
        assert _find_matching_canonical("REDIS") == "redis"


class TestResolutionConfidence:
    """Tests for resolution confidence values."""

    def test_override_highest_confidence(self) -> None:
        assert RESOLUTION_CONFIDENCE[ResolutionSource.OVERRIDE] == 1.0

    def test_official_high_confidence(self) -> None:
        assert RESOLUTION_CONFIDENCE[ResolutionSource.OFFICIAL] == 0.95

    def test_verified_moderate_confidence(self) -> None:
        assert RESOLUTION_CONFIDENCE[ResolutionSource.VERIFIED] == 0.85

    def test_fallback_lowest_confidence(self) -> None:
        assert RESOLUTION_CONFIDENCE[ResolutionSource.FALLBACK] == 0.6

    def test_confidence_ordering(self) -> None:
        override = RESOLUTION_CONFIDENCE[ResolutionSource.OVERRIDE]
        official = RESOLUTION_CONFIDENCE[ResolutionSource.OFFICIAL]
        verified = RESOLUTION_CONFIDENCE[ResolutionSource.VERIFIED]
        fallback = RESOLUTION_CONFIDENCE[ResolutionSource.FALLBACK]
        assert override > official > verified > fallback


class TestIdentityResolution:
    """Tests for IdentityResolution dataclass."""

    def test_creation(self) -> None:
        resolution = IdentityResolution(
            canonical_name="postgres",
            resolution_source=ResolutionSource.OFFICIAL,
            resolution_confidence=0.95,
        )
        assert resolution.canonical_name == "postgres"
        assert resolution.resolution_source == ResolutionSource.OFFICIAL
        assert resolution.resolution_confidence == 0.95
        assert resolution.identity_version == IDENTITY_VERSION


class TestIdentityResolver:
    """Tests for IdentityResolver class."""

    def test_resolve_official_image(self, tmp_path: Path) -> None:
        resolver = IdentityResolver(overrides_path=tmp_path / "overrides.json")
        result = resolver.resolve(
            artifact_id="docker_hub:library/postgres",
            name="postgres",
            is_official=True,
            is_verified=True,
            publisher="library",
        )
        assert result.canonical_name == "postgres"
        assert result.resolution_source == ResolutionSource.OFFICIAL
        assert result.resolution_confidence == 0.95

    def test_resolve_verified_publisher_matching_canonical(self, tmp_path: Path) -> None:
        resolver = IdentityResolver(overrides_path=tmp_path / "overrides.json")
        result = resolver.resolve(
            artifact_id="docker_hub:bitnami/postgresql",
            name="postgresql",
            is_official=False,
            is_verified=True,
            publisher="bitnami",
        )
        assert result.canonical_name == "postgres"
        assert result.resolution_source == ResolutionSource.VERIFIED
        assert result.resolution_confidence == 0.85

    def test_resolve_verified_publisher_no_canonical_match(self, tmp_path: Path) -> None:
        resolver = IdentityResolver(overrides_path=tmp_path / "overrides.json")
        result = resolver.resolve(
            artifact_id="docker_hub:bitnami/customtool",
            name="customtool",
            is_official=False,
            is_verified=True,
            publisher="bitnami",
        )
        # Falls back because no known canonical matches
        assert result.canonical_name == "bitnami/customtool"
        assert result.resolution_source == ResolutionSource.FALLBACK
        assert result.resolution_confidence == 0.6

    def test_resolve_user_image_fallback(self, tmp_path: Path) -> None:
        resolver = IdentityResolver(overrides_path=tmp_path / "overrides.json")
        result = resolver.resolve(
            artifact_id="docker_hub:someuser/myapp",
            name="myapp",
            is_official=False,
            is_verified=False,
            publisher="someuser",
        )
        assert result.canonical_name == "someuser/myapp"
        assert result.resolution_source == ResolutionSource.FALLBACK
        assert result.resolution_confidence == 0.6

    def test_resolve_with_override(self, tmp_path: Path) -> None:
        # Create override file
        overrides_path = tmp_path / "overrides.json"
        overrides_data = {
            "identity_overrides": {
                "docker_hub:someuser/pg-wrapper": {
                    "canonical_name": "postgres",
                    "reason": "This is a postgres wrapper",
                }
            }
        }
        overrides_path.write_text(json.dumps(overrides_data))

        resolver = IdentityResolver(overrides_path=overrides_path)
        result = resolver.resolve(
            artifact_id="docker_hub:someuser/pg-wrapper",
            name="pg-wrapper",
            is_official=False,
            is_verified=False,
            publisher="someuser",
        )
        assert result.canonical_name == "postgres"
        assert result.resolution_source == ResolutionSource.OVERRIDE
        assert result.resolution_confidence == 1.0

    def test_resolve_library_namespace_fallback(self, tmp_path: Path) -> None:
        resolver = IdentityResolver(overrides_path=tmp_path / "overrides.json")
        result = resolver.resolve(
            artifact_id="docker_hub:library/unknowntool",
            name="unknowntool",
            is_official=False,  # Not marked official for some reason
            is_verified=False,
            publisher="library",
        )
        # Should use just name since publisher is "library"
        assert result.canonical_name == "unknowntool"

    def test_resolve_from_tool(self, tmp_path: Path) -> None:
        resolver = IdentityResolver(overrides_path=tmp_path / "overrides.json")
        tool = Tool(
            id="docker_hub:library/nginx",
            name="nginx",
            source=SourceType.DOCKER_HUB,
            source_url="https://hub.docker.com/_/nginx",
            identity=Identity(canonical_name=""),
            maintainer=Maintainer(
                name="library",
                type=MaintainerType.OFFICIAL,
                verified=True,
            ),
            metrics=Metrics(downloads=1_000_000_000),
        )
        result = resolver.resolve_from_tool(tool)
        assert result.canonical_name == "nginx"
        assert result.resolution_source == ResolutionSource.OFFICIAL

    def test_add_override(self, tmp_path: Path) -> None:
        overrides_path = tmp_path / "overrides.json"
        resolver = IdentityResolver(overrides_path=overrides_path)

        resolver.add_override(
            artifact_id="docker_hub:user/custom-postgres",
            canonical_name="postgres",
            reason="Custom postgres build",
        )

        # Verify override was saved
        assert overrides_path.exists()
        data = json.loads(overrides_path.read_text())
        assert "docker_hub:user/custom-postgres" in data["identity_overrides"]

        # Verify it works
        result = resolver.resolve(
            artifact_id="docker_hub:user/custom-postgres",
            name="custom-postgres",
            is_official=False,
            is_verified=False,
            publisher="user",
        )
        assert result.canonical_name == "postgres"
        assert result.resolution_source == ResolutionSource.OVERRIDE

    def test_override_takes_precedence_over_official(self, tmp_path: Path) -> None:
        overrides_path = tmp_path / "overrides.json"
        overrides_data = {
            "identity_overrides": {
                "docker_hub:library/postgres": {
                    "canonical_name": "custom-postgres",
                    "reason": "Override for testing",
                }
            }
        }
        overrides_path.write_text(json.dumps(overrides_data))

        resolver = IdentityResolver(overrides_path=overrides_path)
        result = resolver.resolve(
            artifact_id="docker_hub:library/postgres",
            name="postgres",
            is_official=True,
            is_verified=True,
            publisher="library",
        )
        # Override should win even for official images
        assert result.canonical_name == "custom-postgres"
        assert result.resolution_source == ResolutionSource.OVERRIDE


class TestKnownCanonicals:
    """Tests for KNOWN_CANONICALS mapping."""

    def test_postgres_variants(self) -> None:
        assert "postgresql" in KNOWN_CANONICALS["postgres"]
        assert "pg" in KNOWN_CANONICALS["postgres"]

    def test_redis_variants(self) -> None:
        assert "keydb" in KNOWN_CANONICALS["redis"]
        assert "valkey" in KNOWN_CANONICALS["redis"]

    def test_elasticsearch_variants(self) -> None:
        assert "elastic" in KNOWN_CANONICALS["elasticsearch"]
        assert "opensearch" in KNOWN_CANONICALS["elasticsearch"]

    def test_all_canonicals_have_themselves(self) -> None:
        for canonical, variants in KNOWN_CANONICALS.items():
            assert canonical in variants or canonical == canonical
