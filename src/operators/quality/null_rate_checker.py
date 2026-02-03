"""
Null Rate Checker Operator for Apache Airflow.

Validates NULL percentage in columns against acceptable thresholds.
"""

from typing import Any

from airflow.exceptions import AirflowException

from src.hooks.warehouse_hook import WarehouseHook
from src.operators.quality.base_quality_operator import BaseQualityOperator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class NullRateChecker(BaseQualityOperator):
    """
    Operator for checking NULL rate in columns.

    Validates that NULL percentage in specified columns
    does not exceed maximum acceptable threshold.

    :param table_name: Table to check
    :param column_name: Single column to check (optional)
    :param columns: Multiple columns to check (optional)
    :param max_null_percentage: Maximum allowed NULL percentage
    :param where_clause: SQL WHERE clause for filtering
    :param expect_not_null: Expect column has NOT NULL constraint
    """

    template_fields = BaseQualityOperator.template_fields + ("where_clause",)


    def __init__(
        self,
        *,
        column_name: str | None = None,
        columns: list[str] | None = None,
        max_null_percentage: float = 100.0,
        where_clause: str | None = None,
        expect_not_null: bool = False,
        **kwargs,
    ):
        """Initialize NullRateChecker."""
        super().__init__(**kwargs)

        if not column_name and not columns:
            raise ValueError("Either column_name or columns must be provided")

        self.column_name = column_name
        self.columns = columns or ([column_name] if column_name else [])
        self.max_null_percentage = max_null_percentage
        self.where_clause = where_clause
        self.expect_not_null = expect_not_null

    def get_null_count(self, column: str) -> int:
        """
        Get NULL count for column.

        :param column: Column name
        :return: Number of NULL values
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE {column} IS NULL"

        if self.where_clause:
            query += f" AND ({self.where_clause})"

        result = hook.get_first(query)
        return result[0] if result and result[0] else 0

    def get_total_count(self) -> int:
        """
        Get total row count.

        :return: Total number of rows
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        query = f"SELECT COUNT(*) FROM {self.table_name}"

        if self.where_clause:
            query += f" WHERE {self.where_clause}"

        result = hook.get_first(query)
        return result[0] if result and result[0] else 0

    def get_null_rates(self) -> dict[str, float]:
        """
        Get NULL rates for all columns using a single query.

        :return: Dictionary mapping column to NULL percentage
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        # Build a single query that counts NULLs for all columns at once
        count_exprs = ["COUNT(*) AS total_count"]
        for col in self.columns:
            count_exprs.append(f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS null_{col}")

        query = f"SELECT {', '.join(count_exprs)} FROM {self.table_name}"
        if self.where_clause:
            query += f" WHERE {self.where_clause}"

        result = hook.get_first(query)
        if not result or result[0] == 0:
            return {col: 0.0 for col in self.columns}

        total_count = result[0]
        rates = {}
        for i, col in enumerate(self.columns):
            null_count = result[i + 1] or 0
            null_percentage = (null_count / total_count) * 100.0
            rates[col] = round(null_percentage, 2)

        return rates

    def perform_check(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Perform NULL rate check.

        :param context: Airflow context
        :return: Check result dictionary
        """
        try:
            # Get total count
            total_count = self.get_total_count()

            # Handle empty table
            if total_count == 0:
                return {
                    "passed": not self.expect_not_null,  # Pass if we don't expect data
                    "value": 0.0,
                    "expected": 1.0,
                    "total_count": 0,
                    "message": f"Table {self.table_name} is empty",
                }

            # Single column or multiple columns
            if len(self.columns) == 1:
                # Single column check
                column = self.columns[0]
                null_count = self.get_null_count(column)
                null_percentage = (null_count / total_count) * 100.0
                non_null_count = total_count - null_count

                passed = null_percentage <= self.max_null_percentage

                if self.expect_not_null:
                    passed = null_count == 0

                # Calculate value score (lower NULL rate = higher score)
                value = 1.0 - (null_percentage / 100.0)

                result = {
                    "passed": passed,
                    "value": round(value, 3),
                    "expected": 1.0,
                    "null_count": null_count,
                    "total_count": total_count,
                    "non_null_count": non_null_count,
                    "null_percentage": round(null_percentage, 2),
                    "max_null_percentage": self.max_null_percentage,
                    "column": column,
                }

                # Add message if failed
                if not passed:
                    result["message"] = (
                        f"NULL rate {null_percentage:.2f}% in column '{column}' "
                        f"exceeds maximum {self.max_null_percentage}%"
                    )
                    result["details"] = f"NULL rate check failed for {self.table_name}.{column}"

            else:
                # Multiple columns check
                null_rates = self.get_null_rates()

                # Check each column
                failed_columns = []
                for col, rate in null_rates.items():
                    if rate > self.max_null_percentage:
                        failed_columns.append(col)

                passed = len(failed_columns) == 0

                # Calculate average value score
                avg_value = sum(1.0 - (rate / 100.0) for rate in null_rates.values()) / len(
                    null_rates
                )

                result = {
                    "passed": passed,
                    "value": round(avg_value, 3),
                    "expected": 1.0,
                    "total_count": total_count,
                    "null_rates": null_rates,
                    "max_null_percentage": self.max_null_percentage,
                    "columns": self.columns,
                    "failed_columns": failed_columns,
                }

                # Add message if failed
                if not passed:
                    result["message"] = (
                        f"{len(failed_columns)} column(s) exceed NULL rate threshold: "
                        f"{', '.join(failed_columns)}"
                    )
                    result["details"] = f"NULL rate check failed for {self.table_name}"

            return result

        except Exception as e:
            logger.error(f"NULL rate check error: {str(e)}", exc_info=True)
            raise AirflowException(f"NULL rate check failed: {str(e)}") from e
