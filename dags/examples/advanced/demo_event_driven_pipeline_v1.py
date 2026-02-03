"""
Event-Driven Pipeline - Advanced Example DAG

This DAG demonstrates event-driven workflow patterns using file sensors and
dynamic trigger conditions. Shows how to build reactive pipelines that respond
to external events rather than running on fixed schedules.

Pattern Demonstrated:
- FileSensor: Wait for files to arrive before processing
- Dynamic branching based on file attributes
- Event-driven vs schedule-driven architecture
- File parsing and metadata extraction
- Idempotent file processing with checksums

Use Case:
Process incoming sales data files as soon as they arrive in a landing zone.
Different processing paths based on file size and format. Demonstrates
building reactive data pipelines.

Learning Objectives:
- Understand event-driven vs schedule-driven patterns
- Learn sensor usage and timeout handling
- See dynamic workflow branching based on runtime conditions
- Understand idempotency in file processing
- Learn file metadata extraction patterns

Constitutional Compliance:
- Principle I: DAG-First Development (reactive workflow design)
- Principle V: Observability (event tracking, file processing audit)
"""

import hashlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.trigger_rule import TriggerRule

logger = logging.getLogger(__name__)


# Default arguments
default_args = {
    "owner": "data-engineering@example.com",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}


# File landing zone configuration
# DESIGN-001: Use Airflow Variable for configurable path in production:
#   from airflow.models import Variable
#   LANDING_ZONE = Variable.get("landing_zone_path", default_var="/tmp/airflow/landing_zone")
LANDING_ZONE = "/tmp/airflow/landing_zone"  # Demo only; use Variable in production
FILE_PATTERN = "sales_data_*.csv"


def setup_landing_zone(**context):
    """
    Setup landing zone directory for file arrival.

    In production, this would be a shared filesystem, S3 bucket, or SFTP location.
    For demo, we create a local directory and simulate file arrival.

    Args:
        **context: Airflow context dictionary
    """
    os.makedirs(LANDING_ZONE, exist_ok=True)
    logger.info(f"Landing zone ready: {LANDING_ZONE}")

    # Simulate file arrival for demo
    # In real implementation, files would be dropped by external systems
    execution_date = context["execution_date"]
    filename = f"sales_data_{execution_date.strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(LANDING_ZONE, filename)

    # Create dummy file with sample content
    sample_data = """transaction_id,customer_id,product_id,quantity,amount
TXN001,CUST1234,PROD001,5,129.99
TXN002,CUST5678,PROD002,2,49.98
TXN003,CUST9012,PROD003,1,199.99
"""
    with open(filepath, "w") as f:
        f.write(sample_data)

    logger.info(f"Simulated file arrival: {filepath}")

    # Push filename to XCom for downstream tasks
    context["task_instance"].xcom_push(key="trigger_file", value=filename)

    return {"landing_zone": LANDING_ZONE, "trigger_file": filename}


def extract_file_metadata(**context):
    """
    Extract metadata from detected file for downstream processing decisions.

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: File metadata
    """
    task_instance = context["task_instance"]

    # Get filename from sensor or setup task
    filename = task_instance.xcom_pull(task_ids="setup_landing_zone", key="trigger_file")

    if not filename:
        logger.error("No trigger file found")
        return {"status": "error", "message": "No file detected"}

    filepath = os.path.join(LANDING_ZONE, filename)

    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return {"status": "error", "message": "File not found"}

    # Extract file metadata
    file_stats = os.stat(filepath)
    file_size_bytes = file_stats.st_size
    file_size_mb = file_size_bytes / (1024 * 1024)

    # Calculate file checksum for idempotency using SHA-256 (BUG-004 fix: MD5 is weak)
    # INEFF-004 fix: Read file in chunks for memory efficiency
    hash_obj = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_obj.update(chunk)
    file_hash = hash_obj.hexdigest()

    # Count lines to estimate record count
    with open(filepath) as f:
        line_count = sum(1 for line in f) - 1  # Subtract header

    # Determine file format
    file_extension = Path(filepath).suffix.lower()
    supported_formats = [".csv", ".json", ".parquet"]
    is_supported_format = file_extension in supported_formats

    metadata = {
        "filename": filename,
        "filepath": filepath,
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_mb, 2),
        "file_hash": file_hash,
        "estimated_records": line_count,
        "file_format": file_extension,
        "is_supported_format": is_supported_format,
        "detection_timestamp": datetime.now().isoformat(),
    }

    logger.info("=" * 80)
    logger.info("FILE METADATA EXTRACTED")
    logger.info("=" * 80)
    logger.info(f"File: {filename}")
    logger.info(f"Size: {file_size_mb:.2f} MB")
    logger.info(f"Estimated Records: {line_count:,}")
    logger.info(f"Format: {file_extension}")
    logger.info(f"Checksum: {file_hash}")
    logger.info("=" * 80)

    # Push metadata to XCom
    task_instance.xcom_push(key="file_metadata", value=metadata)

    return metadata


