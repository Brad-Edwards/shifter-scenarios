from __future__ import annotations

from datetime import datetime
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sdk import get_current_context

sys.path.insert(0, "/opt/airflow/config")
from release_operations import execute


OPERATIONS = {
    "orion_visible_release_evaluation": "kep-m09-b",
    "orion_candidate_registration": "kep-m09-a",
    "orion_lineage_resolution": "kep-m09-c",
    "orion_candidate_approval": "kep-m09-d",
    "orion_image_compatibility_decision": "kep-m09-e",
    "orion_release_signing": "kep-m09-f",
    "orion_production_canary_promotion": "kep-m09-g",
    "orion_upstream_release_intake": "kep-m09-h",
    "orion_import_exception_review": "kep-m09-i",
    "orion_upstream_mirror_sync": "kep-m09-j",
    "orion_mirror_review": "kep-m09-k",
    "orion_staging_reconciliation": "kep-m09-l",
}


def run(operation: str):
    context = get_current_context()
    return execute(operation, dict(context["dag_run"].conf or {}))


for dag_id, operation in OPERATIONS.items():
    with DAG(
        dag_id=dag_id,
        description=f"KeplerOps Orion release operation: {dag_id.removeprefix('orion_').replace('_', ' ')}",
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        tags=["orion", "release", "supply-chain"],
    ) as dag:
        PythonOperator(task_id="execute", python_callable=run, op_args=[operation])
    globals()[dag_id] = dag
