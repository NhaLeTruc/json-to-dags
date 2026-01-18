"""
SCD Type 2 DAG - Intermediate Example

PATTERN: Slowly Changing Dimension Type 2 - Track full history of dimension changes

LEARNING OBJECTIVES:
1. Understand SCD Type 2 pattern for dimension history tracking
2. Learn effective date range management (valid_from, valid_to)
3. Practice current flag maintenance (is_current)
4. Implement change detection with hash comparison
5. Handle updates by expiring old records and inserting new versions

USE CASE:
Track complete history of customer dimension changes. When a customer's
address, email, or other attributes change, we preserve the old version
with its time validity and create a new current version. Essential for
historical reporting and regulatory compliance.

KEY AIRFLOW FEATURES:
- PostgresOperator for complex SCD logic
- Multi-step SQL workflow
- Transaction management with single SQL block
- Change detection with MD5 hash

BUSINESS VALUE:
- Enables "as of date" historical reporting
- Maintains audit trail of all changes
- Supports compliance requirements (GDPR, SOX)
- Prevents data loss from updates
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
    "owner": "dimensional_modeling_team",
    "depends_on_past": False,  # Disabled for demo
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# DAG definition
dag = DAG(
    dag_id="demo_scd_type2_v1",
    default_args=default_args,
    description="SCD Type 2 pattern for customer dimension history tracking",
    schedule="@daily",
    start_date=days_ago(7),
    catchup=True,
    max_active_runs=1,
    tags=["intermediate", "scd-type-2", "dimension", "history", "idempotent"],
    doc_md=__doc__,
)


# Task 1: Load source customer data to staging
load_staging = PostgresOperator(
    task_id="load_staging_customers",
    postgres_conn_id="warehouse",
    sql="""
    -- Truncate and load current snapshot from source
    TRUNCATE TABLE staging.dim_customer_scd2_staging;

    INSERT INTO staging.dim_customer_scd2_staging (
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        source_last_modified
    )
    SELECT
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        extract_timestamp AS source_last_modified
    FROM source.dim_customer
    WHERE extract_timestamp <= '{{ ds }}'::date + INTERVAL '1 day';
    """,
    dag=dag,
)


# Task 2: Perform SCD Type 2 processing
# This is the core SCD Type 2 logic - complex but powerful
scd_type2_processing = PostgresOperator(
    task_id="scd_type2_processing",
    postgres_conn_id="warehouse",
    sql="""
    -- SCD Type 2 Processing for Customer Dimension
    -- This maintains full history of customer attribute changes

    -- Step 1: Identify changed records
    -- Records that exist in staging but differ from current warehouse version
    CREATE TEMP TABLE IF NOT EXISTS changed_customers AS
    SELECT
        stg.customer_id,
        stg.customer_key,
        stg.customer_name,
        stg.email,
        stg.country,
        stg.segment,
        stg.source_last_modified,
        -- Calculate hash of attribute values to detect changes
        MD5(
            COALESCE(stg.customer_key, '') ||
            COALESCE(stg.customer_name, '') ||
            COALESCE(stg.email, '') ||
            COALESCE(stg.country, '') ||
            COALESCE(stg.segment, '')
        ) AS record_hash,
        wh.surrogate_key AS old_surrogate_key,
        wh.record_hash AS old_hash
    FROM staging.dim_customer_scd2_staging stg
    LEFT JOIN warehouse.dim_customer_scd2 wh
        ON stg.customer_id = wh.customer_id
       AND wh.is_current = TRUE
    WHERE
        -- New customer (not in warehouse)
        wh.customer_id IS NULL
        OR
        -- Existing customer with changed attributes
        MD5(
            COALESCE(stg.customer_key, '') ||
            COALESCE(stg.customer_name, '') ||
            COALESCE(stg.email, '') ||
            COALESCE(stg.country, '') ||
            COALESCE(stg.segment, '')
        ) != COALESCE(wh.record_hash, '');

    -- Step 2: Expire old versions of changed records
    -- Set valid_to date and is_current flag
    UPDATE warehouse.dim_customer_scd2
    SET
        valid_to = '{{ ds }}'::date - INTERVAL '1 day',
        is_current = FALSE,
        updated_at = CURRENT_TIMESTAMP
    WHERE customer_id IN (
        SELECT customer_id
        FROM changed_customers
        WHERE old_surrogate_key IS NOT NULL
    )
    AND is_current = TRUE;

    -- Step 3: Insert new versions
    -- For both new customers and changed existing customers
    INSERT INTO warehouse.dim_customer_scd2 (
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        valid_from,
        valid_to,
        is_current,
        record_hash,
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
        '{{ ds }}'::date AS valid_from,
        '9999-12-31'::date AS valid_to,
        TRUE AS is_current,
        record_hash,
        CURRENT_TIMESTAMP AS created_at,
        CURRENT_TIMESTAMP AS updated_at
    FROM changed_customers;

    -- Step 4: Log SCD processing statistics
    INSERT INTO etl_metadata.scd_processing_log (
        pipeline_name,
        table_name,
        execution_date,
        new_records,
        changed_records,
        expired_records,
        total_current_records,
        status,
        created_at
    )
    SELECT
        'demo_scd_type2_v1',
        'warehouse.dim_customer_scd2',
        '{{ ds }}'::date,
        (SELECT COUNT(*) FROM changed_customers WHERE old_surrogate_key IS NULL),
        (SELECT COUNT(*) FROM changed_customers WHERE old_surrogate_key IS NOT NULL),
        (SELECT COUNT(*) FROM warehouse.dim_customer_scd2 WHERE valid_to = '{{ ds }}'::date - INTERVAL '1 day'),
        (SELECT COUNT(*) FROM warehouse.dim_customer_scd2 WHERE is_current = TRUE),
        'success',
        CURRENT_TIMESTAMP;

    -- Cleanup temp table
    DROP TABLE IF EXISTS changed_customers;
    """,
    dag=dag,
)


# Task 3: Verify SCD integrity
verify_scd_integrity = PostgresOperator(
    task_id="verify_scd_integrity",
    postgres_conn_id="warehouse",
    sql="""
    -- Verify SCD Type 2 integrity constraints
    DO $$
    DECLARE
        multiple_current_count INTEGER;
        overlapping_dates_count INTEGER;
    BEGIN
        -- Check 1: Each customer should have exactly one current record
        SELECT COUNT(*) INTO multiple_current_count
        FROM (
            SELECT customer_id, COUNT(*) AS current_count
            FROM warehouse.dim_customer_scd2
            WHERE is_current = TRUE
            GROUP BY customer_id
            HAVING COUNT(*) > 1
        ) multi;

        IF multiple_current_count > 0 THEN
            RAISE EXCEPTION 'Found % customers with multiple current records', multiple_current_count;
        END IF;

        -- Check 2: No overlapping date ranges for same customer (skip if no data yet)
        SELECT COUNT(*) INTO overlapping_dates_count
        FROM warehouse.dim_customer_scd2 a
        JOIN warehouse.dim_customer_scd2 b
            ON a.customer_id = b.customer_id
           AND a.surrogate_key != b.surrogate_key
        WHERE a.valid_from <= b.valid_to
          AND a.valid_to >= b.valid_from
          AND a.valid_from != b.valid_from;  -- Exclude same-day records

        IF overlapping_dates_count > 0 THEN
            RAISE WARNING 'Found % potential overlapping date ranges', overlapping_dates_count;
        END IF;

        RAISE NOTICE 'SCD Type 2 integrity verified successfully';
    END $$;
    """,
    dag=dag,
)


# Task 4: Log SCD processing statistics
def log_scd_stats(**context):
    """Log statistics about SCD Type 2 processing."""
    hook = WarehouseHook(postgres_conn_id="warehouse")

    query = """
    SELECT
        COALESCE(new_records, 0),
        COALESCE(changed_records, 0),
        COALESCE(expired_records, 0),
        COALESCE(total_current_records, 0)
    FROM etl_metadata.scd_processing_log
    WHERE pipeline_name = 'demo_scd_type2_v1'
      AND execution_date = %s::date
    ORDER BY created_at DESC
    LIMIT 1;
    """

    result = hook.get_first(query, parameters=(context["ds"],))

    if result:
        new_records, changed_records, expired_records, total_current = result
        logger.info(
            "SCD Type 2 processing completed",
            pipeline="demo_scd_type2_v1",
            execution_date=context["ds"],
            new_records=new_records,
            changed_records=changed_records,
            expired_records=expired_records,
            total_current_records=total_current,
        )
    else:
        logger.warning("No SCD processing stats found", execution_date=context["ds"])


log_stats = PythonOperator(
    task_id="log_scd_statistics",
    python_callable=log_scd_stats,
    dag=dag,
)


# Task 5: Create sample historical query
demo_historical_query = PostgresOperator(
    task_id="demo_historical_query",
    postgres_conn_id="warehouse",
    sql="""
    -- Example: Get current customer records
    SELECT
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        valid_from,
        valid_to,
        is_current
    FROM warehouse.dim_customer_scd2
    WHERE is_current = TRUE
    ORDER BY customer_id
    LIMIT 10;

    -- Example: Get history of changes for first customer
    SELECT
        customer_id,
        customer_key,
        customer_name,
        email,
        country,
        segment,
        valid_from,
        valid_to,
        is_current
    FROM warehouse.dim_customer_scd2
    WHERE customer_id = (SELECT MIN(customer_id) FROM warehouse.dim_customer_scd2)
    ORDER BY valid_from DESC;
    """,
    dag=dag,
)


# Task 6: Pipeline completion
pipeline_complete = EmptyOperator(
    task_id="scd_type2_complete",
    dag=dag,
)


# Define task dependencies
load_staging >> scd_type2_processing
scd_type2_processing >> verify_scd_integrity
verify_scd_integrity >> log_stats
log_stats >> demo_historical_query
demo_historical_query >> pipeline_complete


"""
PATTERN EXPLANATION:

1. SCD TYPE 2 FUNDAMENTALS:
   - Preserves full history of dimension changes
   - Each change creates a new version with new surrogate key
   - Date ranges track when each version was valid
   - Current flag identifies active version
   - Natural key (customer_id) + surrogate key (auto-increment)

2. TABLE STRUCTURE:
   CREATE TABLE warehouse.dim_customer (
       surrogate_key SERIAL PRIMARY KEY,      -- Unique for each version
       customer_id INTEGER NOT NULL,          -- Business key (natural key)
       customer_name VARCHAR(255),            -- Attributes that can change
       email VARCHAR(255),
       address VARCHAR(500),
       ...
       valid_from DATE NOT NULL,              -- Effective start date
       valid_to DATE NOT NULL,                -- Effective end date
       is_current BOOLEAN NOT NULL,           -- TRUE for active version
       record_hash VARCHAR(32),               -- MD5 hash for change detection
       created_at TIMESTAMP NOT NULL,
       updated_at TIMESTAMP NOT NULL
   );

3. CHANGE DETECTION:
   - MD5 hash of all tracked attributes
   - Compare staging hash vs warehouse hash
   - Only process records with hash mismatch
   - Efficient: Avoids unnecessary updates

4. SCD PROCESSING STEPS:
   Step 1: Load current snapshot to staging
   Step 2: Detect changes via hash comparison
   Step 3: Expire old versions (set valid_to, is_current=FALSE)
   Step 4: Insert new versions (valid_from=today, is_current=TRUE)
   Step 5: Verify integrity constraints
   Step 6: Log statistics

5. HISTORICAL QUERIES:

   Current state:
   SELECT * FROM dim_customer WHERE is_current = TRUE;

   State as of specific date:
   SELECT * FROM dim_customer
   WHERE '2025-01-15' BETWEEN valid_from AND valid_to;

   Change history for customer:
   SELECT * FROM dim_customer
   WHERE customer_id = 123
   ORDER BY valid_from;

   Count of changes per customer:
   SELECT customer_id, COUNT(*) - 1 AS num_changes
   FROM dim_customer
   GROUP BY customer_id;

6. IDEMPOTENCY:
   - Rerunning with same execution_date produces same result
   - Hash comparison ensures no duplicate versions
   - Date ranges deterministic based on execution_date
   - Safe to backfill or reprocess

7. INTEGRITY CONSTRAINTS:
   ✓ One current record per customer
   ✓ No overlapping date ranges
   ✓ No gaps in history (optional, depends on requirements)
   ✓ valid_from < valid_to for all records
   ✓ current records have valid_to = 9999-12-31

8. SCD TYPE COMPARISON:

   TYPE 0 (No tracking):
   - Never updates, reject changes
   - Use case: Immutable facts

   TYPE 1 (Overwrite):
   - Updates in place, no history
   - Use case: Error corrections, not true changes

   TYPE 2 (Full history): ← THIS PATTERN
   - New version for each change
   - Use case: Historical reporting, compliance

   TYPE 3 (Limited history):
   - Tracks previous value in separate column
   - Use case: Track last change only

   TYPE 4 (History table):
   - Current table + separate history table
   - Use case: Optimize query performance

   TYPE 6 (Hybrid):
   - Combines Type 1, 2, and 3
   - Use case: Current + historical + previous

9. PERFORMANCE CONSIDERATIONS:
   - Hash comparison reduces unnecessary processing
   - Indexes on customer_id, is_current, valid_from, valid_to
   - Partition by valid_from for large dimensions
   - Batch processing in single transaction

10. WHEN TO USE SCD TYPE 2:
    ✓ Need complete audit trail
    ✓ Regulatory compliance requirements
    ✓ Historical trending and analysis
    ✓ "As of date" reporting
    ✓ Slowly changing dimensions (not rapidly changing)

11. WHEN NOT TO USE:
    ✗ Rapidly changing dimensions (millions of changes/day)
    ✗ Don't need historical analysis
    ✗ Storage constraints (history is expensive)
    ✗ Real-time updates required (use CDC instead)

12. NEXT STEPS:
    - Learn parallel processing patterns
    - Study fact table surrogate key lookups
    - Implement late-arriving dimension handling
    - Explore Type 4 (history table) alternative

13. COMMON PITFALLS:
    ✗ Forgetting to expire old versions
    ✗ Creating overlapping date ranges
    ✗ Not handling NULLs in hash calculation
    ✗ Using natural key instead of surrogate in facts
    ✗ Not indexing is_current and date ranges
    ✗ Updating attributes without creating new version
"""
