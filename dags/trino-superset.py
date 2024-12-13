# File: /path/to/airflow/dags/dynamic_create_table_from_parquet_dag.py

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.trino.operators.trino import TrinoOperator
from airflow.utils.dates import days_ago
from airflow.exceptions import AirflowSkipException

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
}

dag = DAG(
    'dynamic_create_table_from_parquet',
    default_args=default_args,
    schedule_interval=None,
)

MINIO_CONN_ID = 'minio_conn'
MINIO_BUCKET_NAME = 'staging'


'''
SUPERSET_URL = "http://your-superset-url"
SUPERSET_USERNAME = "admin"
SUPERSET_PASSWORD = "admin"
DATABASE_ID = 1  # The ID of the database in Superset (replace with your actual database ID)

def add_table_to_superset(table_name):
    auth_payload = {
        "username": SUPERSET_USERNAME,
        "password": SUPERSET_PASSWORD,
        "provider": "db",
        "refresh": True
    }
    session = requests.Session()
    auth_response = session.post(f"{SUPERSET_URL}/api/v1/security/login", json=auth_payload)
    
    if auth_response.status_code != 200:
        raise Exception("Failed to authenticate with Superset")
    
    csrf_token = session.cookies.get('csrf_access_token')
    
    table_payload = {
        "database": DATABASE_ID,
        "schema": "default",
        "table_name": table_name,
        "is_sqllab_view": False,
        "template_params": None,
        "sql": None
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf_token
    }
    
    add_table_response = session.post(f"{SUPERSET_URL}/api/v1/table/", json=table_payload, headers=headers)
    
    if add_table_response.status_code != 201:
        raise Exception(f"Failed to add table to Superset: {add_table_response.text}")
'''
def create_table_and_update_superset(**context):
    file_key = context['task_instance'].xcom_pull(task_ids='sense_minio')
    if not file_key:
        raise AirflowSkipException("No new Parquet files found in Minio bucket.")

    file_name = file_key.split('/')[-1]
    table_name = file_name.replace('.parquet', '')
    
    create_table_sql = f"""
    CREATE TABLE hive.default.{table_name} (
        id INT,
        name STRING
    )
    WITH (
        external_location = 's3a://{MINIO_BUCKET_NAME}/{file_key}',
        format = 'PARQUET'
    );
    """
    
    # Create and execute a new Trino task dynamically
    trino_task = TrinoOperator(
        task_id=f'create_table_{table_name}',
        sql=create_table_sql,
        trino_conn_id='trino_conn',
        dag=dag,
    )
    trino_task.execute(context)

    # Add the new table to Superset
    #add_table_to_superset(table_name)

sense_minio = S3KeySensor(
    task_id='sense_minio',
    bucket_key='parquets/*.parquet',
    wildcard_match=True,
    bucket_name=MINIO_BUCKET_NAME,
    aws_conn_id=MINIO_CONN_ID,
    timeout=18*60*60,
    poke_interval=60,
    dag=dag,
)

process_new_file = PythonOperator(
    task_id='process_new_file',
    python_callable=create_table_and_update_superset,
    provide_context=True,
    dag=dag,
)

sense_minio >> process_new_file
