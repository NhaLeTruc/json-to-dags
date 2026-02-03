"""
Structured logging utility for Apache Airflow ETL Demo Platform.

Provides consistent logging format with contextual information for debugging.
"""

import logging
import sys
from typing import Any


class StructuredLogger:
    """
    Structured logger with consistent formatting and contextual information.

    Wraps Python's standard logging with additional context fields for better
    observability and debugging in Airflow DAGs.
    """

    def __init__(self, name: str, level: int = logging.INFO) -> None:
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically __name__ from calling module)
            level: Logging level (default: INFO)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Only add handler if none exist (avoid duplicate handlers)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)

            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.context: dict[str, Any] = {}

    def add_context(self, **kwargs: Any) -> None:
        """
        Add context fields to all subsequent log messages.

        Args:
            **kwargs: Context key-value pairs (e.g., dag_id="my_dag")
        """
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context fields."""
        self.context.clear()

    def _format_message(self, msg: str, extra_context: dict[str, Any] | None = None) -> str:
        """
        Format log message with context fields.

        Context keys are sorted alphabetically for deterministic log output,
        which aids in log parsing and grep-based searches. If insertion order
        is needed, subclass and override this method.

        Args:
            msg: Log message
            extra_context: Additional context for this message only

        Returns:
            Formatted message with context fields
        """
        context = {**self.context}
        if extra_context:
            context.update(extra_context)

        if context:
            # Keys sorted alphabetically for deterministic, searchable output
            context_str = " | ".join(f"{k}={v}" for k, v in sorted(context.items()))
            return f"{msg} | {context_str}"
        return msg

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self.logger.debug(self._format_message(msg, kwargs))

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self.logger.info(self._format_message(msg, kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self.logger.warning(self._format_message(msg, kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message with context."""
        self.logger.error(self._format_message(msg, kwargs))

    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        self.logger.critical(self._format_message(msg, kwargs))

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with traceback and context."""
        self.logger.exception(self._format_message(msg, kwargs))


def get_logger(name: str, level: int = logging.INFO) -> StructuredLogger:
    """
    Get or create a structured logger instance.

    Args:
        name: Logger name (typically __name__ from calling module)
        level: Logging level (default: INFO)

    Returns:
        Configured StructuredLogger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.add_context(dag_id="my_dag", task_id="extract")
        >>> logger.info("Starting extraction", rows=1000)
        2025-10-15 12:34:56 - my_module - INFO - Starting extraction | dag_id=my_dag | rows=1000 | task_id=extract
    """
    return StructuredLogger(name, level)
