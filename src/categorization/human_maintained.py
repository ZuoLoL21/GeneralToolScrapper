"""Human-maintained categorization data.

This file contains data that should be manually curated and extended,
including known canonical names and the full taxonomy definition.
"""

from typing import Final

from src.models.model_classification import Category, Subcategory

# Known canonical names for common tools
# Used to match verified publishers to existing canonical names
KNOWN_CANONICALS: Final[dict[str, set[str]]] = {
    "postgres": {"postgresql", "pg", "postgres"},
    "mysql": {"mariadb", "mysql"},
    "redis": {"redis", "keydb", "valkey", "dragonfly"},
    "nginx": {"nginx"},
    "mongodb": {"mongo", "mongodb"},
    "elasticsearch": {"elastic", "elasticsearch", "opensearch"},
    "grafana": {"grafana"},
    "prometheus": {"prometheus"},
    "kafka": {"kafka", "redpanda"},
    "rabbitmq": {"rabbitmq", "rabbit"},
    "vault": {"vault", "hashicorp-vault"},
    "traefik": {"traefik"},
    "jenkins": {"jenkins"},
    "consul": {"consul"},
    "keycloak": {"keycloak"},
    "minio": {"minio"},
}


# Define all categories and subcategories
TAXONOMY: Final[tuple[Category, ...]] = (
    Category(
        name="databases",
        description="Data storage and retrieval systems",
        subcategories=(
            Subcategory(
                name="relational",
                description="SQL databases (postgres, mysql, mariadb)",
                keywords=(
                    "postgres",
                    "postgresql",
                    "mysql",
                    "mariadb",
                    "sql",
                    "sqlite",
                    "oracle",
                    "mssql",
                ),
            ),
            Subcategory(
                name="document",
                description="Document-oriented databases (mongodb, couchdb)",
                keywords=("mongodb", "mongo", "couchdb", "couch", "documentdb", "firestore"),
            ),
            Subcategory(
                name="key-value",
                description="Key-value stores (redis, memcached)",
                keywords=("redis", "memcached", "memcache", "keydb", "dragonfly", "valkey"),
            ),
            Subcategory(
                name="graph",
                description="Graph databases (neo4j, dgraph)",
                keywords=("neo4j", "dgraph", "arangodb", "janusgraph", "graph"),
            ),
            Subcategory(
                name="time-series",
                description="Time-series databases (influxdb, timescaledb)",
                keywords=(
                    "influxdb",
                    "influx",
                    "timescaledb",
                    "timescale",
                    "prometheus",
                    "victoriametrics",
                ),
            ),
            Subcategory(
                name="search",
                description="Search engines (elasticsearch, meilisearch)",
                keywords=(
                    "elasticsearch",
                    "elastic",
                    "opensearch",
                    "meilisearch",
                    "solr",
                    "typesense",
                    "zinc",
                ),
            ),
        ),
    ),
    Category(
        name="monitoring",
        description="Observability and monitoring tools",
        subcategories=(
            Subcategory(
                name="metrics",
                description="Metrics collection (prometheus, telegraf)",
                keywords=("prometheus", "telegraf", "statsd", "graphite", "collectd", "metrics"),
            ),
            Subcategory(
                name="logging",
                description="Log aggregation (loki, fluentd, logstash)",
                keywords=("loki", "fluentd", "fluent", "logstash", "filebeat", "vector", "syslog"),
            ),
            Subcategory(
                name="tracing",
                description="Distributed tracing (jaeger, zipkin)",
                keywords=("jaeger", "zipkin", "tempo", "tracing", "opentelemetry", "otel"),
            ),
            Subcategory(
                name="visualization",
                description="Dashboards (grafana, kibana)",
                keywords=("grafana", "kibana", "chronograf", "dashboard"),
            ),
            Subcategory(
                name="alerting",
                description="Alert management (alertmanager, pagerduty)",
                keywords=("alertmanager", "alert", "pagerduty", "opsgenie"),
            ),
        ),
    ),
    Category(
        name="web",
        description="Web servers, proxies, and load balancers",
        subcategories=(
            Subcategory(
                name="server",
                description="Web servers (nginx, apache, caddy)",
                keywords=("nginx", "apache", "httpd", "caddy", "lighttpd"),
            ),
            Subcategory(
                name="proxy",
                description="Reverse proxies (traefik, kong, envoy)",
                keywords=("traefik", "kong", "envoy", "haproxy", "proxy"),
            ),
            Subcategory(
                name="load-balancer",
                description="Load balancers (haproxy, nginx-lb)",
                keywords=("haproxy", "load-balancer", "loadbalancer", "lb"),
            ),
        ),
    ),
    Category(
        name="messaging",
        description="Message queues and event streaming",
        subcategories=(
            Subcategory(
                name="queue",
                description="Message queues (rabbitmq, activemq)",
                keywords=("rabbitmq", "rabbit", "activemq", "zeromq", "zmq", "sqs", "queue"),
            ),
            Subcategory(
                name="streaming",
                description="Event streaming (kafka, redpanda)",
                keywords=("kafka", "redpanda", "pulsar", "kinesis", "streaming"),
            ),
            Subcategory(
                name="pubsub",
                description="Pub/sub systems (nats, redis-pubsub)",
                keywords=("nats", "pubsub", "pub-sub", "mosquitto", "mqtt", "emqx"),
            ),
        ),
    ),
    Category(
        name="ci-cd",
        description="Continuous integration and deployment",
        subcategories=(
            Subcategory(
                name="build",
                description="Build systems (jenkins, drone, gitlab-runner)",
                keywords=(
                    "jenkins",
                    "drone",
                    "gitlab-runner",
                    "buildkite",
                    "circleci",
                    "concourse",
                ),
            ),
            Subcategory(
                name="deploy",
                description="Deployment tools (argocd, flux, spinnaker)",
                keywords=("argocd", "argo", "flux", "spinnaker", "deploy", "gitops"),
            ),
            Subcategory(
                name="registry",
                description="Artifact registries (harbor, nexus, artifactory)",
                keywords=("harbor", "nexus", "artifactory", "registry", "distribution"),
            ),
        ),
    ),
    Category(
        name="security",
        description="Security and access control",
        subcategories=(
            Subcategory(
                name="secrets",
                description="Secrets management (vault, sealed-secrets)",
                keywords=("vault", "sealed-secrets", "secrets", "sops", "external-secrets"),
            ),
            Subcategory(
                name="auth",
                description="Authentication (keycloak, oauth2-proxy, dex)",
                keywords=(
                    "keycloak",
                    "oauth2-proxy",
                    "oauth",
                    "dex",
                    "hydra",
                    "ory",
                    "auth",
                    "ldap",
                    "openldap",
                ),
            ),
            Subcategory(
                name="scanning",
                description="Security scanning (trivy, clair, falco)",
                keywords=("trivy", "clair", "falco", "grype", "snyk", "scanner", "vulnerability"),
            ),
        ),
    ),
    Category(
        name="storage",
        description="Data storage systems",
        subcategories=(
            Subcategory(
                name="object",
                description="Object storage (minio, seaweedfs)",
                keywords=("minio", "seaweedfs", "ceph", "s3", "object-storage"),
            ),
            Subcategory(
                name="file",
                description="File systems (nfs, glusterfs)",
                keywords=("nfs", "glusterfs", "gluster", "cephfs", "longhorn"),
            ),
            Subcategory(
                name="backup",
                description="Backup solutions (restic, velero, borg)",
                keywords=("restic", "velero", "borg", "borgbackup", "backup", "duplicati"),
            ),
        ),
    ),
    Category(
        name="networking",
        description="Network infrastructure",
        subcategories=(
            Subcategory(
                name="dns",
                description="DNS servers (coredns, pihole, bind)",
                keywords=("coredns", "pihole", "pi-hole", "bind", "dns", "unbound", "dnsmasq"),
            ),
            Subcategory(
                name="vpn",
                description="VPN solutions (wireguard, openvpn)",
                keywords=("wireguard", "openvpn", "vpn", "tailscale", "nebula"),
            ),
            Subcategory(
                name="service-mesh",
                description="Service mesh (istio, linkerd, consul)",
                keywords=("istio", "linkerd", "consul", "service-mesh", "mesh"),
            ),
        ),
    ),
    Category(
        name="runtime",
        description="Container and orchestration runtimes",
        subcategories=(
            Subcategory(
                name="container",
                description="Container runtimes (docker, containerd, podman)",
                keywords=("docker", "containerd", "podman", "cri-o", "runc"),
            ),
            Subcategory(
                name="serverless",
                description="Serverless platforms (openfaas, knative, fission)",
                keywords=("openfaas", "knative", "fission", "serverless", "faas", "lambda"),
            ),
            Subcategory(
                name="orchestration",
                description="Orchestration (kubernetes, nomad, swarm)",
                keywords=("kubernetes", "k8s", "k3s", "nomad", "swarm", "rancher"),
            ),
        ),
    ),
    Category(
        name="development",
        description="Development tools and environments",
        subcategories=(
            Subcategory(
                name="ide",
                description="Development environments (code-server, jupyter)",
                keywords=("code-server", "jupyter", "jupyterlab", "notebook", "theia", "vscode"),
            ),
            Subcategory(
                name="testing",
                description="Testing tools (selenium, playwright, cypress)",
                keywords=("selenium", "playwright", "cypress", "puppeteer", "test", "testing"),
            ),
            Subcategory(
                name="debugging",
                description="Debugging tools (delve, gdb)",
                keywords=("delve", "gdb", "debug", "debugger", "profiler"),
            ),
            Subcategory(
                name="cli",
                description="CLI tools (kubectl, aws-cli, terraform)",
                keywords=("kubectl", "aws-cli", "terraform", "helm", "cli", "command-line"),
            ),
            Subcategory(
                name="sdk",
                description="SDKs and libraries",
                keywords=("sdk", "library", "client", "boto3", "google-cloud"),
            ),
        ),
    ),
)
