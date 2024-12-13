from airflow import DAG
from airflow.decorators import task
from airflow.providers.sftp.hooks.sftp import SFTPHook
from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.trino.hooks.trino import TrinoHook
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.exceptions import AirflowSkipException
from datetime import datetime, timedelta
import os
import logging
import zipfile
import tempfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO

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
                                parquet_key = f"parquets/{file.replace('.csv', '.parquet')}"
                                s3_hook.load_bytes(buffer.getvalue(), key=parquet_key, bucket_name='staging', replace=True)
                                logger.info(f"Uploaded Parquet file to Minio: {parquet_key}")

    @task
    def stop_pipeline():
        logger.info("Stopping the pipeline as no new files were found")

    @task
    def end():
        logger.info("Ending the DAG")

   
    # Trino integration to create Hive tables and update Superset
    MINIO_CONN_ID = 'minio_conn'
    MINIO_BUCKET_NAME = 'staging'

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

    def create_table_and_update_superset(**context):
        s3_hook = S3Hook(aws_conn_id=MINIO_CONN_ID)
        parquet_files = s3_hook.list_keys(bucket_name=MINIO_BUCKET_NAME, prefix='parquets/', delimiter='/')

        if not parquet_files:
            raise AirflowSkipException("No new Parquet files found in Minio bucket.")

        for file_key in parquet_files:
            file_name = file_key.split('/')[-1]
            table_name = file_name.replace('.parquet', '')

            # Download the Parquet file locally
            obj = s3_hook.get_key(key=file_key, bucket_name=MINIO_BUCKET_NAME)
            with tempfile.TemporaryFile() as fp:
                fp.write(obj.get()['Body'].read())
                fp.seek(0)
                table = pq.read_table(fp)

            # Generate the schema dynamically
            schema = table.schema
            schema_sql = ", ".join([f"{field.name} {field.type}" for field in schema])

            create_table_sql = f"""
            CREATE TABLE hive.default.{table_name} (
                {schema_sql}
            )
            WITH (
                external_location = 's3a://{MINIO_BUCKET_NAME}/{file_key}',
                format = 'PARQUET'
            );
            """

        # Using TrinoHook to run the SQL
        trino_hook = TrinoHook(trino_conn_id='trino_conn', schema='default')
        trino_hook.run(sql=create_table_sql)

    process_new_file = PythonOperator(
        task_id='process_new_file',
        python_callable=create_table_and_update_superset,
        provide_context=True,
        dag=dag,
    )



 # Task dependencies
    new_files = list_new_zip_files()
    check_result = check_files(new_files)
    start() >> new_files >> check_result

    check_result >> create_transfer_tasks(new_files) >> unzip_and_transform() >> sense_minio >> process_new_file  >> end()
    check_result >> stop_pipeline() >> end()

 