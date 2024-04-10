from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import logging

# Il est préférable de configurer les logs au niveau global, pas à l'intérieur d'une fonction
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_to_minio():
    from minio import Minio
    from minio.error import S3Error

    try:
        client = Minio("http://127.0.0.1:9090/",
                       access_key="Rd6YQYQOzOB2f0T2",
                       secret_key="yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6",
                       secure=False)

        bucket_name = "cnam2"

        # Utilisation de logger au lieu de print pour une intégration plus cohérente avec les logs d'Airflow
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Bucket {bucket_name} created successfully.")
        else:
            logger.info(f"Bucket {bucket_name} already exists.")
    except S3Error as e:
        logger.error(f"Encountered an error with MinIO S3: {e}")
    except Exception as e:
        logger.error(f"Encountered a general exception: {e}")

# Il est recommandé d'ajouter un peu de délai au start_date pour éviter les confusions de timezone avec Airflow
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['your_email@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG('upload_file_to_minio',
          default_args=default_args,
          description='Upload file to MinIO',
          schedule_interval='0 12 * * *',
          start_date=datetime(2024, 9, 4) - timedelta(days=1),
          catchup=False)

upload_task = PythonOperator(task_id='upload_to_minio',
                             python_callable=upload_to_minio,
                             dag=dag)
