"""
Comprehensive Data Quality Validation - Advanced Example DAG

This DAG demonstrates all five data quality check types with different severity
levels and automated alerting. Shows production-grade quality validation patterns
for ensuring data integrity.

Pattern Demonstrated:
- Schema validation (structure correctness)
- Completeness checks (record count validation)
- Freshness checks (timeliness validation)
- Uniqueness checks (duplicate detection)
- Null rate checks (missing value detection)
- Severity-based workflow (CRITICAL halts pipeline, WARNING logs only)
- Quality metrics aggregation and reporting

Use Case:
Validate sales fact table across all quality dimensions before allowing downstream
consumption. Demonstrates defensive data engineering with comprehensive checks.

Learning Objectives:
- Understand the 5 core data quality dimensions
- Learn severity level patterns (CRITICAL vs WARNING vs INFO)
- See how to aggregate quality results
- Understand when to halt vs. continue pipeline
- Learn quality metrics tracking for monitoring

Constitutional Compliance:
- Principle III: Data Quality Assurance (NON-NEGOTIABLE - comprehensive checks)
- Principle V: Observability (quality metrics logging and tracking)
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

logger = logging.getLogger(__name__)


# Default arguments
default_args = {
    "owner": "data-quality@example.com",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


def validate_schema(**context):
    """
    Validate table schema matches expected structure.

    Checks:
    - All required columns present
    - No unexpected columns
    - Column data types correct

    Severity: CRITICAL (pipeline halts on failure)

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Schema validation results

    Raises:
        AirflowException: If schema validation fails (CRITICAL severity)
    """
    logger.info("Starting schema validation for fact_sales table")

    # Expected schema
    expected_columns = {
        "sale_id": "bigint",
        "transaction_id": "character varying",
        "customer_id": "integer",
        "product_id": "integer",
        "sale_date_id": "integer",
        "quantity": "integer",
        "unit_price": "numeric",
        "discount": "numeric",
        "total_amount": "numeric",
        "created_at": "timestamp without time zone",
    }

    # Simulate schema check
    # In real implementation, query information_schema.columns
    actual_columns = expected_columns.copy()

    # Simulate potential issues
    missing_columns = set(expected_columns.keys()) - set(actual_columns.keys())
    extra_columns = set(actual_columns.keys()) - set(expected_columns.keys())
    type_mismatches = [
        col
        for col in expected_columns
        if col in actual_columns and actual_columns[col] != expected_columns[col]
    ]

    validation_passed = (
        len(missing_columns) == 0 and len(extra_columns) == 0 and len(type_mismatches) == 0
    )

    result = {
        "check_type": "schema_validation",
        "table": "fact_sales",
        "severity": "CRITICAL",
        "passed": validation_passed,
        "expected_columns": len(expected_columns),
        "actual_columns": len(actual_columns),
        "missing_columns": list(missing_columns),
        "extra_columns": list(extra_columns),
        "type_mismatches": type_mismatches,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Schema Validation: {'PASSED' if validation_passed else 'FAILED'}")
    logger.info(f"  Expected columns: {len(expected_columns)}")
    logger.info(f"  Actual columns: {len(actual_columns)}")

    if not validation_passed:
        error_msg = f"Schema validation FAILED: missing={missing_columns}, extra={extra_columns}, type_mismatches={type_mismatches}"
        logger.error(error_msg)
        raise AirflowException(error_msg)

    # Push to XCom
    context["task_instance"].xcom_push(key="schema_check", value=result)

    return result


def validate_completeness(**context):
    """
    Validate record count meets expectations with tolerance.

    Checks:
    - Minimum row count threshold
    - Expected row count with tolerance range
    - Comparison with historical averages

    Severity: WARNING (logs issue but doesn't halt pipeline)

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Completeness validation results
    """
    logger.info("Starting completeness validation for fact_sales table")

    # Simulate row count check
    # In real implementation: SELECT COUNT(*) FROM fact_sales WHERE date = ...
    import random

    random.seed(hash(context["execution_date"].isoformat()))  # Use full date for better diversity

    actual_row_count = random.randint(950, 1050)
    expected_row_count = 1000
    min_row_count = 800
    tolerance_percentage = 10.0

    # Calculate tolerance bounds
    lower_bound = expected_row_count * (1 - tolerance_percentage / 100)
    upper_bound = expected_row_count * (1 + tolerance_percentage / 100)

    validation_passed = (
        actual_row_count >= min_row_count and lower_bound <= actual_row_count <= upper_bound
    )

    deviation_percentage = abs((actual_row_count - expected_row_count) / expected_row_count * 100)

    result = {
        "check_type": "completeness_check",
        "table": "fact_sales",
        "severity": "WARNING",
        "passed": validation_passed,
        "actual_row_count": actual_row_count,
        "expected_row_count": expected_row_count,
        "min_row_count": min_row_count,
        "tolerance_percentage": tolerance_percentage,
        "deviation_percentage": round(deviation_percentage, 2),
        "within_tolerance": validation_passed,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Completeness Validation: {'PASSED' if validation_passed else 'FAILED'}")
    logger.info(f"  Actual rows: {actual_row_count:,}")
    logger.info(f"  Expected rows: {expected_row_count:,}")
    logger.info(f"  Deviation: {deviation_percentage:.2f}%")

    if not validation_passed:
        logger.warning(
            f"Completeness check FAILED but continuing (severity=WARNING). "
            f"Actual={actual_row_count}, Expected range=[{lower_bound:.0f}, {upper_bound:.0f}]"
        )

    # Push to XCom
    context["task_instance"].xcom_push(key="completeness_check", value=result)

    return result


def validate_freshness(**context):
    """
    Validate data freshness based on timestamp columns.

    Checks:
    - Maximum age of most recent record
    - Data arrival SLA compliance
    - Staleness detection

    Severity: CRITICAL (stale data should halt pipeline)

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Freshness validation results

    Raises:
        AirflowException: If data is stale (CRITICAL severity)
    """
    logger.info("Starting freshness validation for fact_sales table")

    # Simulate freshness check
    # In real implementation: SELECT MAX(created_at) FROM fact_sales
    most_recent_timestamp = datetime.now() - timedelta(hours=2)
    current_time = datetime.now()
    data_age_hours = (current_time - most_recent_timestamp).total_seconds() / 3600
    max_age_hours = 24.0  # SLA: data must be less than 24 hours old

    validation_passed = data_age_hours <= max_age_hours

    result = {
        "check_type": "freshness_check",
        "table": "fact_sales",
        "severity": "CRITICAL",
        "passed": validation_passed,
        "most_recent_timestamp": most_recent_timestamp.isoformat(),
        "data_age_hours": round(data_age_hours, 2),
        "max_age_hours": max_age_hours,
        "sla_compliance": validation_passed,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Freshness Validation: {'PASSED' if validation_passed else 'FAILED'}")
    logger.info(f"  Most recent record: {most_recent_timestamp}")
    logger.info(f"  Data age: {data_age_hours:.2f} hours")
    logger.info(f"  SLA threshold: {max_age_hours} hours")

    if not validation_passed:
        error_msg = f"Freshness validation FAILED: data age {data_age_hours:.2f}h exceeds SLA {max_age_hours}h"
        logger.error(error_msg)
        raise AirflowException(error_msg)

    # Push to XCom
    context["task_instance"].xcom_push(key="freshness_check", value=result)

    return result


def validate_uniqueness(**context):
    """
    Validate uniqueness of key columns (duplicate detection).

    Checks:
    - Transaction ID uniqueness
    - Duplicate record detection
    - Composite key validation

    Severity: WARNING (duplicates logged but don't halt pipeline)

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Uniqueness validation results
    """
    logger.info("Starting uniqueness validation for fact_sales table")

    # Simulate uniqueness check
    # In real implementation:
    # SELECT transaction_id, COUNT(*) as cnt
    # FROM fact_sales
    # GROUP BY transaction_id
    # HAVING COUNT(*) > 1

    import random

    random.seed(context["execution_date"].day + 1)

    total_records = 1000
    duplicate_count = random.randint(0, 30)  # 0-3% duplicates
    unique_records = total_records - duplicate_count
    duplicate_percentage = (duplicate_count / total_records * 100) if total_records > 0 else 0

    max_duplicate_percentage = 1.0  # Allow up to 1% duplicates
    validation_passed = duplicate_percentage <= max_duplicate_percentage

    result = {
        "check_type": "uniqueness_check",
        "table": "fact_sales",
        "column": "transaction_id",
        "severity": "WARNING",
        "passed": validation_passed,
        "total_records": total_records,
        "unique_records": unique_records,
        "duplicate_count": duplicate_count,
        "duplicate_percentage": round(duplicate_percentage, 2),
        "max_duplicate_percentage": max_duplicate_percentage,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Uniqueness Validation: {'PASSED' if validation_passed else 'FAILED'}")
    logger.info(f"  Total records: {total_records:,}")
    logger.info(f"  Duplicates found: {duplicate_count:,}")
    logger.info(f"  Duplicate rate: {duplicate_percentage:.2f}%")

    if not validation_passed:
        logger.warning(
            f"Uniqueness check FAILED but continuing (severity=WARNING). "
            f"Duplicate rate {duplicate_percentage:.2f}% exceeds threshold {max_duplicate_percentage}%"
        )

    # Push to XCom
    context["task_instance"].xcom_push(key="uniqueness_check", value=result)

    return result


def validate_null_rate(**context):
    """
    Validate null/missing value rates for critical columns.

    Checks:
    - Null percentage for required columns
    - Missing value detection
    - Data completeness at field level

    Severity: WARNING (nulls logged but don't halt pipeline)

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Null rate validation results
    """
    logger.info("Starting null rate validation for fact_sales table")

    # Simulate null rate check for customer_id column
    # In real implementation:
    # SELECT
    #   COUNT(*) as total_records,
    #   COUNT(customer_id) as non_null_records,
    #   COUNT(*) - COUNT(customer_id) as null_records
    # FROM fact_sales

    import random

    random.seed(context["execution_date"].day + 2)

    total_records = 1000
    null_count = random.randint(0, 25)  # 0-2.5% nulls
    non_null_count = total_records - null_count
    null_percentage = (null_count / total_records * 100) if total_records > 0 else 0

    max_null_percentage = 2.0  # Allow up to 2% nulls
    validation_passed = null_percentage <= max_null_percentage

    result = {
        "check_type": "null_rate_check",
        "table": "fact_sales",
        "column": "customer_id",
        "severity": "WARNING",
        "passed": validation_passed,
        "total_records": total_records,
        "non_null_count": non_null_count,
        "null_count": null_count,
        "null_percentage": round(null_percentage, 2),
        "max_null_percentage": max_null_percentage,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Null Rate Validation: {'PASSED' if validation_passed else 'FAILED'}")
    logger.info(f"  Total records: {total_records:,}")
    logger.info(f"  Null values: {null_count:,}")
    logger.info(f"  Null rate: {null_percentage:.2f}%")

    if not validation_passed:
        logger.warning(
            f"Null rate check FAILED but continuing (severity=WARNING). "
            f"Null rate {null_percentage:.2f}% exceeds threshold {max_null_percentage}%"
        )

    # Push to XCom
    context["task_instance"].xcom_push(key="null_rate_check", value=result)

    return result


def aggregate_quality_results(**context):
    """
    Aggregate all quality check results into comprehensive report.

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Aggregated quality results
    """
    task_instance = context["task_instance"]

    # Pull all quality check results from XCom
    schema_result = task_instance.xcom_pull(
        task_ids="quality_checks.validate_schema", key="schema_check"
    )
    completeness_result = task_instance.xcom_pull(
        task_ids="quality_checks.validate_completeness", key="completeness_check"
    )
    freshness_result = task_instance.xcom_pull(
        task_ids="quality_checks.validate_freshness", key="freshness_check"
    )
    uniqueness_result = task_instance.xcom_pull(
        task_ids="quality_checks.validate_uniqueness", key="uniqueness_check"
    )
    null_rate_result = task_instance.xcom_pull(
        task_ids="quality_checks.validate_null_rate", key="null_rate_check"
    )

    all_checks = [
        schema_result,
        completeness_result,
        freshness_result,
        uniqueness_result,
        null_rate_result,
    ]

    # Aggregate results
    total_checks = len([c for c in all_checks if c is not None])
    passed_checks = len([c for c in all_checks if c and c.get("passed")])
    failed_checks = total_checks - passed_checks

    critical_failures = len(
        [c for c in all_checks if c and not c.get("passed") and c.get("severity") == "CRITICAL"]
    )

    warning_failures = len(
        [c for c in all_checks if c and not c.get("passed") and c.get("severity") == "WARNING"]
    )

    overall_quality_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0

    aggregated_result = {
        "execution_date": context["execution_date"].isoformat(),
        "table": "fact_sales",
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "critical_failures": critical_failures,
        "warning_failures": warning_failures,
        "overall_quality_score": round(overall_quality_score, 2),
        "quality_gate": "PASS" if critical_failures == 0 else "FAIL",
        "individual_results": {
            "schema": schema_result,
            "completeness": completeness_result,
            "freshness": freshness_result,
            "uniqueness": uniqueness_result,
            "null_rate": null_rate_result,
        },
        "aggregation_timestamp": datetime.now().isoformat(),
    }

    # Log comprehensive summary
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE DATA QUALITY REPORT")
    logger.info("=" * 80)
    logger.info(f"Table: {aggregated_result['table']}")
    logger.info(f"Execution Date: {context['execution_date']}")
    logger.info(f"Total Checks: {total_checks}")
    logger.info(f"Passed: {passed_checks} | Failed: {failed_checks}")
    logger.info(f"Critical Failures: {critical_failures}")
    logger.info(f"Warning Failures: {warning_failures}")
    logger.info(f"Overall Quality Score: {overall_quality_score:.2f}%")
    logger.info(f"Quality Gate: {aggregated_result['quality_gate']}")
    logger.info("=" * 80)
    logger.info("Individual Check Results:")
    for check_name, check_result in aggregated_result["individual_results"].items():
        if check_result:
            status = "✓ PASS" if check_result["passed"] else "✗ FAIL"
            logger.info(f"  {check_name.upper()}: {status} (severity={check_result['severity']})")
    logger.info("=" * 80)

    return aggregated_result


def send_quality_alert(**context):
    """
    Send alert if quality issues detected.

    Args:
        **context: Airflow context dictionary
    """
    task_instance = context["task_instance"]

    agg_result = task_instance.xcom_pull(task_ids="aggregate_quality_results")

    if not agg_result:
        logger.warning("No aggregated results found for alerting")
        return

    if agg_result["failed_checks"] > 0:
        alert_message = f"""
        DATA QUALITY ALERT

        Table: {agg_result['table']}
        Execution Date: {agg_result['execution_date']}

        Quality Score: {agg_result['overall_quality_score']:.2f}%
        Failed Checks: {agg_result['failed_checks']}/{agg_result['total_checks']}
        Critical Failures: {agg_result['critical_failures']}
        Warning Failures: {agg_result['warning_failures']}

        Quality Gate: {agg_result['quality_gate']}

        Please investigate data quality issues before allowing downstream consumption.
        """

        logger.warning(alert_message)

        # In real implementation, this would send email/Teams/Telegram notification
    else:
        logger.info("All quality checks passed - no alert needed")


# Define the DAG
with DAG(
    dag_id="demo_comprehensive_quality_v1",
    default_args=default_args,
    description="Demonstrates all 5 data quality check types with severity levels and alerting",
    schedule=None,  # Manual trigger for demo
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["advanced", "quality", "validation", "comprehensive", "demo"],
    doc_md=__doc__,
) as dag:
    # Start task
    start = PythonOperator(
        task_id="start",
        python_callable=lambda: logger.info("Starting comprehensive quality validation"),
    )

    # All 5 quality checks in parallel task group
    with TaskGroup(group_id="quality_checks") as quality_checks:
        # 1. Schema Validation (CRITICAL)
        schema_check = PythonOperator(
            task_id="validate_schema",
            python_callable=validate_schema,
            doc_md="Validate table schema matches expected structure (CRITICAL)",
        )

        # 2. Completeness Check (WARNING)
        completeness_check = PythonOperator(
            task_id="validate_completeness",
            python_callable=validate_completeness,
            doc_md="Validate record count meets expectations (WARNING)",
        )

        # 3. Freshness Check (CRITICAL)
        freshness_check = PythonOperator(
            task_id="validate_freshness",
            python_callable=validate_freshness,
            doc_md="Validate data is not stale (CRITICAL)",
        )

        # 4. Uniqueness Check (WARNING)
        uniqueness_check = PythonOperator(
            task_id="validate_uniqueness",
            python_callable=validate_uniqueness,
            doc_md="Validate key column uniqueness (WARNING)",
        )

        # 5. Null Rate Check (WARNING)
        null_rate_check = PythonOperator(
            task_id="validate_null_rate",
            python_callable=validate_null_rate,
            doc_md="Validate null value rates (WARNING)",
        )

    # Aggregate results
    aggregate = PythonOperator(
        task_id="aggregate_quality_results",
        python_callable=aggregate_quality_results,
        doc_md="Aggregate all quality check results into comprehensive report",
    )

    # Send alert if issues found
    alert = PythonOperator(
        task_id="send_quality_alert",
        python_callable=send_quality_alert,
        doc_md="Send alert notification if quality issues detected",
    )

    # End task
    end = PythonOperator(
        task_id="end",
        python_callable=lambda: logger.info("Comprehensive quality validation completed"),
    )

    # Define task dependencies
    start >> quality_checks >> aggregate >> alert >> end
