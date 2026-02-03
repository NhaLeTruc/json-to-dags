"""
Schema Validation Operator for Apache Airflow.

Validates table schema against expected column definitions including
data types, nullable constraints, and column presence.
"""

from typing import Any

from airflow.exceptions import AirflowException

from src.hooks.warehouse_hook import WarehouseHook
from src.operators.quality.base_quality_operator import BaseQualityOperator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SchemaValidator(BaseQualityOperator):
    """
    Operator for validating table schema.

    Checks column presence, data types, nullable constraints,
    and detects missing or extra columns.

    :param table_name: Table to validate
    :param expected_schema: Expected schema definition with columns list
    :param check_types: Whether to validate data types (default: True)
    :param check_nullability: Whether to validate NULL constraints (default: False)
    :param allow_extra_columns: Whether to allow extra columns (default: False)
    """


    def __init__(
        self,
        *,
        expected_schema: dict[str, Any],
        check_types: bool = True,
        check_nullability: bool = False,
        check_column_order: bool = False,
        allow_extra_columns: bool = False,
        **kwargs,
    ):
        """Initialize SchemaValidator."""
        super().__init__(**kwargs)

        if not expected_schema or "columns" not in expected_schema:
            raise ValueError("expected_schema must contain 'columns' list")

        # Validate each column definition has required keys
        for i, col in enumerate(expected_schema["columns"]):
            if not isinstance(col, dict) or "name" not in col:
                raise ValueError(
                    f"expected_schema column at index {i} must be a dict with at least a 'name' key"
                )
            if check_types and "type" not in col:
                raise ValueError(
                    f"expected_schema column '{col['name']}' must have a 'type' key "
                    f"when check_types=True"
                )

        self.expected_schema = expected_schema
        self.check_types = check_types
        self.check_nullability = check_nullability
        self.check_column_order = check_column_order
        self.allow_extra_columns = allow_extra_columns

    def get_table_schema(self) -> list[dict[str, Any]]:
        """
        Get actual table schema from database.

        :return: List of column definitions
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        # Extract schema and table name
        parts = self.table_name.split(".")
        if len(parts) == 2:
            schema_name, table_name = parts
        else:
            schema_name = "public"
            table_name = self.table_name

        # Query information_schema for column metadata
        query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
        """

        result = hook.get_records(query, parameters=(schema_name, table_name))

        if not result:
            raise AirflowException(f"Table {self.table_name} not found or has no columns")

        return [
            {
                "column_name": row[0],
                "data_type": row[1],
                "is_nullable": row[2],
                "ordinal_position": row[3],
            }
            for row in result
        ]

    def normalize_type(self, db_type: str) -> str:
        """
        Normalize PostgreSQL data type to standard type.

        :param db_type: Database-specific type
        :return: Normalized type name
        """
        type_map = {
            "integer": "INTEGER",
            "bigint": "INTEGER",
            "smallint": "INTEGER",
            "character varying": "VARCHAR",
            "character": "VARCHAR",
            "text": "VARCHAR",
            "numeric": "NUMERIC",
            "decimal": "NUMERIC",
            "real": "NUMERIC",
            "double precision": "NUMERIC",
            "timestamp without time zone": "TIMESTAMP",
            "timestamp with time zone": "TIMESTAMP",
            "date": "DATE",
            "boolean": "BOOLEAN",
        }

        return type_map.get(db_type.lower(), db_type.upper())

    def perform_check(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Perform schema validation check.

        :param context: Airflow context
        :return: Check result dictionary
        """
        try:
            # Get actual schema from database
            actual_columns = self.get_table_schema()
            actual_col_map = {col["column_name"]: col for col in actual_columns}

            # Get expected columns
            expected_columns = self.expected_schema["columns"]
            expected_col_map = {col["name"]: col for col in expected_columns}

            # Check for missing columns
            missing_columns = [
                col_name for col_name in expected_col_map if col_name not in actual_col_map
            ]

            # Check for extra columns
            extra_columns = []
            if not self.allow_extra_columns:
                extra_columns = [
                    col_name for col_name in actual_col_map if col_name not in expected_col_map
                ]

            # Check data types
            type_mismatches = []
            if self.check_types:
                for col_name, expected_col in expected_col_map.items():
                    if col_name in actual_col_map:
                        actual_type = self.normalize_type(actual_col_map[col_name]["data_type"])
                        expected_type = expected_col["type"].upper()

                        if actual_type != expected_type:
                            type_mismatches.append(
                                {
                                    "column": col_name,
                                    "expected": expected_type,
                                    "actual": actual_type,
                                }
                            )

            # Check nullability
            nullability_mismatches = []
            if self.check_nullability:
                for col_name, expected_col in expected_col_map.items():
                    if col_name in actual_col_map and "nullable" in expected_col:
                        actual_nullable = actual_col_map[col_name]["is_nullable"] == "YES"
                        expected_nullable = expected_col["nullable"]

                        if actual_nullable != expected_nullable:
                            nullability_mismatches.append(
                                {
                                    "column": col_name,
                                    "expected_nullable": expected_nullable,
                                    "actual_nullable": actual_nullable,
                                }
                            )

            # Determine if check passed
            passed = (
                len(missing_columns) == 0
                and len(extra_columns) == 0
                and len(type_mismatches) == 0
                and len(nullability_mismatches) == 0
            )

            # Build result
            result = {
                "passed": passed,
                "value": 1.0 if passed else 0.0,
                "expected": 1.0,
                "missing_columns": missing_columns,
                "extra_columns": extra_columns,
                "type_mismatches": type_mismatches,
                "nullability_mismatches": nullability_mismatches,
                "total_columns": len(actual_columns),
                "expected_columns": len(expected_columns),
            }

            # Add error details if failed
            if not passed:
                errors = []
                if missing_columns:
                    errors.append(f"Missing columns: {', '.join(missing_columns)}")
                if extra_columns:
                    errors.append(f"Extra columns: {', '.join(extra_columns)}")
                if type_mismatches:
                    errors.append(f"{len(type_mismatches)} type mismatch(es)")
                if nullability_mismatches:
                    errors.append(f"{len(nullability_mismatches)} nullability mismatch(es)")

                result["message"] = "; ".join(errors)
                result["details"] = f"Schema validation failed for {self.table_name}"

            return result

        except AirflowException:
            raise
        except Exception as e:
            logger.error(f"Schema validation error: {str(e)}", exc_info=True)
            raise AirflowException(f"Schema validation failed: {str(e)}") from e
