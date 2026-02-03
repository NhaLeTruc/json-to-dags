"""
Notification Message Templates.

Provides reusable Jinja2 templates for common notification scenarios
including success, failure, and data quality alerts.
"""

from typing import Any


class NotificationTemplates:
    """Collection of reusable notification message templates."""

    # Success notification templates
    SUCCESS_SIMPLE = """
✅ **DAG Execution Successful**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}
**Run ID**: {{ run_id }}

The pipeline completed successfully.
    """.strip()

    SUCCESS_DETAILED = """
✅ **Pipeline Execution Completed Successfully**

**Details:**
- DAG ID: {{ dag.dag_id }}
- Task ID: {{ task.task_id }}
- Execution Date: {{ ds }}
- Run ID: {{ run_id }}
- Try Number: {{ task_instance.try_number }}
- Duration: {{ (task_instance.end_date - task_instance.start_date).total_seconds() if task_instance.end_date and task_instance.start_date else 'N/A' }} seconds

**Next Steps:**
- Review logs in Airflow UI
- Verify data quality checks
- Monitor downstream dependencies

View in Airflow: {{ conf.get('webserver', 'base_url', fallback='http://localhost:8080') }}/dags/{{ dag.dag_id }}/grid
    """.strip()

    # Failure notification templates
    FAILURE_SIMPLE = """
❌ **DAG Execution Failed**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}
**Run ID**: {{ run_id }}

The pipeline encountered an error. Please investigate.
    """.strip()

    FAILURE_DETAILED = """
❌ **Pipeline Execution Failed**

**Error Details:**
- DAG ID: {{ dag.dag_id }}
- Task ID: {{ task.task_id }}
- Execution Date: {{ ds }}
- Run ID: {{ run_id }}
- Try Number: {{ task_instance.try_number }} of {{ task_instance.max_tries }}
- State: {{ task_instance.state }}

{% if exception is defined and exception %}
**Exception:**
```
{{ exception }}
```
{% endif %}

**Actions Required:**
1. Review task logs in Airflow UI
2. Check upstream dependencies
3. Verify data source availability
4. Clear task and retry if transient error

View in Airflow: {{ conf.get('webserver', 'base_url', fallback='http://localhost:8080') }}/dags/{{ dag.dag_id }}/grid?dag_run_id={{ run_id }}
    """.strip()

    # Retry notification template
    RETRY_NOTIFICATION = """
⚠️ **Task Retry in Progress**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}
**Retry**: {{ task_instance.try_number }} of {{ task_instance.max_tries }}

The task will be retried automatically.
    """.strip()

    # Data quality alert templates
    DATA_QUALITY_ALERT = """
⚠️ **Data Quality Check Failed**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}

**Quality Issue:**
- Check Type: {{ check_type if check_type is defined else 'Unknown' }}
- Table: {{ table_name if table_name is defined else 'Unknown' }}
- Severity: {{ severity if severity is defined else 'UNKNOWN' }}
- Failure Rate: {{ failure_rate if failure_rate is defined else 'N/A' }}%

{% if rows_failed is defined %}
**Impact:**
- Rows Checked: {{ rows_checked if rows_checked is defined else 0 }}
- Rows Failed: {{ rows_failed }}
{% endif %}

**Actions Required:**
1. Review data source quality
2. Check ETL transformation logic
3. Validate upstream data integrity
4. Update quality thresholds if needed

View details in Airflow UI.
    """.strip()

    DATA_QUALITY_CRITICAL = """
🚨 **CRITICAL Data Quality Failure**

**PIPELINE HALTED**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}

**Critical Issue Detected:**
- Check Type: {{ check_type if check_type is defined else 'Unknown' }}
- Table: {{ table_name if table_name is defined else 'Unknown' }}
- Severity: CRITICAL
- Failure Rate: {{ failure_rate if failure_rate is defined else 'N/A' }}%

{% if error_message is defined and error_message %}
**Error Message:**
{{ error_message }}
{% endif %}

**IMMEDIATE ACTION REQUIRED:**
This is a critical data quality failure that has halted the pipeline.
1. Investigate root cause immediately
2. Do NOT manually override quality checks
3. Contact data engineering team if needed
4. Fix data quality issues at source

View in Airflow: {{ conf.get('webserver', 'base_url', fallback='http://localhost:8080') }}/dags/{{ dag.dag_id }}/grid
    """.strip()

    # SLA miss notification
    SLA_MISS = """
⏰ **SLA Missed**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}

**SLA Details:**
- Expected completion: {{ expected_time if expected_time is defined else 'Unknown' }}
- Actual completion: {{ actual_time if actual_time is defined else 'In progress' }}
- Delay: {{ delay if delay is defined else 'Unknown' }}

**Impact:**
- Downstream processes may be delayed
- Business reports may be late

**Actions:**
1. Identify bottleneck in pipeline
2. Optimize slow tasks
3. Consider increasing resources
4. Review SLA thresholds

View in Airflow UI for details.
    """.strip()

    # Spark job notification templates
    SPARK_JOB_SUCCESS = """
✅ **Spark Job Completed Successfully**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}

**Spark Job Details:**
- Cluster Type: {{ cluster_type if cluster_type is defined else 'Unknown' }}
- Job ID: {{ spark_job_id if spark_job_id is defined else 'Unknown' }}
- Duration: {{ duration_seconds if duration_seconds is defined else 'Unknown' }} seconds
- Application: {{ application_name if application_name is defined else 'Unknown' }}

{% if logs_url is defined and logs_url %}
View Spark UI: {{ logs_url }}
{% endif %}

The Spark job executed successfully and data processing is complete.
    """.strip()

    SPARK_JOB_FAILURE = """
❌ **Spark Job Failed**

**DAG**: {{ dag.dag_id }}
**Task**: {{ task.task_id }}
**Execution Date**: {{ ds }}

**Spark Job Details:**
- Cluster Type: {{ cluster_type if cluster_type is defined else 'Unknown' }}
- Job ID: {{ spark_job_id if spark_job_id is defined else 'Unknown' }}
- Application: {{ application_name if application_name is defined else 'Unknown' }}

{% if error_message is defined and error_message %}
**Error:**
```
{{ error_message }}
```
{% endif %}

**Actions Required:**
1. Check Spark application logs
2. Verify cluster resources
3. Review data input/output paths
4. Check Spark configuration

{% if logs_url is defined and logs_url %}
View Spark UI: {{ logs_url }}
{% endif %}
    """.strip()

    # Custom template builder helpers
    @staticmethod
    def build_teams_facts(context: dict[str, Any]) -> list:
        """
        Build facts array for Teams MessageCard.

        :param context: Airflow context
        :return: List of fact dictionaries
        """
        return [
            {"name": "DAG ID", "value": "{{ dag.dag_id }}"},
            {"name": "Task ID", "value": "{{ task.task_id }}"},
            {"name": "Execution Date", "value": "{{ ds }}"},
            {"name": "Run ID", "value": "{{ run_id }}"},
            {"name": "State", "value": "{{ task_instance.state }}"},
        ]

    @staticmethod
    def build_teams_actions(dag_id: str, run_id: str, base_url: str = "http://localhost:8080") -> list:
        """
        Build actions array for Teams MessageCard.

        :param dag_id: DAG identifier
        :param run_id: Run identifier
        :param base_url: Airflow webserver base URL (default: http://localhost:8080)
        :return: List of action dictionaries
        """
        return [
            {
                "@type": "OpenUri",
                "name": "View in Airflow",
                "targets": [
                    {
                        "os": "default",
                        "uri": f"{base_url}/dags/{dag_id}/grid",
                    }
                ],
            }
        ]


