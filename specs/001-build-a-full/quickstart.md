# Quickstart Guide: Apache Airflow ETL Demo Platform

**Last Updated**: 2025-10-21
**Branch**: `001-build-a-full`

## Overview

This quickstart guide provides step-by-step instructions to get the Apache Airflow ETL Demo Platform running locally in under 15 minutes. By the end, you'll have a fully functional Airflow environment with example DAGs, custom operators, and a mock data warehouse.

---

## Prerequisites

**Required**:
- Docker Engine 20.10+ and Docker Compose 2.0+
- Git 2.30+
- 8 GB RAM available for containers
- 20 GB free disk space

**Optional**:
- Python 3.11+ for local development (not required for Docker-only usage)
- Visual Studio Code or similar editor

**Platform Support**:
- Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+)
- macOS (12.0+)
- Windows (with WSL2)

---

## Quick Start (5 minutes)

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/apache-airflow-etl-demo.git
cd apache-airflow-etl-demo
```

### Step 2: Start the Environment

```bash
# Copy environment template
cp .env.example .env

# Start all services (Airflow, PostgreSQL, mock warehouse)
docker compose up -d

# Wait for services to be healthy (usually 2-3 minutes)
docker compose ps
```

**Expected Output**:
```
NAME                    STATUS          PORTS
airflow-webserver       Up (healthy)    0.0.0.0:8080->8080/tcp
airflow-scheduler       Up (healthy)
airflow-warehouse      Up (healthy)    0.0.0.0:5432->5432/tcp
```

### Step 3: Access Airflow UI

Open your browser to: **http://localhost:8080**

**Default Credentials**:
- Username: `admin`
- Password: `admin` (change in `.env` for production use)

### Step 4: Trigger Example DAG

1. In Airflow UI, navigate to the **DAGs** page
2. Find DAG `demo_simple_extract_load_v1`
3. Toggle the DAG to "On" (switch on the left)
4. Click the ▶️ (Play) button → "Trigger DAG"
5. Watch the DAG run complete (usually under 30 seconds)

**Success Indicator**: All tasks turn dark green ✅

---

## Detailed Setup

### Environment Configuration

Edit `.env` file to customize settings:

```bash
# Airflow Configuration
AIRFLOW_UID=50000
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True

# PostgreSQL Warehouse
POSTGRES_USER=warehouse_user
POSTGRES_PASSWORD=warehouse_pass
POSTGRES_DB=warehouse

# SMTP (for email notifications - optional)
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password

# MS Teams Webhook (optional)
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/your-webhook-url

# Telegram Bot (optional)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=your-chat-id
```

### Service Health Check

Verify all services are running correctly:

```bash
# Check service status
docker compose ps

# View logs for troubleshooting
docker compose logs airflow-webserver
docker compose logs airflow-scheduler
docker compose logs airflow-warehouse

# Check Airflow scheduler is processing DAGs
docker compose logs -f airflow-scheduler | grep "DAG bag size"
```

**Expected Log Output**:
```
scheduler  | DAG bag size: 15
scheduler  | Loaded 15 DAGs from dags/ folder
```

### Initial Data Setup

The mock data warehouse is automatically initialized on first startup with:
- 1,000 customers (DimCustomer)
- 500 products (DimProduct)
- 5 years of dates (DimDate)
- 100,000 historical sales (FactSales)

**Verify Data Loading**:

```bash
# Connect to warehouse database
docker exec -it airflow-warehouse psql -U warehouse_user -d warehouse

# Check table counts
SELECT 'customers' as table_name, COUNT(*) FROM warehouse.dim_customer
UNION ALL
SELECT 'products', COUNT(*) FROM warehouse.dim_product
UNION ALL
SELECT 'sales', COUNT(*) FROM warehouse.fact_sales;

