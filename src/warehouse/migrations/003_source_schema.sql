-- ============================================================================
-- Migration: 003 - Source Schema
-- ============================================================================
-- Description: Create source schema for raw data staging
-- Author: Airflow ETL Demo Team
-- Date: 2025-10-23
-- Version: 1.0.0
-- Idempotent: Yes - safe to re-run
-- ============================================================================

-- Create source schema
CREATE SCHEMA IF NOT EXISTS source;

-- ============================================================================
-- Source Tables (Raw Data Landing Zone)
-- ============================================================================

-- Source: Sales Transactions
-- Purpose: Raw sales transaction data from source systems
CREATE TABLE IF NOT EXISTS source.sales_transactions (
    sales_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    date_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price > 0),
    total_amount DECIMAL(10, 2) NOT NULL,
    discount DECIMAL(10, 2) DEFAULT 0 CHECK (discount >= 0),
    tax_amount DECIMAL(10, 2) DEFAULT 0 CHECK (tax_amount >= 0),
    sale_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_sales_last_modified ON source.sales_transactions(last_modified_date);
CREATE INDEX IF NOT EXISTS idx_source_sales_customer ON source.sales_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_source_sales_timestamp ON source.sales_transactions(sale_timestamp);

COMMENT ON TABLE source.sales_transactions IS 'Raw sales transaction data from source systems';
COMMENT ON COLUMN source.sales_transactions.last_modified_date IS 'Used for incremental load watermark tracking';

-- Source: Customer Dimension
-- Purpose: Raw customer data for SCD Type 2 processing
CREATE TABLE IF NOT EXISTS source.dim_customer (
    customer_id INTEGER NOT NULL,
    customer_key VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    country VARCHAR(100),
    segment VARCHAR(50),
    extract_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, extract_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_source_dim_customer_key ON source.dim_customer(customer_key);
CREATE INDEX IF NOT EXISTS idx_source_dim_customer_extract ON source.dim_customer(extract_timestamp);

COMMENT ON TABLE source.dim_customer IS 'Raw customer dimension data for SCD Type 2 processing';
COMMENT ON COLUMN source.dim_customer.extract_timestamp IS 'Timestamp when data was extracted from source system';

-- Grant permissions to warehouse user
GRANT ALL PRIVILEGES ON SCHEMA source TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA source TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA source TO warehouse_user;

-- Insert sample data for testing
INSERT INTO source.sales_transactions (customer_id, product_id, date_id, quantity, unit_price, total_amount, discount, tax_amount, sale_timestamp, last_modified_date)
VALUES
    (1, 1, 20251016, 2, 100.00, 200.00, 10.00, 15.00, '2025-10-16 10:00:00', '2025-10-16 10:00:00'),
    (2, 2, 20251016, 1, 250.00, 250.00, 0.00, 20.00, '2025-10-16 11:00:00', '2025-10-16 11:00:00'),
    (3, 3, 20251016, 5, 50.00, 250.00, 25.00, 18.00, '2025-10-16 12:00:00', '2025-10-16 12:00:00')
ON CONFLICT (sales_id) DO NOTHING;

INSERT INTO source.dim_customer (customer_id, customer_key, customer_name, email, country, segment, extract_timestamp)
VALUES
    (1, 'CUST-001', 'Test Customer 1', 'test1@example.com', 'USA', 'Enterprise', CURRENT_TIMESTAMP),
    (2, 'CUST-002', 'Test Customer 2', 'test2@example.com', 'Canada', 'SMB', CURRENT_TIMESTAMP),
    (3, 'CUST-003', 'Test Customer 3', 'test3@example.com', 'UK', 'Consumer', CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Record this migration
INSERT INTO warehouse.schema_migrations (migration_name, description)
VALUES ('003_source_schema', 'Source schema for raw data staging with sales_transactions and dim_customer')
ON CONFLICT (migration_name) DO NOTHING;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Source schema created successfully';
    RAISE NOTICE 'Tables created: sales_transactions, dim_customer';
    RAISE NOTICE 'Sample data inserted for testing';
END $$;
