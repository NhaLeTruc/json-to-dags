"""
Email Notification Operator for Apache Airflow.

Custom operator for sending email notifications via SMTP with support for
HTML/plain text, attachments, CC/BCC recipients, and template rendering.
"""

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from airflow.exceptions import AirflowException

from src.operators.notifications.base_notification import BaseNotificationOperator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailNotificationOperator(BaseNotificationOperator):
    """
    Operator for sending email notifications via SMTP.

    Supports HTML and plain text emails, multiple recipients, CC/BCC,
    attachments, and Jinja2 template rendering for subject and body.

    :param to: Recipient email address(es) - string or list of strings
    :param subject: Email subject (supports Jinja2 templating)
    :param message_template: Email body template (supports Jinja2 templating)
    :param from_email: Sender email address (default: from SMTP config)
    :param cc: CC recipient(s) - string or list of strings
    :param bcc: BCC recipient(s) - string or list of strings
    :param html: If True, send as HTML email; otherwise plain text
    :param files: List of file paths to attach
    :param smtp_host: SMTP server hostname
    :param smtp_port: SMTP server port (default: 587 for TLS)
    :param smtp_user: SMTP username for authentication
    :param smtp_password: SMTP password for authentication
    :param use_ssl: Use SSL instead of TLS (port 465)
    """

    template_fields = ("to", "subject", "message_template", "cc", "bcc")
    ui_color = "#4caf50"  # Green for email


    def __init__(
        self,
        *,
        to: str | list[str],
        subject: str,
        message_template: str,
        from_email: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
        html: bool = False,
        files: list[str] | None = None,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        use_ssl: bool = False,
        **kwargs,
    ):
        """Initialize EmailNotificationOperator."""
        super().__init__(message_template=message_template, **kwargs)

        # Validate and normalize recipients
        self.to = self._validate_emails(to, "to")
        self.cc = self._validate_emails(cc, "cc") if cc else []
        self.bcc = self._validate_emails(bcc, "bcc") if bcc else []

        # Validate from_email if provided
        if from_email:
            self._validate_emails(from_email, "from_email")

        self.subject = subject
        self.from_email = from_email or smtp_user or "airflow@localhost"
        self.html = html
        self.files = files or []
        if self.files:
            logger.warning(
                "File attachments are not yet implemented. "
                f"{len(self.files)} file(s) will be ignored."
            )

        # SMTP configuration
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_ssl = use_ssl

        # Log configuration
        logger.info(
            f"Email operator initialized: {len(self._to_list(self.to))} recipient(s), "
            f"SMTP={smtp_host}:{smtp_port}, SSL={use_ssl}"
        )

    def _validate_emails(self, emails: str | list[str], field_name: str) -> str | list[str]:
        """
        Validate email address format.

        :param emails: Single email or list of emails
        :param field_name: Field name for error messages
        :return: Validated email(s)
        :raises ValueError: If email format is invalid
        """
        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        def validate_single(email: str) -> str:
            email = email.strip()
            if not email_pattern.match(email):
                raise ValueError(f"Invalid email format for {field_name}: {email}")
            return email

        if isinstance(emails, str):
            return validate_single(emails)
        elif isinstance(emails, list):
            return [validate_single(email) for email in emails]
        else:
            raise ValueError(f"{field_name} must be a string or list of strings")

    def _to_list(self, emails: str | list[str]) -> list[str]:
        """Convert email or list of emails to list."""
        return [emails] if isinstance(emails, str) else emails

    def _create_message(self, subject: str, body: str, context: dict[str, Any]) -> MIMEMultipart:
        """
        Create email message with headers and body.

        :param subject: Rendered email subject
        :param body: Rendered email body
        :param context: Airflow context for additional info
        :return: Configured MIMEMultipart message
        """
        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self._to_list(self.to))
        msg["Subject"] = subject

        # Add CC and BCC headers
        if self.cc:
            msg["Cc"] = ", ".join(self._to_list(self.cc))
        if self.bcc:
            # BCC is not added to headers (hidden recipients)
            pass

        # Attach body
        mime_subtype = "html" if self.html else "plain"
        msg.attach(MIMEText(body, mime_subtype))

        # Note: Attachment support can be added here if needed
        # For now, files parameter is acknowledged but not implemented

        return msg

    def send_notification(self, message: str, context: dict[str, Any]) -> bool:
        """
        Send email notification via SMTP.

        :param message: Rendered email body
        :param context: Airflow context dictionary
        :return: True if email sent successfully
        :raises AirflowException: If SMTP connection or sending fails
        """
        try:
            # Render subject with context
            rendered_subject = self.render_template(self.subject, context)

            # Create email message
            msg = self._create_message(rendered_subject, message, context)

            # Get all recipients (To + CC + BCC)
            all_recipients = (
                self._to_list(self.to) + self._to_list(self.cc) + self._to_list(self.bcc)
            )

            logger.info(
                f"Sending email to {len(all_recipients)} recipient(s)",
                extra={
                    "subject": rendered_subject,
                    "to": self._to_list(self.to),
                    "smtp_host": self.smtp_host,
                },
            )

            # Send email via SMTP
            if self.use_ssl:
                # Use SMTP_SSL for port 465
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                # Use SMTP with STARTTLS for port 587
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

            logger.info("Email sent successfully", extra={"recipients": len(all_recipients)})
            return True

        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connection failed: {str(e)}")
            raise AirflowException(f"SMTP connection error: {str(e)}") from e

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            raise AirflowException(f"SMTP authentication error: {str(e)}") from e

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected: {str(e)}")
            raise AirflowException(f"SMTP server disconnected: {str(e)}") from e

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            raise AirflowException(f"SMTP error: {str(e)}") from e

        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}", exc_info=True)
            raise AirflowException(f"Email sending failed: {str(e)}") from e
