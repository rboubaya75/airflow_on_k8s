from airflow import DAG
from airflow.decorators import task
from airflow.providers.sftp.hooks.sftp import SFTPHook
from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 5, 6),
}

# Define the DAG
with DAG(
    'sftp_to_minio_automate_with_tracking2',
    default_args=default_args,
    description='Transfer files from SFTP to Minio, then process',
    schedule_interval=None,  # Run every 5 minutes
    catchup=False,
    max_active_runs=1,  # Maximum number of active DAG runs
    concurrency=4,     # Maximum number of tasks that can run concurrently
) as dag:

    @task
    def start():
        logger.info("Starting the DAG")

    @task
    def list_new_zip_files():
        logger.info("Connecting to SFTP server...")
        hook = SFTPHook(ssh_conn_id='sftp_conn')
        files = hook.list_directory('/home/rachid')  # Replace with your SFTP directory
        logger.info(f"Files in directory: {files}")
        zip_files = [f for f in files if f.endswith('.zip')]
        logger.info(f"Zip files: {zip_files}")

        tracked_files_path = '/opt/airflow/dags/tracked_files.txt'
        logger.info(f"Checking tracked files at: {tracked_files_path}")
        if not os.path.exists(tracked_files_path):
            logger.info("Tracked files not found, creating a new file.")
            with open(tracked_files_path, 'w') as f:
                f.write("")

        with open(tracked_files_path, 'r') as f:
            tracked_files = f.read().splitlines()
            logger.info(f"Tracked files: {tracked_files}")

        new_files = [file for file in zip_files if file not in tracked_files]
        logger.info(f"New zip files: {new_files}")

        if new_files:
            with open(tracked_files_path, 'a') as f:
                f.writelines(f"{file}\n" for file in new_files)
            logger.info(f"New files added to tracked files: {new_files}")
        else:
            logger.info("No new zip files found.")

        return new_files

    @task
    def check_files(new_files):
        logger.info(f"Files to be transferred: {new_files}")
        if not new_files:
            return 'stop_pipeline'
        return 'create_transfer_tasks'

    @task
    def create_transfer_tasks(new_files):
        for file in new_files:
            SFTPToS3Operator(
                task_id=f'transfer_file_{file}',
                sftp_conn_id='sftp_conn',
                sftp_path=f'/home/rachid/{file}',  # Exact path for each file
                s3_conn_id='minio_conn',
                s3_bucket='landing',
                s3_key=f'{file}',  # Path in the S3 bucket
            ).execute(context={})
            logger.info(f"Transferred {file} successfully.")

    @task
    def stop_pipeline():
        logger.info("Stopping the pipeline as no new files were found")

    @task
    def end():
        logger.info("Ending the DAG")

    # Task dependencies
    new_files = list_new_zip_files()
    check_result = check_files(new_files)
    start() >> new_files >> check_result

    check_result >> create_transfer_tasks(new_files) >> end()
    check_result >> stop_pipeline() >> end()
