from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

def test_minio_connection(bucket_name: str, **kwargs):
    """
    Tests connectivity to a specific bucket in Minio using the S3Hook.
    Prints the keys found in the bucket to the logs.

    :param bucket_name: Name of the bucket to list keys from.
    """
    # Initialize the S3Hook with your Minio connection ID
    hook = S3Hook(aws_conn_id='minio_conn')

    # List keys in the specified bucket
    keys = hook.list_keys(bucket_name)
    
    # If the bucket is empty or does not exist, keys will be None
    if keys is None:
        print(f"No keys found or bucket '{bucket_name}' does not exist.")
        return
    
    # Print found keys
    for key in keys:
        print(f"Found key: {key}")

# Define your DAG
with DAG(
    'test_minio_connectivity',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': 1,
        'retry_delay': datetime.timedelta(minutes=5),
    },
    description='A simple DAG to test Minio connectivity',
    schedule_interval=None,
    start_date=datetime(2023, 1, 1),
    catchup=False,
) as dag:

    # Define the PythonOperator to test Minio connection
    test_minio = PythonOperator(
        task_id='test_minio_connection',
        python_callable=test_minio_connection,
        op_kwargs={'bucket_name': 'your_specific_bucket_name'},  # Replace with your bucket name
    )

# Setting dependencies (In this simple DAG, we only have one task, so no need for setting dependencies explicitly)
