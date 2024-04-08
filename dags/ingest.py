from airflow.providers.amazon.aws.hooks.s3 import S3Hook

def test_minio_connection(bucket_name: str):
    hook = S3Hook(aws_conn_id='your_minio_conn')
    keys = hook.list_keys(bucket_name)
    for key in keys:
        print(f"Found key: {key}")
