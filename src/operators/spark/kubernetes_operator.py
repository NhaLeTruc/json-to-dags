"""
Spark Kubernetes Operator for Apache Airflow.

Custom operator for submitting Spark jobs to a Kubernetes cluster.
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


class SparkKubernetesOperator(BaseOperator):
    """
    Operator for submitting Spark applications to a Kubernetes cluster.

    :param application: Path to the Spark application (Python or JAR file)
    :param namespace: Kubernetes namespace for Spark resources
    :param application_args: Arguments to pass to the application
    :param conf: Spark configuration properties
    :param name: Application name
    :param kubernetes_service_account: Kubernetes service account name
    :param image: Docker image for Spark driver and executors
    :param driver_pod_template: Path to driver pod template YAML
    :param executor_pod_template: Path to executor pod template YAML
    :param executor_pod_cleanup_policy: Pod cleanup policy ('OnSuccess', 'OnFailure', 'Never')
    :param driver_memory: Driver memory (e.g., '1g')
    :param driver_cores: Number of driver cores
    :param executor_memory: Executor memory (e.g., '2g')
    :param executor_cores: Number of executor cores
    :param num_executors: Number of executors
    :param verbose: Enable verbose spark-submit output
    :param conn_id: Airflow connection ID for Spark
    :param kubernetes_master: Kubernetes API server URL (e.g., 'k8s://https://api.k8s.example.com')
    """

    template_fields = ("application", "application_args", "namespace", "image", "conf", "name")
    template_ext = (".py", ".jar")
    ui_color = "#326ce5"  # Blue for Kubernetes


    def __init__(
        self,
        *,
        application: str,
        namespace: str,
        application_args: list[str] | None = None,
        conf: dict[str, str] | None = None,
        name: str | None = None,
        kubernetes_service_account: str | None = None,
        image: str | None = None,
        driver_pod_template: str | None = None,
        executor_pod_template: str | None = None,
        executor_pod_cleanup_policy: str = "OnSuccess",
        driver_memory: str | None = None,
        driver_cores: str | None = None,
        executor_memory: str | None = None,
        executor_cores: str | None = None,
        num_executors: str | None = None,
        verbose: bool = False,
        conn_id: str = "spark_default",
        kubernetes_master: str = "k8s://https://kubernetes.default.svc",
        **kwargs,
    ):
        """Initialize SparkKubernetesOperator."""
        super().__init__(**kwargs)

        # Validate required parameters
        if not application:
            raise ValueError("application parameter is required")
        if not namespace:
            raise TypeError("namespace parameter is required")

        # Validate cleanup policy
        valid_policies = ["OnSuccess", "OnFailure", "Never"]
        if executor_pod_cleanup_policy not in valid_policies:
            raise ValueError(
                f"Invalid executor_pod_cleanup_policy: {executor_pod_cleanup_policy}. "
                f"Must be one of: {', '.join(valid_policies)}"
            )

        self.application = application
        self.namespace = namespace
        self.application_args = application_args or []
        self.conf = conf or {}
        self.name = name or f"spark-k8s-{self.task_id}"
        self.kubernetes_service_account = kubernetes_service_account
        self.image = image
        self.driver_pod_template = driver_pod_template
        self.executor_pod_template = executor_pod_template
        self.executor_pod_cleanup_policy = executor_pod_cleanup_policy
        self.driver_memory = driver_memory
        self.driver_cores = driver_cores
        self.executor_memory = executor_memory
        self.executor_cores = executor_cores
        self.num_executors = num_executors
        self.verbose = verbose
        self.conn_id = conn_id
        self.kubernetes_master = kubernetes_master

        self._job_id: str | None = None
        self._hook: SparkHook | None = None

    def execute(self, context: dict[str, Any]) -> str:
        """
        Execute the Spark Kubernetes job.

        :param context: Airflow task context
        :return: Job ID
        """
        logger.info(f"Executing Spark Kubernetes job: {self.name}")
        logger.info(f"Application: {self.application}")
        logger.info(f"Namespace: {self.namespace}")

        # Simulation mode for demo environments without actual Kubernetes cluster
        if SPARK_SIMULATION_MODE:
            import time
            self._job_id = f"sim-k8s-spark-{self.name}-{int(time.time())}"
            logger.info(f"[SIMULATION MODE] Spark Kubernetes job simulated: {self.name}")
            logger.info(f"[SIMULATION MODE] Would submit to namespace: {self.namespace}")
            logger.info(f"[SIMULATION MODE] Application: {self.application}")
            logger.info(f"[SIMULATION MODE] Image: {self.image}")
            logger.info(f"[SIMULATION MODE] Service account: {self.kubernetes_service_account}")
            logger.info(f"[SIMULATION MODE] Executor memory: {self.executor_memory}")
            logger.info(f"[SIMULATION MODE] Num executors: {self.num_executors}")
            context["task_instance"].xcom_push(key="k8s_spark_job_id", value=self._job_id)
            context["task_instance"].xcom_push(key="simulation_mode", value=True)
            return self._job_id

        # Initialize hook
        self._hook = SparkHook(conn_id=self.conn_id, verbose=self.verbose)

        # Build Kubernetes-specific configuration
        k8s_conf = self.conf.copy()

        # Namespace
        k8s_conf["spark.kubernetes.namespace"] = self.namespace

        # Service account
        if self.kubernetes_service_account:
            k8s_conf["spark.kubernetes.authenticate.driver.serviceAccountName"] = (
                self.kubernetes_service_account
            )

        # Container image
        if self.image:
            k8s_conf["spark.kubernetes.container.image"] = self.image

        # Pod templates
        if self.driver_pod_template:
            k8s_conf["spark.kubernetes.driver.podTemplateFile"] = self.driver_pod_template
        if self.executor_pod_template:
            k8s_conf["spark.kubernetes.executor.podTemplateFile"] = self.executor_pod_template

        # Cleanup policy
        k8s_conf["spark.kubernetes.executor.deleteOnTermination"] = (
            "true" if self.executor_pod_cleanup_policy in ["OnSuccess", "OnFailure"] else "false"
        )

        try:
            # Submit job with Kubernetes master
            self._job_id = self._hook.submit_job(
                application=self.application,
                master=self.kubernetes_master,
                deploy_mode="cluster",  # K8s typically uses cluster mode
                name=self.name,
                conf=k8s_conf,
                application_args=self.application_args,
                driver_memory=self.driver_memory,
                driver_cores=self.driver_cores,
                executor_memory=self.executor_memory,
                executor_cores=self.executor_cores,
                num_executors=self.num_executors,
            )

            logger.info(f"Spark Kubernetes job submitted. Job ID: {self._job_id}")

            # Wait for completion
            success = self._hook.wait_for_completion(self._job_id, timeout=None, poll_interval=5)

            if not success:
                status = self._hook.get_job_status(self._job_id)
                error_msg = (
                    f"Spark Kubernetes job {self._job_id} failed with status: {status.value}"
                )
                logger.error(error_msg)

                # Try to get logs
                logs = self._hook.get_job_logs(self._job_id)
                if logs:
                    logger.error(f"Job logs:\n{logs}")

                raise AirflowException(error_msg)

            logger.info(f"Spark Kubernetes job {self._job_id} completed successfully")

            # Push job ID to XCom
            context["task_instance"].xcom_push(key="k8s_spark_job_id", value=self._job_id)

            return self._job_id

        except Exception as e:
            logger.error(f"Error executing Spark Kubernetes job: {str(e)}")
            raise AirflowException(f"Spark Kubernetes job execution failed: {str(e)}") from e

    def on_kill(self):
        """Handle task kill by terminating Spark job."""
        if self._hook and self._job_id:
            logger.warning(f"Task killed, terminating Spark Kubernetes job {self._job_id}")
            self._hook.kill_job(self._job_id)
