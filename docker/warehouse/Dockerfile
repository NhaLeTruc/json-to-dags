# ============================================================================
# Apache Airflow ETL Demo Platform - Warehouse Container
# ============================================================================
# Base: Official PostgreSQL 15 image
# Purpose: Mock data warehouse with schema and seed data
# Features: Incremental migration support on container restart
# ============================================================================

FROM postgres:15-alpine

# Set environment variables for initial database setup
ENV POSTGRES_DB=warehouse
ENV POSTGRES_USER=warehouse_user
ENV POSTGRES_PASSWORD=warehouse_pass

# Copy initialization scripts
# These run automatically on FIRST container startup only (when data volume is empty)
# Order: alphabetical by filename
# - 000a-schema.sql: Base warehouse schema (dimensions, facts, migrations table)
# - 000b-seed_data.sql: Initial seed data
COPY src/warehouse/schema.sql /docker-entrypoint-initdb.d/000a-schema.sql
COPY src/warehouse/seed_data.sql /docker-entrypoint-initdb.d/000b-seed_data.sql

# Copy migrations to a separate directory for incremental application
# These are applied by run_migrations.sh on EVERY container startup
COPY src/warehouse/migrations/ /migrations/

# Copy migration runner scripts
COPY docker/warehouse/run_migrations.sh /usr/local/bin/run_migrations.sh
COPY docker/warehouse/docker-entrypoint-wrapper.sh /usr/local/bin/docker-entrypoint-wrapper.sh
RUN chmod +x /usr/local/bin/run_migrations.sh /usr/local/bin/docker-entrypoint-wrapper.sh

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD pg_isready -U warehouse_user -d warehouse || exit 1

# Expose PostgreSQL port
EXPOSE 5432

# Use wrapper entrypoint that runs migrations after PostgreSQL starts
ENTRYPOINT ["/usr/local/bin/docker-entrypoint-wrapper.sh"]

# Default command (inherited from base image)
CMD ["postgres"]
