# Architecture Documentation

This document provides comprehensive system architecture details for the Apache Airflow ETL Demo Platform, including component diagrams, data flows, integration points, and deployment architecture.

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow Architecture](#data-flow-architecture)
- [Integration Architecture](#integration-architecture)
- [Deployment Architecture](#deployment-architecture)
- [Network Architecture](#network-architecture)
- [Security Architecture](#security-architecture)
- [Scalability and Performance](#scalability-and-performance)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            User / Developer                                  │
│                    (Airflow UI, CLI, REST API)                              │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Airflow Core Components                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Webserver   │  │  Scheduler   │  │   Workers    │  │  Triggerer   │  │
│  │   (Flask)    │  │ (DAG Parser) │  │  (Executor)  │  │  (Async)     │  │
│  │   Port 8080  │  │              │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────┬────────────┬───────────────────┬─────────────────────────────┘
             │            │                   │
             ▼            ▼                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     Airflow Metadata Database                              │
│                    (PostgreSQL - Task State, DAG Runs)                     │
└────────────────────────────────────────────────────────────────────────────┘

             ┌────────────────────────────────┐
             │      DAG Execution Layer       │
             │  ┌──────────────────────────┐  │
             │  │   Custom Operators       │  │
             │  │  - Spark Operators       │  │
             │  │  - Quality Operators     │  │
             │  │  - Notification Ops      │  │
             │  └──────────────────────────┘  │
             └────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │    Spark     │  │ Notification │
│  Warehouse   │  │   Clusters   │  │   Services   │
│              │  │              │  │              │
│ - Dimensions │  │ - Standalone │  │ - Email      │
│ - Facts      │  │ - YARN       │  │ - MS Teams   │
│ - Staging    │  │ - Kubernetes │  │ - Telegram   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Design Principles

1. **Modularity**: Custom operators, hooks, and utilities are decoupled and reusable
2. **Configuration-Driven**: JSON-based DAG generation reduces code duplication
3. **Testability**: Comprehensive unit and integration tests (80%+ coverage)
4. **Observability**: Multi-channel notifications and structured logging
5. **Resilience**: Automatic retries, exponential backoff, and failure recovery
6. **Scalability**: Horizontal scaling via executor choice and worker pools

---

## Component Architecture

### Airflow Core Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AIRFLOW CORE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Webserver (Flask)                          │   │
│  │  - UI for DAG monitoring and manual triggers                    │   │
│  │  - REST API (Airflow 2.x+)                                      │   │
│  │  - Authentication & Authorization (RBAC)                        │   │
│  │  - Port: 8080                                                   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Scheduler                                  │   │
│  │  - Parses DAGs from dags/ directory                             │   │
│  │  - Schedules task execution based on cron/interval              │   │
│  │  - Monitors DAG runs and task states                            │   │
│  │  - Writes to metadata database                                  │   │
│  │  - DAG Parsing Interval: 30 seconds (default)                   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Executor (LocalExecutor)                   │   │
│  │  - Runs tasks in local subprocesses                             │   │
│  │  - Alternative: CeleryExecutor, KubernetesExecutor              │   │
│  │  - Parallelism: Configurable (default: 32)                      │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Metadata Database                          │   │
│  │  - PostgreSQL 13+ (recommended for production)                  │   │
│  │  - Stores DAG definitions, runs, task instances                 │   │
│  │  - Connection pool management                                   │   │
│  │  - Migrations handled via `airflow db upgrade`                  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Custom Component Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CUSTOM COMPONENTS (src/)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Operators (src/operators/)                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Spark Operators (spark/)                                    │ │ │
│  │  │  - SparkStandaloneOperator                                   │ │ │
│  │  │  - SparkYarnOperator                                         │ │ │
│  │  │  - SparkKubernetesOperator                                   │ │ │
│  │  │  - SparkJobMonitor (status checking)                         │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Quality Operators (quality/)                                │ │ │
│  │  │  - DataQualityCheckOperator (base)                           │ │ │
│  │  │  - SchemaValidationOperator                                  │ │ │
│  │  │  - CompletenessCheckOperator                                 │ │ │
│  │  │  - FreshnessCheckOperator                                    │ │ │
│  │  │  - UniquenessCheckOperator                                   │ │ │
│  │  │  - NullRateCheckOperator                                     │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Notification Operators (notifications/)                     │ │ │
│  │  │  - EmailNotificationOperator                                 │ │ │
│  │  │  - MSTeamsNotificationOperator                               │ │ │
│  │  │  - TelegramNotificationOperator                              │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Hooks (src/hooks/)                                               │ │
│  │  - PostgresWarehouseHook (database connectivity)                  │ │
│  │  - SparkClusterHook (multi-cluster support)                       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Utilities (src/utils/)                                           │ │
│  │  - logging_config.py (structured logging)                         │ │
│  │  - config_loader.py (JSON schema validation)                      │ │
│  │  - data_generator.py (mock data creation)                         │ │
│  │  - great_expectations_helper.py (GE integration)                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Warehouse Schema (src/warehouse/)                                │ │
│  │  - schema.sql (DDL for dimensions, facts, staging)                │ │
│  │  - seed_data.sql (initial data for demos)                         │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### DAG Generation Engine

```
┌───────────────────────────────────────────────────────────────────────┐
│                  DAG FACTORY (dags/factory/)                          │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  JSON Configuration (dags/config/)                              │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │  my_dag.json                                              │  │ │
│  │  │  {                                                        │  │ │
│  │  │    "dag_id": "my_sales_etl_v1",                           │  │ │
│  │  │    "schedule": "@daily",                                  │  │ │
│  │  │    "tasks": [                                             │  │ │
│  │  │      { "task_id": "extract", "operator": "...", ... }     │  │ │
│  │  │    ]                                                      │  │ │
│  │  │  }                                                        │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                            │                                          │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  JSON Schema Validator (dags/config/schemas/)                   │ │
│  │  - dag_schema.json (validates DAG structure)                    │ │
│  │  - task_schema.json (validates task definitions)                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                            │                                          │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  DAG Factory (dags/factory/dag_factory.py)                      │ │
│  │  1. Load JSON configuration                                     │ │
│  │  2. Validate against schema                                     │ │
│  │  3. Instantiate operators dynamically                           │ │
│  │  4. Set task dependencies                                       │ │
│  │  5. Create DAG object                                           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                            │                                          │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Generated DAGs (loaded by Airflow scheduler)                   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

### ETL Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          ETL PIPELINE FLOW                             │
└────────────────────────────────────────────────────────────────────────┘

1. EXTRACT Phase
   ┌─────────────────────────────────────────────────────────────┐
   │  Data Sources                                               │
   │  - External APIs (REST, SOAP)                               │
   │  - Databases (PostgreSQL, MySQL, Oracle)                    │
   │  - Files (CSV, JSON, Parquet) on S3/HDFS/Local             │
   │  - Streaming sources (Kafka topics)                         │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Extraction Operators                                       │
   │  - PostgresOperator (SQL queries)                           │
   │  - HttpOperator (API calls)                                 │
   │  - S3Operator / FileSensor (file retrieval)                 │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Staging Tables (warehouse.staging_*)                       │
   │  - Raw, unprocessed data                                    │
   │  - Extract timestamp recorded                               │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼

2. TRANSFORM Phase
   ┌─────────────────────────────────────────────────────────────┐
   │  Data Quality Checks (BEFORE transformation)                │
   │  - Schema validation                                        │
   │  - Completeness (null checks)                               │
   │  - Freshness (data recency)                                 │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Transformation Layer                                       │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  SQL-based Transform (PostgresOperator)             │   │
   │  │  - Joins, aggregations, window functions            │   │
   │  │  - Type casting, data normalization                 │   │
   │  └─────────────────────────────────────────────────────┘   │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  Spark-based Transform (SparkOperator)              │   │
   │  │  - Large-scale joins on distributed clusters        │   │
   │  │  - Complex aggregations, ML transformations         │   │
   │  └─────────────────────────────────────────────────────┘   │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Intermediate / Cleansed Tables                             │
   │  - Validated, transformed data ready for loading            │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼

3. LOAD Phase
   ┌─────────────────────────────────────────────────────────────┐
   │  Data Quality Checks (AFTER transformation)                 │
   │  - Uniqueness (duplicate detection)                         │
   │  - Business rule validation                                 │
   │  - Null rate checks                                         │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Load Strategy                                              │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  Full Load                                          │   │
   │  │  - TRUNCATE target table                            │   │
   │  │  - INSERT all transformed records                   │   │
   │  └─────────────────────────────────────────────────────┘   │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  Incremental Load                                   │   │
   │  │  - INSERT new records (based on watermark)          │   │
   │  │  - UPDATE changed records                           │   │
   │  └─────────────────────────────────────────────────────┘   │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  SCD Type 2 Load                                    │   │
   │  │  - Expire old records (set end_date)                │   │
   │  │  - INSERT new version with new start_date           │   │
   │  └─────────────────────────────────────────────────────┘   │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  Warehouse Tables                                           │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  Dimensions (warehouse.dim_*)                       │   │
   │  │  - dim_customer                                     │   │
   │  │  - dim_product                                      │   │
   │  │  - dim_date                                         │   │
   │  │  - dim_store                                        │   │
   │  └─────────────────────────────────────────────────────┘   │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │  Facts (warehouse.fact_*)                           │   │
   │  │  - fact_sales                                       │   │
   │  │  - fact_inventory                                   │   │
   │  └─────────────────────────────────────────────────────┘   │
   └─────────────────┬───────────────────────────────────────────┘
                     │
                     ▼

4. NOTIFY Phase
   ┌─────────────────────────────────────────────────────────────┐
   │  Notifications                                              │
   │  - Email: Success/Failure reports                           │
   │  - MS Teams: Pipeline status updates                        │
   │  - Telegram: Critical alerts                                │
   └─────────────────────────────────────────────────────────────┘
```

### XCom Data Passing

```
┌─────────────────────────────────────────────────────────────────┐
│                    XCom Data Flow                               │
└─────────────────────────────────────────────────────────────────┘

Task A                    Task B                    Task C
  │                         │                         │
  │ return {"count": 100}   │                         │
  ├────────────────────────►│                         │
  │    XCom push            │                         │
                            │ count = ti.xcom_pull()  │
                            │ # count = {"count":100} │
                            │                         │
                            │ return {"avg": 45.2}    │
                            ├────────────────────────►│
                            │    XCom push            │
                                                      │
                                                      │ data = ti.xcom_pull()
                                                      │ # data = {"avg": 45.2}

XCom Storage:
┌──────────────────────────────────────────────────┐
│  Airflow Metadata DB (xcom table)                │
│  - dag_id, task_id, execution_date               │
│  - key (default: 'return_value')                 │
│  - value (JSON serialized)                       │
│  - timestamp                                     │
└──────────────────────────────────────────────────┘

Note: XCom is best for small metadata (e.g., row counts, file paths).
      For large data, use external storage (S3, database tables).
```

---

## Integration Architecture

### External System Integration

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      INTEGRATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Apache Spark Clusters                                           │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │  │
│  │  │  Standalone    │  │  YARN          │  │  Kubernetes    │     │  │
│  │  │  - spark://    │  │  - yarn://     │  │  - k8s://      │     │  │
│  │  │    host:7077   │  │    resource    │  │    api-server  │     │  │
│  │  │  - Web UI:     │  │    manager     │  │  - Dynamic     │     │  │
│  │  │    8080        │  │  - Queue mgmt  │  │    pod alloc   │     │  │
│  │  └────────────────┘  └────────────────┘  └────────────────┘     │  │
│  │                                                                   │  │
│  │  Integration: SparkOperators submit jobs via REST API            │  │
│  │  Monitoring: Poll job status until completion                    │  │
│  │  Error Handling: Retry on transient failures                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Data Quality Framework (Great Expectations)                     │  │
│  │  - Expectation suites stored in dags/config/expectations/        │  │
│  │  - Validation results logged to XCom                             │  │
│  │  - Integration via great_expectations_helper.py                  │  │
│  │                                                                   │  │
│  │  Flow:                                                            │  │
│  │  1. Load expectation suite from JSON                             │  │
│  │  2. Validate dataset (DataFrame or SQL query)                    │  │
│  │  3. Parse results (success, warnings, failures)                  │  │
│  │  4. Trigger alerts on critical failures                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Notification Services                                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │  │
│  │  │  Email       │  │  MS Teams    │  │  Telegram    │           │  │
│  │  │  (SMTP)      │  │  (Webhook)   │  │  (Bot API)   │           │  │
│  │  │              │  │              │  │              │           │  │
│  │  │  - Host:     │  │  - POST to   │  │  - POST to   │           │  │
│  │  │    smtp.     │  │    webhook   │  │    api.      │           │  │
│  │  │    gmail.com │  │    URL       │  │    telegram  │           │  │
│  │  │  - Port: 587 │  │  - JSON      │  │  - Chat ID   │           │  │
│  │  │              │  │    payload   │  │    + token   │           │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │  │
│  │                                                                   │  │
│  │  Integration: Notification operators in src/operators/           │  │
│  │  Templates: Jinja2 templates for HTML/Markdown formatting        │  │
│  │  Retry Logic: Exponential backoff on delivery failures           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  File Storage Systems                                            │  │
│  │  - Local filesystem (for development)                            │  │
│  │  - S3 / MinIO (object storage)                                   │  │
│  │  - HDFS (Hadoop distributed filesystem)                          │  │
│  │                                                                   │  │
│  │  Integration: FileSensor for event-driven pipelines              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

### Local Development (Docker Compose)

```
┌──────────────────────────────────────────────────────────────────────┐
│                      LOCAL DEPLOYMENT                                │
│                     (docker-compose.yml)                             │
└──────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Host Machine (developer laptop)                                       │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  airflow-webserver                                               │ │
│  │  - Image: apache/airflow:2.8.0-python3.11                        │ │
│  │  - Port: 8080:8080                                               │ │
│  │  - Volumes: ./dags:/opt/airflow/dags                             │ │
│  │             ./src:/opt/airflow/src                               │ │
│  │  - Env: AIRFLOW__CORE__EXECUTOR=LocalExecutor                    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  airflow-scheduler                                               │ │
│  │  - Image: apache/airflow:2.8.0-python3.11                        │ │
│  │  - Volumes: ./dags:/opt/airflow/dags                             │ │
│  │             ./src:/opt/airflow/src                               │ │
│  │  - Depends on: postgres-metadata                                 │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  postgres-metadata (Airflow metadata DB)                         │ │
│  │  - Image: postgres:15                                            │ │
│  │  - Port: 5432:5432                                               │ │
│  │  - Volume: postgres-metadata-volume                              │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  postgres-warehouse (Mock data warehouse)                        │ │
│  │  - Image: postgres:15                                            │ │
│  │  - Port: 5433:5432                                               │ │
│  │  - Volume: postgres-warehouse-volume                             │ │
│  │  - Init Script: src/warehouse/schema.sql                         │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  spark-standalone (Optional)                                     │ │
│  │  - Image: bitnami/spark:3.5                                      │ │
│  │  - Port: 7077 (master), 8081 (web UI)                            │ │
│  │  - Workers: 2 (configurable)                                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘

Docker Network: airflow-network (bridge)
```

### Production Deployment (Kubernetes)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   PRODUCTION DEPLOYMENT (Kubernetes)                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                                     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Namespace: airflow-production                                    │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Deployment: airflow-webserver                              │ │ │
│  │  │  - Replicas: 2 (for HA)                                     │ │ │
│  │  │  - Resources: 1 CPU, 2Gi memory                             │ │ │
│  │  │  - Service: LoadBalancer (port 80 → 8080)                   │ │ │
│  │  │  - Ingress: airflow.example.com (HTTPS)                     │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  Deployment: airflow-scheduler                              │ │ │
│  │  │  - Replicas: 1 (single scheduler for consistency)           │ │ │
│  │  │  - Resources: 2 CPU, 4Gi memory                             │ │ │
│  │  │  - PersistentVolumeClaim: dags-pvc (shared with webserver)  │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  StatefulSet: airflow-workers (if CeleryExecutor)           │ │ │
│  │  │  - Replicas: 3-10 (autoscaling based on queue depth)        │ │ │
│  │  │  - Resources: 2 CPU, 4Gi memory each                        │ │ │
│  │  │  - Redis: Message broker for Celery                         │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  External Service: postgres-metadata                        │ │ │
│  │  │  - Managed PostgreSQL (AWS RDS, GCP CloudSQL, Azure DB)     │ │ │
│  │  │  - Multi-AZ for high availability                           │ │ │
│  │  │  - Automatic backups (daily)                                │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Namespace: data-warehouse                                        │ │
│  │  - PostgreSQL StatefulSet (or external RDS)                       │ │
│  │  - Persistent storage for warehouse data                          │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Namespace: spark                                                 │ │
│  │  - Spark on Kubernetes (native k8s executor)                      │ │
│  │  - Dynamic pod allocation                                         │ │
│  │  - Spark Operator for job management                              │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Ingress: NGINX or ALB (Application Load Balancer)
SSL/TLS: Cert-manager with Let's Encrypt
Monitoring: Prometheus + Grafana
Logging: ELK Stack or CloudWatch
```

---

## Network Architecture

### Network Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                        NETWORK ARCHITECTURE                           │
└───────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Internet / External Users                                          │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Load Balancer / Ingress Controller                                │
│  - SSL Termination (HTTPS)                                         │
│  - Rate Limiting                                                   │
│  - DDoS Protection                                                 │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DMZ / Public Subnet                                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Airflow Webserver (Port 8080)                               │  │
│  │  - Public-facing UI                                          │  │
│  │  - Authentication required (RBAC)                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Application Subnet (Private)                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Airflow Scheduler                                           │  │
│  │  - No direct internet access                                 │  │
│  │  - Communicates with metadata DB                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Airflow Workers (if Celery)                                 │  │
│  │  - Execute tasks                                             │  │
│  │  - Access to warehouse DB, Spark, external APIs             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Database Subnet (Private)                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Metadata DB (Port 5432)                          │  │
│  │  - Only accessible from Airflow components                   │  │
│  │  - Security groups restrict access                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Warehouse DB (Port 5432)                         │  │
│  │  - Accessible from workers only                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  External Integrations (via NAT Gateway)                            │
│  - Spark clusters (private VPC peering or VPN)                     │
│  - Email SMTP servers (TLS encrypted)                              │
│  - MS Teams webhooks (HTTPS)                                       │
│  - Telegram API (HTTPS)                                            │
└─────────────────────────────────────────────────────────────────────┘

Firewall Rules:
- Webserver: Inbound 8080 (HTTPS only), Outbound to metadata DB
- Scheduler: Outbound to metadata DB, workers, external services
- Workers: Outbound to warehouse DB, Spark, APIs
- Databases: Inbound 5432 (from Airflow subnet only)
```

---

## Security Architecture

### Security Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────┘

1. Authentication & Authorization
   ┌──────────────────────────────────────────────────────────────┐
   │  Airflow RBAC (Role-Based Access Control)                    │
   │  - Roles: Admin, User, Viewer, Op                            │
   │  - Permissions: can_read, can_edit, can_delete DAGs          │
   │  - Integration: LDAP, OAuth (Google, GitHub, Okta)           │
   └──────────────────────────────────────────────────────────────┘

2. Secrets Management
   ┌──────────────────────────────────────────────────────────────┐
   │  Airflow Connections & Variables                             │
   │  - Encrypted in metadata DB (Fernet key)                     │
   │  - External secrets backend (AWS Secrets Manager, Vault)     │
   │  - Never hardcode credentials in DAG files                   │
   └──────────────────────────────────────────────────────────────┘

3. Network Security
   ┌──────────────────────────────────────────────────────────────┐
   │  - SSL/TLS for all external communication                    │
   │  - VPC isolation (no direct internet access for workers)     │
   │  - Security groups / Network policies                        │
   │  - DDoS protection via CDN/WAF                               │
   └──────────────────────────────────────────────────────────────┘

4. Data Security
   ┌──────────────────────────────────────────────────────────────┐
   │  - Encryption at rest (database encryption)                  │
   │  - Encryption in transit (TLS for DB connections)            │
   │  - Data masking for PII in logs                              │
   │  - Audit trails for data access                              │
   └──────────────────────────────────────────────────────────────┘

5. Code Security
   ┌──────────────────────────────────────────────────────────────┐
   │  - Dependency scanning (safety check in CI/CD)               │
   │  - Static code analysis (ruff, bandit)                       │
   │  - No eval() or exec() in DAG code                           │
   │  - Input validation and sanitization                         │
   └──────────────────────────────────────────────────────────────┘

6. Operational Security
   ┌──────────────────────────────────────────────────────────────┐
   │  - Regular security patches and updates                      │
   │  - Log monitoring and alerting (failed auth attempts)        │
   │  - Backup and disaster recovery                              │
   │  - Incident response procedures                              │
   └──────────────────────────────────────────────────────────────┘
```

---

## Scalability and Performance

### Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SCALABILITY PATTERNS                           │
└─────────────────────────────────────────────────────────────────────┘

1. Executor Selection
   ┌──────────────────────────────────────────────────────────────┐
   │  LocalExecutor (Development)                                 │
   │  - Single machine                                            │
   │  - Parallelism limited by CPU cores                          │
   │  - Best for: Development, small workloads                    │
   └──────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────┐
   │  CeleryExecutor (Production)                                 │
   │  - Distributed workers                                       │
   │  - Auto-scaling based on queue depth                         │
   │  - Best for: High throughput, variable workloads             │
   └──────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────┐
   │  KubernetesExecutor (Cloud-native)                           │
   │  - Dynamic pod creation per task                             │
   │  - Auto-scaling via Kubernetes HPA                           │
   │  - Best for: Kubernetes environments, resource isolation     │
   └──────────────────────────────────────────────────────────────┘

2. DAG Parsing Optimization
   ┌──────────────────────────────────────────────────────────────┐
   │  - Reduce top-level Python code execution                    │
   │  - Use dynamic task generation sparingly                     │
   │  - Increase DAG_DIR_LIST_INTERVAL (default: 30s)             │
   │  - Use .airflowignore to skip non-DAG files                  │
   └──────────────────────────────────────────────────────────────┘

3. Database Performance
   ┌──────────────────────────────────────────────────────────────┐
   │  - Connection pooling (default: 5 connections)               │
   │  - Regular VACUUM and ANALYZE on PostgreSQL                  │
   │  - Purge old task instances (retention policy)               │
   │  - Index optimization on dag_run, task_instance tables       │
   └──────────────────────────────────────────────────────────────┘

4. Task-Level Optimization
   ┌──────────────────────────────────────────────────────────────┐
   │  - Use TaskGroups to organize tasks logically                │
   │  - Set appropriate pool sizes for resource-heavy tasks       │
   │  - Use SubDAGs sparingly (prefer TaskGroups)                 │
   │  - Parallelize independent tasks                             │
   └──────────────────────────────────────────────────────────────┘
```

### Performance Metrics

| Metric | Development | Production Target |
|--------|-------------|-------------------|
| DAG Parsing Time | <5s per DAG | <2s per DAG |
| Scheduler Latency | <30s | <10s |
| Task Throughput | 10-50 tasks/min | 100-500 tasks/min |
| Webserver Response | <500ms | <200ms |
| Database Connections | <10 | <50 (pooled) |
| Worker Memory | 512Mi-1Gi | 2Gi-4Gi |

---

## Monitoring and Observability

### Observability Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────┘

1. Metrics (Prometheus + Grafana)
   ┌──────────────────────────────────────────────────────────────┐
   │  Airflow StatsD Exporter → Prometheus                        │
   │  - DAG run duration (P50, P95, P99)                          │
   │  - Task success/failure rates                                │
   │  - Scheduler lag                                             │
   │  - Worker CPU/memory usage                                   │
   │  - Database connection pool metrics                          │
   │                                                              │
   │  Grafana Dashboards:                                         │
   │  - DAG overview (success rate, duration trends)              │
   │  - Task-level metrics                                        │
   │  - Infrastructure health (CPU, memory, disk)                 │
   └──────────────────────────────────────────────────────────────┘

2. Logging (ELK Stack or CloudWatch)
   ┌──────────────────────────────────────────────────────────────┐
   │  Airflow Logs → Elasticsearch → Kibana                       │
   │  - Structured JSON logging                                   │
   │  - Centralized log aggregation                               │
   │  - Full-text search across all task logs                     │
   │  - Retention policy: 90 days                                 │
   └──────────────────────────────────────────────────────────────┘

3. Tracing (Jaeger / OpenTelemetry)
   ┌──────────────────────────────────────────────────────────────┐
   │  DAG → Task → Operator → Hook                                │
   │  - Distributed tracing for task execution                    │
   │  - Identify bottlenecks in multi-step pipelines              │
   └──────────────────────────────────────────────────────────────┘

4. Alerting (PagerDuty, Slack)
   ┌──────────────────────────────────────────────────────────────┐
   │  - DAG failure alerts (critical pipelines)                   │
   │  - SLA miss alerts                                           │
   │  - Database connection failures                              │
   │  - Worker pod crashes                                        │
   └──────────────────────────────────────────────────────────────┘
```

---

## Summary

This architecture document provides a comprehensive overview of the Apache Airflow ETL Demo Platform:

- **Component Architecture**: Modular design with custom operators, hooks, and utilities
- **Data Flow**: Extract → Transform → Load with quality checks at each stage
- **Integration**: Spark clusters, Great Expectations, multi-channel notifications
- **Deployment**: Docker Compose for local dev, Kubernetes for production
- **Network**: Secure multi-tier architecture with DMZ, app, and database subnets
- **Security**: RBAC, secrets management, encryption, and audit trails
- **Scalability**: Horizontal scaling via CeleryExecutor or KubernetesExecutor
- **Observability**: Prometheus metrics, centralized logging, distributed tracing

For implementation details, refer to:
- [Operator Guide](operator_guide.md) - Custom operator usage
- [DAG Configuration Guide](dag_configuration.md) - JSON schema reference
- [CI/CD Pipeline](ci_cd_pipeline.md) - Deployment automation
- [Development Guide](development.md) - Local setup and contribution

---

**Last Updated**: 2025-10-21
**Maintained By**: Platform Team