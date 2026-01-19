#!/bin/bash
# ============================================================================
# Warehouse Database Migration Runner
# ============================================================================
# Purpose: Apply database migrations incrementally on container startup
# Usage: Called automatically by Docker entrypoint or manually
# ============================================================================

set -e

# Configuration
MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-warehouse}"
PGUSER="${PGUSER:-warehouse_user}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Wait for PostgreSQL to be ready
wait_for_postgres() {
    local max_attempts=30
    local attempt=1

    log_info "Waiting for PostgreSQL to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" > /dev/null 2>&1; then
            log_success "PostgreSQL is ready!"
            return 0
        fi

        echo "  Attempt $attempt/$max_attempts: PostgreSQL not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL failed to become ready after $max_attempts attempts"
    return 1
}

# Check if schema_migrations table exists
ensure_migrations_table() {
    log_info "Ensuring schema_migrations table exists..."

    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -q -c "
        CREATE TABLE IF NOT EXISTS warehouse.schema_migrations (
            migration_id SERIAL PRIMARY KEY,
            migration_name VARCHAR(255) NOT NULL UNIQUE,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            description TEXT,
            checksum VARCHAR(64)
        );
    " 2>/dev/null || {
        # If warehouse schema doesn't exist yet, that's OK - base schema will create it
        log_warning "warehouse schema not ready yet, will retry after base schema"
        return 1
    }

    return 0
}

# Check if a migration has been applied
is_migration_applied() {
    local migration_name="$1"

    local result
    result=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -q -c "
        SELECT COUNT(*) FROM warehouse.schema_migrations
        WHERE migration_name = '$migration_name';
    " 2>/dev/null | tr -d ' ')

    [ "$result" = "1" ]
}

# Record a migration as applied
record_migration() {
    local migration_name="$1"
    local checksum="$2"
    local description="$3"

    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -q -c "
        INSERT INTO warehouse.schema_migrations (migration_name, checksum, description)
        VALUES ('$migration_name', '$checksum', '$description')
        ON CONFLICT (migration_name) DO UPDATE SET
            applied_at = CURRENT_TIMESTAMP,
            checksum = EXCLUDED.checksum;
    "
}

# Calculate checksum for a migration file
get_file_checksum() {
    local file="$1"
    md5sum "$file" 2>/dev/null | cut -d' ' -f1 || echo "unknown"
}

# Apply a single migration
apply_migration() {
    local migration_file="$1"
    local migration_name
    migration_name=$(basename "$migration_file" .sql)
    local checksum
    checksum=$(get_file_checksum "$migration_file")

    log_info "Applying migration: $migration_name"

    if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$migration_file" 2>&1; then
        record_migration "$migration_name" "$checksum" "Applied by migration runner"
        log_success "Migration $migration_name applied successfully"
        return 0
    else
        log_error "Migration $migration_name failed!"
        return 1
    fi
}

# Main migration runner
run_migrations() {
    echo ""
    echo "============================================"
    echo "  Warehouse Database Migration Runner"
    echo "============================================"
    echo ""

    # Check if migrations directory exists
    if [ ! -d "$MIGRATIONS_DIR" ]; then
        log_warning "Migrations directory not found: $MIGRATIONS_DIR"
        return 0
    fi

    # Wait for PostgreSQL
    wait_for_postgres || return 1

    # Ensure migrations table exists (may fail if base schema not ready)
    ensure_migrations_table || {
        log_info "Will create migrations table after base schema is applied"
    }

    # Get list of migration files (sorted numerically by prefix)
    local migration_files
    migration_files=$(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.sql" -type f | sort -V)

    if [ -z "$migration_files" ]; then
        log_info "No migration files found in $MIGRATIONS_DIR"
        return 0
    fi

    local applied_count=0
    local skipped_count=0
    local failed_count=0

    log_info "Found migration files in $MIGRATIONS_DIR"
    echo ""

    for migration_file in $migration_files; do
        local migration_name
        migration_name=$(basename "$migration_file" .sql)

        # Skip README and other non-migration files
        if [[ "$migration_name" == "README" ]] || [[ ! "$migration_name" =~ ^[0-9] ]]; then
            continue
        fi

        # Check if migration is already applied
        if is_migration_applied "$migration_name"; then
            echo "  [SKIP] $migration_name (already applied)"
            skipped_count=$((skipped_count + 1))
        else
            echo "  [APPLY] $migration_name"
            if apply_migration "$migration_file"; then
                applied_count=$((applied_count + 1))
            else
                failed_count=$((failed_count + 1))
                log_error "Stopping migrations due to failure"
                break
            fi
        fi
    done

    echo ""
    echo "============================================"
    echo "  Migration Summary"
    echo "============================================"
    echo "  Applied: $applied_count"
    echo "  Skipped: $skipped_count"
    echo "  Failed:  $failed_count"
    echo "============================================"
    echo ""

    if [ $failed_count -gt 0 ]; then
        return 1
    fi

    return 0
}

# Show migration status
show_status() {
    echo ""
    echo "============================================"
    echo "  Migration Status"
    echo "============================================"
    echo ""

    wait_for_postgres || return 1

    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
        SELECT
            migration_name,
            applied_at,
            COALESCE(description, '-') as description
        FROM warehouse.schema_migrations
        ORDER BY migration_name;
    "
}

# Main entry point
case "${1:-run}" in
    run)
        run_migrations
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {run|status}"
        exit 1
        ;;
esac
