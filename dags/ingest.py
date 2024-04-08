from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

def test_minio_connection(bucket_name: str, **kwargs):
    hook = S3Hook(aws_conn_id='minio_conn')
    keys = hook.list_keys(bucket_name)
    if keys is None:
        print(f"No keys found or bucket '{bucket_name}' does not exist.")
        return
    for key in keys:
        print(f"Found key: {key}")

with DAG(
    'test_minio_connectivity',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='A simple DAG to test Minio connectivity',
    schedule_interval=None,
    start_date=datetime(2023, 1, 1),
    catchup=False,
) as dag:

    test_minio = PythonOperator(
        task_id='test_minio_connection',
        python_callable=test_minio_connection,
        op_kwargs={'bucket_name': 'cnam'},  # Replace with your bucket name
    )
