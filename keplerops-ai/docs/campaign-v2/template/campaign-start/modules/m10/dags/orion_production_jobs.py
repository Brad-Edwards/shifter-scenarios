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
    "orion_artifact_pod_execution": "artifact-pod-execution",
    "orion_model_support_export": "model-support-export",
    "orion_feature_impact_audit": "feature-impact-audit",
    "orion_cinder_replication": "cinder-replication",
    "cinder_offline_execution": "cinder-offline-execution",
    "orion_canary_availability_audit": "canary-availability-audit",
    "orion_compute_chargeback": "compute-chargeback",
    "orion_research_fanout_audit": "research-fanout-audit",
    "orion_feedback_quality_audit": "feedback-quality-audit",
    "orion_credit_impact_audit": "credit-impact-audit",
    "orion_publication_impact_audit": "publication-impact-audit",
    "orion_advisory_impact_audit": "advisory-impact-audit",
    "orion_support_impact_audit": "support-impact-audit",
    "orion_feedback_validation": "feedback-validation",
    "orion_retention_impact_audit": "retention-impact-audit",
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
