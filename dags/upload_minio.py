from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime
from minio import Minio
from minio.error import S3Error

def upload_to_minio():
    client = Minio("https://20.19.131.164:443",
                   access_key="Rd6YQYQOzOB2f0T2",
                   secret_key="yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6",
                   secure=False)

    # Le chemin vers le fichier dans le stockage temporaire
    #source_file_path = "/path/to/the/source/file"
    
    # Nom du bucket et chemin de destination dans MinIO
    bucket_name = "cnam2"
   # destination_file_path = "destination/path/in/bucket"

    # Assurez-vous que le bucket existe
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

    # Téléversement du fichier
   # client.fput_object(bucket_name, destination_file_path, source_file_path)

   # print(f"File {source_file_path} uploaded to {bucket_name}/{destination_file_path}")

# Définition du DAG
dag = DAG('upload_file_to_minio', description='Upload file to MinIO',
          schedule_interval='0 12 * * *',
          start_date=datetime(2024, 9, 4), catchup=False)

upload_task = PythonOperator(task_id='upload_to_minio',
                             python_callable=upload_to_minio,
                             dag=dag)
