# Docker Code Review Issues

Review of `docker/` directory. Last updated: 2026-02-02

## 1. Security Issues

| File | Line | Issue |
|------|------|-------|
| `warehouse/Dockerfile` | 13-14 | **Hardcoded credentials** - `warehouse_pass` is baked into the image |
| `airflow/entrypoint.sh` | 80 | **Weak default password** - Default admin password is `admin` |
| `warehouse/run_migrations.sh` | 91, 103-108 | **SQL Injection risk** - Migration names are interpolated directly into SQL without escaping. A malicious filename like `001'; DROP TABLE users; --` could cause damage |

## 2. Bugs

| File | Line | Issue |
|------|------|-------|
| `warehouse/docker-entrypoint-wrapper.sh` | 18 | **Race condition** - Hardcoded `sleep 5` is unreliable; may be too short on slow systems or too long on fast ones |
| `warehouse/docker-entrypoint-wrapper.sh` | 62 | **Silent failures** - Background process errors won't be visible; migrations can fail while PostgreSQL keeps running with incomplete schema |
| `warehouse/run_migrations.sh` | 176 | **Word splitting** - `for migration_file in $migration_files` breaks on filenames with spaces (should quote or use `while read`) |
| `warehouse/run_migrations.sh` | 162 | **Portability** - `sort -V` (version sort) may not be available on Alpine Linux |
| `airflow/fix_callback_type.sql` | 14 | **Missing schema qualification** - `table_name = 'callback_request'` doesn't specify schema, could match wrong table |
| `spark/Dockerfile.standalone` | 17 | **Build failure risk** - `COPY src/spark_apps/*` fails if directory is empty |

## 3. Inefficiencies

| File | Line | Issue |
|------|------|-------|
| `airflow/Dockerfile` | 28 | **Unused file** - `requirements.txt` is copied but never used (only `requirements-dev.txt` is installed) |
| `warehouse/run_migrations.sh` | 42-61 | **Duplicate logic** - `wait_for_postgres` already runs in wrapper script at lines 38-46; runs twice |
| `spark/docker-compose.spark.yml` | 4 | **Deprecated** - `version: '3.8'` is deprecated in modern Docker Compose |

## 4. Other Issues

| File | Line | Issue |
|------|------|-------|
| `spark/docker-compose.spark.yml` | 78-79 | **External dependency** - `external: true` network requires Airflow to be running first; standalone Spark startup will fail |
| `spark/docker-compose.spark.yml` | N/A | **Missing healthchecks** - Workers have no healthchecks (master has one via Dockerfile CMD) |
| `airflow/entrypoint.sh` | 58-83 | **Inconsistent step numbering** - Steps 3 and 4 are conditional, so output may show "Step 1, 2, 5" confusing users |
| `warehouse/run_migrations.sh` | 156-158 | **Error handling** - `ensure_migrations_table` failure at line 79 is treated as recoverable, but subsequent operations may fail anyway |
