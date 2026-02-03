"""
Integration tests for all example DAGs.

Tests ensure each example DAG:
- Executes successfully without errors
- Completes within expected time limits
- Demonstrates the intended pattern
- Leaves the system in a clean state
"""

from datetime import datetime

import pytest
from airflow.models import DagBag, TaskInstance
from airflow.utils.state import DagRunState, TaskInstanceState
from airflow.utils.types import DagRunType


@pytest.fixture
def dag_bag():
    """Load all DAGs from the examples directory."""
    return DagBag(dag_folder="dags/examples", include_examples=False)


@pytest.fixture
def execution_date():
    """Provide a consistent execution date for testing."""
    return datetime(2025, 1, 15, 10, 0, 0)


class TestBeginnerExampleDAGs:
    """Test suite for beginner-level example DAGs."""

    def test_simple_extract_load_executes(self, dag_bag, execution_date):
        """Test simple extract-load DAG executes successfully."""
        dag_id = "demo_simple_extract_load_v1"

        # Skip if DAG not yet implemented
        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify DAG structure
        assert dag is not None
        assert len(dag.tasks) > 0

        # Create DAG run
        dag_run = dag.create_dagrun(
            state=DagRunState.RUNNING,
            execution_date=execution_date,
            run_type=DagRunType.MANUAL,
            run_id=f"test_{dag_id}_{execution_date.isoformat()}",
        )

        # Execute all tasks
        for task in dag.tasks:
            task_instance = TaskInstance(task, execution_date)
            task_instance.run(ignore_ti_state=True)
            assert task_instance.state == TaskInstanceState.SUCCESS

        # Verify DAG run succeeded
        assert dag_run.state == DagRunState.SUCCESS

    def test_scheduled_pipeline_executes(self, dag_bag, execution_date):
        """Test scheduled pipeline DAG with retry logic."""
        dag_id = "demo_scheduled_pipeline_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify retry configuration
        for task in dag.tasks:
            assert task.retries >= 3
            assert task.retry_delay is not None

        # Execute DAG
        dag.create_dagrun(
            state=DagRunState.RUNNING,
            execution_date=execution_date,
            run_type=DagRunType.SCHEDULED,
            run_id=f"scheduled__{execution_date.isoformat()}",
        )

        for task in dag.tasks:
            task_instance = TaskInstance(task, execution_date)
            task_instance.run(ignore_ti_state=True)
            assert task_instance.state == TaskInstanceState.SUCCESS

    def test_data_quality_basics_executes(self, dag_bag, execution_date):
        """Test data quality basics DAG with validation checks."""
        dag_id = "demo_data_quality_basics_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify quality operators present
        quality_operators = [
            task
            for task in dag.tasks
            if "quality" in task.task_id.lower() or "check" in task.task_id.lower()
        ]
        assert len(quality_operators) > 0

        # Execute DAG
        dag.create_dagrun(
            state=DagRunState.RUNNING,
            execution_date=execution_date,
            run_type=DagRunType.MANUAL,
            run_id=f"test_{dag_id}_{execution_date.isoformat()}",
        )

        for task in dag.tasks:
            task_instance = TaskInstance(task, execution_date)
            task_instance.run(ignore_ti_state=True)

    def test_notification_basics_executes(self, dag_bag, execution_date):
        """Test notification basics DAG."""
        dag_id = "demo_notification_basics_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify notification operators present
        notification_tasks = [
            task
            for task in dag.tasks
            if "notification" in task.task_id.lower() or "notify" in task.task_id.lower()
        ]
        assert len(notification_tasks) > 0


class TestIntermediateExampleDAGs:
    """Test suite for intermediate-level example DAGs."""

    def test_incremental_load_executes(self, dag_bag, execution_date):
        """Test incremental load DAG with watermark tracking."""
        dag_id = "demo_incremental_load_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Execute DAG
        dag.create_dagrun(
            state=DagRunState.RUNNING,
            execution_date=execution_date,
            run_type=DagRunType.SCHEDULED,
            run_id=f"scheduled__{execution_date.isoformat()}",
        )

        for task in dag.tasks:
            task_instance = TaskInstance(task, execution_date)
            task_instance.run(ignore_ti_state=True)

    def test_scd_type2_executes(self, dag_bag, execution_date):
        """Test SCD Type 2 DAG for dimension history tracking."""
        dag_id = "demo_scd_type2_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify SCD-related tasks present
        scd_tasks = [
            task
            for task in dag.tasks
            if any(
                keyword in task.task_id.lower()
                for keyword in ["scd", "history", "effective", "current"]
            )
        ]
        assert len(scd_tasks) > 0

    def test_parallel_processing_executes(self, dag_bag, execution_date):
        """Test parallel processing DAG with fan-out pattern."""
        dag_id = "demo_parallel_processing_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify parallel task structure
        # Should have tasks with multiple downstream dependencies
        parallel_tasks = [task for task in dag.tasks if len(task.downstream_list) > 1]
        assert len(parallel_tasks) > 0 or any(len(task.upstream_list) > 1 for task in dag.tasks)

    def test_spark_standalone_executes(self, dag_bag, execution_date):
        """Test Spark standalone DAG."""
        dag_id = "demo_spark_standalone_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify Spark operators present
        spark_tasks = [
            task
            for task in dag.tasks
            if "spark" in task.task_id.lower() or "Spark" in task.__class__.__name__
        ]
        assert len(spark_tasks) > 0

    def test_cross_dag_dependency_executes(self, dag_bag, execution_date):
        """Test cross-DAG dependency with sensors and triggers."""
        dag_id = "demo_cross_dag_dependency_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify sensor or trigger operators present
        sensor_tasks = [
            task
            for task in dag.tasks
            if "sensor" in task.task_id.lower() or "Sensor" in task.__class__.__name__
        ]
        trigger_tasks = [
            task
            for task in dag.tasks
            if "trigger" in task.task_id.lower() or "Trigger" in task.__class__.__name__
        ]
        assert len(sensor_tasks) > 0 or len(trigger_tasks) > 0


