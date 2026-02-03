"""
Timeout handling utility for Apache Airflow ETL Demo Platform.

Provides functions for timeout detection, elapsed time calculation,
and timeout configuration for Airflow tasks.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TimeoutChecker:
    """
    Timeout checker for monitoring task execution time.

    Tracks elapsed time and detects when timeout threshold is exceeded.
    """

    def __init__(self, timeout_seconds: int) -> None:
        """
        Initialize timeout checker.

        Args:
            timeout_seconds: Timeout threshold in seconds

        Raises:
            ValueError: If timeout_seconds is negative
        """
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative (0 means no timeout)")

        self.timeout_seconds = timeout_seconds
        logger.debug("TimeoutChecker initialized", timeout_seconds=timeout_seconds)

    def check_timeout(self, start_time: datetime, current_time: datetime) -> bool:
        """
        Check if timeout has been exceeded.

        Args:
            start_time: Task start timestamp
            current_time: Current timestamp

        Returns:
            True if timeout exceeded, False otherwise
        """
        if self.timeout_seconds == 0:
            return False  # No timeout enforcement

        elapsed = (current_time - start_time).total_seconds()
        is_timeout = elapsed > self.timeout_seconds

        if is_timeout:
            logger.warning(
                "Timeout exceeded",
                elapsed_seconds=elapsed,
                timeout_seconds=self.timeout_seconds,
            )

        return is_timeout


class TimeoutContext:
    """
    Context manager for timeout monitoring during task execution.

    Usage:
        with TimeoutContext(timeout_seconds=300) as ctx:
            # Execute task
            result = long_running_function()

        if ctx.timed_out:
            # Handle timeout
    """

    def __init__(self, timeout_seconds: int) -> None:
        """
        Initialize timeout context.

        Args:
            timeout_seconds: Timeout threshold in seconds
        """
        self.timeout_seconds = timeout_seconds
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.timed_out = False

    def __enter__(self):
        """Enter context and start timer."""
        self.start_time = datetime.now()
        logger.debug("Timeout context started", timeout_seconds=self.timeout_seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and check for timeout."""
        self.end_time = datetime.now()

        if self.start_time:
            elapsed = (self.end_time - self.start_time).total_seconds()
            self.timed_out = self.timeout_seconds > 0 and elapsed > self.timeout_seconds

            logger.debug(
                "Timeout context ended",
                elapsed_seconds=elapsed,
                timed_out=self.timed_out,
            )

        return False  # Don't suppress exceptions

    def is_timed_out(self) -> bool:
        """
        Check if execution timed out.

        Returns:
            True if timed out, False otherwise
        """
        if self.start_time is None:
            return False

        current_time = self.end_time if self.end_time else datetime.now()
        elapsed = (current_time - self.start_time).total_seconds()

        return self.timeout_seconds > 0 and elapsed > self.timeout_seconds


def calculate_elapsed_time(
    start_time: datetime, end_time: datetime, return_timedelta: bool = False
) -> int | timedelta:
    """
    Calculate elapsed time between start and end.

    Args:
        start_time: Start timestamp
        end_time: End timestamp
        return_timedelta: Return timedelta instead of seconds

    Returns:
        Elapsed time in seconds or as timedelta

    Example:
        >>> start = datetime(2024, 1, 1, 12, 0, 0)
        >>> end = datetime(2024, 1, 1, 12, 5, 30)
        >>> calculate_elapsed_time(start, end)
        330
    """
    elapsed = end_time - start_time

    if return_timedelta:
        return elapsed

    return int(elapsed.total_seconds())


def calculate_timeout_remaining(
    start_time: datetime, current_time: datetime, timeout_seconds: int
) -> int:
    """
    Calculate remaining time before timeout.

    Args:
        start_time: Task start timestamp
        current_time: Current timestamp
        timeout_seconds: Timeout threshold in seconds

    Returns:
        Remaining seconds (negative if timeout exceeded)

    Example:
        >>> start = datetime(2024, 1, 1, 12, 0, 0)
        >>> current = datetime(2024, 1, 1, 12, 3, 0)
        >>> calculate_timeout_remaining(start, current, 300)
        120
    """
    elapsed = (current_time - start_time).total_seconds()
    remaining = timeout_seconds - elapsed

    return int(remaining)


