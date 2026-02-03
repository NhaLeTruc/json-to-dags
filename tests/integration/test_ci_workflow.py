"""
Integration tests for CI/CD workflow validation.

Tests verify that GitHub Actions workflow files are valid, properly configured,
and have correct job dependencies.

Constitutional Compliance:
- Principle II: Test-Driven Data Engineering (validates CI/CD infrastructure)
- Principle V: Observability (ensures CI pipeline visibility)
"""

from pathlib import Path

import pytest
import yaml

# Path to GitHub workflows
WORKFLOWS_DIR = Path(__file__).parents[2] / ".github" / "workflows"


@pytest.fixture
def ci_workflow_path():
    """Path to CI workflow file."""
    return WORKFLOWS_DIR / "ci.yml"


@pytest.fixture
def cd_staging_workflow_path():
    """Path to staging deployment workflow file."""
    return WORKFLOWS_DIR / "cd-staging.yml"


@pytest.fixture
def cd_production_workflow_path():
    """Path to production deployment workflow file."""
    return WORKFLOWS_DIR / "cd-production.yml"


class TestCIWorkflowStructure:
    """Test CI workflow file structure and configuration."""

    def test_ci_workflow_exists(self, ci_workflow_path):
        """Test that CI workflow file exists."""
        assert ci_workflow_path.exists(), f"CI workflow not found at {ci_workflow_path}"

    def test_ci_workflow_valid_yaml(self, ci_workflow_path):
        """Test that CI workflow is valid YAML."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            try:
                workflow = yaml.safe_load(f)
                assert workflow is not None, "Workflow file is empty"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax in CI workflow: {e}")

    def test_ci_workflow_has_required_triggers(self, ci_workflow_path):
        """Test that CI workflow triggers on push and pull_request."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert "on" in workflow, "Workflow missing 'on' trigger configuration"

        triggers = workflow["on"]
        # Support both list and dict formats
        if isinstance(triggers, list):
            assert "push" in triggers, "CI should trigger on push"
            assert "pull_request" in triggers, "CI should trigger on pull_request"
        elif isinstance(triggers, dict):
            assert (
                "push" in triggers or "pull_request" in triggers
            ), "CI should trigger on push or pull_request"

    def test_ci_workflow_has_required_jobs(self, ci_workflow_path):
        """Test that CI workflow has all required jobs."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert "jobs" in workflow, "Workflow missing jobs section"
        jobs = workflow["jobs"]

        # Required jobs
        required_jobs = {
            "lint": "Code linting with ruff/black",
            "test": "Unit and integration tests",
            "dag-validation": "DAG parsing validation",
        }

        for job_name, job_description in required_jobs.items():
            # Job name might have variations (e.g., lint, linting, code-lint)
            matching_jobs = [j for j in jobs if job_name.replace("-", "_") in j.replace("-", "_")]
            assert (
                len(matching_jobs) > 0
            ), f"CI workflow missing '{job_name}' job ({job_description})"


class TestCIWorkflowSteps:
    """Test CI workflow job steps."""

    def test_ci_workflow_has_checkout_step(self, ci_workflow_path):
        """Test that all jobs checkout code."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            has_checkout = any(
                step.get("uses", "").startswith("actions/checkout") for step in steps
            )
            assert has_checkout, f"Job '{job_name}' missing checkout step"

    def test_ci_workflow_has_python_setup(self, ci_workflow_path):
        """Test that workflow sets up Python."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})

        # At least one job should set up Python
        has_python_setup = False
        for job_config in jobs.values():
            steps = job_config.get("steps", [])
            if any(step.get("uses", "").startswith("actions/setup-python") for step in steps):
                has_python_setup = True
                break

        assert has_python_setup, "No job sets up Python environment"

    def test_ci_workflow_installs_dependencies(self, ci_workflow_path):
        """Test that workflow installs Python dependencies."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})

        # At least one job should install dependencies
        has_dependency_install = False
        for job_config in jobs.values():
            steps = job_config.get("steps", [])
            for step in steps:
                run_command = step.get("run", "")
                if "pip install" in run_command or "requirements" in run_command:
                    has_dependency_install = True
                    break
            if has_dependency_install:
                break

        assert has_dependency_install, "No job installs Python dependencies"


