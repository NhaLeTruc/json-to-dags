-- ============================================================================
-- Apache Airflow ETL Demo Platform - Mock Data Warehouse Schema
-- ============================================================================
-- Purpose: Define star schema for data warehouse with dimensions and facts
-- Target: PostgreSQL 15+
-- ============================================================================

-- Drop existing tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS warehouse.quality_check_results CASCADE;
DROP TABLE IF EXISTS warehouse.spark_job_submissions CASCADE;
DROP TABLE IF EXISTS warehouse.notification_log CASCADE;
DROP TABLE IF EXISTS warehouse.fact_sales CASCADE;
DROP TABLE IF EXISTS warehouse.staging_sales CASCADE;
DROP TABLE IF EXISTS warehouse.dim_customer CASCADE;
DROP TABLE IF EXISTS warehouse.dim_product CASCADE;
DROP TABLE IF EXISTS warehouse.dim_date CASCADE;
DROP SCHEMA IF EXISTS warehouse CASCADE;
DROP SCHEMA IF EXISTS staging CASCADE;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS staging;

-- ============================================================================
-- Dimension Tables
-- ============================================================================

-- Dimension: Customer
CREATE TABLE warehouse.dim_customer (
    customer_id SERIAL PRIMARY KEY,
    customer_key VARCHAR(50) NOT NULL UNIQUE,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    country VARCHAR(100),
    segment VARCHAR(50) CHECK (segment IN ('Enterprise', 'SMB', 'Consumer')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_customer_key ON warehouse.dim_customer(customer_key);
CREATE INDEX idx_dim_customer_segment ON warehouse.dim_customer(segment);

COMMENT ON TABLE warehouse.dim_customer IS 'Customer master data dimension';
COMMENT ON COLUMN warehouse.dim_customer.customer_key IS 'Natural business key (e.g., CUST-10001)';
COMMENT ON COLUMN warehouse.dim_customer.segment IS 'Customer segment: Enterprise, SMB, or Consumer';

-- Dimension: Product
CREATE TABLE warehouse.dim_product (
    product_id SERIAL PRIMARY KEY,
    product_key VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price > 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_product_key ON warehouse.dim_product(product_key);
CREATE INDEX idx_dim_product_category ON warehouse.dim_product(category);

COMMENT ON TABLE warehouse.dim_product IS 'Product master data dimension';
COMMENT ON COLUMN warehouse.dim_product.product_key IS 'SKU or product code (e.g., PROD-ABC123)';

-- Dimension: Date
CREATE TABLE warehouse.dim_date (
    date_id INTEGER PRIMARY KEY,  -- YYYYMMDD format
    date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name VARCHAR(20) NOT NULL,
    week INTEGER NOT NULL CHECK (week BETWEEN 1 AND 53),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_dim_date_date ON warehouse.dim_date(date);
CREATE INDEX idx_dim_date_year_month ON warehouse.dim_date(year, month);

COMMENT ON TABLE warehouse.dim_date IS 'Time dimension for date-based analytics';
COMMENT ON COLUMN warehouse.dim_date.date_id IS 'Date in YYYYMMDD integer format (e.g., 20250115)';
COMMENT ON COLUMN warehouse.dim_date.day_of_week IS '1=Monday, 7=Sunday (ISO 8601)';

-- ============================================================================
-- Fact Tables
-- ============================================================================

-- Fact: Sales Transactions
CREATE TABLE warehouse.fact_sales (
    sale_id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(100) NOT NULL,
    customer_id INTEGER REFERENCES warehouse.dim_customer(customer_id),
    product_id INTEGER REFERENCES warehouse.dim_product(product_id),
    sale_date_id INTEGER REFERENCES warehouse.dim_date(date_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price > 0),
    discount DECIMAL(10, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    total_amount DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_fact_sales_transaction ON warehouse.fact_sales(transaction_id);
CREATE INDEX idx_fact_sales_customer ON warehouse.fact_sales(customer_id);
CREATE INDEX idx_fact_sales_product ON warehouse.fact_sales(product_id);
CREATE INDEX idx_fact_sales_date ON warehouse.fact_sales(sale_date_id);
CREATE INDEX idx_fact_sales_date_customer ON warehouse.fact_sales(sale_date_id, customer_id);

COMMENT ON TABLE warehouse.fact_sales IS 'Sales transaction fact table';
COMMENT ON COLUMN warehouse.fact_sales.transaction_id IS 'Business transaction identifier';
COMMENT ON COLUMN warehouse.fact_sales.total_amount IS 'Calculated: quantity * unit_price - discount';

-- ============================================================================
-- Staging Tables
-- ============================================================================

-- Staging: Sales (landing zone for raw data)
CREATE TABLE staging.staging_sales (
    sale_id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(100) NOT NULL,
    customer_id INTEGER,
    product_id INTEGER,
    sale_date_id INTEGER,
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    discount DECIMAL(10, 2),
    total_amount DECIMAL(12, 2),
    source_system VARCHAR(100),
    load_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_processed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_staging_sales_load_timestamp ON staging.staging_sales(load_timestamp);
CREATE INDEX idx_staging_sales_is_processed ON staging.staging_sales(is_processed);

COMMENT ON TABLE staging.staging_sales IS 'Staging table for raw sales data before validation';

-- ============================================================================
-- Operational Metadata Tables
-- ============================================================================

-- Quality Check Results
CREATE TABLE warehouse.quality_check_results (
    check_id BIGSERIAL PRIMARY KEY,
    dag_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING', 'INFO')),
    passed BOOLEAN NOT NULL,
    rows_checked BIGINT,
    rows_failed BIGINT,
    failure_rate DECIMAL(5, 2),
    threshold DECIMAL(5, 2),
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quality_check_dag_execution ON warehouse.quality_check_results(dag_id, execution_date);
CREATE INDEX idx_quality_check_table ON warehouse.quality_check_results(table_name, created_at);
CREATE INDEX idx_quality_check_severity ON warehouse.quality_check_results(severity, passed);

COMMENT ON TABLE warehouse.quality_check_results IS 'Historical tracking of data quality validation results';
COMMENT ON COLUMN warehouse.quality_check_results.check_type IS 'Type: schema_validation, completeness_check, freshness_check, uniqueness_check, null_rate_check';

-- Spark Job Submissions
CREATE TABLE warehouse.spark_job_submissions (
    job_id BIGSERIAL PRIMARY KEY,
    dag_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    cluster_type VARCHAR(50) NOT NULL CHECK (cluster_type IN ('standalone', 'yarn', 'kubernetes')),
    application_path TEXT NOT NULL,
    spark_job_id VARCHAR(255),
    status VARCHAR(50) NOT NULL CHECK (status IN ('SUBMITTED', 'RUNNING', 'SUCCESS', 'FAILED')),
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    error_message TEXT,
    logs_url TEXT
);

CREATE INDEX idx_spark_job_dag_execution ON warehouse.spark_job_submissions(dag_id, execution_date);
CREATE INDEX idx_spark_job_status ON warehouse.spark_job_submissions(status, submitted_at);
CREATE INDEX idx_spark_job_cluster ON warehouse.spark_job_submissions(cluster_type, submitted_at);

COMMENT ON TABLE warehouse.spark_job_submissions IS 'Tracking of Spark job submissions and execution';

-- Notification Log
CREATE TABLE warehouse.notification_log (
    notification_id BIGSERIAL PRIMARY KEY,
    dag_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    channel VARCHAR(50) NOT NULL CHECK (channel IN ('email', 'teams', 'telegram')),
    recipients JSONB NOT NULL,
    subject VARCHAR(500),
    message TEXT NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('SENT', 'FAILED', 'RETRYING')),
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_notification_dag_execution ON warehouse.notification_log(dag_id, execution_date);
CREATE INDEX idx_notification_channel_status ON warehouse.notification_log(channel, status);

COMMENT ON TABLE warehouse.notification_log IS 'Audit trail for notification deliveries';

-- ============================================================================
-- Grants (for application user)
-- ============================================================================

-- Grant permissions to warehouse user
GRANT USAGE ON SCHEMA warehouse TO warehouse_user;
GRANT USAGE ON SCHEMA staging TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA warehouse TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA staging TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA warehouse TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA staging TO warehouse_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA warehouse GRANT ALL ON TABLES TO warehouse_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON TABLES TO warehouse_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA warehouse GRANT ALL ON SEQUENCES TO warehouse_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON SEQUENCES TO warehouse_user;

-- ============================================================================
-- Schema Ready
-- ============================================================================

-- Verification query
SELECT
    'warehouse' AS schema_name,
    COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'warehouse'
UNION ALL
SELECT
    'staging' AS schema_name,
    COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'staging';
