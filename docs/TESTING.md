# Testing Guide

## Environment Setup

### Python Version Requirement

**IMPORTANT**: This project requires Python 3.8-3.11 for Apache Airflow 2.8.x compatibility.

Current system has Python 3.12, which is not compatible with Airflow 2.8.1. To run tests and the application:

#### Option 1: Use Docker (Recommended)

The Docker environment is configured with Python 3.11:

```bash
docker compose up -d
docker compose exec airflow-scheduler pytest tests/
```

#### Option 2: Use pyenv to install Python 3.11

```bash
# Install pyenv if not already installed
curl https://pyenv.run | bash

# Install Python 3.11
pyenv install 3.11.9

# Set local Python version
pyenv local 3.11.9

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### Option 3: Update to Airflow 3.0+ (Future)

Once Airflow 3.0+ is stable and supports Python 3.12, update `requirements.txt`:

```
apache-airflow>=3.0.0
```

## Running Tests

### All Tests

```bash
pytest tests/
```

### Unit Tests Only

```bash
pytest tests/unit/
```

### Integration Tests Only

```bash
pytest tests/integration/ -m integration
```

### Specific Test Suite

```bash
# Config validator tests
pytest tests/unit/test_dag_factory/test_config_validator.py -v

# Operator registry tests
pytest tests/unit/test_dag_factory/test_operator_registry.py -v

# DAG builder tests
pytest tests/unit/test_dag_factory/test_dag_builder.py -v
```

### With Coverage

```bash
pytest tests/ --cov=src --cov=dags --cov-report=html --cov-report=term
```

Open `htmlcov/index.html` to view coverage report.

### Test Markers

Tests are organized with markers:

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests requiring Airflow
- `@pytest.mark.slow` - Long-running tests

Run specific markers:

```bash
# Only unit tests (fast)
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Only integration tests
pytest -m integration
```

## Test Structure

```
tests/
├── unit/                          # Unit tests (no external dependencies)
│   ├── test_dag_factory/
│   │   ├── test_config_validator.py    # 17 tests
│   │   ├── test_operator_registry.py   # 17 tests
│   │   └── test_dag_builder.py         # 22 tests
│   ├── test_operators/
│   ├── test_hooks/
│   └── test_utils/
├── integration/                    # Integration tests (require Airflow)
│   ├── test_dag_parsing.py             # 17 tests
│   └── test_dynamic_dag_execution.py   # 18 tests
├── fixtures/                       # Test data
│   ├── mock_configs/
│   │   ├── simple_etl.json
│   │   └── invalid_config.json
│   └── mock_datasets/
│       ├── customers_sample.json
│       └── sales_with_issues.json
└── conftest.py                     # Shared fixtures

Total: 91 tests written for Phase 3
```

## Test Coverage Requirements

Per `pyproject.toml`, minimum coverage is 80%:

```toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov=dags --cov-report=term --cov-report=html"

[tool.coverage.report]
fail_under = 80
```

## Fixtures

Common fixtures available from `conftest.py`:

### Configuration Fixtures

- `sample_dag_config` - Valid DAG configuration dict
- `mock_dag_configs_dir` - Path to test configs
- `mock_datasets_dir` - Path to test datasets

### Data Fixtures

- `mock_data_generator` - MockDataGenerator with seed=42
- `sample_customers` - 100 customer records
- `sample_products` - 50 product records
- `sample_sales` - 500 sales records with quality issues

### Airflow Fixtures

- `mock_airflow_context` - Mock task context
- `dag_bag` - DagBag for DAG validation tests
- `mock_warehouse_connection` - Mock warehouse connection config

### Notification Fixtures

- `mock_smtp_config` - SMTP configuration
- `mock_teams_webhook_url` - Teams webhook URL
- `mock_telegram_config` - Telegram bot configuration

## Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Hooks include:
- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON validation
- Black code formatting
- Ruff linting
- Mypy type checking
- Interrogate docstring coverage (80%+)
- Bandit security checks

## Continuous Integration

GitHub Actions workflow runs:
1. Linting (ruff, black, mypy)
2. Unit tests
3. Integration tests (with Airflow in Docker)
4. Coverage report
5. Build Docker images

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'airflow'`:

- Ensure you're in the correct Python environment (3.8-3.11)
- Activate virtual environment: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

### Docker Tests Failing

```bash
# Rebuild containers
docker compose down -v
docker compose build --no-cache
docker compose up -d

# Check logs
docker compose logs airflow-scheduler
```

### Database Connection Errors

Ensure PostgreSQL containers are healthy:

```bash
docker compose ps
docker compose logs airflow-warehouse
docker compose logs airflow-postgres
```

## Test Development Workflow

Following TDD (Test-Driven Development):

1. **Write failing test** for new feature
2. **Run test** to verify it fails: `pytest tests/unit/... -v`
3. **Implement** minimal code to pass test
4. **Run test** to verify it passes
5. **Refactor** code while keeping tests green
6. **Run all tests** to ensure no regressions: `pytest tests/`

## Next Steps

Once Python 3.11 environment is set up:

1. Install dependencies
2. Run all tests: `pytest tests/ -v`
3. Check coverage: `pytest tests/ --cov`
4. Fix any failing tests
5. Continue with Phase 4 implementation

## Testing Status

### Phase 3: User Story 1 - Dynamic DAG Configuration

**Unit Tests Written**: 56 tests
- ✅ Config validator: 17 tests
- ✅ Operator registry: 17 tests
- ✅ DAG builder: 22 tests

**Integration Tests Written**: 35 tests
- ✅ DAG parsing: 17 tests
- ✅ Dynamic DAG execution: 18 tests

**Status**: Tests written, awaiting Python 3.11 environment for execution

### Next Phase Tests

Tests for Phase 4+ will be written following the same TDD approach.
