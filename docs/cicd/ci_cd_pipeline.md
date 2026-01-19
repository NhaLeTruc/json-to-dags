# CI/CD Pipeline Architecture

This document describes the automated CI/CD pipeline architecture for the Apache Airflow ETL Demo Platform, including workflow design, deployment strategies, and operational procedures.

---

## Table of Contents

- [Overview](#overview)
- [Pipeline Architecture](#pipeline-architecture)
- [CI Workflow](#ci-workflow)
- [CD Workflows](#cd-workflows)
- [Deployment Strategies](#deployment-strategies)
- [Rollback Procedures](#rollback-procedures)
- [Monitoring and Alerts](#monitoring-and-alerts)
- [Best Practices](#best-practices)

---

## Overview

### Goals

The CI/CD pipeline provides:

1. **Automated Validation**: Every code change is automatically tested
2. **Fast Feedback**: Developers receive feedback within 10-15 minutes
3. **Deployment Automation**: Reduce manual deployment errors
4. **Safe Production Releases**: Multi-stage approval gates
5. **Rollback Capability**: Quick recovery from failed deployments

### Pipeline Stages

```
┌─────────────────┐
│  Code Push/PR   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   CI Pipeline   │ ◄── Automated
│  - Lint         │
│  - Test         │
│  - DAG Validate │
│  - Security     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Merge to Main  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Staging Deploy  │ ◄── Auto-triggered
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Smoke Tests    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Manual Approval │ ◄── Human gate
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Production      │ ◄── Manual trigger
│ Deployment      │
└─────────────────┘
```

---

## Pipeline Architecture

### Workflow Files

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| CI Pipeline | `.github/workflows/ci.yml` | Push, PR | Automated testing and validation |
| Staging Deployment | `.github/workflows/cd-staging.yml` | Push to main, Manual | Deploy to staging environment |
| Production Deployment | `.github/workflows/cd-production.yml` | Manual only | Deploy to production with approval |

### Infrastructure Requirements

**CI/CD Runner**:
- **Platform**: GitHub Actions (hosted runners)
- **OS**: Ubuntu Latest
- **Resources**: Standard (2 CPU, 7GB RAM)

**Test Environment**:
- **Database**: PostgreSQL 15 (Docker service)
- **Python**: 3.11
- **Airflow**: 2.8+

**Deployment Targets**:
- **Staging**: Isolated staging server/cluster
- **Production**: Production Airflow cluster

---

## CI Workflow

### Workflow: `.github/workflows/ci.yml`

#### Trigger Conditions

```yaml
on:
  push:
    branches: [ main, develop, 'feature/**' ]
  pull_request:
    branches: [ main, develop ]
  workflow_dispatch:
```

**Runs on**:
- Every push to main, develop, or feature branches
- Every pull request to main or develop
- Manual trigger via GitHub UI

#### Jobs

##### 1. Lint Job

**Purpose**: Code quality and style checking

**Steps**:
1. Checkout code
2. Setup Python 3.11
3. Install linting tools (ruff, black, mypy)
4. Run ruff (linting)
5. Run black (formatting check)
6. Run mypy (type checking - optional)

**Duration**: ~2 minutes

**Failure Conditions**:
- Ruff finds linting errors
- Black finds formatting issues
- Type checking errors (warning only)

##### 2. Test Job

**Purpose**: Unit and integration testing

**Depends On**: Lint job success

**Steps**:
1. Checkout code
2. Setup Python 3.11
3. Start PostgreSQL service
4. Install dependencies
5. Initialize Airflow DB
6. Run unit tests
7. Run integration tests (non-slow)
8. Generate coverage report
9. Upload coverage artifact

**Duration**: ~8-10 minutes

**Failure Conditions**:
- Any unit test fails
- Any integration test fails
- Test timeout

##### 3. DAG Validation Job

**Purpose**: Validate all DAG files

**Depends On**: Lint job success

**Steps**:
1. Checkout code
2. Setup Python 3.11
3. Install Airflow
4. Load all DAGs with DagBag
5. Check for import errors
6. Verify no circular dependencies

**Duration**: ~3 minutes

**Failure Conditions**:
- DAG import errors
- Circular task dependencies detected
- Missing required DAG attributes

##### 4. Security Scan Job

**Purpose**: Dependency vulnerability scanning

**Depends On**: Lint job success

**Steps**:
1. Checkout code
2. Install safety tool
3. Scan requirements.txt for vulnerabilities
4. Check for hardcoded secrets (grep-based)

**Duration**: ~2 minutes

**Failure Conditions**:
- Critical vulnerabilities (warning only)
- Obvious hardcoded secrets found

##### 5. Build Summary Job

**Purpose**: Aggregate results and report status

**Depends On**: All previous jobs (runs always)

**Steps**:
1. Check status of all jobs
2. Fail if critical jobs failed
3. Generate summary report
4. Post comment to PR (if applicable)

**Duration**: <1 minute

### CI Metrics

**Target Metrics**:
- **Total CI Time**: < 15 minutes
- **Pass Rate**: > 95%
- **Mean Time to Feedback**: < 10 minutes

**Current Performance**:
- Lint: ~2 minutes
- Test: ~8-10 minutes
- DAG Validation: ~3 minutes
- Security: ~2 minutes
- **Total**: ~13-15 minutes

---

## CD Workflows

### Staging Deployment

**Workflow**: `.github/workflows/cd-staging.yml`

#### Trigger

```yaml
on:
  push:
    branches: [ main ]
  workflow_dispatch:
```

**Automatically runs on**: Merge to main branch

#### Jobs

##### 1. Pre-Deployment Validation

**Steps**:
1. Validate DAGs one final time
2. Run smoke tests
3. Ensure no import errors

##### 2. Deploy to Staging

**Steps**:
1. Create deployment artifact (tar.gz)
2. Upload artifact for audit trail
3. Deploy to staging server
4. Restart Airflow services

**Deployment Methods** (choose based on infrastructure):

- **SSH Deployment**:
  ```bash
  scp deployment.tar.gz user@staging:/opt/airflow/
  ssh user@staging 'cd /opt/airflow && tar -xzf deployment.tar.gz'
  ssh user@staging 'sudo systemctl restart airflow-scheduler'
  ```

- **Docker Deployment**:
  ```bash
  docker build -t airflow:staging-${SHA} .
  docker push airflow:staging-${SHA}
  kubectl set image deployment/airflow scheduler=airflow:staging-${SHA}
  ```

##### 3. Post-Deployment Tests

**Steps**:
1. Wait for services to stabilize (30s)
2. Check health endpoints
3. Verify DAG count
4. Run smoke tests

##### 4. Notification

**Steps**:
1. Send deployment status to Slack
2. Email team on failure
3. Log deployment to audit trail

#### Rollback

**Automatic**: No (manual intervention required)

**Procedure**:
1. Identify last successful deployment
2. Redeploy previous version
3. Verify rollback success

---

### Production Deployment

**Workflow**: `.github/workflows/cd-production.yml`

#### Trigger

```yaml
on:
  workflow_dispatch:
    inputs:
      version: (required)
      reason: (required)
      skip_tests: (optional, default: false)
```

**Runs on**: Manual trigger ONLY with required inputs

#### Jobs

##### 1. Approval Check

**Environment**: `production` (requires manual approval)

**Reviewers**: 2 required

**Wait Timer**: 5 minutes (cooling-off period)

**Steps**:
1. Log deployment request
2. Validate inputs (version, reason)
3. Wait for manual approval

##### 2. Pre-Deployment Validation

**Steps**:
1. Checkout specified version
2. Verify version exists
3. Validate all DAGs
4. Run critical tests
5. Security scan

##### 3. Create Backup

**Steps**:
1. Tag current production state
2. Backup DAG files
3. Store backup artifact (90-day retention)

##### 4. Deploy to Production

**Environment**: `production`

**Steps**:
1. Create production artifact
2. Calculate checksum
3. Deploy to production servers
4. Gradual traffic shift (if blue-green)

**Deployment Strategy**: Blue-Green (recommended)

```
1. Deploy to "green" environment (new version)
2. Run health checks on green
3. Run smoke tests on green
4. Shift 10% traffic to green
5. Monitor for 5 minutes
6. Shift 50% traffic to green
7. Monitor for 5 minutes
8. Shift 100% traffic to green
9. Decommission "blue" (old version)
```

##### 5. Post-Deployment Validation

**Steps**:
1. Wait 60 seconds for stabilization
2. Run production smoke tests
3. Verify DAG count
4. Check scheduler health
5. Monitor error rates

##### 6. Deployment Report

**Steps**:
1. Generate deployment report
2. Send notifications (Slack, email, PagerDuty)
3. Log to deployment history

##### 7. Emergency Rollback (On Failure)

**Trigger**: If deployment or validation fails

**Steps**:
1. Alert on-call engineer
2. Restore from backup
3. Redeploy previous version
4. Notify stakeholders

---

## Deployment Strategies

### Blue-Green Deployment

**Concept**: Maintain two identical production environments (Blue and Green)

**Advantages**:
- Zero-downtime deployments
- Instant rollback (switch traffic back)
- Full testing before cutover

**Process**:
```
┌──────────┐
│  Blue    │ ◄── Current production (receiving traffic)
│ (v1.0.0) │
└──────────┘

┌──────────┐
│  Green   │ ◄── Deploy new version
│ (v1.1.0) │
└──────────┘

Test Green → Switch traffic → Green becomes production → Decommission Blue
```

**Implementation**:
- Load balancer switches traffic between Blue and Green
- Kubernetes: Update service selector
- AWS: Route 53 weighted routing

### Canary Deployment

**Concept**: Gradually roll out to subset of users

**Advantages**:
- Detect issues with limited blast radius
- Gradual confidence building
- Real-world testing

**Process**:
```
v1.0.0: 100% traffic
      ↓
v1.0.0: 90% traffic | v1.1.0: 10% traffic (canary)
      ↓ (monitor for 10 minutes)
v1.0.0: 50% traffic | v1.1.0: 50% traffic
      ↓ (monitor for 10 minutes)
v1.1.0: 100% traffic
```

### Rolling Deployment

**Concept**: Gradually update instances one-by-one

**Advantages**:
- Resource efficient
- No extra infrastructure needed

**Process**:
```
Instance 1: v1.0.0 → v1.1.0 ✓
Instance 2: v1.0.0 → v1.1.0 ✓
Instance 3: v1.0.0 → v1.1.0 ✓
```

**Recommended for Airflow**:
1. Update scheduler first
2. Update webserver
3. Update workers

---

## Rollback Procedures

### Staging Rollback

**Trigger**: Post-deployment tests fail

**Procedure**:
1. Identify last successful staging deployment
2. Redeploy previous artifact
3. Restart services
4. Verify rollback

**Automation**: Manual (low risk)

### Production Rollback

**Trigger**: Critical issues detected post-deployment

**Types**:

#### 1. Immediate Rollback (Blue-Green)

**When**: Critical production issue detected

**Steps**:
1. Switch load balancer back to Blue environment
2. Verify Blue is healthy
3. Investigate Green issues

**Time**: < 1 minute

#### 2. Artifact Rollback

**When**: Issues discovered after full cutover

**Steps**:
1. Retrieve previous production backup artifact
2. Trigger production deployment workflow with previous version
3. Follow full deployment process with previous version

**Time**: ~15-20 minutes

#### 3. Database Rollback (if schema changed)

**When**: Deployment included schema changes

**Steps**:
1. Rollback application code
2. Run database migration rollback script
3. Verify data integrity

**Time**: Variable (depends on data size)

### Rollback Decision Matrix

| Severity | Impact | Rollback Type | Timeline |
|----------|--------|---------------|----------|
| Critical | Production down | Immediate (Blue-Green) | < 1 min |
| High | Data corruption risk | Immediate + DB rollback | < 5 min |
| Medium | Feature broken | Artifact rollback | < 20 min |
| Low | Minor UI issue | Hotfix forward | Next deployment |

---

## Monitoring and Alerts

### CI/CD Metrics

**Track**:
- Build success rate
- Build duration (P50, P95, P99)
- Test coverage trends
- DAG validation failure rate
- Deployment frequency
- Deployment success rate
- Mean time to recovery (MTTR)

**Tools**:
- GitHub Actions insights
- Custom dashboards (Grafana)
- Deployment tracking (Jira, linear)

### Alerts

**CI Alerts**:
- ❌ Main branch CI fails → Alert team lead
- ⚠️  Coverage drops below 80% → Warning to team
- ❌ Security vulnerabilities detected → Alert security team

**CD Alerts**:
- ❌ Staging deployment fails → Alert on-call engineer
- ❌ Production deployment fails → PagerDuty incident
- ✅ Production deployment succeeds → Slack notification
- ⚠️  Rollback triggered → Immediate PagerDuty + Slack

**Integration**:
- Slack: #deployments channel
- PagerDuty: Critical alerts
- Email: Team distribution list

---

## Best Practices

### Development Workflow

1. **Create feature branch** from main
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Develop locally** with tests
   ```bash
   pytest tests/
   ruff check .
   black .
   ```

3. **Push and create PR**
   ```bash
   git push origin feature/my-feature
   # Create PR in GitHub
   ```

4. **CI runs automatically** - wait for green checks

5. **Address feedback** from code review and CI

6. **Squash and merge** to main

7. **Staging deploy** happens automatically

8. **Promote to production** when ready (manual)

### Pre-Deployment Checklist

Before triggering production deployment:

- [ ] All CI checks passed on main
- [ ] Code reviewed and approved
- [ ] Staging deployment successful
- [ ] Smoke tests passed on staging
- [ ] Database migrations tested (if applicable)
- [ ] Rollback plan documented
- [ ] Stakeholders notified
- [ ] On-call engineer available
- [ ] Change ticket created
- [ ] Deployment reason documented

### Post-Deployment Checklist

After production deployment:

- [ ] Health checks passed
- [ ] DAG count verified
- [ ] No import errors
- [ ] Scheduler running
- [ ] Monitor error rates (15 minutes)
- [ ] Check Airflow logs
- [ ] Verify critical DAGs
- [ ] Update deployment log
- [ ] Send completion notification
- [ ] Close change ticket

---

## Deployment Runbook

### Staging Deployment

**Frequency**: Automatic on main merge (multiple times per day)

**Process**:
1. Merge PR to main
2. CI pipeline completes
3. Staging deployment triggers automatically
4. Monitor GitHub Actions for status
5. If failed, investigate and fix forward

### Production Deployment

**Frequency**: Manual, as needed (weekly recommended)

**Process**:

1. **Pre-Deployment** (Day before):
   - Review main branch changes since last deployment
   - Verify staging is stable
   - Schedule deployment window
   - Notify stakeholders

2. **Deployment** (Deployment day):
   - Navigate to **Actions → Deploy to Production**
   - Click **Run workflow**
   - Fill in:
     - **Version**: main or specific SHA
     - **Reason**: Ticket number + description
   - Click **Run workflow**
   - Wait for approval (2 reviewers)
   - Monitor deployment progress
   - Watch for alerts

3. **Post-Deployment** (After deployment):
   - Monitor for 30 minutes
   - Check error rates
   - Verify critical DAGs
   - Send completion notification
   - Update documentation if needed

4. **Rollback** (If issues):
   - Assess severity
   - Decide rollback vs. fix-forward
   - Execute rollback procedure
   - Investigate root cause
   - Plan remediation

---

## Troubleshooting

### Common Issues

#### CI Pipeline Fails

**Issue**: Lint errors

**Solution**:
```bash
ruff check . --fix
black .
git add .
git commit -m "Fix linting issues"
git push
```

**Issue**: Test failures

**Solution**:
```bash
pytest tests/unit/test_failing_module.py -v
# Fix issues
pytest tests/
git commit -m "Fix failing tests"
git push
```

**Issue**: DAG validation fails

**Solution**:
```python
# Load DAGs locally to debug
from airflow.models import DagBag
dag_bag = DagBag(dag_folder='dags/')
print(dag_bag.import_errors)  # Shows errors
```

#### Deployment Fails

**Issue**: Artifact upload fails

**Solution**: Check GitHub Actions artifact size limit (check workflow logs)

**Issue**: SSH connection fails

**Solution**: Verify SSH key is correctly configured in secrets

**Issue**: Service restart fails

**Solution**: Check service logs on target server

#### Post-Deployment Issues

**Issue**: DAGs not appearing

**Solution**: Check Airflow scheduler logs, verify DAG folder path

**Issue**: Import errors post-deployment

**Solution**: Verify all dependencies installed, check Python version

---

## Continuous Improvement

### Monthly Reviews

- Review deployment frequency
- Analyze CI/CD metrics
- Identify bottlenecks
- Update procedures

### Quarterly Goals

- Reduce CI time by 10%
- Increase deployment frequency
- Improve rollback time
- Enhance monitoring

---

## Additional Resources

- [CI Workflow File](.github/workflows/ci.yml)
- [Staging Deployment Workflow](.github/workflows/cd-staging.yml)
- [Production Deployment Workflow](.github/workflows/cd-production.yml)
- [Branch Protection Setup](ci_cd_setup.md)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

**Last Updated**: 2025-10-21
**Maintained By**: DevOps Team
**Next Review**: 2026-01-21