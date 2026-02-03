"""
Uniqueness Checker Operator for Apache Airflow.

Validates uniqueness of key columns and detects duplicate records.
"""

import re
from typing import Any

from airflow.exceptions import AirflowException

from src.hooks.warehouse_hook import WarehouseHook
from src.operators.quality.base_quality_operator import BaseQualityOperator
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Valid SQL identifier pattern (alphanumeric + underscore, must start with letter/underscore)
_SQL_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class UniquenessChecker(BaseQualityOperator):
    """
    Operator for checking uniqueness constraints.

    Detects duplicate records based on key columns and validates
    that all rows have unique key combinations.

    :param table_name: Table to check
    :param key_columns: List of columns forming unique key
    :param max_duplicate_percentage: Maximum allowed duplicate percentage
    :param where_clause: SQL WHERE clause for filtering
    :param exclude_nulls: Exclude NULL values from check (default: True).
        Note: When True, rows with NULL in any key column are excluded from
        both duplicate and total count queries, which may mask duplicates
        in nullable columns.
    :param case_sensitive: Case-sensitive comparison
    :param trim_whitespace: Trim whitespace before comparison
    :param return_duplicates: Return specific duplicate rows
    """

    template_fields = BaseQualityOperator.template_fields + ("where_clause",)


    def __init__(
        self,
        *,
        key_columns: list[str],
        max_duplicate_percentage: float = 0.0,
        where_clause: str | None = None,
        exclude_nulls: bool = True,
        case_sensitive: bool = True,
        trim_whitespace: bool = False,
        return_duplicates: bool = False,
        **kwargs,
    ):
        """Initialize UniquenessChecker."""
        super().__init__(**kwargs)

        if not key_columns:
            raise ValueError("key_columns must contain at least one column")

        # Validate column names to prevent SQL injection
        for col in key_columns:
            if not _SQL_IDENTIFIER_PATTERN.match(col):
                raise ValueError(
                    f"Invalid column name: '{col}'. "
                    "Column names must be alphanumeric with underscores."
                )

        self.key_columns = key_columns
        self.max_duplicate_percentage = max_duplicate_percentage
        self.where_clause = where_clause
        self.exclude_nulls = exclude_nulls
        self.case_sensitive = case_sensitive
        self.trim_whitespace = trim_whitespace
        self.return_duplicates = return_duplicates

    def build_key_expression(self) -> str:
        """
        Build SQL expression for key columns.

        :return: SQL expression string
        """
        expressions = []

        for col in self.key_columns:
            expr = col

            # Apply transformations
            if self.trim_whitespace:
                expr = f"TRIM({expr})"

            if not self.case_sensitive:
                expr = f"UPPER({expr})"

            expressions.append(expr)

        return ", ".join(expressions)

    def get_duplicate_count(self) -> int:
        """
        Get count of duplicate rows.

        :return: Number of duplicate rows
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        # Build key expression
        key_expr = self.build_key_expression()

        # Build query to count duplicates
        query = f"""
            SELECT COUNT(*) - COUNT(DISTINCT {key_expr})
            FROM {self.table_name}
        """

        # Add WHERE clause
        conditions = []
        if self.where_clause:
            conditions.append(f"({self.where_clause})")

        if self.exclude_nulls:
            null_conditions = [f"{col} IS NOT NULL" for col in self.key_columns]
            conditions.append(f"({' AND '.join(null_conditions)})")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        result = hook.get_first(query)
        return result[0] if result and result[0] else 0

    def get_total_count(self) -> int:
        """
        Get total row count.

        :return: Total number of rows
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        query = f"SELECT COUNT(*) FROM {self.table_name}"

        # Add WHERE clause
        conditions = []
        if self.where_clause:
            conditions.append(f"({self.where_clause})")

        if self.exclude_nulls:
            null_conditions = [f"{col} IS NOT NULL" for col in self.key_columns]
            conditions.append(f"({' AND '.join(null_conditions)})")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        result = hook.get_first(query)
        return result[0] if result and result[0] else 0

    def get_duplicate_rows(self) -> list[dict[str, Any]]:
        """
        Get specific duplicate rows.

        :return: List of duplicate key values with counts
        """
        if not self.return_duplicates:
            return []

        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        # Build key expression
        key_expr = self.build_key_expression()
        key_list = ", ".join(self.key_columns)

        # Query for duplicate keys
        query = f"""
            SELECT {key_list}, COUNT(*) as count
            FROM {self.table_name}
        """

        # Add WHERE clause
        conditions = []
        if self.where_clause:
            conditions.append(f"({self.where_clause})")

        if self.exclude_nulls:
            null_conditions = [f"{col} IS NOT NULL" for col in self.key_columns]
            conditions.append(f"({' AND '.join(null_conditions)})")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f"""
            GROUP BY {key_expr}
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 100
        """

        results = hook.get_records(query)

        return [
            {
                **{self.key_columns[i]: row[i] for i in range(len(self.key_columns))},
                "count": row[-1],
            }
            for row in results
        ]

    def perform_check(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Perform uniqueness check.

        :param context: Airflow context
        :return: Check result dictionary
        """
        try:
            # Get counts
            duplicate_count = self.get_duplicate_count()
            total_count = self.get_total_count()

            # Calculate percentage
            duplicate_percentage = duplicate_count / total_count * 100.0 if total_count > 0 else 0.0

            # Check if passed
            passed = duplicate_percentage <= self.max_duplicate_percentage

            # Get duplicate rows if requested
            duplicate_rows = []
            if self.return_duplicates and duplicate_count > 0:
                duplicate_rows = self.get_duplicate_rows()

            # Calculate value score
            value = 1.0 - (duplicate_percentage / 100.0)

            result = {
                "passed": passed,
                "value": round(value, 3),
                "expected": 1.0,
                "duplicate_count": duplicate_count,
                "total_count": total_count,
                "duplicate_percentage": round(duplicate_percentage, 2),
                "max_duplicate_percentage": self.max_duplicate_percentage,
                "key_columns": self.key_columns,
            }

            if duplicate_rows:
                result["duplicate_rows"] = duplicate_rows

            # Add message if failed
            if not passed:
                result["message"] = (
                    f"Found {duplicate_count} duplicate(s) "
                    f"({duplicate_percentage:.2f}%) exceeds maximum "
                    f"{self.max_duplicate_percentage}%"
                )
                result["details"] = f"Uniqueness check failed for {self.table_name}"

            return result

        except Exception as e:
            logger.error(f"Uniqueness check error: {str(e)}", exc_info=True)
            raise AirflowException(f"Uniqueness check failed: {str(e)}") from e
