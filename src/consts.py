from pathlib import Path

DEFAULT_DATA_DIR = (Path(__file__).parent.parent.resolve() / "data").absolute().resolve()

# Docker Hub namespace configuration
DOCKER_HUB_DEFAULT_NAMESPACES = ["library"]  # Official images only (~177)

# Popular/verified namespaces (curated list)
DOCKER_HUB_POPULAR_NAMESPACES = [
    "library",  # Official images
    "bitnami",  # Bitnami verified
    "ubuntu",  # Ubuntu official
    "alpine",  # Alpine official
    "mysql",  # MySQL official
    "postgres",  # PostgreSQL official
    "nginx",  # NGINX official
    "redis",  # Redis official
    "mongo",  # MongoDB official
]

# Comprehensive list of well-known Docker Hub namespaces
DOCKER_HUB_ALL_NAMESPACES = [
    # Official and verified publishers
    "library",  # Official Docker images (~177 images)
    "bitnami",  # Bitnami verified publisher
    "ubuntu",  # Ubuntu official
    "alpine",  # Alpine Linux official
    "amazonlinux",  # Amazon Linux official
    "fedora",  # Fedora official
    "centos",  # CentOS official
    "debian",  # Debian official
    "oraclelinux",  # Oracle Linux official
    # Databases
    "mysql",  # MySQL official
    "postgres",  # PostgreSQL official
    "mongo",  # MongoDB official
    "redis",  # Redis official
    "mariadb",  # MariaDB official
    "elasticsearch",  # Elasticsearch official
    "cassandra",  # Apache Cassandra official
    "couchbase",  # Couchbase official
    "influxdb",  # InfluxDB official
    "neo4j",  # Neo4j official
    # Web servers and proxies
    "nginx",  # NGINX official
    "httpd",  # Apache HTTP Server official
    "traefik",  # Traefik official
    "haproxy",  # HAProxy official
    "caddy",  # Caddy official
    # Programming languages
    "node",  # Node.js official
    "python",  # Python official
    "golang",  # Go official
    "openjdk",  # OpenJDK official
    "ruby",  # Ruby official
    "php",  # PHP official
    "rust",  # Rust official
    "dotnet",  # .NET official
    # DevOps and CI/CD
    "jenkins",  # Jenkins official
    "gitlab",  # GitLab official
    "sonarqube",  # SonarQube official
    "nexus3",  # Sonatype Nexus official
    "artifactory",  # JFrog Artifactory (may be jfrog namespace)
    # Monitoring and observability
    "grafana",  # Grafana official
    "prometheus",  # Prometheus official
    "kibana",  # Kibana official
    "logstash",  # Logstash official
    "telegraf",  # Telegraf official
    "fluentd",  # Fluentd official
    # Message queues and streaming
    "rabbitmq",  # RabbitMQ official
    "kafka",  # Apache Kafka official
    "nats",  # NATS official
    "memcached",  # Memcached official
    # Security and secrets management
    "vault",  # HashiCorp Vault official
    "consul",  # HashiCorp Consul official
    # Content management and applications
    "wordpress",  # WordPress official
    "ghost",  # Ghost official
    "drupal",  # Drupal official
    "joomla",  # Joomla official
    "nextcloud",  # Nextcloud official
    # Other popular namespaces
    "portainer",  # Portainer
    "rancher",  # Rancher
    "docker",  # Docker official tools
    "circleci",  # CircleCI
]

# Mapping of presets to namespace lists
DOCKER_HUB_NAMESPACE_PRESETS = {
    "default": DOCKER_HUB_DEFAULT_NAMESPACES,
    "popular": DOCKER_HUB_POPULAR_NAMESPACES,
    "all": DOCKER_HUB_ALL_NAMESPACES,
}

# Trivy scanner constants
TRIVY_DEFAULT_TIMEOUT = 300  # 5 minutes
TRIVY_DEFAULT_TAG = "latest"
TRIVY_STALENESS_DAYS = 7  # Re-scan after 7 days
TRIVY_CONCURRENCY = 1  # Max concurrent scans (set to 1 to avoid cache lock conflicts)
TRIVY_FAILED_SCAN_TTL = 3600  # 1 hour cache for failed scans
TRIVY_DB_WARMUP = True  # Pre-download vulnerability DB before scanning to avoid timeouts
TRIVY_DB_WARMUP_TIMEOUT = 600  # Timeout for DB warmup (10 minutes)
TRIVY_SKIP_DB_UPDATE_AFTER_WARMUP = True  # Skip DB updates after warmup to avoid cache locks
TRIVY_CACHE_DIR = DEFAULT_DATA_DIR / "cache" / "trivy"  # Project-local Trivy cache directory

# Trivy cache isolation and error handling
TRIVY_CACHE_CLEANUP_THRESHOLD_SECONDS = 600  # 10 minutes - consider locks stale after this
TRIVY_MAX_CACHE_LOCK_RETRIES = 4  # Maximum retries for cache lock errors
TRIVY_RETRY_BASE_DELAY = 1.0  # Base delay in seconds for exponential backoff
TRIVY_VERBOSE_ERRORS = True  # Set to True to see full Trivy stderr output in logs
TRIVY_USE_ISOLATED_CACHE = False  # DEPRECATED: Causes DB download failures, use global cache instead

# Manifest validation and unscannable images
DOCKER_MANIFEST_VALIDATION_ENABLED = True  # Pre-validate images before scanning
UNSCANNABLE_CACHE_TTL = 604800  # 7 days - cache for permanently unscannable images

# Docker digest constants
DOCKER_DIGEST_STALENESS_DAYS = 30  # Refetch digest after 30 days

# Images that cannot be scanned (special/reserved images)
TRIVY_UNSCANNABLE_IMAGES = [
    "docker_hub:library/scratch",  # Virtual base image, cannot be pulled
]

# Digest fetch status codes
DIGEST_FETCH_SUCCESS = "success"
DIGEST_FETCH_NO_TAGS = "no_tags"
DIGEST_FETCH_AUTH_FAILED = "auth_failed"
DIGEST_FETCH_NETWORK_ERROR = "network_error"
DIGEST_FETCH_NOT_FOUND = "not_found"
DIGEST_FETCH_FALLBACK_USED = "fallback_used"
DIGEST_FETCH_UNKNOWN_ERROR = "unknown_error"

# Tag extraction status codes
TAG_EXTRACTION_SUCCESS = "success"
TAG_EXTRACTION_NO_CATEGORIES = "no_categories_field"
TAG_EXTRACTION_EMPTY_CATEGORIES = "empty_categories"
TAG_EXTRACTION_INVALID_FORMAT = "invalid_format"