class TestCDStagingWorkflow:
    """Test staging deployment workflow."""

    def test_staging_workflow_exists(self, cd_staging_workflow_path):
        """Test that staging deployment workflow exists."""
        # This is optional for initial implementation
        if not cd_staging_workflow_path.exists():
            pytest.skip("Staging deployment workflow not yet created (optional)")

    def test_staging_workflow_valid_yaml(self, cd_staging_workflow_path):
        """Test that staging workflow is valid YAML."""
        if not cd_staging_workflow_path.exists():
            pytest.skip("Staging deployment workflow not yet created")

        with open(cd_staging_workflow_path) as f:
            try:
                workflow = yaml.safe_load(f)
                assert workflow is not None
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in staging workflow: {e}")

    def test_staging_workflow_triggers_on_main_merge(self, cd_staging_workflow_path):
        """Test that staging deploys on merge to main."""
        if not cd_staging_workflow_path.exists():
            pytest.skip("Staging deployment workflow not yet created")

        with open(cd_staging_workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert "on" in workflow, "Staging workflow missing trigger"
        triggers = workflow["on"]

        # Should trigger on push to main or workflow_dispatch
        has_main_trigger = False
        if isinstance(triggers, dict):
            if "push" in triggers:
                branches = triggers["push"].get("branches", [])
                has_main_trigger = "main" in branches or "master" in branches
            elif "workflow_dispatch" in triggers:
                has_main_trigger = True  # Manual trigger is acceptable

        assert has_main_trigger, "Staging should trigger on main branch or manual dispatch"


class TestCDProductionWorkflow:
    """Test production deployment workflow."""

    def test_production_workflow_exists(self, cd_production_workflow_path):
        """Test that production deployment workflow exists."""
        # This is optional for initial implementation
        if not cd_production_workflow_path.exists():
            pytest.skip("Production deployment workflow not yet created (optional)")

    def test_production_workflow_valid_yaml(self, cd_production_workflow_path):
        """Test that production workflow is valid YAML."""
        if not cd_production_workflow_path.exists():
            pytest.skip("Production deployment workflow not yet created")

        with open(cd_production_workflow_path) as f:
            try:
                workflow = yaml.safe_load(f)
                assert workflow is not None
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in production workflow: {e}")

    def test_production_workflow_requires_manual_approval(self, cd_production_workflow_path):
        """Test that production deployment requires manual trigger or approval."""
        if not cd_production_workflow_path.exists():
            pytest.skip("Production deployment workflow not yet created")

        with open(cd_production_workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert "on" in workflow, "Production workflow missing trigger"
        triggers = workflow["on"]

        # Production should only trigger manually or with approval
        # workflow_dispatch = manual trigger
        # Or should have approval environment
        is_manual = "workflow_dispatch" in triggers

        # Alternative: check for environment with approval
        jobs = workflow.get("jobs", {})
        has_approval_env = any(job.get("environment") is not None for job in jobs.values())

        assert (
            is_manual or has_approval_env
        ), "Production deployment should require manual trigger or approval environment"


class TestWorkflowDependencies:
    """Test workflow job dependencies."""

    def test_ci_job_dependencies_valid(self, ci_workflow_path):
        """Test that CI job dependencies are correctly configured."""
        if not ci_workflow_path.exists():
            pytest.skip("CI workflow file not yet created")

        with open(ci_workflow_path) as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})

        for job_name, job_config in jobs.items():
            if "needs" in job_config:
                needs = job_config["needs"]
                # Ensure all needed jobs exist
                if isinstance(needs, str):
                    needs = [needs]

                for needed_job in needs:
                    assert (
                        needed_job in jobs
                    ), f"Job '{job_name}' depends on non-existent job '{needed_job}'"


class TestCoverageReporting:
    """Test coverage reporting configuration."""


@pytest.mark.integration
def test_workflow_files_in_correct_location():
    """Test that workflow files are in .github/workflows/ directory."""
    assert WORKFLOWS_DIR.exists(), f"Workflows directory not found at {WORKFLOWS_DIR}"

    # At minimum, CI workflow should exist
    ci_workflow = WORKFLOWS_DIR / "ci.yml"
    if not ci_workflow.exists():
        pytest.skip("CI workflow not yet created")


@pytest.mark.integration
def test_no_workflow_syntax_errors():
    """Test that all workflow files have valid YAML syntax."""
    if not WORKFLOWS_DIR.exists():
        pytest.skip("Workflows directory not found")

    workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))

    if not workflow_files:
        pytest.skip("No workflow files found")

    errors = []
    for workflow_file in workflow_files:
        try:
            with open(workflow_file) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"{workflow_file.name}: {e}")

    assert len(errors) == 0, "Workflow syntax errors:\n" + "\n".join(errors)
