"""
Base Quality Operator for Apache Airflow.

Provides common functionality for all data quality operators including
severity levels, threshold validation, result storage, and error handling.
"""

from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from airflow.exceptions import AirflowException
from airflow.models import BaseOperator

from src.utils.logger import get_logger

logger = get_logger(__name__)


class QualitySeverity(Enum):
    """Severity levels for quality check results."""

    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class BaseQualityOperator(BaseOperator):
    """
    Base operator for data quality checks.

    This operator provides common functionality for all quality checks:
    - Severity-based failure handling
    - Threshold validation
    - Result logging and storage
    - Structured error reporting

    Subclasses must implement the perform_check() method.

    :param table_name: Name of the table to check (supports Jinja2 templates)
    :param severity: Quality check severity level (INFO, WARNING, ERROR, CRITICAL)
    :param threshold: Minimum acceptable threshold value (0.0-1.0)
    :param warehouse_conn_id: Airflow connection ID for warehouse database
    :param store_results: Whether to store results in quality_check_results table
    """

    template_fields = ("table_name",)
    ui_color = "#f0ad4e"  # Orange for quality checks

    def __init__(
        self,
        *,
        table_name: str,
        severity: QualitySeverity = QualitySeverity.ERROR,
        threshold: float | None = None,
        warehouse_conn_id: str = "warehouse_default",
        store_results: bool = True,
        **kwargs,
    ):
        """Initialize BaseQualityOperator."""
        super().__init__(**kwargs)

        # Validate table name
        if not table_name or not table_name.strip():
            raise ValueError("table_name parameter is required")

        self.table_name = table_name
        self.severity = severity
        self.threshold = threshold
        self.warehouse_conn_id = warehouse_conn_id
        self.store_results = store_results

        # Validate threshold if provided
        if threshold is not None and not (0.0 <= threshold <= 1.0):
            raise ValueError(f"threshold must be between 0.0 and 1.0, got {threshold}")

    @abstractmethod
    def perform_check(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Perform the quality check.

        This method must be implemented by subclasses.

        :param context: Airflow context dictionary
        :return: Dictionary with check results including:
            - passed (bool): Whether check passed
            - value (float): Check result value
            - expected (float, optional): Expected value
            - details (str, optional): Additional details
            - message (str, optional): Custom message
        :raises AirflowException: If check execution fails
        """
        raise NotImplementedError("Subclasses must implement perform_check()")

    def validate_threshold(self, result: dict[str, Any]) -> bool:
        """
        Validate result against threshold.

        :param result: Check result dictionary
        :return: True if result meets threshold, False otherwise
        """
        if self.threshold is None:
            # No threshold specified, use passed flag from result
            return result.get("passed", True)

        value = result.get("value")
        if value is None:
            logger.warning(f"No value in result for threshold validation: {result}")
            return result.get("passed", False)

        # Check if value meets threshold
        return value >= self.threshold

    def handle_result(self, result: dict[str, Any], context: dict[str, Any]) -> None:
        """
        Handle quality check result based on severity.

        :param result: Check result dictionary
        :param context: Airflow context
        :raises AirflowException: If severity is CRITICAL or ERROR and check failed
        """
        passed = result.get("passed", False)

        if not passed:
            message = result.get("message", f"Quality check failed for {self.table_name}")

            if self.severity == QualitySeverity.CRITICAL:
                logger.error(
                    "CRITICAL quality check failure",
                    extra={
                        "table": self.table_name,
                        "check_type": self.__class__.__name__,
                        "result": result,
                    },
                )
                raise AirflowException(f"CRITICAL: {message}")

            elif self.severity == QualitySeverity.ERROR:
                logger.error(
                    "Quality check error",
                    extra={
                        "table": self.table_name,
                        "check_type": self.__class__.__name__,
                        "result": result,
                    },
                )
                raise AirflowException(f"ERROR: {message}")

            elif self.severity == QualitySeverity.WARNING:
                logger.warning(
                    "Quality check warning",
                    extra={
                        "table": self.table_name,
                        "check_type": self.__class__.__name__,
                        "result": result,
                    },
                )
                # Don't fail task for WARNING

            else:  # INFO
                logger.info(
                    "Quality check info",
                    extra={
                        "table": self.table_name,
                        "check_type": self.__class__.__name__,
                        "result": result,
                    },
                )
        else:
            logger.info(
                "Quality check passed",
                extra={
                    "table": self.table_name,
                    "check_type": self.__class__.__name__,
                    "result": result,
                },
            )

    def store_result(self, result: dict[str, Any], context: dict[str, Any]) -> None:
        """
        Store quality check result to database.

        :param result: Check result dictionary
        :param context: Airflow context
        """
        if not self.store_results:
            return

        try:
            # FUTURE ENHANCEMENT: Result storage to warehouse.quality_check_results table
            # Implementation would require:
            # 1. Use WarehouseHook to connect to warehouse database
            # 2. Insert into quality_check_results table (see src/warehouse/migrations/002_etl_metadata_schema.sql)
            # 3. Store: check_id, table_name, check_type, severity, status, metrics, timestamp
            # 4. Enable historical trending and SLA monitoring
            # For now, results are logged and can be retrieved from Airflow task logs
            logger.warning(
                "Result storage to database not yet implemented; "
                "results are available in Airflow task logs only"
            )
        except Exception as e:
            # Don't fail task if result storage fails
            logger.warning(
                f"Failed to store quality check result: {str(e)}", extra={"result": result}
            )

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the quality check.

        :param context: Airflow context dictionary
        :return: Quality check result dictionary
        :raises AirflowException: If check fails with ERROR or CRITICAL severity
        """
        # Use self.dag_id/self.task_id from BaseOperator as reliable fallbacks
        dag_id = getattr(context.get("dag"), "dag_id", None) or self.dag_id
        task_id_val = getattr(context.get("task"), "task_id", None) or self.task_id
        execution_date = context.get("execution_date", "unknown")

        logger.info(
            f"Executing quality check: {self.__class__.__name__}",
            dag_id=dag_id,
            task_id=task_id_val,
            table=self.table_name,
            severity=self.severity.name,
        )

        try:
            # Perform the check
            check_result = self.perform_check(context)

            # Validate threshold if specified
            if self.threshold is not None:
                passed = self.validate_threshold(check_result)
                check_result["passed"] = passed

            # Add metadata to result
            result = {
                **check_result,
                "check_type": self.__class__.__name__,
                "table_name": self.table_name,
                "severity": self.severity.name,
                "threshold": self.threshold,
                "timestamp": datetime.now().isoformat(),
                "dag_id": dag_id,
                "task_id": task_id_val,
                "execution_date": str(execution_date),
            }

            # Store result if enabled
            self.store_result(result, context)

            # Handle result based on severity
            self.handle_result(result, context)

            return result

        except AirflowException:
            # Re-raise Airflow exceptions (from handle_result)
            raise

        except Exception as e:
            logger.error(
                f"Quality check execution failed: {str(e)}",
                dag_id=dag_id,
                task_id=task_id_val,
                table=self.table_name,
                error_type=type(e).__name__,
            )
            raise AirflowException(f"Quality check failed for {self.table_name}: {str(e)}") from e

    def on_kill(self):
        """Handle task kill event."""
        logger.warning(
            f"Quality check operator {self.__class__.__name__} killed",
            extra={"task_id": self.task_id, "table": self.table_name},
        )
