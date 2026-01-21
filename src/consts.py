from pathlib import Path

DEFAULT_DATA_DIR = (Path(__file__).parent.parent.resolve() / "data").absolute().resolve()

# Docker Hub namespace configuration
DOCKER_HUB_DEFAULT_NAMESPACES = ["library"]  # Official images only (~177)
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
