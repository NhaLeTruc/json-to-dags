"""
Unit tests for operator registry.

Tests operator registration, lookup, instantiation, and parameter validation.
"""

import pytest
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


class TestOperatorRegistry:
    """Test suite for OperatorRegistry class."""

    def test_registry_initializes_with_builtin_operators(self):
        """Test that registry initializes with built-in Airflow operators."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        # Check that common built-in operators are registered
        assert registry.is_registered("BashOperator")
        assert registry.is_registered("PythonOperator")
        assert registry.is_registered("DummyOperator")

    def test_get_operator_class_returns_correct_class(self):
        """Test that get_operator_class returns correct operator class."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        bash_op_class = registry.get_operator_class("BashOperator")
        assert bash_op_class == BashOperator

        python_op_class = registry.get_operator_class("PythonOperator")
        assert python_op_class == PythonOperator

    def test_get_operator_class_raises_for_unregistered_operator(self):
        """Test that getting unregistered operator raises error."""
        from dags.factory.operator_registry import OperatorNotFoundError, OperatorRegistry

        registry = OperatorRegistry()

        with pytest.raises(OperatorNotFoundError) as exc_info:
            registry.get_operator_class("NonExistentOperator")

        assert "NonExistentOperator" in str(exc_info.value)

    def test_register_custom_operator(self):
        """Test registration of custom operator."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        # Register a custom operator
        registry.register_operator("CustomBash", BashOperator)

        assert registry.is_registered("CustomBash")
        assert registry.get_operator_class("CustomBash") == BashOperator

    def test_register_duplicate_operator_overwrites(self):
        """Test that registering same name twice overwrites previous registration."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        # Register with one class
        registry.register_operator("TestOperator", BashOperator)
        assert registry.get_operator_class("TestOperator") == BashOperator

        # Register with different class (should overwrite)
        registry.register_operator("TestOperator", PythonOperator)
        assert registry.get_operator_class("TestOperator") == PythonOperator

    def test_list_registered_operators(self):
        """Test that list_registered returns all operator names."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()
        registered = registry.list_registered()

        assert isinstance(registered, list)
        assert len(registered) > 0
        assert "BashOperator" in registered
        assert "PythonOperator" in registered

    def test_create_operator_instance_with_valid_params(self, mock_airflow_context):
        """Test creating operator instance with valid parameters."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        operator = registry.create_operator(
            operator_name="BashOperator",
            task_id="test_task",
            dag=mock_airflow_context["dag"],
            params={"bash_command": "echo 'Hello World'"},
        )

        assert isinstance(operator, BashOperator)
        assert operator.task_id == "test_task"
        assert operator.bash_command == "echo 'Hello World'"

    def test_create_operator_instance_missing_required_params(self, mock_airflow_context):
        """Test that creating operator without required params raises error."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        # BashOperator requires bash_command parameter
        with pytest.raises((TypeError, ValueError)):
            registry.create_operator(
                operator_name="BashOperator",
                task_id="test_task",
                dag=mock_airflow_context["dag"],
                params={},  # Missing bash_command
            )

    def test_create_operator_with_extra_params(self, mock_airflow_context):
        """Test creating operator with extra default_args style params."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        operator = registry.create_operator(
            operator_name="BashOperator",
            task_id="test_task",
            dag=mock_airflow_context["dag"],
            params={
                "bash_command": "echo 'Test'",
                "retries": 3,
                "retry_delay": 300,
                "email_on_failure": True,
            },
        )

        assert isinstance(operator, BashOperator)
        assert operator.retries == 3

    def test_get_operator_info(self):
        """Test getting operator metadata and documentation."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        info = registry.get_operator_info("BashOperator")

        assert info is not None
        assert "name" in info
        assert info["name"] == "BashOperator"
        # May include docstring, required params, etc.

    def test_registry_is_case_sensitive(self):
        """Test that operator names are case-sensitive."""
        from dags.factory.operator_registry import OperatorNotFoundError, OperatorRegistry

        registry = OperatorRegistry()

        assert registry.is_registered("BashOperator")
        assert not registry.is_registered("bashoperator")

        with pytest.raises(OperatorNotFoundError):
            registry.get_operator_class("bashoperator")

    def test_singleton_registry_pattern(self):
        """Test that get_default_registry returns singleton instance."""
        from dags.factory.operator_registry import get_default_registry

        registry1 = get_default_registry()
        registry2 = get_default_registry()

        # Should return same instance
        assert registry1 is registry2

    def test_custom_operators_from_src_directory(self):
        """Test that custom operators from src/operators/ can be registered."""
        from dags.factory.operator_registry import OperatorRegistry

        OperatorRegistry()

        # Placeholder for custom operators we'll implement later
        # registry.register_operator("SparkSubmitOperatorCustom", SparkSubmitOperatorCustom)
        # assert registry.is_registered("SparkSubmitOperatorCustom")

    @pytest.mark.parametrize(
        "operator_name,expected_class",
        [
            ("BashOperator", BashOperator),
            ("PythonOperator", PythonOperator),
        ],
    )
    def test_multiple_operator_lookups(self, operator_name, expected_class):
        """Test looking up multiple different operators."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()
        operator_class = registry.get_operator_class(operator_name)

        assert operator_class == expected_class

    def test_create_operator_without_dag(self):
        """Test creating operator without DAG reference (for testing)."""
        from dags.factory.operator_registry import OperatorRegistry

        registry = OperatorRegistry()

        # Some operators can be instantiated without DAG for testing
        operator = registry.create_operator(
            operator_name="BashOperator",
            task_id="test_task",
            dag=None,
            params={"bash_command": "echo 'Test'"},
        )

        assert isinstance(operator, BashOperator)
        assert operator.task_id == "test_task"
