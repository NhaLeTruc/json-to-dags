"""
DAG builder factory for creating DAGs from JSON configurations.

Reads JSON configurations, validates them, instantiates DAGs and tasks,
and sets up dependencies.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.models import BaseOperator

from factory.config_validator import ValidationResult, get_default_validator
from factory.operator_registry import get_default_registry
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DAGBuildError(Exception):
    """Raised when DAG cannot be built from configuration."""

    pass


class CircularDependencyError(DAGBuildError):
    """Raised when circular dependencies detected in task graph."""

    pass


class DAGBuilder:
    """
    Builder for creating Airflow DAGs from JSON configurations.

    Handles DAG instantiation, task creation, dependency resolution,
    and error handling.
    """

    def __init__(self) -> None:
        """Initialize DAG builder with validator and operator registry."""
        self.validator = get_default_validator()
        self.operator_registry = get_default_registry()
        logger.debug("DAGBuilder initialized")

    def build_dag(self, config: dict[str, Any]) -> DAG:
        """
        Build DAG from configuration dict.

        Args:
            config: DAG configuration dict

        Returns:
            Configured Airflow DAG instance

        Raises:
            DAGBuildError: If DAG cannot be built
            CircularDependencyError: If circular dependencies detected
        """
        dag_id = config.get("dag_id", "unknown")
        logger.info("Building DAG from config", dag_id=dag_id)

        # Step 1: Validate configuration
        validation_result: ValidationResult = self.validator.validate(config)
        if not validation_result.is_valid:
            error_msg = (
                f"DAG '{dag_id}' configuration invalid: {', '.join(validation_result.errors)}"
            )
            logger.error(error_msg)
            raise DAGBuildError(error_msg)

        # Step 2: Parse DAG-level configuration
        try:
            dag_kwargs = self._build_dag_kwargs(config)
        except Exception as e:
            error_msg = f"Failed to parse DAG configuration for '{dag_id}': {str(e)}"
            logger.error(error_msg)
            raise DAGBuildError(error_msg) from e

        # Step 3: Create DAG instance
        try:
            dag = DAG(**dag_kwargs)
            logger.debug("DAG instance created", dag_id=dag_id)
        except Exception as e:
            error_msg = f"Failed to create DAG '{dag_id}': {str(e)}"
            logger.error(error_msg)
            raise DAGBuildError(error_msg) from e

        # Step 4: Create tasks
        tasks: dict[str, BaseOperator] = {}
        task_configs = config.get("tasks", [])

        for task_config in task_configs:
            try:
                task = self._create_task(task_config, dag, config.get("default_args", {}))
                tasks[task.task_id] = task
                logger.debug("Task created", task_id=task.task_id, operator=task.__class__.__name__)
            except Exception as e:
                error_msg = f"Failed to create task '{task_config.get('task_id')}' in DAG '{dag_id}': {str(e)}"
                logger.error(error_msg)
                raise DAGBuildError(error_msg) from e

        # Step 5: Set up task dependencies
        try:
            self._set_dependencies(task_configs, tasks, dag_id)
            logger.debug("Task dependencies configured", dag_id=dag_id, task_count=len(tasks))
        except Exception as e:
            error_msg = f"Failed to set dependencies for DAG '{dag_id}': {str(e)}"
            logger.error(error_msg)
            raise DAGBuildError(error_msg) from e

        logger.info("DAG built successfully", dag_id=dag_id, task_count=len(tasks))
        return dag

    def _build_dag_kwargs(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Build DAG constructor kwargs from configuration.

        Args:
            config: DAG configuration dict

        Returns:
            Dict of kwargs for DAG constructor
        """
        dag_id = config["dag_id"]
        description = config["description"]
        schedule_interval = config["schedule_interval"]
        start_date_str = config["start_date"]

        # Parse start date
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

        # Parse default_args
        default_args = config.get("default_args", {})
        processed_default_args = self._process_default_args(default_args)

        # Build DAG kwargs
        dag_kwargs = {
            "dag_id": dag_id,
            "description": description,
            "schedule": schedule_interval,  # Using 'schedule' param (Airflow 2.4+, replaces schedule_interval)
            "start_date": start_date,
            "default_args": processed_default_args,
            "catchup": config.get("catchup", False),
            "tags": config.get("tags", []),
        }

        return dag_kwargs

    def _process_default_args(self, default_args: dict[str, Any]) -> dict[str, Any]:
        """
        Process default_args, converting special types.

        Args:
            default_args: Raw default args from config

        Returns:
            Processed default args
        """
        processed = default_args.copy()

        # Convert retry_delay_minutes to timedelta
        if "retry_delay_minutes" in processed:
            retry_minutes = processed.pop("retry_delay_minutes")
            processed["retry_delay"] = timedelta(minutes=retry_minutes)

        return processed

    def _create_task(
        self,
        task_config: dict[str, Any],
        dag: DAG,
        default_args: dict[str, Any],
    ) -> BaseOperator:
        """
        Create task from configuration.

        Args:
            task_config: Task configuration dict
            dag: Parent DAG instance
            default_args: Default args to merge with task params

        Returns:
            Instantiated task operator

        Raises:
            DAGBuildError: If task cannot be created
        """
        task_id = task_config["task_id"]
        operator_name = task_config["operator"]
        task_params = task_config.get("params", {})

        # Merge default args with task params (task params take precedence)
        # Note: Some args go to DAG default_args, others to task directly
        merged_params = {**task_params}

        # Handle common task-level overrides
        if "retries" in task_params:
            merged_params["retries"] = task_params["retries"]
        if "retry_delay_minutes" in task_params:
            merged_params["retry_delay"] = timedelta(minutes=task_params.pop("retry_delay_minutes"))

        # Create task using operator registry
        try:
            task = self.operator_registry.create_operator(
                operator_name=operator_name,
                task_id=task_id,
                dag=dag,
                params=merged_params,
            )
            return task
        except Exception as e:
            raise DAGBuildError(f"Failed to create task '{task_id}': {str(e)}") from e

    def _set_dependencies(
        self,
        task_configs: list[dict[str, Any]],
        tasks: dict[str, BaseOperator],
        dag_id: str,
    ) -> None:
        """
        Set up task dependencies based on configuration.

        Args:
            task_configs: List of task configurations
            tasks: Dict of task_id -> task instance
            dag_id: DAG ID for error messages

        Raises:
            DAGBuildError: If dependency references non-existent task
        """
        for task_config in task_configs:
            task_id = task_config["task_id"]
            dependencies = task_config.get("dependencies", [])

            if not dependencies:
                continue

            task = tasks[task_id]

            # Set upstream dependencies
            for upstream_task_id in dependencies:
                if upstream_task_id not in tasks:
                    raise DAGBuildError(
                        f"Task '{task_id}' in DAG '{dag_id}' references "
                        f"non-existent dependency: '{upstream_task_id}'"
                    )

                upstream_task = tasks[upstream_task_id]
                task.set_upstream(upstream_task)

    def build_dag_from_file(self, config_path: str) -> DAG:
        """
        Build DAG from JSON configuration file.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            Configured Airflow DAG instance

        Raises:
            DAGBuildError: If DAG cannot be built
            FileNotFoundError: If config file not found
        """
        config_file = Path(config_path)

        if not config_file.exists():
            error_msg = f"Configuration file not found: {config_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with config_file.open("r") as f:
                config = json.load(f)
            logger.debug("Configuration loaded from file", config_path=config_path)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in configuration file: {config_path} - {str(e)}"
            logger.error(error_msg)
            raise DAGBuildError(error_msg) from e

        return self.build_dag(config)


# Convenience function
def build_dag_from_config(config: dict[str, Any]) -> DAG:
    """
    Build DAG from configuration dict.

    Convenience function that creates a DAGBuilder and builds the DAG.

    Args:
        config: DAG configuration dict

    Returns:
        Configured Airflow DAG instance

    Raises:
        DAGBuildError: If DAG cannot be built
    """
    builder = DAGBuilder()
    return builder.build_dag(config)


def build_dag_from_file(config_path: str) -> DAG:
    """
    Build DAG from JSON configuration file.

    Convenience function that creates a DAGBuilder and builds the DAG.

    Args:
        config_path: Path to JSON configuration file

    Returns:
        Configured Airflow DAG instance

    Raises:
        DAGBuildError: If DAG cannot be built
    """
    builder = DAGBuilder()
    return builder.build_dag_from_file(config_path)
