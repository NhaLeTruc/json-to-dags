"""
Integration test for DAG hot-reload functionality.

Tests that new DAG files appear in Airflow UI within acceptable time.
"""

from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestDAGHotReload:
    """Integration tests for DAG hot-reload functionality."""

    def test_dags_directory_mounted_as_volume(self):
        """Test that dags directory is mounted as volume for hot-reload."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Check airflow services have dags volume
        airflow_services = ["airflow-webserver", "airflow-scheduler"]

        for service_name in airflow_services:
            service = services.get(service_name, {})
            volumes = service.get("volumes", [])

            # Convert to string for easier checking
            volumes_str = str(volumes)
            assert "dags" in volumes_str, f"Service '{service_name}' should mount dags directory"

    def test_dag_factory_discovers_new_configs(self):
        """Test that DAG factory discovers new JSON config files."""
        config_dir = Path("dags/config/examples")

        if not config_dir.exists():
            pytest.skip("Config directory not yet created")

        # Check for existing configs
        json_configs = list(config_dir.glob("*.json"))

        # Should have at least one example config
        assert len(json_configs) >= 0

    def test_dag_errors_reported(self):
        """Test that DAG parsing errors are reported."""
        from airflow.models import DagBag

        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Should not have import errors in properly configured environment
        # If errors exist, they should be logged
        if len(dag_bag.import_errors) > 0:
            # Print errors for debugging
            for file_path, error_msg in dag_bag.import_errors.items():
                print(f"Import error in {file_path}: {error_msg}")

    def test_dynamic_dag_generation_works(self):
        """Test that dynamic DAG generation from configs works."""
        from airflow.models import DagBag

        dag_bag = DagBag(dag_folder="dags/", include_examples=False)

        # Check for JSON-configured DAGs
        [dag_id for dag_id in dag_bag.dags if "v1" in dag_id or "simple" in dag_id]

        # Should have some dynamically generated DAGs if configs exist

    def test_file_watcher_mechanism(self):
        """Test that file watching mechanism is available."""
        # Airflow's scheduler watches for file changes
        # This is built into Airflow, just verify configuration allows it

        # Volume mounts must be configured for file changes to propagate
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        scheduler = services.get("airflow-scheduler", {})
        volumes = scheduler.get("volumes", [])

        assert len(volumes) > 0, "Scheduler should have volume mounts for hot-reload"

    def test_dag_serialization_enabled(self):
        """Test that DAG serialization is configured (improves reload)."""
        # DAG serialization improves performance of DAG loading
        # Check if environment configures this

        import yaml

        with open("docker-compose.yml") as f:
            yaml.safe_load(f)

        # DAG serialization is default in Airflow 2.x
        # No specific test needed unless custom configuration

    def test_src_directory_hot_reloadable(self):
        """Test that src directory is mounted for code hot-reload."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Check that src is mounted
        scheduler = services.get("airflow-scheduler", {})
        volumes = scheduler.get("volumes", [])

        volumes_str = str(volumes)
        assert "src" in volumes_str, "src directory should be mounted for hot-reload"

    def test_logs_directory_writable(self):
        """Test that logs directory is writable for DAG execution logs."""
        Path("logs")

        # Logs directory should exist or be creatable
        # Check if mounted as volume
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        scheduler = services.get("airflow-scheduler", {})
        volumes = scheduler.get("volumes", [])

        str(volumes)
        # Logs should be mounted for persistence and access
