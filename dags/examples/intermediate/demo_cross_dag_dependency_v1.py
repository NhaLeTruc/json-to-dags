"""
Cross-DAG Dependencies - Intermediate Example DAG

This DAG demonstrates how to create dependencies between different DAGs using
sensors and trigger operators. Shows coordination patterns for complex workflows
spanning multiple DAGs.

Pattern Demonstrated:
- ExternalTaskSensor: Wait for tasks in other DAGs to complete
- TriggerDagRunOperator: Trigger execution of other DAGs
- Cross-DAG data passing via XCom
- Conditional DAG triggering based on results

Use Case:
Orchestrate a multi-stage data pipeline where downstream DAGs wait for upstream
DAGs to complete before processing. Demonstrates separation of concerns while
maintaining workflow coordination.

Learning Objectives:
- Understand cross-DAG dependencies and communication
- Learn when to split vs. combine DAGs
- See sensor patterns for external task waiting
- Understand DAG triggering strategies

Constitutional Compliance:
- Principle I: DAG-First Development (modular DAG design)
- Principle V: Observability (cross-DAG execution tracking)

Note: This DAG coordinates with demo_simple_extract_load_v1 (upstream)
and can trigger quality checks (downstream).
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import DagRun
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.session import provide_session
from airflow.utils.state import DagRunState
from airflow.utils.trigger_rule import TriggerRule

logger = logging.getLogger(__name__)


@provide_session
def get_most_recent_dag_run(dt, session=None):
    """
    Get the execution date of the most recent successful run of the upstream DAG.

    This allows the ExternalTaskSensor to find a matching run even when this DAG
    is triggered manually with a different execution date.
    """
    dag_runs = (
        session.query(DagRun)
        .filter(
            DagRun.dag_id == "demo_simple_extract_load_v1",
            DagRun.state == DagRunState.SUCCESS,
        )
        .order_by(DagRun.execution_date.desc())
        .first()
    )
    if dag_runs:
        return dag_runs.execution_date
    # Return a date far in the past if no successful runs exist
    # The sensor will timeout, but with a clearer reason
    return datetime(2000, 1, 1)


# Default arguments
default_args = {
    "owner": "data-engineering@example.com",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}


def check_upstream_data_quality(**context):
    """
    Check if upstream DAG produced data of sufficient quality to proceed.

    This simulates a quality gate that determines whether to trigger
    downstream DAGs.

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Quality check results
    """
    execution_date = context["execution_date"]
    logger.info(f"Checking upstream data quality for execution date: {execution_date}")

    # Simulate quality check logic
    # In real implementation, this would query quality metrics from upstream DAG
    import random

    random.seed(hash(execution_date.isoformat()))  # Deterministic using full date

    record_count = random.randint(500, 1500)
    error_rate = random.uniform(0.0, 0.05)  # 0-5% error rate

    quality_passed = error_rate < 0.03 and record_count >= 800

    result = {
        "execution_date": execution_date.isoformat(),
        "record_count": record_count,
        "error_rate": error_rate,
        "quality_threshold_met": quality_passed,
        "quality_gate": "PASS" if quality_passed else "FAIL",
    }

    logger.info("Quality Check Results:")
    logger.info(f"  Record Count: {record_count}")
    logger.info(f"  Error Rate: {error_rate:.2%}")
    logger.info(f"  Quality Gate: {result['quality_gate']}")

    # Push results to XCom for downstream tasks
    context["task_instance"].xcom_push(key="quality_check_result", value=result)

    return result


def decide_next_action(**context):
    """
    Branch operator to decide whether to trigger quality DAG or skip.

    Args:
        **context: Airflow context dictionary

    Returns:
        str: Task ID of next task to execute
    """
    task_instance = context["task_instance"]

    # Pull quality check results
    quality_result = task_instance.xcom_pull(
        task_ids="check_data_quality", key="quality_check_result"
    )

    if not quality_result:
        logger.warning("No quality check results found, skipping downstream processing")
        return "skip_processing"

    if quality_result["quality_threshold_met"]:
        logger.info("Quality threshold met - triggering comprehensive quality DAG")
        return "trigger_quality_dag"
    else:
        logger.warning(
            f"Quality threshold NOT met (error rate: {quality_result['error_rate']:.2%}). "
            "Skipping downstream processing."
        )
        return "skip_processing"


def process_validated_data(**context):
    """
    Process data that has passed quality checks.

    This task only runs if quality checks passed.

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Processing results
    """
    task_instance = context["task_instance"]

    quality_result = task_instance.xcom_pull(
        task_ids="check_data_quality", key="quality_check_result"
    )

    # BUG-006 fix: Add defensive null check for XCom result
    if not quality_result:
        logger.warning("No quality check result available, using default values")
        quality_result = {"record_count": 0}

    logger.info("Processing validated data from upstream DAG")
    logger.info(f"Processing {quality_result.get('record_count', 0)} records")

    # Simulate processing
    result = {
        "records_processed": quality_result["record_count"],
        "processing_timestamp": datetime.now().isoformat(),
        "status": "success",
    }

    logger.info(f"Successfully processed {result['records_processed']} records")

    return result


def log_completion(**context):
    """
    Log final status of cross-DAG coordination workflow.

    Args:
        **context: Airflow context dictionary
    """
    task_instance = context["task_instance"]

    quality_result = task_instance.xcom_pull(
        task_ids="check_data_quality", key="quality_check_result"
    )

    logger.info("=" * 80)
    logger.info("CROSS-DAG COORDINATION SUMMARY")
    logger.info("=" * 80)

    if quality_result:
        logger.info(f"Upstream Data Quality: {quality_result['quality_gate']}")
        logger.info(f"Records Available: {quality_result['record_count']}")
        logger.info(f"Error Rate: {quality_result['error_rate']:.2%}")

        if quality_result["quality_threshold_met"]:
            logger.info("Action Taken: Triggered downstream quality validation DAG")
        else:
            logger.info("Action Taken: Skipped downstream processing due to quality issues")
    else:
        logger.warning("No quality check results available")

    logger.info("=" * 80)


# Define the DAG
with DAG(
    dag_id="demo_cross_dag_dependency_v1",
    default_args=default_args,
    description="Demonstrates cross-DAG dependencies using sensors and triggers",
    schedule=None,  # Manual trigger for demo
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["intermediate", "cross-dag", "sensor", "trigger", "demo"],
    doc_md=__doc__,
) as dag:
    # Start task
    start = EmptyOperator(
        task_id="start",
        doc_md="Start of cross-DAG coordination workflow",
    )

    # SENSOR: Wait for upstream DAG to complete
    # This sensor waits for demo_simple_extract_load_v1 to finish
    # Uses execution_date_fn to find the most recent successful run instead of
    # requiring an exact execution date match (which fails for manual triggers)
    wait_for_upstream = ExternalTaskSensor(
        task_id="wait_for_upstream_dag",
        external_dag_id="demo_simple_extract_load_v1",
        external_task_id=None,  # Wait for entire DAG to complete
        execution_date_fn=get_most_recent_dag_run,
        allowed_states=[DagRunState.SUCCESS],
        failed_states=[DagRunState.FAILED],
        mode="poke",
        timeout=60,  # 1 minute for demo; production: use 3600+ (1 hour) or Variable.get("sensor_timeout")
        poke_interval=10,  # Check every 10 seconds
        doc_md="""
        Wait for upstream DAG (demo_simple_extract_load_v1) to complete successfully.

        This sensor uses execution_date_fn to find the most recent successful run
        of the upstream DAG, rather than requiring an exact execution date match.
        This allows the DAG to work when triggered manually.
        """,
    )

    # Check data quality from upstream DAG
    check_quality = PythonOperator(
        task_id="check_data_quality",
        python_callable=check_upstream_data_quality,
        doc_md="Validate data quality from upstream DAG before proceeding",
    )

    # BRANCH: Decide whether to trigger downstream DAG based on quality
    decide_branch = BranchPythonOperator(
        task_id="decide_next_action",
        python_callable=decide_next_action,
        doc_md="""
        Branching logic to decide next action based on data quality.

        If quality checks pass → trigger comprehensive quality DAG
        If quality checks fail → skip downstream processing
        """,
    )

    # TRIGGER: Trigger downstream quality validation DAG
    trigger_quality = TriggerDagRunOperator(
        task_id="trigger_quality_dag",
        trigger_dag_id="demo_comprehensive_quality_v1",
        wait_for_completion=False,  # Don't wait for triggered DAG to finish
        poke_interval=30,
        reset_dag_run=True,  # Allow re-triggering same execution date
        doc_md="""
        Trigger comprehensive quality validation DAG if data quality checks pass.

        This demonstrates conditional DAG triggering based on upstream results.
        The triggered DAG runs independently and doesn't block this DAG's completion.
        """,
    )

    # Skip branch when quality doesn't meet threshold
    skip_processing = EmptyOperator(
        task_id="skip_processing",
        doc_md="Placeholder task when quality checks fail and processing is skipped",
    )

    # Process data (only if quality checks passed)
    process_data = PythonOperator(
        task_id="process_validated_data",
        python_callable=process_validated_data,
        trigger_rule=TriggerRule.ONE_SUCCESS,  # Run if either trigger or skip succeeded
        doc_md="Process validated data from upstream DAG",
    )

    # Join point after branch
    join = EmptyOperator(
        task_id="join",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
        doc_md="Join point after conditional branching",
    )

    # Log final status
    complete = PythonOperator(
        task_id="log_completion",
        python_callable=log_completion,
        trigger_rule=TriggerRule.ALL_DONE,
        doc_md="Log final status of cross-DAG coordination workflow",
    )

    # Define task dependencies
    # Linear flow: start → wait for upstream → check quality → branch
    # Branch paths:
    #   - Quality PASS: trigger downstream DAG → process → join
    #   - Quality FAIL: skip processing → join
    # Final: join → complete
    start >> wait_for_upstream >> check_quality >> decide_branch

    # Branch outcomes
    decide_branch >> trigger_quality >> process_data >> join
    decide_branch >> skip_processing >> join

    # Final steps
    join >> complete


# Additional helper DAG for demonstration
# This represents the "triggered" DAG that would run after quality checks
# In real implementation, this would be in a separate file

with DAG(
    dag_id="demo_cross_dag_dependency_helper_v1",
    default_args=default_args,
    description="Helper DAG to demonstrate being triggered by another DAG",
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["intermediate", "cross-dag", "helper", "demo"],
    doc_md="""
    Helper DAG that demonstrates being triggered by demo_cross_dag_dependency_v1.

    This DAG shows what happens when a DAG is triggered programmatically by
    another DAG using TriggerDagRunOperator.
    """,
) as helper_dag:

    def log_triggered_execution(**context):
        """Log that this DAG was triggered by another DAG."""
        conf = context.get("dag_run").conf or {}
        triggered_by = conf.get("triggered_by", "unknown")

        logger.info("=" * 80)
        logger.info("TRIGGERED DAG EXECUTION")
        logger.info("=" * 80)
        logger.info(f"This DAG was triggered by: {triggered_by}")
        logger.info(f"Execution Date: {context['execution_date']}")
        logger.info(f"Run ID: {context['run_id']}")
        logger.info("=" * 80)

    log_trigger = PythonOperator(
        task_id="log_triggered_execution",
        python_callable=log_triggered_execution,
        doc_md="Log information about being triggered by another DAG",
    )

    simulate_work = EmptyOperator(
        task_id="simulate_work",
        doc_md="Simulate processing work in triggered DAG",
    )

    log_trigger >> simulate_work
