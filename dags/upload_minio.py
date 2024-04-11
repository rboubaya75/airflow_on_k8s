from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
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
    # Vérification et création du seau si nécessaire
    exists = client.bucket_exists(bucket_name)
    if not exists:
        client.make_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' created.")
    else:
        print(f"Bucket '{bucket_name}' already exists.")

with DAG('minio_bucket', start_date=datetime(2024, 4, 11),
         schedule_interval='@once', catchup=False) as dag:  # Correction de 'schedule' à 'schedule_interval'

    connect_to_minio_task = PythonOperator(
        task_id='connect_to_minio',
        python_callable=connect_to_minio(),
    )
    
    create_bucket_task = PythonOperator(
        task_id='create_minio_bucket',
        python_callable=create_bucket_if_not_exists(),
      )

connect_to_minio_task >> create_bucket_task  
