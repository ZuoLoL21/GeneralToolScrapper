FROM falkordb/falkordb:latest

# Optional: copy a custom config
# COPY falkordb.conf /etc/falkordb/falkordb.conf

# Copy schema files for initialization
COPY schema/ /opt/falkordb/schema/

# Environment variables for schema initialization
ENV FALKORDB_HOST=localhost
ENV FALKORDB_PORT=6379
ENV FALKORDB_GRAPH=templates

EXPOSE 6379

# Default data directory
VOLUME ["/data"]

# Healthcheck to ensure FalkorDB is running
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
    CMD redis-cli ping | grep -q PONG || exit 1

# If using a custom config, uncomment:
# CMD ["falkordb-server", "/etc/falkordb/falkordb.conf"]

# Otherwise use image default
CMD ["falkordb-server"]
