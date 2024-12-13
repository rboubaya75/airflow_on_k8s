from airflow import DAG
from airflow.decorators import task
from airflow.providers.sftp.hooks.sftp import SFTPHook
from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import os
import logging
import zipfile
import tempfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.trino.operators.trino import TrinoOperator
from airflow.utils.dates import days_ago
from airflow.exceptions import AirflowSkipException


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
                s3_key=f'zip_files/{file}',  # Path in the S3 bucket
            ).execute(context={})
            logger.info(f"Transferred {file} successfully.")

    @task
    def unzip_and_transform():
        s3_hook = S3Hook(aws_conn_id='minio_conn')
        zip_files = s3_hook.list_keys(bucket_name='landing', prefix='zip_files/', delimiter='/')
        logger.info(f"Found zip files in Minio: {zip_files}")

        for zip_file in zip_files:
            if zip_file.endswith('.zip'):
                logger.info(f"Processing file: {zip_file}")
                zip_obj = s3_hook.get_key(key=zip_file, bucket_name='landing')

                with tempfile.TemporaryDirectory() as tmp_dir:
                    zip_path = os.path.join(tmp_dir, zip_file.split('/')[-1])
                    with open(zip_path, 'wb') as f:
                        f.write(zip_obj.get()['Body'].read())

                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(tmp_dir)

                    for root, _, files in os.walk(tmp_dir):
                        for file in files:
                            if file.endswith('.csv'):
                                file_path = os.path.join(root, file)
                                df = pd.read_csv(file_path)
                                table = pa.Table.from_pandas(df)
                                buffer = BytesIO()
                                pq.write_table(table, buffer)
                                buffer.seek(0)
                                parquet_key = f"parquet_files/{file.replace('.csv', '.parquet')}"
                                s3_hook.load_bytes(buffer.getvalue(), key=parquet_key, bucket_name='staging', replace=True)
                                logger.info(f"Uploaded Parquet file to Minio: {parquet_key}")

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

    check_result >> create_transfer_tasks(new_files) >> unzip_and_transform() >> end()
    check_result >> stop_pipeline() >> end()





MINIO_CONN_ID = 'minio_conn'
MINIO_BUCKET_NAME = 'staging'

SUPERSET_URL = "http://superset.superset.svc.cluster.local:8088"
SUPERSET_USERNAME = "admin"
SUPERSET_PASSWORD = "admin_password"
DATABASE_ID = 1  # The ID of the database in Superset (replace with your actual database ID)

def add_table_to_superset(table_name):
    auth_payload = {
        "username": SUPERSET_USERNAME,
        "password": SUPERSET_PASSWORD,
        "provider": "db",
        "refresh": True
    }
    session = requests.Session()
    auth_response = session.post(f"{SUPERSET_URL}/api/v1/security/login", json=auth_payload)
    
    if auth_response.status_code != 200:
        raise Exception("Failed to authenticate with Superset")
    
    csrf_token = session.cookies.get('csrf_access_token')
    
    table_payload = {
        "database": DATABASE_ID,
        "schema": "default",
        "table_name": table_name,
        "is_sqllab_view": False,
        "template_params": None,
        "sql": None
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }
    
    add_table_response = session.post(f"{SUPERSET_URL}/api/v1/table/", json=table_payload, headers=headers)
    
    if add_table_response.status_code != 201:
        raise Exception(f"Failed to add table to Superset: {add_table_response.text}")

def create_table_and_update_superset(**context):
    file_key = context['task_instance'].xcom_pull(task_ids='sense_minio')
    if not file_key:
        raise AirflowSkipException("No new Parquet files found in Minio bucket.")

    file_name = file_key.split('/')[-1]
    table_name = file_name.replace('.parquet', '')
    
    create_table_sql = f"""
    CREATE TABLE hive.default.{table_name} (
        id INT,
        name STRING
    )
    WITH (
        external_location = 's3a://{MINIO_BUCKET_NAME}/{file_key}',
        format = 'PARQUET'
    );
    """
    
    # Create and execute a new Trino task dynamically
    trino_task = TrinoOperator(
        task_id=f'create_table_{table_name}',
        sql=create_table_sql,
        trino_conn_id='trino_conn',
        dag=dag,
    )
    trino_task.execute(context)

    # Add the new table to Superset
    #add_table_to_superset(table_name)

sense_minio = S3KeySensor(
    task_id='sense_minio',
    bucket_key='parquets/*.parquet',
    wildcard_match=True,
    bucket_name=MINIO_BUCKET_NAME,
    aws_conn_id=MINIO_CONN_ID,
    timeout=18*60*60,
    poke_interval=60,
    dag=dag,
)

process_new_file = PythonOperator(
    task_id='process_new_file',
    python_callable=create_table_and_update_superset,
    provide_context=True,
    dag=dag,
)

sense_minio >> process_new_file
