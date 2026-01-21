"""Human-maintained categorization data.

This file contains data that should be manually curated and extended,
including known canonical names and the full taxonomy definition.
"""

from typing import Final

from src.models.model_classification import Category, Subcategory

# Known canonical names for common tools
# Used to match verified publishers to existing canonical names
KNOWN_CANONICALS: Final[dict[str, set[str]]] = {
    # Infrastructure and databases
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
    "rethinkdb": {"rethinkdb"},
    "aerospike": {"aerospike"},
    # Programming languages
    "node": {"node", "nodejs"},
    "python": {"python", "python3"},
    "ruby": {"ruby", "jruby"},
    "java": {"java", "openjdk", "jdk"},
    "golang": {"go", "golang"},
    "php": {"php", "php-fpm"},
    # Operating systems
    "ubuntu": {"ubuntu"},
    "centos": {"centos", "almalinux", "rockylinux"},
    "alpine": {"alpine"},
    "debian": {"debian"},
    # CMS and content
    "wordpress": {"wordpress", "wp"},
    "drupal": {"drupal"},
    "ghost": {"ghost"},
    # Application servers
    "jetty": {"jetty"},
    "tomcat": {"tomcat"},
    "glassfish": {"glassfish", "payara"},
    "liberty": {"websphere-liberty", "open-liberty"},
    # Build tools
    "gradle": {"gradle"},
    "maven": {"maven"},
    # Business apps
    "odoo": {"odoo"},
    "redmine": {"redmine"},
    # Communication
    "rocketchat": {"rocket.chat", "rocketchat"},
    "teamspeak": {"teamspeak", "ts3"},
    # Web tools
    "varnish": {"varnish"},
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
            Subcategory(
                name="admin",
                description="Database administration (adminer)",
                keywords=(
                    "adminer",
                    "phpmyadmin",
                    "pgadmin",
                    "dbeaver",
                    "admin",
                    "database-admin",
                    "gui",
                    "management",
                ),
            ),
            Subcategory(
                name="migration",
                description="Database migration (liquibase)",
                keywords=(
                    "liquibase",
                    "flyway",
                    "alembic",
                    "migration",
                    "schema",
                    "versioning",
                    "changeset",
                ),
            ),
            Subcategory(
                name="nosql",
                description="Other NoSQL databases (rethinkdb, aerospike)",
                keywords=(
                    "rethinkdb",
                    "aerospike",
                    "cassandra",
                    "couchbase",
                    "nosql",
                    "distributed",
                    "column-store",
                    "wide-column",
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
            Subcategory(
                name="analytics",
                description="Web analytics (matomo)",
                keywords=(
                    "matomo",
                    "piwik",
                    "plausible",
                    "analytics",
                    "tracking",
                    "web-analytics",
                    "stats",
                    "visitors",
                ),
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
            Subcategory(
                name="application-server",
                description="Application servers (jetty, glassfish, websphere-liberty, open-liberty)",
                keywords=(
                    "jetty",
                    "tomcat",
                    "glassfish",
                    "wildfly",
                    "jboss",
                    "websphere",
                    "liberty",
                    "open-liberty",
                    "payara",
                    "application-server",
                    "servlet",
                    "j2ee",
                    "jakarta",
                ),
            ),
            Subcategory(
                name="cache",
                description="Web caching (varnish)",
                keywords=(
                    "varnish",
                    "squid",
                    "nginx-cache",
                    "cache",
                    "http-cache",
                    "cdn",
                    "acceleration",
                    "reverse-proxy-cache",
                ),
            ),
            Subcategory(
                name="utilities",
                description="Web utilities (yourls)",
                keywords=("yourls", "url-shortener", "link", "redirect", "utilities", "web-tools"),
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
            Subcategory(
                name="api-gateway",
                description="API gateways (krakend, api-firewall)",
                keywords=(
                    "krakend",
                    "kong",
                    "tyk",
                    "api-gateway",
                    "gateway",
                    "api-management",
                    "rate-limiting",
                    "api",
                    "rest-api",
                ),
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
            Subcategory(
                name="build-tools",
                description="Build and package management (gradle, composer, buildpack-deps, gcc)",
                keywords=(
                    "gradle",
                    "maven",
                    "ant",
                    "make",
                    "cmake",
                    "composer",
                    "npm",
                    "yarn",
                    "pip",
                    "cargo",
                    "buildpack-deps",
                    "build",
                    "compile",
                    "package",
                ),
            ),
            Subcategory(
                name="quality",
                description="Code quality and analysis (sonarqube)",
                keywords=(
                    "sonarqube",
                    "sonar",
                    "eslint",
                    "prettier",
                    "lint",
                    "quality",
                    "static-analysis",
                    "code-review",
                    "coverage",
                    "checkstyle",
                    "pmd",
                    "spotbugs",
                ),
            ),
        ),
    ),
    Category(
        name="base-images",
        description="Base operating system images for container builds",
        subcategories=(
            Subcategory(
                name="linux",
                description="Linux distributions (ubuntu, centos, debian, alpine, etc.)",
                keywords=(
                    "ubuntu",
                    "debian",
                    "alpine",
                    "centos",
                    "fedora",
                    "rhel",
                    "amazonlinux",
                    "almalinux",
                    "rockylinux",
                    "busybox",
                    "photon",
                    "opensuse",
                    "mageia",
                    "alt",
                    "euleros",
                    "sl",
                    "clefos",
                    "linux",
                    "distro",
                    "base-image",
                ),
            ),
            Subcategory(
                name="minimal",
                description="Minimal/scratch images (scratch, distroless, cirros)",
                keywords=(
                    "scratch",
                    "distroless",
                    "minimal",
                    "tiny",
                    "micro",
                    "cirros",
                    "empty",
                    "base",
                ),
            ),
        ),
    ),
    Category(
        name="languages",
        description="Programming language runtimes and interpreters",
        subcategories=(
            Subcategory(
                name="compiled",
                description="Compiled languages (java, golang, rust, gcc, swift, haskell)",
                keywords=(
                    "java",
                    "openjdk",
                    "jdk",
                    "jre",
                    "golang",
                    "go",
                    "rust",
                    "cargo",
                    "gcc",
                    "g++",
                    "c",
                    "cpp",
                    "swift",
                    "haskell",
                    "ghc",
                ),
            ),
            Subcategory(
                name="interpreted",
                description="Interpreted languages (python, node, ruby, php, perl, bash)",
                keywords=(
                    "python",
                    "python3",
                    "pip",
                    "node",
                    "nodejs",
                    "npm",
                    "ruby",
                    "gem",
                    "bundler",
                    "php",
                    "composer-pkg",
                    "perl",
                    "cpan",
                    "bash",
                    "shell",
                    "sh",
                ),
            ),
            Subcategory(
                name="functional",
                description="Functional languages (haskell, clojure, elixir, erlang, etc.)",
                keywords=(
                    "haskell",
                    "ghc",
                    "clojure",
                    "leiningen",
                    "elixir",
                    "mix",
                    "erlang",
                    "beam",
                    "scala",
                    "sbt",
                    "ocaml",
                    "swipl",
                    "prolog",
                    "rakudo",
                    "raku",
                    "perl6",
                ),
            ),
            Subcategory(
                name="jvm",
                description="JVM-based languages (java, scala, clojure, jruby)",
                keywords=(
                    "jvm",
                    "java",
                    "openjdk",
                    "scala",
                    "clojure",
                    "jruby",
                    "kotlin",
                    "groovy",
                ),
            ),
            Subcategory(
                name="scientific",
                description="Scientific computing (julia, pypy, r)",
                keywords=(
                    "julia",
                    "jupyter",
                    "pypy",
                    "numpy",
                    "scipy",
                    "r",
                    "rstudio",
                    "matlab",
                    "octave",
                ),
            ),
            Subcategory(
                name="alternative",
                description="Alternative/specialized runtimes (haxe, lua)",
                keywords=("haxe", "lua", "dart", "crystal", "nim", "zig"),
            ),
        ),
    ),
    Category(
        name="content",
        description="Content management and publishing platforms",
        subcategories=(
            Subcategory(
                name="cms",
                description="Content management systems (wordpress, drupal, joomla, ghost)",
                keywords=(
                    "wordpress",
                    "wp",
                    "drupal",
                    "joomla",
                    "cms",
                    "content-management",
                    "ghost",
                    "wagtail",
                    "strapi",
                    "contentful",
                    "directus",
                ),
            ),
            Subcategory(
                name="wiki",
                description="Wiki platforms (mediawiki, xwiki)",
                keywords=(
                    "wiki",
                    "mediawiki",
                    "xwiki",
                    "confluence",
                    "dokuwiki",
                    "bookstack",
                    "knowledge-base",
                    "documentation",
                ),
            ),
            Subcategory(
                name="blog",
                description="Blogging platforms (ghost)",
                keywords=(
                    "blog",
                    "ghost",
                    "hexo",
                    "hugo",
                    "jekyll",
                    "gatsby",
                    "publishing",
                    "medium",
                ),
            ),
            Subcategory(
                name="collaboration",
                description="File sharing (owncloud, plone)",
                keywords=(
                    "owncloud",
                    "nextcloud",
                    "plone",
                    "seafile",
                    "collaboration",
                    "file-sharing",
                    "sync",
                    "groupware",
                ),
            ),
            Subcategory(
                name="community",
                description="Community platforms (backdrop, known, friendica)",
                keywords=(
                    "backdrop",
                    "known",
                    "friendica",
                    "discourse",
                    "flarum",
                    "community",
                    "forum",
                    "social",
                ),
            ),
        ),
    ),
    Category(
        name="business",
        description="Business and enterprise applications",
        subcategories=(
            Subcategory(
                name="erp",
                description="Enterprise resource planning (odoo)",
                keywords=(
                    "odoo",
                    "erpnext",
                    "erp",
                    "enterprise",
                    "accounting",
                    "inventory",
                    "manufacturing",
                ),
            ),
            Subcategory(
                name="bpm",
                description="Business process management (bonita)",
                keywords=(
                    "bonita",
                    "camunda",
                    "activiti",
                    "bpm",
                    "bpmn",
                    "workflow",
                    "process",
                    "automation",
                ),
            ),
            Subcategory(
                name="crm",
                description="Customer relationship management (monica)",
                keywords=(
                    "monica",
                    "suitecrm",
                    "crm",
                    "customer",
                    "contact",
                    "sales",
                    "relationship",
                ),
            ),
            Subcategory(
                name="project",
                description="Project management (redmine)",
                keywords=(
                    "redmine",
                    "taiga",
                    "openproject",
                    "project",
                    "issue-tracking",
                    "task",
                    "scrum",
                    "agile",
                ),
            ),
            Subcategory(
                name="document",
                description="Document management (nuxeo, silverpeas)",
                keywords=(
                    "nuxeo",
                    "alfresco",
                    "silverpeas",
                    "document",
                    "ecm",
                    "dam",
                    "content-repository",
                    "archive",
                ),
            ),
            Subcategory(
                name="integration",
                description="Business integration platforms (convertigo)",
                keywords=(
                    "convertigo",
                    "talend",
                    "mulesoft",
                    "integration",
                    "etl",
                    "esb",
                    "connector",
                    "low-code",
                ),
            ),
            Subcategory(
                name="gis",
                description="Geographic information systems (geonetwork)",
                keywords=(
                    "geonetwork",
                    "geoserver",
                    "mapserver",
                    "gis",
                    "geospatial",
                    "mapping",
                    "geo",
                    "spatial",
                ),
            ),
        ),
    ),
    Category(
        name="communication",
        description="Communication and collaboration tools",
        subcategories=(
            Subcategory(
                name="chat",
                description="Team chat and messaging (rocket.chat, znc)",
                keywords=(
                    "rocket.chat",
                    "rocketchat",
                    "mattermost",
                    "slack",
                    "chat",
                    "messaging",
                    "team",
                    "collaboration",
                    "irc",
                    "znc",
                ),
            ),
            Subcategory(
                name="voice",
                description="Voice/video communication (teamspeak)",
                keywords=(
                    "teamspeak",
                    "mumble",
                    "jitsi",
                    "voice",
                    "voip",
                    "video",
                    "conference",
                    "webrtc",
                ),
            ),
            Subcategory(
                name="email",
                description="Email servers and management (postfixadmin)",
                keywords=(
                    "postfixadmin",
                    "postfix",
                    "mailcow",
                    "email",
                    "mail",
                    "smtp",
                    "imap",
                    "webmail",
                ),
            ),
        ),
    ),
)


def main() -> None:
    """Example usage of human-maintained categorization data."""
    print("=== Human-Maintained Taxonomy Module Example ===\n")

    # Show taxonomy overview
    print("1. Taxonomy overview:")
    total_subcategories = 0
    for category in TAXONOMY:
        subcats = len(category.subcategories)
        total_subcategories += subcats
        print(f"   - {category.name}: {subcats} subcategories")
        print(f"      {category.description}")
    print(f"\n   Total categories: {len(TAXONOMY)}")
    print(f"   Total subcategories: {total_subcategories}\n")

    # Show new categories
    print("2. New categories added:")
    new_categories = ["base-images", "languages", "content", "business", "communication"]
    for cat_name in new_categories:
        cat = next((c for c in TAXONOMY if c.name == cat_name), None)
        if cat:
            print(f"   - {cat_name}:")
            for subcat in cat.subcategories:
                print(f"      * {subcat.name}: {subcat.description}")
    print()

    # Show canonical mappings
    print("3. Canonical name mappings:")
    print(f"   Total canonical groups: {len(KNOWN_CANONICALS)}")
    print("   Examples:")
    examples = [
        ("node", "Programming language"),
        ("centos", "OS (RHEL-compatible)"),
        ("wordpress", "CMS"),
        ("rocketchat", "Communication"),
    ]
    for canonical, description in examples:
        if canonical in KNOWN_CANONICALS:
            variants = KNOWN_CANONICALS[canonical]
            print(f"   - {canonical} ({description}): {', '.join(sorted(variants))}")
    print()

    # Test subcategory lookup
    print("4. Test subcategory lookup:")
    test_lookups = [
        ("languages", "interpreted"),
        ("content", "cms"),
        ("business", "erp"),
        ("web", "application-server"),
    ]
    for cat_name, subcat_name in test_lookups:
        cat = next((c for c in TAXONOMY if c.name == cat_name), None)
        if cat:
            subcat = cat.get_subcategory(subcat_name)
            if subcat:
                keywords_preview = ", ".join(subcat.keywords[:5])
                print(f"   {cat_name}/{subcat_name}: {keywords_preview}...")
            else:
                print(f"   {cat_name}/{subcat_name}: NOT FOUND")
        else:
            print(f"   {cat_name}: CATEGORY NOT FOUND")
    print()

    print("Done!")


if __name__ == "__main__":
    main()