# Pre-defined template sets for common scenarios
NOTIFICATION_TEMPLATES = {
    "success": {
        "simple": NotificationTemplates.SUCCESS_SIMPLE,
        "detailed": NotificationTemplates.SUCCESS_DETAILED,
    },
    "failure": {
        "simple": NotificationTemplates.FAILURE_SIMPLE,
        "detailed": NotificationTemplates.FAILURE_DETAILED,
    },
    "retry": NotificationTemplates.RETRY_NOTIFICATION,
    "data_quality": {
        "warning": NotificationTemplates.DATA_QUALITY_ALERT,
        "critical": NotificationTemplates.DATA_QUALITY_CRITICAL,
    },
    "sla": NotificationTemplates.SLA_MISS,
    "spark": {
        "success": NotificationTemplates.SPARK_JOB_SUCCESS,
        "failure": NotificationTemplates.SPARK_JOB_FAILURE,
    },
}


def get_template(category: str, subcategory: str = None) -> str:
    """
    Get a notification template by category and subcategory.

    :param category: Template category (e.g., 'success', 'failure')
    :param subcategory: Template subcategory (e.g., 'simple', 'detailed')
    :return: Template string
    :raises ValueError: If template not found
    """
    if subcategory:
        template = NOTIFICATION_TEMPLATES.get(category, {}).get(subcategory)
    else:
        template = NOTIFICATION_TEMPLATES.get(category)

    if template is None:
        raise ValueError(f"Template not found: category='{category}', subcategory='{subcategory}'")

    return template
