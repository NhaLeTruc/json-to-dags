# Migration Plan: Airflow 3.0 → 2.10.5

## Overview

This document provides a step-by-step plan to migrate from Airflow 3.0 to Airflow 2.10.5 to resolve critical LocalExecutor issues.

## Pre-Migration Checklist

- [x] Document current issues (see [airflow3_issues_and_migration.md](./airflow3_issues_and_migration.md))
- [x] Identify API incompatibilities
- [x] Fix database schemas
- [x] Create migration plan
- [ ] Backup current state
- [ ] Test in development environment

## Migration Steps

### Step 1: Backup Current State (CRITICAL)

Before making any changes, back up your current setup:

```bash
# Backup Docker volumes
docker compose down
docker run --rm -v airflow-postgres-db-volume:/data -v $(pwd)/backups:/backup ubuntu tar czf /backup/postgres-backup-$(date +%Y%m%d-%H%M%S).tar.gz /data

# Backup DAGs and configurations
tar czf backups/dags-config-backup-$(date +%Y%m%d-%H%M%S).tar.gz dags/ src/ docker-compose.yml docker/

# Backup warehouse data
docker run --rm -v claude-airflow-etl_warehouse-data:/data -v $(pwd)/backups:/backup ubuntu tar czf /backup/warehouse-backup-$(date +%Y%m%d-%H%M%S).tar.gz /data
```

### Step 2: Update Docker Compose Configuration

**File**: `docker-compose.yml`

**Changes Required**:

1. **Update Airflow image version**
   - From: `apache/airflow:3.0.0-python3.12` (or custom build)
   - To: `apache/airflow:2.10.5-python3.12`

2. **Remove Airflow 3.0 specific configurations**
   - Remove: `AIRFLOW__CORE__TASK_RUNNER`
   - Remove: `AIRFLOW__CORE__MP_START_METHOD`
   - Keep all other configurations

3. **Update service build contexts** (if using custom Dockerfile)
   - Update base image in `docker/airflow/Dockerfile`
   - From: `FROM apache/airflow:3.0.0-python3.12`
   - To: `FROM apache/airflow:2.10.5-python3.12`

4. **Review provider versions** (if specified in requirements)
   - Ensure compatibility with Airflow 2.10.5
   - Remove any 3.0-specific provider overrides

**Example Docker Compose Changes**:

```yaml
# BEFORE (Airflow 3.0)
x-airflow-common:
  &airflow-common
  build:
    context: .
    dockerfile: docker/airflow/Dockerfile
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__CORE__TASK_RUNNER: airflow.task.task_runner.standard_task_runner.StandardTaskRunner
    AIRFLOW__CORE__MP_START_METHOD: fork
    # ... other configs

# AFTER (Airflow 2.10.5)
x-airflow-common:
  &airflow-common
  image: apache/airflow:2.10.5-python3.12
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    # Removed task_runner and mp_start_method configs
    # ... other configs
```

### Step 3: Update Dockerfile (If Using Custom Build)

**File**: `docker/airflow/Dockerfile`

```dockerfile
# BEFORE
FROM apache/airflow:3.0.0-python3.12

# AFTER
FROM apache/airflow:2.10.5-python3.12

# Keep all other customizations
USER root
# ... your customizations ...
USER airflow
```

### Step 4: Revert Hook API Changes

**File**: `dags/examples/intermediate/demo_incremental_load_v1.py`
**File**: `dags/examples/intermediate/demo_scd_type2_v1.py`

**Revert to Airflow 2.x API**:

```python
# CURRENT (Airflow 3.0 compatible)
hook = WarehouseHook(warehouse_conn_id="warehouse_default")

# CHANGE BACK TO (Airflow 2.x compatible)
hook = WarehouseHook(postgres_conn_id="warehouse")
```

**Note**: This assumes your `WarehouseHook` supports both parameters. You may need to update the hook itself.

### Step 5: Update WarehouseHook for Backward Compatibility

**File**: `src/hooks/warehouse_hook.py`

Update the `__init__` method to accept both parameter names:

```python
def __init__(
    self,
    warehouse_conn_id: str | None = None,
    postgres_conn_id: str | None = None,  # Add for backward compatibility
    *args,
    **kwargs,
) -> None:
    """
    Initialize WarehouseHook.

    Args:
        warehouse_conn_id: Connection ID (Airflow 3.0 style)
        postgres_conn_id: Connection ID (Airflow 2.x style, deprecated)
    """
    # Support both parameter names for backward compatibility
    conn_id = warehouse_conn_id or postgres_conn_id
    if not conn_id:
        raise ValueError("Either warehouse_conn_id or postgres_conn_id must be provided")

    super().__init__(*args, **kwargs)
    self.warehouse_conn_id = conn_id
    self.conn = None
```

