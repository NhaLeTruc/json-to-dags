"""
Demo DAG: Multi-Cluster Spark Job Orchestration

Demonstrates submitting Spark jobs to different cluster types:
- Standalone cluster
- YARN cluster
- Kubernetes cluster

This advanced example shows how to:
- Use all three Spark operator types
- Configure cluster-specific parameters
- Handle different deployment modes
- Run parallel jobs across clusters

Prerequisites:
- At least one cluster type available (Standalone recommended for demo)
- Appropriate Airflow connections configured
- Network connectivity to clusters

Note: This DAG is designed to showcase all operators. In production, you would
typically use one cluster type based on your infrastructure.
"""

import logging
from datetime import datetime

from airflow import DAG

logger = logging.getLogger(__name__)
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

from src.operators.spark.kubernetes_operator import SparkKubernetesOperator
from src.operators.spark.standalone_operator import SparkStandaloneOperator
from src.operators.spark.yarn_operator import SparkYarnOperator
from src.utils.retry_policies import create_retry_config

# DAG default arguments
retry_config = create_retry_config(max_retries=2, strategy="exponential")

default_args = {
    "owner": "data_engineering_team",
    "depends_on_past": False,
    "email_on_failure": False,
    **retry_config,
}

# Create DAG
dag = DAG(
    dag_id="demo_spark_multi_cluster_v1",
    default_args=default_args,
    description="Advanced multi-cluster Spark orchestration across Standalone, YARN, and Kubernetes",
    schedule=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["demo", "advanced", "spark", "multi-cluster", "parallel"],
)

# Start
start = EmptyOperator(task_id="start", dag=dag)


# Cluster availability check (mock - in production, use sensors)
def check_cluster_availability(**context):
    """Check which clusters are available."""
    # In production, implement actual cluster health checks
    available_clusters = {
        "standalone": True,  # Usually available in demo environment
        "yarn": False,  # Requires YARN cluster
        "kubernetes": False,  # Requires K8s cluster
    }

    # Push to XCom for conditional execution
    context["task_instance"].xcom_push(key="available_clusters", value=available_clusters)


check_clusters = PythonOperator(
    task_id="check_cluster_availability",
    python_callable=check_cluster_availability,
    dag=dag,
)

# ==============================================================================
# Spark Standalone Jobs
# ==============================================================================

# INEFF-005 fix: Use explicit parameters instead of duplicating in conf dict
standalone_word_count = SparkStandaloneOperator(
    task_id="standalone_word_count",
    application="/opt/spark/apps/word_count.py",
    master="spark://spark-master:7077",
    name="Standalone_WordCount",
    deploy_mode="client",
    conf={},  # Use explicit parameters below instead
    executor_memory="1g",
    executor_cores="1",
    num_executors="2",
    conn_id="spark_standalone",
    dag=dag,
)

# DESIGN-002: In production, use Airflow connections instead of hardcoded JDBC URLs
standalone_sales_agg = SparkStandaloneOperator(
    task_id="standalone_sales_aggregation",
    application="/opt/spark/apps/sales_aggregation.py",
    master="spark://spark-master:7077",
    name="Standalone_SalesAgg",
    deploy_mode="client",
    conf={
        "spark.sql.shuffle.partitions": "10",
    },
    application_args=[
        "jdbc:postgresql://airflow-warehouse:5432/warehouse",  # Demo only; use Airflow connection in production
        "/opt/spark/data/standalone_sales",
    ],
    executor_memory="2g",
    executor_cores="2",
    num_executors="2",
    conn_id="spark_standalone",
    dag=dag,
)

# ==============================================================================
# YARN Jobs (demonstration - requires YARN cluster)
# ==============================================================================

yarn_word_count = SparkYarnOperator(
    task_id="yarn_word_count",
    application="/opt/spark/apps/word_count.py",
    queue="default",
    name="YARN_WordCount",
    deploy_mode="cluster",  # YARN typically uses cluster mode
    conf={
        "spark.executor.memory": "2g",
        "spark.executor.cores": "2",
        "spark.yarn.maxAppAttempts": "3",
    },
    executor_memory="2g",
    executor_cores="2",
    num_executors="3",
    conn_id="spark_yarn",  # Requires YARN connection
    dag=dag,
)

yarn_sales_agg = SparkYarnOperator(
    task_id="yarn_sales_aggregation",
    application="/opt/spark/apps/sales_aggregation.py",
    queue="production",  # Use production queue
    name="YARN_SalesAgg",
    deploy_mode="cluster",
    conf={
        "spark.executor.memory": "4g",
        "spark.dynamicAllocation.enabled": "true",
        "spark.dynamicAllocation.minExecutors": "2",
        "spark.dynamicAllocation.maxExecutors": "10",
    },
    application_args=[
        "jdbc:postgresql://warehouse-host:5432/warehouse",
        "/data/yarn_sales",
    ],
    executor_memory="4g",
    executor_cores="4",
    conn_id="spark_yarn",
    dag=dag,
)