# Exit psql
\q
```

---

## Exploring Example DAGs

### DAG Categories

The platform includes 14 example DAGs organized by complexity:

**Beginner** (`dags/examples/beginner/`):
1. `demo_simple_extract_load_v1` - Basic data extraction and loading
2. `demo_scheduled_pipeline_v1` - Daily scheduled ETL with retry logic
3. `demo_data_quality_basics_v1` - Schema validation and completeness checks
4. `demo_notification_basics_v1` - Email and Teams notifications

**Intermediate** (`dags/examples/intermediate/`):
5. `demo_incremental_load_v1` - Incremental data extraction with watermarks
6. `demo_scd_type2_v1` - Slowly Changing Dimension Type 2 implementation
7. `demo_parallel_processing_v1` - Parallel task execution patterns
8. `demo_spark_standalone_v1` - Spark job submission to standalone cluster
9. `demo_cross_dag_dependency_v1` - DAG triggering and dependencies

**Advanced** (`dags/examples/advanced/`):
10. `demo_spark_multi_cluster_v1` - Spark jobs across standalone, YARN, K8s
11. `demo_comprehensive_quality_v1` - Full data quality validation suite
12. `demo_event_driven_pipeline_v1` - Sensor-based event-driven workflow
13. `demo_failure_recovery_v1` - Failure handling and compensation logic

### Running a Specific DAG

**Via Airflow UI**:
1. Go to DAGs page
2. Enable the DAG (toggle switch)
3. Click the ▶️ button → "Trigger DAG"
4. Monitor execution in Graph or Grid view

**Via Airflow CLI** (inside container):
```bash
# Enter Airflow scheduler container
docker exec -it airflow-scheduler bash

# Trigger DAG manually
airflow dags trigger demo_simple_extract_load_v1

# Check DAG run status
airflow dags list-runs -d demo_simple_extract_load_v1

# Test a specific task without running full DAG
airflow tasks test demo_simple_extract_load_v1 extract_sales_data 2025-10-15
```

### Understanding DAG Structure

Example: `demo_simple_extract_load_v1`

```
extract_sales_data (PostgresOperator)
       ↓
validate_schema (SchemaValidationOperator)
       ↓
load_to_staging (PostgresOperator)
       ↓
send_success_notification (EmailNotificationOperator)
```

**View DAG Code**:
- Location: `dags/examples/beginner/demo_simple_extract_load_v1.py`
- Alternatively: Click DAG name in UI → "Code" tab

---

## Creating Your First DAG with JSON Configuration

### Step 1: Create JSON Configuration File

Create `dags/config/my_first_dag.json`:

```json
{
  "dag_id": "my_sales_report_v1",
  "description": "My first DAG using JSON configuration",
  "schedule": "@daily",
  "catchup": false,
  "tags": ["custom", "learning"],
  "default_args": {
    "owner": "your-name@example.com",
    "retries": 2,
    "retry_delay": 300
  },
  "tasks": [
    {
      "task_id": "extract_daily_sales",
      "operator": "PostgresOperator",
      "parameters": {
        "sql": "SELECT * FROM warehouse.fact_sales WHERE sale_date = '{{ ds }}'",
        "postgres_conn_id": "warehouse"
      }
    },
    {
      "task_id": "check_data_quality",
      "operator": "CompletenessCheckOperator",
      "parameters": {
        "table": "warehouse.fact_sales",
        "min_row_count": 100,
        "severity": "WARNING"
      },
      "upstream_tasks": ["extract_daily_sales"]
    },
    {
      "task_id": "send_report",
      "operator": "EmailNotificationOperator",
      "parameters": {
        "to": "your-email@example.com",
        "subject": "Daily Sales Report for {{ ds }}",
        "body": "Daily sales ETL completed successfully. Check Airflow UI for details."
      },
      "upstream_tasks": ["check_data_quality"]
    }
  ]
}
```

### Step 2: Validate Configuration

```bash
# Validate JSON syntax
docker exec airflow-scheduler python -c "
import json
with open('/opt/airflow/dags/config/my_first_dag.json') as f:
    config = json.load(f)
    print(f'Valid JSON: {config[\"dag_id\"]}')
