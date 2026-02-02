# Code Review Issues - src/

**Generated:** 2026-02-02
**Total Issues Found:** 26

---

## Bugs (13 found)

### High Severity (6)

| Location | Issue |
| -------- | ----- |
| `data_generator.py:46` | Division by zero when `null_email_rate=0.0` in `generate_customers()` |
| `data_generator.py:169` | Division by zero when `duplicate_rate=0.0` in `generate_sales()` |
| `data_generator.py:190` | Division by zero when `negative_quantity_rate=0.0` |
| `data_generator.py:199` | Division by zero when `calculation_error_rate=0.0` |
| `completeness_checker.py:89` | **SQL injection** - partition_value interpolated directly into SQL |
| `uniqueness_checker.py:156` | Unsafe SQL interpolation of column names |

### Medium Severity (6)

| Location | Issue |
| -------- | ----- |
| `config_loader.py:61` | `get_str()` returns `""` instead of respecting provided default |
| `timeout_handler.py:104` | Logic error - marks as timed out when `timeout_seconds=0` |
| `warehouse_hook.py:148` | Misleading use of `DictCursor` for write operations |
| `spark_hook.py:326` | `communicate(timeout=1)` can leave file descriptors in bad state |
| `freshness_checker.py:114` | Timezone-naive `datetime.now()` compared with timezone-aware DB values |
| `sales_aggregation.py:18` | Silent exit with no error message when args missing |

### Low Severity (1)

| Location | Issue |
| -------- | ----- |
| `word_count.py:16-21` | Argument check condition `< 3` should likely be `< 2`; silently uses defaults |

---

## Inefficiencies (7 found)

| Location | Issue |
| -------- | ----- |
| `data_generator.py:44-46` | Modulo-based rate calculation is hard to read; use `random.random() < rate` instead |
| `great_expectations_helper.py:87` | Bare `except Exception` masks real errors |
| `warehouse_hook.py:104-124` | Bare exception catches all including KeyboardInterrupt; original error not logged |
| `spark_hook.py:195-214` | Creates subprocess pipes but never reads them - can block on large output |
| `null_rate_checker.py:91-109` | Executes separate query per column; could use single query with multiple COUNTs |
| `standalone_operator.py:119-124` | Multiple redundant log lines instead of structured single entry |
| `completeness_checker.py:68,147` | Tolerance calculated twice |

---

## Other Issues (13 found)

| Location | Issue |
| -------- | ----- |
| `config_loader.py:159` | Logger kwargs usage inconsistent with StructuredLogger pattern |
| `logger.py:74` | Silent context key sorting; no way to preserve insertion order |
| `notification_templates.py:258` | Hardcoded `localhost:8080` URL should be configurable |
| `email_operator.py:149-150` | `files` parameter accepted but not implemented - misleading API |
| `base_quality_operator.py:199` | `store_results` feature unimplemented, no error raised |
| `completeness_checker.py:97-112` | `get_previous_count()` always returns None, silently fails |
| `base_notification_operator.py:116-125` | Returns "unknown" for missing dag_id/task_id instead of raising error |
| `schema_validator.py:140` | Missing validation of expected_schema structure - KeyError possible |
| `spark_hook.py:84` | Unsafe dict access - `extra_dejson` might be None |
| `sales_aggregation.py:56` | Ambiguous column names - mixing implicit and explicit join styles |
| `word_count.py:58-59` | `.count()` return values unused |
| `uniqueness_checker.py:44-48` | `exclude_nulls=True` default silently ignores nullable key columns |
| `warehouse_hook.py:6-11` | Missing documentation on when to use this vs PostgresHook |

---

## Priority Fixes Recommended

1. **Division by zero bugs** in `data_generator.py` - Add `if rate > 0:` guards
2. **SQL injection** in `completeness_checker.py:89` - Parameterize the partition value
3. **Bare exception handling** - Be specific about caught exception types
4. **Remove or implement** unimplemented features (email attachments, result storage)

---

## Detailed Descriptions

### Division by Zero in data_generator.py

The pattern `i % int(1 / rate)` causes `ZeroDivisionError` when rate is 0.0:

```python
# Line 46
if i % int(1 / null_email_rate) == 0:  # ZeroDivisionError if null_email_rate=0.0

# Line 169
if i % int(1 / duplicate_rate) == 0:

# Line 190
if i % int(1 / negative_quantity_rate) == 0:

# Line 199
if i % int(1 / calculation_error_rate) == 0:
```

**Fix:** Guard with `if rate > 0:` or use `random.random() < rate` instead.

### SQL Injection in completeness_checker.py

Line 89 interpolates partition_value directly into SQL:

```python
f"{self.partition_column} = '{self.partition_value}'"
```

**Fix:** Use parameterized queries instead of string interpolation.

### Unsafe SQL in uniqueness_checker.py

Line 156 interpolates column names directly:

```python
key_list = ", ".join(self.key_columns)
query = f"""SELECT {key_list}, COUNT(*) as count..."""
```

**Fix:** Validate column names against allowed list or use identifier quoting.

### Timezone Issues in freshness_checker.py

Line 114 uses timezone-naive `datetime.now()`:

```python
now = datetime.now()  # Should be datetime.now(timezone.utc)
```

**Fix:** Use `datetime.now(timezone.utc)` for consistent timezone handling.
