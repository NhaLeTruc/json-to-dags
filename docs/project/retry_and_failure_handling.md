# Operator Guide: Retry and Failure Handling Patterns

Complete guide to implementing robust retry and failure handling patterns in Apache Airflow ETL pipelines.

## Table of Contents

- [Overview](#overview)
- [Retry Strategies](#retry-strategies)
- [Timeout Management](#timeout-management)
- [Failure Handling](#failure-handling)
- [Trigger Rules](#trigger-rules)
- [Compensation Logic](#compensation-logic)
- [Error Logging](#error-logging)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

Resilient pipelines handle failures gracefully through:
- **Automatic retries** with configurable backoff strategies
- **Timeout enforcement** to prevent hung tasks
- **Failure propagation** control via trigger rules
- **Compensation logic** for cleanup and rollback
- **Comprehensive error logging** for debugging

## Retry Strategies

### Exponential Backoff (Recommended)

Doubles the delay between each retry attempt.

**When to use**: Most scenarios, especially external API calls and database operations

**Configuration**:

```python
from src.utils.retry_policies import create_retry_config

retry_config = create_retry_config(
    max_retries=3,
    strategy="exponential",
    base_delay=60,  # 1 minute
    max_delay=600   # 10 minutes cap
)

# Retry delays: 60s → 120s → 240s → 480s (capped at 600s)
```

**Advantages**:
- Reduces load on failing systems
- Gives systems time to recover
- Standard industry practice

**Use in default_args**:

```python
default_args = {
    "owner": "data_team",
    **retry_config,
}
```

### Linear Backoff

Increases delay by a fixed amount each retry.

**When to use**: Predictable recovery times, rate limiting scenarios

**Configuration**:

```python
retry_config = create_retry_config(
    max_retries=4,
    strategy="linear",
    base_delay=60
)

# Retry delays: 60s → 120s → 180s → 240s
```

**Advantages**:
- Predictable retry schedule
- Gentler increase than exponential

### Fixed Backoff

Same delay for all retry attempts.

**When to use**: Known fixed recovery windows, simple retry logic

**Configuration**:

```python
retry_config = create_retry_config(
    max_retries=5,
    strategy="fixed",
    base_delay=120  # Always 2 minutes
)

# Retry delays: 120s → 120s → 120s → 120s → 120s
```

**Advantages**:
- Simplest to understand
- Consistent behavior

## Timeout Management

### Task-Level Timeouts

Prevent tasks from running indefinitely.

**Configuration**:

```python
from src.utils.timeout_handler import create_timeout_config

timeout_config = create_timeout_config(
    timeout_seconds=1800  # 30 minutes
)

default_args = {
    "owner": "data_team",
    **timeout_config,
}
```

### Timeout with Callback

Execute custom logic when timeout occurs.

```python
def on_timeout_callback(context):
    """Called when task times out."""
    task_id = context["task"].task_id
    execution_date = context["execution_date"]

    logger.error(
        "Task timeout",
        task_id=task_id,
        execution_date=str(execution_date)
    )

    # Send alert, cleanup resources, etc.

timeout_config = create_timeout_config(
    timeout_seconds=1800,
    on_timeout_callback=on_timeout_callback
)
```

### Monitoring Timeout Approaching

Warn before timeout is reached.

```python
from src.utils.timeout_handler import should_warn_about_timeout

start_time = task_instance.start_date
current_time = datetime.now()

if should_warn_about_timeout(start_time, current_time, 1800, threshold=0.8):
    logger.warning("Task approaching timeout (80% elapsed)")
```

## Failure Handling

### Downstream Task Skipping

By default, downstream tasks skip when upstream fails.

```python
# Task A fails → Task B automatically skips
task_a >> task_b
```

**Behavior**:
- Task B state: `SKIPPED`
- Task B doesn't consume resources
- Failure doesn't propagate further

### Parallel Task Independence

Parallel tasks continue even if siblings fail.

```python
# If task_a fails, task_b still runs
[task_a, task_b] >> task_c
```

**Behavior**:
- Task A fails → Task B continues
- Task C waits for both (may skip if default trigger)

### Failure Callbacks

Execute custom logic on task failure.

```python
def on_failure_callback(context):
    """Called when task fails after all retries."""
    task_id = context["task"].task_id
    exception = context.get("exception")
    try_number = context["task_instance"].try_number

    logger.error(
        "Task failed permanently",
        task_id=task_id,
        try_number=try_number,
        exception=str(exception),
        error_type=type(exception).__name__
    )

    # Send alerts, create tickets, etc.

default_args = {
    "on_failure_callback": on_failure_callback,
}
```

### Retry Callbacks

Execute logic on each retry attempt.

```python
def on_retry_callback(context):
    """Called when task is retried."""
    task_id = context["task"].task_id
    try_number = context["task_instance"].try_number
    max_tries = context["task_instance"].max_tries

    logger.warning(
        "Task retrying",
        task_id=task_id,
        try_number=try_number,
        max_tries=max_tries
    )

default_args = {
    "on_retry_callback": on_retry_callback,
}
```

## Trigger Rules

Control when tasks execute based on upstream states.

### ALL_SUCCESS (Default)

Task runs only if ALL upstream tasks succeeded.

```python
from airflow.utils.trigger_rule import TriggerRule

task = BashOperator(
    task_id="task",
    bash_command="echo 'All upstream succeeded'",
    trigger_rule=TriggerRule.ALL_SUCCESS,  # Default
)
```

### ONE_SUCCESS

Task runs if AT LEAST ONE upstream task succeeded.

```python
task = BashOperator(
    task_id="merge_results",
    bash_command="echo 'At least one branch succeeded'",
    trigger_rule=TriggerRule.ONE_SUCCESS,
)

# Use for: Partial result processing
```

### ALL_FAILED

Task runs only if ALL upstream tasks failed.

```python
task = BashOperator(
    task_id="send_failure_alert",
    bash_command="echo 'Everything failed'",
    trigger_rule=TriggerRule.ALL_FAILED,
)

# Use for: Global failure handling
```

### ALL_DONE

Task runs after ALL upstream tasks complete (success OR failure).

```python
task = BashOperator(
    task_id="cleanup",
    bash_command="echo 'Cleaning up resources'",
    trigger_rule=TriggerRule.ALL_DONE,
)

# Use for: Cleanup, final status checks
```

### ONE_FAILED

Task runs if AT LEAST ONE upstream task failed.

```python
task = BashOperator(
    task_id="partial_failure_handler",
    bash_command="echo 'Something went wrong'",
    trigger_rule=TriggerRule.ONE_FAILED,
)
```

### NONE_FAILED

Task runs if NO upstream tasks failed (skipped = ok).

```python
task = BashOperator(
    task_id="conditional_task",
    bash_command="echo 'No failures detected'",
    trigger_rule=TriggerRule.NONE_FAILED,
)
```

## Compensation Logic

### Cleanup Tasks

Always run cleanup regardless of success/failure.

```python
def cleanup_resources(**context):
    """Cleanup temporary files, connections, locks."""
    logger.info("Executing cleanup")

    # Release locks
    # Delete temporary files
    # Close connections
    # Update status tables

cleanup = PythonOperator(
    task_id="cleanup",
    python_callable=cleanup_resources,
    trigger_rule=TriggerRule.ALL_DONE,  # Always run
)

main_tasks >> cleanup
```

### Rollback Logic

Undo partial changes on failure.

```python
def rollback_changes(**context):
    """Rollback database changes on failure."""
    execution_date = context["execution_date"]

    logger.warning("Rolling back changes", execution_date=str(execution_date))

    # Delete partially loaded data
    # Restore backups
    # Reset state flags

rollback = PythonOperator(
    task_id="rollback",
    python_callable=rollback_changes,
    trigger_rule=TriggerRule.ONE_FAILED,  # Only on failure
)

[extract, transform, load] >> rollback
```

### Compensation Transactions

Execute compensating actions for failed operations.

```python
def compensate_failed_transfer(**context):
    """Compensate for failed data transfer."""
    logger.info("Executing compensation logic")

    # Reverse credited amounts
    # Send reversal notifications
    # Update audit logs

compensate = PythonOperator(
    task_id="compensate",
    python_callable=compensate_failed_transfer,
    trigger_rule=TriggerRule.ALL_FAILED,
)
```

## Error Logging

### Structured Logging with Context

Include full execution context in error logs.

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

def task_function(**context):
    # Add context
    logger.add_context(
        dag_id=context["dag"].dag_id,
        task_id=context["task"].task_id,
        execution_date=str(context["execution_date"]),
        run_id=context["run_id"],
        try_number=context["task_instance"].try_number
    )

    try:
        # Task logic
        logger.info("Task started")
        result = perform_operation()
        logger.info("Task completed", result=result)

    except Exception as e:
        logger.exception(
            "Task failed",
            error_type=type(e).__name__,
            error_message=str(e)
        )
        raise
```

### Error Context in Bash Tasks

Log context in bash commands.

```bash
bash_command="""
echo "============================================"
echo "Task: {{ task.task_id }}"
echo "DAG: {{ dag.dag_id }}"
echo "Execution Date: {{ ds }}"
echo "Run ID: {{ run_id }}"
echo "Try Number: {{ task_instance.try_number }}"
echo "Max Tries: {{ task_instance.max_tries }}"
echo "============================================"

# Your task logic here

if [ $? -ne 0 ]; then
    echo "ERROR: Task failed"
    echo "Error code: $?"
    exit 1
fi
"""
```

## Best Practices

### 1. Choose Appropriate Retry Strategy

- **External APIs**: Exponential backoff (reduces load)
- **Database operations**: Exponential backoff (connection recovery)
- **File operations**: Fixed backoff (filesystem issues)
- **Rate-limited APIs**: Linear backoff (predictable)

### 2. Set Reasonable Timeouts

- **Quick tasks** (< 1 min): 5 minute timeout
- **Medium tasks** (1-10 min): 30 minute timeout
- **Long tasks** (10-60 min): 2 hour timeout
- **Very long tasks** (> 1 hour): Consider breaking into smaller tasks

### 3. Use Trigger Rules Appropriately

- **Cleanup**: `ALL_DONE`
- **Partial results**: `ONE_SUCCESS`
- **Critical paths**: `ALL_SUCCESS` (default)
- **Error handling**: `ONE_FAILED`

### 4. Implement Idempotency

Make tasks safe to retry:

```python
def idempotent_task(**context):
    execution_date = context["execution_date"]

    # Check if already processed
    if is_already_processed(execution_date):
        logger.info("Already processed, skipping", execution_date=str(execution_date))
        return

    # Process data
    process_data(execution_date)

    # Mark as processed
    mark_as_processed(execution_date)
```

### 5. Log Comprehensively

Always log:
- Task start/end
- Retry attempts
- Error details with stack traces
- Execution context (dag_id, task_id, execution_date)
- Performance metrics (rows processed, duration)

### 6. Monitor and Alert

- **Email on failure**: Critical paths only
- **Email on retry**: Usually disable (too noisy)
- **SLA misses**: For time-sensitive pipelines
- **Callback functions**: Custom alerting logic

## Examples

### Example 1: Robust API Call

```python
from src.utils.retry_policies import create_retry_config
from src.utils.timeout_handler import create_timeout_config

retry_config = create_retry_config(
    max_retries=5,
    strategy="exponential",
    base_delay=60,
    max_delay=1800
)

timeout_config = create_timeout_config(timeout_seconds=600)

api_task = BashOperator(
    task_id="call_external_api",
    bash_command="curl -f https://api.example.com/data",
    **retry_config,
    **timeout_config,
)
```

### Example 2: Database Operation with Rollback

```python
def load_to_database(**context):
    logger.info("Starting database load")

    try:
        # Start transaction
        conn = get_connection()
        conn.begin()

        # Load data
        load_data(conn)

        # Commit
        conn.commit()
        logger.info("Database load committed")

    except Exception as e:
        # Rollback on error
        conn.rollback()
        logger.error("Database load failed, rolled back", error=str(e))
        raise

load_task = PythonOperator(
    task_id="load_database",
    python_callable=load_to_database,
    retries=2,
    retry_delay=timedelta(minutes=5),
)
```

### Example 3: Parallel Processing with Partial Failure Handling

```python
# Parallel extracts
extract_a = BashOperator(task_id="extract_a", ...)
extract_b = BashOperator(task_id="extract_b", ...)
extract_c = BashOperator(task_id="extract_c", ...)

# Merge whatever succeeded
merge = BashOperator(
    task_id="merge_results",
    bash_command="merge.sh",
    trigger_rule=TriggerRule.ONE_SUCCESS,  # Process partial results
)

# Cleanup always runs
cleanup = BashOperator(
    task_id="cleanup",
    bash_command="cleanup.sh",
    trigger_rule=TriggerRule.ALL_DONE,
)

[extract_a, extract_b, extract_c] >> merge >> cleanup
```

## Reference

### Utility Functions

```python
# Retry policies
from src.utils.retry_policies import (
    calculate_exponential_backoff,
    calculate_linear_backoff,
    calculate_fixed_backoff,
    create_retry_config,
    generate_retry_delays,
)

# Timeout handling
from src.utils.timeout_handler import (
    TimeoutChecker,
    TimeoutContext,
    create_timeout_config,
    is_timeout_exceeded,
    format_timeout_duration,
)

# Logging
from src.utils.logger import get_logger
```

### Example DAGs

- **Beginner**: `dags/examples/beginner/demo_scheduled_pipeline_v1.py`
- **Advanced**: `dags/examples/advanced/demo_failure_recovery_v1.py`

## Next Steps

- Review example DAGs in `dags/examples/`
- Implement retry and timeout in your DAGs
- Test failure scenarios
- Monitor retry patterns in production
- Tune backoff strategies based on metrics

For more information, see:
- [Airflow Documentation - Error Handling](https://airflow.apache.org/docs/apache-airflow/stable/concepts/tasks.html#error-handling)
- [Development Guide](./development.md)
- [Testing Guide](../TESTING.md)

---

# Spark Operators Guide

Complete guide to using custom Spark operators for multi-cluster job orchestration.

## Overview

The platform provides three custom Spark operators for submitting and monitoring Spark jobs across different cluster types:

- **SparkStandaloneOperator**: Submits jobs to Spark Standalone clusters
- **SparkYarnOperator**: Submits jobs to Hadoop YARN clusters
- **SparkKubernetesOperator**: Submits jobs to Kubernetes clusters

All operators share common functionality:
- Job submission and tracking
- Status monitoring
- Log retrieval
- Graceful cancellation
- Resource configuration

## Spark Standalone Operator

### Use Case

Best for local development, testing, and small-scale processing.

### Configuration

```python
from src.operators.spark.standalone_operator import SparkStandaloneOperator

spark_task = SparkStandaloneOperator(
    task_id='process_data',
    application='/opt/spark/apps/my_app.py',
    master='spark://spark-master:7077',
    name='MySparkJob',
    deploy_mode='client',  # or 'cluster'
    
    # Resource configuration
    driver_memory='1g',
    driver_cores='1',
    executor_memory='2g',
    executor_cores='2',
    num_executors='3',
    
    # Spark configuration
    conf={
        'spark.executor.memory': '2g',
        'spark.sql.shuffle.partitions': '10',
    },
    
    # Application arguments
    application_args=['--input', '/data/input', '--output', '/data/output'],
    
    # Airflow connection
    conn_id='spark_standalone',
    
    dag=dag,
)
```

### Parameters

- **application** (required): Path to Spark application (.py or .jar)
- **master** (required): Spark master URL (e.g., `spark://host:7077`)
- **deploy_mode**: `client` (default) or `cluster`
- **name**: Application name (visible in Spark UI)
- **conf**: Dict of Spark configuration properties
- **application_args**: List of arguments to pass to application
- **driver_memory**: Driver memory (e.g., '1g', '512m')
- **driver_cores**: Number of driver cores
- **executor_memory**: Executor memory
- **executor_cores**: Number of cores per executor
- **num_executors**: Number of executor instances
- **verbose**: Enable verbose spark-submit output
- **conn_id**: Airflow connection ID

### Example

```python
word_count = SparkStandaloneOperator(
    task_id='word_count',
    application='/opt/spark/apps/word_count.py',
    master='spark://spark-master:7077',
    name='WordCount',
    executor_memory='1g',
    executor_cores='1',
    num_executors='2',
    dag=dag,
)
```

## Spark YARN Operator

### Use Case

Best for large-scale production workloads in Hadoop ecosystems.

### Configuration

```python
from src.operators.spark.yarn_operator import SparkYarnOperator

yarn_task = SparkYarnOperator(
    task_id='process_large_dataset',
    application='/apps/sales_aggregation.py',
    queue='production',  # YARN queue name
    deploy_mode='cluster',  # Recommended for YARN
    
    # Resource configuration
    driver_memory='2g',
    driver_cores='2',
    executor_memory='4g',
    executor_cores='4',
    num_executors='10',
    
    # YARN-specific configuration
    conf={
        'spark.yarn.queue': 'production',
        'spark.yarn.maxAppAttempts': '3',
        'spark.dynamicAllocation.enabled': 'true',
        'spark.dynamicAllocation.minExecutors': '2',
        'spark.dynamicAllocation.maxExecutors': '20',
    },
    
    application_args=['--input', 'hdfs:///data/sales'],
    conn_id='spark_yarn',
    dag=dag,
)
```

### YARN-Specific Parameters

- **queue** (required): YARN queue name (default: 'default')
- **deploy_mode**: Use 'cluster' for production workloads

### Dynamic Resource Allocation

Enable dynamic allocation for variable workloads:

```python
conf={
    'spark.dynamicAllocation.enabled': 'true',
    'spark.dynamicAllocation.minExecutors': '2',
    'spark.dynamicAllocation.maxExecutors': '50',
    'spark.dynamicAllocation.initialExecutors': '5',
}
```

## Spark Kubernetes Operator

### Use Case

Best for cloud-native deployments and containerized workflows.

### Configuration

```python
from src.operators.spark.kubernetes_operator import SparkKubernetesOperator

k8s_task = SparkKubernetesOperator(
    task_id='process_on_k8s',
    application='/opt/spark/apps/my_app.py',
    namespace='spark-jobs',  # K8s namespace
    kubernetes_service_account='spark-sa',
    image='my-registry.io/spark:3.5.0-custom',
    
    # Resource requests and limits
    conf={
        'spark.kubernetes.driver.request.cores': '1',
        'spark.kubernetes.driver.limit.cores': '2',
        'spark.kubernetes.driver.request.memory': '2g',
        'spark.kubernetes.executor.request.cores': '2',
        'spark.kubernetes.executor.limit.cores': '4',
        'spark.kubernetes.executor.request.memory': '4g',
    },
    
    # Pod cleanup
    executor_pod_cleanup_policy='OnSuccess',  # or 'OnFailure', 'Never'
    
    application_args=['--mode', 'production'],
    conn_id='spark_k8s',
    dag=dag,
)
```

### Kubernetes-Specific Parameters

- **namespace** (required): Kubernetes namespace for Spark resources
- **kubernetes_service_account**: Service account for driver/executor pods
- **image**: Docker image for Spark containers
- **driver_pod_template**: Path to driver pod template YAML
- **executor_pod_template**: Path to executor pod template YAML
- **executor_pod_cleanup_policy**: 'OnSuccess', 'OnFailure', or 'Never'

### Pod Templates

Use pod templates for advanced configuration:

```python
k8s_task = SparkKubernetesOperator(
    task_id='custom_pods',
    application='/apps/my_app.py',
    namespace='spark-jobs',
    driver_pod_template='/config/driver-template.yaml',
    executor_pod_template='/config/executor-template.yaml',
    dag=dag,
)
```

## Common Patterns

### 1. Job Chaining

Run multiple Spark jobs in sequence:

```python
job1 = SparkStandaloneOperator(
    task_id='extract_data',
    application='/apps/extract.py',
    master='spark://master:7077',
    dag=dag,
)

job2 = SparkStandaloneOperator(
    task_id='transform_data',
    application='/apps/transform.py',
    master='spark://master:7077',
    dag=dag,
)

job1 >> job2
```

### 2. Parallel Processing

Run independent jobs in parallel:

```python
jobs = []
for region in ['us-east', 'us-west', 'eu']:
    job = SparkStandaloneOperator(
        task_id=f'process_{region}',
        application='/apps/process_region.py',
        application_args=['--region', region],
        master='spark://master:7077',
        dag=dag,
    )
    jobs.append(job)

start >> jobs >> aggregate
```

### 3. Multi-Cluster Deployment

Use different clusters for different workloads:

```python
# Development: Standalone
dev_job = SparkStandaloneOperator(
    task_id='dev_job',
    application='/apps/test.py',
    master='spark://dev-master:7077',
    dag=dag,
)

# Production: YARN
prod_job = SparkYarnOperator(
    task_id='prod_job',
    application='/apps/production.py',
    queue='production',
    deploy_mode='cluster',
    dag=dag,
)
```

### 4. Resource Tuning

Adjust resources based on data volume:

```python
# Small dataset
small_job = SparkStandaloneOperator(
    task_id='small_processing',
    application='/apps/process.py',
    executor_memory='1g',
    executor_cores='1',
    num_executors='2',
    dag=dag,
)

# Large dataset
large_job = SparkStandaloneOperator(
    task_id='large_processing',
    application='/apps/process.py',
    executor_memory='8g',
    executor_cores='4',
    num_executors='20',
    conf={'spark.sql.shuffle.partitions': '200'},
    dag=dag,
)
```

## Error Handling

### Retry Configuration

Combine with retry policies:

```python
from src.utils.retry_policies import create_retry_config

retry_config = create_retry_config(
    max_retries=2,
    strategy='exponential',
    base_delay=120,
)

spark_job = SparkStandaloneOperator(
    task_id='resilient_job',
    application='/apps/my_app.py',
    master='spark://master:7077',
    retries=retry_config['retries'],
    retry_delay=retry_config['retry_delay'],
    dag=dag,
)
```

### Timeout Management

Set execution timeout:

```python
from datetime import timedelta

spark_job = SparkStandaloneOperator(
    task_id='long_job',
    application='/apps/batch_process.py',
    master='spark://master:7077',
    execution_timeout=timedelta(hours=2),
    dag=dag,
)
```

### Failure Handling

Use trigger rules for compensation:

```python
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.python import PythonOperator

cleanup = PythonOperator(
    task_id='cleanup_on_failure',
    python_callable=cleanup_temp_data,
    trigger_rule=TriggerRule.ONE_FAILED,
    dag=dag,
)

spark_job >> cleanup
```

## Monitoring and Debugging

### XCom Integration

Access job IDs for monitoring:

```python
def check_job_status(**context):
    job_id = context['task_instance'].xcom_pull(
        task_ids='spark_job',
        key='spark_job_id'
    )
    print(f"Spark job ID: {job_id}")
```

### Log Retrieval

Logs are automatically captured and available in Airflow task logs.

### Spark UI

Access Spark UI for detailed monitoring:
- Standalone: http://spark-master:8080
- YARN: YARN Resource Manager UI
- Kubernetes: Use kubectl logs or K8s dashboard

## Performance Optimization

### Memory Management

```python
conf={
    # Driver memory
    'spark.driver.memory': '4g',
    'spark.driver.maxResultSize': '2g',
    
    # Executor memory
    'spark.executor.memory': '8g',
    'spark.executor.memoryOverhead': '1g',
    
    # Memory fractions
    'spark.memory.fraction': '0.8',
    'spark.memory.storageFraction': '0.3',
}
```

### Shuffle Optimization

```python
conf={
    # Shuffle partitions
    'spark.sql.shuffle.partitions': '200',  # Adjust based on data size
    
    # Shuffle behavior
    'spark.shuffle.compress': 'true',
    'spark.shuffle.spill.compress': 'true',
    
    # Shuffle service (YARN/K8s)
    'spark.shuffle.service.enabled': 'true',
}
```

### Parallelism

```python
conf={
    # Default parallelism
    'spark.default.parallelism': '100',
    
    # SQL partitions
    'spark.sql.shuffle.partitions': '100',
    
    # Task execution
    'spark.task.cpus': '1',
    'spark.executor.cores': '4',
}
```

## Security

### Kerberos (YARN)

```python
conf={
    'spark.yarn.keytab': '/path/to/keytab',
    'spark.yarn.principal': 'spark@REALM',
}
```

### Kubernetes RBAC

```python
k8s_task = SparkKubernetesOperator(
    task_id='secure_job',
    kubernetes_service_account='spark-privileged',
    conf={
        'spark.kubernetes.authenticate.driver.serviceAccountName': 'spark-privileged',
    },
    dag=dag,
)
```

## Best Practices

1. **Use appropriate cluster type**:
   - Development: Standalone
   - Production (on-premise): YARN
   - Production (cloud): Kubernetes

2. **Set resource limits**:
   - Prevent resource starvation
   - Use dynamic allocation for variable workloads

3. **Enable monitoring**:
   - Spark UI for job details
   - Airflow logs for orchestration
   - Metrics collection for performance

4. **Implement retry logic**:
   - Use exponential backoff
   - Set reasonable max retries (2-3)

5. **Configure timeouts**:
   - Prevent hung jobs
   - Set based on expected runtime + buffer

6. **Test locally first**:
   - Use Standalone cluster for development
   - Validate on larger clusters for production

7. **Version control Spark apps**:
   - Treat Spark applications as code
   - Use Git for version management

## Example DAGs

- **Intermediate**: `dags/examples/intermediate/demo_spark_standalone_v1.py`
- **Advanced**: `dags/examples/advanced/demo_spark_multi_cluster_v1.py`

## Troubleshooting

### Job submission fails

**Check**:
- Spark cluster is running
- Airflow connection configured correctly
- Network connectivity from Airflow to cluster
- Application path is accessible

### Jobs hang indefinitely

**Solutions**:
- Set execution_timeout
- Check Spark UI for blocked stages
- Verify resource availability
- Check for data skew

### Out of memory errors

**Solutions**:
- Increase executor memory
- Adjust memory fractions
- Repartition data
- Enable dynamic allocation

### Slow performance

**Solutions**:
- Optimize shuffle partitions
- Check data locality
- Enable compression
- Review execution plan in Spark UI

---

## Multi-Channel Notification Operators

The platform provides custom operators for sending notifications via email, Microsoft Teams, and Telegram with support for template rendering, retry logic, and error handling.

### Email Notifications

Send email notifications via SMTP with HTML/plain text support.

**Operator**: `EmailNotificationOperator`

**Basic Usage**:

```python
from src.operators.notifications.email_operator import EmailNotificationOperator

send_email = EmailNotificationOperator(
    task_id="send_success_email",
    to="admin@example.com",
    subject="Pipeline {{ dag.dag_id }} completed",
    message_template="""
    Pipeline execution completed successfully!

    DAG: {{ dag.dag_id }}
    Date: {{ ds }}
    Run ID: {{ run_id }}
    """,
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_user="{{ var.value.smtp_user }}",
    smtp_password="{{ var.value.smtp_password }}",
)
```

**Parameters**:

- `to` (str | list): Recipient email address(es)
- `subject` (str): Email subject (supports Jinja2 templates)
- `message_template` (str): Email body (supports Jinja2 templates)
- `from_email` (str, optional): Sender email address
- `cc` (str | list, optional): CC recipients
- `bcc` (str | list, optional): BCC recipients
- `html` (bool): Send as HTML email (default: False)
- `smtp_host` (str): SMTP server hostname
- `smtp_port` (int): SMTP port (default: 587 for TLS)
- `smtp_user` (str, optional): SMTP authentication username
- `smtp_password` (str, optional): SMTP authentication password
- `use_ssl` (bool): Use SSL instead of TLS for port 465 (default: False)

**HTML Email Example**:

```python
send_html_email = EmailNotificationOperator(
    task_id="send_html_report",
    to=["team@example.com", "manager@example.com"],
    subject="Daily Report - {{ ds }}",
    message_template="""
    <html>
    <body>
        <h1>Daily Pipeline Report</h1>
        <p><strong>DAG:</strong> {{ dag.dag_id }}</p>
        <p><strong>Date:</strong> {{ ds }}</p>
        <p><strong>Status:</strong> <span style="color: green;">SUCCESS</span></p>
    </body>
    </html>
    """,
    html=True,
    smtp_host="smtp.gmail.com",
    smtp_port=587,
)
```

**Email Validation**:
- All email addresses are validated for correct format
- Invalid emails will raise `ValueError` during DAG parsing

### Microsoft Teams Notifications

Send rich message cards to Microsoft Teams channels via incoming webhooks.

**Operator**: `TeamsNotificationOperator`

**Basic Usage**:

```python
from src.operators.notifications.teams_operator import TeamsNotificationOperator

send_teams = TeamsNotificationOperator(
    task_id="send_teams_notification",
    webhook_url="{{ var.value.teams_webhook_url }}",
    message_template="Pipeline {{ dag.dag_id }} completed successfully!",
    title="✅ Pipeline Success",
    theme_color="00FF00",  # Green
)
```

**Parameters**:

- `webhook_url` (str): Teams incoming webhook URL (must start with https://)
- `message_template` (str): Message text (supports Jinja2 templates and Markdown)
- `title` (str, optional): Message card title (default: "Airflow Notification")
- `theme_color` (str, optional): Hex color code without # (default: "0078D4")
- `facts` (list, optional): List of key-value pairs for facts section
- `actions` (list, optional): List of action buttons with URIs
- `timeout` (int): Request timeout in seconds (default: 30)

**Advanced Example with Facts and Actions**:

```python
send_teams_detailed = TeamsNotificationOperator(
    task_id="send_teams_detailed",
    webhook_url="{{ var.value.teams_webhook_url }}",
    message_template="""
    Pipeline execution completed successfully.

    **Summary:**
    - All quality checks passed
    - 10,000 records processed
    - Duration: 5 minutes
    """,
    title="📊 {{ dag.dag_id }} - Success",
    theme_color="00FF00",
    facts=[
        {"name": "DAG ID", "value": "{{ dag.dag_id }}"},
        {"name": "Execution Date", "value": "{{ ds }}"},
        {"name": "Duration", "value": "{{ (task_instance.end_date - task_instance.start_date).total_seconds() if task_instance.end_date else 'N/A' }}s"},
        {"name": "State", "value": "{{ task_instance.state|upper }}"},
    ],
    actions=[
        {
            "@type": "OpenUri",
            "name": "View in Airflow",
            "targets": [{"os": "default", "uri": "http://localhost:8080/dags/{{ dag.dag_id }}"}]
        }
    ],
)
```

**Theme Colors**:
- Success: `00FF00` (Green)
- Warning: `FFA500` (Orange)
- Error: `FF0000` (Red)
- Info: `0078D4` (Microsoft Blue)

### Telegram Notifications

Send notifications via Telegram Bot API with Markdown/HTML formatting support.

**Operator**: `TelegramNotificationOperator`

**Basic Usage**:

```python
from src.operators.notifications.telegram_operator import TelegramNotificationOperator

send_telegram = TelegramNotificationOperator(
    task_id="send_telegram_notification",
    bot_token="{{ var.value.telegram_bot_token }}",
    chat_id="{{ var.value.telegram_chat_id }}",
    message_template="Pipeline *{{ dag.dag_id }}* completed!",
    parse_mode="Markdown",
)
```

**Parameters**:

- `bot_token` (str): Telegram Bot API token (format: "123456:ABC-DEF...")
- `chat_id` (str): Telegram chat ID (user ID or group chat ID with -)
- `message_template` (str): Message text (supports Jinja2 templates)
- `parse_mode` (str, optional): "Markdown", "HTML", or None
- `disable_notification` (bool): Send silently without sound (default: False)
- `disable_web_page_preview` (bool): Disable link previews (default: False)
- `timeout` (int): Request timeout in seconds (default: 30)

**Markdown Formatting Example**:

```python
send_telegram_markdown = TelegramNotificationOperator(
    task_id="send_telegram_markdown",
    bot_token="{{ var.value.telegram_bot_token }}",
    chat_id="{{ var.value.telegram_chat_id }}",
    message_template="""
*Pipeline Success* ✅

*DAG:* `{{ dag.dag_id }}`
*Date:* {{ ds }}
*Run ID:* `{{ run_id }}`

_All tasks completed successfully!_
    """,
    parse_mode="Markdown",
)
```

**HTML Formatting Example**:

```python
send_telegram_html = TelegramNotificationOperator(
    task_id="send_telegram_html",
    bot_token="{{ var.value.telegram_bot_token }}",
    chat_id="{{ var.value.telegram_chat_id }}",
    message_template="""
<b>Pipeline Failure</b> ❌

<b>DAG:</b> <code>{{ dag.dag_id }}</code>
<b>Task:</b> <code>{{ task.task_id }}</code>
<b>Error:</b> <i>{{ exception if exception is defined else 'Unknown error' }}</i>

<a href="http://localhost:8080/dags/{{ dag.dag_id }}">View in Airflow</a>
    """,
    parse_mode="HTML",
)
```

**Silent Notification** (for non-critical alerts):

```python
send_telegram_silent = TelegramNotificationOperator(
    task_id="send_telegram_silent",
    bot_token="{{ var.value.telegram_bot_token }}",
    chat_id="{{ var.value.telegram_chat_id }}",
    message_template="Background job completed.",
    disable_notification=True,  # No sound
)
```

### Notification Templates

Use pre-defined templates for common scenarios.

**Available Templates**:

```python
from src.utils.notification_templates import get_template, NOTIFICATION_TEMPLATES

# Success templates
success_simple = get_template("success", "simple")
success_detailed = get_template("success", "detailed")

# Failure templates
failure_simple = get_template("failure", "simple")
failure_detailed = get_template("failure", "detailed")

# Data quality templates
data_quality_warning = get_template("data_quality", "warning")
data_quality_critical = get_template("data_quality", "critical")

# Spark job templates
spark_success = get_template("spark", "success")
spark_failure = get_template("spark", "failure")
```

**Using Templates in Operators**:

```python
send_success_email = EmailNotificationOperator(
    task_id="send_success_email",
    to="admin@example.com",
    subject="Pipeline Success - {{ dag.dag_id }}",
    message_template=get_template("success", "detailed"),
    smtp_host="smtp.gmail.com",
    smtp_port=587,
)
```

### Common Patterns

#### Success Notification

```python
# Send notification on successful DAG run
send_success_notification = EmailNotificationOperator(
    task_id="send_success_notification",
    to="team@example.com",
    subject="✅ {{ dag.dag_id }} - Success",
    message_template=get_template("success", "detailed"),
    trigger_rule="all_success",  # Only run if all upstream tasks succeed
)

# Place at end of DAG
all_tasks >> send_success_notification
```

#### Failure Notification

```python
# Send notification on any task failure
send_failure_notification = TeamsNotificationOperator(
    task_id="send_failure_notification",
    webhook_url="{{ var.value.teams_webhook_url }}",
    message_template=get_template("failure", "detailed"),
    title="❌ {{ dag.dag_id }} - Failed",
    theme_color="FF0000",  # Red
    trigger_rule="one_failed",  # Run if any upstream task fails
)

# Add as final task with trigger_rule
all_tasks >> send_failure_notification
```

#### Multi-Channel Notifications

```python
# Send to all channels in parallel
from airflow.operators.python import BranchPythonOperator

send_email = EmailNotificationOperator(...)
send_teams = TeamsNotificationOperator(...)
send_telegram = TelegramNotificationOperator(...)

# All notifications run in parallel after task completes
task >> [send_email, send_teams, send_telegram]
```

#### Conditional Notifications

```python
# Only send if threshold exceeded
def check_threshold(**context):
    ti = context['task_instance']
    count = ti.xcom_pull(task_ids='count_records')
    if count > 1000:
        return 'send_notification'
    else:
        return 'skip_notification'

check = BranchPythonOperator(
    task_id='check_threshold',
    python_callable=check_threshold,
)

send_notification = TelegramNotificationOperator(
    task_id='send_notification',
    bot_token="{{ var.value.telegram_bot_token }}",
    chat_id="{{ var.value.telegram_chat_id }}",
    message_template="High record count detected: {{ ti.xcom_pull('count_records') }}",
)

count_records >> check >> send_notification
```

### Configuration

Store sensitive credentials in Airflow Variables:

**Via Airflow UI**:
Admin → Variables → Add

**Via CLI**:

```bash
# Email
airflow variables set smtp_host "smtp.gmail.com"
airflow variables set smtp_user "notifications@company.com"
airflow variables set smtp_password "app-specific-password"

# Teams
airflow variables set teams_webhook_url "https://outlook.office.com/webhook/abc123..."

# Telegram
airflow variables set telegram_bot_token "123456:ABC-DEF..."
airflow variables set telegram_chat_id "-1001234567890"
```

### Error Handling

All notification operators include:
- **Automatic retries** with configurable delays
- **Timeout enforcement** to prevent hanging
- **Structured error logging** with full context
- **Graceful degradation** (logs errors without failing DAG)

**Retry Configuration**:

```python
send_email = EmailNotificationOperator(
    task_id="send_email",
    to="admin@example.com",
    subject="Test",
    message_template="Test message",
    retries=3,
    retry_delay=timedelta(minutes=2),
    retry_exponential_backoff=True,  # 2min → 4min → 8min
)
```

### Best Practices

1. **Use Airflow Variables for credentials** (never hardcode)
2. **Set appropriate trigger rules** (`all_success`, `one_failed`, `all_done`)
3. **Keep messages concise** (especially for Telegram - 4096 char limit)
4. **Use templates** for consistent messaging
5. **Test notifications** with dummy values first
6. **Add retries** for transient network errors
7. **Set timeouts** to prevent hanging tasks
8. **Include context** in messages (DAG ID, date, run ID)
9. **Use appropriate severity colors** (green for success, red for failure)
10. **Monitor notification delivery** in task logs

### Troubleshooting

**Email not sending**:
- Check SMTP credentials and host
- Verify port (587 for TLS, 465 for SSL)
- Check firewall/network rules
- Enable "less secure apps" for Gmail (or use app password)
- Review task logs for specific errors

**Teams notification fails**:
- Verify webhook URL is correct
- Check webhook has not been deleted in Teams
- Ensure message card JSON is valid
- Review HTTP response code in logs

**Telegram notification fails**:
- Verify bot token format (contains colon)
- Check chat ID is correct
- Ensure bot has been added to group (for group chats)
- Check message length < 4096 characters
- Review Telegram API error codes in logs

**Template rendering errors**:
- Check Jinja2 syntax (proper `{{ }}` usage)
- Verify context variables exist
- Test templates with simple values first
- Review template error messages in logs

## Additional Resources

- [Apache Spark Documentation](https://spark.apache.org/docs/latest/)
- [Spark Configuration Reference](https://spark.apache.org/docs/latest/configuration.html)
- [Spark on Kubernetes Guide](https://spark.apache.org/docs/latest/running-on-kubernetes.html)
- [Microsoft Teams Webhooks](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Development Guide](./development.md)
- [Docker Spark Setup](../docker/spark/README.md)
- [Example DAG: Notification Basics](../dags/examples/beginner/demo_notification_basics_v1.py)
