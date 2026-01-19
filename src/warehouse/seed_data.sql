-- ============================================================================
-- Apache Airflow ETL Demo Platform - Mock Warehouse Seed Data
-- ============================================================================
-- Purpose: Populate warehouse with realistic test data for demonstrations
-- Data Volumes: 1000 customers, 500 products, 5 years dates, 100k sales
-- Note: This seed data includes intentional quality issues for testing
-- ============================================================================

-- Disable triggers temporarily for faster bulk insert
SET session_replication_role = replica;

-- ============================================================================
-- Dimension: Date (7 years: 2020-2026)
-- ============================================================================

INSERT INTO warehouse.dim_date (date_id, date, year, quarter, month, month_name, week, day_of_week, day_name, is_weekend, is_holiday)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER AS date_id,
    d::DATE AS date,
    EXTRACT(YEAR FROM d)::INTEGER AS year,
    EXTRACT(QUARTER FROM d)::INTEGER AS quarter,
    EXTRACT(MONTH FROM d)::INTEGER AS month,
    TO_CHAR(d, 'Month') AS month_name,
    EXTRACT(WEEK FROM d)::INTEGER AS week,
    EXTRACT(ISODOW FROM d)::INTEGER AS day_of_week,
    TO_CHAR(d, 'Day') AS day_name,
    EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend,
    FALSE AS is_holiday  -- Simplified for demo
FROM generate_series(
    '2020-01-01'::DATE,
    '2026-12-31'::DATE,
    '1 day'::INTERVAL
) AS d;

-- Mark some holidays (simplified US holidays for demo)
UPDATE warehouse.dim_date SET is_holiday = TRUE
WHERE (month = 1 AND EXTRACT(DAY FROM date) = 1)   -- New Year's Day
   OR (month = 7 AND EXTRACT(DAY FROM date) = 4)   -- Independence Day
   OR (month = 12 AND EXTRACT(DAY FROM date) = 25); -- Christmas

-- ============================================================================
-- Dimension: Customer (1000 records with realistic data patterns)
-- ============================================================================

