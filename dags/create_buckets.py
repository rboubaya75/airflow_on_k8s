from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
from minio import Minio
from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook

# Constants for Minio bucket names
LANDING_BUCKET_NAME = "landing"
RAW_BUCKET_NAME = "raw"
STAGING_BUCKET_NAME = "staging"
REFINED_BUCKET_NAME = "refined"

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def get_minio_client():
    """Returns a configured Minio client using the AWS connection."""
    # Get AWS connection details
    hook = AwsBaseHook(aws_conn_id='minio_conn', client_type='s3')
    credentials = hook.get_credentials()

    # Extract endpoint URL from the connection extra
    conn = hook.get_connection('minio_conn')
    endpoint_url = conn.extra_dejson.get('host')

    if not endpoint_url:
        raise ValueError("Minio endpoint URL not found in connection extra")

    # Initialize Minio client
    return Minio(
        endpoint_url,
        access_key=credentials.access_key,
        secret_key=credentials.secret_key,
        secure=False  # Update this if you are using HTTPS
    )

def create_bucket(bucket_name):
    """Create a Minio bucket if it does not exist."""
    client = get_minio_client()
    exists = client.bucket_exists(bucket_name)
    if not exists:
        client.make_bucket(bucket_name)
        return f"Bucket '{bucket_name}' created."
    else:
        return f"Bucket '{bucket_name}' already exists."

with DAG(
    dag_id='minio_storage_pipeline',
    default_args=default_args,
    schedule_interval='@once'
) as dag:

    create_landing_bucket = PythonOperator(
        task_id='create_landing_bucket',
        python_callable=create_bucket,
        op_args=[LANDING_BUCKET_NAME]
    )

    create_raw_bucket = PythonOperator(
        task_id='create_raw_bucket',
        python_callable=create_bucket,
        op_args=[RAW_BUCKET_NAME]
    )
    
    create_staging_bucket = PythonOperator(
        task_id='create_staging_bucket',
        python_callable=create_bucket,
        op_args=[STAGING_BUCKET_NAME]
    )

    create_refined_bucket = PythonOperator(
        task_id='create_refined_bucket',
        python_callable=create_bucket,
        op_args=[REFINED_BUCKET_NAME]
    )

create_landing_bucket >> create_raw_bucket >> create_staging_bucket >> create_refined_bucket