### Step 6: Update Connection ID in Airflow

The connection ID may need to be renamed:

```bash
# After migration, check existing connections
docker exec airflow-webserver airflow connections list

# If needed, add new connection with correct name
docker exec airflow-webserver airflow connections add \
    'warehouse' \
    --conn-type 'postgres' \
    --conn-host 'airflow-warehouse' \
    --conn-schema 'warehouse' \
    --conn-login 'warehouse_user' \
    --conn-password 'warehouse_password' \
    --conn-port '5432'
```

### Step 7: Clean Airflow Metadata (Optional but Recommended)

To start fresh and avoid state issues:

```bash
# Stop all services
docker compose down

# Remove Airflow metadata volume (this will delete all DAG run history)
docker volume rm claude-airflow-etl_postgres-db-volume

# Or, to keep data but reset task instances:
docker compose up airflow-postgres -d
docker exec airflow-postgres psql -U airflow -d airflow -c "TRUNCATE task_instance CASCADE;"
docker exec airflow-postgres psql -U airflow -d airflow -c "TRUNCATE dag_run CASCADE;"
docker compose down
```

**⚠️ WARNING**: This will delete all DAG run history. Only do this if acceptable.

### Step 8: Rebuild and Start Services

```bash
# Pull new image or rebuild
docker compose build --no-cache

# Start services
docker compose up -d

# Wait for initialization
sleep 30

# Check scheduler health
docker logs airflow-scheduler --tail=50

# Check for errors
docker logs airflow-scheduler 2>&1 | grep -i error | tail -20
```

### Step 9: Initialize Airflow Database

```bash
# Run database migrations (should be automatic, but verify)
docker exec airflow-scheduler airflow db check

# Check Airflow version
docker exec airflow-scheduler airflow version
# Expected: 2.10.5

# List DAGs
docker exec airflow-webserver airflow dags list
```

### Step 10: Verify Warehouse Schemas

Ensure the warehouse schemas created earlier still exist:

```bash
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dn"
# Should show: etl_metadata, source, warehouse, public

docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dt etl_metadata.*"
# Should show: incremental_watermarks, scd_processing_log, load_log

docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "\dt source.*"
# Should show: sales_transactions, dim_customer
```

### Step 11: Test DAG Execution

```bash
# Test a simple task manually
docker exec airflow-webserver airflow tasks test demo_scheduled_pipeline_v1 extract_data 2025-10-23

# Trigger a DAG run
docker exec airflow-webserver airflow dags trigger demo_scheduled_pipeline_v1

# Wait 30 seconds and check status
sleep 30
docker exec airflow-postgres psql -U airflow -d airflow -c "
SELECT dag_id, task_id, state, start_date, end_date, hostname, pid
FROM task_instance
WHERE dag_id = 'demo_scheduled_pipeline_v1'
ORDER BY start_date DESC
LIMIT 10;"
```

**Expected Results**:
- `state`: 'success' or 'running'
- `hostname`: Should have a value (e.g., 'airflow-scheduler')
- `pid`: Should have a process ID
- `start_date`: Should have a timestamp
- NO SIGKILL errors in scheduler logs

### Step 12: Monitor for Issues

```bash
# Check for SIGKILL errors (should be none)
docker logs airflow-scheduler 2>&1 | grep -i sigkill

# Check for state mismatch errors (should be none)
docker logs airflow-scheduler 2>&1 | grep "finished with state failed"

# Monitor task execution
docker logs airflow-scheduler --follow
```

### Step 13: Unpause DAGs

```bash
# List paused DAGs
docker exec airflow-webserver airflow dags list-paused

# Unpause specific DAGs
docker exec airflow-webserver airflow dags unpause demo_scheduled_pipeline_v1
docker exec airflow-webserver airflow dags unpause demo_incremental_load_v1
docker exec airflow-webserver airflow dags unpause demo_scd_type2_v1

# Or unpause all DAGs
for dag in $(docker exec airflow-webserver airflow dags list -o plain | tail -n +2 | awk '{print $1}'); do
  docker exec airflow-webserver airflow dags unpause $dag
done
```

## Rollback Plan

If migration fails, rollback to Airflow 3.0:

```bash
# Stop services
docker compose down

# Restore from backup
docker volume rm claude-airflow-etl_postgres-db-volume
docker run --rm -v airflow-postgres-db-volume:/data -v $(pwd)/backups:/backup ubuntu tar xzf /backup/postgres-backup-TIMESTAMP.tar.gz -C /

# Revert docker-compose.yml changes
git checkout docker-compose.yml

# Restart services
docker compose up -d
```

## Post-Migration Validation

### Success Criteria