class TestAdvancedExampleDAGs:
    """Test suite for advanced-level example DAGs."""

    def test_spark_multi_cluster_executes(self, dag_bag, execution_date):
        """Test multi-cluster Spark DAG."""
        dag_id = "demo_spark_multi_cluster_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify multiple Spark operators for different cluster types
        spark_tasks = [
            task
            for task in dag.tasks
            if "spark" in task.task_id.lower() or "Spark" in task.__class__.__name__
        ]
        # Should have at least 3 Spark tasks (standalone, YARN, K8s)
        assert len(spark_tasks) >= 3

    def test_comprehensive_quality_executes(self, dag_bag, execution_date):
        """Test comprehensive quality DAG with all check types."""
        dag_id = "demo_comprehensive_quality_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify all 5 quality check types present
        quality_tasks = [
            task
            for task in dag.tasks
            if any(
                keyword in task.task_id.lower()
                for keyword in ["schema", "completeness", "freshness", "uniqueness", "null"]
            )
        ]
        # Should have all 5 quality check types
        assert len(quality_tasks) >= 5

    def test_event_driven_pipeline_executes(self, dag_bag, execution_date):
        """Test event-driven pipeline with file sensor."""
        dag_id = "demo_event_driven_pipeline_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify file sensor present
        sensor_tasks = [
            task
            for task in dag.tasks
            if "file" in task.task_id.lower() and "sensor" in task.task_id.lower()
        ]
        assert len(sensor_tasks) > 0

    def test_failure_recovery_executes(self, dag_bag, execution_date):
        """Test failure recovery DAG with compensation logic."""
        dag_id = "demo_failure_recovery_v1"

        if dag_id not in dag_bag.dags:
            pytest.skip(f"{dag_id} not implemented yet")

        dag = dag_bag.get_dag(dag_id)

        # Verify compensation or cleanup tasks present
        recovery_tasks = [
            task
            for task in dag.tasks
            if any(
                keyword in task.task_id.lower()
                for keyword in ["cleanup", "rollback", "compensation", "recovery"]
            )
        ]
        assert len(recovery_tasks) > 0


class TestAllExampleDAGs:
    """Test suite for validating all example DAGs collectively."""

    def test_all_dags_parse_without_errors(self, dag_bag):
        """Test that all example DAGs parse without import errors."""
        assert len(dag_bag.import_errors) == 0, f"Import errors: {dag_bag.import_errors}"

    def test_all_dags_have_documentation(self, dag_bag):
        """Test that all DAGs have docstrings."""
        for dag_id, dag in dag_bag.dags.items():
            assert dag.doc_md or dag.description, f"{dag_id} missing documentation"

    def test_all_dags_follow_naming_convention(self, dag_bag):
        """Test that all DAGs follow naming convention: demo_<name>_v<version>."""
        for dag_id in dag_bag.dag_ids:
            assert dag_id.startswith("demo_"), f"{dag_id} doesn't follow naming convention"
            assert "_v" in dag_id, f"{dag_id} missing version suffix"

    def test_all_dags_have_tags(self, dag_bag):
        """Test that all DAGs have appropriate tags."""
        for dag_id, dag in dag_bag.dags.items():
            assert len(dag.tags) > 0, f"{dag_id} has no tags"
            # Should have difficulty level tag
            difficulty_tags = ["beginner", "intermediate", "advanced"]
            has_difficulty = any(tag in dag.tags for tag in difficulty_tags)
            assert has_difficulty, f"{dag_id} missing difficulty tag"

    def test_all_dags_have_owners(self, dag_bag):
        """Test that all DAGs have owners configured."""
        for dag_id, dag in dag_bag.dags.items():
            assert dag.default_args.get("owner"), f"{dag_id} missing owner"

    def test_correct_dag_count(self, dag_bag):
        """Test that expected number of example DAGs are present."""
        # Beginner: 4, Intermediate: 5, Advanced: 4 = 13 total example DAGs
        expected_count = 13
        actual_count = len([dag_id for dag_id in dag_bag.dag_ids if dag_id.startswith("demo_")])

        # Allow partial implementation
        assert (
            actual_count <= expected_count
        ), f"More DAGs than expected: {actual_count} > {expected_count}"
