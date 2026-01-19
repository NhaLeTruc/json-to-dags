"""
Spark YARN Operator for Apache Airflow.

Custom operator for submitting Spark jobs to a YARN cluster.
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


class SparkYarnOperator(BaseOperator):
    """
    Operator for submitting Spark applications to a YARN cluster.

    :param application: Path to the Spark application (Python or JAR file)
    :param queue: YARN queue name (default 'default')
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

    template_fields = ("application", "application_args", "conf", "name")  # Removed 'queue' - reserved by Airflow executor
    # Note: Do NOT set template_ext to .py/.jar - these are Spark app paths, not Jinja templates
    ui_color = "#d4a76a"  # Brown/tan for YARN


    def __init__(
        self,
        *,
        application: str,
        queue: str = "default",
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
        """Initialize SparkYarnOperator."""
        super().__init__(**kwargs)

        # Validate required parameters
        if not application:
            raise ValueError("application parameter is required")

        # Validate deploy mode
        if deploy_mode not in ["client", "cluster"]:
            raise ValueError(f"Invalid deploy_mode: {deploy_mode}. Must be 'client' or 'cluster'")

        self.application = application
        self.queue = queue
        self.application_args = application_args or []
        self.conf = conf or {}
        self.name = name or f"spark_yarn_{self.task_id}"
        self.deploy_mode = deploy_mode
        self.driver_memory = driver_memory
        self.driver_cores = driver_cores
        self.executor_memory = executor_memory
        self.executor_cores = executor_cores
        self.num_executors = num_executors
        self.verbose = verbose
        self.conn_id = conn_id

        self._job_id: str | None = None
        self._application_id: str | None = None
        self._hook: SparkHook | None = None

    def execute(self, context: dict[str, Any]) -> str:
        """
        Execute the Spark YARN job.

        :param context: Airflow task context
        :return: Job ID (YARN application ID)
        """
        logger.info(f"Executing Spark YARN job: {self.name}")
        logger.info(f"Application: {self.application}")
        logger.info(f"Queue: {self.queue}")
        logger.info(f"Deploy mode: {self.deploy_mode}")

        # Simulation mode for demo environments without actual YARN cluster
        if SPARK_SIMULATION_MODE:
            import time
            self._job_id = f"sim-yarn-application_{int(time.time())}"
            self._application_id = self._job_id
            logger.info(f"[SIMULATION MODE] Spark YARN job simulated: {self.name}")
            logger.info(f"[SIMULATION MODE] Would submit to YARN queue: {self.queue}")
            logger.info(f"[SIMULATION MODE] Application: {self.application}")
            logger.info(f"[SIMULATION MODE] Deploy mode: {self.deploy_mode}")
            logger.info(f"[SIMULATION MODE] Executor memory: {self.executor_memory}")
            logger.info(f"[SIMULATION MODE] Num executors: {self.num_executors}")
            context["task_instance"].xcom_push(key="yarn_application_id", value=self._application_id)
            context["task_instance"].xcom_push(key="simulation_mode", value=True)
            return self._application_id

        # Initialize hook
        self._hook = SparkHook(conn_id=self.conn_id, verbose=self.verbose)

        # Add YARN-specific configuration
        yarn_conf = self.conf.copy()
        yarn_conf["spark.yarn.queue"] = self.queue

        # Add any additional YARN configurations
        if "spark.yarn.submit.waitAppCompletion" not in yarn_conf:
            yarn_conf["spark.yarn.submit.waitAppCompletion"] = "true"

        try:
            # Submit job with master=yarn
            self._job_id = self._hook.submit_job(
                application=self.application,
                master="yarn",
                deploy_mode=self.deploy_mode,
                name=self.name,
                conf=yarn_conf,
                application_args=self.application_args,
                driver_memory=self.driver_memory,
                driver_cores=self.driver_cores,
                executor_memory=self.executor_memory,
                executor_cores=self.executor_cores,
                num_executors=self.num_executors,
            )

            logger.info(f"Spark YARN job submitted. Job ID: {self._job_id}")

            # The job ID is our internal tracking ID
            # YARN application ID would be parsed from spark-submit output in production
            self._application_id = self._job_id

            # Wait for completion
            success = self._hook.wait_for_completion(self._job_id, timeout=None, poll_interval=5)

            if not success:
                status = self._hook.get_job_status(self._job_id)
                error_msg = f"Spark YARN job {self._job_id} failed with status: {status.value}"
                logger.error(error_msg)

                # Try to get logs
                logs = self._hook.get_job_logs(self._job_id)
                if logs:
                    logger.error(f"Job logs:\n{logs}")

                raise AirflowException(error_msg)

            logger.info(f"Spark YARN job {self._job_id} completed successfully")

            # Push application ID to XCom
            context["task_instance"].xcom_push(
                key="yarn_application_id", value=self._application_id
            )

            return self._application_id

        except Exception as e:
            logger.error(f"Error executing Spark YARN job: {str(e)}")
            raise AirflowException(f"Spark YARN job execution failed: {str(e)}") from e

    def on_kill(self):
        """Handle task kill by terminating Spark job."""
        if self._hook and self._job_id:
            logger.warning(f"Task killed, terminating Spark YARN job {self._job_id}")
            self._hook.kill_job(self._job_id)

    def get_logs(self) -> str | None:
        """
        Retrieve YARN application logs.

        :return: Application logs
        """
        if self._hook and self._job_id:
            return self._hook.get_job_logs(self._job_id)
        return None
