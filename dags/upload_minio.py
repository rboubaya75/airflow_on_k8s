from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import boto3
from botocore.client import Config

def create_minio_bucket():
    s3_client = boto3.client(
        service_name='s3',
        endpoint_url='https://20.19.131.164:443',
        aws_access_key_id="Rd6YQYQOzOB2f0T2",
        aws_secret_access_key='yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6',
        config=Config(signature_version='s3v4'),
        verify=False  # This disables SSL certificate verification
    )

    bucket_name = 'my-test-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    print(f"Bucket '{bucket_name}' created")

def upload_file_to_bucket():
    s3_client = boto3.client(
        service_name='s3',
        endpoint_url='https://20.19.131.164:443',
        aws_access_key_id="Rd6YQYQOzOB2f0T2",
        aws_secret_access_key='yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6',
        config=Config(signature_version='s3v4'),
        verify=False
    )
    
    bucket_name = 'my-test-bucket'
    file_name = 'example.csv'
    s3_client.upload_file(file_name, bucket_name, file_name)
    print(f"'{file_name}' uploaded to bucket '{bucket_name}'")

with DAG('minio_bucket_and_upload', start_date=datetime(2021, 1, 1),
         schedule_interval='@once', catchup=False) as dag:
    
    create_bucket_task = PythonOperator(
        task_id='create_minio_bucket',
        python_callable=create_minio_bucket,
    )

    upload_file_task = PythonOperator(
        task_id='upload_file_to_bucket',
        python_callable=upload_file_to_bucket,
    )

create_bucket_task >> upload_file_task