"

# Wait for DAG to appear (up to 30 seconds for scheduler refresh)
# Or restart scheduler to force reload
docker compose restart airflow-scheduler
```

### Step 3: Verify DAG Appears in UI

1. Refresh Airflow UI (http://localhost:8080)
2. Look for `my_sales_report_v1` in DAG list
3. Enable and trigger the DAG
4. Monitor execution in Graph view

**Troubleshooting**:
- Check scheduler logs: `docker-compose logs airflow-scheduler | grep ERROR`
- Verify JSON is valid using online validator
- Ensure all referenced operators are registered

---

## Running Tests

### Unit Tests

```bash
# Run all unit tests with coverage
docker exec airflow-scheduler pytest tests/unit/ \
    --cov=src --cov=dags/factory --cov-report=term-missing

# Run specific test file
docker exec airflow-scheduler pytest tests/unit/test_operators/test_spark_operators.py -v

# Run tests matching pattern
docker exec airflow-scheduler pytest tests/unit/ -k "quality" -v
```

**Expected Coverage**: 80%+ for all custom operators and utility functions.

### Integration Tests

```bash
# Run integration tests (slower, requires running services)
docker exec airflow-scheduler pytest tests/integration/ -v

# Test DAG parsing
docker exec airflow-scheduler pytest tests/integration/test_dag_parsing.py -v

# Test DAG execution end-to-end
docker exec airflow-scheduler pytest tests/integration/test_dag_execution.py -v
```

**Expected Duration**: 5-10 minutes for full integration suite.

### DAG Validation Tests

```bash
# Validate all DAGs can be parsed without errors
docker exec airflow-scheduler python -c "
from airflow.models import DagBag
dag_bag = DagBag(dag_folder='/opt/airflow/dags', include_examples=False)
print(f'DAGs loaded: {len(dag_bag.dags)}')
print(f'Import errors: {len(dag_bag.import_errors)}')
if dag_bag.import_errors:
    print(dag_bag.import_errors)
"
```

**Expected Output**: 0 import errors, 14 DAGs loaded.

---

## Monitoring and Debugging

### View DAG Run Logs

**Airflow UI**:
1. Click DAG name → Grid view
2. Click on task instance (green/red square)
3. Click "Log" button
4. View task execution logs

**CLI**:
```bash
# View task logs
docker exec airflow-scheduler airflow tasks logs \
    demo_simple_extract_load_v1 extract_sales_data 2025-10-15

# Follow live logs
docker compose logs -f airflow-scheduler
```

### Check Data Quality Results

```bash
# Query quality check history
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "
SELECT
    dag_id,
    task_id,
    table_name,
    check_type,
    severity,
    passed,
    failure_rate
FROM warehouse.quality_check_results
ORDER BY created_at DESC
LIMIT 10;
"
```

### Monitor Spark Job Submissions

```bash
# View Spark job submission history
docker exec airflow-warehouse psql -U warehouse_user -d warehouse -c "
SELECT
    dag_id,
    cluster_type,
    status,
    duration_seconds,
    submitted_at
FROM warehouse.spark_job_submissions
ORDER BY submitted_at DESC
LIMIT 10;
"
```

---

## Common Operations

### Pause/Unpause DAG

**UI**: Toggle switch next to DAG name

**CLI**:
```bash
# Pause DAG
docker exec airflow-scheduler airflow dags pause my_sales_report_v1

# Unpause DAG
docker exec airflow-scheduler airflow dags unpause my_sales_report_v1
```

### Clear Failed Task and Re-run

**UI**:
1. Click on failed task instance (red square)
2. Click "Clear" button
3. Confirm clear
4. Task will automatically re-run

**CLI**:
```bash
docker exec airflow-scheduler airflow tasks clear \
    my_sales_report_v1 check_data_quality \
    --start-date 2025-10-15 --end-date 2025-10-15
