from __future__ import annotations

from datetime import datetime

from airflow.sdk import dag, task


@dag(
    dag_id="engineering_inventory",
    description="Record the current engineering service inventory.",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["engineering", "inventory"],
)
def engineering_inventory():
    @task
    def inventory() -> dict[str, str]:
        return {
            "artifact_store": "minio",
            "dataset_versioning": "lakefs-dvc",
            "experiment_registry": "mlflow",
            "vector_store": "qdrant",
        }

    inventory()


engineering_inventory()
