"""
Incremental Load DAG - Intermediate Example

PATTERN: Incremental ETL with watermark tracking for efficient data loading

LEARNING OBJECTIVES:
1. Understand incremental vs full load patterns
2. Learn watermark (checkpoint) tracking for resumable loads
3. Practice idempotent incremental loading
4. Use XCom to pass watermarks between tasks
5. Handle initial load vs incremental load logic

USE CASE:
Load only new or changed sales transactions from source system using
last_modified_date watermark. This pattern is essential for large fact
tables where full refreshes would be prohibitively expensive.

KEY AIRFLOW FEATURES:
- PythonOperator for watermark management
- XCom for passing values between tasks
- Jinja2 templating with variables
- BranchPythonOperator for conditional logic (initial vs incremental)
- PostgresOperator with dynamic SQL

EFFICIENCY:
- Only processes new/changed records since last run
- Reduces compute time from hours to minutes
- Enables real-time or near-real-time data pipelines
- Scalable to billions of records
"""

from datetime import timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

def days_ago(n):
    return datetime.now() - timedelta(days=n)

from src.hooks.warehouse_hook import WarehouseHook
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default arguments
default_args = {
    "owner": "etl_team",
    "depends_on_past": False,  # Disabled for demo
    "wait_for_downstream": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# DAG definition
dag = DAG(
    dag_id="demo_incremental_load_v1",
    default_args=default_args,
    description="Incremental load pattern with watermark tracking",
    schedule="@hourly",  # Run every hour for near-real-time
    start_date=days_ago(7),
    catchup=True,  # Backfill from start_date
    max_active_runs=1,  # Prevent overlapping runs
    tags=["intermediate", "incremental", "watermark", "idempotent", "fact-table"],
    doc_md=__doc__,
)


# Task 1: Get last watermark (high water mark) from metadata table
def get_last_watermark(**context):
    """
    Retrieve the last successful watermark from metadata table.

    Returns the max last_modified_date from previous successful run,
    or None for initial load.
    """
    hook = WarehouseHook(postgres_conn_id="warehouse")

    query = """
    SELECT MAX(watermark_value) AS last_watermark
    FROM etl_metadata.incremental_watermarks
    WHERE pipeline_name = 'demo_incremental_load_v1'
      AND table_name = 'warehouse.fact_sales'
      AND status = 'success';
    """

    result = hook.get_first(query)
    last_watermark = result[0] if result and result[0] else None

    logger.info(
        "Retrieved last watermark",
        pipeline="demo_incremental_load_v1",
        last_watermark=str(last_watermark) if last_watermark else "None (initial load)",
    )

    # Push to XCom for downstream tasks
    context["task_instance"].xcom_push(
        key="last_watermark", value=str(last_watermark) if last_watermark else None
    )

    return last_watermark


get_watermark = PythonOperator(
    task_id="get_last_watermark",
    python_callable=get_last_watermark,
    dag=dag,
)


# Task 2: Load incremental sales data
load_incremental_sales = PostgresOperator(
    task_id="load_incremental_sales",
    postgres_conn_id="warehouse",
    sql="""
    -- Insert new or modified sales transactions
    -- Maps source.sales_transactions to warehouse.fact_sales
    INSERT INTO warehouse.fact_sales (
        transaction_id,
        customer_id,
        product_id,
        sale_date_id,
        quantity,
        unit_price,
        discount,
        total_amount
    )
    SELECT
        'TXN-' || s.sales_id::text AS transaction_id,
        s.customer_id,
        s.product_id,
        s.date_id AS sale_date_id,
        s.quantity,
        s.unit_price,
        s.discount,
        s.total_amount
    FROM source.sales_transactions s
    WHERE s.last_modified_date > COALESCE(
        NULLIF('{{ task_instance.xcom_pull(task_ids="get_last_watermark", key="last_watermark") }}', 'None')::timestamp,
        '1970-01-01'::timestamp  -- For initial load
    )
    AND s.last_modified_date <= '{{ execution_date }}'::timestamp
    ON CONFLICT (transaction_id) DO UPDATE
    SET
        customer_id = EXCLUDED.customer_id,
        product_id = EXCLUDED.product_id,
        sale_date_id = EXCLUDED.sale_date_id,
        quantity = EXCLUDED.quantity,
        unit_price = EXCLUDED.unit_price,
        discount = EXCLUDED.discount,
        total_amount = EXCLUDED.total_amount;
    """,
    dag=dag,
)


# Task 3: Calculate new watermark (max last_modified_date from this run)
def calculate_new_watermark(**context):
    """Calculate the new watermark value for this run."""
    hook = WarehouseHook(postgres_conn_id="warehouse")

    # Get max last_modified_date from source that was processed
    query = """
    SELECT MAX(last_modified_date) AS new_watermark
    FROM source.sales_transactions
    WHERE last_modified_date <= %s::timestamp;
    """

    result = hook.get_first(query, parameters=(str(context["execution_date"]),))
    new_watermark = result[0] if result and result[0] else context["execution_date"]

    logger.info(
        "Calculated new watermark",
        new_watermark=str(new_watermark),
        execution_date=str(context["execution_date"]),
    )

    context["task_instance"].xcom_push(key="new_watermark", value=str(new_watermark))

    return new_watermark


calculate_watermark = PythonOperator(
    task_id="calculate_new_watermark",
    python_callable=calculate_new_watermark,
    dag=dag,
)


# Task 4: Save watermark to metadata table
save_watermark = PostgresOperator(
    task_id="save_watermark",
    postgres_conn_id="warehouse",
    sql="""
    INSERT INTO etl_metadata.incremental_watermarks (
        pipeline_name,
        table_name,
        watermark_value,
        execution_date,
        status,
        records_processed,
        created_at
    )
    SELECT
        'demo_incremental_load_v1',
        'warehouse.fact_sales',
        COALESCE(
            NULLIF('{{ task_instance.xcom_pull(task_ids="calculate_new_watermark", key="new_watermark") }}', 'None')::timestamp,
            '{{ execution_date }}'::timestamp
        ),
        '{{ execution_date }}'::timestamp,
        'success',
        (SELECT COUNT(*) FROM warehouse.fact_sales),
        CURRENT_TIMESTAMP;
    """,
    dag=dag,
)


# Task 5: Log load statistics
def log_load_stats(**context):
    """Log statistics about the incremental load."""
    ti = context["task_instance"]
    last_watermark = ti.xcom_pull(task_ids="get_last_watermark", key="last_watermark")
    new_watermark = ti.xcom_pull(task_ids="calculate_new_watermark", key="new_watermark")

    hook = WarehouseHook(postgres_conn_id="warehouse")

    # Get record count for this run (query source table which has last_modified_date)
    query = """
    SELECT COUNT(*) AS records_loaded
    FROM source.sales_transactions
    WHERE last_modified_date > COALESCE(%s::timestamp, '1970-01-01'::timestamp)
      AND last_modified_date <= %s::timestamp;
    """

    result = hook.get_first(query, parameters=(last_watermark, new_watermark))
    records_loaded = result[0] if result else 0

    logger.info(
        "Incremental load completed",
        pipeline="demo_incremental_load_v1",
        last_watermark=last_watermark or "None (initial load)",
        new_watermark=new_watermark,
        records_loaded=records_loaded,
        execution_date=context["ds"],
    )


log_stats = PythonOperator(
    task_id="log_load_statistics",
    python_callable=log_load_stats,
    dag=dag,
)


# Task 6: Verify data quality (check for duplicates)
verify_no_duplicates = PostgresOperator(
    task_id="verify_no_duplicates",
    postgres_conn_id="warehouse",
    sql="""
    -- Verify no duplicate transaction_id exists
    DO $$
    DECLARE
        duplicate_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO duplicate_count
        FROM (
            SELECT transaction_id, COUNT(*) AS cnt
            FROM warehouse.fact_sales
            GROUP BY transaction_id
            HAVING COUNT(*) > 1
        ) duplicates;

        IF duplicate_count > 0 THEN
            RAISE EXCEPTION 'Found % duplicate transaction_id in fact_sales table', duplicate_count;
        END IF;

        RAISE NOTICE 'No duplicates found - idempotency verified';
    END $$;
    """,
    dag=dag,
)


# Task 7: Pipeline completion marker
pipeline_complete = EmptyOperator(
    task_id="incremental_load_complete",
    dag=dag,
)


# Define task dependencies
# Linear flow: Get watermark → Load → Calculate → Save → Log → Verify → Complete
get_watermark >> load_incremental_sales
load_incremental_sales >> calculate_watermark
calculate_watermark >> save_watermark
save_watermark >> log_stats
log_stats >> verify_no_duplicates
verify_no_duplicates >> pipeline_complete


"""
PATTERN EXPLANATION:

1. WATERMARK (HIGH WATER MARK) PATTERN:
   - Track the maximum timestamp processed in previous run
   - Only process records with timestamp > last watermark
   - Save new watermark after successful processing
   - Idempotent: Rerunning with same execution_date loads same data

2. FLOW:
   Step 1: Get last watermark (e.g., 2025-01-15 08:00:00)
   Step 2: Load records where last_modified_date > 2025-01-15 08:00:00
          AND last_modified_date <= execution_date (2025-01-15 09:00:00)
   Step 3: Calculate new watermark (max timestamp from this batch)
   Step 4: Save watermark for next run
   Step 5: Verify no duplicates (idempotency check)

3. IDEMPOTENCY:
   - ON CONFLICT DO UPDATE ensures upsert behavior
   - Same watermark range always loads same records
   - Rerunning doesn't create duplicates
   - Safe to backfill or reprocess

4. HANDLING EDGE CASES:

   INITIAL LOAD (no watermark):
   - COALESCE returns '1970-01-01' for first run
   - Loads all historical records

   LATE-ARRIVING DATA:
   - Records with old last_modified_date may arrive late
   - Use buffer window (e.g., execution_date - 1 hour) to catch them
   - Upsert handles updates to existing records

   CLOCK SKEW:
   - Source system clock may be ahead/behind
   - Use execution_date as upper bound (not CURRENT_TIMESTAMP)
   - Ensures deterministic, reproducible loads

5. PERFORMANCE OPTIMIZATION:
   - Index on last_modified_date in source table
   - Partition target table by date for faster inserts
   - Batch size controlled by schedule_interval (hourly = ~1hr of data)
   - Parallel processing possible by partitioning key ranges

6. MONITORING:
   - Watermark metadata table provides audit trail
   - Records processed count tracks data volume
   - Gap detection: Check for missing watermark entries
   - Lag monitoring: Compare watermark to current time

7. COMPARISON TO ALTERNATIVES:

   vs FULL LOAD:
   - Much faster (only new data)
   - Enables higher frequency (hourly vs daily)
   - Lower resource usage

   vs CDC (Change Data Capture):
   - Simpler (no log parsing)
   - Works with any source (just needs timestamp)
   - Slightly higher latency (batch vs streaming)

   vs DELETE + INSERT:
   - Safer (no window where data is missing)
   - Faster (targeted updates only)
   - Preserves foreign key relationships

8. DEPENDENCIES & CONSTRAINTS:
   - depends_on_past=True: Ensures previous hour completed
   - max_active_runs=1: Prevents overlapping runs
   - catchup=True: Backfills missed runs
   - ON CONFLICT requires unique constraint on sales_id

9. NEXT STEPS:
   - Learn SCD Type 2 for dimension history tracking
   - Implement duplicate detection and alerting
   - Add freshness checks to verify timely data
   - Study parallel processing patterns

10. BEST PRACTICES:
    ✓ Always save watermark AFTER successful load
    ✓ Use execution_date, not CURRENT_TIMESTAMP
    ✓ Include buffer window for late-arriving data
    ✓ Verify idempotency with duplicate checks
    ✓ Log statistics for monitoring
    ✓ Handle initial load gracefully (COALESCE)
    ✓ Use upsert (ON CONFLICT) for updates
    ✓ Index watermark column in source
    ✓ Partition target table for performance
    ✓ Monitor watermark lag and gaps
"""
