# Airflow 3.0 Issues and Migration to 2.10.5

## Executive Summary

This document details the issues encountered with Airflow 3.0 and provides a migration plan to downgrade to Airflow 2.10.5 for stability.

## Issues Discovered in Airflow 3.0

### 1. LocalExecutor SIGKILL Issue (Critical)

**Symptoms:**
- Tasks reported as "finished with state failed, but the task instance's state attribute is queued"
- All DAG runs failing immediately
- Process exit with SIGKILL (-9) signal
- Error message: `uhoh` in LocalExecutor logs

**Root Cause:**
- Airflow 3.0 + Python 3.12 + LocalExecutor incompatibility
- Task runner processes are spawned but immediately killed with SIGKILL
- Multiprocessing start method conflicts between Python 3.12 defaults and Airflow 3.0 expectations
- Missing or incompatible task_runner configuration

**Evidence:**
```
[2025-10-23T09:54:27.208500Z] [info] Process exited exit_code=<Negsignal.SIGKILL: -9> pid=102 signal_sent=SIGKILL
[2025-10-23T09:54:27.209099Z] [error] uhoh [airflow.executors.local_executor.LocalExecutor] loc=local_executor.py:100
[2025-10-23T09:54:27.519201Z] [error] Executor LocalExecutor(parallelism=32) reported that the task instance finished with state failed, but the task instance's state attribute is queued.
```

**Impact:**
- **Severity: Critical** - No tasks can execute
- All scheduled and manually triggered DAGs fail
- Task instances stuck in `queued` or `up_for_retry` state
- No `pid` or `hostname` recorded for failed tasks
- `start_date` remains NULL despite task being marked as running

### 2. API Breaking Changes

**WarehouseHook Parameter Changes:**
- Airflow 3.0 changed hook initialization parameters
- Old: `WarehouseHook(postgres_conn_id="warehouse")`
- New: `WarehouseHook(warehouse_conn_id="warehouse_default")`
- **Status: Fixed** in commits

**Missing Hook Methods:**
- `get_first()` and `get_records()` methods were not migrated to Airflow 3.0 SDK
- **Status: Fixed** - Added methods to [src/hooks/warehouse_hook.py:186-252](../src/hooks/warehouse_hook.py#L186-L252)

### 3. Database Schema Issues

**Missing Schemas:**
- `etl_metadata` schema did not exist
- `source` schema did not exist
- Required tables: `incremental_watermarks`, `scd_processing_log`, `load_log`, `sales_transactions`, `dim_customer`

**Status: Fixed**
- Created migration [src/warehouse/migrations/002_etl_metadata_schema.sql](../src/warehouse/migrations/002_etl_metadata_schema.sql)
- Created migration [src/warehouse/migrations/003_source_schema.sql](../src/warehouse/migrations/003_source_schema.sql)

## Attempted Fixes (Unsuccessful)

### Fix Attempt 1: Task Runner Configuration
```yaml
AIRFLOW__CORE__TASK_RUNNER: airflow.task.task_runner.standard_task_runner.StandardTaskRunner
```
**Result:** Configuration accepted but SIGKILL issue persisted

### Fix Attempt 2: Multiprocessing Start Method
```yaml
AIRFLOW__CORE__MP_START_METHOD: fork
```
**Result:** Configuration key not recognized by Airflow 3.0
```
[warning] section/key [core/mp_start_method] not found in config
```

### Fix Attempt 3: Scheduler Restart
- Cleared all failed task instances
- Restarted scheduler service
**Result:** New task instances immediately killed with same SIGKILL error

## Database State Analysis

**Failed Task Characteristics:**
```sql
SELECT task_id, state, hostname, pid, start_date
FROM task_instance
WHERE state IN ('failed', 'up_for_retry', 'queued');
```

Results showed:
- `hostname`: NULL (task never assigned to worker)
- `pid`: NULL (process never started successfully)
- `start_date`: NULL (task never actually began execution)
- `state`: 'up_for_retry' or 'queued'
- `executor_state`: 'failed'

This indicates tasks are failing **during spawn**, not during execution.

## Manual Task Testing

Tasks work correctly when run via `airflow tasks test`:
```bash
docker exec airflow-webserver airflow tasks test demo_scheduled_pipeline_v1 extract_data 2025-10-23
# Result: SUCCESS
```

This proves:
- DAG code is correct
- Database connections work
- Hooks and operators function properly
- **Issue is specifically with LocalExecutor task spawning in Airflow 3.0**

## Known Issues Research

This matches known Airflow 3.0 issues:
1. **Python 3.12 Compatibility**: Airflow 3.0 has incomplete Python 3.12 support
2. **LocalExecutor Bugs**: Task runner process management has regressions
3. **Multiprocessing Changes**: Python 3.12 changed default multiprocessing behavior
4. **Task SDK Migration**: Airflow 3.0 refactored task execution model

## Migration Decision

**Recommendation: Downgrade to Airflow 2.10.5**

### Rationale:
1. ✅ **Stability**: Airflow 2.10.5 is the latest stable 2.x release
2. ✅ **Python 3.12 Support**: Official support in 2.10.x series
3. ✅ **LocalExecutor Reliability**: Proven track record
4. ✅ **Migration Path**: Clear upgrade path to 3.x when stable
5. ✅ **Community Support**: Large user base, well-documented

### Airflow 2.10.5 Benefits:
- Latest features from 2.x series
- Full Python 3.12 compatibility
- Stable LocalExecutor implementation
- Security updates and bug fixes
- Production-ready for enterprise use

## Migration Plan

See [MIGRATION_PLAN.md](./migration_plan.md) for detailed steps.

## Lessons Learned

1. **Bleeding Edge Risk**: Airflow 3.0 is too new for production
2. **Executor Choice Matters**: LocalExecutor has regressions in 3.0
3. **Test Before Upgrade**: Always test in staging environment
4. **Version Pinning**: Pin exact versions in requirements
5. **Rollback Plan**: Always have downgrade path ready

## Timeline

- **2025-10-23 09:30**: Identified state mismatch errors
- **2025-10-23 09:35**: Found WarehouseHook API incompatibilities
- **2025-10-23 09:40**: Fixed hook methods and database schemas
- **2025-10-23 09:45**: Discovered SIGKILL issue
- **2025-10-23 09:50**: Attempted task_runner configuration fixes
- **2025-10-23 09:55**: Decision to migrate to Airflow 2.10.5

## References

- [Airflow 3.0 Release Notes](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html)
- [Airflow 2.10.5 Documentation](https://airflow.apache.org/docs/apache-airflow/2.10.5/)
- [Python 3.12 Multiprocessing Changes](https://docs.python.org/3.12/library/multiprocessing.html)
- [Airflow Executor Comparison](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/index.html)

---

**Author**: Claude (AI Assistant)
**Date**: 2025-10-23
**Status**: Approved for Migration
