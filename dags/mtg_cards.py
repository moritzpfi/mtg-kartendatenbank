"""One daily DAG; every task processes the same immutable run identifier."""

from datetime import datetime, timedelta, timezone
import hashlib

from airflow import DAG
from airflow.operators.python import PythonOperator


def execute_step(step, **context):
    from scripts.fetch_cards import fetch
    from scripts.process_cards import process

    dag_run = context["dag_run"]
    run_id = "airflow_" + hashlib.sha256(dag_run.run_id.encode()).hexdigest()[:24]
    configuration = dag_run.conf or {}
    max_pages = int(configuration.get("max_pages", 0))
    if max_pages < 0:
        raise ValueError("max_pages cannot be negative")
    test_database = max_pages > 0 or configuration.get("test_database") is True
    if step == "fetch":
        fetch(run_id, max_pages=max_pages)
    else:
        process(step, run_id, test_database=test_database)


with DAG(
    "mtg_cards", description="MTG API → HDFS raw → PySpark final → MySQL",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc), schedule="0 5 * * *",
    catchup=False, max_active_runs=1,
    default_args={"owner": "mtg", "retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["mtg", "practical-exam"],
) as dag:
    previous = None
    for task_id, step in (
        ("fetch_to_hdfs_raw", "fetch"), ("transform_to_hdfs_final", "transform"),
        ("validate_final", "validate-final"), ("load_database", "load"),
        ("validate_database", "validate-database"),
    ):
        task = PythonOperator(task_id=task_id, python_callable=execute_step, op_kwargs={"step": step})
        if previous is not None:
            previous >> task
        previous = task
