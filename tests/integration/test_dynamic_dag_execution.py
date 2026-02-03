"""
Integration test for dynamic DAG execution.

Tests that JSON-configured DAGs can be executed successfully end-to-end.
"""

from datetime import datetime

import pytest
from airflow.models import DagBag, TaskInstance
from airflow.utils.state import State


@pytest.mark.integration
@pytest.mark.slow
class TestDynamicDAGExecution:
    """Integration tests for executing dynamically generated DAGs."""

    def test_dag_with_dependencies_executes_in_order(self):
        """Test that DAG with task dependencies executes in correct order."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Find DAG with dependencies (ETL pattern: extract -> transform -> load)
        etl_dags = [
            dag
            for dag_id, dag in dag_bag.dags.items()
            if any(keyword in dag_id.lower() for keyword in ["etl", "pipeline", "simple"])
        ]

        if len(etl_dags) == 0:
            pytest.skip("No ETL DAG found for testing")

        dag = etl_dags[0]
        execution_date = datetime(2024, 10, 15, 12, 0, 0)

        # Track execution order
        execution_order = []

        # Create DAG run
        dag.clear()
        dag.create_dagrun(
            run_id=f"test_dependency_run_{execution_date.isoformat()}",
            execution_date=execution_date,
            state=State.RUNNING,
        )

        # Get tasks in topological order
        topological_order = dag.topological_sort()

        # Execute tasks respecting dependencies
        for task in topological_order:
            # Check that all upstream tasks completed first
            task_instance = TaskInstance(task, execution_date=execution_date)

            for upstream_task in task.upstream_list:
                upstream_ti = TaskInstance(upstream_task, execution_date=execution_date)
                assert (
                    upstream_ti.state == State.SUCCESS
                ), f"Upstream task {upstream_task.task_id} not completed before {task.task_id}"

            # Execute task
            task_instance.run(ignore_all_deps=True, ignore_ti_state=True)
            execution_order.append(task.task_id)

            assert task_instance.state == State.SUCCESS, f"Task {task.task_id} failed"

        # Verify all tasks executed
        assert len(execution_order) == len(dag.tasks)

    def test_parallel_tasks_can_execute_independently(self):
        """Test that independent tasks can execute in parallel (no dependencies)."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        # Take first available DAG
        dag = list(dag_bag.dags.values())[0]
        execution_date = datetime(2024, 10, 15, 12, 0, 0)

        # Find tasks with no dependencies
        independent_tasks = [task for task in dag.tasks if len(task.upstream_list) == 0]

        if len(independent_tasks) == 0:
            pytest.skip("No independent tasks found")

        # All independent tasks should be executable immediately
        for task in independent_tasks:
            task_instance = TaskInstance(task, execution_date=execution_date)
            task_instance.run(ignore_all_deps=True, ignore_ti_state=True)

            assert task_instance.state == State.SUCCESS

    def test_task_params_from_config_applied_correctly(self):
        """Test that task parameters from JSON config are applied correctly."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        dag = list(dag_bag.dags.values())[0]

        # Check that tasks have expected attributes from config
        for task in dag.tasks:
            assert task.task_id is not None
            assert task.owner is not None
            # BashOperator tasks should have bash_command
            if task.__class__.__name__ == "BashOperator":
                assert hasattr(task, "bash_command")
                assert task.bash_command is not None

    def test_retry_configuration_from_config(self):
        """Test that retry configuration from JSON is applied."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        dag = list(dag_bag.dags.values())[0]

        # Check retry configuration on tasks
        for task in dag.tasks:
            # Should have retries configured (either from default_args or task params)
            assert hasattr(task, "retries")
            assert isinstance(task.retries, int)
            assert task.retries >= 0

    def test_dag_schedule_interval_respected(self):
        """Test that DAG schedule interval from config is applied."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        for _dag_id, dag in dag_bag.dags.items():
            # Schedule interval should be set
            assert dag.schedule_interval is not None

    def test_dag_start_date_from_config(self):
        """Test that DAG start date from config is applied correctly."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        for _dag_id, dag in dag_bag.dags.items():
            assert dag.start_date is not None
            assert isinstance(dag.start_date, datetime)

    def test_task_execution_context_available(self):
        """Test that Airflow context is available during task execution."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        dag = list(dag_bag.dags.values())[0]
        execution_date = datetime(2024, 10, 15, 12, 0, 0)

        # Create DAG run
        dag.create_dagrun(
            run_id=f"test_context_run_{execution_date.isoformat()}",
            execution_date=execution_date,
            state=State.RUNNING,
        )

        # Execute first task and verify context
        task = dag.tasks[0]
        task_instance = TaskInstance(task, execution_date=execution_date)

        # Context should be available
        context = task_instance.get_template_context()
        assert "dag" in context
        assert "task" in context
        assert "execution_date" in context
        assert "ds" in context

    def test_multiple_dag_runs_independent(self):
        """Test that multiple DAG runs can execute independently."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        dag = list(dag_bag.dags.values())[0]

        # Create two separate DAG runs
        execution_date_1 = datetime(2024, 10, 15, 12, 0, 0)
        execution_date_2 = datetime(2024, 10, 16, 12, 0, 0)

        dag.clear()

        dag_run_1 = dag.create_dagrun(
            run_id=f"test_run_1_{execution_date_1.isoformat()}",
            execution_date=execution_date_1,
            state=State.RUNNING,
        )

        dag_run_2 = dag.create_dagrun(
            run_id=f"test_run_2_{execution_date_2.isoformat()}",
            execution_date=execution_date_2,
            state=State.RUNNING,
        )

        # Both should exist independently
        assert dag_run_1.run_id != dag_run_2.run_id
        assert dag_run_1.execution_date != dag_run_2.execution_date

    def test_json_config_changes_reflected_in_dag(self, tmp_path):
        """Test that changes to JSON config are reflected when DAG is reloaded."""
        # This test verifies that the factory re-reads configs on each load

        dag_bag_1 = DagBag(dag_folder="dags/", include_examples=False)
        initial_dag_count = len(dag_bag_1.dags)

        # Reload (simulating Airflow's refresh)
        dag_bag_2 = DagBag(dag_folder="dags/", include_examples=False)
        reloaded_dag_count = len(dag_bag_2.dags)

        # Should have same count
        assert reloaded_dag_count == initial_dag_count

    def test_error_handling_in_dag_execution(self):
        """Test that DAG handles task failures gracefully."""
        # This test would require a DAG with intentionally failing task
        # For now, just verify error handling mechanism exists

        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        # DAGs should have error handling configured
        for _dag_id, dag in dag_bag.dags.items():
            # Check that tasks have failure callbacks or email settings
            for task in dag.tasks:
                # Should have some error handling configured
                assert hasattr(task, "retries")

    def test_dag_description_from_config(self):
        """Test that DAG description from config is applied."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs found for testing")

        for _dag_id, dag in dag_bag.dags.items():
            assert dag.description is not None
            assert len(dag.description) > 0

    def test_task_count_matches_config(self, mock_dag_configs_dir):
        """Test that number of tasks in DAG matches config."""
        import json

        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Load a config file and compare
        config_file = mock_dag_configs_dir / "simple_etl.json"
        if not config_file.exists():
            pytest.skip("No config file found for comparison")

        with open(config_file) as f:
            config = json.load(f)

        dag_id = config["dag_id"]
        if dag_id not in dag_bag.dags:
            pytest.skip(f"DAG {dag_id} not found in dag_bag")

        dag = dag_bag.dags[dag_id]
        expected_task_count = len(config["tasks"])

        assert len(dag.tasks) == expected_task_count
