FROM apache/airflow:slim-2.9.1-python3.9

USER root
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    nano \
    sudo \
    vim \
    iputils-ping \
    net-tools \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV SLUGIFY_USES_TEXT_UNIDECODE=yes

COPY requirements.txt .
#COPY pod_template.yaml /opt/airflow/pod_template.yaml
COPY entrypoint.sh /entrypoint.sh
COPY id_rsa_airflow /opt/airflow/.ssh/id_rsa_airflow

RUN chmod +x /entrypoint.sh

# Add the airflow user to sudoers
RUN echo "airflow ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN chmod 400 /opt/airflow/.ssh/id_rsa_airflow
RUN chown -R 1001:1001 /opt/airflow/.ssh/id_rsa_airflow
RUN chown airflow /opt/airflow/.ssh/id_rsa_airflow
RUN touch /opt/airflow/dags/tracked_files.txt && \
    chmod 664 /opt/airflow/dags/tracked_files.txt && \
    chown airflow:root /opt/airflow/dags/tracked_files.txt

USER airflow
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install psycopg2-binary statsd
RUN pip install apache-airflow-providers-cncf-kubernetes
RUN pip install apache-airflow-providers-apache-hive
ENTRYPOINT ["/entrypoint.sh"]
