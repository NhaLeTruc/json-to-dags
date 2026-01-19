# Running Tests in Docker

## Overview

Due to Python version requirements (Airflow 2.8.x requires Python 3.8-3.11), the recommended way to run tests is inside the Docker container which has Python 3.11 pre-configured.

## Quick Start

### 1. Build and Start Containers

```bash
# Build images
docker compose build

# Start services
docker compose up -d

# Wait for services to be healthy
docker compose ps
```

### 2. Run Tests in Container

```bash
# Run all tests
docker compose exec airflow-scheduler pytest /opt/airflow/tests/ -v

# Run unit tests only
docker compose exec airflow-scheduler pytest /opt/airflow/tests/unit/ -v

# Run integration tests only
docker compose exec airflow-scheduler pytest /opt/airflow/tests/integration/ -v -m integration

# Run with coverage
docker compose exec airflow-scheduler pytest /opt/airflow/tests/ --cov=/opt/airflow/src --cov=/opt/airflow/dags --cov-report=term
```

### 3. Run Specific Test Files

```bash
# Config validator tests
docker compose exec airflow-scheduler pytest /opt/airflow/tests/unit/test_dag_factory/test_config_validator.py -v

# Operator registry tests
docker compose exec airflow-scheduler pytest /opt/airflow/tests/unit/test_dag_factory/test_operator_registry.py -v

# DAG builder tests
docker compose exec airflow-scheduler pytest /opt/airflow/tests/unit/test_dag_factory/test_dag_builder.py -v

# DAG parsing integration tests
docker compose exec airflow-scheduler pytest /opt/airflow/tests/integration/test_dag_parsing.py -v

# DAG execution integration tests
docker compose exec airflow-scheduler pytest /opt/airflow/tests/integration/test_dynamic_dag_execution.py -v
```

## Container Shell Access

To interactively debug or run tests:

```bash
# Open shell in scheduler container
docker compose exec airflow-scheduler bash

# Inside container, you can run:
cd /opt/airflow
pytest tests/unit/ -v
pytest tests/integration/ -v
python -m pytest tests/ --cov
```

## Test Development Workflow

### 1. Edit tests locally

```bash
vim tests/unit/test_dag_factory/test_config_validator.py
```

### 2. Tests are automatically available in container (via volume mount)

The `docker-compose.yml` mounts:
- `./tests:/opt/airflow/tests`
- `./src:/opt/airflow/src`
- `./dags:/opt/airflow/dags`

So changes are immediately reflected in the container.

### 3. Run tests in container

```bash
docker compose exec airflow-scheduler pytest /opt/airflow/tests/unit/test_dag_factory/test_config_validator.py -v
```

### 4. Fix code and re-run

Edit implementation files locally, then re-run tests in container.

## Viewing Test Results

### Terminal Output

Tests output directly to terminal with `-v` flag:

```bash
docker compose exec airflow-scheduler pytest /opt/airflow/tests/ -v
```

### Coverage Report

Generate HTML coverage report:

```bash
docker compose exec airflow-scheduler pytest /opt/airflow/tests/ \
    --cov=/opt/airflow/src \
    --cov=/opt/airflow/dags \
    --cov-report=html \
    --cov-report=term

# Coverage report is in htmlcov/ directory (volume mounted)
# Open htmlcov/index.html in browser
```

## Troubleshooting

### Tests Fail to Import Modules

**Problem**: `ModuleNotFoundError: No module named 'src'`

**Solution**: Check PYTHONPATH in container:

```bash
docker compose exec airflow-scheduler bash -c 'echo $PYTHONPATH'
```

Should show: `/opt/airflow:/opt/airflow/dags:/opt/airflow/src`

If not, rebuild container:

```bash
docker compose down
docker compose build --no-cache airflow-scheduler
docker compose up -d
```

### Airflow Not Running

**Problem**: Tests fail because Airflow is not initialized

**Solution**: Wait for airflow-init to complete:

```bash
docker compose logs airflow-init

# Should see: "Airflow initialization complete"
```

### Database Not Ready

**Problem**: Tests fail with database connection errors

**Solution**: Ensure PostgreSQL is healthy:

```bash
docker compose ps

# airflow-postgres and airflow-warehouse should show "healthy"

# Check logs:
docker compose logs airflow-warehouse
docker compose logs airflow-postgres
```

### Permission Errors

**Problem**: `PermissionError: [Errno 13] Permission denied`

**Solution**: Check file ownership:

```bash
# On host machine
ls -la tests/
ls -la src/

# If needed, fix ownership (using UID 50000 for airflow user)
sudo chown -R 50000:50000 tests/ src/ dags/
```

## Running Tests During Development

### Watch Mode

Use pytest-watch for automatic test re-running:

```bash
# In container
docker compose exec airflow-scheduler bash

# Install pytest-watch
pip install pytest-watch

# Watch and auto-run tests
ptw tests/unit/ -- -v
```

### Running Subset of Tests

```bash
# By marker
docker compose exec airflow-scheduler pytest -m "unit and not slow" -v

# By keyword
docker compose exec airflow-scheduler pytest -k "validator" -v

# Stop on first failure
docker compose exec airflow-scheduler pytest -x -v

# Last failed tests
docker compose exec airflow-scheduler pytest --lf -v
```

## CI/CD Integration

GitHub Actions workflow (`.github/workflows/test.yml`) runs tests in Docker:

```yaml
- name: Run tests
  run: |
    docker compose build
    docker compose up -d
    docker compose exec -T airflow-scheduler pytest tests/ -v --cov
```

## Performance Considerations

### Speeding Up Tests

1. **Run unit tests only** during development (fast):
   ```bash
   docker compose exec airflow-scheduler pytest tests/unit/ -v
   ```

2. **Skip slow tests**:
   ```bash
   docker compose exec airflow-scheduler pytest -m "not slow" -v
   ```

3. **Run in parallel** (with pytest-xdist):
   ```bash
   docker compose exec airflow-scheduler bash
   pip install pytest-xdist
   pytest tests/ -n auto -v
   ```

### Test Execution Times

Approximate execution times:

- **Unit tests** (56 tests): ~5-10 seconds
- **Integration tests** (35 tests): ~30-60 seconds (requires Airflow initialization)
- **All tests** (91 tests): ~40-70 seconds

## Pre-commit Hooks in Docker

To run pre-commit hooks in Docker environment:

```bash
docker compose exec airflow-scheduler bash -c "
pip install pre-commit && \
pre-commit run --all-files
"
```

## Next Steps

1. **Start containers**: `docker compose up -d`
2. **Run tests**: `docker compose exec airflow-scheduler pytest tests/ -v`
3. **View results**: Check terminal output and coverage report
4. **Iterate**: Fix any failing tests, re-run

## Summary

✅ **Recommended approach**: Run all tests in Docker container
✅ **Fast feedback**: Volume mounts enable quick edit-test cycle
✅ **CI/CD ready**: Same environment locally and in GitHub Actions
✅ **No Python version issues**: Container has correct Python 3.11

For local Python 3.11 setup instructions, see [TESTING.md](../TESTING.md).
