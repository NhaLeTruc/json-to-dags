"""Great Expectations integration utility for data quality validation.

This module provides helpers for loading expectation suites, validating data,
and parsing validation results for use in Airflow data quality operators.

Constitutional Compliance:
- Principle III: Data Quality Assurance (enables quality checks)
- Principle IV: Code Quality (type hints, docstrings, clean structure)
- Principle V: Observability (structured result parsing for logging)
"""

import json
import logging
from pathlib import Path
from typing import Any

from great_expectations.checkpoint import SimpleCheckpoint
from great_expectations.core import ExpectationConfiguration, ExpectationSuite
from great_expectations.core.batch import RuntimeBatchRequest
from great_expectations.data_context import DataContext
from great_expectations.data_context.types.base import (
    DataContextConfig,
    FilesystemStoreBackendDefaults,
)

logger = logging.getLogger(__name__)


class GreatExpectationsHelper:
    """Helper class for Great Expectations integration with Airflow.

    Provides methods to load expectation suites, run validations,
    and parse results into Airflow-friendly formats.

    Attributes:
        context: Great Expectations DataContext instance
        expectations_dir: Path to expectation suite JSON files
    """

    def __init__(
        self,
        context_root_dir: str | None = None,
        expectations_dir: str | None = None,
    ):
        """Initialize Great Expectations helper.

        Args:
            context_root_dir: Root directory for GE context. If None, uses in-memory config.
            expectations_dir: Directory containing expectation suite JSON files.
                Defaults to 'expectations/' relative to context root.
        """
        if context_root_dir:
            self.context = DataContext(context_root_dir=context_root_dir)
        else:
            # Create in-memory context for simpler usage
            config = DataContextConfig(
                store_backend_defaults=FilesystemStoreBackendDefaults(
                    root_directory="/tmp/great_expectations"
                )
            )
            self.context = DataContext(project_config=config)

        self.expectations_dir = Path(expectations_dir or "expectations/")
        logger.info(
            f"Initialized GreatExpectationsHelper with context_root={context_root_dir}, "
            f"expectations_dir={self.expectations_dir}"
        )

    def load_expectation_suite(self, suite_name: str) -> ExpectationSuite:
        """Load an expectation suite from JSON file or GE store.

        Args:
            suite_name: Name of the expectation suite to load

        Returns:
            ExpectationSuite object

        Raises:
            FileNotFoundError: If suite file doesn't exist
            ValueError: If suite JSON is invalid
        """
        # Try loading from context store first
        try:
            suite = self.context.get_expectation_suite(suite_name)
            logger.info(f"Loaded expectation suite '{suite_name}' from GE store")
            return suite
        except (KeyError, ValueError, FileNotFoundError) as store_error:
            logger.debug(f"Could not load from store: {store_error}")

        # Fall back to loading from JSON file
        suite_path = self.expectations_dir / f"{suite_name}.json"
        if not suite_path.exists():
            raise FileNotFoundError(
                f"Expectation suite not found: {suite_path}. " f"Tried GE store and filesystem."
            )

        with open(suite_path) as f:
            suite_dict = json.load(f)

        # Convert to ExpectationSuite object
        suite = ExpectationSuite(
            expectation_suite_name=suite_name,
            expectations=[
                ExpectationConfiguration(**exp) for exp in suite_dict.get("expectations", [])
            ],
            meta=suite_dict.get("meta", {}),
        )

        logger.info(
            f"Loaded expectation suite '{suite_name}' from {suite_path} "
            f"with {len(suite.expectations)} expectations"
        )
        return suite

    def validate_dataset(
        self,
        suite_name: str,
        dataset: Any,
        batch_request_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate a dataset against an expectation suite.

        Args:
            suite_name: Name of the expectation suite to use
            dataset: Dataset to validate (pandas DataFrame, SQL table, etc.)
            batch_request_config: Optional config for RuntimeBatchRequest

        Returns:
            Validation result dictionary with keys:
                - success: bool indicating overall validation success
                - statistics: dict with summary statistics
                - results: list of individual expectation results
                - evaluated_expectations: int count of expectations evaluated

        Raises:
            ValueError: If validation fails to execute
        """
        self.load_expectation_suite(suite_name)

        # Create batch request
        if batch_request_config is None:
            batch_request_config = {
                "datasource_name": "runtime_datasource",
                "data_connector_name": "runtime_data_connector",
                "data_asset_name": suite_name,
                "runtime_parameters": {"batch_data": dataset},
                "batch_identifiers": {"default_identifier_name": "default"},
            }

        batch_request = RuntimeBatchRequest(**batch_request_config)

        # Create and run checkpoint
        checkpoint_config = {
            "name": f"checkpoint_{suite_name}",
            "config_version": 1.0,
            "class_name": "SimpleCheckpoint",
            "expectation_suite_name": suite_name,
        }

        try:
            checkpoint = SimpleCheckpoint(
                name=checkpoint_config["name"],
                data_context=self.context,
                expectation_suite_name=suite_name,
            )

            results = checkpoint.run(validations=[{"batch_request": batch_request}])

            # Parse results
            validation_result = self._parse_validation_result(results)

            logger.info(
                f"Validation completed for suite '{suite_name}': "
                f"success={validation_result['success']}, "
                f"evaluated={validation_result['evaluated_expectations']}"
            )

            return validation_result

        except Exception as e:
            logger.error(f"Validation failed for suite '{suite_name}': {e}")
            raise ValueError(f"Validation execution failed: {e}") from e

    def _parse_validation_result(self, checkpoint_result: Any) -> dict[str, Any]:
        """Parse Great Expectations validation result into simplified format.

        Args:
            checkpoint_result: GE checkpoint run result object

        Returns:
            Dictionary with parsed results:
                - success: bool
                - statistics: dict with counts
                - results: list of expectation results
                - evaluated_expectations: int
        """
        # Extract validation result from checkpoint result
        run_results = checkpoint_result.list_validation_results()

        if not run_results:
            return {
                "success": False,
                "statistics": {"evaluated_expectations": 0, "successful_expectations": 0},
                "results": [],
                "evaluated_expectations": 0,
            }

        validation_result = run_results[0]

        # Parse statistics
        stats = validation_result.get("statistics", {})

        # Parse individual expectation results
        results_list = []
        for result in validation_result.get("results", []):
            results_list.append(
                {
                    "expectation_type": result.get("expectation_config", {}).get(
                        "expectation_type"
                    ),
                    "success": result.get("success"),
                    "exception_info": result.get("exception_info"),
                    "result": result.get("result", {}),
                }
            )

        return {
            "success": validation_result.get("success", False),
            "statistics": {
                "evaluated_expectations": stats.get("evaluated_expectations", 0),
                "successful_expectations": stats.get("successful_expectations", 0),
                "unsuccessful_expectations": stats.get("unsuccessful_expectations", 0),
                "success_percent": stats.get("success_percent", 0.0),
            },
            "results": results_list,
            "evaluated_expectations": stats.get("evaluated_expectations", 0),
        }

    def create_expectation_suite_from_config(
        self,
        suite_name: str,
        expectations_config: list[dict[str, Any]],
        save_to_store: bool = True,
    ) -> ExpectationSuite:
        """Create an expectation suite from configuration dictionary.

        Args:
            suite_name: Name for the new expectation suite
            expectations_config: List of expectation configurations as dicts
                Each dict should have 'expectation_type' and 'kwargs'
            save_to_store: If True, save suite to GE store

        Returns:
            Created ExpectationSuite object

        Example:
            expectations_config = [
                {
                    "expectation_type": "expect_column_values_to_be_unique",
                    "kwargs": {"column": "transaction_id"}
                },
                {
                    "expectation_type": "expect_column_values_to_be_between",
                    "kwargs": {"column": "quantity", "min_value": 1, "max_value": 1000}
                }
            ]
        """
        expectations = [
            ExpectationConfiguration(**exp_config) for exp_config in expectations_config
        ]

        suite = ExpectationSuite(
            expectation_suite_name=suite_name,
            expectations=expectations,
            meta={"created_by": "GreatExpectationsHelper"},
        )

        if save_to_store:
            self.context.save_expectation_suite(suite)
            logger.info(f"Saved expectation suite '{suite_name}' to GE store")

        return suite

    def get_validation_summary(self, validation_result: dict[str, Any]) -> str:
        """Generate human-readable summary of validation results.

        Args:
            validation_result: Parsed validation result from validate_dataset()

        Returns:
            Multi-line string summary of validation results
        """
        stats = validation_result["statistics"]
        success = validation_result["success"]

        summary_lines = [
            f"Validation Status: {'PASSED' if success else 'FAILED'}",
            f"Evaluated Expectations: {stats['evaluated_expectations']}",
            f"Successful: {stats['successful_expectations']}",
            f"Unsuccessful: {stats['unsuccessful_expectations']}",
            f"Success Rate: {stats['success_percent']:.1f}%",
        ]

        # Add failed expectations details
        if not success:
            summary_lines.append("\nFailed Expectations:")
            for idx, result in enumerate(validation_result["results"], 1):
                if not result["success"]:
                    summary_lines.append(
                        f"  {idx}. {result['expectation_type']}: "
                        f"{result.get('exception_info', 'No details available')}"
                    )

        return "\n".join(summary_lines)


def load_expectations_from_json(json_path: str) -> list[dict[str, Any]]:
    """Load expectation configurations from JSON file.

    Utility function for loading expectation suite configurations from
    standalone JSON files (not GE suite format).

    Args:
        json_path: Path to JSON file containing expectation configurations

    Returns:
        List of expectation configuration dictionaries

    Raises:
        FileNotFoundError: If JSON file doesn't exist
        ValueError: If JSON is invalid
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Expectations JSON file not found: {json_path}")

    with open(path) as f:
        config = json.load(f)

    # Support both direct list and wrapped format
    if isinstance(config, list):
        return config
    elif isinstance(config, dict) and "expectations" in config:
        return config["expectations"]
    else:
        raise ValueError(
            f"Invalid expectations JSON format. Expected list or dict with "
            f"'expectations' key, got {type(config)}"
        )
