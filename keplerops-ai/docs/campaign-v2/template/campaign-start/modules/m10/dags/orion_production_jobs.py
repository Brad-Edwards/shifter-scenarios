from __future__ import annotations

from datetime import datetime
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sdk import get_current_context

sys.path.insert(0, "/opt/airflow/config")
from production_jobs import execute


JOB_DAGS = {
    "orion_production_continuity": "production-continuity",
    "orion_production_integrity_review": "production-integrity-review",
    "orion_model_support_export": "model-support-export",
    "orion_feature_control": "feature-control",
    "orion_cinder_replication": "cinder-replication",
    "cinder_offline_execution": "cinder-offline-execution",
    "orion_canary_availability": "canary-availability",
    "orion_compute_chargeback": "compute-chargeback",
    "orion_research_delegation": "research-delegation",
    "orion_feedback_quality": "feedback-quality",
    "orion_entitlement_adjustment": "entitlement-adjustment",
    "orion_incident_publication": "incident-publication",
    "orion_advisory_delivery": "advisory-delivery",
    "orion_support_triage": "support-triage",
    "orion_feedback_validation": "feedback-validation",
    "orion_tenant_retention": "tenant-retention",
}


def run(job: str):
    context = get_current_context()
    return execute(job, dict(context["dag_run"].conf or {}))


for dag_id, job in JOB_DAGS.items():
    with DAG(
        dag_id=dag_id,
        description=f"KeplerOps {job.replace('-', ' ')} production workflow",
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        tags=["orion", "production"],
    ) as dag:
        PythonOperator(task_id="execute", python_callable=run, op_args=[job])
    globals()[dag_id] = dag
