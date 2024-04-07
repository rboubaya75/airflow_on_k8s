from airflow import DAG
from datetime import datetime

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 4, 4),
    'retries': 1,
}



# No need to call upload_to_minio() since defining tasks within the DAG context makes them executable by Airflow
