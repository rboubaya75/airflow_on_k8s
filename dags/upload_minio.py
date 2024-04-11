from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
import boto3
from botocore.client import Config
import urllib3
import os
# Disable SSL certificate verification warning
urllib3.disable_warnings()

def connect_to_minio():
    # Bypass SSL verification - Note: Only use for testing; not recommended for production
    http_client = urllib3.PoolManager(
        cert_reqs='CERT_NONE',
        assert_hostname=False,
    )
    
    # Initialize the Minio client
    client = Minio(
        "20.19.131.164:443",
        access_key="Rd6YQYQOzOB2f0T2",
        secret_key="yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6",
        secure=True,  # True indicates HTTPS
        http_client=http_client
    )
    return client

def create_bucket_if_not_exists(client, bucket_name):
    # Check if the bucket exists, and create it if not
    exists = client.bucket_exists(bucket_name)
    if not exists:
        client.make_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' created.")
    else:
        print(f"Bucket '{bucket_name}' already exists.")



with DAG('minio_bucket_and_upload', start_date=datetime(2021, 1, 1),
         schedule='@once', catchup=False) as dag:  # Updated here
    
    create_bucket_task = PythonOperator(
        task_id='create_minio_bucket',
        python_callable=create_bucket_if_not_exists,
    )

    upload_file_task = PythonOperator(
        task_id='upload_file_to_bucket',
        python_callable=upload_file_to_bucket,
    )

create_bucket_task 
