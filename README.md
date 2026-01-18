# Apache Airflow ETL Demo Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Apache Airflow 2.10](https://img.shields.io/badge/airflow-2.10-blue.svg)](https://airflow.apache.org/)
[![CI Pipeline](https://img.shields.io/badge/CI-passing-brightgreen.svg)](./.github/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-80%25+-brightgreen.svg)](./tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A comprehensive demonstration platform showcasing enterprise-grade Apache Airflow ETL capabilities including dynamic DAG generation, multi-cluster Spark orchestration, data quality validation, and production-ready CI/CD pipelines.

## Features

🚀 **Dynamic DAG Generation** - Create ETL pipelines via JSON configuration without writing Python code

🔄 **Resilient Execution** - Automatic retry, exponential backoff, timeout handling, and graceful failure recovery

⚡ **Multi-Cluster Spark** - Submit and monitor Spark jobs across standalone, YARN, and Kubernetes clusters

📨 **Multi-Channel Notifications** - Email, MS Teams, and Telegram integrations for operational awareness

✅ **Data Quality Assurance** - Comprehensive quality checks with configurable severity levels (schema, completeness, freshness, uniqueness, null rates)

📚 **14 Example DAGs** - Progressive learning from beginner to advanced ETL patterns

🐳 **Docker Compose Environment** - Complete local development stack with one command

🔧 **CI/CD Pipeline** - Automated linting, testing, and deployment via GitHub Actions

## Quick Start

### Prerequisites

- Docker Engine 20.10+ and Docker Compose 2.0+
- Git 2.30+
- 8 GB RAM available for containers
- 20 GB free disk space

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/apache-airflow-etl-demo.git
cd apache-airflow-etl-demo

# Copy environment template
cp .env.example .env

# Start the entire stack (Airflow, PostgreSQL warehouse, Spark)
docker compose up -d

# Wait for services to be healthy (~2-3 minutes)
docker compose ps
```

### Access Airflow UI

Open your browser to: **http://localhost:8080**

**Default Credentials**:
- Username: `admin`
- Password: `admin`

### Run Your First DAG

1. In Airflow UI, navigate to **DAGs** page
2. Find `demo_simple_extract_load_v1`
3. Toggle the DAG to "On"
4. Click ▶️ (Play) → "Trigger DAG"
5. Watch execution complete (usually <30 seconds)

✅ Success: All tasks turn dark green!

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Airflow Webserver                        │
│                   (UI & REST API: 8080)                      │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────┐
│                    Airflow Scheduler                         │
│              (DAG Parsing & Task Execution)                  │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │
   ┌───▼──┐      ┌───▼──┐      ┌───▼──┐      ┌───▼──┐
   │ DAG  │      │ DAG  │      │ DAG  │      │ DAG  │
   │  1   │      │  2   │      │  3   │      │ ...  │
   └───┬──┘      └───┬──┘      └───┬──┘      └───┬──┘
       │              │              │              │
┌──────▼──────────────▼──────────────▼──────────────▼─────────┐
│                 PostgreSQL Warehouse                         │
│          (Mock DW: dimensions, facts, staging)               │
└──────────────────────────────────────────────────────────────┘
```

### Project Structure

```
apache-airflow-etl-demo/
├── dags/                      # Airflow DAGs
│   ├── config/               # JSON DAG configurations
│   │   ├── schemas/         # JSON schema definitions
│   │   └── examples/        # Example configurations
│   ├── factory/             # Dynamic DAG generation engine
│   └── examples/            # 14 example DAGs
│       ├── beginner/       # 4 basic patterns
│       ├── intermediate/   # 6 advanced patterns
│       └── advanced/       # 4 expert patterns
├── src/                      # Source code
│   ├── operators/           # Custom Airflow operators
│   │   ├── spark/          # Spark cluster operators
│   │   ├── notifications/  # Email, Teams, Telegram
│   │   └── quality/        # Data quality checks
│   ├── hooks/              # Custom Airflow hooks
│   ├── utils/              # Utilities (logging, config, data gen)
│   └── warehouse/          # Mock warehouse schema & data
├── tests/                    # Test suite
│   ├── unit/               # Unit tests (80%+ coverage)
│   └── integration/        # Integration tests
├── docker/                   # Docker configurations
│   ├── airflow/            # Airflow container
│   ├── warehouse/          # PostgreSQL warehouse
│   └── spark/              # Spark clusters
├── docs/                     # Documentation
│   ├── architecture.md
│   ├── dag_configuration.md
│   ├── operator_guide.md
│   └── development.md
└── .github/workflows/        # CI/CD pipelines
    ├── ci.yml              # Lint, test, validate
    ├── cd-staging.yml      # Deploy to staging
    └── cd-production.yml   # Deploy to production
```

## Creating Your First JSON-Configured DAG

Create `dags/config/my_first_dag.json`:

```json
{
  "dag_id": "my_sales_report_v1",
  "description": "My first JSON-configured DAG",
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
      "task_id": "send_report",
      "operator": "EmailNotificationOperator",
      "parameters": {
        "to": "your-email@example.com",
        "subject": "Daily Sales Report for {{ ds }}",
        "body": "Sales ETL completed successfully."
      },
      "upstream_tasks": ["extract_daily_sales"]
    }
  ]
}
```

The DAG will appear in Airflow UI within 30 seconds!

## Testing

```bash
# Run all tests with coverage
docker exec airflow-scheduler pytest

# Run only unit tests (fast)
docker exec airflow-scheduler pytest tests/unit/ -m unit

# Run only integration tests
docker exec airflow-scheduler pytest tests/integration/ -m integration

# Run specific test file
docker exec airflow-scheduler pytest tests/unit/test_operators/test_spark_operators.py -v
```

**Expected Coverage**: 80%+ for all custom code

## Development

### Local Setup

```bash
python3 -m venv venv

source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Run linting
ruff check .
black --check .
mypy src/ dags/factory/

# Format code
black .
ruff check --fix .
```

### Docker Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f airflow-scheduler

# Stop services
docker compose down

# Reset environment (deletes all data)
docker compose down -v
docker compose up -d
```

## Example DAG Gallery

| DAG | Complexity | Pattern Demonstrated |
|-----|------------|---------------------|
| `demo_simple_extract_load_v1` | Beginner | Basic extract-load pipeline |
| `demo_scheduled_pipeline_v1` | Beginner | Scheduled execution with retry |
| `demo_data_quality_basics_v1` | Beginner | Schema validation, completeness checks |
| `demo_notification_basics_v1` | Beginner | Email and Teams notifications |
| `demo_incremental_load_v1` | Intermediate | Incremental data with watermarks |
| `demo_scd_type2_v1` | Intermediate | Slowly Changing Dimensions Type 2 |
| `demo_parallel_processing_v1` | Intermediate | Fan-out/fan-in parallel execution |
| `demo_spark_standalone_v1` | Intermediate | Spark job on standalone cluster |
| `demo_cross_dag_dependency_v1` | Intermediate | DAG triggering and sensors |
| `demo_spark_multi_cluster_v1` | Advanced | Spark on standalone, YARN, K8s |
| `demo_comprehensive_quality_v1` | Advanced | All 5 quality check types |
| `demo_event_driven_pipeline_v1` | Advanced | File sensor triggering |
| `demo_failure_recovery_v1` | Advanced | Compensation logic and state recovery |

## CI/CD Pipeline

Every push to a feature branch triggers:
1. ✅ Code linting (ruff, black, mypy)
2. ✅ Unit tests (80%+ coverage required)
3. ✅ Integration tests (DAG parsing, execution)
4. ✅ DAG validation (no import errors)

On merge to `main`:
1. 🚀 Deploy to staging environment
2. 🧪 Run smoke tests
3. ⏸️ Manual approval gate
4. 🚀 Deploy to production

## Documentation

### Getting Started
- **[Quick Start - Development](docs/QUICK_START_DEV.md)** - 5-minute setup guide for developers
- **[Quickstart Guide](specs/001-build-a-full/quickstart.md)** - Detailed setup and usage
- **[Development Setup Fixes](docs/DEVELOPMENT_SETUP_FIXES.md)** - Python 3.12 compatibility & troubleshooting

### Technical Documentation
- **[Architecture](docs/architecture.md)** - System design and components
- **[DAG Configuration](docs/dag_configuration.md)** - JSON schema reference
- **[Operator Guide](docs/operator_guide.md)** - Custom operator usage
- **[Development Guide](docs/development.md)** - Local development workflow

### Project Information
- **[Changelog](CHANGELOG.md)** - Version history and changes
- **[Session Summary](SESSION_SUMMARY.md)** - Latest development session notes

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests first (TDD required)
4. Implement feature
5. Ensure tests pass (`pytest`)
6. Ensure code quality (`ruff check . && black . && mypy src/`)
7. Commit changes (`git commit -m 'Add amazing feature'`)
8. Push to branch (`git push origin feature/amazing-feature`)
9. Open Pull Request

## License

MIT License - See [LICENSE](LICENSE) file for details

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/apache-airflow-etl-demo/issues)
- **Documentation**: [docs/](docs/)
- **Airflow Docs**: https://airflow.apache.org/docs/

## Acknowledgments

- Apache Airflow community for excellent orchestration platform
- Great Expectations for data quality framework
- PySpark for distributed computing capabilities

---

**Built with ❤️ for the data engineering community**
