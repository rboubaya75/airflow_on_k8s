from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
#from airflow.providers.cncf.kubernetes.sensors.spark_kubernetes import SparkKubernetesSensor
from airflow.utils.dates import days_ago
from datetime import timedelta

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email': ['airflow@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'max_active_runs': 1,
    'retries': 3
}

# Instantiate the DAG
dag = DAG(
    'spark_kubernetes_example',
    start_date=days_ago(1),
    default_args=default_args,
    schedule_interval=timedelta(days=1),
    tags=['example']
)

SparkKubernetesOperator(
    task_id="spark_task",
    image="rboubaya/spark:4.1",  # OR custom image using that
    code_path="local:///app/read_parquet3.py",
    application_file="kube/spark-apps.yaml",  # OR spark_job_template.json
    dag=dag,
)


