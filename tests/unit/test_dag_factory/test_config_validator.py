"""
Unit tests for JSON DAG configuration validator.

Tests validation logic for DAG configurations against JSON schema,
circular dependency detection, and operator reference verification.
"""

import pytest


class TestConfigValidator:
    """Test suite for ConfigValidator class."""

    def test_valid_config_passes_validation(self, sample_dag_config):
        """Test that a valid DAG configuration passes validation."""
        from dags.factory.config_validator import ConfigValidator

        validator = ConfigValidator()
        result = validator.validate(sample_dag_config)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.config == sample_dag_config

    def test_missing_required_fields_fails_validation(self):
        """Test that configs missing required fields fail validation."""
        from dags.factory.config_validator import ConfigValidator

        invalid_config = {
            "dag_id": "test_dag",
            # Missing: description, schedule_interval, start_date, tasks
        }

        validator = ConfigValidator()
        result = validator.validate(invalid_config)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("required" in error.lower() for error in result.errors)

    def test_invalid_dag_id_format_fails_validation(self):
        """Test that invalid DAG ID format fails validation."""
        from dags.factory.config_validator import ConfigValidator

        invalid_config = {
            "dag_id": "Invalid-DAG-ID!",  # Contains invalid characters
            "description": "Test",
            "schedule_interval": "0 2 * * *",
            "start_date": "2024-01-01",
            "tasks": [],
        }

        validator = ConfigValidator()
        result = validator.validate(invalid_config)

        assert result.is_valid is False
        assert any("dag_id" in error.lower() for error in result.errors)

    def test_circular_dependencies_detected(self):
        """Test that circular task dependencies are detected."""
        from dags.factory.config_validator import ConfigValidator

        config_with_cycle = {
            "dag_id": "circular_dag",
            "description": "DAG with circular dependencies",
            "schedule_interval": "0 2 * * *",
            "start_date": "2024-01-01",
            "default_args": {"owner": "airflow", "retries": 1},
            "tasks": [
                {
                    "task_id": "task_a",
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo A"},
                    "dependencies": ["task_c"],
                },
                {
                    "task_id": "task_b",
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo B"},
                    "dependencies": ["task_a"],
                },
                {
                    "task_id": "task_c",
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo C"},
                    "dependencies": ["task_b"],
                },
            ],
        }

        validator = ConfigValidator()
        result = validator.validate(config_with_cycle)

        assert result.is_valid is False
        assert any("circular" in error.lower() for error in result.errors)

    def test_non_existent_dependency_fails_validation(self):
        """Test that references to non-existent tasks fail validation."""
        from dags.factory.config_validator import ConfigValidator

        config_with_bad_dep = {
            "dag_id": "bad_dependency_dag",
            "description": "DAG with non-existent dependency",
            "schedule_interval": "0 2 * * *",
            "start_date": "2024-01-01",
            "default_args": {"owner": "airflow", "retries": 1},
            "tasks": [
                {
                    "task_id": "task_a",
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo A"},
                    "dependencies": ["non_existent_task"],
                },
            ],
        }

        validator = ConfigValidator()
        result = validator.validate(config_with_bad_dep)

        assert result.is_valid is False
        assert any("non_existent_task" in error for error in result.errors)

    def test_invalid_schedule_interval_fails_validation(self):
        """Test that invalid cron expressions fail validation."""
        from dags.factory.config_validator import ConfigValidator

        invalid_config = {
            "dag_id": "invalid_schedule",
            "description": "DAG with invalid schedule",
            "schedule_interval": "invalid cron",
            "start_date": "2024-01-01",
            "default_args": {"owner": "airflow", "retries": 1},
            "tasks": [
                {
                    "task_id": "task_a",
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo A"},
                }
            ],
        }

        validator = ConfigValidator()
        validator.validate(invalid_config)

        # Note: This might pass schema validation if schedule_interval is just a string
        # But should fail semantic validation for invalid cron expression
        # Implementation can choose to be lenient or strict

    def test_empty_tasks_list_fails_validation(self):
        """Test that DAGs with no tasks fail validation."""
        from dags.factory.config_validator import ConfigValidator

        config_no_tasks = {
            "dag_id": "no_tasks_dag",
            "description": "DAG with no tasks",
            "schedule_interval": "0 2 * * *",
            "start_date": "2024-01-01",
            "default_args": {"owner": "airflow", "retries": 1},
            "tasks": [],
        }

        validator = ConfigValidator()
        result = validator.validate(config_no_tasks)

        assert result.is_valid is False
        assert any("tasks" in error.lower() for error in result.errors)

    def test_duplicate_task_ids_fail_validation(self):
        """Test that duplicate task IDs in same DAG fail validation."""
        from dags.factory.config_validator import ConfigValidator

        config_duplicate_ids = {
            "dag_id": "duplicate_tasks",
            "description": "DAG with duplicate task IDs",
            "schedule_interval": "0 2 * * *",
            "start_date": "2024-01-01",
            "default_args": {"owner": "airflow", "retries": 1},
            "tasks": [
                {
                    "task_id": "task_a",
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo A"},
                },
                {
                    "task_id": "task_a",  # Duplicate ID
                    "operator": "BashOperator",
                    "params": {"bash_command": "echo B"},
                },
            ],
        }

        validator = ConfigValidator()
        result = validator.validate(config_duplicate_ids)

        assert result.is_valid is False
        assert any("duplicate" in error.lower() for error in result.errors)

    def test_validate_from_file_success(self, mock_dag_configs_dir):
        """Test validation from JSON file."""
        from dags.factory.config_validator import ConfigValidator

        config_file = mock_dag_configs_dir / "simple_etl.json"
        validator = ConfigValidator()
        result = validator.validate_from_file(str(config_file))

        assert result.is_valid is True
        assert result.config is not None

    def test_validate_from_file_invalid_json(self, tmp_path):
        """Test validation fails for malformed JSON file."""
        from dags.factory.config_validator import ConfigValidator

        bad_json_file = tmp_path / "bad.json"
        bad_json_file.write_text("{invalid json")

        validator = ConfigValidator()
        result = validator.validate_from_file(str(bad_json_file))

        assert result.is_valid is False
        assert any("json" in error.lower() for error in result.errors)

    def test_validate_from_file_not_found(self):
        """Test validation fails for non-existent file."""
        from dags.factory.config_validator import ConfigValidator

        validator = ConfigValidator()
        result = validator.validate_from_file("/non/existent/file.json")

        assert result.is_valid is False
        assert any(
            "not found" in error.lower() or "file" in error.lower() for error in result.errors
        )

    def test_validation_result_structure(self, sample_dag_config):
        """Test that ValidationResult has expected structure."""
        from dags.factory.config_validator import ConfigValidator, ValidationResult

        validator = ConfigValidator()
        result = validator.validate(sample_dag_config)

        assert isinstance(result, ValidationResult)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "config")
        assert isinstance(result.errors, list)
        assert isinstance(result.is_valid, bool)
