"""
Retry policy utility functions for Apache Airflow ETL Demo Platform.

Provides functions for calculating retry delays with various backoff strategies:
exponential, linear, and fixed.
"""

from datetime import timedelta
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_exponential_backoff(
    retry_number: int,
    base_delay: int,
    max_delay: int | None = None,
    return_timedelta: bool = False,
) -> int | timedelta:
    """
    Calculate exponential backoff delay.

    Formula: delay = base_delay * (2 ^ retry_number)

    Args:
        retry_number: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds (optional)
        return_timedelta: Return timedelta object instead of seconds

    Returns:
        Delay in seconds or timedelta object

    Raises:
        ValueError: If retry_number is negative or base_delay is invalid

    Example:
        >>> calculate_exponential_backoff(0, 60)
        60
        >>> calculate_exponential_backoff(1, 60)
        120
        >>> calculate_exponential_backoff(2, 60)
        240
    """
    if retry_number < 0:
        raise ValueError("retry_number must be non-negative")

    if base_delay <= 0:
        raise ValueError("base_delay must be positive")

    delay = base_delay * (2**retry_number)

    if max_delay is not None and delay > max_delay:
        delay = max_delay

    logger.debug(
        "Exponential backoff calculated",
        retry_number=retry_number,
        base_delay=base_delay,
        calculated_delay=delay,
        capped=max_delay is not None and (base_delay * (2**retry_number)) > max_delay,
    )

    if return_timedelta:
        return timedelta(seconds=delay)

    return delay


def calculate_linear_backoff(
    retry_number: int, base_delay: int, max_delay: int | None = None
) -> int:
    """
    Calculate linear backoff delay.

    Formula: delay = base_delay * (retry_number + 1)

    Args:
        retry_number: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds (optional)

    Returns:
        Delay in seconds

    Example:
        >>> calculate_linear_backoff(0, 60)
        60
        >>> calculate_linear_backoff(1, 60)
        120
        >>> calculate_linear_backoff(2, 60)
        180
    """
    if retry_number < 0:
        raise ValueError("retry_number must be non-negative")

    if base_delay <= 0:
        raise ValueError("base_delay must be positive")

    delay = base_delay * (retry_number + 1)

    if max_delay is not None and delay > max_delay:
        delay = max_delay

    logger.debug("Linear backoff calculated", retry_number=retry_number, delay=delay)

    return delay


def calculate_fixed_backoff(retry_number: int, delay: int) -> int:
    """
    Calculate fixed backoff delay (constant delay).

    Args:
        retry_number: Current retry attempt (ignored, for interface consistency)
        delay: Fixed delay in seconds

    Returns:
        Delay in seconds (always same value)

    Example:
        >>> calculate_fixed_backoff(0, 120)
        120
        >>> calculate_fixed_backoff(5, 120)
        120
    """
    if delay <= 0:
        raise ValueError("delay must be positive")

    return delay


def should_retry(current_attempt: int, max_retries: int) -> bool:
    """
    Check if task should retry based on current attempt and max retries.

    Args:
        current_attempt: Current attempt number (1-indexed)
        max_retries: Maximum number of retries allowed

    Returns:
        True if should retry, False otherwise

    Example:
        >>> should_retry(1, 3)
        True
        >>> should_retry(4, 3)
        False
    """
    return current_attempt <= max_retries


def generate_retry_delays(
    max_retries: int,
    base_delay: int,
    strategy: str = "exponential",
    max_delay: int | None = None,
    return_timedeltas: bool = False,
) -> list[int | timedelta]:
    """
    Generate sequence of retry delays for all retry attempts.

    Args:
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds
        strategy: Backoff strategy ("exponential", "linear", "fixed")
        max_delay: Maximum delay cap in seconds (optional)
        return_timedeltas: Return list of timedelta objects

    Returns:
        List of delays for each retry attempt

    Example:
        >>> generate_retry_delays(3, 60, "exponential")
        [60, 120, 240]
    """
    delays = []

    for retry_num in range(max_retries):
        if strategy == "exponential":
            delay = calculate_exponential_backoff(retry_num, base_delay, max_delay)
        elif strategy == "linear":
            delay = calculate_linear_backoff(retry_num, base_delay, max_delay)
        elif strategy == "fixed":
            delay = calculate_fixed_backoff(retry_num, base_delay)
        else:
            raise ValueError(f"Unknown retry strategy: {strategy}")

        if return_timedeltas:
            delays.append(timedelta(seconds=delay))
        else:
            delays.append(delay)

    logger.debug(
        "Retry delay sequence generated",
        max_retries=max_retries,
        strategy=strategy,
        delays=delays,
    )

    return delays


def get_retry_delay_for_airflow(
    retry_number: int,
    strategy: str = "exponential",
    base_delay: int = 60,
    max_delay: int | None = None,
) -> timedelta:
    """
    Get retry delay as timedelta for Airflow task configuration.

    Args:
        retry_number: Current retry attempt (0-indexed)
        strategy: Backoff strategy ("exponential", "linear", "fixed")
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds (optional)

    Returns:
        Retry delay as timedelta

    Raises:
        ValueError: If strategy is invalid

    Example:
        >>> get_retry_delay_for_airflow(1, "exponential", 60)
        datetime.timedelta(seconds=120)
    """
    if strategy == "exponential":
        delay_seconds = calculate_exponential_backoff(retry_number, base_delay, max_delay)
    elif strategy == "linear":
        delay_seconds = calculate_linear_backoff(retry_number, base_delay, max_delay)
    elif strategy == "fixed":
        delay_seconds = calculate_fixed_backoff(retry_number, base_delay)
    else:
        raise ValueError(
            f"Unknown retry strategy: {strategy}. Use 'exponential', 'linear', or 'fixed'"
        )

    return timedelta(seconds=delay_seconds)


def create_retry_config(
    max_retries: int,
    strategy: str = "exponential",
    base_delay: int = 60,
    max_delay: int | None = None,
) -> dict[str, Any]:
    """
    Create retry configuration dict for Airflow task default_args.

    Args:
        max_retries: Maximum number of retries
        strategy: Backoff strategy ("exponential", "linear", "fixed")
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds (optional)

    Returns:
        Dict with retry configuration for Airflow

    Example:
        >>> config = create_retry_config(3, "exponential", 60)
        >>> config['retries']
        3
        >>> config['retry_exponential_backoff']
        True
    """
    config = {
        "retries": max_retries,
        "retry_delay": timedelta(seconds=base_delay),
    }

    if strategy == "exponential":
        config["retry_exponential_backoff"] = True
    else:
        config["retry_exponential_backoff"] = False

    if max_delay is not None:
        config["max_retry_delay"] = timedelta(seconds=max_delay)

    logger.info(
        "Retry configuration created",
        max_retries=max_retries,
        strategy=strategy,
        base_delay=base_delay,
    )

    return config


# Convenience constants
DEFAULT_BASE_DELAY = 60  # 1 minute
DEFAULT_MAX_DELAY = 1800  # 30 minutes
DEFAULT_MAX_RETRIES = 3
