-- ============================================================================
-- Migration: 002 - ETL Metadata Schema
-- ============================================================================
-- Description: Create etl_metadata schema for ETL operational metadata
-- Author: Airflow ETL Demo Team
-- Date: 2025-10-23
-- Version: 1.0.0
-- Idempotent: Yes - safe to re-run
-- ============================================================================

-- Create ETL metadata schema
CREATE SCHEMA IF NOT EXISTS etl_metadata;

-- ============================================================================
-- ETL Metadata Tables
-- ============================================================================

-- Table: incremental_watermarks
-- Purpose: Track high water marks for incremental load patterns
CREATE TABLE IF NOT EXISTS etl_metadata.incremental_watermarks (
    watermark_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    watermark_value TIMESTAMP NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('success', 'failed', 'running')),
    records_processed INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incremental_watermarks_pipeline ON etl_metadata.incremental_watermarks(pipeline_name, table_name);
CREATE INDEX IF NOT EXISTS idx_incremental_watermarks_status ON etl_metadata.incremental_watermarks(status);
CREATE INDEX IF NOT EXISTS idx_incremental_watermarks_execution_date ON etl_metadata.incremental_watermarks(execution_date);

COMMENT ON TABLE etl_metadata.incremental_watermarks IS 'Tracks watermarks for incremental ETL loads';
COMMENT ON COLUMN etl_metadata.incremental_watermarks.watermark_value IS 'The high water mark timestamp for this load';
COMMENT ON COLUMN etl_metadata.incremental_watermarks.execution_date IS 'Airflow execution date for this run';

-- Table: scd_processing_log
-- Purpose: Track SCD Type 2 processing statistics
CREATE TABLE IF NOT EXISTS etl_metadata.scd_processing_log (
    log_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    execution_date DATE NOT NULL,
    new_records INTEGER DEFAULT 0,
    changed_records INTEGER DEFAULT 0,
    expired_records INTEGER DEFAULT 0,
    total_current_records INTEGER DEFAULT 0,
    processing_time_seconds INTEGER,
    status VARCHAR(50) NOT NULL CHECK (status IN ('success', 'failed', 'running')),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scd_processing_log_pipeline ON etl_metadata.scd_processing_log(pipeline_name, table_name);
CREATE INDEX IF NOT EXISTS idx_scd_processing_log_execution_date ON etl_metadata.scd_processing_log(execution_date);
CREATE INDEX IF NOT EXISTS idx_scd_processing_log_status ON etl_metadata.scd_processing_log(status);

COMMENT ON TABLE etl_metadata.scd_processing_log IS 'Tracks SCD Type 2 dimension processing statistics';
COMMENT ON COLUMN etl_metadata.scd_processing_log.new_records IS 'Number of new dimension records inserted';
COMMENT ON COLUMN etl_metadata.scd_processing_log.changed_records IS 'Number of changed dimension records (new versions created)';
COMMENT ON COLUMN etl_metadata.scd_processing_log.expired_records IS 'Number of expired dimension records (is_current set to false)';

-- Table: load_log
-- Purpose: Track ETL load execution and statistics
CREATE TABLE IF NOT EXISTS etl_metadata.load_log (
    load_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    load_type VARCHAR(50) NOT NULL CHECK (load_type IN ('full', 'incremental', 'delta', 'snapshot')),
    records_extracted INTEGER DEFAULT 0,
    records_loaded INTEGER DEFAULT 0,
    records_rejected INTEGER DEFAULT 0,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    status VARCHAR(50) NOT NULL CHECK (status IN ('success', 'failed', 'running', 'partial')),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_load_log_pipeline ON etl_metadata.load_log(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_load_log_execution_date ON etl_metadata.load_log(execution_date);
CREATE INDEX IF NOT EXISTS idx_load_log_status ON etl_metadata.load_log(status);
CREATE INDEX IF NOT EXISTS idx_load_log_start_time ON etl_metadata.load_log(start_time DESC);

COMMENT ON TABLE etl_metadata.load_log IS 'Tracks ETL pipeline execution and statistics';
COMMENT ON COLUMN etl_metadata.load_log.load_type IS 'Type of load: full, incremental, delta, or snapshot';
COMMENT ON COLUMN etl_metadata.load_log.records_rejected IS 'Number of records rejected due to quality issues';

-- Record this migration
INSERT INTO warehouse.schema_migrations (migration_name, description)
VALUES ('002_etl_metadata_schema', 'ETL metadata schema with watermarks, SCD logs, and load logs')
ON CONFLICT (migration_name) DO NOTHING;

-- Grant permissions to warehouse user
GRANT USAGE ON SCHEMA etl_metadata TO warehouse_user;
GRANT ALL PRIVILEGES ON SCHEMA etl_metadata TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA etl_metadata TO warehouse_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA etl_metadata TO warehouse_user;

-- Set default privileges for future tables in etl_metadata schema
ALTER DEFAULT PRIVILEGES IN SCHEMA etl_metadata GRANT ALL ON TABLES TO warehouse_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA etl_metadata GRANT ALL ON SEQUENCES TO warehouse_user;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'ETL metadata schema created successfully';
    RAISE NOTICE 'Tables created: incremental_watermarks, scd_processing_log, load_log';
END $$;
