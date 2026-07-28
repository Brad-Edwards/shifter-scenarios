"""Native Airflow DAG used only for ordinary company workflow records."""

from __future__ import annotations

from datetime import datetime, timezone

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator


def finish_company_run(**context) -> None:
    run = context["dag_run"]
    if run.conf.get("experiment", {}).get("status") == "abandoned":
        raise AirflowFailException("represented company workflow was abandoned")


with DAG(
    dag_id="company_state_orion_release",
    start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=["company-state", "keplerops-company-state"],
) as dag:
    PythonOperator(
        task_id="record_terminal_state",
        python_callable=finish_company_run,
    )
