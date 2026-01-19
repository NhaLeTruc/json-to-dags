# CI/CD Setup and Branch Protection Rules

This document describes the CI/CD pipeline configuration and GitHub repository settings required for the Apache Airflow ETL Demo Platform.

---

## Table of Contents

- [Overview](#overview)
- [Branch Protection Rules](#branch-protection-rules)
- [GitHub Environment Configuration](#github-environment-configuration)
- [Required Secrets](#required-secrets)
- [Branch Strategy](#branch-strategy)
- [Workflow Permissions](#workflow-permissions)
- [Setup Instructions](#setup-instructions)

---

## Overview

The CI/CD pipeline provides automated validation, testing, and deployment capabilities:

- **Continuous Integration (CI)**: Automated testing and validation on every push and pull request
- **Continuous Deployment (CD)**: Automated deployment to staging on main branch merges
- **Production Deployment**: Manual, approval-gated deployment to production

---

## Branch Protection Rules

### Main Branch Protection

Configure the following protection rules for the `main` branch:

#### Required Status Checks

Enable "Require status checks to pass before merging" with:

- ✅ `lint` - Code linting must pass
- ✅ `test` - All tests must pass
- ✅ `dag-validation` - DAG parsing and validation must pass
- ✅ `build-summary` - Overall CI pipeline must succeed

**Settings**:
- ✅ Require branches to be up to date before merging
- ✅ Require status checks to pass before merging

#### Pull Request Requirements

- ✅ **Require pull request before merging**
  - Required approvals: **1** (adjust based on team size)
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners (if CODEOWNERS file exists)

#### Additional Restrictions

- ✅ **Require linear history** - Prevent merge commits (prefer rebase or squash)
- ✅ **Require signed commits** - Enforce commit signing (recommended for security)
- ✅ **Include administrators** - Apply rules to repository administrators
- ✅ **Restrict who can push** - Limit direct pushes (optional, recommended)
- ❌ **Allow force pushes** - NEVER enable force push to main
- ❌ **Allow deletions** - NEVER allow branch deletion

---

### Develop Branch Protection (Optional)

If using a `develop` branch for integration:

#### Required Status Checks

- ✅ `lint` - Code linting must pass
- ✅ `test` - All tests must pass
- ✅ `dag-validation` - DAG validation must pass

#### Pull Request Requirements

- ✅ Require pull request before merging
  - Required approvals: **1**

---

### Feature Branch Naming Convention

Enforce branch naming patterns (via external tools or policy):

**Allowed patterns**:
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Critical production fixes
- `release/*` - Release preparation branches

**Examples**:
- `feature/add-spark-operator`
- `bugfix/fix-dag-parsing`
- `hotfix/critical-scheduler-issue`
- `release/v1.2.0`

---

## GitHub Environment Configuration

### Staging Environment

**Name**: `staging`

**Protection Rules**:
- ❌ No required reviewers (auto-deploy on main merge)
- ✅ Deployment branches: Limit to `main` branch only

**Environment Secrets**:
- `STAGING_HOST` - Staging server hostname
- `STAGING_USER` - Deployment user for staging
- `STAGING_SSH_KEY` - SSH private key for deployment
- `STAGING_URL` - Staging Airflow UI URL

**Environment Variables**:
- `DEPLOYMENT_ENV=staging`

---

### Production Environment

**Name**: `production`

**Protection Rules** (CRITICAL):
- ✅ **Required reviewers**: **2** (adjust based on team, minimum 1)
  - Recommended: Senior engineers or DevOps team
- ✅ **Wait timer**: 5 minutes (cooling-off period)
- ✅ **Deployment branches**: Manual workflow dispatch only (no automatic triggers)
- ✅ **Prevent self-review**: Deployer cannot approve their own deployment

**Environment Secrets**:
- `PROD_HOST` - Production server hostname
- `PROD_USER` - Deployment user for production
- `PROD_SSH_KEY` - SSH private key for production deployment
- `PROD_URL` - Production Airflow UI URL
- `SLACK_PROD_WEBHOOK` - Slack webhook for production notifications
- `PAGERDUTY_API_KEY` - PagerDuty key for incident management

**Environment Variables**:
- `DEPLOYMENT_ENV=production`

---

## Required Secrets

### Repository Secrets

Configure the following secrets at the repository level (Settings → Secrets and variables → Actions):

#### Deployment Secrets

| Secret Name | Description | Example |
|------------|-------------|---------|
| `STAGING_HOST` | Staging server hostname | `staging.example.com` |
| `STAGING_USER` | SSH user for staging | `deploy` |
| `STAGING_SSH_KEY` | Private SSH key for staging | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `STAGING_URL` | Staging Airflow URL | `https://staging-airflow.example.com` |
| `PROD_HOST` | Production server hostname | `airflow.example.com` |
| `PROD_USER` | SSH user for production | `deploy` |
| `PROD_SSH_KEY` | Private SSH key for production | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `PROD_URL` | Production Airflow URL | `https://airflow.example.com` |

#### Notification Secrets

| Secret Name | Description | Example |
|------------|-------------|---------|
| `SLACK_WEBHOOK_URL` | Slack webhook for deployments | `https://hooks.slack.com/services/...` |
| `SLACK_PROD_WEBHOOK` | Slack webhook for production | `https://hooks.slack.com/services/...` |
| `TEAMS_WEBHOOK_URL` | MS Teams webhook (optional) | `https://outlook.office.com/webhook/...` |

#### Cloud Provider Secrets (if applicable)

| Secret Name | Description | Example |
|------------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `DOCKER_HUB_USERNAME` | Docker Hub username | `myorg` |
| `DOCKER_HUB_TOKEN` | Docker Hub access token | `dckr_pat_...` |

---

## Branch Strategy

### GitFlow-Inspired Strategy

```
main (protected)
  ├── develop (optional, integration branch)
  │   ├── feature/add-new-operator
  │   ├── feature/improve-logging
  │   └── bugfix/fix-quality-check
  ├── release/v1.2.0 (release preparation)
  └── hotfix/critical-bug (emergency production fixes)
```

### Workflow

1. **Feature Development**:
   ```bash
   git checkout -b feature/my-new-feature
   # Make changes, commit
   git push origin feature/my-new-feature
   # Create pull request to main (or develop)
   ```

2. **Pull Request Process**:
   - CI pipeline runs automatically
   - Code review required (1+ approvals)
   - All status checks must pass
   - Squash and merge (or rebase) to main

3. **Main Branch**:
   - Merge triggers staging deployment automatically
   - Always deployable to production
   - Protected from direct pushes

4. **Production Deployment**:
   - Manual trigger via GitHub Actions UI
   - Requires approval from designated reviewers
   - Includes rollback capability

5. **Hotfix Process**:
   ```bash
   git checkout -b hotfix/critical-issue main
   # Fix issue, commit
   git push origin hotfix/critical-issue
   # Create PR, fast-track review
   # After merge, immediately deploy to production
   ```

---

## Workflow Permissions

### Repository Settings

Navigate to **Settings → Actions → General**:

#### Workflow Permissions

- ✅ **Read and write permissions** (required for workflows to update artifacts, create releases)
- ✅ **Allow GitHub Actions to create and approve pull requests** (optional, for automated PR creation)

#### Fork Permissions

- ❌ **Disable "Run workflows from fork pull requests"** (security: prevent untrusted code execution)
- ✅ **Require approval for first-time contributors**

---

## Setup Instructions

### 1. Configure Branch Protection

1. Navigate to **Settings → Branches**
2. Click **Add branch protection rule**
3. Branch name pattern: `main`
4. Configure settings as specified in [Branch Protection Rules](#branch-protection-rules)
5. Click **Create** or **Save changes**

### 2. Create GitHub Environments

#### Staging Environment

1. Navigate to **Settings → Environments**
2. Click **New environment**
3. Name: `staging`
4. Configure protection rules:
   - Deployment branches: `main` only
5. Add environment secrets (see [Required Secrets](#required-secrets))

#### Production Environment

1. Click **New environment**
2. Name: `production`
3. Configure protection rules:
   - Required reviewers: Add 2 reviewers
   - Wait timer: 5 minutes
   - Deployment branches: Selected branches → (none, manual only)
4. Add environment secrets

### 3. Add Repository Secrets

1. Navigate to **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Add each secret from [Required Secrets](#required-secrets)

### 4. Enable GitHub Actions

1. Navigate to **Settings → Actions → General**
2. Enable **Allow all actions and reusable workflows**
3. Set workflow permissions as specified above

### 5. Verify CI Pipeline

1. Create a test branch:
   ```bash
   git checkout -b test/ci-verification
   echo "# Test" >> README.md
   git add README.md
   git commit -m "Test CI pipeline"
   git push origin test/ci-verification
   ```

2. Open pull request to `main`
3. Verify all CI checks run and pass
4. Close PR (don't merge)

### 6. Test Deployment Workflows

#### Test Staging Deployment

1. Merge a PR to `main`
2. Navigate to **Actions** tab
3. Verify "Deploy to Staging" workflow runs automatically
4. Check deployment logs

#### Test Production Deployment

1. Navigate to **Actions → Deploy to Production**
2. Click **Run workflow**
3. Fill in:
   - Version: `main` or specific commit SHA
   - Reason: "Testing production deployment workflow"
4. Click **Run workflow**
5. Approval will be required (if configured)
6. Monitor deployment

---

## CODEOWNERS File (Optional)

Create `.github/CODEOWNERS` to automatically request reviews:

```
# Global owners
* @team-lead @senior-engineer

# DAG files require data engineering review
/dags/ @data-engineering-team

# Infrastructure changes require DevOps review
/.github/workflows/ @devops-team
/docker/ @devops-team

# Source code requires code review
/src/ @backend-team

# Documentation
/docs/ @tech-writers @team-lead
```

---

## Troubleshooting

### CI Pipeline Fails

**Symptom**: CI status check fails on PR

**Solutions**:
1. Check **Actions** tab for detailed logs
2. Common issues:
   - Linting errors: Run `ruff check .` and `black --check .` locally
   - Test failures: Run `pytest tests/` locally
   - DAG errors: Check DAG import errors

### Deployment Fails

**Symptom**: Staging or production deployment fails

**Solutions**:
1. Check workflow logs in **Actions** tab
2. Verify secrets are correctly configured
3. Check server accessibility (SSH, network)
4. Verify Airflow services are running on target

### Status Checks Not Running

**Symptom**: CI checks don't appear on PR

**Solutions**:
1. Verify workflows are in `.github/workflows/` directory
2. Check workflow trigger conditions match branch name
3. Ensure GitHub Actions is enabled
4. Check workflow YAML syntax

---

## Security Best Practices

1. **Rotate Secrets Regularly**: Change deployment keys, API tokens quarterly
2. **Use Least Privilege**: Grant minimal permissions to deployment users
3. **Audit Access**: Review who has access to environments and secrets monthly
4. **Monitor Deployments**: Set up alerts for failed or unauthorized deployments
5. **Sign Commits**: Enable GPG commit signing for all contributors
6. **Scan Dependencies**: Regularly review security scan results from CI

---

## Maintenance

### Quarterly Review

- Review and update branch protection rules
- Audit environment access and secrets
- Update GitHub Actions versions
- Review deployment logs for patterns

### Annual Tasks

- Rotate all deployment credentials
- Review and update CI/CD architecture
- Assess workflow efficiency and optimization opportunities

---

## Additional Resources

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [GitHub Environments Documentation](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [GitHub Actions Security Best Practices](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [GitFlow Workflow Guide](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow)

---

**Last Updated**: 2025-10-21
**Maintained By**: DevOps Team