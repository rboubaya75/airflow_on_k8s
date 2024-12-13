from airflow import DAG
from airflow.contrib.operators.sftp_to_s3_operator import SFTPToS3Operator
from airflow.operators.dummy import DummyOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'sftp_to_minio_all_files',
    default_args=default_args,
    description='Transfer all CSV files from SFTP to Minio',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2023, 5, 14),
    catchup=False,
) as dag:

    start_task = DummyOperator(task_id='start')

    transfer_files = SFTPToS3Operator(
        task_id='sftp_to_minio',
        sftp_conn_id='ssh_conn',
        sftp_path='/home/rachid/text.csv',
        s3_conn_id='minio_conn',
        s3_bucket='landing',
        s3_key='text.csv'
    )

    start_task >> transfer_files