def decide_processing_path(**context):
    """
    Branch operator to decide processing path based on file size.

    Small files (< 10MB): Process with single task
    Large files (>= 10MB): Process with parallel chunking

    Args:
        **context: Airflow context dictionary

    Returns:
        str: Task ID of next task to execute
    """
    task_instance = context["task_instance"]

    metadata = task_instance.xcom_pull(task_ids="extract_file_metadata", key="file_metadata")

    if not metadata:
        logger.error("No file metadata available for branching decision")
        return "handle_error"

    if not metadata.get("is_supported_format"):
        logger.warning(f"Unsupported file format: {metadata.get('file_format')}")
        return "handle_unsupported_format"

    file_size_mb = metadata.get("file_size_mb", 0)
    threshold_mb = 10.0

    if file_size_mb < threshold_mb:
        logger.info(
            f"File size {file_size_mb:.2f} MB < {threshold_mb} MB: using small file processing"
        )
        return "process_small_file"
    else:
        logger.info(
            f"File size {file_size_mb:.2f} MB >= {threshold_mb} MB: using large file processing"
        )
        return "process_large_file"


def process_small_file(**context):
    """
    Process small files in single task (simpler, faster for small data).

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Processing results
    """
    task_instance = context["task_instance"]

    metadata = task_instance.xcom_pull(task_ids="extract_file_metadata", key="file_metadata")

    logger.info(f"Processing small file: {metadata['filename']}")
    logger.info(f"Estimated records: {metadata['estimated_records']:,}")

    # Simulate processing
    # In real implementation: parse CSV, validate, load to staging table
    filepath = metadata["filepath"]

    with open(filepath) as f:
        lines = f.readlines()
        records_processed = len(lines) - 1  # Subtract header

    result = {
        "processing_mode": "small_file",
        "filename": metadata["filename"],
        "records_processed": records_processed,
        "file_hash": metadata["file_hash"],
        "processing_timestamp": datetime.now().isoformat(),
        "status": "success",
    }

    logger.info(f"Small file processing complete: {records_processed} records processed")

    task_instance.xcom_push(key="processing_result", value=result)

    return result


