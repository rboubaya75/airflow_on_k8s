import logging
from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.sftp.hooks.sftp import SFTPHook
from datetime import datetime, timedelta

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Fetch variables from Airflow
sftp_conn_id = 'sftp_conn'
ssh_conn_id = 'ssh_conn'
sftp_path = '/home/rachid'  # Path to the directory on the SFTP server
file_extension = '.zip'  # Default to .zip
minio_conn_id = 'minio_conn'
minio_bucket = 'landing'

# Initialize the DAG
with DAG(
    'sftp_to_minio_directory',
    default_args=default_args,
    description='Transfer files in directory from SFTP to Minio',
    schedule_interval=timedelta(minutes=5),
    start_date=datetime(2024, 5, 23),
    catchup=False,
) as dag:

    start_task = DummyOperator(task_id='start')

    def get_latest_file(**kwargs):
        hook = SFTPHook(ssh_conn_id=ssh_conn_id)
        files = hook.list_directory(sftp_path)
        logging.info(f"Files in SFTP directory: {files}")
        # Filter files to only get those with the specified extension
        filtered_files = [file for file in files if file.endswith(file_extension)]
        logging.info(f"Filtered files: {filtered_files}")
        if not filtered_files:
            raise FileNotFoundError(f"No files with extension {file_extension} found in {sftp_path}")

        # Assuming we need the latest file by name (you can modify this to sort by date or other criteria)
        latest_file = sorted(filtered_files)[-1]
        logging.info(f"Latest file to transfer: {latest_file}")
        return latest_file

    list_files = PythonOperator(
        task_id='get_latest_file',
        python_callable=get_latest_file
    )

    transfer_task_op = SFTPToS3Operator(
        task_id='transfer_latest_file',
        sftp_conn_id=sftp_conn_id,
        sftp_path=f"{sftp_path}/{{{{ task_instance.xcom_pull(task_ids='get_latest_file') }}}}",
        s3_conn_id=minio_conn_id,
        s3_bucket=minio_bucket,
        s3_key="{{ task_instance.xcom_pull(task_ids='get_latest_file') }}"
    )

    end_task = DummyOperator(task_id='end')

    start_task >> list_files >> transfer_task_op >> end_task

