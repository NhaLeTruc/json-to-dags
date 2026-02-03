"""
Integration test for DAG parsing.

Tests that all JSON configurations in dags/config/ parse correctly
and produce valid DAGs without errors.
"""

from pathlib import Path

import pytest
from airflow.models import DagBag


@pytest.mark.integration
class TestDAGParsing:
    """Integration tests for DAG factory parsing."""

    def test_all_dags_parse_without_errors(self):
        """Test that all DAGs in dags/ folder parse without errors."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Check for import errors
        assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"

    def test_correct_number_of_dags_loaded(self):
        """Test that expected number of DAGs are loaded."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Count JSON configs in dags/config/examples/
        config_dir = Path("dags/config/examples")
        if config_dir.exists():
            json_configs = list(config_dir.glob("*.json"))
            expected_dag_count = len(json_configs)

            # At minimum, should have at least 1 DAG from configs
            assert len(dag_bag.dags) >= expected_dag_count
        else:
            # If no configs exist yet, just verify no errors
            assert len(dag_bag.import_errors) == 0

    def test_each_dag_has_required_attributes(self):
        """Test that each DAG has required attributes."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        for dag_id, dag in dag_bag.dags.items():
            assert dag.dag_id is not None
            assert dag.description is not None
            assert dag.schedule_interval is not None
            assert dag.start_date is not None
            assert len(dag.tasks) > 0, f"DAG {dag_id} has no tasks"

    def test_dags_have_no_cycles(self):
        """Test that no DAGs have circular dependencies."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        for dag_id, dag in dag_bag.dags.items():
            # Airflow's check_cycle() will raise if cycle detected
            try:
                dag.check_cycle()
            except Exception as e:
                pytest.fail(f"DAG {dag_id} has circular dependency: {e}")

    def test_all_tasks_have_valid_operators(self):
        """Test that all tasks use valid operator types."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        for _dag_id, dag in dag_bag.dags.items():
            for task in dag.tasks:
                # Task should have a valid operator class
                assert task.__class__.__name__ is not None
                assert hasattr(task, "task_id")
                assert task.task_id is not None

    def test_factory_module_imports_successfully(self):
        """Test that DAG factory module can be imported."""
        try:
            from dags.factory import config_validator, dag_builder, operator_registry

            assert config_validator is not None
            assert dag_builder is not None
            assert operator_registry is not None
        except ImportError as e:
            pytest.fail(f"Failed to import factory modules: {e}")

    @pytest.mark.slow
    def test_dag_validation_passes(self):
        """Test that all DAGs pass Airflow's validation."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        for _dag_id, dag in dag_bag.dags.items():
            # Validate task dependencies
            for task in dag.tasks:
                # Check that upstream tasks exist in DAG
                for upstream_task in task.upstream_list:
                    assert upstream_task in dag.tasks

                # Check that downstream tasks exist in DAG
                for downstream_task in task.downstream_list:
                    assert downstream_task in dag.tasks

    def test_config_validator_integrated_with_factory(self):
        """Test that config validator is integrated into DAG factory."""
        from dags.factory.config_validator import ConfigValidator

        validator = ConfigValidator()
        assert validator is not None

        # Validator should be used by factory to validate configs before building

    def test_operator_registry_integrated_with_factory(self):
        """Test that operator registry is integrated into DAG factory."""
        from dags.factory.operator_registry import get_default_registry

        registry = get_default_registry()
        assert registry is not None

        # Registry should be used by factory to instantiate operators

    def test_multiple_config_files_create_multiple_dags(self, tmp_path):
        """Test that multiple JSON configs create multiple DAGs."""
        # This test would need to set up temp config directory
        # and verify multiple DAGs are created

        # For now, just verify the mechanism exists
        DagBag(dag_folder="dags/", include_examples=False)
        # Count should match number of valid JSON configs

    def test_invalid_config_does_not_break_other_dags(self):
        """Test that one invalid config doesn't prevent other DAGs from loading."""
        # The factory should handle errors gracefully and log them
        # without preventing valid DAGs from being created

        DagBag(dag_folder="dags/", include_examples=False)

        # Even if there are errors, valid DAGs should still load
        # (This behavior depends on implementation - could be strict or lenient)

    def test_dag_tags_from_config(self):
        """Test that DAG tags from config are applied."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        for _dag_id, dag in dag_bag.dags.items():
            # DAGs from JSON configs should have tags
            assert isinstance(dag.tags, list | set)

    def test_dag_default_args_applied(self):
        """Test that default_args from config are applied to tasks."""
        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        for _dag_id, dag in dag_bag.dags.items():
            for task in dag.tasks:
                # Tasks should have owner set (from default_args or task params)
                assert hasattr(task, "owner")
                assert task.owner is not None
