"""
JSON DAG configuration validator.

Validates DAG configurations against JSON schema, checks for circular dependencies,
and verifies task references.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import ValidationError as JSONSchemaValidationError

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    errors: list[str]
    config: dict[str, Any] | None = None


class ConfigValidator:
    """
    Validator for DAG JSON configurations.

    Validates configurations against JSON schema and performs semantic validation
    including circular dependency detection and task reference verification.
    """

    def __init__(self, schema_path: str | None = None) -> None:
        """
        Initialize configuration validator.

        Args:
            schema_path: Path to JSON schema file (default: dags/config/schemas/dag-config-schema.json)
        """
        if schema_path is None:
            schema_path = str(
                Path(__file__).parent.parent / "config" / "schemas" / "dag-config-schema.json"
            )

        self.schema_path = schema_path
        self.schema = self._load_schema()
        logger.debug("ConfigValidator initialized", schema_path=schema_path)

    def _load_schema(self) -> dict[str, Any]:
        """
        Load JSON schema from file.

        Returns:
            JSON schema dict

        Raises:
            FileNotFoundError: If schema file not found
            json.JSONDecodeError: If schema is invalid JSON
        """
        schema_file = Path(self.schema_path)
        if not schema_file.exists():
            msg = f"Schema file not found: {self.schema_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        try:
            with schema_file.open("r") as f:
                schema = json.load(f)
            logger.debug("JSON schema loaded successfully")
            return schema
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in schema file: {self.schema_path}"
            logger.error(msg, error=str(e))
            raise

    def validate(self, config: dict[str, Any]) -> ValidationResult:
        """
        Validate DAG configuration.

        Args:
            config: DAG configuration dict

        Returns:
            ValidationResult with validation status and any errors
        """
        errors: list[str] = []

        # Step 1: Validate against JSON schema
        try:
            jsonschema.validate(instance=config, schema=self.schema)
            logger.debug("JSON schema validation passed", dag_id=config.get("dag_id"))
        except JSONSchemaValidationError as e:
            error_msg = f"JSON schema validation failed: {e.message}"
            errors.append(error_msg)
            logger.warning("Schema validation failed", dag_id=config.get("dag_id"), error=e.message)
            # Return early on schema validation failure
            return ValidationResult(is_valid=False, errors=errors, config=config)

        # Step 2: Semantic validation
        dag_id = config.get("dag_id", "unknown")

        # Check for empty tasks list
        tasks = config.get("tasks", [])
        if not tasks or len(tasks) == 0:
            errors.append(f"DAG '{dag_id}' has no tasks defined")

        # Check for duplicate task IDs
        task_ids = [task.get("task_id") for task in tasks]
        duplicate_ids = [task_id for task_id in task_ids if task_ids.count(task_id) > 1]
        if duplicate_ids:
            errors.append(f"Duplicate task IDs found in DAG '{dag_id}': {set(duplicate_ids)}")

        # Build task ID set for dependency validation
        task_id_set = set(task_ids)

        # Check for non-existent dependencies
        for task in tasks:
            task_id = task.get("task_id")
            dependencies = task.get("dependencies", [])
            for dep in dependencies:
                if dep not in task_id_set:
                    errors.append(f"Task '{task_id}' references non-existent dependency: '{dep}'")

        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies(config)
        if circular_deps:
            errors.append(f"Circular dependencies detected in DAG '{dag_id}': {circular_deps}")

        # Determine validation result
        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Configuration validation passed", dag_id=dag_id, task_count=len(tasks))
        else:
            logger.warning(
                "Configuration validation failed", dag_id=dag_id, error_count=len(errors)
            )

        return ValidationResult(is_valid=is_valid, errors=errors, config=config)

    def _detect_circular_dependencies(self, config: dict[str, Any]) -> str | None:
        """
        Detect circular dependencies in task graph.

        Uses depth-first search to detect cycles.

        Args:
            config: DAG configuration dict

        Returns:
            Description of circular dependency if found, None otherwise
        """
        tasks = config.get("tasks", [])

        # Build adjacency list
        graph: dict[str, list[str]] = {}
        for task in tasks:
            task_id = task.get("task_id")
            dependencies = task.get("dependencies", [])
            graph[task_id] = dependencies

        # Track visited nodes and recursion stack
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycle_path: list[str] = []

        def dfs(node: str, path: list[str]) -> bool:
            """Depth-first search to detect cycle."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Visit all dependencies (upstream tasks)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Cycle detected
                    cycle_start = path.index(neighbor)
                    cycle_path.extend(path[cycle_start:] + [neighbor])
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        # Check each task for cycles
        for task_id in graph:
            if task_id not in visited and dfs(task_id, []):
                return " -> ".join(cycle_path)

        return None

    def validate_from_file(self, config_path: str) -> ValidationResult:
        """
        Validate DAG configuration from JSON file.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            ValidationResult with validation status and any errors
        """
        config_file = Path(config_path)

        if not config_file.exists():
            error_msg = f"Configuration file not found: {config_path}"
            logger.error(error_msg)
            return ValidationResult(is_valid=False, errors=[error_msg])

        try:
            with config_file.open("r") as f:
                config = json.load(f)
            logger.debug("Configuration file loaded", config_path=config_path)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in configuration file: {config_path} - {str(e)}"
            logger.error(error_msg)
            return ValidationResult(is_valid=False, errors=[error_msg])

        return self.validate(config)


# DESIGN-005 fix: Use lru_cache for thread-safe singleton pattern
@lru_cache(maxsize=1)
def get_default_validator() -> ConfigValidator:
    """
    Get or create global ConfigValidator instance.

    Uses lru_cache for thread-safe singleton pattern.

    Returns:
        Singleton ConfigValidator instance
    """
    return ConfigValidator()
