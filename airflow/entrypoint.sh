#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status.

# Initialize the Airflow database
airflow db migrate

airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

# Add AWS connection
airflow connections add 'minio_conn' \
    --conn-type 'aws' \
    --conn-extra '{"aws_access_key_id": "TLzIBJM3DcfUyUwYuiDm", "aws_secret_access_key": "aNiWKBv6uxBmnaMNDEJX3KX9IWfB9MnVl212m8JW", "endpoint_url": "http://10.98.210.183:9000"}' || echo "Connection minio_conn already exists"
# Add SFTP connection with SSH private key
airflow connections add 'sftp_conn' \
    --conn-type 'sftp' \
    --conn-host '10.0.3.5' \
    --conn-login 'rachid' \
    --conn-port '22' \
    --conn-extra '{"key_file": "/opt/airflow/.ssh/id_rsa_airflow", "no_host_key_check": true}' || echo "Connection sftp_conn already exists"


# Add SSH connection with SSH private key
airflow connections add 'ssh_conn' \
    --conn-type 'ssh' \
    --conn-host '10.0.3.5' \
    --conn-login 'rachid' \
    --conn-port '22' \
    --conn-extra '{"key_file": "/opt/airflow/.ssh/id_rsa_airflow"", "no_host_key_check": true}' || echo "Connection ssh_conn already exists"

# Execute the command passed to the container
exec "$@"
