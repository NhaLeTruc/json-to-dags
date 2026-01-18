# ============================================================================
# Apache Airflow ETL Demo Platform - Warehouse Container
# ============================================================================
# Base: Official PostgreSQL 15 image
# Purpose: Mock data warehouse with schema and seed data
# ============================================================================

FROM postgres:15-alpine

# Set environment variables for initial database setup
ENV POSTGRES_DB=warehouse
ENV POSTGRES_USER=warehouse_user
ENV POSTGRES_PASSWORD=warehouse_pass

# Copy initialization scripts
# These run automatically on first container startup in alphabetical order
# Paths are relative to build context (project root)
# Base schema and seed data use 000x prefix to run before migrations (001_, 002_, etc.)
COPY src/warehouse/schema.sql /docker-entrypoint-initdb.d/000a-schema.sql
COPY src/warehouse/seed_data.sql /docker-entrypoint-initdb.d/000b-seed_data.sql
# Copy all migrations - new migrations will be automatically included
COPY src/warehouse/migrations/ /docker-entrypoint-initdb.d/

# Create migrations directory for future use
RUN mkdir -p /migrations

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD pg_isready -U warehouse_user -d warehouse || exit 1

# Expose PostgreSQL port
EXPOSE 5432

# Default command (inherited from base image)
CMD ["postgres"]