- ✅ All services start successfully
- ✅ Scheduler shows no SIGKILL errors
- ✅ Task instances execute successfully
- ✅ Tasks have valid `hostname`, `pid`, and `start_date`
- ✅ DAG runs complete successfully
- ✅ No "state mismatch" errors in logs
- ✅ Airflow webserver accessible at http://localhost:8080

### Validation Tests

1. **Connection Test**:
   ```bash
   docker exec airflow-webserver airflow connections test warehouse
   ```

2. **Task Test**:
   ```bash
   docker exec airflow-webserver airflow tasks test demo_incremental_load_v1 get_last_watermark 2025-10-23
   ```

3. **Full DAG Run**:
   ```bash
   docker exec airflow-webserver airflow dags trigger demo_scheduled_pipeline_v1
   # Monitor in UI or logs
   ```

4. **Database Query**:
   ```sql
   SELECT dag_id, COUNT(*) as success_count
   FROM task_instance
   WHERE state = 'success'
   AND execution_date > NOW() - INTERVAL '1 hour'
   GROUP BY dag_id;
   ```

## Known Differences Between 2.10.5 and 3.0

### Features Lost (Minor Impact)

1. **Task SDK**: Airflow 3.0's new Task SDK is not available
2. **Asset-based Scheduling**: Some advanced scheduling features
3. **New UI Features**: Latest UI improvements

### Features Gained (Stability)

1. **Stable LocalExecutor**: Proven, reliable task execution
2. **Better Python 3.12 Support**: More mature integration
3. **Production Ready**: Battle-tested in enterprise environments
4. **Extensive Documentation**: Larger community knowledge base

## Configuration Differences

### Airflow 2.10.5 Configuration

The following configurations are **NOT needed** in Airflow 2.10.5:

```yaml
# REMOVE THESE from docker-compose.yml
AIRFLOW__CORE__TASK_RUNNER: airflow.task.task_runner.standard_task_runner.StandardTaskRunner
AIRFLOW__CORE__MP_START_METHOD: fork
```

### Keep These Configurations

```yaml
# KEEP THESE in docker-compose.yml
AIRFLOW__CORE__EXECUTOR: LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres/airflow
AIRFLOW__CORE__FERNET_KEY: ''
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
AIRFLOW__API__AUTH_BACKENDS: 'airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session'
AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK: 'true'
AIRFLOW__SCHEDULER__SCHEDULER_HEARTBEAT_SEC: 5
AIRFLOW__SCHEDULER__MAX_TIS_PER_QUERY: 512
AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT: 'false'
AIRFLOW__SCHEDULER__ZOMBIE_TASK_TIMEOUT: 300
AIRFLOW__CORE__PARALLELISM: 32
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: 16
```

## Timeline Estimate

- **Step 1-2 (Backup & Update Config)**: 15 minutes
- **Step 3-6 (Code Changes)**: 30 minutes
- **Step 7-9 (Rebuild & Initialize)**: 20 minutes
- **Step 10-12 (Testing)**: 30 minutes
- **Step 13 (Production Enablement)**: 10 minutes

**Total Estimated Time**: ~2 hours

## Support and Troubleshooting

### Common Issues

#### Issue 1: Connection Not Found

```
Error: Connection 'warehouse' not found
```

**Solution**:
```bash
docker exec airflow-webserver airflow connections add 'warehouse' \
    --conn-type 'postgres' \
    --conn-host 'airflow-warehouse' \
    --conn-schema 'warehouse' \
    --conn-login 'warehouse_user' \
    --conn-password 'warehouse_password' \
    --conn-port '5432'
```

#### Issue 2: Import Errors

```
ModuleNotFoundError: No module named 'hooks.warehouse_hook'
```

**Solution**: Ensure PYTHONPATH is set correctly:
```yaml
PYTHONPATH: /opt/airflow:/opt/airflow/dags:/opt/airflow/src
```

#### Issue 3: Permission Denied

```
PermissionError: [Errno 13] Permission denied
```

**Solution**: Fix file permissions:
```bash
sudo chown -R 50000:0 dags/ logs/ plugins/ src/
```

## Future Upgrade Path

When Airflow 3.x matures (6-12 months):

1. Monitor Airflow 3.x release notes for LocalExecutor fixes
2. Test in development environment first
3. Follow official migration guide
4. Update provider packages
5. Re-test all DAGs thoroughly

## Contact and Support

For issues during migration:
- Check logs: `docker logs airflow-scheduler`
- Airflow Slack: https://apache-airflow.slack.com
- GitHub Issues: https://github.com/apache/airflow/issues
- Documentation: https://airflow.apache.org/docs/apache-airflow/2.10.5/

---

**Author**: Claude (AI Assistant)
**Date**: 2025-10-23
**Version**: 1.0
**Status**: Ready for Execution
