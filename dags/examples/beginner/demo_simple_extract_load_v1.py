"""
Simple Extract-Load DAG - Beginner Example

PATTERN: Basic ETL - Extract data from source and load to warehouse staging table

LEARNING OBJECTIVES:
1. Understand basic DAG structure and configuration
2. Learn PostgresOperator for database operations
3. Practice simple extract-load pattern with truncate-and-load for idempotency
4. Use Airflow templating with execution_date

USE CASE:
Extract customer dimension data from source warehouse and load to staging table
for downstream processing. This is a full refresh pattern - truncate before load
to ensure idempotency.

KEY AIRFLOW FEATURES:
- Basic DAG definition with default_args
- PostgresOperator for SQL execution
- Task dependencies with >>
- Jinja templating with {{ ds }}
- Airflow connections for database access
"""

from datetime import timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta

def days_ago(n):
    return datetime.now() - timedelta(days=n)

# Default arguments applied to all tasks
default_args = {
    "owner": "airflow_demo",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    dag_id="demo_simple_extract_load_v1",
    default_args=default_args,
    description="Simple extract-load pattern with truncate-and-load for idempotency",
    schedule="@daily",
    start_date=days_ago(1),
    catchup=False,
    tags=["beginner", "extract-load", "postgres", "idempotent"],
    doc_md=__doc__,
)

# Task 1: Truncate staging table for idempotent full refresh
# Creates staging table if it doesn't exist first
truncate_staging = PostgresOperator(
    task_id="truncate_staging_table",
    postgres_conn_id="warehouse",
    sql="""
    -- Create staging table if it doesn't exist
    CREATE TABLE IF NOT EXISTS staging.dim_customer_staging (
        customer_id INTEGER NOT NULL,
        customer_key VARCHAR(50) NOT NULL,
        customer_name VARCHAR(255) NOT NULL,
        email VARCHAR(255),
        country VARCHAR(100),
        segment VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    TRUNCATE TABLE staging.dim_customer_staging;
    """,
    dag=dag,
)

# Task 2: Extract and load customer data from source to staging
extract_load_customers = PostgresOperator(
    task_id="extract_load_customers",
    postgres_conn_id="warehouse",
    sql="""
    INSERT INTO staging.dim_customer_staging (
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        created_at,
        updated_at
    )
    SELECT
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        created_at,
        updated_at
    FROM warehouse.dim_customer
    WHERE updated_at <= '{{ ds }}'::date + INTERVAL '1 day';
    """,
    dag=dag,
)

# Task 3: Log extraction statistics
log_extraction_stats = PostgresOperator(
    task_id="log_extraction_stats",
    postgres_conn_id="warehouse",
    sql="""
    -- Log extraction stats to etl_metadata.load_log (created by migration 002)
    INSERT INTO etl_metadata.load_log (
        pipeline_name,
        table_name,
        execution_date,
        load_type,
        records_extracted,
        records_loaded,
        records_rejected,
        start_time,
        status
    )
    SELECT
        'demo_simple_extract_load_v1',
        'staging.dim_customer_staging',
        '{{ ts }}'::timestamp,
        'full',
        COUNT(*)::integer,
        COUNT(*)::integer,
        0,
        CURRENT_TIMESTAMP,
        'success'
    FROM staging.dim_customer_staging;
    """,
    dag=dag,
)

# Define task dependencies
# Pattern: Truncate → Extract/Load → Log Stats
truncate_staging >> extract_load_customers >> log_extraction_stats

"""
PATTERN EXPLANATION:

1. TRUNCATE-AND-LOAD PATTERN:
   - Truncate staging table first to ensure clean slate
   - Load all data from source (full refresh)
   - Idempotent: Running multiple times with same execution_date produces same result

2. WHY THIS PATTERN:
   - Simple and reliable for full dimension refreshes
   - Easy to understand and debug
   - No need to track deletes or updates
   - Staging table size manageable for daily full loads

3. WHEN TO USE:
   - Small to medium dimension tables (< 10M rows)
   - Daily full refreshes acceptable
   - Downstream processing can handle full table scans
   - Don't need incremental loading complexity

4. WHEN NOT TO USE:
   - Large tables where full refresh is expensive
   - Need real-time or streaming updates
   - Source system doesn't support full extracts
   - Historical tracking required (use SCD Type 2 instead)

5. IDEMPOTENCY:
   - Execution_date = 2025-01-15 always loads data <= 2025-01-15
   - Truncate ensures no duplicates from previous runs
   - Rerunning produces identical results

6. NEXT STEPS:
   - Learn incremental loading (demo_incremental_load_v1)
   - Add data quality checks (demo_data_quality_basics_v1)
   - Add notifications on failure (demo_notification_basics_v1)
   - Add retry logic and timeouts (demo_scheduled_pipeline_v1)
"""
