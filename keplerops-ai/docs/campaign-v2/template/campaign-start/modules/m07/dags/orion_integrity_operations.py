from __future__ import annotations

import sys
from datetime import datetime

from airflow.sdk import dag, get_current_context, task

sys.path.insert(0, "/opt/airflow/orion-integrity")

from integrity import (  # noqa: E402
    audit_model,
    evaluate_holdout,
    mirror_upstream,
    publish_attestation,
    train_model,
    validate_graph,
    version_labels,
)


DEFAULTS = {
    "schedule": None,
    "start_date": datetime(2026, 1, 1),
    "catchup": False,
    "is_paused_upon_creation": False,
    "max_active_runs": 1,
}


@dag(
    dag_id="orion_label_export",
    description="Version reviewed Orion release-risk annotations through DVC and lakeFS.",
    tags=["orion", "release-risk", "label-studio", "dvc", "lineage"],
    **DEFAULTS,
)
def label_export_dag():
    @task
    def export():
        conf = get_current_context()["dag_run"].conf or {}
        return version_labels(conf.get("attempt_id"))

    export()


@dag(
    dag_id="orion_integrity_training",
    description="Train an Orion release-risk candidate from an immutable reviewed data revision.",
    tags=["orion", "release-risk", "training", "mlflow"],
    **DEFAULTS,
)
def model_training_dag():
    @task
    def train():
        conf = get_current_context()["dag_run"].conf or {}
        return train_model(conf.get("lakefs_commit"), conf.get("attempt_id"))

    train()


@dag(
    dag_id="orion_integrity_review",
    description="Measure targeted behavior, near-trigger controls, and clean utility for an exact model run.",
    tags=["orion", "release-risk", "evaluation", "mlflow"],
    **DEFAULTS,
)
def model_audit_dag():
    @task
    def audit():
        conf = get_current_context()["dag_run"].conf or {}
        return audit_model(conf.get("mlflow_run_id"), conf.get("objective_ref"), conf.get("attempt_id"))

    audit()


@dag(
    dag_id="orion_upstream_sync",
    description="Mirror a signed trusted-upstream dataset release into immutable KeplerOps data storage.",
    tags=["orion", "dataset", "mirror", "forgejo", "lakefs"],
    **DEFAULTS,
)
def upstream_sync_dag():
    @task
    def sync():
        conf = get_current_context()["dag_run"].conf or {}
        return mirror_upstream(conf.get("release_tag"), conf.get("attempt_id"))

    sync()


@dag(
    dag_id="orion_holdout_evaluation",
    description="Run release evaluation from the versioned holdout branch and exact candidate.",
    tags=["orion", "release-risk", "holdout", "evaluation"],
    **DEFAULTS,
)
def holdout_evaluation_dag():
    @task
    def evaluate():
        conf = get_current_context()["dag_run"].conf or {}
        return evaluate_holdout(conf.get("mlflow_run_id"), conf.get("git_ref", "main"), conf.get("attempt_id"))

    evaluate()


@dag(
    dag_id="orion_graph_review",
    description="Build and test the submitted Orion computation graph branch.",
    tags=["orion", "release-risk", "graph", "onnx", "forgejo"],
    **DEFAULTS,
)
def graph_build_dag():
    @task
    def build():
        conf = get_current_context()["dag_run"].conf or {}
        return validate_graph(conf.get("git_ref"), conf.get("base_mlflow_run_id"), conf.get("attempt_id"))

    build()


@dag(
    dag_id="orion_dataset_attestation",
    description="Verify and attest an immutable Orion-compatible dataset publication.",
    tags=["orion", "dataset", "harbor", "attestation"],
    **DEFAULTS,
)
def dataset_attestation_dag():
    @task
    def attest():
        conf = get_current_context()["dag_run"].conf or {}
        return publish_attestation(conf.get("artifact_reference"), conf.get("attempt_id"))

    attest()


label_export_dag()
model_training_dag()
model_audit_dag()
upstream_sync_dag()
holdout_evaluation_dag()
graph_build_dag()
dataset_attestation_dag()
