def upload_to_minio():
    try:
        client = Minio("https://20.19.131.164:443",
                       access_key="Rd6YQYQOzOB2f0T2",
                       secret_key="yyEKqqUdMAVURAoEk7jKqxKEd42RoOq6",
                       secure=False)

        bucket_name = "cnam2"

        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"Bucket {bucket_name} created successfully.")
        else:
            print(f"Bucket {bucket_name} already exists.")
    except S3Error as e:
        print(f"Encountered an error with MinIO S3: {e}")
    except Exception as e:
        print(f"Encountered a general exception: {e}")
