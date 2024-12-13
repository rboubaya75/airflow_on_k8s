from airflow import DAG
from airflow.providers.trino.operators.trino import TrinoOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import logging

# Define the default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Set up logging
logger = logging.getLogger(__name__)

def log_trino_response(response):
    logger.info(f"Trino response: {response}")

# Define the DAG
dag = DAG(
    'create_hive_table_in_trino',
    default_args=default_args,
    description='Create Hive table in Trino from Parquet file in Minio',
    schedule_interval=timedelta(days=1),
    start_date=days_ago(1),
)

# Define the SQL command to create the table
create_table_sql = """
CREATE TABLE hive.default.prescription (
    enveloppe_uuid VARCHAR,
    date_creation VARCHAR,
    version VARCHAR,
    nom_cible VARCHAR,
    nom_source VARCHAR,
    nature VARCHAR,
    rejeter BOOLEAN,
    format VARCHAR,
    type VARCHAR,
    date_creation_format VARCHAR
)
WITH (
    external_location = 's3a://staging/parquets/schema_80e0201ff99f6bffe4ffdff3519098ba',
    format = 'PARQUET'
)
"""

# Define the TrinoOperator to run the SQL command
create_table = TrinoOperator(
    task_id='create_table_in_trino',
    trino_conn_id='trino_conn',  # Make sure this connection is defined in Airflow with the DNS name
    sql=create_table_sql,
    dag=dag,
    handler=log_trino_response  # Add this line to handle the response
)

# A simple test task to verify Trino connection
test_trino_connection = TrinoOperator(
    task_id='test_trino_connection',
    trino_conn_id='trino_conn',
    sql='SELECT 1',
    dag=dag,
    handler=log_trino_response  # Add this line to handle the response
)

# Set the task dependencies
test_trino_connection >> create_table
