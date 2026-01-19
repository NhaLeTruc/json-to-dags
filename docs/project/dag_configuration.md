# DAG Configuration Guide

Complete guide to creating Apache Airflow DAGs using JSON configuration files.

## Table of Contents

- [Overview](#overview)
- [Configuration Schema](#configuration-schema)
- [DAG-Level Configuration](#dag-level-configuration)
- [Task Configuration](#task-configuration)
- [Dependencies](#dependencies)
- [Operators](#operators)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The DAG Factory allows you to create Airflow DAGs using JSON configuration files instead of writing Python code. Simply create a JSON file following the schema below, place it in `dags/config/examples/`, and the DAG will be automatically generated and appear in the Airflow UI.

### Quick Start

1. Create a JSON file in `dags/config/examples/`
2. Define your DAG configuration following the schema
3. Restart Airflow or wait for the DAG refresh interval
4. Your DAG will appear in the Airflow UI

## Configuration Schema

### Top-Level Structure

```json
{
  "dag_id": "my_dag_name",
  "description": "What this DAG does",
  "schedule_interval": "0 2 * * *",
  "start_date": "2024-01-01",
  "catchup": false,
  "tags": ["tag1", "tag2"],
  "default_args": { ... },
  "tasks": [ ... ]
}
```

## DAG-Level Configuration

### Required Fields

#### `dag_id` (string, required)

Unique identifier for the DAG. Must follow naming convention:
- Lowercase letters, numbers, underscores only
- No spaces or special characters
- Must be unique across all DAGs

```json
"dag_id": "daily_sales_etl"
```

#### `description` (string, required)

Human-readable description of what the DAG does.

```json
"description": "Daily ETL pipeline for sales data processing"
```

#### `schedule_interval` (string, required)

Cron expression or Airflow preset defining when the DAG runs.

Common values:
- `"0 2 * * *"` - Daily at 2 AM
- `"*/15 * * * *"` - Every 15 minutes
- `"0 */6 * * *"` - Every 6 hours
- `"@daily"` - Daily at midnight
- `"@hourly"` - Every hour
- `null` - Manual trigger only

```json
"schedule_interval": "0 2 * * *"
```

#### `start_date` (string, required)

Date from which the DAG should start running (YYYY-MM-DD format).

```json
"start_date": "2024-01-01"
```

### Optional Fields

#### `catchup` (boolean, optional, default: false)

Whether to backfill DAG runs for past dates.

```json
"catchup": false
```

#### `tags` (array of strings, optional)

Tags for categorizing and filtering DAGs in the UI.

```json
"tags": ["production", "sales", "etl"]
```

#### `default_args` (object, optional)

Default arguments applied to all tasks in the DAG.

```json
"default_args": {
  "owner": "data_team",
  "retries": 3,
  "retry_delay_minutes": 5,
  "email_on_failure": true,
  "email_on_retry": false,
  "email": ["alerts@example.com"]
}
```

**Available default_args:**

- `owner` (string) - Task owner name
- `retries` (integer) - Number of retry attempts on failure
- `retry_delay_minutes` (integer) - Minutes to wait between retries
- `email_on_failure` (boolean) - Send email on task failure
- `email_on_retry` (boolean) - Send email on task retry
- `email` (array of strings) - Email addresses for notifications

## Task Configuration

Tasks are defined in the `tasks` array. Each task requires:

### Required Task Fields

#### `task_id` (string, required)

Unique identifier for the task within the DAG.

```json
"task_id": "extract_data"
```

#### `operator` (string, required)

Name of the Airflow operator to use.

Available operators:
- `BashOperator` - Execute bash commands
- `PythonOperator` - Execute Python functions
- `DummyOperator` - Placeholder task (no operation)

```json
"operator": "BashOperator"
```

#### `params` (object, required)

Operator-specific parameters.

```json
"params": {
  "bash_command": "echo 'Hello World'"
}
```

### Optional Task Fields

#### `dependencies` (array of strings, optional)

List of upstream task IDs that must complete before this task runs.

```json
"dependencies": ["extract_data", "validate_schema"]
```

### Task-Level Overrides

Tasks can override `default_args` by including them in `params`:

```json
{
  "task_id": "critical_task",
  "operator": "BashOperator",
  "params": {
    "bash_command": "echo 'Important task'",
    "retries": 10,
    "retry_delay_minutes": 1
  }
}
```

## Dependencies

### Linear Dependencies

Tasks execute in sequence:

```json
"tasks": [
  {
    "task_id": "extract",
    "operator": "BashOperator",
    "params": {"bash_command": "echo 'Extract'"}
  },
  {
    "task_id": "transform",
    "operator": "BashOperator",
    "params": {"bash_command": "echo 'Transform'"},
    "dependencies": ["extract"]
  },
  {
    "task_id": "load",
    "operator": "BashOperator",
    "params": {"bash_command": "echo 'Load'"},
    "dependencies": ["transform"]
  }
]
```

Flow: `extract` → `transform` → `load`

### Parallel Dependencies

Multiple tasks run in parallel, then converge:

```json
"tasks": [
  {
    "task_id": "extract_source_a",
    "operator": "BashOperator",
    "params": {"bash_command": "echo 'Extract A'"}
  },
  {
    "task_id": "extract_source_b",
    "operator": "BashOperator",
    "params": {"bash_command": "echo 'Extract B'"}
  },
  {
    "task_id": "merge",
    "operator": "BashOperator",
    "params": {"bash_command": "echo 'Merge'"},
    "dependencies": ["extract_source_a", "extract_source_b"]
  }
]
```

Flow: `extract_source_a` and `extract_source_b` run in parallel, then `merge` runs.

### No Dependencies

Tasks with no dependencies run immediately when the DAG starts.

## Operators

### BashOperator

Executes bash commands.

**Required Parameters:**
- `bash_command` (string) - Bash command to execute

**Example:**

```json
{
  "task_id": "run_script",
  "operator": "BashOperator",
  "params": {
    "bash_command": "bash /scripts/process_data.sh"
  }
}
```

### PythonOperator

Executes Python functions.

**Required Parameters:**
- `python_callable` (string) - Name of Python function to call

**Example:**

```json
{
  "task_id": "process_data",
  "operator": "PythonOperator",
  "params": {
    "python_callable": "my_module.process_function"
  }
}
```

### DummyOperator

Placeholder task that does nothing (useful for organizing DAG structure).

**Parameters:** None required

**Example:**

```json
{
  "task_id": "start",
  "operator": "DummyOperator",
  "params": {}
}
```

## Examples

### Example 1: Simple ETL Pipeline

```json
{
  "dag_id": "simple_etl",
  "description": "Simple ETL pipeline",
  "schedule_interval": "0 2 * * *",
  "start_date": "2024-01-01",
  "catchup": false,
  "tags": ["example", "etl"],
  "default_args": {
    "owner": "airflow",
    "retries": 2,
    "retry_delay_minutes": 5
  },
  "tasks": [
    {
      "task_id": "extract",
      "operator": "BashOperator",
      "params": {"bash_command": "echo 'Extracting data'"}
    },
    {
      "task_id": "transform",
      "operator": "BashOperator",
      "params": {"bash_command": "echo 'Transforming data'"},
      "dependencies": ["extract"]
    },
    {
      "task_id": "load",
      "operator": "BashOperator",
      "params": {"bash_command": "echo 'Loading data'"},
      "dependencies": ["transform"]
    }
  ]
}
```

### Example 2: Parallel Processing

```json
{
  "dag_id": "parallel_processing",
  "description": "Process multiple data sources in parallel",
  "schedule_interval": "0 6 * * *",
  "start_date": "2024-01-01",
  "catchup": false,
  "tags": ["example", "parallel"],
  "default_args": {
    "owner": "airflow",
    "retries": 1
  },
  "tasks": [
    {
      "task_id": "start",
      "operator": "DummyOperator",
      "params": {}
    },
    {
      "task_id": "process_customers",
      "operator": "BashOperator",
      "params": {"bash_command": "echo 'Processing customers'"},
      "dependencies": ["start"]
    },
    {
      "task_id": "process_products",
      "operator": "BashOperator",
      "params": {"bash_command": "echo 'Processing products'"},
      "dependencies": ["start"]
    },
    {
      "task_id": "process_sales",
      "operator": "BashOperator",
      "params": {"bash_command": "echo 'Processing sales'"},
      "dependencies": ["start"]
    },
    {
      "task_id": "end",
      "operator": "DummyOperator",
      "params": {},
      "dependencies": ["process_customers", "process_products", "process_sales"]
    }
  ]
}
```

## Best Practices

### 1. Naming Conventions

- Use descriptive, lowercase `dag_id` with underscores
- Use verb-noun pattern for `task_id` (e.g., `extract_data`, `validate_schema`)
- Keep names concise but meaningful

### 2. Error Handling

- Set appropriate `retries` based on task reliability
- Use `retry_delay_minutes` to avoid overwhelming systems
- Configure `email_on_failure` for critical DAGs

### 3. Dependencies

- Keep dependency graphs simple and clear
- Avoid circular dependencies (validator will catch these)
- Use `DummyOperator` for branching/merging visualization

### 4. Scheduling

- Use `catchup: false` for most DAGs to avoid backfill
- Choose appropriate `schedule_interval` for data freshness needs
- Set `start_date` to a date in the past for immediate scheduling

### 5. Documentation

- Write clear, descriptive `description` fields
- Use `tags` consistently for DAG organization
- Include comments in bash commands when needed

## Troubleshooting

### DAG Not Appearing in UI

**Check:**
1. JSON file is in `dags/config/examples/`
2. JSON syntax is valid (use a JSON validator)
3. Airflow DAG refresh interval has passed
4. Check Airflow logs for errors

### Validation Errors

**Common issues:**
- Missing required fields (`dag_id`, `description`, etc.)
- Invalid `dag_id` format (special characters, uppercase)
- Duplicate `task_id` values
- Non-existent task in `dependencies` array
- Circular dependencies detected

**Check logs:**
```bash
docker-compose logs airflow-scheduler | grep ERROR
```

### Task Execution Failures

**Check:**
- Bash commands are executable
- Required files/scripts exist
- Permissions are correct
- Retry configuration is appropriate

## Schema Validation

All configurations are validated against the JSON schema located at:
`dags/config/schemas/dag-config-schema.json`

The validator checks for:
- ✓ Required fields present
- ✓ Correct data types
- ✓ Valid `dag_id` format
- ✓ No duplicate `task_id` values
- ✓ All dependencies reference existing tasks
- ✓ No circular dependencies

## Next Steps

- See example DAGs in `dags/config/examples/`
- Review JSON schema in `dags/config/schemas/`
- Check Airflow UI to verify your DAG appears
- Monitor execution in Airflow logs

For custom operators and advanced configurations, see:
- [Custom Operators Guide](./custom_operators.md) (coming soon)
- [Airflow Documentation](https://airflow.apache.org/docs/)
