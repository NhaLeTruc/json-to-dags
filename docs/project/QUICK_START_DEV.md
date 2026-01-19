# Quick Start - Development Environment

**Updated:** 2025-10-22 - Python 3.12 Compatible

---

## Prerequisites

- **Python:** 3.12.3 (or 3.11+)
- **Operating System:** Linux (tested on Linux 6.14.0-33-generic)
- **Git:** For version control

---

## Setup (5 minutes)

### 1. Clone and Enter Directory
```bash
cd /path/to/claude-airflow-etl
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies (including dev tools)
pip install -r requirements-dev.txt
```

**Expected:** All packages install successfully (~5 minutes)

---

## Verify Installation

Run all code quality checks:

```bash
source venv/bin/activate

# Check formatting (should show "92 files would be left unchanged")
black --check .

# Check linting (should show "All checks passed!")
ruff check .

# Check type hints (should show "Success: no issues found in 36 source files")
mypy src/ dags/factory/
```

---

## Common Development Tasks

### Format Code
```bash
# Check formatting
black --check .

# Auto-format all files
black .
```

### Lint Code
```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Type Check
```bash
# Check types
mypy src/ dags/factory/
```

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov=dags/factory

# Run specific test
pytest tests/unit/test_hooks/test_warehouse_hook.py
```

### Run Specific Test Categories
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests (requires services)
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

---

## Project Structure

```
claude-airflow-etl/
├── dags/                    # Airflow DAG definitions
│   ├── examples/            # Example DAGs
│   │   ├── beginner/        # Beginner-level examples
│   │   ├── intermediate/    # Intermediate examples
│   │   └── advanced/        # Advanced patterns
│   ├── factory/             # DAG factory for dynamic generation
│   └── config/              # DAG configurations
├── src/                     # Source code
│   ├── hooks/               # Custom Airflow hooks
│   ├── operators/           # Custom Airflow operators
│   │   ├── quality/         # Data quality operators
│   │   ├── notifications/   # Notification operators
│   │   └── spark/           # Spark operators
│   ├── utils/               # Utility modules
│   └── spark_apps/          # Spark applications
├── tests/                   # Test suite
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docs/                    # Documentation
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
└── pyproject.toml           # Tool configuration
```

---

## Code Quality Standards

### Black (Formatting)
- **Line length:** 100 characters
- **Target:** Python 3.11
- **Auto-formatting:** Enabled

### Ruff (Linting)
- **Line length:** 100 characters
- **Checks enabled:** pycodestyle, pyflakes, isort, complexity, bugbear, security
- **Auto-fix:** Available for most issues

### Mypy (Type Checking)
- **Mode:** Relaxed (appropriate for Airflow projects)
- **Coverage:** Basic type checking for safety
- **Philosophy:** Gradual typing

### Pytest (Testing)
- **Coverage target:** 80%
- **Markers:** unit, integration, slow
- **Reports:** Terminal + HTML

---

## Pre-Commit Hook (Optional)

Install pre-commit hooks for automatic checks:

```bash
# Install pre-commit
pip install pre-commit

# Setup hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

---

## Troubleshooting

### Issue: "Module not found" errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements-dev.txt
```

### Issue: "No module named 'airflow'"
```bash
# Airflow is installed - check PYTHONPATH
echo $PYTHONPATH

# Ensure you're in the virtual environment
which python  # Should show /path/to/venv/bin/python
```

### Issue: Black/Ruff/Mypy not found
```bash
# Install dev dependencies
pip install -r requirements-dev.txt
```

### Issue: Tests failing
```bash
# Run with verbose output
pytest -v

# Run specific test to debug
pytest -v tests/unit/test_hooks/test_warehouse_hook.py::TestWarehouseHook::test_get_connection
```

---

## Quick Reference

### Code Quality Commands
```bash
# All checks in one command
black --check . && ruff check . && mypy src/ dags/factory/ && pytest

# Format, lint, type-check, and test (fix mode)
black . && ruff check --fix . && mypy src/ dags/factory/ && pytest
```

### Package Management
```bash
# Add new package
pip install package-name
pip freeze | grep package-name >> requirements.txt

# Add new dev package
pip install package-name
pip freeze | grep package-name >> requirements-dev.txt

# Update all packages (be careful!)
pip install --upgrade -r requirements-dev.txt
```

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Check status
git status

# Stage changes
git add .

# Commit (with pre-commit hooks if enabled)
git commit -m "Description of changes"

# Push to remote
git push origin feature/your-feature-name
```

---

## Configuration Files

### pyproject.toml
Central configuration for:
- Black formatter
- Ruff linter
- Mypy type checker
- Pytest
- Coverage

**Location:** [pyproject.toml](../pyproject.toml)

### requirements.txt
Production dependencies for running Airflow DAGs.

**Key packages:**
- `apache-airflow==2.10.5`
- `pyspark==3.5.3`
- `great-expectations==0.18.19`

### requirements-dev.txt
Development tools and testing dependencies.

**Key packages:**
- `pytest==8.3.4`
- `black==24.10.0`
- `ruff==0.8.4`
- `mypy==1.14.0`

---

## Resources

- **Full Setup Documentation:** [DEVELOPMENT_SETUP_FIXES.md](./DEVELOPMENT_SETUP_FIXES.md)
- **Changelog:** [CHANGELOG.md](../CHANGELOG.md)
- **Project README:** [README.md](../README.md)
- **Development Guidelines:** [CLAUDE.md](../CLAUDE.md)

---

## Need Help?

1. Check [DEVELOPMENT_SETUP_FIXES.md](./DEVELOPMENT_SETUP_FIXES.md) for detailed troubleshooting
2. Review error messages carefully - they usually point to the issue
3. Verify virtual environment is activated: `which python`
4. Check Python version: `python --version` (should be 3.12+)

---

**Ready to develop!** 🚀

Start by exploring the example DAGs in `dags/examples/` or run the test suite with `pytest`.