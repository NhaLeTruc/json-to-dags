"""
Spark Standalone Operator for Apache Airflow.

Custom operator for submitting Spark jobs to a Standalone cluster.
"""

import os
from typing import Any

from airflow.exceptions import AirflowException
from airflow.models import BaseOperator

from src.hooks.spark_hook import SparkHook
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Enable simulation mode when no Spark cluster is available (demo environments)
SPARK_SIMULATION_MODE = os.environ.get("SPARK_SIMULATION_MODE", "true").lower() == "true"


class SparkStandaloneOperator(BaseOperator):
    """
    Operator for submitting Spark applications to a Standalone cluster.

    :param application: Path to the Spark application (Python or JAR file)
    :param master: Spark master URL (e.g., 'spark://master:7077')
    :param application_args: Arguments to pass to the application
    :param conf: Spark configuration properties
    :param name: Application name
    :param deploy_mode: Deploy mode ('client' or 'cluster'), default 'client'
    :param driver_memory: Driver memory (e.g., '1g')
    :param driver_cores: Number of driver cores
    :param executor_memory: Executor memory (e.g., '2g')
    :param executor_cores: Number of executor cores
    :param num_executors: Number of executors
    :param verbose: Enable verbose spark-submit output
    :param conn_id: Airflow connection ID for Spark
    """

    template_fields = ("application", "application_args", "conf", "name")
    # Note: Do NOT set template_ext to .py/.jar - these are Spark app paths, not Jinja templates
    ui_color = "#e47128"  # Orange for Spark Standalone


    def __init__(
        self,
        *,
        application: str,
        master: str,
        application_args: list[str] | None = None,
        conf: dict[str, str] | None = None,
        name: str | None = None,
        deploy_mode: str = "client",
        driver_memory: str | None = None,
        driver_cores: str | None = None,
        executor_memory: str | None = None,
        executor_cores: str | None = None,
        num_executors: str | None = None,
        verbose: bool = False,
        conn_id: str = "spark_default",
        **kwargs,
    ):
        """Initialize SparkStandaloneOperator."""
        super().__init__(**kwargs)

        # Validate required parameters
        if not application:
            raise ValueError("application parameter is required")
        if not master:
            raise ValueError("master parameter is required")

        # Validate master URL
        if not master.startswith("spark://") and master != "local":
            raise ValueError(
                f"Invalid master URL: {master}. Must start with 'spark://' or be 'local'"
            )

        # Validate deploy mode
        if deploy_mode not in ["client", "cluster"]:
            raise ValueError(f"Invalid deploy_mode: {deploy_mode}. Must be 'client' or 'cluster'")

        # Validate application path
        if not (application.endswith(".py") or application.endswith(".jar")):
            logger.warning(f"Application {application} does not end with .py or .jar")

        self.application = application
        self.master = master
        self.application_args = application_args or []
        self.conf = conf or {}
        self.name = name or f"spark_standalone_{self.task_id}"
        self.deploy_mode = deploy_mode
        self.driver_memory = driver_memory
        self.driver_cores = driver_cores
        self.executor_memory = executor_memory
        self.executor_cores = executor_cores
        self.num_executors = num_executors
        self.verbose = verbose
        self.conn_id = conn_id

        self._job_id: str | None = None
        self._hook: SparkHook | None = None

    def execute(self, context: dict[str, Any]) -> str:
        """
        Execute the Spark Standalone job.

        :param context: Airflow task context
        :return: Job ID
        """
        logger.info(f"Executing Spark Standalone job: {self.name}")
        logger.info(f"Application: {self.application}")
        logger.info(f"Master: {self.master}")

        # Simulation mode for demo environments without actual Spark cluster
        if SPARK_SIMULATION_MODE:
            import time
            self._job_id = f"sim-standalone-{int(time.time())}"
            logger.info(
                f"[SIMULATION MODE] Spark Standalone job simulated: {self.name}",
                master=self.master,
                application=self.application,
                deploy_mode=self.deploy_mode,
                executor_memory=self.executor_memory,
                num_executors=self.num_executors,
            )
            context["task_instance"].xcom_push(key="spark_job_id", value=self._job_id)
            context["task_instance"].xcom_push(key="simulation_mode", value=True)
            return self._job_id

        # Initialize hook
        self._hook = SparkHook(conn_id=self.conn_id, verbose=self.verbose)

        try:
            # Submit job
            self._job_id = self._hook.submit_job(
                application=self.application,
                master=self.master,
                deploy_mode=self.deploy_mode,
                name=self.name,
                conf=self.conf,
                application_args=self.application_args,
                driver_memory=self.driver_memory,
                driver_cores=self.driver_cores,
                executor_memory=self.executor_memory,
                executor_cores=self.executor_cores,
                num_executors=self.num_executors,
            )

            logger.info(f"Spark job submitted. Job ID: {self._job_id}")

            # Wait for completion (no timeout by default)
            success = self._hook.wait_for_completion(self._job_id, timeout=None, poll_interval=5)

            if not success:
                status = self._hook.get_job_status(self._job_id)
                error_msg = f"Spark job {self._job_id} failed with status: {status.value}"
                logger.error(error_msg)

                # Try to get logs
                logs = self._hook.get_job_logs(self._job_id)
                if logs:
                    logger.error(f"Job logs:\n{logs}")

                raise AirflowException(error_msg)

            logger.info(f"Spark job {self._job_id} completed successfully")

            # Push job ID to XCom
            context["task_instance"].xcom_push(key="spark_job_id", value=self._job_id)

            return self._job_id

        except Exception as e:
            logger.error(f"Error executing Spark job: {str(e)}")
            raise AirflowException(f"Spark job execution failed: {str(e)}") from e

    def on_kill(self):
        """Handle task kill by terminating Spark job."""
        if self._hook and self._job_id:
            logger.warning(f"Task killed, terminating Spark job {self._job_id}")
            self._hook.kill_job(self._job_id)
