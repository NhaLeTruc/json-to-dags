"""
Operator registry for dynamic operator instantiation.

Registers built-in and custom Airflow operators and provides lookup
and instantiation functionality for the DAG factory.
"""

from functools import lru_cache
from typing import Any

from airflow.models import BaseOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

# Import custom Spark operators
try:
    from src.operators.spark.kubernetes_operator import SparkKubernetesOperator
    from src.operators.spark.standalone_operator import SparkStandaloneOperator
    from src.operators.spark.yarn_operator import SparkYarnOperator

    SPARK_OPERATORS_AVAILABLE = True
except ImportError:
    SPARK_OPERATORS_AVAILABLE = False

# Import custom notification operators
try:
    from src.operators.notifications.email_operator import EmailNotificationOperator
    from src.operators.notifications.teams_operator import TeamsNotificationOperator
    from src.operators.notifications.telegram_operator import TelegramNotificationOperator

    NOTIFICATION_OPERATORS_AVAILABLE = True
except ImportError:
    NOTIFICATION_OPERATORS_AVAILABLE = False

# Import custom data quality operators
try:
    from src.operators.quality.completeness_checker import CompletenessChecker
    from src.operators.quality.freshness_checker import FreshnessChecker
    from src.operators.quality.null_rate_checker import NullRateChecker
    from src.operators.quality.schema_validator import SchemaValidator
    from src.operators.quality.uniqueness_checker import UniquenessChecker

    QUALITY_OPERATORS_AVAILABLE = True
except ImportError:
    QUALITY_OPERATORS_AVAILABLE = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class OperatorNotFoundError(Exception):
    """Raised when operator is not found in registry."""

    pass


class OperatorRegistry:
    """
    Registry for Airflow operators.

    Manages operator registration, lookup, and instantiation for dynamic DAG generation.
    """

    def __init__(self) -> None:
        """Initialize operator registry with built-in operators."""
        self._operators: dict[str, type[BaseOperator]] = {}
        self._register_builtin_operators()
        self._register_custom_operators()
        logger.debug("OperatorRegistry initialized", operator_count=len(self._operators))

    def _register_builtin_operators(self) -> None:
        """Register built-in Airflow operators."""
        builtin_operators = {
            "BashOperator": BashOperator,
            "PythonOperator": PythonOperator,
            "EmptyOperator": EmptyOperator,
            "DummyOperator": EmptyOperator,  # Backwards compatibility
        }

        for name, operator_class in builtin_operators.items():
            self._operators[name] = operator_class

        logger.debug("Built-in operators registered", count=len(builtin_operators))

    def _register_custom_operators(self) -> None:
        """Register custom operators (Spark, notifications, data quality, etc.)."""
        custom_operators = {}

        # Register Spark operators if available
        if SPARK_OPERATORS_AVAILABLE:
            custom_operators.update(
                {
                    "SparkStandaloneOperator": SparkStandaloneOperator,
                    "SparkYarnOperator": SparkYarnOperator,
                    "SparkKubernetesOperator": SparkKubernetesOperator,
                }
            )
            logger.debug("Spark operators registered", count=3)

        # Register notification operators if available
        if NOTIFICATION_OPERATORS_AVAILABLE:
            custom_operators.update(
                {
                    "EmailNotificationOperator": EmailNotificationOperator,
                    "TeamsNotificationOperator": TeamsNotificationOperator,
                    "TelegramNotificationOperator": TelegramNotificationOperator,
                }
            )
            logger.debug("Notification operators registered", count=3)

        # Register data quality operators if available
        if QUALITY_OPERATORS_AVAILABLE:
            custom_operators.update(
                {
                    "SchemaValidator": SchemaValidator,
                    "CompletenessChecker": CompletenessChecker,
                    "FreshnessChecker": FreshnessChecker,
                    "UniquenessChecker": UniquenessChecker,
                    "NullRateChecker": NullRateChecker,
                }
            )
            logger.debug("Data quality operators registered", count=5)

        # Register custom operators
        for name, operator_class in custom_operators.items():
            self._operators[name] = operator_class

        logger.debug("Custom operators registered", count=len(custom_operators))

    def register_operator(self, name: str, operator_class: type[BaseOperator]) -> None:
        """
        Register an operator with the registry.

        Args:
            name: Operator name (used in JSON configs)
            operator_class: Operator class to register
        """
        if name in self._operators:
            logger.warning("Overwriting existing operator registration", operator_name=name)

        self._operators[name] = operator_class
        logger.debug("Operator registered", operator_name=name)

    def is_registered(self, name: str) -> bool:
        """
        Check if operator is registered.

        Args:
            name: Operator name

        Returns:
            True if operator is registered, False otherwise
        """
        return name in self._operators

    def get_operator_class(self, name: str) -> type[BaseOperator]:
        """
        Get operator class by name.

        Args:
            name: Operator name

        Returns:
            Operator class

        Raises:
            OperatorNotFoundError: If operator not found in registry
        """
        if name not in self._operators:
            msg = f"Operator not found in registry: {name}"
            logger.error(msg, available_operators=list(self._operators.keys()))
            raise OperatorNotFoundError(msg)

        return self._operators[name]

    def list_registered(self) -> list[str]:
        """
        Get list of all registered operator names.

        Returns:
            List of operator names
        """
        return list(self._operators.keys())

    def create_operator(
        self,
        operator_name: str,
        task_id: str,
        dag: Any,
        params: dict[str, Any],
    ) -> BaseOperator:
        """
        Create operator instance with given parameters.

        Args:
            operator_name: Name of operator to instantiate
            task_id: Task ID for the operator
            dag: DAG instance to attach operator to
            params: Operator-specific parameters

        Returns:
            Instantiated operator instance

        Raises:
            OperatorNotFoundError: If operator not found
            TypeError: If required parameters missing
        """
        operator_class = self.get_operator_class(operator_name)

        # Prepare operator kwargs
        operator_kwargs = {
            "task_id": task_id,
            "dag": dag,
            **params,
        }

        try:
            operator = operator_class(**operator_kwargs)
            logger.debug(
                "Operator instantiated",
                operator_name=operator_name,
                task_id=task_id,
            )
            return operator
        except TypeError as e:
            msg = f"Failed to instantiate operator '{operator_name}': {str(e)}"
            logger.error(msg, task_id=task_id)
            raise

    def get_operator_info(self, name: str) -> dict[str, Any]:
        """
        Get operator metadata and information.

        Args:
            name: Operator name

        Returns:
            Dict with operator information
        """
        operator_class = self.get_operator_class(name)

        return {
            "name": name,
            "class": operator_class.__name__,
            "module": operator_class.__module__,
            "docstring": operator_class.__doc__,
        }


# DESIGN-005 fix: Use lru_cache for thread-safe singleton pattern
@lru_cache(maxsize=1)
def get_default_registry() -> OperatorRegistry:
    """
    Get or create global OperatorRegistry instance.

    Uses lru_cache for thread-safe singleton pattern.

    Returns:
        Singleton OperatorRegistry instance
    """
    return OperatorRegistry()
