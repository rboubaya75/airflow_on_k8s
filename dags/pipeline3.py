import os
import logging
import tempfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
from datetime import datetime, timedelta
import zipfile  # Ensure this module is imported
from airflow import DAG
from airflow.decorators import task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.trino.hooks.trino import TrinoHook
from airflow.providers.sftp.hooks.sftp import SFTPHook
from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowSkipException
from airflow.utils.dates import days_ago
import re

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

def extract_alpha_prefix(filename, length=15):
    return ''.join(re.findall(r'[a-zA-Z]', filename)[:length])

def convert_arrow_type_to_trino_type(arrow_type):
    if pa.types.is_int64(arrow_type):
        return 'bigint'
    elif pa.types.is_float64(arrow_type):
        return 'double'
    elif pa.types.is_string(arrow_type):
        return 'varchar'
    elif pa.types.is_timestamp(arrow_type):
        return 'timestamp'
    elif pa.types.is_boolean(arrow_type):
        return 'boolean'
    else:
        raise ValueError(f"Unsupported Arrow type: {arrow_type}")

def create_table_and_update_superset(**context):
    import traceback

    schema_directories = context['ti'].xcom_pull(task_ids='unzip_and_transform')
    s3_hook = S3Hook(aws_conn_id='minio_conn')

    for schema_dir, parquet_files in schema_directories.items():
        if not parquet_files:
            logger.info(f"No files found in directory: {schema_dir}")
            continue

        file_sample = parquet_files[0]  # Use the first file to infer the schema
        obj = s3_hook.get_key(key=file_sample, bucket_name='staging')
        
        logger.info(f"Parquet files: {parquet_files}")
        logger.info(f"Sample file for schema inference: {file_sample}")
        
        try:
            with tempfile.TemporaryFile() as fp:
                fp.write(obj.get()['Body'].read())
                fp.seek(0)
                table = pq.read_table(fp)
        except Exception as e:
            logger.error(f"Error reading Parquet file: {e}")
            logger.error(traceback.format_exc())
            continue

        schema = table.schema
        schema_sql = ", ".join([f'"{field.name.replace("-", "_")}" {convert_arrow_type_to_trino_type(field.type)}' for field in schema])

        table_name = schema_dir.split('/')[-1]
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS hive.default.{table_name} (
            {schema_sql}
        )
        WITH (
            external_location = 's3a://staging/{schema_dir}',
            format = 'PARQUET'
        )
        """

        logger.info(f"Executing SQL: {create_table_sql}")
        
        try:
            trino_hook = TrinoHook(trino_conn_id='trino_conn', schema='default')
            trino_hook.run(sql=create_table_sql)
            logger.info(f"Table {table_name} created successfully in Hive via Trino.")
        except Exception as e:
            logger.error(f"Error creating table in Trino: {e}")
            logger.error(traceback.format_exc())

# Define the DAG
with DAG(
    'sftp_to_minio_trino',
    default_args=default_args,
    description='Transfer files from SFTP to Minio, process them, and create tables in Trino',
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    concurrency=4,
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
    def stop_pipeline():
        logger.info("Stopping the pipeline as no new files were found")

    @task
    def end():
        logger.info("Ending the DAG")

    @task
    def unzip_and_transform():
        s3_hook = S3Hook(aws_conn_id='minio_conn')
        zip_files = s3_hook.list_keys(bucket_name='landing', prefix='zip_files/', delimiter='/')
        logger.info(f"Found zip files in Minio: {zip_files}")

        schema_directories = {}

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

                                alpha_prefix = extract_alpha_prefix(file)
                                schema_directory = f"parquets/{alpha_prefix}"
                                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                                parquet_key = f"{schema_directory}/{timestamp}_{file.replace('.csv', '.parquet')}"
                                
                                if schema_directory not in schema_directories:
                                    schema_directories[schema_directory] = []

                                schema_directories[schema_directory].append(parquet_key)

                                s3_hook.load_bytes(buffer.getvalue(), key=parquet_key, bucket_name='staging', replace=True)
                                logger.info(f"Uploaded Parquet file to Minio: {parquet_key}")

        return schema_directories

    process_new_files_task = PythonOperator(
        task_id='process_new_files',
        python_callable=create_table_and_update_superset,
        provide_context=True,
        dag=dag,
    )

    # Define the task dependencies
    start_task = start()
    list_files_task = list_new_zip_files()
    check_files_task = check_files(list_files_task)
    create_tasks_task = create_transfer_tasks(list_files_task)
    unzip_transform_task = unzip_and_transform()
    stop_pipeline_task = stop_pipeline()
    end_task = end()

    start_task >> list_files_task >> check_files_task
    check_files_task >> [stop_pipeline_task, create_tasks_task]
    create_tasks_task >> unzip_transform_task >> process_new_files_task >> end_task
