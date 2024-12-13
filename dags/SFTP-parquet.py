import logging
from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.sftp.hooks.sftp import SFTPHook
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from datetime import datetime, timedelta
from io import BytesIO
import os
import tempfile
import zipfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Constants
MINIO_ENDPOINT = "10.98.210.183:9000"
MINIO_ACCESS_KEY = "TLzIBJM3DcfUyUwYuiDm"
MINIO_SECRET_KEY = "aNiWKBv6uxBmnaMNDEJX3KX9IWfB9MnVl212m8JW"
LANDING_BUCKET_NAME = "landing"
RAW_BUCKET_NAME = "raw"
STAGING_BUCKET_NAME = "staging"

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 5, 23),
}

# Initialize the DAG
with DAG(
    'sftp_to_minio_and_process',
    default_args=default_args,
    description='Transfer files from SFTP to Minio, then process',
    schedule_interval=timedelta(minutes=5),
    catchup=False,
) as dag:

    start_task = DummyOperator(task_id='start')

    def get_latest_file(**kwargs):
        hook = SFTPHook(ssh_conn_id='ssh_conn')
        files = hook.list_directory('/home/rachid')
        logging.info(f"Files in SFTP directory: {files}")
        filtered_files = [file for file in files if file.endswith('.zip')]
        logging.info(f"Filtered files: {filtered_files}")
        if not filtered_files:
            raise FileNotFoundError("No files with extension .zip found in /home/rachid")
        latest_file = sorted(filtered_files)[-1]
        logging.info(f"Latest file to transfer: {latest_file}")
        return latest_file

    list_files = PythonOperator(
        task_id='get_latest_file',
        python_callable=get_latest_file,
    )

    transfer_task_op = SFTPToS3Operator(
        task_id='transfer_latest_file',
        sftp_conn_id='sftp_conn',
        sftp_path='/home/rachid/{{ task_instance.xcom_pull(task_ids="get_latest_file") }}',
        s3_conn_id='minio_conn',
        s3_bucket=LANDING_BUCKET_NAME,
        s3_key='{{ task_instance.xcom_pull(task_ids="get_latest_file") }}',
    )

    detect_zip_upload = S3KeySensor(
        task_id='detect_zip_upload',
        bucket_name=LANDING_BUCKET_NAME,
        bucket_key='*.zip',
        wildcard_match=True,
        verify=False,
        aws_conn_id='minio_conn',
        timeout=18 * 3600,
        poke_interval=60,
    )

    def unzip_and_upload_files(**kwargs):
        """Extracts files from all zip files in the source bucket and uploads contents to another bucket."""
        s3_hook = S3Hook(aws_conn_id='minio_conn', verify=False)
        keys = s3_hook.list_keys(bucket_name=LANDING_BUCKET_NAME, delimiter='/')
        zip_keys = [key for key in keys if key.endswith('.zip')]

        for zip_key in zip_keys:
            source_obj = s3_hook.get_key(zip_key, bucket_name=LANDING_BUCKET_NAME)
            with tempfile.TemporaryDirectory() as tmp_dir:
                zip_path = os.path.join(tmp_dir, zip_key.split('/')[-1])
                with open(zip_path, 'wb') as f:
                    f.write(source_obj.get()['Body'].read())
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                for root, _, files in os.walk(tmp_dir):
                    for file in files:
                        if file.endswith('.csv'):
                            file_path = os.path.join(root, file)
                            s3_path = file_path[len(tmp_dir) + 1:]
                            s3_hook.load_file(filename=file_path, key=s3_path, bucket_name=RAW_BUCKET_NAME, replace=True)

    unzip_and_upload = PythonOperator(
        task_id='unzip_and_upload',
        python_callable=unzip_and_upload_files,
    )

    def transform_csv_to_parquet(**kwargs):
        """Transforms each CSV file in a bucket to Parquet and uploads it."""
        s3_hook = S3Hook(aws_conn_id='minio_conn', verify=False)
        keys = s3_hook.list_keys(bucket_name=RAW_BUCKET_NAME)
        for key in keys:
            if key.endswith('.csv'):
                csv_obj = s3_hook.get_key(key, bucket_name=RAW_BUCKET_NAME)
                df = pd.read_csv(csv_obj.get()['Body'])
                table = pa.Table.from_pandas(df)
                buffer = BytesIO()
                pq.write_table(table, buffer)
                buffer.seek(0)
                subdir = "parquets"
                parquet_key = f"{subdir}/{key.replace('.csv', '.parquet')}"
                s3_hook.load_bytes(buffer.getvalue(), key=parquet_key, bucket_name=STAGING_BUCKET_NAME, replace=True)

    transform_to_parquet = PythonOperator(
        task_id='transform_csv_to_parquet',
        python_callable=transform_csv_to_parquet,
    )

    end_task = DummyOperator(task_id='end')

    # Task sequence
    start_task >> list_files >> transfer_task_op >> detect_zip_upload >> unzip_and_upload >> transform_to_parquet >> end_task
