# ============================================================================
# Apache Airflow ETL Demo Platform - Airflow Container
# ============================================================================
# Base: Official Apache Airflow image with Python 3.12
# Purpose: Extends base image with custom operators and dependencies
# Migrated from 3.1.0 to 2.10.5 for stability (see docs/migration_plan.md)
# ============================================================================

FROM apache/airflow:2.10.5-python3.12

# Switch to root for system-level installations
USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && usermod -aG 0 airflow \
    && mkdir -p /opt/airflow/{logs,dags,plugins,data} \
    && chown -R airflow: /opt/airflow

# Switch back to airflow user
USER airflow

# Copy requirements files
COPY requirements.txt /opt/airflow/requirements.txt
COPY requirements-dev.txt /opt/airflow/requirements-dev.txt

# Install Python dependencies (including dev dependencies for testing)
RUN pip install --no-cache-dir --user -r /opt/airflow/requirements-dev.txt

# Set environment variables
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True
ENV AIRFLOW__CORE__AUTH_MANAGER=airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=3 \
    CMD airflow jobs check --job-type SchedulerJob --hostname $(hostname) || exit 1

# Working directory
WORKDIR /opt/airflow

# Default command (can be overridden in docker-compose)
CMD ["bash"]
