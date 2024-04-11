from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from minio import Minio
import urllib3

def setup_minio_and_create_bucket(bucket_name):
    # Configuration du client Minio (avec vérification SSL désactivée pour le test)
    urllib3.disable_warnings()
    #http_client = urllib3.PoolManager(cert_reqs='CERT_NONE', assert_hostname=False)
    client = Minio(
         "10.224.2.34:9000",
        access_key="Rd6YQYQOzOB2f0T2",
        secret_key="yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6",
        secure=false,
       # http_client=http_client
    )
    
    # Vérification et création du seau si nécessaire
    exists = client.bucket_exists(bucket_name)
    if not exists:
        client.make_bucket(bucket_name)
        return f"Bucket '{bucket_name}' created."
    else:
        return f"Bucket '{bucket_name}' already exists."

with DAG('minio_bucket', start_date=datetime(2024, 4, 11), schedule_interval='@once', catchup=False) as dag:
    create_minio_bucket_task = PythonOperator(
        task_id='create_minio_bucket',
        python_callable=setup_minio_and_create_bucket,
        op_kwargs={'bucket_name': 'cnam4'},
    )
