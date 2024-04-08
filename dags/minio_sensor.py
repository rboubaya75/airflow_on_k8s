from airflow import DAG
from airflow.utils.dates import days_ago
# Use the generic S3 sensor if available in your Airflow version
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
}

dag = DAG(
    dag_id='example_s3_sensor',
    default_args=default_args,
    schedule_interval='@daily',
    tags=['example'],
)

# Example usage of the S3KeySensor
task = S3KeySensor(
    task_id='check_s3_for_key',
    bucket_key='s3://cnam/UsersAD.xlsx',
    aws_conn_id='minio_conn',
    timeout=18*60*60,
    poke_interval=120,
    dag=dag,
)
