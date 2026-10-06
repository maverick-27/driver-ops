"""Driver Ops corpus ingestion.

Processes the whole corpus on every run, so the first run is the backfill; later runs only
re-parse files whose content changed. Trigger with {"force_reparse": true} or {"force_reindex": true}
after changing the parser, the chunker or the embedding model.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from driver_ops_ingestion.fetching import fetch_and_parse_documents
from driver_ops_ingestion.indexing import index_documents
from driver_ops_ingestion.reporting import generate_report
from driver_ops_ingestion.setup import setup_environment

default_args = {
    "owner": "driver-ops",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="driver_ops_ingestion",
    description="Parse the regulation and company-policy corpus and index it for hybrid search",
    default_args=default_args,
    schedule="0 6 * * *",  # daily: picks up re-downloaded regulations and edited policies
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["driver-ops", "ingestion"],
) as dag:
    setup = PythonOperator(task_id="setup_environment", python_callable=setup_environment)
    fetch = PythonOperator(
        task_id="fetch_and_parse_documents",
        python_callable=fetch_and_parse_documents,
        execution_timeout=timedelta(minutes=60),
    )
    index = PythonOperator(
        task_id="index_documents", python_callable=index_documents, execution_timeout=timedelta(minutes=60)
    )
    report = PythonOperator(task_id="generate_report", python_callable=generate_report)

    setup >> fetch >> index >> report