```

### Backfill Historical Runs

```bash
# Backfill DAG for date range
docker exec airflow-scheduler airflow dags backfill \
    my_sales_report_v1 \
    --start-date 2025-10-01 \
    --end-date 2025-10-14
```

### Reset Environment to Clean State

```bash
# Stop all services and remove volumes (DELETES ALL DATA)
docker compose down -v

# Restart with fresh state
docker compose up -d

# Wait for services to initialize
sleep 120
```

---

## Next Steps

### Learn More

- **Architecture**: Read `docs/architecture.md` for system design details
- **DAG Configuration**: See `docs/dag_configuration.md` for JSON schema reference
- **Custom Operators**: Check `docs/operator_guide.md` for operator development
- **CI/CD Pipeline**: Review `docs/ci_cd_pipeline.md` for deployment automation
- **Development**: Follow `docs/development.md` for local Python development setup

### Customize for Your Use Case

1. **Add New Operators**: Extend `src/operators/` with custom logic
2. **Create DAG Templates**: Build reusable DAG patterns in `dags/factory/`
3. **Integrate Real Data Sources**: Replace mock warehouse with actual database connections
4. **Add Business Logic**: Implement domain-specific transformations in Spark jobs

### Deploy to Production

1. **Review Security**: Update credentials, enable RBAC, configure HTTPS
2. **Choose Executor**: Switch to CeleryExecutor or KubernetesExecutor for scalability
3. **Setup Monitoring**: Integrate with Prometheus, Grafana, or cloud monitoring
4. **Implement CI/CD**: Use `.github/workflows/` for automated deployment

---

## Troubleshooting

### Issue: Airflow UI not accessible

**Symptoms**: Browser cannot connect to http://localhost:8080

**Solutions**:
```bash
# Check if webserver is running
docker compose ps airflow-webserver

# Check logs for errors
docker compose logs airflow-webserver | tail -50

# Verify port 8080 is not in use by another service
lsof -i :8080  # macOS/Linux
netstat -ano | findstr :8080  # Windows

# Restart webserver
docker compose restart airflow-webserver
```

---

### Issue: DAG not appearing in UI

**Symptoms**: New DAG file or JSON config not visible after 30+ seconds

**Solutions**:
```bash
# Check for DAG parsing errors
docker exec airflow-scheduler python -c "
from airflow.models import DagBag
dag_bag = DagBag(dag_folder='/opt/airflow/dags')
print(dag_bag.import_errors)
"

# Verify file is in correct location
docker exec airflow-scheduler ls -la /opt/airflow/dags/config/

# Force scheduler to reprocess DAGs
docker compose restart airflow-scheduler
```

---

### Issue: Task fails with "Connection not found"

**Symptoms**: Tasks fail with error "Connection 'warehouse' doesn't exist"

**Solutions**:
```bash
# Create missing connection via CLI
docker exec airflow-scheduler airflow connections add warehouse \
    --conn-type postgres \
    --conn-host airflow-warehouse \
    --conn-login warehouse_user \
    --conn-password warehouse_pass \
    --conn-schema warehouse \
    --conn-port 5432

# Or create via UI: Admin → Connections → Add
```

---

### Issue: Out of disk space

**Symptoms**: Services fail to start or crash unexpectedly

**Solutions**:
```bash
# Check disk usage
df -h

# Clean up Docker resources
docker system prune -a --volumes

# Remove old Airflow logs (inside scheduler container)
docker exec airflow-scheduler find /opt/airflow/logs -type f -mtime +7 -delete
```

---

## Support and Resources

- **GitHub Issues**: [Report bugs or request features](https://github.com/your-org/apache-airflow-etl-demo/issues)
- **Documentation**: Full docs in `docs/` directory
- **Airflow Official Docs**: https://airflow.apache.org/docs/
- **Community Slack**: #airflow channel in Apache Slack

---

**Congratulations!** You now have a fully functional Apache Airflow ETL demo platform running locally. Start exploring the example DAGs, create custom configurations, and adapt the platform for your data engineering needs.
