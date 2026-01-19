# Airflow Scheduler Stability Fixes

## Problem Summary

The Airflow scheduler was crashing with exit code 1, causing service instability. Analysis revealed two critical issues:

### 1. Database Schema Issue
**Error**: `sqlalchemy.exc.DataError: value too long for type character varying(20)`

The `callback_request` table had a `callback_type` column limited to 20 characters, but Airflow was trying to insert "EmailNotificationRequest" (24 characters). This caused the scheduler to crash when attempting to send email notifications.

### 2. API Connection Issue
**Error**: `httpx.ConnectError: [Errno 111] Connection refused`

Tasks were attempting to connect to the API server before it was ready, causing connection failures.

## Fixes Implemented

### Database Schema Fix

**Migration script**: Created [docker/airflow/fix_callback_type.sql](../docker/airflow/fix_callback_type.sql)
- Automatically applies via dedicated `airflow-db-fix` service
- Idempotent - safe to run multiple times
- Uses environment variables from .env for credentials (no hardcoded secrets)
- Runs independently after `airflow-init` completes successfully

**New Service**: `airflow-db-fix` ([docker-compose.yml:133-160](../docker-compose.yml#L133-L160))
```yaml
airflow-db-fix:
  image: postgres:15-alpine
  environment:
    PGHOST: ${POSTGRES_AIRFLOW_HOST:-airflow-postgres}
    PGPORT: ${POSTGRES_AIRFLOW_PORT:-5432}
    PGDATABASE: ${POSTGRES_AIRFLOW_DB:-airflow}
    PGUSER: ${POSTGRES_AIRFLOW_USER:-airflow}
    PGPASSWORD: ${POSTGRES_AIRFLOW_PASSWORD:-airflow}
  command:
    - sh
    - -c
    - |
      echo "Waiting for Airflow initialization to complete..."
      sleep 5
      echo "Applying database schema fixes..."
      psql -f /docker/airflow/fix_callback_type.sql
      echo "Database schema fixes applied successfully"
  volumes:
    - ./docker:/docker:ro
  depends_on:
    airflow-init:
      condition: service_completed_successfully
```

### Docker Compose Improvements

#### Scheduler Configuration ([docker-compose.yml:207-243](../docker-compose.yml#L207-L243))

**Enhanced Dependencies**:
- Depends on `airflow-init` completion
- Depends on `airflow-db-fix` completion (ensures schema is fixed before starting)
- Depends on `airflow-webserver` (API server) health
- Depends on `airflow-dag-processor` health

**Robustness Settings**:
```yaml
environment:
  AIRFLOW__SCHEDULER__SCHEDULER_HEARTBEAT_SEC: 5
  AIRFLOW__SCHEDULER__MAX_TIS_PER_QUERY: 512
  AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT: 'false'
  AIRFLOW__SCHEDULER__ZOMBIE_TASK_TIMEOUT: 300
  AIRFLOW__CORE__PARALLELISM: 32
  AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: 16
```

**Resource Limits**:
```yaml
deploy:
  resources:
    limits:
      memory: 2G
    reservations:
      memory: 512M
```

**Improved Health Checks**:
- Increased `start_period` from 30s to 60s
- Changed restart policy to `unless-stopped` for better control

## Results

- Scheduler is now stable and running continuously
- Database schema fix applies automatically on each fresh deployment
- Proper startup sequencing prevents connection errors
- Resource limits prevent memory exhaustion
- Health checks provide better monitoring
- No hardcoded credentials (all from .env)

## Verification

Check all services status:
```bash
docker compose ps
```

Check db-fix service logs:
```bash
docker logs airflow-db-fix
```

Monitor scheduler logs:
```bash
docker logs airflow-scheduler --tail=50 -f
```

Verify database fix:
```bash
docker exec airflow-postgres psql -U airflow -d airflow \
  -c "SELECT character_maximum_length FROM information_schema.columns
      WHERE table_name = 'callback_request' AND column_name = 'callback_type';"
```

Expected output: `100` (should be 100, not 20)

## Architecture

The startup sequence is now:
1. `airflow-postgres` starts
2. `airflow-warehouse` starts
3. `airflow-init` runs (DB migrations, user creation)
4. `airflow-db-fix` runs (applies schema fixes) - **NEW SERVICE**
5. `airflow-webserver` starts
6. `airflow-dag-processor` starts
7. `airflow-scheduler` starts (only after all above are healthy/completed)

This ensures all prerequisites are met before the scheduler starts.

## Future Maintenance

- Add new schema fixes to `docker/airflow/fix_callback_type.sql` or create new SQL files
- Mount additional SQL files in the `airflow-db-fix` service if needed
- Monitor resource usage with `docker stats airflow-scheduler`
- Adjust memory limits if needed based on DAG complexity
- Credentials are managed via .env file - update there, not in docker-compose.yml
