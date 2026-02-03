"""
Base Notification Operator for Apache Airflow.

Provides common functionality for all notification operators including
retry logic, template rendering, error handling, and logging.
"""

from abc import abstractmethod
from datetime import timedelta
from typing import Any

from airflow.exceptions import AirflowException
from airflow.models import BaseOperator
from jinja2 import Template, TemplateError

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseNotificationOperator(BaseOperator):
    """
    Base operator for sending notifications with retry logic and template rendering.

    This operator provides common functionality for all notification operators:
    - Jinja2 template rendering with Airflow context
    - Structured error logging
    - Retry mechanism with configurable delays
    - Template field support for dynamic values

    Subclasses must implement the send_notification() method.

    :param message_template: Jinja2 template string for the notification message
    :param retries: Number of retry attempts on failure (inherited from BaseOperator)
    :param retry_delay: Delay between retry attempts (inherited from BaseOperator)
    :param retry_exponential_backoff: Use exponential backoff for retries (inherited from BaseOperator)
    :param execution_timeout: Maximum execution time (inherited from BaseOperator)
    """

    template_fields = ("message_template",)
    ui_color = "#d4a5d4"  # Light purple for notifications


    def __init__(
        self,
        *,
        message_template: str,
        retries: int = 2,
        retry_delay: timedelta = timedelta(seconds=30),
        retry_exponential_backoff: bool = False,
        execution_timeout: timedelta | None = None,
        **kwargs,
    ):
        """Initialize BaseNotificationOperator."""
        super().__init__(
            retries=retries,
            retry_delay=retry_delay,
            retry_exponential_backoff=retry_exponential_backoff,
            execution_timeout=execution_timeout,
            **kwargs,
        )

        # Validate message template
        if not message_template or not message_template.strip():
            raise ValueError("message_template cannot be empty")

        self.message_template = message_template

    def render_template(self, template_str: str, context: dict[str, Any]) -> str:
        """
        Render a Jinja2 template with Airflow context.

        :param template_str: Template string to render
        :param context: Airflow context dictionary
        :return: Rendered template string
        :raises AirflowException: If template rendering fails
        """
        try:
            template = Template(template_str)
            rendered = template.render(**context)
            return rendered
        except TemplateError as e:
            logger.error(
                f"Template rendering failed for template: {template_str[:100]}... "
                f"Error: {str(e)}"
            )
            raise AirflowException(f"Template rendering error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error during template rendering: {str(e)}", exc_info=True)
            raise AirflowException(f"Template rendering failed: {str(e)}") from e

    @abstractmethod
    def send_notification(self, message: str, context: dict[str, Any]) -> bool:
        """
        Send the notification message.

        This method must be implemented by subclasses.

        :param message: Rendered message content
        :param context: Airflow context dictionary
        :return: True if notification sent successfully, False otherwise
        :raises AirflowException: If notification fails
        """
        raise NotImplementedError("Subclasses must implement send_notification()")

    def execute(self, context: dict[str, Any]) -> bool | None:
        """
        Execute the notification operator.

        Renders the template and sends the notification.

        :param context: Airflow context dictionary
        :return: True if successful, None otherwise
        :raises AirflowException: If notification fails after retries
        """
        # Use self.dag_id/self.task_id from BaseOperator as reliable fallbacks
        dag_id = getattr(context.get("dag"), "dag_id", None) or self.dag_id
        task_id_val = getattr(context.get("task"), "task_id", None) or self.task_id
        execution_date = context.get("execution_date", "unknown")

        logger.info(
            f"Executing notification operator: {self.__class__.__name__}",
            dag_id=dag_id,
            task_id=task_id_val,
            execution_date=str(execution_date),
        )

        try:
            # Render message template
            rendered_message = self.render_template(self.message_template, context)

            logger.info(
                f"Rendered message (length: {len(rendered_message)} chars)",
                extra={"message_preview": rendered_message[:200]},
            )

            # Send notification
            result = self.send_notification(rendered_message, context)

            if result:
                logger.info(
                    "Notification sent successfully", extra={"operator": self.__class__.__name__}
                )
                return True
            else:
                error_msg = f"Notification failed for {self.__class__.__name__}"
                logger.error(error_msg)
                raise AirflowException(error_msg)

        except AirflowException:
            # Re-raise Airflow exceptions (including template errors)
            raise
        except Exception as e:
            logger.error(
                f"Notification operator failed: {str(e)}",
                dag_id=dag_id,
                task_id=task_id_val,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise AirflowException(f"Notification failed: {str(e)}") from e

    def on_kill(self):
        """Handle task kill event."""
        logger.warning(
            f"Notification operator {self.__class__.__name__} killed",
            extra={"task_id": self.task_id},
        )
