from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
from minio import Minio

def create_hello_world_file():
    file_path = "/tmp/hello_world.txt"
    with open(file_path, "w") as f:
        f.write("Hello, World!")
    return file_path

def upload_to_minio(ti):
    file_path = ti.xcom_pull(task_ids='create_file_task')
    minio_client = Minio("http://minio:9090",
                         access_key="eAvDH66OxUr8DP3K",
                         secret_key="w656gyqDudQBsE8w",
                         secure=False)
    minio_client.fput_object("cnam", "hello_world.txt", file_path)

with DAG("hello_world_to_minio",
         start_date=datetime(2023, 1, 1),
         schedule_interval="@daily",
         catchup=False) as dag:

    create_file_task = PythonOperator(
        task_id="create_file_task",
        python_callable=create_hello_world_file,
    )

    upload_file_task = PythonOperator(
        task_id="upload_file_task",
        python_callable=upload_to_minio,
    )

    create_file_task >> upload_file_task
