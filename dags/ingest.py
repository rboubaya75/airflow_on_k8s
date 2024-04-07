from airflow import DAG
from airflow.providers.amazon.aws.transfers.local_to_s3 import LocalFilesystemToS3Operator
from datetime import datetime

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 4, 4),
    'retries': 1,
}

with DAG(
    'csv_to_minio',
    default_args=default_args,
    schedule_interval=None,  # Set your desired schedule here
    catchup=False,
) as dag:

    upload_to_minio = LocalFilesystemToS3Operator(
        task_id='upload_to_minio',
        filename='C:/Users/RachidBOUBAYA/Airflow-Tuto/image',  # Modified to avoid backslash issues
        bucket_name='cnam',
        aws_conn_id='minio_connection',  # Ensure this connection ID is correctly set up in Airflow
        s3_key='kbRU29BGMlSc7a6z0m7g',  # `s3_key` is the correct parameter name, not `key`
    )

# No need to call upload_to_minio() since defining tasks within the DAG context makes them executable by Airflow