def process_large_file(**context):
    """
    Process large files with parallel chunking (more complex, scalable).

    Args:
        **context: Airflow context dictionary

    Returns:
        dict: Processing results
    """
    task_instance = context["task_instance"]

    metadata = task_instance.xcom_pull(task_ids="extract_file_metadata", key="file_metadata")

    logger.info(f"Processing large file: {metadata['filename']}")
    logger.info(f"Estimated records: {metadata['estimated_records']:,}")

    # Simulate parallel chunked processing
    # In real implementation: split file, process chunks in parallel, merge results
    chunk_size = 1000  # Records per chunk
    estimated_chunks = max(1, metadata["estimated_records"] // chunk_size)

    logger.info(f"Processing in {estimated_chunks} parallel chunks")

    result = {
        "processing_mode": "large_file",
        "filename": metadata["filename"],
        "records_processed": metadata["estimated_records"],
        "chunks_processed": estimated_chunks,
        "file_hash": metadata["file_hash"],
        "processing_timestamp": datetime.now().isoformat(),
        "status": "success",
    }

    logger.info(
        f"Large file processing complete: {metadata['estimated_records']} records in {estimated_chunks} chunks"
    )

    task_instance.xcom_push(key="processing_result", value=result)

    return result


def handle_unsupported_format(**context):
    """
    Handle files with unsupported formats.

    Args:
        **context: Airflow context dictionary
    """
    task_instance = context["task_instance"]

    metadata = task_instance.xcom_pull(task_ids="extract_file_metadata", key="file_metadata")

    # BUG-005 fix: Add null check before accessing metadata
    if not metadata:
        logger.error("No metadata available")
        return {"status": "error", "reason": "no_metadata"}

    logger.warning(f"Unsupported file format: {metadata.get('file_format')}")
    logger.warning(f"File: {metadata.get('filename')}")
    logger.warning("Supported formats: .csv, .json, .parquet")

    # In real implementation: move file to error folder, send notification
    result = {
        "status": "skipped",
        "reason": "unsupported_format",
        "filename": metadata.get("filename"),
        "file_format": metadata.get("file_format"),
    }

    task_instance.xcom_push(key="processing_result", value=result)

    return result


def archive_processed_file(**context):
    """
    Archive processed file to prevent reprocessing.

    Uses file hash for idempotency tracking.

    Args:
        **context: Airflow context dictionary
    """
    task_instance = context["task_instance"]

    # Get processing result and metadata
    result = task_instance.xcom_pull(
        task_ids=["process_small_file", "process_large_file", "handle_unsupported_format"]
    )

    # Get the non-None result
    processing_result = next((r for r in result if r is not None), None)

    if not processing_result:
        logger.warning("No processing result found - skipping archive")
        return

    metadata = task_instance.xcom_pull(task_ids="extract_file_metadata", key="file_metadata")

    logger.info(f"Archiving file: {metadata['filename']}")
    logger.info(f"File hash: {metadata['file_hash']}")
    logger.info(f"Processing status: {processing_result.get('status')}")

    # In real implementation:
    # 1. Move file to archive folder
    # 2. Log file hash to database to prevent reprocessing
    # 3. Set retention policy (e.g., delete after 30 days)

    logger.info("File archived successfully")


def log_completion(**context):
    """
    Log final pipeline status.

    Args:
        **context: Airflow context dictionary
    """
    task_instance = context["task_instance"]

    metadata = task_instance.xcom_pull(task_ids="extract_file_metadata", key="file_metadata")

    result = task_instance.xcom_pull(
        task_ids=["process_small_file", "process_large_file", "handle_unsupported_format"]
    )

    processing_result = next((r for r in result if r is not None), None)

    logger.info("=" * 80)
    logger.info("EVENT-DRIVEN PIPELINE SUMMARY")
    logger.info("=" * 80)

    if metadata:
        logger.info(f"Trigger File: {metadata['filename']}")
        logger.info(f"File Size: {metadata['file_size_mb']:.2f} MB")
        logger.info(f"File Format: {metadata['file_format']}")

    if processing_result:
        logger.info(f"Processing Mode: {processing_result.get('processing_mode', 'N/A')}")
        logger.info(f"Records Processed: {processing_result.get('records_processed', 0):,}")
        logger.info(f"Status: {processing_result.get('status', 'unknown')}")

    logger.info("=" * 80)


# Define the DAG
with DAG(
    dag_id="demo_event_driven_pipeline_v1",
    default_args=default_args,
    description="Demonstrates event-driven pipeline with file sensors and dynamic branching",
    schedule=None,  # Event-driven, not scheduled
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["advanced", "event-driven", "sensor", "dynamic", "demo"],
    doc_md=__doc__,
) as dag:
    # Setup: Prepare landing zone and simulate file arrival
    # In production, this step wouldn't exist - files arrive externally
    setup = PythonOperator(
        task_id="setup_landing_zone",
        python_callable=setup_landing_zone,
        doc_md="Setup landing zone and simulate file arrival (demo only)",
    )

    # SENSOR: Wait for file to arrive in landing zone
    # Note: For demo, file is created by setup task
    # In production, sensor would wait for external file drop
    wait_for_file = FileSensor(
        task_id="wait_for_file",
        filepath=os.path.join(LANDING_ZONE, FILE_PATTERN),
        poke_interval=10,  # Check every 10 seconds
        timeout=300,  # 5 minutes timeout
        mode="poke",  # Could use "reschedule" for longer waits
        doc_md="""
        Wait for file to arrive in landing zone.

        Uses FileSensor to detect file arrival. In production, this would
        wait for external systems to drop files into shared storage.
        """,
    )

    # Extract file metadata for processing decisions
    extract_metadata = PythonOperator(
        task_id="extract_file_metadata",
        python_callable=extract_file_metadata,
        doc_md="Extract file metadata (size, format, checksum) for routing decisions",
    )

    # BRANCH: Decide processing path based on file attributes
    decide_path = BranchPythonOperator(
        task_id="decide_processing_path",
        python_callable=decide_processing_path,
        doc_md="""
        Branch based on file size and format.

        Small files (< 10MB): Simple single-task processing
        Large files (>= 10MB): Parallel chunked processing
        Unsupported format: Error handling path
        """,
    )

    # Processing paths
    small_file = PythonOperator(
        task_id="process_small_file",
        python_callable=process_small_file,
        doc_md="Process small files in single task",
    )

    large_file = PythonOperator(
        task_id="process_large_file",
        python_callable=process_large_file,
        doc_md="Process large files with parallel chunking",
    )

    unsupported = PythonOperator(
        task_id="handle_unsupported_format",
        python_callable=handle_unsupported_format,
        doc_md="Handle files with unsupported formats",
    )

    # Join point after branch
    join = EmptyOperator(
        task_id="join",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
        doc_md="Join point after processing branches",
    )

    # Archive processed file
    archive = PythonOperator(
        task_id="archive_file",
        python_callable=archive_processed_file,
        trigger_rule=TriggerRule.NONE_FAILED,
        doc_md="Archive processed file and log hash for idempotency",
    )

    # Log completion
    complete = PythonOperator(
        task_id="log_completion",
        python_callable=log_completion,
        trigger_rule=TriggerRule.ALL_DONE,
        doc_md="Log final pipeline status",
    )

    # Define task dependencies
    # Event trigger: setup → wait for file → extract metadata → branch
    # Branch paths: small/large/unsupported → join → archive → complete
    setup >> wait_for_file >> extract_metadata >> decide_path

    # Branch outcomes
    decide_path >> small_file >> join
    decide_path >> large_file >> join
    decide_path >> unsupported >> join

    # Post-processing
    join >> archive >> complete
