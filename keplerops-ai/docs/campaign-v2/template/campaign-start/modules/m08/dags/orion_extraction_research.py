from __future__ import annotations

import sys
from datetime import datetime

from airflow.sdk import dag, get_current_context, task

sys.path.insert(0, "/opt/airflow/campaign-m08")

from research import run  # noqa: E402


DEFAULTS = {
    "schedule": None,
    "start_date": datetime(2026, 1, 1),
    "catchup": False,
    "is_paused_upon_creation": False,
    "max_active_runs": 4,
}


def workflow(dag_id: str, description: str, function: str, tags: list[str]):
    @dag(dag_id=dag_id, description=description, tags=tags, **DEFAULTS)
    def generated():
        @task
        def execute():
            conf = dict(get_current_context()["dag_run"].conf or {})
            return run(function, conf)

        execute()

    return generated()


workflow(
    "orion_scoped_worker_prediction",
    "Request teacher predictions through the bounded Orion training-contributor identity.",
    "worker_predictions", ["orion", "training-contributor", "teacher", "lineage"],
)
workflow(
    "orion_teacher_corpus_capture",
    "Query the live Orion release-risk teacher and preserve a versioned research corpus.",
    "build_teacher_corpus", ["orion", "distillation", "teacher", "lineage"],
)
workflow(
    "orion_distillation_corpus_review",
    "Profile, split, and version a teacher-query corpus through DVC and lakeFS.",
    "version_balanced_corpus", ["orion", "distillation", "dvc", "lakefs"],
)
workflow(
    "orion_student_training_first",
    "Train and register a first Release Risk student from the submitted teacher corpus.",
    "train_first_student", ["orion", "distillation", "training", "mlflow"],
)
workflow(
    "orion_student_training_revision",
    "Retrain the Release Risk student after active teacher-query selection.",
    "train_second_student", ["orion", "distillation", "active-learning", "mlflow"],
)
workflow(
    "orion_student_hidden_compatibility",
    "Evaluate an immutable student package against disjoint server-held compatibility cases.",
    "hidden_fidelity", ["orion", "distillation", "hidden-evaluation"],
)
workflow(
    "cinder_offline_student_submission",
    "Submit an accepted student package to Cinder's networkless execution queue.",
    "queue_offline_student", ["cinder", "offline", "model-execution"],
)
workflow(
    "cinder_artifact_proxy_training",
    "Train and evaluate a Release Risk proxy from gathered architecture, configuration, and human-label artifacts.",
    "train_artifact_proxy", ["cinder", "artifact-collection", "training", "mlflow"],
)
workflow(
    "orion_vision_privacy_audit",
    "Audit a reconstructed protected prototype against the live model and calibrated perceptual thresholds.",
    "vision_audit", ["orion", "vision", "privacy", "inversion"],
)
workflow(
    "orion_protected_package_validation",
    "Validate a complete protected Orion package through a networkless fresh-load job.",
    "queue_protected_package", ["orion", "model-package", "offline", "validation"],
)
workflow(
    "orion_review_prediction",
    "Produce a live Orion prediction for a fresh Label Studio review task.",
    "review_prediction", ["orion", "label-studio", "prediction-review"],
)