-- Note: Using deterministic generation for reproducibility
INSERT INTO warehouse.dim_customer (customer_key, customer_name, email, country, segment)
WITH customer_base AS (
    SELECT
        i,
        'CUST-' || LPAD(i::TEXT, 5, '0') AS customer_key,
        -- Generate realistic names
        (ARRAY['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Robert', 'Lisa', 'James', 'Jennifer',
               'William', 'Linda', 'Richard', 'Patricia', 'Joseph', 'Elizabeth', 'Thomas', 'Maria', 'Charles', 'Susan'])[1 + (i % 20)] ||
        ' ' ||
        (ARRAY['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
               'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'])[1 + ((i / 20) % 20)] AS customer_name,
        -- Generate emails (some with missing data for quality testing)
        CASE
            WHEN i % 50 = 0 THEN NULL  -- 2% missing emails (quality issue)
            ELSE LOWER(
                REPLACE(
                    (ARRAY['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Robert', 'Lisa', 'James', 'Jennifer',
                           'William', 'Linda', 'Richard', 'Patricia', 'Joseph', 'Elizabeth', 'Thomas', 'Maria', 'Charles', 'Susan'])[1 + (i % 20)],
                    ' ', ''
                ) || '.' ||
                REPLACE(
                    (ARRAY['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                           'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'])[1 + ((i / 20) % 20)],
                    ' ', ''
                ) || i || '@example.com'
            )
        END AS email,
        -- Distribute across countries
        (ARRAY['USA', 'Canada', 'UK', 'Germany', 'France', 'Spain', 'Italy', 'Australia', 'Japan', 'Brazil'])[1 + (i % 10)] AS country,
        -- Distribute across segments
        CASE
            WHEN i % 10 < 2 THEN 'Enterprise'  -- 20%
            WHEN i % 10 < 6 THEN 'SMB'          -- 40%
            ELSE 'Consumer'                      -- 40%
        END AS segment
    FROM generate_series(1, 1000) AS i
)
SELECT customer_key, customer_name, email, country, segment
FROM customer_base;

-- ============================================================================
-- Dimension: Product (500 records)
-- ============================================================================

INSERT INTO warehouse.dim_product (product_key, product_name, category, subcategory, unit_price)
WITH product_base AS (
    SELECT
        i,
        'PROD-' || (ARRAY['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])[1 + (i % 10)] ||
        LPAD((i / 10)::TEXT, 3, '0') AS product_key,
        -- Generate product names
        (ARRAY['Premium', 'Standard', 'Economy', 'Deluxe', 'Professional', 'Basic', 'Advanced', 'Ultimate', 'Classic', 'Modern'])[1 + (i % 10)] ||
        ' ' ||
        (ARRAY['Widget', 'Gadget', 'Device', 'Tool', 'Instrument', 'Apparatus', 'Equipment', 'Machine', 'System', 'Component'])[1 + ((i / 10) % 10)] AS product_name,
        -- Categories
        (ARRAY['Electronics', 'Clothing', 'Food', 'Books', 'Home'])[1 + (i % 5)] AS category,
        -- Subcategories
        (ARRAY['Accessories', 'Main Items', 'Supplies', 'Parts', 'Bundles'])[1 + ((i / 5) % 5)] AS subcategory,
        -- Unit prices between $5 and $500
        (5 + (i % 100) * 5.0)::DECIMAL(10,2) AS unit_price
    FROM generate_series(1, 500) AS i
)
SELECT product_key, product_name, category, subcategory, unit_price
FROM product_base;

-- ============================================================================
-- Fact: Sales (100,000 records with intentional quality issues)
-- ============================================================================

INSERT INTO warehouse.fact_sales (transaction_id, customer_id, product_id, sale_date_id, quantity, unit_price, discount, total_amount)
WITH sales_base AS (
    SELECT
        i,
        'TXN-' || LPAD(i::TEXT, 8, '0') AS transaction_id,
        -- Customer references (some NULL for orphaned records - quality issue)
        CASE
            WHEN i % 50 = 0 THEN NULL  -- 2% orphaned records
            ELSE 1 + (i % 1000)
        END AS customer_id,
        -- Product references
        1 + ((i * 7) % 500) AS product_id,
        -- Sale dates distributed over 2020-2024
        TO_CHAR(
            '2020-01-01'::DATE + (i % 1826) * INTERVAL '1 day',
            'YYYYMMDD'
        )::INTEGER AS sale_date_id,
        -- Quantities (some negative for error testing - quality issue)
        CASE
            WHEN i % 100 = 0 THEN -1 * (1 + (i % 10))  -- 1% negative quantities
            ELSE 1 + (i % 10)
        END AS quantity,
        -- Unit prices
        (10 + (i % 50) * 5.0)::DECIMAL(10,2) AS unit_price,
        -- Discounts
        ((i % 20) * 2.5)::DECIMAL(10,2) AS discount
    FROM generate_series(1, 100000) AS i
)
SELECT
    transaction_id,
    customer_id,
    product_id,
    sale_date_id,
    quantity,
    unit_price,
    discount,
    -- Calculate total amount (some with intentional calculation errors - quality issue)
    CASE
        WHEN i % 200 = 0 THEN (quantity * unit_price)  -- 0.5% missing discount application
        ELSE (quantity * unit_price - discount)
    END AS total_amount
FROM sales_base;

-- Attempt to add duplicate transaction_ids for uniqueness testing
-- With UNIQUE constraint on transaction_id, duplicates are rejected (ON CONFLICT DO NOTHING)
-- This demonstrates proper data integrity enforcement
INSERT INTO warehouse.fact_sales (transaction_id, customer_id, product_id, sale_date_id, quantity, unit_price, discount, total_amount)
SELECT
    'TXN-' || LPAD((i % 1000)::TEXT, 8, '0') AS transaction_id,  -- Attempts duplicate transactions
    1 + (i % 1000) AS customer_id,
    1 + ((i * 11) % 500) AS product_id,
    TO_CHAR('2020-01-01'::DATE + (i % 365) * INTERVAL '1 day', 'YYYYMMDD')::INTEGER AS sale_date_id,
    1 + (i % 5) AS quantity,
    (15 + (i % 30) * 5.0)::DECIMAL(10,2) AS unit_price,
    ((i % 10) * 2.0)::DECIMAL(10,2) AS discount,
    ((1 + (i % 5)) * (15 + (i % 30) * 5.0) - ((i % 10) * 2.0))::DECIMAL(10,2) AS total_amount
FROM generate_series(1, 3000) AS i
ON CONFLICT (transaction_id) DO NOTHING;  -- Duplicates silently rejected

-- ============================================================================
-- Staging: Sales (sample staging data)
-- ============================================================================

INSERT INTO staging.staging_sales (transaction_id, customer_id, product_id, sale_date_id, quantity, unit_price, discount, total_amount, source_system, is_processed)
SELECT
    'TXN-STAGE-' || LPAD(i::TEXT, 6, '0') AS transaction_id,
    1 + (i % 1000) AS customer_id,
    1 + ((i * 13) % 500) AS product_id,
    TO_CHAR('2024-10-01'::DATE + (i % 15) * INTERVAL '1 day', 'YYYYMMDD')::INTEGER AS sale_date_id,
    1 + (i % 5) AS quantity,
    (20 + (i % 40) * 5.0)::DECIMAL(10,2) AS unit_price,
    ((i % 15) * 3.0)::DECIMAL(10,2) AS discount,
    ((1 + (i % 5)) * (20 + (i % 40) * 5.0) - ((i % 15) * 3.0))::DECIMAL(10,2) AS total_amount,
    'POS_SYSTEM' AS source_system,
    FALSE AS is_processed
FROM generate_series(1, 1000) AS i;

-- Re-enable triggers
SET session_replication_role = DEFAULT;

-- ============================================================================
-- Data Quality Summary
-- ============================================================================

-- Verify data volumes and intentional quality issues
SELECT
    'dim_customer' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE email IS NULL) AS null_emails,
    ROUND(100.0 * COUNT(*) FILTER (WHERE email IS NULL) / COUNT(*), 2) AS null_rate_percent
FROM warehouse.dim_customer

UNION ALL

SELECT
    'dim_product' AS table_name,
    COUNT(*) AS total_rows,
    0 AS null_count,
    0.0 AS null_rate_percent
FROM warehouse.dim_product

UNION ALL

SELECT
    'dim_date' AS table_name,
    COUNT(*) AS total_rows,
    0 AS null_count,
    0.0 AS null_rate_percent
FROM warehouse.dim_date

UNION ALL

SELECT
    'fact_sales' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE customer_id IS NULL) AS orphaned_records,
    ROUND(100.0 * COUNT(*) FILTER (WHERE customer_id IS NULL) / COUNT(*), 2) AS orphan_rate_percent
FROM warehouse.fact_sales

UNION ALL

SELECT
    'staging_sales' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE is_processed = FALSE) AS unprocessed,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_processed = FALSE) / COUNT(*), 2) AS unprocessed_percent
FROM staging.staging_sales;

-- Duplicate transactions summary
SELECT
    'Duplicate Check' AS check_name,
    COUNT(*) AS total_transactions,
    COUNT(DISTINCT transaction_id) AS unique_transactions,
    COUNT(*) - COUNT(DISTINCT transaction_id) AS duplicates
FROM warehouse.fact_sales;
