# Airflow DAG Monitoring & Troubleshooting Guide

This guide provides Docker and Bash commands to monitor and troubleshoot Airflow DAG performance issues.

---

## Table of Contents

1. [Real-time Monitoring](#real-time-monitoring)
2. [Identifying Slow DAGs](#identifying-slow-dags)
3. [Airflow-Specific Diagnostics](#airflow-specific-diagnostics)
4. [Performance Analysis](#performance-analysis)
5. [Debugging Specific Issues](#debugging-specific-issues)
6. [Quick Health Dashboard](#quick-health-dashboard)

---

## Real-time Monitoring

### Monitor Container Resource Usage

```bash
# Real-time resource usage for all containers (updates every second)
docker stats

# Monitor specific Airflow services only
docker stats airflow-scheduler airflow-dag-processor airflow-webserver

# One-time snapshot (no streaming)
docker stats --no-stream

# Formatted output with specific columns
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
```

**What to look for:**
- **High CPU %**: Indicates heavy computation or inefficient code
- **Memory usage near limit**: Can cause OOM kills and container restarts
- **High BlockIO**: Indicates heavy disk I/O operations

### Watch Live Logs

```bash
# Tail scheduler logs (where DAG execution happens)
docker compose logs -f airflow-scheduler

# Tail dag-processor logs (where DAG parsing happens)
docker compose logs -f airflow-dag-processor

# Follow logs from all Airflow services
docker compose logs -f airflow-scheduler airflow-dag-processor airflow-webserver

# Filter logs by timestamp (last 5 minutes)
docker compose logs --since 5m airflow-scheduler

# Show last 100 lines and follow
docker compose logs --tail=100 -f airflow-scheduler

# Show logs with timestamps
docker compose logs -f --timestamps airflow-scheduler
```

### Monitor Database Connections & Queries

```bash
# Check active connections to Airflow metadata DB
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT count(*) as active_connections, state
   FROM pg_stat_activity
   GROUP BY state;"

# Show running queries (look for slow queries)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT pid,
          now() - query_start as duration,
          state,
          query
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY duration DESC;"

# Check for locks in the database
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT blocked_locks.pid AS blocked_pid,
          blocking_locks.pid AS blocking_pid,
          blocked_activity.query AS blocked_query,
          blocking_activity.query AS blocking_query
   FROM pg_catalog.pg_locks blocked_locks
   JOIN pg_catalog.pg_stat_activity blocked_activity
     ON blocked_activity.pid = blocked_locks.pid
   JOIN pg_catalog.pg_locks blocking_locks
     ON blocking_locks.locktype = blocked_locks.locktype
   WHERE NOT blocked_locks.granted;"

# Monitor connection pool usage
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT max_conn, used, res_for_super, max_conn-used-res_for_super res_for_normal
   FROM (SELECT count(*) used FROM pg_stat_activity) t1,
        (SELECT setting::int res_for_super FROM pg_settings WHERE name='superuser_reserved_connections') t2,
        (SELECT setting::int max_conn FROM pg_settings WHERE name='max_connections') t3;"
```

---

## Identifying Slow DAGs

### 1. Find Currently Running DAGs and Their Duration

```bash
# Show all currently running DAG runs with duration
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          execution_date,
          start_date,
          (now() - start_date) as running_duration,
          state
   FROM dag_run
   WHERE state = 'running'
   ORDER BY start_date ASC;"
```

### 2. Identify Slowest DAG Runs (Historical)

```bash
# Find top 20 slowest completed DAG runs in the last 7 days
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          execution_date,
          start_date,
          end_date,
          (end_date - start_date) as duration,
          state
   FROM dag_run
   WHERE end_date IS NOT NULL
     AND start_date > now() - interval '7 days'
   ORDER BY (end_date - start_date) DESC
   LIMIT 20;"

# Average duration per DAG (last 30 days)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          count(*) as runs,
          avg(end_date - start_date) as avg_duration,
          max(end_date - start_date) as max_duration,
          min(end_date - start_date) as min_duration
   FROM dag_run
   WHERE end_date IS NOT NULL
     AND start_date > now() - interval '30 days'
   GROUP BY dag_id
   ORDER BY avg_duration DESC;"
```

### 3. Find Slowest Tasks Within a DAG

```bash
# Replace <dag_id> with your actual DAG ID
# Show slowest tasks for a specific DAG
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT task_id,
          count(*) as executions,
          avg(end_date - start_date) as avg_duration,
          max(end_date - start_date) as max_duration
   FROM task_instance
   WHERE dag_id = '<dag_id>'
     AND end_date IS NOT NULL
     AND start_date > now() - interval '7 days'
   GROUP BY task_id
   ORDER BY avg_duration DESC;"

# Currently running tasks with their duration
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          task_id,
          execution_date,
          start_date,
          (now() - start_date) as running_duration
   FROM task_instance
   WHERE state = 'running'
   ORDER BY start_date ASC;"
```

### 4. Identify DAGs with High Failure Rates

```bash
# DAGs with most failures in last 7 days
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          count(*) as total_runs,
          sum(case when state = 'failed' then 1 else 0 end) as failures,
          round(100.0 * sum(case when state = 'failed' then 1 else 0 end) / count(*), 2) as failure_rate
   FROM dag_run
   WHERE start_date > now() - interval '7 days'
   GROUP BY dag_id
   HAVING sum(case when state = 'failed' then 1 else 0 end) > 0
   ORDER BY failure_rate DESC;"
```

### 5. Find DAGs Consuming Most Resources

```bash
# Count task instances per DAG (resource usage indicator)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          count(*) as task_instances,
          sum(case when state = 'running' then 1 else 0 end) as currently_running
   FROM task_instance
   WHERE execution_date > now() - interval '24 hours'
   GROUP BY dag_id
   ORDER BY currently_running DESC, task_instances DESC;"
```

### 6. Analyze DAG Parse Times

```bash
# Check which DAGs are slow to parse (causes scheduler delays)
docker compose logs airflow-dag-processor --since 1h | grep "Processing file" | grep -oP '\d+\.\d+s' | sort -rn | head -20

# Look for DAG import errors or warnings
docker compose logs airflow-dag-processor --since 1h | grep -E "ERROR|WARNING" | grep -i dag

# Check DAG parsing duration from logs
docker compose logs airflow-dag-processor --since 1h | grep "DAG(s)" | tail -20
```

### 7. Quick Command to Identify Problem DAG

```bash
# One-liner to find the currently slowest running DAG
docker compose exec airflow-postgres psql -U airflow -d airflow -t -c \
  "SELECT dag_id, (now() - start_date) as duration
   FROM dag_run
   WHERE state = 'running'
   ORDER BY start_date ASC
   LIMIT 1;"
```

---

## Airflow-Specific Diagnostics

### Check DAG Status & Task Details

```bash
# List all DAGs and their status
docker compose exec airflow-scheduler airflow dags list

# Show specific DAG details and structure
docker compose exec airflow-scheduler airflow dags show <dag_id>

# List all tasks for a DAG
docker compose exec airflow-scheduler airflow tasks list <dag_id>

# Check if DAG is paused
docker compose exec airflow-scheduler airflow dags list-import-errors

# Get DAG details in JSON format
docker compose exec airflow-scheduler airflow dags details <dag_id>
```

### Monitor DAG Runs & Task Performance

```bash
# List recent DAG runs
docker compose exec airflow-scheduler airflow dags list-runs -d <dag_id>

# List only running DAG runs
docker compose exec airflow-scheduler airflow dags list-runs -d <dag_id> --state running

# Show task instance history for a specific DAG run
docker compose exec airflow-scheduler airflow tasks states-for-dag-run <dag_id> <execution_date>

# Test a task locally (dry run)
docker compose exec airflow-scheduler airflow tasks test <dag_id> <task_id> <execution_date>

# Get task logs
docker compose exec airflow-scheduler airflow tasks log <dag_id> <task_id> <execution_date>
```

### Check Scheduler & Executor Performance

```bash
# Check scheduler health
docker compose exec airflow-scheduler airflow jobs check --job-type SchedulerJob

# List all jobs
docker compose exec airflow-scheduler airflow jobs list

# Check DAG processor status
docker compose exec airflow-dag-processor airflow jobs check --job-type DagProcessorJob

# View pool usage (if using pools to limit parallelism)
docker compose exec airflow-scheduler airflow pools list

# Check pool details
docker compose exec airflow-scheduler airflow pools get <pool_name>

# View configuration
docker compose exec airflow-scheduler airflow config get-value core parallelism
docker compose exec airflow-scheduler airflow config get-value core max_active_tasks_per_dag
docker compose exec airflow-scheduler airflow config get-value core max_active_runs_per_dag
```

### Task Instance States Overview

```bash
# Count task instances by state (last 24 hours)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT state, count(*) as count
   FROM task_instance
   WHERE execution_date > now() - interval '24 hours'
   GROUP BY state
   ORDER BY count DESC;"

# Task instance state distribution per DAG
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id, state, count(*) as count
   FROM task_instance
   WHERE execution_date > now() - interval '24 hours'
   GROUP BY dag_id, state
   ORDER BY dag_id, count DESC;"
```

---

## Performance Analysis

### Analyze Container Performance

```bash
# Check container CPU/memory limits
docker inspect airflow-scheduler --format='Memory: {{.HostConfig.Memory}}, CPUs: {{.HostConfig.NanoCpus}}'

# Check container restart count (indicates crashes)
docker inspect airflow-scheduler --format='Restart Count: {{.RestartCount}}'

# View container resource constraints
docker inspect airflow-scheduler | grep -A 10 "HostConfig"

# Check container uptime
docker inspect airflow-scheduler --format='Started: {{.State.StartedAt}}, Status: {{.State.Status}}'
```

### Database Performance Queries

```bash
# Check table sizes (look for bloat)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT schemaname,
          tablename,
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
          pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
   FROM pg_tables
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
   LIMIT 10;"

# Check index usage (unused indexes waste space and slow writes)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT schemaname,
          tablename,
          indexname,
          idx_scan as index_scans,
          pg_size_pretty(pg_relation_size(indexrelid)) as index_size
   FROM pg_stat_user_indexes
   ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
   LIMIT 10;"

# Check for table bloat
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT schemaname,
          tablename,
          n_dead_tup,
          n_live_tup,
          round(100 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio
   FROM pg_stat_user_tables
   WHERE n_dead_tup > 1000
   ORDER BY n_dead_tup DESC
   LIMIT 10;"

# Show cache hit ratio (should be > 95%)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT
     sum(heap_blks_read) as heap_read,
     sum(heap_blks_hit) as heap_hit,
     round(100 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as cache_hit_ratio
   FROM pg_statio_user_tables;"
```

### Warehouse Database Performance

```bash
# Check warehouse database connections
docker compose exec airflow-warehouse psql -U warehouse_user -d warehouse -c \
  "SELECT count(*) as connections, state
   FROM pg_stat_activity
   GROUP BY state;"

# Check warehouse table sizes
docker compose exec airflow-warehouse psql -U warehouse_user -d warehouse -c \
  "SELECT schemaname,
          tablename,
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
   LIMIT 10;"
```

---

## Debugging Specific Issues

### Find Zombie/Stuck Tasks

```bash
# Find tasks stuck in running state for more than 1 hour
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          task_id,
          execution_date,
          state,
          start_date,
          (now() - start_date) as running_duration,
          hostname,
          pid
   FROM task_instance
   WHERE state = 'running'
     AND (now() - start_date) > interval '1 hour'
   ORDER BY start_date ASC;"

# Find queued tasks (waiting to run)
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          task_id,
          execution_date,
          state,
          queued_dttm,
          (now() - queued_dttm) as queued_duration
   FROM task_instance
   WHERE state = 'queued'
   ORDER BY queued_dttm ASC
   LIMIT 20;"

# Find tasks that have been retrying
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          task_id,
          execution_date,
          try_number,
          max_tries,
          state
   FROM task_instance
   WHERE try_number > 1
     AND execution_date > now() - interval '24 hours'
   ORDER BY try_number DESC
   LIMIT 20;"
```

### Clear Stuck Tasks (Use with Caution!)

```bash
# Clear specific task instance
docker compose exec airflow-scheduler airflow tasks clear <dag_id> --task-regex <task_id> --yes

# Clear all tasks for a DAG run
docker compose exec airflow-scheduler airflow tasks clear <dag_id> --start-date <date> --end-date <date> --yes

# Mark failed task as success (use carefully!)
docker compose exec airflow-scheduler airflow tasks set-state <dag_id> <task_id> <execution_date> --state success

# Set DAG run state
docker compose exec airflow-scheduler airflow dags set-run-state <dag_id> <execution_date> --state failed
```

### Grep Logs for Errors

```bash
# Search for errors in scheduler logs (last hour)
docker compose logs airflow-scheduler --since 1h | grep -i "error\|exception\|failed"

# Search for specific DAG issues
docker compose logs airflow-scheduler --since 1h | grep -i "<dag_id>"

# Count error occurrences
docker compose logs airflow-scheduler --since 1h | grep -i "error" | wc -l

# Find slow task warnings
docker compose logs airflow-scheduler --since 1h | grep -i "slow\|timeout\|delay"

# Look for out-of-memory errors
docker compose logs airflow-scheduler --since 1h | grep -i "memory\|oom"

# Search for database connection issues
docker compose logs airflow-scheduler --since 1h | grep -i "database\|connection\|psycopg2"

# Export errors to a file for analysis
docker compose logs airflow-scheduler --since 24h 2>&1 | grep -i "error\|exception" > airflow_errors.log
```

### Network & Connectivity Issues

```bash
# Check network connectivity between containers
docker compose exec airflow-scheduler ping -c 3 airflow-postgres
docker compose exec airflow-scheduler ping -c 3 airflow-warehouse

# Test Airflow database connection
docker compose exec airflow-scheduler python -c "
from airflow.settings import Session
try:
    Session().execute('SELECT 1')
    print('✓ Airflow DB connection OK')
except Exception as e:
    print(f'✗ DB connection failed: {e}')
"

# Test warehouse connection
docker compose exec airflow-scheduler psql postgresql://warehouse_user:warehouse_pass@airflow-warehouse:5432/warehouse -c "SELECT 1;"

# Check DNS resolution
docker compose exec airflow-scheduler nslookup airflow-postgres
docker compose exec airflow-scheduler nslookup airflow-warehouse

# View network configuration
docker network inspect airflow-network
```

### Inspect Container Internals

```bash
# Open shell in scheduler container
docker compose exec airflow-scheduler bash

# Check Python package versions
docker compose exec airflow-scheduler pip list | grep airflow

# Verify DAG files are mounted correctly
docker compose exec airflow-scheduler ls -la /opt/airflow/dags/

# Check environment variables
docker compose exec airflow-scheduler env | grep AIRFLOW

# View Airflow configuration
docker compose exec airflow-scheduler airflow config list

# Check disk space inside container
docker compose exec airflow-scheduler df -h
```

---

## Quick Health Dashboard

### Save this as `monitor-airflow.sh` and make it executable

```bash
#!/bin/bash
# Airflow Health Dashboard Script
# Usage: ./monitor-airflow.sh

echo "========================================="
echo "   Airflow Health Dashboard"
echo "   Generated: $(date)"
echo "========================================="
echo ""

echo "📊 Container Status:"
echo "-------------------"
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo ""

echo "💾 Resource Usage:"
echo "------------------"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo ""

echo "📋 Active DAG Runs:"
echo "-------------------"
docker compose exec -T airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id, state, count(*) as count
   FROM dag_run
   WHERE execution_date > now() - interval '24 hours'
   GROUP BY dag_id, state
   ORDER BY dag_id;" 2>/dev/null
echo ""

echo "⚡ Task Instance States (Last 24h):"
echo "------------------------------------"
docker compose exec -T airflow-postgres psql -U airflow -d airflow -c \
  "SELECT state, count(*) as count
   FROM task_instance
   WHERE execution_date > now() - interval '24 hours'
   GROUP BY state
   ORDER BY count DESC;" 2>/dev/null
echo ""

echo "🐌 Long Running Tasks (>5 min):"
echo "--------------------------------"
docker compose exec -T airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          task_id,
          (now() - start_date) as duration
   FROM task_instance
   WHERE state = 'running'
     AND (now() - start_date) > interval '5 minutes'
   ORDER BY duration DESC;" 2>/dev/null
echo ""

echo "🔄 Currently Running DAG Runs:"
echo "------------------------------"
docker compose exec -T airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          (now() - start_date) as duration
   FROM dag_run
   WHERE state = 'running'
   ORDER BY start_date ASC;" 2>/dev/null
echo ""

echo "❌ Recent Errors (last hour):"
echo "-----------------------------"
docker compose logs --since 1h airflow-scheduler 2>&1 | grep -i "error\|exception" | tail -10
echo ""

echo "🔧 Database Connection Pool:"
echo "----------------------------"
docker compose exec -T airflow-postgres psql -U airflow -d airflow -c \
  "SELECT count(*) as active_connections, state
   FROM pg_stat_activity
   WHERE datname = 'airflow'
   GROUP BY state;" 2>/dev/null
echo ""

echo "📈 DAG Performance (Last 7 days - Top 10 slowest):"
echo "--------------------------------------------------"
docker compose exec -T airflow-postgres psql -U airflow -d airflow -c \
  "SELECT dag_id,
          count(*) as runs,
          avg(end_date - start_date) as avg_duration
   FROM dag_run
   WHERE end_date IS NOT NULL
     AND start_date > now() - interval '7 days'
   GROUP BY dag_id
   ORDER BY avg_duration DESC
   LIMIT 10;" 2>/dev/null
echo ""

echo "========================================="
echo "   End of Health Dashboard"
echo "========================================="
```

**Make it executable:**
```bash
chmod +x monitor-airflow.sh
./monitor-airflow.sh
```

### Continuous Monitoring (Watch Mode)

```bash
# Auto-refresh every 5 seconds
watch -n 5 'docker compose exec -T airflow-postgres psql -U airflow -d airflow -c "SELECT state, count(*) FROM task_instance WHERE execution_date > now() - interval '\''1 hour'\'' GROUP BY state;"'

# Monitor running DAGs continuously
watch -n 2 'docker compose exec -T airflow-postgres psql -U airflow -d airflow -c "SELECT dag_id, (now() - start_date) as duration FROM dag_run WHERE state = '\''running'\'';"'

# Monitor container resources continuously
watch -n 3 'docker stats --no-stream'
```

---

## Common Performance Issues & Solutions

### Issue 1: DAG is slow to execute

**Diagnosis:**
```bash
# Find slowest tasks in the DAG
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT task_id, avg(end_date - start_date) as avg_duration
   FROM task_instance
   WHERE dag_id = '<dag_id>' AND end_date IS NOT NULL
   GROUP BY task_id
   ORDER BY avg_duration DESC;"
```

**Potential Solutions:**
- Parallelize tasks using task groups or dynamic task mapping
- Optimize slow tasks (check task logs for bottlenecks)
- Increase `max_active_tasks_per_dag` if tasks are waiting
- Use pools to better manage resource allocation

### Issue 2: DAG is slow to parse

**Diagnosis:**
```bash
# Check DAG parsing logs
docker compose logs airflow-dag-processor | grep "Processing file" | grep "<dag_file>"
```

**Potential Solutions:**
- Avoid heavy imports at the top level of DAG files
- Use lazy loading for connections and variables
- Simplify DAG definition (avoid complex logic in DAG file)
- Reduce number of DAG files or combine related DAGs

### Issue 3: Tasks are queued but not running

**Diagnosis:**
```bash
# Check executor capacity
docker compose exec airflow-scheduler airflow config get-value core parallelism

# Check active tasks
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT state, count(*) FROM task_instance WHERE state IN ('running', 'queued') GROUP BY state;"
```

**Potential Solutions:**
- Increase `parallelism` configuration
- Increase `max_active_tasks_per_dag`
- Check pool slots availability
- Scale executor resources (add workers if using CeleryExecutor)

### Issue 4: Database is slow

**Diagnosis:**
```bash
# Check slow queries
docker compose exec airflow-postgres psql -U airflow -d airflow -c \
  "SELECT pid, now() - query_start as duration, query
   FROM pg_stat_activity
   WHERE state != 'idle' AND now() - query_start > interval '10 seconds';"
```

**Potential Solutions:**
- Run `VACUUM ANALYZE` on Airflow database
- Add indexes to frequently queried tables
- Clean up old task instances and DAG runs
- Increase database resources (memory, CPU)

---

## Best Practices

1. **Regular Cleanup**: Schedule regular cleanup of old DAG runs and task instances
2. **Monitor Proactively**: Set up alerts for long-running tasks or failed DAGs
3. **Resource Limits**: Set appropriate memory and CPU limits for containers
4. **Database Maintenance**: Run VACUUM and ANALYZE regularly on PostgreSQL
5. **Log Rotation**: Ensure logs are rotated to prevent disk space issues
6. **Metric Collection**: Consider integrating with Prometheus/Grafana for historical metrics

---

## Additional Resources

- [Airflow Official Documentation](https://airflow.apache.org/docs/)
- [Airflow CLI Reference](https://airflow.apache.org/docs/apache-airflow/stable/cli-and-env-variables-ref.html)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Docker Monitoring Guide](https://docs.docker.com/config/containers/runmetrics/)