"""
Spark Hook for Apache Airflow.

Provides functionality for submitting and monitoring Spark jobs across different cluster types.
Supports job submission, status polling, log retrieval, and job termination.
"""

import subprocess
import tempfile
import time
from enum import Enum

from airflow.exceptions import AirflowException
from airflow.hooks.base import BaseHook

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SparkJobStatus(Enum):
    """Enumeration of possible Spark job statuses."""

    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class SparkSubmitException(AirflowException):
    """Exception raised when spark-submit fails."""

    pass


class SparkHook(BaseHook):
    """
    Hook for interacting with Apache Spark clusters.

    Supports job submission, monitoring, and management for Spark applications.
    Works with Standalone, YARN, and Kubernetes cluster managers.

    :param conn_id: Airflow connection ID for Spark cluster
    :param verbose: Enable verbose logging for spark-submit
    """

    conn_name_attr = "conn_id"
    default_conn_name = "spark_default"
    conn_type = "spark"
    hook_name = "Spark"

    def __init__(self, conn_id: str = default_conn_name, verbose: bool = False):
        """Initialize Spark hook."""
        super().__init__()
        self.conn_id = conn_id
        self.verbose = verbose
        self._jobs: dict[str, subprocess.Popen] = {}
        self._job_logs: dict[str, tuple[str, str]] = {}  # job_id -> (stdout_path, stderr_path)
        self._connection = None
        self._master_url = None
        self._spark_binary = None

    def get_conn(self):
        """Get connection to Spark cluster."""
        if self._connection is None:
            self._connection = self.get_connection(self.conn_id)
        return self._connection

    @property
    def master_url(self) -> str:
        """Get Spark master URL from connection."""
        if self._master_url is None:
            conn = self.get_conn()
            if conn.host:
                port = conn.port or 7077
                self._master_url = f"spark://{conn.host}:{port}"
            else:
                self._master_url = "local"
        return self._master_url

    def get_spark_binary(self) -> str:
        """Get path to spark-submit binary."""
        if self._spark_binary is None:
            conn = self.get_conn()
            extra = getattr(conn, "extra_dejson", None) or {}
            self._spark_binary = extra.get("spark_binary", "spark-submit")
        return self._spark_binary

    def build_submit_command(
        self,
        application: str,
        master: str | None = None,
        deploy_mode: str | None = None,
        name: str | None = None,
        conf: dict[str, str] | None = None,
        application_args: list[str] | None = None,
        driver_memory: str | None = None,
        driver_cores: str | None = None,
        executor_memory: str | None = None,
        executor_cores: str | None = None,
        num_executors: str | None = None,
    ) -> list[str]:
        """
        Build spark-submit command with all parameters.

        :param application: Path to Spark application (JAR or Python file)
        :param master: Spark master URL (overrides connection)
        :param deploy_mode: Deploy mode (client or cluster)
        :param name: Application name
        :param conf: Spark configuration properties
        :param application_args: Arguments to pass to application
        :param driver_memory: Driver memory (e.g., '1g')
        :param driver_cores: Number of driver cores
        :param executor_memory: Executor memory (e.g., '2g')
        :param executor_cores: Number of executor cores
        :param num_executors: Number of executors
        :return: Command as list of strings
        """
        command = [self.get_spark_binary()]

        # Master URL
        master_url = master or self.master_url
        command.extend(["--master", master_url])

        # Deploy mode
        if deploy_mode:
            command.extend(["--deploy-mode", deploy_mode])

        # Application name
        if name:
            command.extend(["--name", name])

        # Resource configuration
        if driver_memory:
            command.extend(["--driver-memory", driver_memory])
        if driver_cores:
            command.extend(["--driver-cores", str(driver_cores)])
        if executor_memory:
            command.extend(["--executor-memory", executor_memory])
        if executor_cores:
            command.extend(["--executor-cores", str(executor_cores)])
        if num_executors:
            command.extend(["--num-executors", str(num_executors)])

        # Spark configuration
        if conf:
            for key, value in conf.items():
                command.extend(["--conf", f"{key}={value}"])

        # Verbose mode
        if self.verbose:
            command.append("--verbose")

        # Application path
        command.append(application)

        # Application arguments
        if application_args:
            command.extend(application_args)

        logger.info(f"Built spark-submit command: {' '.join(command)}")
        return command

    def submit_job(
        self,
        application: str,
        master: str | None = None,
        deploy_mode: str | None = None,
        name: str | None = None,
        conf: dict[str, str] | None = None,
        application_args: list[str] | None = None,
        **kwargs,
    ) -> str:
        """
        Submit Spark job and return job ID.

        :param application: Path to Spark application
        :param master: Spark master URL
        :param deploy_mode: Deploy mode (client or cluster)
        :param name: Application name
        :param conf: Spark configuration
        :param application_args: Application arguments
        :param kwargs: Additional parameters for build_submit_command
        :return: Job ID for tracking
        """
        command = self.build_submit_command(
            application=application,
            master=master,
            deploy_mode=deploy_mode,
            name=name,
            conf=conf,
            application_args=application_args,
            **kwargs,
        )

        try:
            logger.info(f"Submitting Spark job: {name or application}")

            # Use temp files instead of PIPE to avoid blocking on large output
            stdout_file = tempfile.NamedTemporaryFile(
                mode="w", suffix="_stdout.log", delete=False
            )
            stderr_file = tempfile.NamedTemporaryFile(
                mode="w", suffix="_stderr.log", delete=False
            )

            process = subprocess.Popen(
                command,
                stdout=stdout_file,
                stderr=stderr_file,
                universal_newlines=True,
            )

            # Generate job ID from process PID and timestamp
            job_id = f"spark-{process.pid}-{int(time.time())}"
            self._jobs[job_id] = process
            self._job_logs[job_id] = (stdout_file.name, stderr_file.name)

            logger.info(f"Spark job submitted successfully. Job ID: {job_id}, PID: {process.pid}")
            return job_id

        except Exception as e:
            error_msg = f"Failed to submit Spark job: {str(e)}"
            logger.error(error_msg)
            raise SparkSubmitException(error_msg) from e

    def get_job_status(self, job_id: str) -> SparkJobStatus:
        """
        Get current status of Spark job.

        :param job_id: Job ID returned from submit_job
        :return: Current job status
        """
        if job_id not in self._jobs:
            logger.warning(f"Job ID {job_id} not found in tracked jobs")
            return SparkJobStatus.UNKNOWN

        process = self._jobs[job_id]
        return_code = process.poll()

        if return_code is None:
            # Process is still running
            return SparkJobStatus.RUNNING
        elif return_code == 0:
            # Process completed successfully
            return SparkJobStatus.SUCCEEDED
        else:
            # Process failed
            return SparkJobStatus.FAILED

    def wait_for_completion(
        self, job_id: str, timeout: int | None = None, poll_interval: int = 5
    ) -> bool:
        """
        Wait for Spark job to complete.

        :param job_id: Job ID to wait for
        :param timeout: Maximum time to wait in seconds (None = wait forever)
        :param poll_interval: Interval between status checks in seconds
        :return: True if job succeeded, False if failed or timeout
        """
        if job_id not in self._jobs:
            logger.error(f"Job ID {job_id} not found")
            return False

        logger.info(f"Waiting for job {job_id} to complete (timeout={timeout}s)")
        start_time = time.time()

        while True:
            status = self.get_job_status(job_id)

            if status == SparkJobStatus.SUCCEEDED:
                logger.info(f"Job {job_id} completed successfully")
                return True
            elif status == SparkJobStatus.FAILED:
                logger.error(f"Job {job_id} failed")
                return False

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"Job {job_id} timed out after {timeout} seconds")
                return False

            # Wait before next poll
            time.sleep(poll_interval)

    def kill_job(self, job_id: str, force: bool = False):
        """
        Kill a running Spark job.

        :param job_id: Job ID to kill
        :param force: Use SIGKILL instead of SIGTERM
        """
        if job_id not in self._jobs:
            logger.warning(f"Job ID {job_id} not found, cannot kill")
            return

        process = self._jobs[job_id]

        if process.poll() is not None:
            logger.info(f"Job {job_id} is already terminated")
            return

        try:
            if force:
                logger.warning(f"Force killing job {job_id}")
                process.kill()
            else:
                logger.info(f"Terminating job {job_id}")
                process.terminate()

            # Wait for process to terminate
            process.wait(timeout=10)
            logger.info(f"Job {job_id} terminated successfully")

        except subprocess.TimeoutExpired:
            logger.warning(f"Job {job_id} did not terminate, force killing")
            process.kill()
        except Exception as e:
            logger.error(f"Error killing job {job_id}: {str(e)}")

    def get_job_logs(self, job_id: str) -> str | None:
        """
        Retrieve logs for a Spark job.

        :param job_id: Job ID to get logs for
        :return: Job logs as string, or None if not available
        """
        if job_id not in self._jobs:
            logger.warning(f"Job ID {job_id} not found")
            return None

        if job_id not in self._job_logs:
            logger.warning(f"No log files found for job {job_id}")
            return None

        stdout_path, stderr_path = self._job_logs[job_id]

        try:
            # Read logs from temp files (safe even while process is running)
            stdout = ""
            stderr = ""
            with open(stdout_path) as f:
                stdout = f.read()
            with open(stderr_path) as f:
                stderr = f.read()
            logs = f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}"
            return logs
        except Exception as e:
            logger.error(f"Error retrieving logs for job {job_id}: {str(e)}")
            return None

    def cleanup_job(self, job_id: str):
        """
        Clean up job tracking and temp log files for completed job.

        :param job_id: Job ID to clean up
        """
        if job_id in self._jobs:
            del self._jobs[job_id]

        # Clean up temp log files
        if job_id in self._job_logs:
            import os

            stdout_path, stderr_path = self._job_logs[job_id]
            for path in (stdout_path, stderr_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            del self._job_logs[job_id]

        logger.debug(f"Cleaned up tracking for job {job_id}")
