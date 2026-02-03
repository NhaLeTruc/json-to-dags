"""
Demo DAG: Notification Basics

Demonstrates multi-channel notification operators for success and failure scenarios.
This beginner-level DAG shows how to:
- Send email notifications
- Send Microsoft Teams notifications
- Send Telegram notifications
- Use notification templates with Jinja2
- Configure notifications for success and failure callbacks

Learning objectives:
- Understand notification operator configuration
- Use template variables in messages
- Set up multiple notification channels
- Handle notification failures gracefully
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Import custom notification operators
from src.operators.notifications.email_operator import EmailNotificationOperator
from src.operators.notifications.teams_operator import TeamsNotificationOperator
from src.operators.notifications.telegram_operator import TelegramNotificationOperator

# Import notification templates
from src.utils.notification_templates import get_template

# Default arguments for all tasks
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email": ["airflow@example.com"],
    "email_on_failure": False,  # We'll use custom notification operators
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# Create DAG
with DAG(
    dag_id="demo_notification_basics_v1",
    default_args=default_args,
    description="Demonstrate multi-channel notification operators",
    schedule=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["demo", "beginner", "notifications"],
) as dag:
    # Task 1: Simple bash task that succeeds
    simple_success_task = BashOperator(
        task_id="simple_success_task",
        bash_command="echo 'Task executed successfully at {{ ts }}'",
    )

    # Task 2: Email notification on success
    send_email_notification = EmailNotificationOperator(
        task_id="send_email_notification",
        to="admin@example.com",
        subject="[Airflow] {{ dag.dag_id }} - Success",
        message_template=get_template("success", "simple"),
        html=False,
        smtp_host="{{ var.value.get('smtp_host', 'localhost') }}",
        smtp_port=587,
        smtp_user="{{ var.value.get('smtp_user', '') }}",
        smtp_password="{{ var.value.get('smtp_password', '') }}",
    )

    # Task 3: Teams notification with custom facts
    send_teams_notification = TeamsNotificationOperator(
        task_id="send_teams_notification",
        webhook_url="{{ var.value.get('teams_webhook_url', 'https://outlook.office.com/webhook/dummy') }}",
        message_template="""
Pipeline executed successfully! All tasks completed without errors.

**Summary:**
- Total tasks: {{ dag.task_count if dag.task_count is defined else 'N/A' }}
- Execution time: {{ execution_date }}
- Next run: {{ next_execution_date if next_execution_date is defined else 'Manual trigger only' }}
        """.strip(),
        title="✅ {{ dag.dag_id }} - Success",
        theme_color="00FF00",  # Green
        facts=[
            {"name": "DAG ID", "value": "{{ dag.dag_id }}"},
            {"name": "Execution Date", "value": "{{ ds }}"},
            {"name": "Task ID", "value": "{{ task.task_id }}"},
            {"name": "State", "value": "{{ task_instance.state }}"},
        ],
    )

    # Task 4: Telegram notification with Markdown formatting
    send_telegram_notification = TelegramNotificationOperator(
        task_id="send_telegram_notification",
        bot_token="{{ var.value.get('telegram_bot_token', '123456:ABC-DEF') }}",
        chat_id="{{ var.value.get('telegram_chat_id', '12345') }}",
        message_template="""
*Pipeline Success* ✅

*DAG:* `{{ dag.dag_id }}`
*Task:* `{{ task.task_id }}`
*Date:* {{ ds }}
*Run ID:* `{{ run_id }}`

All tasks completed successfully!
        """.strip(),
        parse_mode="Markdown",
        disable_notification=False,  # Enable sound
    )

    # Task 5: Python task that simulates work
    def process_data(**context):
        """Simulate data processing."""
        import random
        import time

        time.sleep(2)  # Simulate processing

        # Return some stats for downstream use
        return {
            "records_processed": random.randint(100, 1000),
            "processing_time_seconds": 2,
        }

    process_data_task = PythonOperator(
        task_id="process_data_task",
        python_callable=process_data,
    )

    # Task 6: Detailed success notification with processing stats
    send_detailed_notification = EmailNotificationOperator(
        task_id="send_detailed_notification",
        to=["admin@example.com", "team@example.com"],
        subject="[Airflow] {{ dag.dag_id }} - Processing Complete",
        message_template=get_template("success", "detailed"),
        html=True,
        smtp_host="{{ var.value.get('smtp_host', 'localhost') }}",
        smtp_port=587,
    )

    # Task 7: Summary notification (always runs)
    send_summary_notification = EmailNotificationOperator(
        task_id="send_summary_notification",
        to="admin@example.com",
        subject="[Airflow] {{ dag.dag_id }} - Execution Summary",
        message_template="""
**DAG Execution Summary**

**DAG:** {{ dag.dag_id }}
**Execution Date:** {{ ds }}
**Run ID:** {{ run_id }}

**Status:** {{ task_instance.state|upper }}

**Tasks Executed:**
- simple_success_task
- process_data_task
- Multiple notification tasks

**Next Steps:**
- Review logs if any issues occurred
- Verify notifications were delivered
- Check downstream dependencies

This is an automated notification from Airflow.
        """.strip(),
        html=False,
        smtp_host="{{ var.value.get('smtp_host', 'localhost') }}",
        smtp_port=587,
        trigger_rule="all_done",  # Run regardless of upstream status
    )

    # Define task dependencies
    # Simple linear flow for success notifications
    simple_success_task >> send_email_notification
    simple_success_task >> send_teams_notification
    simple_success_task >> send_telegram_notification

    # Parallel processing and notification
    simple_success_task >> process_data_task
    process_data_task >> send_detailed_notification

    # Summary notification at the end (waits for all tasks)
    [
        send_email_notification,
        send_teams_notification,
        send_telegram_notification,
        send_detailed_notification,
    ] >> send_summary_notification


# DAG Documentation
"""
## Configuration Required

This DAG requires the following Airflow Variables to be set:

### Email Configuration
- `smtp_host`: SMTP server hostname (default: localhost)
- `smtp_port`: SMTP server port (default: 587)
- `smtp_user`: SMTP username for authentication
- `smtp_password`: SMTP password for authentication

### Teams Configuration
- `teams_webhook_url`: Microsoft Teams incoming webhook URL

### Telegram Configuration
- `telegram_bot_token`: Telegram Bot API token
- `telegram_chat_id`: Telegram chat ID to send messages to

## Setting Variables

Via Airflow UI:
Admin → Variables → Add a new record

Via CLI:
```bash
airflow variables set smtp_host "smtp.gmail.com"
airflow variables set teams_webhook_url "https://outlook.office.com/webhook/your-webhook"
airflow variables set telegram_bot_token "123456:ABC-DEF..."
airflow variables set telegram_chat_id "12345"
```

## Testing Locally

For local testing without real SMTP/Teams/Telegram:
1. Leave variables unset (defaults will be used)
2. Check Airflow logs for notification attempts
3. Notifications will fail gracefully and log errors

## Usage

1. Set required variables (see above)
2. Enable the DAG in Airflow UI
3. Trigger manually: Click "Trigger DAG" button
4. Monitor execution in Grid view
5. Check email/Teams/Telegram for notifications

## Learning Exercises

1. Add a CC recipient to email notifications
2. Change Teams theme color to red for failures
3. Add silent Telegram notifications (disable_notification=True)
4. Uncomment the failing task to test failure notifications
5. Create a custom message template
6. Add attachment support to email operator
7. Implement notification retry logic
"""
