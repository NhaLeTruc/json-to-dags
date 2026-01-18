-- ============================================================================
-- Migration: 004 - SCD Type 2 Tables
-- ============================================================================
-- Description: Create tables for SCD Type 2 dimension processing
-- Author: Airflow ETL Demo Team
-- Date: 2025-10-23
-- Version: 1.0.0
-- ============================================================================

-- ============================================================================
-- Warehouse: SCD Type 2 Customer Dimension
-- ============================================================================

-- SCD Type 2 Customer Dimension
-- Tracks full history of customer attribute changes
CREATE TABLE IF NOT EXISTS warehouse.dim_customer_scd2 (
    surrogate_key BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    customer_key VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    country VARCHAR(100),
    segment VARCHAR(50),
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL DEFAULT '9999-12-31',
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    record_hash VARCHAR(32),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_customer_scd2_customer_id ON warehouse.dim_customer_scd2(customer_id);
CREATE INDEX idx_dim_customer_scd2_is_current ON warehouse.dim_customer_scd2(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_dim_customer_scd2_valid_dates ON warehouse.dim_customer_scd2(valid_from, valid_to);
CREATE INDEX idx_dim_customer_scd2_hash ON warehouse.dim_customer_scd2(record_hash);

COMMENT ON TABLE warehouse.dim_customer_scd2 IS 'SCD Type 2 customer dimension with full change history';
COMMENT ON COLUMN warehouse.dim_customer_scd2.surrogate_key IS 'Auto-generated surrogate key for each version';
COMMENT ON COLUMN warehouse.dim_customer_scd2.customer_id IS 'Natural business key from source system';
COMMENT ON COLUMN warehouse.dim_customer_scd2.valid_from IS 'Date this version became effective';
COMMENT ON COLUMN warehouse.dim_customer_scd2.valid_to IS 'Date this version expired (9999-12-31 for current)';
COMMENT ON COLUMN warehouse.dim_customer_scd2.is_current IS 'TRUE for the active version of each customer';
COMMENT ON COLUMN warehouse.dim_customer_scd2.record_hash IS 'MD5 hash of tracked attributes for change detection';

-- ============================================================================
-- Staging: SCD Type 2 Staging Table
-- ============================================================================

-- Staging table for SCD Type 2 processing
CREATE TABLE IF NOT EXISTS staging.dim_customer_scd2_staging (
    staging_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    customer_key VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    country VARCHAR(100),
    segment VARCHAR(50),
    source_last_modified TIMESTAMP,
    load_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_staging_scd2_customer_id ON staging.dim_customer_scd2_staging(customer_id);

COMMENT ON TABLE staging.dim_customer_scd2_staging IS 'Staging table for SCD Type 2 customer dimension processing';

-- ============================================================================
-- Seed initial SCD2 data from existing dim_customer
-- ============================================================================

-- Populate SCD2 dimension with initial records from existing customers
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
    created_at::date AS valid_from,
    '9999-12-31'::date AS valid_to,
    TRUE AS is_current,
    MD5(
        COALESCE(customer_key, '') ||
        COALESCE(customer_name, '') ||
        COALESCE(email, '') ||
        COALESCE(country, '') ||
        COALESCE(segment, '')
    ) AS record_hash,
    created_at,
    updated_at
FROM warehouse.dim_customer
ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON warehouse.dim_customer_scd2 TO warehouse_user;
GRANT ALL PRIVILEGES ON staging.dim_customer_scd2_staging TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA warehouse TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA staging TO warehouse_user;

-- Record this migration
INSERT INTO warehouse.schema_migrations (migration_name, description)
VALUES ('004_scd_type2_tables', 'SCD Type 2 dimension and staging tables for customer history tracking')
ON CONFLICT (migration_name) DO NOTHING;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'SCD Type 2 tables created successfully';
    RAISE NOTICE 'Tables created: warehouse.dim_customer_scd2, staging.dim_customer_scd2_staging';
    RAISE NOTICE 'Initial data seeded from warehouse.dim_customer';
END $$;
