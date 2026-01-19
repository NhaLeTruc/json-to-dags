-- ============================================================================
-- Migration: 001 - Initial Schema
-- ============================================================================
-- Description: Create initial warehouse schema with dimensions and facts
-- Author: Airflow ETL Demo Team
-- Date: 2025-10-15
-- Version: 1.0.0
-- Idempotent: Yes - safe to re-run
-- ============================================================================

-- This migration creates the foundational warehouse structure
-- Run this migration first before any other migrations

-- See schema.sql for full table definitions
-- This file exists for migration tracking purposes

-- Ensure migration metadata table exists (also created by base schema)
CREATE TABLE IF NOT EXISTS warehouse.schema_migrations (
    migration_id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    checksum VARCHAR(64)
);

-- Record this migration (idempotent)
INSERT INTO warehouse.schema_migrations (migration_name, description)
VALUES ('001_initial_schema', 'Initial warehouse schema with dimensions, facts, and operational tables')
ON CONFLICT (migration_name) DO NOTHING;
