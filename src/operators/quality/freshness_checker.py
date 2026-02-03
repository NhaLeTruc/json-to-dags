"""
Freshness Checker Operator for Apache Airflow.

Validates data freshness by checking timestamp age against
maximum acceptable age thresholds.
"""

from datetime import UTC, datetime
from typing import Any

from airflow.exceptions import AirflowException

from src.hooks.warehouse_hook import WarehouseHook
from src.operators.quality.base_quality_operator import BaseQualityOperator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FreshnessChecker(BaseQualityOperator):
    """
    Operator for checking data freshness.

    Validates that most recent data timestamp is within
    acceptable age limit (max_age_hours or max_age_minutes).

    :param table_name: Table to check
    :param timestamp_column: Column containing timestamp
    :param max_age_hours: Maximum age in hours (optional)
    :param max_age_minutes: Maximum age in minutes (optional)
    :param sla_hours: SLA hours for compliance checking (optional)
    :param where_clause: SQL WHERE clause for filtering (optional)
    :param timestamp_columns: Multiple timestamp columns to check (optional)
    """

    template_fields = BaseQualityOperator.template_fields + ("where_clause",)


    def __init__(
        self,
        *,
        timestamp_column: str | None = None,
        max_age_hours: float | None = None,
        max_age_minutes: float | None = None,
        sla_hours: float | None = None,
        where_clause: str | None = None,
        timestamp_columns: list[str] | None = None,
        **kwargs,
    ):
        """Initialize FreshnessChecker."""
        super().__init__(**kwargs)

        if not timestamp_column and not timestamp_columns:
            raise ValueError("Either timestamp_column or timestamp_columns must be provided")

        self.timestamp_column = timestamp_column
        self.max_age_hours = max_age_hours
        self.max_age_minutes = max_age_minutes
        self.sla_hours = sla_hours
        self.where_clause = where_clause
        self.timestamp_columns = timestamp_columns

        # Convert max_age_minutes to hours if provided
        if max_age_minutes and not max_age_hours:
            self.max_age_hours = max_age_minutes / 60.0

    def get_max_timestamp(self) -> datetime | None:
        """
        Get maximum timestamp from table.

        :return: Most recent timestamp or None if table empty
        """
        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)

        # Build query
        query = f"SELECT MAX({self.timestamp_column}) FROM {self.table_name}"

        # Add WHERE clause if provided
        if self.where_clause:
            query += f" WHERE {self.where_clause}"

        result = hook.get_first(query)
        return result[0] if result and result[0] else None

    def get_max_timestamps(self) -> dict[str, datetime | None]:
        """
        Get maximum timestamps for multiple columns.

        :return: Dictionary mapping column name to max timestamp
        """
        if not self.timestamp_columns:
            return {}

        hook = WarehouseHook(postgres_conn_id=self.warehouse_conn_id)
        results = {}

        for col in self.timestamp_columns:
            query = f"SELECT MAX({col}) FROM {self.table_name}"
            if self.where_clause:
                query += f" WHERE {self.where_clause}"

            result = hook.get_first(query)
            results[col] = result[0] if result and result[0] else None

        return results

    def calculate_age(self, timestamp: datetime) -> dict[str, float]:
        """
        Calculate age of timestamp.

        :param timestamp: Timestamp to calculate age for
        :return: Dictionary with age in hours and minutes
        """
        # Use timezone-aware now() for consistent comparison with DB timestamps
        now = datetime.now(UTC)

        # Handle timezone-naive timestamps from DB
        if timestamp.tzinfo is None:
            # Assume naive timestamps are UTC
            from datetime import timezone
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        age_delta = now - timestamp
        age_hours = age_delta.total_seconds() / 3600.0
        age_minutes = age_delta.total_seconds() / 60.0

        return {
            "age_hours": round(age_hours, 2),
            "age_minutes": round(age_minutes, 2),
        }

    def perform_check(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Perform freshness check.

        :param context: Airflow context
        :return: Check result dictionary
        """
        try:
            # Handle single or multiple timestamp columns
            if self.timestamp_columns:
                timestamps = self.get_max_timestamps()
                if not timestamps:
                    raise AirflowException("No timestamp columns found")

                # Find most recent timestamp
                max_timestamp = max(
                    (ts for ts in timestamps.values() if ts is not None), default=None
                )

                result = {
                    "timestamps": {k: v.isoformat() if v else None for k, v in timestamps.items()},
                    "max_timestamp": max_timestamp.isoformat() if max_timestamp else None,
                }
            else:
                # Single timestamp column
                max_timestamp = self.get_max_timestamp()
                result = {
                    "max_timestamp": max_timestamp.isoformat() if max_timestamp else None,
                }

            # Check if data exists
            if max_timestamp is None:
                return {
                    **result,
                    "passed": False,
                    "value": 0.0,
                    "expected": 1.0,
                    "message": f"No data found in {self.table_name}",
                    "no_data": True,
                }

            # Calculate age
            age_info = self.calculate_age(max_timestamp)
            result.update(age_info)

            # Check against max age
            passed = True
            if self.max_age_hours is not None:
                passed = age_info["age_hours"] <= self.max_age_hours

            # Check SLA compliance
            sla_compliant = True
            if self.sla_hours is not None:
                sla_compliant = age_info["age_hours"] <= self.sla_hours
                result["sla_compliant"] = sla_compliant
                result["sla_hours"] = self.sla_hours

            # Calculate value score (fresher = higher score)
            if self.max_age_hours and self.max_age_hours > 0:
                value = max(0.0, 1.0 - (age_info["age_hours"] / self.max_age_hours))
            else:
                value = 1.0 if passed else 0.0

            result.update(
                {
                    "passed": passed,
                    "value": round(value, 3),
                    "expected": 1.0,
                    "max_age_hours": self.max_age_hours,
                }
            )

            # Add message if failed
            if not passed:
                result["message"] = (
                    f"Data is stale: age {age_info['age_hours']:.1f} hours "
                    f"exceeds maximum {self.max_age_hours} hours"
                )
                result["details"] = f"Freshness check failed for {self.table_name}"

            return result

        except AirflowException:
            raise
        except Exception as e:
            logger.error(f"Freshness check error: {str(e)}", exc_info=True)
            raise AirflowException(f"Freshness check failed: {str(e)}") from e
