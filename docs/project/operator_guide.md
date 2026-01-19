# Operator Guide

This comprehensive guide documents all custom Airflow operators available in the Apache Airflow ETL Demo Platform, including their parameters, usage examples, and best practices.

---

## Table of Contents

- [Overview](#overview)
- [Spark Operators](#spark-operators)
  - [SparkStandaloneOperator](#sparkstandaloneoperator)
  - [SparkYarnOperator](#sparkyarnoperator)
  - [SparkKubernetesOperator](#sparkkubernetesoperator)
- [Data Quality Operators](#data-quality-operators)
  - [SchemaValidationOperator](#schemavalidationoperator)
  - [CompletenessCheckOperator](#completenesscheckoperator)
  - [FreshnessCheckOperator](#freshnesscheckoperator)
  - [UniquenessCheckOperator](#uniquenesscheckoperator)
  - [NullRateCheckOperator](#nullratecheckoperator)
- [Notification Operators](#notification-operators)
  - [EmailNotificationOperator](#emailnotificationoperator)
  - [MSTeamsNotificationOperator](#msteamsnotificationoperator)
  - [TelegramNotificationOperator](#telegramnotificationoperator)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

All custom operators extend Airflow's `BaseOperator` and follow consistent patterns:

- **Error Handling**: Automatic retries with exponential backoff
- **Logging**: Structured logging via `src.utils.logging_config`
- **Configuration**: Parameters validated at instantiation time
- **Testability**: Unit tests with mocked dependencies

### Import Path

```python
# Spark operators
from src.operators.spark import (
    SparkStandaloneOperator,
    SparkYarnOperator,
    SparkKubernetesOperator
)

# Quality operators
from src.operators.quality import (
    SchemaValidationOperator,
    CompletenessCheckOperator,
    FreshnessCheckOperator,
    UniquenessCheckOperator,
    NullRateCheckOperator
)

# Notification operators
from src.operators.notifications import (
    EmailNotificationOperator,
    MSTeamsNotificationOperator,
    TelegramNotificationOperator
)
```

---

## Spark Operators

All Spark operators submit jobs to distributed Spark clusters and monitor execution until completion.

### SparkStandaloneOperator

Submits Spark jobs to a standalone Spark cluster.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `application_file` | `str` | Yes | - | Path to Spark application (`.py` or `.jar`) |
| `spark_master` | `str` | Yes | - | Spark master URL (e.g., `spark://master:7077`) |
| `application_args` | `List[str]` | No | `[]` | Command-line arguments for Spark application |
| `conf` | `Dict[str, str]` | No | `{}` | Spark configuration properties |
| `total_executor_cores` | `int` | No | `2` | Total cores for all executors |
| `executor_memory` | `str` | No | `'2g'` | Memory per executor |
| `driver_memory` | `str` | No | `'1g'` | Memory for driver |
| `poll_interval` | `int` | No | `30` | Seconds between status checks |
| `timeout` | `int` | No | `3600` | Max execution time (seconds) |

#### Usage Example

```python
from airflow import DAG
from src.operators.spark import SparkStandaloneOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-engineering',
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    dag_id='spark_standalone_example',
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule='@daily',
    catchup=False
) as dag:

    transform_sales_data = SparkStandaloneOperator(
        task_id='transform_sales_data',
        application_file='/opt/airflow/spark_jobs/transform_sales.py',
        spark_master='spark://spark-master:7077',
        application_args=[
            '--input', 's3://my-bucket/raw/sales/{{ ds }}',
            '--output', 's3://my-bucket/processed/sales/{{ ds }}'
        ],
        conf={
            'spark.sql.shuffle.partitions': '200',
            'spark.executor.memoryOverhead': '512m'
        },
        total_executor_cores=8,
        executor_memory='4g',
        driver_memory='2g',
        timeout=7200  # 2 hours
    )
```

#### Behavior

1. Submits Spark application via `spark-submit`
2. Polls Spark REST API for job status every `poll_interval` seconds
3. Returns job metrics (rows processed, execution time) via XCom
4. Raises `AirflowException` on job failure or timeout

#### XCom Output

```python
{
    "job_id": "app-20250101-1234-0001",
    "status": "SUCCESS",
    "duration_seconds": 425,
    "rows_processed": 1500000,
    "output_path": "s3://my-bucket/processed/sales/2025-01-01"
}
```

---

### SparkYarnOperator

Submits Spark jobs to a Hadoop YARN cluster.

#### Parameters

Inherits all parameters from `SparkStandaloneOperator`, plus:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `yarn_queue` | `str` | No | `'default'` | YARN queue name |
| `deploy_mode` | `str` | No | `'cluster'` | Deployment mode (`client` or `cluster`) |
| `num_executors` | `int` | No | `4` | Number of executors |

#### Usage Example

```python
from src.operators.spark import SparkYarnOperator

process_large_dataset = SparkYarnOperator(
    task_id='process_large_dataset',
    application_file='/opt/airflow/spark_jobs/process_dataset.py',
    spark_master='yarn',
    deploy_mode='cluster',
    yarn_queue='data-engineering',
    num_executors=10,
    executor_cores=4,
    executor_memory='8g',
    driver_memory='4g',
    application_args=[
        '--date', '{{ ds }}',
        '--table', 'warehouse.fact_transactions'
    ],
    conf={
        'spark.yarn.maxAppAttempts': '2',
        'spark.dynamicAllocation.enabled': 'true'
    }
)
```

#### YARN-Specific Features

- **Dynamic Allocation**: Automatically scales executors based on workload
- **Queue Management**: Submit to specific YARN queues for resource isolation
- **Cluster Mode**: Driver runs on YARN cluster (recommended for production)

---

### SparkKubernetesOperator

Submits Spark jobs to Kubernetes using Spark's native Kubernetes executor.

#### Parameters

Inherits all parameters from `SparkStandaloneOperator`, plus:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `k8s_namespace` | `str` | No | `'spark'` | Kubernetes namespace |
| `service_account` | `str` | No | `'spark'` | K8s service account for pods |
| `image` | `str` | No | `'apache/spark:3.5.0'` | Docker image for driver/executor |
| `image_pull_policy` | `str` | No | `'IfNotPresent'` | Image pull policy |

#### Usage Example

```python
from src.operators.spark import SparkKubernetesOperator

ml_training = SparkKubernetesOperator(
    task_id='ml_model_training',
    application_file='/opt/airflow/spark_jobs/train_model.py',
    spark_master='k8s://https://kubernetes.default.svc:443',
    k8s_namespace='ml-workloads',
    service_account='spark-ml',
    image='myregistry/spark-ml:3.5.0-cuda',
    num_executors=20,
    executor_cores=4,
    executor_memory='16g',
    driver_memory='8g',
    application_args=['--model', 'xgboost', '--iterations', '100'],
    conf={
        'spark.kubernetes.executor.request.cores': '3.5',
        'spark.kubernetes.executor.limit.cores': '4',
        'spark.kubernetes.executor.podTemplateFile': '/path/to/executor-template.yaml'
    }
)
```

#### Kubernetes-Specific Features

- **Dynamic Pod Creation**: Creates driver and executor pods on-demand
- **Auto-scaling**: Leverages K8s horizontal pod autoscaling
- **Resource Quotas**: Respects K8s namespace resource limits
- **Pod Templates**: Custom pod configurations via YAML templates

---

## Data Quality Operators

All quality operators extend `DataQualityCheckOperator` and support configurable severity levels.

### Severity Levels

| Level | Behavior | Use Case |
|-------|----------|----------|
| `INFO` | Log result, continue | Informational checks |
| `WARNING` | Log warning, continue | Non-critical issues |
| `CRITICAL` | Fail task immediately | Data integrity violations |

### SchemaValidationOperator

Validates that a table schema matches expected structure.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `table_name` | `str` | Yes | - | Table to validate |
| `expected_schema` | `Dict` | Yes | - | Expected schema definition |
| `postgres_conn_id` | `str` | No | `'warehouse'` | Airflow connection ID |
| `severity` | `str` | No | `'CRITICAL'` | Severity level |

#### Expected Schema Format

```python
expected_schema = {
    "columns": [
        {"name": "customer_id", "type": "integer", "nullable": False},
        {"name": "email", "type": "varchar", "nullable": False},
        {"name": "created_at", "type": "timestamp", "nullable": True}
    ]
}
```

#### Usage Example

```python
from src.operators.quality import SchemaValidationOperator

validate_customer_schema = SchemaValidationOperator(
    task_id='validate_customer_schema',
    table_name='warehouse.dim_customer',
    expected_schema={
        "columns": [
            {"name": "customer_id", "type": "integer", "nullable": False},
            {"name": "customer_name", "type": "varchar", "nullable": False},
            {"name": "email", "type": "varchar", "nullable": False},
            {"name": "phone", "type": "varchar", "nullable": True},
            {"name": "created_at", "type": "timestamp", "nullable": False}
        ]
    },
    postgres_conn_id='warehouse',
    severity='CRITICAL'
)
```

#### Checks Performed

1. All expected columns exist
2. Column data types match
3. Nullable constraints are correct
4. No unexpected extra columns (optional)

---

### CompletenessCheckOperator

Validates that required columns have values (no nulls).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `table_name` | `str` | Yes | - | Table to check |
| `required_columns` | `List[str]` | Yes | - | Columns that must be non-null |
| `threshold` | `float` | No | `0.0` | Max allowed null rate (0.0 = 0%, 1.0 = 100%) |
| `postgres_conn_id` | `str` | No | `'warehouse'` | Airflow connection ID |
| `severity` | `str` | No | `'CRITICAL'` | Severity level |

#### Usage Example

```python
from src.operators.quality import CompletenessCheckOperator

check_sales_completeness = CompletenessCheckOperator(
    task_id='check_sales_completeness',
    table_name='warehouse.fact_sales',
    required_columns=['customer_id', 'product_id', 'sale_date', 'sale_amount'],
    threshold=0.01,  # Allow up to 1% nulls
    postgres_conn_id='warehouse',
    severity='CRITICAL'
)
```

#### Output

```python
# XCom result
{
    "check": "completeness",
    "table": "warehouse.fact_sales",
    "columns_checked": ["customer_id", "product_id", "sale_date", "sale_amount"],
    "null_counts": {
        "customer_id": 0,
        "product_id": 5,
        "sale_date": 0,
        "sale_amount": 2
    },
    "total_rows": 10000,
    "null_rate": 0.0007,  # 0.07%
    "passed": True
}
```

---

### FreshnessCheckOperator

Validates that data is recent based on a timestamp column.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `table_name` | `str` | Yes | - | Table to check |
| `timestamp_column` | `str` | Yes | - | Column with timestamp values |
| `max_age_hours` | `int` | No | `24` | Maximum allowed age in hours |
| `postgres_conn_id` | `str` | No | `'warehouse'` | Airflow connection ID |
| `severity` | `str` | No | `'WARNING'` | Severity level |

#### Usage Example

```python
from src.operators.quality import FreshnessCheckOperator

check_data_freshness = FreshnessCheckOperator(
    task_id='check_data_freshness',
    table_name='warehouse.staging_customer_events',
    timestamp_column='event_timestamp',
    max_age_hours=6,  # Data should be less than 6 hours old
    postgres_conn_id='warehouse',
    severity='WARNING'
)
```

#### Behavior

- Queries `MAX(timestamp_column)` from table
- Compares to current time
- Fails if data is older than `max_age_hours`

---

### UniquenessCheckOperator

Validates that specified columns have unique values (no duplicates).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `table_name` | `str` | Yes | - | Table to check |
| `unique_columns` | `List[str]` | Yes | - | Columns that should be unique |
| `threshold` | `float` | No | `0.0` | Max allowed duplicate rate |
| `postgres_conn_id` | `str` | No | `'warehouse'` | Airflow connection ID |
| `severity` | `str` | No | `'CRITICAL'` | Severity level |

#### Usage Example

```python
from src.operators.quality import UniquenessCheckOperator

check_customer_uniqueness = UniquenessCheckOperator(
    task_id='check_customer_uniqueness',
    table_name='warehouse.dim_customer',
    unique_columns=['customer_id'],
    threshold=0.0,  # No duplicates allowed
    postgres_conn_id='warehouse',
    severity='CRITICAL'
)
```

#### Composite Uniqueness

```python
# Check uniqueness of combination of columns
check_sales_uniqueness = UniquenessCheckOperator(
    task_id='check_sales_uniqueness',
    table_name='warehouse.fact_sales',
    unique_columns=['customer_id', 'product_id', 'sale_date'],  # Composite key
    threshold=0.0,
    severity='CRITICAL'
)
```

---

### NullRateCheckOperator

Validates that null rate for columns is within acceptable threshold.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `table_name` | `str` | Yes | - | Table to check |
| `columns` | `List[str]` | Yes | - | Columns to check |
| `max_null_rate` | `float` | No | `0.05` | Max null rate (5% default) |
| `postgres_conn_id` | `str` | No | `'warehouse'` | Airflow connection ID |
| `severity` | `str` | No | `'WARNING'` | Severity level |

#### Usage Example

```python
from src.operators.quality import NullRateCheckOperator

check_null_rates = NullRateCheckOperator(
    task_id='check_null_rates',
    table_name='warehouse.dim_product',
    columns=['product_name', 'category', 'price'],
    max_null_rate=0.02,  # Allow up to 2% nulls
    postgres_conn_id='warehouse',
    severity='WARNING'
)
```

---

## Notification Operators

### EmailNotificationOperator

Sends email notifications via SMTP.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `to` | `str` or `List[str]` | Yes | - | Recipient email address(es) |
| `subject` | `str` | Yes | - | Email subject (supports Jinja templates) |
| `body` | `str` | Yes | - | Email body (HTML or plain text) |
| `cc` | `str` or `List[str]` | No | `None` | CC recipients |
| `bcc` | `str` or `List[str]` | No | `None` | BCC recipients |
| `email_conn_id` | `str` | No | `'smtp_default'` | Airflow SMTP connection ID |
| `html` | `bool` | No | `True` | Send as HTML email |

#### Usage Example

```python
from src.operators.notifications import EmailNotificationOperator

send_success_email = EmailNotificationOperator(
    task_id='send_success_email',
    to=['data-team@example.com', 'manager@example.com'],
    subject='ETL Pipeline {{ dag.dag_id }} Completed Successfully',
    body='''
    <h2>Pipeline Execution Report</h2>
    <p><strong>DAG:</strong> {{ dag.dag_id }}</p>
    <p><strong>Execution Date:</strong> {{ ds }}</p>
    <p><strong>Status:</strong> SUCCESS</p>
    <p><strong>Duration:</strong> {{ ti.duration }} seconds</p>

    <h3>Summary</h3>
    <ul>
        <li>Records Processed: {{ ti.xcom_pull(task_ids='extract_data')['row_count'] }}</li>
        <li>Quality Checks: PASSED</li>
    </ul>
    ''',
    cc='stakeholders@example.com',
    html=True
)
```

#### Email Templates

For reusable templates, store in `dags/templates/emails/`:

```python
send_email = EmailNotificationOperator(
    task_id='send_email',
    to='team@example.com',
    subject='Pipeline Report',
    body='{{ dag.get_template("email_report.html").render(context) }}'
)
```

---

### MSTeamsNotificationOperator

Sends notifications to Microsoft Teams via webhooks.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | `str` | Yes | - | Message text (Markdown supported) |
| `title` | `str` | No | `None` | Card title |
| `webhook_url` | `str` | No | - | Teams webhook URL (or use connection) |
| `teams_conn_id` | `str` | No | `'teams_default'` | Airflow connection ID |
| `color` | `str` | No | `'0078D7'` | Theme color (hex code) |

#### Usage Example

```python
from src.operators.notifications import MSTeamsNotificationOperator

notify_teams = MSTeamsNotificationOperator(
    task_id='notify_teams',
    title='🚀 ETL Pipeline Completed',
    message='''
    **DAG:** `{{ dag.dag_id }}`
    **Date:** {{ ds }}
    **Status:** SUCCESS ✅

    **Metrics:**
    - Records: {{ ti.xcom_pull(task_ids='transform')['record_count'] }}
    - Duration: {{ ti.duration }}s
    ''',
    teams_conn_id='teams_data_engineering',
    color='00FF00'  # Green for success
)
```

#### Conditional Notifications

```python
from airflow.operators.python import BranchPythonOperator

def decide_notification(**context):
    task_instance = context['task_instance']
    state = task_instance.state
    return 'notify_teams_success' if state == 'success' else 'notify_teams_failure'

branch = BranchPythonOperator(
    task_id='decide_notification',
    python_callable=decide_notification
)

notify_success = MSTeamsNotificationOperator(
    task_id='notify_teams_success',
    title='Success',
    message='Pipeline completed',
    color='00FF00'
)

notify_failure = MSTeamsNotificationOperator(
    task_id='notify_teams_failure',
    title='Failure',
    message='Pipeline failed',
    color='FF0000'
)

branch >> [notify_success, notify_failure]
```

---

### TelegramNotificationOperator

Sends notifications to Telegram via Bot API.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | `str` | Yes | - | Message text (Markdown or HTML) |
| `chat_id` | `str` | No | - | Telegram chat ID |
| `telegram_conn_id` | `str` | No | `'telegram_default'` | Airflow connection ID |
| `parse_mode` | `str` | No | `'Markdown'` | Parse mode (`Markdown` or `HTML`) |

#### Usage Example

```python
from src.operators.notifications import TelegramNotificationOperator

alert_telegram = TelegramNotificationOperator(
    task_id='alert_telegram',
    message='''
    🔴 *CRITICAL ALERT*

    *Pipeline:* `{{ dag.dag_id }}`
    *Task:* `{{ task.task_id }}`
    *Status:* FAILED

    *Error:* {{ ti.xcom_pull(task_ids='failing_task')['error'] }}

    Action required immediately!
    ''',
    telegram_conn_id='telegram_oncall',
    parse_mode='Markdown'
)
```

#### Setup Telegram Connection

In Airflow UI:
1. Go to **Admin → Connections**
2. Create new connection:
   - **Conn ID**: `telegram_default`
   - **Conn Type**: `HTTP`
   - **Host**: `https://api.telegram.org`
   - **Password**: `<bot_token>` (from BotFather)
   - **Extra**: `{"chat_id": "<your_chat_id>"}`

---

## Best Practices

### 1. Use Task Retries with Exponential Backoff

```python
from datetime import timedelta

default_args = {
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(hours=1)
}
```

### 2. Set Appropriate Timeouts

```python
# Spark job with 2-hour timeout
spark_task = SparkStandaloneOperator(
    task_id='long_running_job',
    application_file='/path/to/job.py',
    spark_master='spark://master:7077',
    timeout=7200,  # 2 hours
    execution_timeout=timedelta(hours=2.5)  # Airflow-level timeout
)
```

### 3. Use XCom for Metadata, Not Large Data

```python
# ✅ Good: Store metadata
def extract_data(**context):
    # ... extract logic ...
    return {
        "row_count": 1000000,
        "file_path": "s3://bucket/data.parquet",
        "extraction_time": "2025-01-01T10:30:00Z"
    }

# ❌ Bad: Store large datasets
def extract_data(**context):
    df = pd.read_csv(...)  # Large DataFrame
    return df.to_dict()  # Don't do this!
```

### 4. Chain Quality Checks

```python
from airflow.models import TaskGroup

with TaskGroup(group_id='quality_checks') as quality_group:
    schema_check = SchemaValidationOperator(...)
    completeness_check = CompletenessCheckOperator(...)
    freshness_check = FreshnessCheckOperator(...)

    # All quality checks run in parallel
    [schema_check, completeness_check, freshness_check]

# Then proceed with next step
extract >> transform >> quality_group >> load
```

### 5. Severity-Based Workflows

```python
# CRITICAL failures stop the pipeline
critical_check = SchemaValidationOperator(
    task_id='critical_schema_check',
    table_name='warehouse.fact_sales',
    expected_schema={...},
    severity='CRITICAL'  # Will fail task if check fails
)

# WARNING allows pipeline to continue
warning_check = NullRateCheckOperator(
    task_id='warning_null_check',
    table_name='warehouse.dim_product',
    columns=['description'],
    max_null_rate=0.10,
    severity='WARNING'  # Logs warning, continues
)

critical_check >> warning_check >> load_data
```

### 6. Notification Patterns

```python
# On-success callback
def on_success_callback(context):
    EmailNotificationOperator(
        task_id='success_email',
        to='team@example.com',
        subject='Success',
        body='Pipeline completed'
    ).execute(context)

# On-failure callback
def on_failure_callback(context):
    TelegramNotificationOperator(
        task_id='failure_alert',
        message='🔴 Pipeline failed!',
        chat_id='oncall'
    ).execute(context)

dag = DAG(
    dag_id='my_pipeline',
    default_args={
        'on_success_callback': on_success_callback,
        'on_failure_callback': on_failure_callback
    }
)
```

---

## Troubleshooting

### Spark Operators

**Issue**: Spark job times out

**Solution**:
```python
# Increase timeout and check Spark cluster logs
spark_task = SparkStandaloneOperator(
    task_id='job',
    application_file='job.py',
    spark_master='spark://master:7077',
    timeout=10800,  # 3 hours
    poll_interval=60  # Check status every minute
)
```

**Issue**: Out of memory errors

**Solution**:
```python
spark_task = SparkYarnOperator(
    task_id='job',
    application_file='job.py',
    spark_master='yarn',
    executor_memory='8g',  # Increase executor memory
    driver_memory='4g',    # Increase driver memory
    conf={
        'spark.executor.memoryOverhead': '1g',  # Add overhead
        'spark.sql.shuffle.partitions': '400'   # Increase partitions
    }
)
```

---

### Quality Operators

**Issue**: False positives on schema checks

**Solution**:
```python
# Be specific about expected types and allow nullable columns
expected_schema = {
    "columns": [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "description", "type": "text", "nullable": True}  # Allow nulls
    ]
}
```

**Issue**: Completeness checks too strict

**Solution**:
```python
# Allow small percentage of nulls for optional fields
check = CompletenessCheckOperator(
    task_id='check',
    table_name='table',
    required_columns=['optional_field'],
    threshold=0.05,  # Allow 5% nulls
    severity='WARNING'  # Don't fail pipeline
)
```

---

### Notification Operators

**Issue**: Email not sent

**Solution**:
1. Verify SMTP connection in Airflow UI
2. Check firewall allows port 587/465
3. Enable "Allow less secure apps" for Gmail
4. Check Airflow logs for SMTP errors

**Issue**: Teams webhook returns 400 error

**Solution**:
```python
# Ensure message is valid Markdown
notify = MSTeamsNotificationOperator(
    task_id='notify',
    title='Title',
    message='**Bold** _italic_ `code`',  # Valid Markdown
    webhook_url='<correct_webhook_url>'
)
```

---

## See Also

- [Architecture Documentation](architecture.md) - System design overview
- [DAG Configuration Guide](dag_configuration.md) - JSON schema for dynamic DAGs
- [Retry and Failure Handling](retry_and_failure_handling.md) - Comprehensive retry strategies
- [Development Guide](development.md) - Local setup and testing
- [Example DAG Catalog](dag_examples_catalog.md) - 14 example DAGs

---

**Last Updated**: 2025-10-21
**Maintained By**: Platform Team