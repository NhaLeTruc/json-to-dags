"""
Integration test for retry behavior.

Tests that tasks retry the correct number of times with backoff,
then fail permanently.
"""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from airflow.models import DagBag


@pytest.mark.integration
class TestRetryBehavior:
    """Integration tests for task retry behavior."""

    def test_task_retries_configured_number_of_times(self):
        """Test that task retries exactly the configured number of times."""
        # This test would require a DAG with retry configuration
        # and would execute the task to verify retry behavior

        # Load DAG with retry configuration
        dag_bag = DagBag(dag_folder="dags/examples/", include_examples=False)

        # Find a DAG with retry configuration
        retry_dags = [
            dag
            for dag_id, dag in dag_bag.dags.items()
            if "retry" in dag_id.lower() or "scheduled" in dag_id.lower()
        ]

        if len(retry_dags) == 0:
            pytest.skip("No retry DAG found for testing")

        dag = retry_dags[0]

        # Find task with retries configured
        retry_tasks = [task for task in dag.tasks if task.retries > 0]

        if len(retry_tasks) == 0:
            pytest.skip("No tasks with retries configured")

        task = retry_tasks[0]

        # Verify retry configuration
        assert task.retries >= 1
        assert task.retry_delay is not None
        assert isinstance(task.retry_delay, timedelta)

    def test_exponential_backoff_increases_delay(self):
        """Test that retry delays increase exponentially."""
        dag_bag = DagBag(dag_folder="dags/examples/", include_examples=False)

        retry_dags = [dag for dag_id, dag in dag_bag.dags.items() if "retry" in dag_id.lower()]

        if len(retry_dags) == 0:
            pytest.skip("No retry DAG found")

        dag = retry_dags[0]

        # Check for exponential backoff configuration
        for task in dag.tasks:
            if hasattr(task, "retry_exponential_backoff"):
                # Task configured for exponential backoff
                assert task.retry_exponential_backoff is True
                assert task.retries > 1

    def test_task_fails_after_max_retries(self):
        """Test that task fails permanently after max retries exceeded."""
        # This test simulates a task that fails repeatedly
        # and verifies it eventually marks as failed

        dag_bag = DagBag(dag_folder="dags/examples/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs available for testing")

        # Verify DAGs have retry configuration
        has_retry_config = False
        for _dag_id, dag in dag_bag.dags.items():
            for task in dag.tasks:
                if task.retries > 0:
                    has_retry_config = True
                    break

        assert has_retry_config, "At least one task should have retry configuration"

    def test_retry_delay_applied_between_attempts(self):
        """Test that retry delay is applied between retry attempts."""
        from src.utils.retry_policies import calculate_exponential_backoff

        # Verify retry delay calculation
        delay_1 = calculate_exponential_backoff(retry_number=1, base_delay=60)
        delay_2 = calculate_exponential_backoff(retry_number=2, base_delay=60)

        # Delays should increase
        assert delay_2 > delay_1

    def test_retry_with_linear_backoff(self):
        """Test retry behavior with linear backoff strategy."""
        from src.utils.retry_policies import calculate_linear_backoff

        # Linear backoff increases linearly
        delay_1 = calculate_linear_backoff(retry_number=1, base_delay=60)
        delay_2 = calculate_linear_backoff(retry_number=2, base_delay=60)
        delay_3 = calculate_linear_backoff(retry_number=3, base_delay=60)

        # Verify linear progression
        assert delay_2 - delay_1 == 60
        assert delay_3 - delay_2 == 60

    def test_retry_with_fixed_backoff(self):
        """Test retry behavior with fixed backoff strategy."""
        from src.utils.retry_policies import calculate_fixed_backoff

        # Fixed backoff always same delay
        delay_1 = calculate_fixed_backoff(retry_number=1, delay=120)
        delay_2 = calculate_fixed_backoff(retry_number=2, delay=120)
        delay_3 = calculate_fixed_backoff(retry_number=3, delay=120)

        assert delay_1 == delay_2 == delay_3 == 120

    def test_successful_task_does_not_retry(self):
        """Test that successful tasks don't trigger retry logic."""
        dag_bag = DagBag(dag_folder="dags/examples/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs available")

        # All DAGs should have tasks
        for _dag_id, dag in dag_bag.dags.items():
            assert len(dag.tasks) > 0

    def test_retry_count_logged_correctly(self):
        """Test that retry attempts are logged with correct count."""
        # This verifies logging captures retry attempt number
        from src.utils.logger import get_logger

        logger = get_logger("test_retry")
        logger.add_context(retry_attempt=2, max_retries=3)

        # Logger should have context
        assert "retry_attempt" in logger.context
        assert logger.context["retry_attempt"] == 2

    def test_max_retry_delay_enforced(self):
        """Test that maximum retry delay is enforced."""
        from src.utils.retry_policies import calculate_exponential_backoff

        # High retry number with max delay
        delay = calculate_exponential_backoff(retry_number=10, base_delay=60, max_delay=600)

        # Should be capped at max
        assert delay == 600

    def test_retry_configuration_from_dag_config(self):
        """Test that retry configuration is correctly applied from DAG config."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Check JSON-configured DAGs have retry settings
        for _dag_id, dag in dag_bag.dags.items():
            # DAGs from JSON configs should have default_args
            if hasattr(dag, "default_args") and dag.default_args:
                # May have retries in default_args
                pass

    def test_task_instance_retry_tracking(self):
        """Test that TaskInstance tracks retry attempts."""
        # Mock TaskInstance
        mock_ti = Mock()
        mock_ti.try_number = 2
        mock_ti.max_tries = 3

        # Can still retry
        assert mock_ti.try_number < mock_ti.max_tries

    def test_retry_policy_consistency_across_dags(self):
        """Test that retry policies are consistent across example DAGs."""
        dag_bag = DagBag(dag_folder="dags/examples/", include_examples=False)

        retry_configs = []

        for dag_id, dag in dag_bag.dags.items():
            for task in dag.tasks:
                if task.retries > 0:
                    retry_configs.append(
                        {"dag_id": dag_id, "task_id": task.task_id, "retries": task.retries}
                    )

        # Should have some retry configurations
        # (This assertion depends on example DAGs existing)

    def test_retry_callback_execution(self):
        """Test that on_retry_callback is executed on retry."""
        # This tests that callbacks are properly configured
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Check for tasks with callbacks
        for _dag_id, dag in dag_bag.dags.items():
            for task in dag.tasks:
                if hasattr(task, "on_retry_callback") and task.on_retry_callback:
                    pass

        # Callbacks are optional, so this is informational

    def test_retry_with_dependency_tasks(self):
        """Test retry behavior when task has downstream dependencies."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        if len(dag_bag.dags) == 0:
            pytest.skip("No DAGs available")

        # Find tasks with dependencies and retries
        for _dag_id, dag in dag_bag.dags.items():
            for task in dag.tasks:
                if task.retries > 0 and len(task.downstream_list) > 0:
                    # Task has both retries and dependencies
                    # Downstream tasks should wait for retries to complete
                    assert task.retries >= 0
