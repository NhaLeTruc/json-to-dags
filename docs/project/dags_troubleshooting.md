# DAG Troubleshooting Guide

This document captures common issues encountered with the Airflow DAGs and their solutions.

## Table of Contents
- [demo_scd_type2_v1](#demo_scd_type2_v1)
- [demo_incremental_load_v1](#demo_incremental_load_v1)
- [General Database Issues](#general-database-issues)

---

## demo_scd_type2_v1

### Issue: `relation "staging.dim_customer_scd2_staging" does not exist`

**Error Message:**
```
psycopg2.errors.UndefinedTable: relation "staging.dim_customer_scd2_staging" does not exist
```

**Root Cause:**
The migration `004_scd_type2_tables.sql` was never applied to the database. PostgreSQL's `docker-entrypoint-initdb.d` scripts only run on **first container startup** when the data volume is empty. If the container was created before this migration file was added, the tables don't exist.

**Solution:**
Apply the migration manually:
```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/004_scd_type2_tables.sql
```

Or restart the warehouse container (migrations now run automatically on startup):
```bash
docker compose restart airflow-warehouse
```

**Related Tables:**
- `staging.dim_customer_scd2_staging`
- `warehouse.dim_customer_scd2`

---

### Issue: `relation "source.dim_customer" does not exist`

**Error Message:**
```
psycopg2.errors.UndefinedTable: relation "source.dim_customer" does not exist
```

**Root Cause:**
The migration `003_source_schema.sql` was not applied.

**Solution:**
```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/003_source_schema.sql
```

After creating the schema, populate source.dim_customer from warehouse data:
```sql
INSERT INTO source.dim_customer (customer_id, customer_key, customer_name, email, country, segment, extract_timestamp)
SELECT customer_id, customer_key, customer_name, email, country, segment, created_at
FROM warehouse.dim_customer
ON CONFLICT DO NOTHING;
```

---

### Issue: `relation "etl_metadata.scd_processing_log" does not exist`

**Root Cause:**
The migration `002_etl_metadata_schema.sql` was not applied.

**Solution:**
```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/002_etl_metadata_schema.sql
```

---

## demo_incremental_load_v1

### Issue: `relation "etl_metadata.incremental_watermarks" does not exist`

**Error Message:**
```
psycopg2.errors.UndefinedTable: relation "etl_metadata.incremental_watermarks" does not exist
```

**Root Cause:**
Same as above - migration `002_etl_metadata_schema.sql` was not applied.

**Solution:**
```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/002_etl_metadata_schema.sql
```

---

### Issue: Foreign key violation on `fact_sales` - date not in `dim_date`

**Error Message:**
```
psycopg2.errors.ForeignKeyViolation: insert or update on table "fact_sales"
violates foreign key constraint "fact_sales_sale_date_id_fkey"
DETAIL: Key (sale_date_id)=(20251016) is not present in table "dim_date".
```

**Root Cause:**
The `source.sales_transactions` table contains dates (e.g., October 2025) that don't exist in `warehouse.dim_date`. The seed data originally only generated dates from 2020-2024.

**Diagnosis:**
```sql
-- Check dim_date range
SELECT MIN(date_id), MAX(date_id) FROM warehouse.dim_date;

-- Check source data dates
SELECT DISTINCT date_id FROM source.sales_transactions ORDER BY date_id;
```

**Solution:**
Extend the dim_date table to include the missing years:
```sql
INSERT INTO warehouse.dim_date (date_id, date, year, quarter, month, month_name, week, day_of_week, day_name, is_weekend, is_holiday)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER AS date_id,
    d::DATE AS date,
    EXTRACT(YEAR FROM d)::INTEGER AS year,
    EXTRACT(QUARTER FROM d)::INTEGER AS quarter,
    EXTRACT(MONTH FROM d)::INTEGER AS month,
    TO_CHAR(d, 'Month') AS month_name,
    EXTRACT(WEEK FROM d)::INTEGER AS week,
    EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week,
    TO_CHAR(d, 'Day') AS day_name,
    EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend,
    FALSE AS is_holiday
FROM generate_series(
    '2025-01-01'::DATE,
    '2026-12-31'::DATE,
    '1 day'::INTERVAL
) AS d
ON CONFLICT (date_id) DO NOTHING;
```

**Prevention:**
The `seed_data.sql` has been updated to generate dates through 2026. For fresh container builds, this issue should not occur.

---

## General Database Issues

### Checking Migration Status

View which migrations have been applied:
```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c \
  "SELECT migration_name, applied_at FROM warehouse.schema_migrations ORDER BY migration_name;"
```

### Manually Applying All Migrations

If migrations are missing, apply them in order:
```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/001_initial_schema.sql
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/002_etl_metadata_schema.sql
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/003_source_schema.sql
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -f /migrations/004_scd_type2_tables.sql
```

### Force Rebuild Container with Fresh Data

If you need a completely fresh start:
```bash
# Stop and remove containers and volumes
docker compose down -v

# Rebuild and start
docker compose up -d --build
```

**Warning:** This will delete all data in the warehouse.

### Checking Table Existence

```bash
# List all tables in a schema
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dt staging.*"
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dt warehouse.*"
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dt etl_metadata.*"
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dt source.*"
```

---

## Migration Runner

The warehouse container includes an automatic migration runner that:
1. Runs on every container startup (not just first initialization)
2. Checks `warehouse.schema_migrations` for already-applied migrations
3. Applies any new migrations in numerical order
4. Skips migrations that have already been applied

**Checking migration runner logs:**
```bash
docker logs airflow-warehouse | grep -A 20 "Migration Runner"
```

**Expected output on restart (migrations already applied):**
```
============================================
  Warehouse Database Migration Runner
============================================

  [SKIP] 001_initial_schema (already applied)
  [SKIP] 002_etl_metadata_schema (already applied)
  [SKIP] 003_source_schema (already applied)
  [SKIP] 004_scd_type2_tables (already applied)

============================================
  Migration Summary
============================================
  Applied: 0
  Skipped: 4
  Failed:  0
============================================
```

---

## Quick Diagnostic Commands

```bash
# Check if warehouse container is healthy
docker ps | grep warehouse

# View recent warehouse logs
docker logs airflow-warehouse --tail 50

# Test database connectivity
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "SELECT 1;"

# Check watermarks (for incremental load DAG)
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c \
  "SELECT * FROM etl_metadata.incremental_watermarks ORDER BY created_at DESC LIMIT 5;"

# Check SCD processing logs
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c \
  "SELECT * FROM etl_metadata.scd_processing_log ORDER BY created_at DESC LIMIT 5;"
```
