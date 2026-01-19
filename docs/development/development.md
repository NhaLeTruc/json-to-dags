# Local Development Guide

Complete guide for setting up and working with the Apache Airflow ETL Demo Platform locally.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Common Tasks](#common-tasks)
- [Architecture Overview](#architecture-overview)

---

## Prerequisites

### Required Software

1. **Docker** (version 20.10 or higher)
   - [Install Docker](https://docs.docker.com/get-docker/)
   - Verify: `docker --version`

2. **Docker Compose** (version 2.0 or higher)
   - Included with Docker Desktop on Mac/Windows
   - Linux: [Install Docker Compose](https://docs.docker.com/compose/install/)
   - Verify: `docker compose version`

3. **Git**
   - [Install Git](https://git-scm.com/downloads)
   - Verify: `git --version`

### System Requirements

- **RAM**: Minimum 4GB available (8GB recommended)
- **Disk Space**: Minimum 10GB free space
- **CPU**: 2+ cores recommended
- **OS**: Linux, macOS, or Windows with WSL2

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd claude-airflow-etl
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` if you need to customize any settings (optional for local development).

### 3. Start the Environment

```bash
# Build and start all services
docker compose up -d

# View logs
docker compose logs -f
```

### 4. Wait for Services to Initialize

The first startup takes 2-5 minutes while services initialize:

- Airflow database migration
- Admin user creation
- DAG parsing
- Health checks

### 5. Validate Environment

```bash
# Run validation script
./scripts/validate_environment.sh
```

### 6. Access Airflow UI

Open your browser to: **http://localhost:8080**

- **Username**: `admin`
- **Password**: `admin`

### 7. Verify DAGs Loaded

In the Airflow UI, you should see example DAGs:

- `simple_extract_load_v1` (from JSON config)
- `demo_scheduled_pipeline_v1` (scheduled ETL)
- `demo_failure_recovery_v1` (failure handling)

---

## Development Workflow

### Working with DAGs

The `dags/` directory is mounted into the containers, enabling **hot-reload**:

1. **Edit a DAG file** in your editor
2. **Wait 30 seconds** (DAG refresh interval in dev mode)
3. **Refresh the Airflow UI** to see changes

No container restart needed!

### Project Structure

```
claude-airflow-etl/
├── dags/                    # Airflow DAG definitions
│   ├── config/              # JSON DAG configurations
│   │   ├── schemas/         # JSON schemas
│   │   └── examples/        # Example configs
│   ├── factory/             # Dynamic DAG generation
│   └── examples/            # Example DAGs
│       ├── beginner/        # Beginner examples
│       └── advanced/        # Advanced examples
├── src/                     # Source code
│   ├── utils/               # Utility modules
│   ├── warehouse/           # Warehouse setup
│   └── operators/           # Custom operators
├── tests/                   # Test suite
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docker/                  # Dockerfiles
│   ├── airflow/             # Airflow container
│   └── warehouse/           # Warehouse container
├── logs/                    # Airflow logs (auto-created)
├── plugins/                 # Airflow plugins
└── data/                    # Data files
```

### Creating a New DAG

#### Option 1: JSON Configuration (Recommended)

1. Create a JSON file in `dags/config/examples/`:

```json
{
  "dag_id": "my_pipeline_v1",
  "description": "My custom pipeline",
  "schedule_interval": "0 3 * * *",
  "start_date": "2024-01-01",
  "tags": ["custom", "etl"],
  "default_args": {
    "owner": "data_team",
    "retries": 2,
    "retry_delay": 60
  },
  "tasks": [
    {
      "task_id": "extract",
      "operator_type": "bash",
      "params": {
        "bash_command": "echo 'Extracting data...'"
      }
    },
    {
      "task_id": "transform",
      "operator_type": "bash",
      "params": {
        "bash_command": "echo 'Transforming data...'"
      },
      "dependencies": ["extract"]
    }
  ]
}
```

2. Wait 30 seconds for auto-discovery
3. Refresh Airflow UI - your DAG appears automatically!

See [DAG Configuration Guide](dag_configuration.md) for complete documentation.

#### Option 2: Python DAG

Create a Python file in `dags/`:

```python
from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="my_custom_dag",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
) as dag:
    task = BashOperator(
        task_id="my_task",
        bash_command="echo 'Hello World'"
    )
```

### Accessing the Warehouse

The warehouse PostgreSQL database is exposed on port **5433**:

```bash
# Connect using psql
docker exec -it airflow-warehouse psql -U warehouse_user -d warehouse

# Or from host (if psql installed)
psql -h localhost -p 5433 -U warehouse_user -d warehouse
# Password: warehouse_pass
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f airflow-scheduler
docker compose logs -f airflow-webserver

# Airflow task logs (in UI or logs/ directory)
ls -la logs/
```

### Restarting Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart airflow-scheduler

# Rebuild and restart (after code changes)
docker compose up -d --build
```

---

## Testing

### Running Tests in Docker

The recommended way to run tests is inside the Docker container (Python 3.11):

```bash
# Run all tests
docker compose exec airflow-scheduler pytest tests/ -v

# Run specific test file
docker compose exec airflow-scheduler pytest tests/unit/test_retry_policies.py -v

# Run with coverage
docker compose exec airflow-scheduler pytest tests/ --cov=src --cov-report=html

# Run only unit tests
docker compose exec airflow-scheduler pytest tests/unit/ -v

# Run only integration tests
docker compose exec airflow-scheduler pytest tests/integration/ -v -m integration
```

### Test Markers

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests requiring Docker
- `@pytest.mark.slow` - Long-running tests

### Running Linters

```bash
# Ruff (linting and formatting)
docker compose exec airflow-scheduler ruff check .

# Type checking with mypy
docker compose exec airflow-scheduler mypy src/
```

See [Testing Guide](../TESTING.md) for comprehensive testing documentation.

---

## Troubleshooting

### Services Won't Start

**Problem**: `docker compose up` fails or services crash

**Solutions**:

1. Check Docker resource limits (increase RAM to 4GB+)
2. Ensure ports 8080 and 5433 are available:
   ```bash
   lsof -i:8080
   lsof -i:5433
   ```
3. Check logs for errors:
   ```bash
   docker compose logs airflow-init
   ```
4. Try clean restart:
   ```bash
   docker compose down -v
   docker compose up -d
   ```

### DAGs Not Appearing in UI

**Problem**: DAGs don't show up after 30 seconds

**Solutions**:

1. Check DAG file for syntax errors:
   ```bash
   docker compose exec airflow-scheduler python /opt/airflow/dags/your_dag.py
   ```
2. Check scheduler logs:
   ```bash
   docker compose logs -f airflow-scheduler
   ```
3. Force DAG refresh in UI: Admin > Configuration > Trigger Scheduler
4. For JSON DAGs, validate JSON syntax:
   ```bash
   cat dags/config/examples/your_dag.json | jq .
   ```

### Database Connection Errors

**Problem**: "Can't connect to database" errors

**Solutions**:

1. Wait for health checks to pass (check `docker compose ps`)
2. Verify database is running:
   ```bash
   docker exec airflow-postgres pg_isready -U airflow
   docker exec airflow-warehouse pg_isready -U warehouse_user -d warehouse
   ```
3. Check connection string in `.env` file
4. Restart services:
   ```bash
   docker compose restart airflow-webserver airflow-scheduler
   ```

### Permission Errors

**Problem**: Permission denied errors in logs

**Solutions**:

1. Set AIRFLOW_UID in `.env`:
   ```bash
   echo "AIRFLOW_UID=$(id -u)" >> .env
   ```
2. Fix directory permissions:
   ```bash
   sudo chown -R $(id -u):$(id -g) logs/ plugins/ data/
   ```
3. Restart services:
   ```bash
   docker compose down
   docker compose up -d
   ```

### Slow Performance

**Problem**: Airflow UI is slow or tasks take long to start

**Solutions**:

1. Increase Docker resource limits (RAM, CPU)
2. Check disk space: `df -h`
3. Reduce DAG parsing frequency (in production mode)
4. Check for heavy DAG files (large data files)

### Clean Reset

**Problem**: Environment is corrupted or behaving unexpectedly

**Solution**: Complete reset (⚠️ destroys all data):

```bash
# Stop and remove everything
docker compose down -v

# Remove all containers, volumes, and networks
docker system prune -a --volumes

# Start fresh
docker compose up -d
```

---

## Common Tasks

### Adding Python Dependencies

1. **Edit** `requirements.txt`
2. **Rebuild** containers:
   ```bash
   docker compose down
   docker compose up -d --build
   ```

### Creating Custom Operators

1. Create operator in `src/operators/`:
   ```python
   from airflow.models import BaseOperator

   class MyCustomOperator(BaseOperator):
       def execute(self, context):
           # Your logic here
           pass
   ```

2. Register in `dags/factory/operator_registry.py`:
   ```python
   registry.register_operator("my_custom", MyCustomOperator)
   ```

3. Use in JSON DAG:
   ```json
   {
     "operator_type": "my_custom",
     "params": {...}
   }
   ```

### Accessing Container Shell

```bash
# Scheduler container (primary Airflow service)
docker compose exec airflow-scheduler bash

# Webserver container
docker compose exec airflow-webserver bash

# Warehouse database
docker compose exec airflow-warehouse bash
```

### Backing Up Data

```bash
# Export warehouse data
docker exec airflow-warehouse pg_dump -U warehouse_user warehouse > backup.sql

# Export Airflow metadata
docker exec airflow-postgres pg_dump -U airflow airflow > airflow_backup.sql

# Restore
docker exec -i airflow-warehouse psql -U warehouse_user warehouse < backup.sql
```

### Updating Airflow Version

1. Edit `requirements.txt`:
   ```
   apache-airflow==2.9.0  # Update version
   ```

2. Rebuild:
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```

3. Verify:
   ```bash
   docker compose exec airflow-scheduler airflow version
   ```

### Checking Service Health

```bash
# View service status
docker compose ps

# Check health of all services
docker inspect airflow-postgres airflow-warehouse airflow-webserver airflow-scheduler \
  --format='{{.Name}}: {{.State.Health.Status}}'

# Run validation script
./scripts/validate_environment.sh
```

---

## Architecture Overview

### Services

| Service | Description | Port | Health Check |
|---------|-------------|------|--------------|
| `airflow-postgres` | Airflow metadata database | - | `pg_isready` |
| `airflow-warehouse` | Mock data warehouse | 5433 | `pg_isready` |
| `airflow-init` | One-time initialization | - | Exits after completion |
| `airflow-webserver` | Airflow web UI | 8080 | HTTP `/health` |
| `airflow-scheduler` | DAG scheduler and executor | - | Airflow jobs check |

### Volumes

| Volume | Purpose | Lifecycle |
|--------|---------|-----------|
| `airflow-postgres-data` | Airflow metadata | Persists until `down -v` |
| `airflow-warehouse-data` | Warehouse data | Persists until `down -v` |
| `./dags` | DAG files (bind mount) | Host filesystem |
| `./src` | Source code (bind mount) | Host filesystem |
| `./logs` | Airflow logs (bind mount) | Host filesystem |

### Networks

- `airflow-network` - Internal bridge network for service communication

### Environment Modes

**Development Mode** (default with `docker-compose.override.yml`):
- Debug logging
- Fast DAG refresh (30s)
- No automatic restarts
- Example DAGs disabled

**Production Mode** (without override):
- Info logging
- Standard refresh intervals
- Automatic restarts
- Optimized settings

To use production mode:
```bash
docker compose -f docker-compose.yml up -d
```

---

## Additional Resources

- [DAG Configuration Guide](dag_configuration.md) - JSON DAG creation
- [Operator Guide](operator_guide.md) - Retry and failure handling
- [Testing Guide](../TESTING.md) - Running tests
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)

---

## Getting Help

1. **Check logs**: `docker compose logs -f [service]`
2. **Run validation**: `./scripts/validate_environment.sh`
3. **Review troubleshooting**: See [Troubleshooting](#troubleshooting) section
4. **Check Airflow docs**: [airflow.apache.org](https://airflow.apache.org)

---

**Last Updated**: 2024-01-15