# ==============================================================================
# Kubernetes Jobs (demonstration - requires K8s cluster)
# ==============================================================================

k8s_word_count = SparkKubernetesOperator(
    task_id="k8s_word_count",
    application="/opt/spark/apps/word_count.py",
    namespace="spark-jobs",
    name="k8s-wordcount",
    kubernetes_service_account="spark-sa",
    image="apache/spark:3.5.0-python3",
    conf={
        "spark.kubernetes.driver.request.cores": "1",
        "spark.kubernetes.driver.limit.cores": "1",
        "spark.kubernetes.executor.request.cores": "1",
        "spark.kubernetes.executor.limit.cores": "2",
    },
    driver_memory="1g",
    executor_memory="2g",
    num_executors="2",
    executor_pod_cleanup_policy="OnSuccess",
    conn_id="spark_k8s",  # Requires K8s connection
    dag=dag,
)

k8s_sales_agg = SparkKubernetesOperator(
    task_id="k8s_sales_aggregation",
    application="/opt/spark/apps/sales_aggregation.py",
    namespace="spark-jobs",
    name="k8s-sales-agg",
    kubernetes_service_account="spark-sa",
    image="apache/spark:3.5.0-python3",
    conf={
        "spark.kubernetes.driver.request.cores": "2",
        "spark.kubernetes.executor.request.cores": "2",
        "spark.kubernetes.executor.request.memory": "4g",
    },
    application_args=[
        "jdbc:postgresql://warehouse-host:5432/warehouse",
        "/data/k8s_sales",
    ],
    driver_memory="2g",
    executor_memory="4g",
    num_executors="3",
    executor_pod_cleanup_policy="OnSuccess",
    conn_id="spark_k8s",
    dag=dag,
)

# ==============================================================================
# Aggregation and Completion
# ==============================================================================


def aggregate_results(**context):
    """Aggregate results from all completed Spark jobs."""
    ti = context["task_instance"]

    # Collect job IDs from XCom
    results = {
        "standalone_wc": ti.xcom_pull(task_ids="standalone_word_count", key="spark_job_id"),
        "standalone_sales": ti.xcom_pull(
            task_ids="standalone_sales_aggregation", key="spark_job_id"
        ),
        # YARN and K8s jobs would also be collected if they ran
    }

    # INEFF-003 fix: Log aggregated results instead of doing nothing
    completed_jobs = {name: job_id for name, job_id in results.items() if job_id}
    logger.info(f"Aggregated {len(completed_jobs)} completed Spark jobs: {list(completed_jobs.keys())}")


aggregate = PythonOperator(
    task_id="aggregate_results",
    python_callable=aggregate_results,
    dag=dag,
)

complete = EmptyOperator(task_id="complete", dag=dag)

# ==============================================================================
# Task Dependencies
# ==============================================================================

# Check clusters first
start >> check_clusters

# Standalone cluster (parallel execution)
check_clusters >> [standalone_word_count, standalone_sales_agg]

# YARN cluster (parallel execution)
# Note: These will fail if YARN is not configured - that's expected in demo
check_clusters >> [yarn_word_count, yarn_sales_agg]

# Kubernetes cluster (parallel execution)
# Note: These will fail if K8s is not configured - that's expected in demo
check_clusters >> [k8s_word_count, k8s_sales_agg]

# Aggregate all results
(
    [
        standalone_word_count,
        standalone_sales_agg,
        yarn_word_count,
        yarn_sales_agg,
        k8s_word_count,
        k8s_sales_agg,
    ]
    >> aggregate
    >> complete
)

# ==============================================================================
# Documentation Notes
# ==============================================================================

"""
Cluster-Specific Configuration:

STANDALONE:
- Best for: Local development, testing, small-scale processing
- Pros: Easy setup, full control, works in Docker
- Cons: Limited scalability, manual cluster management

YARN:
- Best for: Large-scale production workloads, Hadoop ecosystem
- Pros: Resource sharing, mature ecosystem, dynamic allocation
- Cons: Complex setup, Hadoop dependency

KUBERNETES:
- Best for: Cloud-native deployments, containerized workflows
- Pros: Modern orchestration, auto-scaling, cloud integration
- Cons: Requires K8s expertise, more complex networking

This DAG demonstrates all three. In practice, choose based on your infrastructure:
- Development: Standalone
- On-premise big data: YARN
- Cloud/modern stack: Kubernetes
"""
