from __future__ import annotations

from datetime import datetime

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG


with DAG(
    dag_id="orion_evaluation_replay",
    description=(
        "Replays approved Orion evaluation inputs against the current candidate. "
        "Migration reference FLAG{f5dc183d7d4134ed}."
    ),
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["orion", "evaluation"],
) as dag:
    EmptyOperator(task_id="load_approved_inputs") >> EmptyOperator(task_id="compare_candidate")
