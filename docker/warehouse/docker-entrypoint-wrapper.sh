#!/bin/bash
# ============================================================================
# Warehouse Database Docker Entrypoint Wrapper
# ============================================================================
# Purpose: Wrap PostgreSQL entrypoint to run migrations after startup
# Usage: Called as Docker entrypoint
# ============================================================================

set -e

# Configuration
MIGRATIONS_DIR="/migrations"
MIGRATION_RUNNER="/usr/local/bin/run_migrations.sh"

# Function to run migrations in background after PostgreSQL is ready
run_migrations_after_startup() {
    # Wait for PostgreSQL to be fully ready (including initdb scripts)
    sleep 5

    echo ""
    echo "============================================"
    echo "  Running Incremental Migrations"
    echo "============================================"
    echo ""

    # Set environment for psql
    export PGHOST=localhost
    export PGPORT=5432
    export PGDATABASE="${POSTGRES_DB:-warehouse}"
    export PGUSER="${POSTGRES_USER:-warehouse_user}"
    export PGPASSWORD="${POSTGRES_PASSWORD:-warehouse_pass}"
    export MIGRATIONS_DIR="$MIGRATIONS_DIR"

    # Wait for PostgreSQL to accept connections
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h localhost -U "$PGUSER" -d "$PGDATABASE" > /dev/null 2>&1; then
            echo "PostgreSQL is ready, running migrations..."
            break
        fi
        echo "Waiting for PostgreSQL... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    if [ $attempt -gt $max_attempts ]; then
        echo "ERROR: PostgreSQL failed to become ready"
        return 1
    fi

    # Run migrations
    if [ -x "$MIGRATION_RUNNER" ]; then
        "$MIGRATION_RUNNER" run
    else
        echo "WARNING: Migration runner not found or not executable: $MIGRATION_RUNNER"
    fi
}

# Start migrations in background after PostgreSQL starts
run_migrations_after_startup &

# Execute the original PostgreSQL entrypoint
exec docker-entrypoint.sh "$@"
