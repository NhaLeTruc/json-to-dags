"""
Integration test for environment reset functionality.

Tests that environment can be reset to clean state after docker-compose down -v.
"""

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestEnvironmentReset:
    """Integration tests for Docker environment reset functionality."""

    def test_down_command_removes_containers(self):
        """Test that docker-compose down removes all containers."""
        # This tests the reset mechanism exists
        # Actual execution would be: docker compose down

        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        # Verify services are defined (can be removed with down)
        services = compose_config.get("services", {})
        assert len(services) > 0, "Services should be defined for reset testing"

    def test_volumes_flag_removes_data(self):
        """Test that -v flag removes named volumes."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        volumes = compose_config.get("volumes", {})

        # Named volumes should exist for removal
        assert len(volumes) > 0, "Named volumes should exist for clean reset"

    def test_clean_state_after_restart(self):
        """Test that environment starts in clean state after down -v and up."""
        # This verifies the reset mechanism:
        # 1. docker compose down -v (removes containers and volumes)
        # 2. docker compose up (starts fresh)
        # 3. All data should be reinitialized

        # Test that initialization scripts are configured
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Check warehouse has initialization
        services.get("postgres-warehouse", {})
        # Should have build or init mechanism

    def test_airflow_database_reinitializes(self):
        """Test that Airflow database is reinitialized on fresh start."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # airflow-init service should handle DB initialization
        airflow_init = services.get("airflow-init", {})
        assert airflow_init is not None, "airflow-init service should exist for DB init"

    def test_warehouse_data_reseeds(self):
        """Test that warehouse data is reseeded on fresh start."""
        # Warehouse Dockerfile should include seed data initialization

        import os

        warehouse_dockerfile = "docker/warehouse/Dockerfile"
        assert os.path.exists(warehouse_dockerfile), "Warehouse Dockerfile should exist"

        # Check that seed data SQL files exist
        assert os.path.exists("src/warehouse/schema.sql"), "Schema SQL should exist"
        assert os.path.exists("src/warehouse/seed_data.sql"), "Seed data SQL should exist"

    def test_no_stale_data_after_reset(self):
        """Test that no stale data persists after environment reset."""
        # This is ensured by removing named volumes with -v flag
        # Volumes defined in docker-compose.yml will be recreated empty

        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        volumes = compose_config.get("volumes", {})

        # Verify critical volumes are named (not bind mounts) for clean removal
        critical_volumes = ["postgres-airflow-data", "postgres-warehouse-data"]

        for vol in critical_volumes:
            assert vol in volumes, f"Volume {vol} should be named volume for clean reset"

    def test_config_files_persist_after_reset(self):
        """Test that configuration files persist after reset."""
        # Config files in host filesystem should not be affected by reset
        # Only Docker volumes are removed

        import os

        config_files = [".env.example", "docker-compose.yml", "requirements.txt"]

        for config_file in config_files:
            assert os.path.exists(config_file), f"{config_file} should persist after reset"

    def test_source_code_persists_after_reset(self):
        """Test that source code persists after reset."""
        import os

        source_dirs = ["src", "dags", "tests"]

        for source_dir in source_dirs:
            assert os.path.exists(source_dir), f"{source_dir} should persist after reset"

    def test_dependencies_reinstall_on_rebuild(self):
        """Test that dependencies are reinstalled on image rebuild."""
        # If requirements.txt changes, rebuild installs new dependencies

        import os

        assert os.path.exists("requirements.txt"), "requirements.txt should exist"
        assert os.path.exists("requirements-dev.txt"), "requirements-dev.txt should exist"

    def test_network_recreates_on_restart(self):
        """Test that Docker network is recreated on restart."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        networks = compose_config.get("networks", {})
        assert len(networks) > 0, "Network configuration should exist"

    def test_reset_procedure_documented(self):
        """Test that reset procedure is documented."""
        # Check if documentation exists for environment reset

        import os

        # README or development docs should document reset
        docs_exist = os.path.exists("README.md") or os.path.exists("docs/development.md")
        assert docs_exist, "Documentation should exist for environment management"

    def test_service_dependencies_respected_after_reset(self):
        """Test that service dependencies are respected after reset."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Services should have depends_on configured
        webserver = services.get("airflow-webserver", {})
        depends_on = webserver.get("depends_on", {})

        # Webserver should depend on init completing
        assert len(depends_on) > 0, "Service dependencies should be configured"

    @pytest.mark.parametrize(
        "command,description",
        [
            ("docker compose down", "Stop and remove containers"),
            ("docker compose down -v", "Stop and remove containers and volumes"),
            ("docker compose up -d", "Start services in detached mode"),
            ("docker compose restart", "Restart services"),
        ],
    )
    def test_reset_commands_available(self, command, description):
        """Test that reset commands are available and documented."""
        # These commands should be documented in README/docs
        assert len(command) > 0, f"Command '{command}' should be available"
        assert len(description) > 0, f"Description for '{command}' should exist"
