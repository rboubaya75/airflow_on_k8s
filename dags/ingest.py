from airflow import DAG
from airflow.operators.python import PythonOperator 
from airflow.providers.amazon.aws.transfers.local_to_s3 import LocalFilesystemToS3Operator
from datetime import datetime

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 4, 4),
    'retries': 1,
}

dag = DAG(
    'csv_to_minio',
    default_args=default_args,
    schedule_interval=None,  # Set your desired schedule here
    catchup=False,
)

def upload_to_minio():
    # Set your Minio connection ID (configured in Airflow)
    minio_conn_id = 'minio_connection'

    # Specify the local file path
    local_csv_path = 'C:\Users\RachidBOUBAYA\Airflow-Tuto\image'

    # Specify the Minio bucket name and object key
    bucket_name = 'cnam'
    object_key = 'kbRU29BGMlSc7a6z0m7g'

    # Upload the local file to Minio
    upload_task = LocalFilesystemToS3Operator(
        task_id='upload_to_minio',
        filename=local_csv_path,
        bucket_name=bucket_name,
        aws_conn_id=minio_conn_id,
        key=object_key,
        dag=dag,
    )

# Call the upload task
upload_to_minio()





