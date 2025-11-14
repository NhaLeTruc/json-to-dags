# ADR 001: Downgrade from Airflow 3.1.0 to 2.10.5

## Status

**Accepted** - Implemented on 2025-11-14

## Context

The project was initially built using Apache Airflow 3.1.0 (released late 2024), which represented the latest major version with significant architectural changes including:

- New DAG processor architecture (separate from scheduler)
- API-first design with `api-server` command replacing `webserver`
- Enhanced task runner isolation
- Breaking changes in hook interfaces and executor behavior

### Issues Encountered with Airflow 3.1.0

1. **Scheduler Stability Issues**
   - LocalExecutor experiencing task runner process management regressions
   - Scheduler heartbeat timeouts causing task execution delays
   - Zombie task detection false positives

2. **Ecosystem Maturity**
   - Limited provider package compatibility (many still targeting 2.x)
   - Community adoption lag (most production deployments on 2.x)
   - Sparse documentation for 3.x-specific issues

3. **Production Readiness Concerns**
   - Airflow 3.0 marked as experimental/preview in some contexts
   - Breaking API changes requiring significant downstream updates
   - Reduced stability compared to mature 2.x branch

### Business Requirements

- **Demo Platform**: This is a learning/demo platform requiring stability over cutting-edge features
- **Developer Experience**: Users need reliable DAG execution for learning workflows
- **Production Patterns**: Should demonstrate production-ready practices, not experimental features

## Decision

**We will downgrade from Airflow 3.1.0 to Airflow 2.10.5** and maintain compatibility with the 2.x series until 3.x reaches production maturity.

### Rationale

1. **Stability Over Features**: Airflow 2.10.5 is battle-tested in production environments
2. **Ecosystem Support**: Full provider package compatibility and community support
3. **Learning Clarity**: Users learn stable patterns, not experimental architectures
4. **Upgrade Path**: Clear migration path to 3.x when mature (documented patterns exist)

## Consequences

### Positive

- **Improved Stability**: LocalExecutor runs reliably without process management issues
- **Better Documentation**: Extensive 2.x documentation and community knowledge
- **Provider Compatibility**: All Airflow providers fully support 2.10.5
- **Production Alignment**: Matches current production best practices (2024-2025)
- **Lower Maintenance**: Fewer edge cases and workarounds needed

### Negative

- **Missing 3.x Features**: Don't showcase new DAG processor architecture
- **Future Migration**: Will need to migrate to 3.x eventually when stable
- **Deprecated Patterns**: Some 2.x patterns will be deprecated in future 3.x
- **API Changes**: Lost opportunity to demonstrate 3.x API improvements

### Neutral

- **DAG Syntax**: Minimal changes (mostly `schedule` parameter compatibility)
- **Docker Images**: Official images available for both versions
- **Hook Interfaces**: Backward compatibility maintained in WarehouseHook

## Implementation

### Files Modified

1. **requirements.txt**: `apache-airflow==3.1.0` → `2.10.5`
2. **docker/airflow/Dockerfile**: Base image `3.1.0-python3.12` → `2.10.5-python3.12`
3. **docker-compose.yml**: Image and configuration updates
4. **src/hooks/warehouse_hook.py**: Backward compatibility support

### Migration Steps Taken

1. Updated all version references in deployment files
2. Adjusted docker-compose service configurations
3. Fixed schema compatibility (callback type handling)
4. Updated documentation to reflect 2.10.5 as target
5. Tested all 14 example DAGs for compatibility
6. Validated CI/CD pipeline execution

### Backward Compatibility

The codebase maintains compatibility patterns:
```python
# WarehouseHook supports both 2.x and 3.x parameter names
def __init__(self, warehouse_conn_id=None, postgres_conn_id=None):
    conn_id = warehouse_conn_id or postgres_conn_id or "warehouse_default"
```

## Alternatives Considered

### 1. Stay on Airflow 3.1.0 and Fix Issues

**Rejected**: Would require significant effort debugging experimental features with limited community support.

### 2. Downgrade to Airflow 2.8.x (LTS)

**Rejected**: While very stable, 2.10.5 offers better Python 3.12 support and more recent bug fixes while maintaining stability.

### 3. Wait for Airflow 3.2+

**Rejected**: Uncertain timeline, and demo platform needs stability now.

## References

- [Airflow 2.10.5 Release Notes](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html)
- [Airflow 3.0 Migration Guide](https://airflow.apache.org/docs/apache-airflow/stable/upgrading-to-3.html)
- Internal: `docs/migration_plan.md` (468 lines detailing migration process)
- Internal: `docs/AIRFLOW_3_MIGRATION_GUIDE.md` (issues encountered)
- Internal: `docs/scheduler_stability_fixes.md` (LocalExecutor problems)

## Future Considerations

When Airflow 3.x reaches production maturity (estimated late 2025):

1. Re-evaluate stability and ecosystem support
2. Create upgrade plan leveraging existing migration documentation
3. Update demo examples to showcase 3.x-specific features
4. Maintain backward-compatible patterns during transition

## Versioning Impact

- **Current**: Airflow 2.10.5 + Python 3.12
- **Providers**: All using latest 2.x-compatible versions
- **SQLAlchemy**: Pinned to 1.4.x (Airflow 2.x requirement)

---

**Decision made by**: Development Team
**Date**: 2025-11-14
**Last updated**: 2025-11-14
**Supersedes**: Initial decision to use Airflow 3.1.0
**Related ADRs**: None (first ADR in this project)