def is_timeout_exceeded(
    start_time: datetime, current_time: datetime, timeout_seconds: int | None = None
) -> bool:
    """
    Check if timeout has been exceeded.

    Args:
        start_time: Task start timestamp
        current_time: Current timestamp
        timeout_seconds: Timeout threshold in seconds (None or 0 = no timeout)

    Returns:
        True if timeout exceeded, False otherwise

    Example:
        >>> start = datetime(2024, 1, 1, 12, 0, 0)
        >>> current = datetime(2024, 1, 1, 12, 10, 0)
        >>> is_timeout_exceeded(start, current, 300)
        True
    """
    if timeout_seconds is None or timeout_seconds == 0:
        return False  # No timeout enforcement

    elapsed = (current_time - start_time).total_seconds()
    return elapsed > timeout_seconds


def should_warn_about_timeout(
    start_time: datetime, current_time: datetime, timeout_seconds: int, threshold: float = 0.8
) -> bool:
    """
    Check if warning should be issued for approaching timeout.

    Args:
        start_time: Task start timestamp
        current_time: Current timestamp
        timeout_seconds: Timeout threshold in seconds
        threshold: Warning threshold as fraction of timeout (default 0.8 = 80%)

    Returns:
        True if warning should be issued, False otherwise

    Example:
        >>> start = datetime(2024, 1, 1, 12, 0, 0)
        >>> current = datetime(2024, 1, 1, 12, 8, 0)
        >>> should_warn_about_timeout(start, current, 600, threshold=0.8)
        True
    """
    elapsed = (current_time - start_time).total_seconds()
    warning_threshold = timeout_seconds * threshold

    return elapsed >= warning_threshold and elapsed < timeout_seconds


def get_timeout_status(start_time: datetime, current_time: datetime, timeout_seconds: int) -> str:
    """
    Get human-readable timeout status string.

    Args:
        start_time: Task start timestamp
        current_time: Current timestamp
        timeout_seconds: Timeout threshold in seconds

    Returns:
        Status string with elapsed and remaining time

    Example:
        >>> start = datetime(2024, 1, 1, 12, 0, 0)
        >>> current = datetime(2024, 1, 1, 12, 3, 0)
        >>> get_timeout_status(start, current, 600)
        'Elapsed: 3 minutes | Remaining: 7 minutes'
    """
    elapsed = (current_time - start_time).total_seconds()
    remaining = timeout_seconds - elapsed

    elapsed_str = format_timeout_duration(int(elapsed))
    remaining_str = format_timeout_duration(int(remaining)) if remaining > 0 else "EXCEEDED"

    return f"Elapsed: {elapsed_str} | Remaining: {remaining_str}"


def format_timeout_duration(seconds: int) -> str:
    """
    Format timeout duration as human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "5 minutes 30 seconds")

    Example:
        >>> format_timeout_duration(330)
        '5 minutes 30 seconds'
        >>> format_timeout_duration(3661)
        '1 hour 1 minute 1 second'
    """
    if seconds < 0:
        return f"{abs(seconds)} seconds (exceeded)"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []

    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    if secs > 0 or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return " ".join(parts)


def create_timeout_config(
    timeout_seconds: int, on_timeout_callback: Callable | None = None
) -> dict[str, Any]:
    """
    Create timeout configuration dict for Airflow task.

    Args:
        timeout_seconds: Timeout threshold in seconds
        on_timeout_callback: Optional callback function for timeout events

    Returns:
        Dict with timeout configuration for Airflow

    Example:
        >>> config = create_timeout_config(1800)
        >>> config['execution_timeout']
        datetime.timedelta(seconds=1800)
    """
    config = {"execution_timeout": timedelta(seconds=timeout_seconds)}

    if on_timeout_callback:
        config["on_failure_callback"] = on_timeout_callback

    logger.info("Timeout configuration created", timeout_seconds=timeout_seconds)

    return config


# Convenience constants
DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes
WARNING_THRESHOLD = 0.8  # Warn at 80% of timeout
