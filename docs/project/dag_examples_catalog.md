# Example DAG Catalog

This catalog provides a comprehensive index of all example DAGs in the Apache Airflow ETL Demo Platform. Each example demonstrates specific patterns, use cases, and Airflow features to help you learn and build production-ready data pipelines.

**Total Examples**: 14 DAGs (4 Beginner, 6 Intermediate, 4 Advanced)

---

## Table of Contents

- [How to Use This Catalog](#how-to-use-this-catalog)
- [Beginner Examples](#beginner-examples)
- [Intermediate Examples](#intermediate-examples)
- [Advanced Examples](#advanced-examples)
- [Learning Path](#learning-path)
- [Quick Reference Matrix](#quick-reference-matrix)

---

## How to Use This Catalog

Each example DAG in this catalog includes:

- **Difficulty Level**: Beginner, Intermediate, or Advanced
- **Primary Pattern**: The main design pattern demonstrated
- **Use Case**: Real-world scenario the DAG addresses
- **Key Learning Objectives**: What you'll learn by studying this example
- **Airflow Features**: Specific Airflow capabilities showcased
- **Estimated Completion Time**: How long it takes to run
- **Dependencies**: Prerequisites or related examples

### Recommended Learning Path

1. Start with **Beginner** examples to understand fundamentals
2. Progress to **Intermediate** examples for common patterns
3. Study **Advanced** examples for production-grade techniques
4. Mix and match patterns from different examples in your own DAGs

---

## Beginner Examples

### 1. Simple Extract-Load Pipeline
**DAG ID**: `demo_simple_extract_load_v1`
**File**: [dags/examples/beginner/demo_simple_extract_load_v1.py](../dags/examples/beginner/demo_simple_extract_load_v1.py)

**Primary Pattern**: Basic ETL workflow
**Difficulty**: ⭐ Beginner

**Use Case**:
Extract data from a source table and load it into a staging area without transformation. Demonstrates the simplest possible data pipeline structure.

**Key Learning Objectives**:
- Understand DAG definition and structure
- Learn task creation with PostgresOperator
- See basic task dependencies (>>)
- Understand execution flow

**Airflow Features**:
- DAG definition with default_args
- PostgresOperator for SQL execution
- Task dependencies
- Connection management

**Estimated Completion Time**: < 1 minute

**Prerequisites**: None - start here!

---

### 2. Scheduled Pipeline with Retry Logic
**DAG ID**: `demo_scheduled_pipeline_v1`
**File**: [dags/examples/beginner/demo_scheduled_pipeline_v1.py](../dags/examples/beginner/demo_scheduled_pipeline_v1.py)

**Primary Pattern**: Scheduled execution with resilience
**Difficulty**: ⭐ Beginner

**Use Case**:
Run a data pipeline on a daily schedule with automatic retry logic for transient failures. Shows production-ready configuration for reliability.

**Key Learning Objectives**:
- Configure schedule intervals (cron expressions)
- Implement retry policies and exponential backoff
- Set task timeouts
- Handle catchup behavior

**Airflow Features**:
- `schedule_interval` configuration
- `retries` and `retry_delay` parameters
- `execution_timeout` settings
- `catchup` flag

**Estimated Completion Time**: < 2 minutes

**Prerequisites**: demo_simple_extract_load_v1

**Related Examples**: demo_failure_recovery_v1 (advanced failure handling)

---

### 3. Data Quality Basics
**DAG ID**: `demo_data_quality_basics_v1`
**File**: [dags/examples/beginner/demo_data_quality_basics_v1.py](../dags/examples/beginner/demo_data_quality_basics_v1.py)

**Primary Pattern**: Basic data validation
**Difficulty**: ⭐ Beginner

**Use Case**:
Validate data quality with schema checks and completeness validation before allowing downstream consumption. Demonstrates defensive data engineering.

**Key Learning Objectives**:
- Implement schema validation
- Add completeness checks (row count validation)
- Understand quality gates in pipelines
- Learn when to halt vs. warn

**Airflow Features**:
- Custom quality check operators
- Task failure handling
- Conditional execution based on checks
- XCom for passing validation results

**Estimated Completion Time**: < 2 minutes

**Prerequisites**: demo_simple_extract_load_v1

**Related Examples**: demo_comprehensive_quality_v1 (advanced quality checks)

---

### 4. Notification Basics
**DAG ID**: `demo_notification_basics_v1`
**File**: [dags/examples/beginner/demo_notification_basics_v1.py](../dags/examples/beginner/demo_notification_basics_v1.py)

**Primary Pattern**: Multi-channel alerting
**Difficulty**: ⭐ Beginner

**Use Case**:
Send notifications via email and MS Teams on pipeline success or failure. Shows how to integrate external communication channels.

**Key Learning Objectives**:
- Configure notification operators
- Send email alerts
- Post to MS Teams channels
- Use callbacks for failure notifications

**Airflow Features**:
- Custom notification operators
- `on_failure_callback` and `on_success_callback`
- Template rendering for messages
- Connection configuration

**Estimated Completion Time**: < 1 minute

**Prerequisites**: demo_simple_extract_load_v1

---

## Intermediate Examples

### 5. Incremental Load with Watermarking
**DAG ID**: `demo_incremental_load_v1`
**File**: [dags/examples/intermediate/demo_incremental_load_v1.py](../dags/examples/intermediate/demo_incremental_load_v1.py)

**Primary Pattern**: Incremental data ingestion
**Difficulty**: ⭐⭐ Intermediate

**Use Case**:
Process only new records since last run using watermark tracking. Demonstrates efficient data synchronization and idempotency.

**Key Learning Objectives**:
- Implement watermark tracking (high water mark pattern)
- Query only new records since last execution
- Ensure idempotent pipeline execution
- Handle initial load vs. incremental load

**Airflow Features**:
- Variable for watermark storage
- SQL with dynamic date filtering
- Idempotent task design
- Execution date templating

**Estimated Completion Time**: < 3 minutes

**Prerequisites**: demo_simple_extract_load_v1, demo_scheduled_pipeline_v1

**Related Examples**: demo_scd_type2_v1 (dimension change tracking)

---

### 6. SCD Type 2 (Slowly Changing Dimensions)
**DAG ID**: `demo_scd_type2_v1`
**File**: [dags/examples/intermediate/demo_scd_type2_v1.py](../dags/examples/intermediate/demo_scd_type2_v1.py)

**Primary Pattern**: Dimension history tracking
**Difficulty**: ⭐⭐ Intermediate

**Use Case**:
Track historical changes in dimension tables with effective dates and current flags. Essential for data warehousing.

**Key Learning Objectives**:
- Implement SCD Type 2 logic (insert new, expire old)
- Manage effective_from and effective_to dates
- Use current_flag for active records
- Handle dimension updates vs. inserts

**Airflow Features**:
- Complex SQL patterns in PostgresOperator
- Multi-step dimension updates
- Transactional integrity
- Historical data preservation

**Estimated Completion Time**: < 3 minutes

**Prerequisites**: demo_incremental_load_v1

**Related Examples**: demo_incremental_load_v1

---

### 7. Parallel Processing (Fan-Out/Fan-In)
**DAG ID**: `demo_parallel_processing_v1`
**File**: [dags/examples/intermediate/demo_parallel_processing_v1.py](../dags/examples/intermediate/demo_parallel_processing_v1.py)

**Primary Pattern**: Parallel task execution
**Difficulty**: ⭐⭐ Intermediate

**Use Case**:
Process multiple product categories in parallel, then aggregate results. Shows how to maximize throughput with concurrency.

**Key Learning Objectives**:
- Implement fan-out pattern (one-to-many)
- Implement fan-in pattern (many-to-one aggregation)
- Use TaskGroups for organization
- Pass data between tasks via XCom

**Airflow Features**:
- Dynamic task generation
- TaskGroup for logical grouping
- XCom for inter-task communication
- Parallel execution with dependencies

**Estimated Completion Time**: < 3 minutes

**Prerequisites**: demo_simple_extract_load_v1

---

### 8. Spark Standalone Integration
**DAG ID**: `demo_spark_standalone_v1`
**File**: [dags/examples/intermediate/demo_spark_standalone_v1.py](../dags/examples/intermediate/demo_spark_standalone_v1.py)

**Primary Pattern**: Big data processing orchestration
**Difficulty**: ⭐⭐ Intermediate

**Use Case**:
Submit and monitor Spark jobs on standalone cluster for large-scale data processing. Demonstrates big data workflow integration.

**Key Learning Objectives**:
- Submit Spark applications from Airflow
- Monitor Spark job status
- Retrieve Spark logs
- Configure Spark resources

**Airflow Features**:
- Custom Spark operators
- Job submission and monitoring
- External system integration
- Resource management

**Estimated Completion Time**: < 4 minutes

**Prerequisites**: demo_simple_extract_load_v1

**Related Examples**: demo_spark_multi_cluster_v1 (multi-cluster orchestration)

---

### 9. Cross-DAG Dependencies
**DAG ID**: `demo_cross_dag_dependency_v1`
**File**: [dags/examples/intermediate/demo_cross_dag_dependency_v1.py](../dags/examples/intermediate/demo_cross_dag_dependency_v1.py)

**Primary Pattern**: DAG coordination and orchestration
**Difficulty**: ⭐⭐ Intermediate

**Use Case**:
Coordinate multiple DAGs where one DAG waits for another to complete before proceeding. Shows complex workflow orchestration.

**Key Learning Objectives**:
- Use ExternalTaskSensor to wait for other DAGs
- Trigger downstream DAGs with TriggerDagRunOperator
- Pass data between DAGs
- Implement conditional DAG triggering

**Airflow Features**:
- ExternalTaskSensor for waiting
- TriggerDagRunOperator for triggering
- Cross-DAG XCom communication
- Branching based on upstream results

**Estimated Completion Time**: < 3 minutes

**Prerequisites**: demo_simple_extract_load_v1, demo_data_quality_basics_v1

**Helper DAG**: demo_cross_dag_dependency_helper_v1

---

### 10. Cross-DAG Dependency Helper
**DAG ID**: `demo_cross_dag_dependency_helper_v1`
**File**: [dags/examples/intermediate/demo_cross_dag_dependency_v1.py](../dags/examples/intermediate/demo_cross_dag_dependency_v1.py) (same file)

**Primary Pattern**: Triggered DAG pattern
**Difficulty**: ⭐⭐ Intermediate

**Use Case**:
Demonstrates a DAG that can be triggered programmatically by another DAG, showing the "triggered" side of cross-DAG orchestration.

**Key Learning Objectives**:
- Understand DAG triggering mechanics
- Access trigger configuration
- Handle programmatic DAG execution
- Log trigger metadata

**Airflow Features**:
- DagRun configuration
- Trigger context access
- Manual vs. triggered execution
- DAG coordination patterns

**Estimated Completion Time**: < 1 minute

**Prerequisites**: demo_cross_dag_dependency_v1

---

## Advanced Examples

### 11. Multi-Cluster Spark Orchestration
**DAG ID**: `demo_spark_multi_cluster_v1`
**File**: [dags/examples/advanced/demo_spark_multi_cluster_v1.py](../dags/examples/advanced/demo_spark_multi_cluster_v1.py)

**Primary Pattern**: Multi-environment job orchestration
**Difficulty**: ⭐⭐⭐ Advanced

**Use Case**:
Submit Spark jobs to different cluster types (Standalone, YARN, Kubernetes) based on workload characteristics. Shows enterprise-grade Spark orchestration.

**Key Learning Objectives**:
- Configure multiple Spark cluster types
- Route jobs to appropriate clusters
- Manage different resource profiles
- Handle cluster-specific configurations

**Airflow Features**:
- Multiple custom Spark operators
- Cluster-specific configurations
- Resource optimization
- Multi-environment orchestration

**Estimated Completion Time**: < 5 minutes

**Prerequisites**: demo_spark_standalone_v1

---

### 12. Comprehensive Data Quality Validation
**DAG ID**: `demo_comprehensive_quality_v1`
**File**: [dags/examples/advanced/demo_comprehensive_quality_v1.py](../dags/examples/advanced/demo_comprehensive_quality_v1.py)

**Primary Pattern**: Production-grade quality assurance
**Difficulty**: ⭐⭐⭐ Advanced

**Use Case**:
Validate data across all 5 quality dimensions (schema, completeness, freshness, uniqueness, null rate) with severity-based workflow control and automated alerting.

**Key Learning Objectives**:
- Implement all 5 quality check types
- Use severity levels (CRITICAL vs. WARNING)
- Aggregate quality results
- Send quality alerts
- Understand when to halt pipeline vs. continue with warnings

**Airflow Features**:
- TaskGroup for parallel quality checks
- Custom quality operators
- Result aggregation
- Conditional alerting
- Exception handling for critical failures

**Estimated Completion Time**: < 3 minutes

**Prerequisites**: demo_data_quality_basics_v1

**Related Examples**: demo_data_quality_basics_v1

---

### 13. Event-Driven Pipeline
**DAG ID**: `demo_event_driven_pipeline_v1`
**File**: [dags/examples/advanced/demo_event_driven_pipeline_v1.py](../dags/examples/advanced/demo_event_driven_pipeline_v1.py)

**Primary Pattern**: Reactive workflow (event-triggered)
**Difficulty**: ⭐⭐⭐ Advanced

**Use Case**:
Trigger pipeline execution when files arrive in landing zone, with dynamic routing based on file attributes. Shows event-driven vs. schedule-driven architecture.

**Key Learning Objectives**:
- Use FileSensor to detect file arrival
- Extract file metadata for routing decisions
- Branch based on runtime file attributes
- Implement idempotent file processing
- Archive processed files

**Airflow Features**:
- FileSensor for event detection
- BranchPythonOperator for dynamic routing
- File metadata extraction
- Checksum-based idempotency
- Dynamic workflow branching

**Estimated Completion Time**: < 3 minutes

**Prerequisites**: demo_simple_extract_load_v1

---

### 14. Failure Recovery and Compensation
**DAG ID**: `demo_failure_recovery_v1`
**File**: [dags/examples/advanced/demo_failure_recovery_v1.py](../dags/examples/advanced/demo_failure_recovery_v1.py)

**Primary Pattern**: Graceful degradation and cleanup
**Difficulty**: ⭐⭐⭐ Advanced

**Use Case**:
Handle failures gracefully with compensation logic, cleanup tasks, and state recovery. Demonstrates production-ready error handling.

**Key Learning Objectives**:
- Implement compensation tasks
- Use trigger rules for cleanup
- Handle partial pipeline failures
- Recover from interrupted state
- Rollback on failure

**Airflow Features**:
- `trigger_rule` settings (ALL_DONE, ALL_FAILED, etc.)
- `on_failure_callback` for cleanup
- Compensation task patterns
- State recovery mechanisms
- Error propagation control

**Estimated Completion Time**: < 4 minutes

**Prerequisites**: demo_scheduled_pipeline_v1

**Related Examples**: demo_scheduled_pipeline_v1 (basic retry)

---

## Learning Path

### Path 1: Pipeline Fundamentals (Est. 30 minutes)
Perfect for data engineers new to Airflow.

1. `demo_simple_extract_load_v1` - Understand DAG basics
2. `demo_scheduled_pipeline_v1` - Add scheduling and retries
3. `demo_notification_basics_v1` - Integrate alerting
4. `demo_data_quality_basics_v1` - Add quality checks

**Outcome**: Build simple, reliable, monitored pipelines

---

### Path 2: Advanced ETL Patterns (Est. 45 minutes)
For engineers building production data warehouses.

1. `demo_incremental_load_v1` - Efficient data synchronization
2. `demo_scd_type2_v1` - Dimension change tracking
3. `demo_parallel_processing_v1` - Performance optimization
4. `demo_comprehensive_quality_v1` - Production-grade validation

**Outcome**: Implement enterprise ETL patterns

---

### Path 3: Big Data Integration (Est. 30 minutes)
For engineers orchestrating Spark workloads.

1. `demo_spark_standalone_v1` - Basic Spark integration
2. `demo_spark_multi_cluster_v1` - Multi-cluster orchestration
3. `demo_event_driven_pipeline_v1` - Event-triggered processing

**Outcome**: Orchestrate complex Spark workflows

---

### Path 4: Production Resilience (Est. 30 minutes)
For engineers building fault-tolerant systems.

1. `demo_scheduled_pipeline_v1` - Retry and timeout basics
2. `demo_failure_recovery_v1` - Compensation and cleanup
3. `demo_cross_dag_dependency_v1` - Multi-DAG coordination
4. `demo_comprehensive_quality_v1` - Quality gates

**Outcome**: Build resilient, production-ready pipelines

---

## Quick Reference Matrix

| DAG | Difficulty | Pattern | Schedule | Sensors | Quality | Notifications | Spark | Cross-DAG |
|-----|-----------|---------|----------|---------|---------|--------------|-------|-----------|
| demo_simple_extract_load_v1 | Beginner | Basic ETL | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| demo_scheduled_pipeline_v1 | Beginner | Scheduled | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| demo_data_quality_basics_v1 | Beginner | Quality | ❌ | ❌ | ✅ Basic | ❌ | ❌ | ❌ |
| demo_notification_basics_v1 | Beginner | Alerting | ❌ | ❌ | ❌ | ✅ Email/Teams | ❌ | ❌ |
| demo_incremental_load_v1 | Intermediate | Incremental | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| demo_scd_type2_v1 | Intermediate | SCD Type 2 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| demo_parallel_processing_v1 | Intermediate | Fan-Out/In | ❌ | ❌ | ❌ | ✅ Summary | ❌ | ❌ |
| demo_spark_standalone_v1 | Intermediate | Spark | ❌ | ❌ | ❌ | ❌ | ✅ Standalone | ❌ |
| demo_cross_dag_dependency_v1 | Intermediate | Orchestration | ❌ | ✅ External | ✅ Gates | ❌ | ❌ | ✅ |
| demo_cross_dag_dependency_helper_v1 | Intermediate | Triggered | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| demo_spark_multi_cluster_v1 | Advanced | Multi-Cluster | ❌ | ❌ | ❌ | ❌ | ✅ All Types | ❌ |
| demo_comprehensive_quality_v1 | Advanced | Quality Suite | ❌ | ❌ | ✅ All 5 | ✅ Alerts | ❌ | ❌ |
| demo_event_driven_pipeline_v1 | Advanced | Event-Driven | ❌ | ✅ File | ❌ | ❌ | ❌ | ❌ |
| demo_failure_recovery_v1 | Advanced | Resilience | ❌ | ❌ | ❌ | ✅ Failure | ❌ | ❌ |

---

## Pattern Index

### By Airflow Feature

**Scheduling & Timing**:
- demo_scheduled_pipeline_v1
- demo_incremental_load_v1
- demo_scd_type2_v1

**Sensors**:
- demo_cross_dag_dependency_v1 (ExternalTaskSensor)
- demo_event_driven_pipeline_v1 (FileSensor)

**Data Quality**:
- demo_data_quality_basics_v1 (schema, completeness)
- demo_comprehensive_quality_v1 (all 5 dimensions)

**Notifications**:
- demo_notification_basics_v1 (email, Teams)
- demo_parallel_processing_v1 (summary alerts)
- demo_comprehensive_quality_v1 (quality alerts)
- demo_failure_recovery_v1 (failure alerts)

**Spark Integration**:
- demo_spark_standalone_v1 (standalone cluster)
- demo_spark_multi_cluster_v1 (standalone, YARN, K8s)

**Cross-DAG Coordination**:
- demo_cross_dag_dependency_v1 (sensors + triggers)
- demo_cross_dag_dependency_helper_v1 (triggered DAG)

### By ETL Pattern

**Extract-Load**:
- demo_simple_extract_load_v1

**Incremental Sync**:
- demo_incremental_load_v1

**Dimension Management**:
- demo_scd_type2_v1

**Parallel Processing**:
- demo_parallel_processing_v1

**Event-Driven**:
- demo_event_driven_pipeline_v1

### By Reliability Pattern

**Retry & Timeout**:
- demo_scheduled_pipeline_v1

**Failure Handling**:
- demo_failure_recovery_v1

**Data Quality Gates**:
- demo_data_quality_basics_v1
- demo_comprehensive_quality_v1

---

## Running the Examples

### Prerequisites

1. Start the local development environment:
   ```bash
   docker-compose up -d
   ```

2. Access Airflow UI:
   ```
   http://localhost:8080
   Username: admin
   Password: admin
   ```

### Running a Specific Example

1. Navigate to the DAGs view in Airflow UI
2. Find the example DAG by name (e.g., `demo_simple_extract_load_v1`)
3. Toggle the DAG to "On" (enable it)
4. Click "Trigger DAG" to run manually
5. Monitor execution in Graph View or Grid View

### Viewing Results

- **Logs**: Click on task → View Log
- **XCom**: Click on task → XCom
- **Graph**: Use Graph View to see task dependencies
- **Gantt**: Use Gantt View to analyze timing and parallelism

---

## Troubleshooting Common Issues

### DAG Not Appearing in UI

- **Cause**: DAG parsing error
- **Solution**: Check Airflow logs for import errors
- **Command**: `docker-compose logs airflow-scheduler | grep ERROR`

### Task Failures

- **Cause**: Missing connections, configuration issues
- **Solution**: Check task logs, verify connection configurations
- **Common Issue**: Warehouse connection not configured - see [development.md](development.md)

### Long Execution Times

- **Cause**: Resource constraints, sequential execution
- **Solution**: Check parallelism settings, review task dependencies
- **Optimization**: Use `demo_parallel_processing_v1` pattern for concurrency

---

## Contributing New Examples

Want to add a new example DAG? Follow these guidelines:

1. **File Naming**: `demo_<pattern_name>_v1.py`
2. **Location**: Place in appropriate difficulty folder
3. **Documentation**: Include comprehensive module docstring
4. **Tags**: Add appropriate tags (difficulty, pattern, features)
5. **Self-Contained**: Ensure DAG runs independently
6. **Execution Time**: Target < 5 minutes
7. **Update Catalog**: Add entry to this document

See existing examples for structure and style guidelines.

---

## Additional Resources

- [Airflow Documentation](https://airflow.apache.org/docs/)
- [DAG Configuration Guide](dag_configuration.md)
- [Operator Guide](operator_guide.md)
- [Development Setup](development.md)
- [Architecture Overview](architecture.md)

---

## Summary Statistics

- **Total Example DAGs**: 14
- **Total Patterns Demonstrated**: 12+
- **Beginner Examples**: 4
- **Intermediate Examples**: 6
- **Advanced Examples**: 4
- **Average Execution Time**: 2.5 minutes
- **Airflow Features Covered**: 25+

**All examples are production-ready, well-documented, and independently executable.**