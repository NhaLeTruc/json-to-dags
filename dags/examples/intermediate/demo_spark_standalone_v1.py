"""
Demo DAG: Spark Standalone Cluster Integration

Demonstrates submitting Spark jobs to a Standalone cluster using custom operator.
This intermediate example shows how to:
- Configure Spark Standalone operator
- Submit PySpark applications
- Monitor job execution
- Handle job completion and failures

Prerequisites:
- Spark Standalone cluster running (see docker/spark/README.md)
- Airflow connection 'spark_standalone' configured
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.empty import EmptyOperator

from src.operators.spark.standalone_operator import SparkStandaloneOperator
from src.utils.retry_policies import create_retry_config
from src.utils.timeout_handler import create_timeout_config

# DAG default arguments
retry_config = create_retry_config(max_retries=2, strategy="exponential", base_delay=60)
timeout_config = create_timeout_config(timeout_seconds=600)  # 10 minutes

default_args = {
    "owner": "data_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    **retry_config,
    **timeout_config,
}

# Create DAG
dag = DAG(
    dag_id="demo_spark_standalone_v1",
    default_args=default_args,
    description="Demonstrates Spark Standalone job submission and monitoring",
    schedule=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["demo", "intermediate", "spark", "standalone"],
)

# Start placeholder
start = EmptyOperator(task_id="start", dag=dag)

# Spark job 1: Word Count (simple example)
word_count_job = SparkStandaloneOperator(
    task_id="spark_word_count",
    application="/opt/spark/apps/word_count.py",
    master="spark://spark-master:7077",
    name="WordCount_Demo",
    deploy_mode="client",
    conf={
        "spark.dynamicAllocation.enabled": "false",
    },
    application_args=[],  # Will use default sample data
    executor_memory="1g",
    executor_cores="1",
    num_executors="2",
    verbose=True,
    conn_id="spark_standalone",
    dag=dag,
)

# Spark job 2: Sales Aggregation (realistic example)
# Note: This requires warehouse database to be accessible from Spark
# DESIGN-002: In production, use Airflow connections instead of hardcoded JDBC URLs:
#   from airflow.hooks.base import BaseHook
#   conn = BaseHook.get_connection("warehouse")
#   jdbc_url = f"jdbc:postgresql://{conn.host}:{conn.port}/{conn.schema}"
sales_aggregation_job = SparkStandaloneOperator(
    task_id="spark_sales_aggregation",
    application="/opt/spark/apps/sales_aggregation.py",
    master="spark://spark-master:7077",
    name="SalesAggregation_Demo",
    deploy_mode="client",
    conf={
        "spark.sql.shuffle.partitions": "10",
        "spark.dynamicAllocation.enabled": "false",
    },
    application_args=[
        "jdbc:postgresql://airflow-warehouse:5432/warehouse",  # Demo only; use Airflow connection in production
        "/opt/spark/data/sales_output",
    ],
    executor_memory="2g",
    executor_cores="2",
    num_executors="2",
    verbose=True,
    conn_id="spark_standalone",
    dag=dag,
)

# Completion placeholder
complete = EmptyOperator(task_id="complete", dag=dag)

# Define task dependencies
# Run word count first (simpler), then sales aggregation
start >> word_count_job >> sales_aggregation_job >> complete
