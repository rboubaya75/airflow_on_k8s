from airflow import DAG
from airflow.providers.ssh.operators.ssh import SSHOperator
from airflow.contrib.operators.sftp_operator import SFTPOperator
from airflow.hooks.S3_hook import S3Hook
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from datetime import datetime, timedelta
import os

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def upload_to_minio(**kwargs):
    s3_hook = S3Hook(aws_conn_id='minio_conn')
    local_path = kwargs['local_path']
    s3_bucket = kwargs['s3_bucket']

    for root, _, files in os.walk(local_path):
        for file in files:
            file_path = os.path.join(root, file)
            s3_key = file  # Use the filename as the key in the S3 bucket
            s3_hook.load_file(
                filename=file_path,
                key=s3_key,
                bucket_name=s3_bucket,
                replace=True
            )

with DAG(
    'sftp_to_minio_all_files',
    default_args=default_args,
    description='Transfer all CSV files from SFTP to Minio',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2023, 5, 14),
    catchup=False,
) as dag:

    start_task = DummyOperator(task_id='start')

    create_local_dir = BashOperator(
        task_id='create_local_dir',
        bash_command='mkdir -p /mnt/data/airflow/uploads/',
        do_xcom_push=False
    )

    download_files = SFTPOperator(
        task_id='download_files',
        ssh_conn_id='sftp_conn_id',
        local_filepath='/mnt/data/airflow/uploads/',
        remote_filepath='/home/sftpuser/uploads/*.csv',
        operation='get',
        create_intermediate_dirs=True
    )

    upload_files = PythonOperator(
        task_id='upload_files_to_minio',
        python_callable=upload_to_minio,
        op_kwargs={
            'local_path': '/mnt/data/airflow/uploads/',
            's3_bucket': 'landing'
        }
    )

    end_task = DummyOperator(task_id='end')

    start_task >> create_local_dir >> download_files >> upload_files >> end_task
