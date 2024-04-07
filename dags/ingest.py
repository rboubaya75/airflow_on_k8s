import datetime

from airflow import models

default_dag_args = {
    # The start_date describes when a DAG is valid / can be run. Set this to a
    # fixed point in time rather than dynamically, since it is evaluated every
    # time a DAG is parsed. See:
    # https://airflow.apache.org/faq.html#what-s-the-deal-with-start-date
    "start_date": datetime.datetime(2024, 4, 7),
}

# Define a DAG (directed acyclic graph) of tasks.
# Any task you create within the context manager is automatically added to the
# DAG object.
with models.DAG(
    "composer_sample_simple_greeting",
    schedule_interval=datetime.timedelta(days=1),
    default_args=default_dag_args,
) as dag:
