# Known Issues in DAGs

This document catalogs known bugs, inefficiencies, design issues, and code quality concerns identified in the `dags/` directory.

**Last Updated:** 2026-02-02
**Total Issues:** 25

---

## Table of Contents

- [Bugs (6)](#bugs)
- [Inefficiencies (6)](#inefficiencies)
- [Design Issues (7)](#design-issues)
- [Code Quality Issues (6)](#code-quality-issues)
- [Summary](#summary)

---

## Bugs

### BUG-001: Duplicate imports

**Severity:** Low
**Files:**
- `dags/examples/beginner/demo_simple_extract_load_v1.py` (lines 25, 29)
- `dags/examples/beginner/demo_data_quality_basics_v1.py` (lines 25, 31)

**Description:**
`timedelta` is imported twice from the `datetime` module in the same file.

```python
from datetime import timedelta
...
from datetime import datetime, timedelta  # Duplicated import
```

**Impact:** Minor - causes no runtime issues but violates DRY principle and may confuse linters.

**Fix:** Remove the duplicate import statement.

---

### BUG-002: Non-deterministic `start_date` using `days_ago()`

**Severity:** High
**Files:**
- `dags/examples/beginner/demo_simple_extract_load_v1.py` (line 50)
- `dags/examples/beginner/demo_data_quality_basics_v1.py` (line 59)
- `dags/examples/intermediate/demo_incremental_load_v1.py` (line 65)
- `dags/examples/intermediate/demo_scd_type2_v1.py` (line 64)

**Description:**
These files define a `days_ago()` function that uses `datetime.now()`:

```python
def days_ago(n):
    return datetime.now() - timedelta(days=n)
```

Using `datetime.now()` causes the `start_date` to change every time the DAG file is parsed by Airflow's scheduler. This is against Airflow best practices.

**Impact:** Can cause scheduling issues, unexpected DAG runs, and inconsistent behavior between scheduler restarts.

**Fix:** Use a fixed date instead:
```python
start_date=datetime(2025, 1, 1)
```

---

### BUG-003: Redundant `start_date` in DAG and `default_args`

**Severity:** Low
**File:** `dags/examples/beginner/demo_notification_basics_v1.py` (lines 37, 51)

**Description:**
`start_date` is specified in both `default_args` and the DAG constructor:

```python
default_args = {
    ...
    "start_date": datetime(2025, 1, 1),  # Here
}
with DAG(
    ...
    start_date=datetime(2025, 1, 1),     # And here again
)
```

**Impact:** The DAG-level value takes precedence, making the `default_args` value misleading and potentially confusing.

**Fix:** Remove `start_date` from `default_args` when specifying it at the DAG level.

---

### BUG-004: Weak MD5 hash for file integrity

**Severity:** Medium
**File:** `dags/examples/advanced/demo_event_driven_pipeline_v1.py` (line 131)

**Description:**
MD5 is used for file integrity/checksum calculation:

```python
file_hash = hashlib.md5(f.read()).hexdigest()
```

MD5 is cryptographically broken and susceptible to collision attacks.

**Impact:** In security-sensitive contexts, file integrity cannot be guaranteed. For idempotency tracking, collisions could cause incorrect behavior.

**Fix:** Use SHA-256 instead:
```python
file_hash = hashlib.sha256(f.read()).hexdigest()
```

---

### BUG-005: Missing null check in `handle_unsupported_format`

**Severity:** Medium
**File:** `dags/examples/advanced/demo_event_driven_pipeline_v1.py` (lines 301-303)

**Description:**
No check if `metadata` is None before accessing it:

```python
def handle_unsupported_format(**context):
    ...
    metadata = task_instance.xcom_pull(...)
    logger.warning(f"Unsupported file format: {metadata.get('file_format')}")
```

**Impact:** If XCom pull fails or returns None, calling `.get()` on None raises `AttributeError`.

**Fix:** Add null check:
```python
if not metadata:
    logger.error("No metadata available")
    return {"status": "error", "reason": "no_metadata"}
```

---

### BUG-006: Inconsistent XCom key usage with trigger rule

**Severity:** Medium
**File:** `dags/examples/intermediate/demo_cross_dag_dependency_v1.py`

**Description:**
The `process_validated_data` task uses `trigger_rule=TriggerRule.ONE_SUCCESS` but depends on quality check data that may not be available if the skip path is taken.

**Impact:** Potential runtime errors when the task runs after `skip_processing` instead of `trigger_quality_dag`.

**Fix:** Add defensive null checking or restructure the dependency graph.

---

## Inefficiencies

### INEFF-001: Logger initialized at module level during DAG parsing

**Severity:** Low
**Files:** Multiple files throughout `dags/`

**Description:**
```python
logger = get_logger(__name__)
```

This executes every time Airflow parses the DAG file (which happens frequently - every `min_file_process_interval` seconds).

**Impact:** Adds overhead to DAG parsing, especially with many DAG files.

**Fix:** Consider using Airflow's built-in `logging` module directly or lazy initialization.

---

### INEFF-002: Repeated database connections in Python tasks

**Severity:** Medium
**Files:**
- `dags/examples/intermediate/demo_incremental_load_v1.py`
- `dags/examples/intermediate/demo_scd_type2_v1.py`

**Description:**
Each Python task creates a new `WarehouseHook` instance:

```python
hook = WarehouseHook(postgres_conn_id="warehouse")
```

**Impact:** Creates unnecessary connection overhead when multiple tasks in the same worker could share connections.

**Fix:** Consider connection pooling or using Airflow's connection management more efficiently.

---

### INEFF-003: Unused loop variables in `aggregate_results`

**Severity:** Low
**File:** `dags/examples/advanced/demo_spark_multi_cluster_v1.py` (lines 233-234)

**Description:**
```python
for _job_name, _job_id in results.items():
    pass  # Does nothing
```

The `aggregate_results` function iterates but does nothing with the results.

**Impact:** Dead code that adds no value and confuses readers.

**Fix:** Either implement the aggregation logic or remove the loop.

---

### INEFF-004: Memory-inefficient file reading

**Severity:** Medium
**File:** `dags/examples/advanced/demo_event_driven_pipeline_v1.py` (lines 130-131, 134-135)

**Description:**
```python
with open(filepath, "rb") as f:
    file_hash = hashlib.md5(f.read()).hexdigest()  # Loads entire file into memory
```

**Impact:** For large files, this could cause memory issues or OOM errors.

**Fix:** Read file in chunks:
```python
hash_obj = hashlib.sha256()
with open(filepath, "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        hash_obj.update(chunk)
file_hash = hash_obj.hexdigest()
```

---

### INEFF-005: Redundant Spark operator parameter specifications

**Severity:** Low
**Files:**
- `dags/examples/intermediate/demo_spark_standalone_v1.py` (lines 65-66)
- `dags/examples/advanced/demo_spark_multi_cluster_v1.py` (lines 91-96)

**Description:**
Same values specified in both `conf` dict and explicit parameters:

```python
conf={
    "spark.executor.memory": "1g",
    ...
},
executor_memory="1g",  # Duplicated
```

**Impact:** Confusing and violates DRY principle. Could lead to inconsistencies if one is updated without the other.

**Fix:** Use one or the other, not both.

---

### INEFF-006: Inefficient duplicate detection query

**Severity:** Low
**File:** `dags/examples/intermediate/demo_incremental_load_v1.py` (lines 271-277)

**Description:**
The duplicate check uses a nested query structure that's more complex than necessary:

```sql
SELECT COUNT(*) INTO duplicate_count
FROM (
    SELECT transaction_id, COUNT(*) AS cnt
    FROM warehouse.fact_sales
    GROUP BY transaction_id
    HAVING COUNT(*) > 1
) duplicates;
```

**Impact:** Slightly less efficient than it could be, though the impact is minimal for small datasets.

**Fix:** Consider using `EXISTS` for a simple true/false check if only existence matters.

---

## Design Issues

### DESIGN-001: Hardcoded file paths

**Severity:** Medium
**File:** `dags/examples/advanced/demo_event_driven_pipeline_v1.py` (line 59)

**Description:**
```python
LANDING_ZONE = "/tmp/airflow/landing_zone"
```

**Impact:** Path is not configurable, making the DAG inflexible across environments.

**Fix:** Use Airflow Variables or environment variables:
```python
LANDING_ZONE = Variable.get("landing_zone_path", default_var="/tmp/airflow/landing_zone")
```

---

### DESIGN-002: Hardcoded JDBC URLs

**Severity:** Medium
**Files:**
- `dags/examples/intermediate/demo_spark_standalone_v1.py` (line 88)
- `dags/examples/advanced/demo_spark_multi_cluster_v1.py` (lines 112-113)

**Description:**
```python
"jdbc:postgresql://airflow-warehouse:5432/warehouse"
```

**Impact:** Database connection strings are hardcoded instead of using Airflow connections, making environment-specific deployments difficult.

**Fix:** Use Airflow connections and the `BaseHook.get_connection()` method to build URLs dynamically.

---

### DESIGN-003: Insufficient timeout on ExternalTaskSensor

**Severity:** Medium
**File:** `dags/examples/intermediate/demo_cross_dag_dependency_v1.py` (line 256)

**Description:**
```python
timeout=60,  # 1 minute timeout for demo
```

**Impact:** 60 seconds is extremely short for production use. The comment acknowledges it's "for demo" but there's no guidance for production values.

**Fix:** Document production-appropriate timeout values or use a Variable for configurability.

---

### DESIGN-004: Two DAGs defined in one file

**Severity:** Low
**File:** `dags/examples/intermediate/demo_cross_dag_dependency_v1.py` (lines 228-343, 350-390)

**Description:**
Two separate DAGs are defined in a single file:
- `demo_cross_dag_dependency_v1`
- `demo_cross_dag_dependency_helper_v1`

**Impact:** Makes maintenance harder, can cause confusion, and doesn't follow the recommended one-DAG-per-file pattern.

**Fix:** Split into separate files or clearly document why they must coexist.

---

### DESIGN-005: Global mutable singleton without thread safety

**Severity:** Medium
**Files:**
- `dags/factory/operator_registry.py` (lines 252-265)
- `dags/factory/config_validator.py` (lines 230-243)

**Description:**
```python
_registry: OperatorRegistry | None = None

def get_default_registry() -> OperatorRegistry:
    global _registry
    if _registry is None:
        _registry = OperatorRegistry()
    return _registry
```

**Impact:** Could cause race conditions in multi-threaded environments, though Airflow's multiprocessing model mitigates this somewhat.

**Fix:** Use thread-safe singleton pattern or Python's `functools.lru_cache`.

---

### DESIGN-006: Random seed based only on day of month

**Severity:** Low
**Files:**
- `dags/examples/intermediate/demo_cross_dag_dependency_v1.py` (line 104)
- `dags/examples/advanced/demo_comprehensive_quality_v1.py` (line 159)

**Description:**
```python
random.seed(execution_date.day)
```

**Impact:** Using only the day (1-31) means different months with the same day number will produce identical "random" results, reducing test coverage diversity.

**Fix:** Include month and year in the seed:
```python
random.seed(hash(execution_date.isoformat()))
```

---

### DESIGN-007: Temp table operations not in explicit transaction

**Severity:** Low
**File:** `dags/examples/intermediate/demo_scd_type2_v1.py` (lines 115-116)

**Description:**
```python
DROP TABLE IF EXISTS changed_customers;
CREATE TEMP TABLE changed_customers AS ...
```

**Impact:** Relies on implicit transaction behavior. In some edge cases (e.g., connection pooling, certain failure modes), this could lead to unexpected state.

**Fix:** Wrap in explicit transaction control or document the implicit behavior reliance.

---

## Code Quality Issues

### QUALITY-001: Inconsistent DAG creation patterns

**Severity:** Low
**Files:** Throughout `dags/examples/`

**Description:**
Some DAGs use the context manager pattern:
```python
with DAG(...) as dag:
    task = SomeOperator(...)
```

Others use explicit assignment:
```python
dag = DAG(...)
task = SomeOperator(..., dag=dag)
```

**Impact:** Inconsistency makes the codebase harder to read and maintain.

**Fix:** Standardize on one pattern (context manager is recommended for Airflow 2.x+).

---

### QUALITY-002: Large blocks of commented-out code

**Severity:** Low
**File:** `dags/examples/beginner/demo_notification_basics_v1.py` (lines 146-162)

**Description:**
Large blocks of commented code for "failure notification demo" are left in the file.

**Impact:** Clutters the codebase and can confuse readers about what's active.

**Fix:** Either remove the commented code or move it to a separate example file.

---

### QUALITY-003: Missing return type hints in callables

**Severity:** Low
**Files:** Multiple files throughout `dags/`

**Description:**
Python callables lack return type hints:
```python
def extract_category_data(category: str, **context):  # Missing return type
```

**Impact:** Reduces code clarity and IDE/type checker support.

**Fix:** Add return type hints:
```python
def extract_category_data(category: str, **context) -> dict[str, Any]:
```

---

### QUALITY-004: SQL strings without parameterization

**Severity:** Low
**Files:** Multiple files using `PostgresOperator`

**Description:**
SQL queries use Jinja templating for values:
```python
sql="... WHERE extract_timestamp <= '{{ ds }}'::date ..."
```

**Impact:** While Jinja is appropriate for Airflow templating, mixing template variables with potential user input could be risky.

**Fix:** For user-provided values, use parameterized queries via `parameters` argument.

---

### QUALITY-005: Factory missing `max_active_runs` processing

**Severity:** Low
**File:** `dags/factory/dag_builder.py` (lines 141-150)

**Description:**
The `_build_dag_kwargs` method doesn't process `max_active_runs` from config, even though it's a common and important DAG parameter.

**Impact:** JSON configurations cannot set `max_active_runs`, limiting the factory's usefulness.

**Fix:** Add `max_active_runs` to the kwargs processing:
```python
if "max_active_runs" in config:
    dag_kwargs["max_active_runs"] = config["max_active_runs"]
```

---

### QUALITY-006: `depends_on_past` always disabled

**Severity:** Low
**Files:** Most example DAGs

**Description:**
```python
"depends_on_past": False,  # Disabled for demo
```

**Impact:** While acceptable for demos, this universal pattern may not accurately represent production patterns where `depends_on_past=True` is often needed for data pipelines.

**Fix:** Include at least one example demonstrating `depends_on_past=True` usage.

---

## Summary

| Category | Count | Critical | Medium | Low |
|----------|-------|----------|--------|-----|
| Bugs | 6 | 1 | 3 | 2 |
| Inefficiencies | 6 | 0 | 2 | 4 |
| Design Issues | 7 | 0 | 4 | 3 |
| Code Quality | 6 | 0 | 0 | 6 |
| **Total** | **25** | **1** | **9** | **15** |

### Priority Recommendations

**High Priority (Fix Immediately):**
1. BUG-002: Non-deterministic `start_date` - can cause production scheduling issues

**Medium Priority (Fix Soon):**
1. BUG-004: Weak MD5 hashing - security concern
2. BUG-005: Missing null checks - potential runtime errors
3. BUG-006: XCom key inconsistency - potential runtime errors
4. INEFF-004: Memory-inefficient file reading - scalability concern
5. DESIGN-001: Hardcoded paths - deployment flexibility
6. DESIGN-002: Hardcoded JDBC URLs - deployment flexibility
7. DESIGN-005: Thread-unsafe singletons - potential race conditions

**Low Priority (Fix When Convenient):**
- All remaining issues