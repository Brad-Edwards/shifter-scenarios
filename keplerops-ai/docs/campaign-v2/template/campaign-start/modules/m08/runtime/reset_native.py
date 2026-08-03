from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import requests

import research


def protected_native_state(operation: str) -> dict[str, set[tuple[str, ...]]]:
    protected: dict[str, set[tuple[str, ...]]] = {
        "s3": set(),
        "lakefs-branch": set(),
        "mlflow-run": set(),
        "mlflow-model-version": set(),
        "label-studio-prediction": set(),
        "label-studio-task": set(),
    }
    path = research.STATE / "accepted" / f"{operation}.json"
    if not path.is_file():
        return protected
    accepted = research.accepted_record(operation)

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            system = value.get("system")
            bucket = value.get("bucket")
            key = value.get("key")
            if system and bucket and key:
                protected["s3"].add((str(system), str(bucket), str(key)))
            if value.get("report_key"):
                protected["s3"].add(("cinder-minio", "artifacts", str(value["report_key"])))
            if value.get("attestation_key"):
                protected["s3"].add(("cinder-minio", "artifacts", str(value["attestation_key"])))
            if value.get("lakefs_branch"):
                protected["lakefs-branch"].add(("orion", str(value["lakefs_branch"])))
            if value.get("mlflow_run_id"):
                protected["mlflow-run"].add((str(value["mlflow_run_id"]),))
            if value.get("registered_model_name") and value.get("registered_model_version"):
                protected["mlflow-model-version"].add(
                    (str(value["registered_model_name"]), str(value["registered_model_version"]))
                )
            if value.get("prediction_id"):
                protected["label-studio-prediction"].add((str(value["prediction_id"]),))
            if value.get("task_id"):
                protected["label-studio-task"].add((str(value["task_id"]),))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(accepted)
    native = accepted.get("native_record") or {}
    if native.get("system") and native.get("bucket") and native.get("key"):
        protected["s3"].add(
            (str(native["system"]), str(native["bucket"]), str(native["key"]))
        )
    return protected


def remove_queue_job(root: Path, job_id: str, directories: tuple[str, ...]) -> None:
    for directory in directories:
        location = root / directory
        shutil.rmtree(location / job_id, ignore_errors=True)
        for path in location.glob(f"{job_id}.*"):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)


def remove_resource(resource: dict[str, Any], protected: dict[str, set[tuple[str, ...]]]) -> None:
    kind = str(resource.get("kind", ""))
    if kind == "s3":
        identity = (
            str(resource.get("system")), str(resource.get("bucket")), str(resource.get("key"))
        )
        if identity in protected[kind]:
            return
        clients = {
            "kepler-minio": research.minio,
            "cinder-minio": research.cinder_minio,
        }
        factory = clients.get(identity[0])
        if factory is None:
            raise ValueError(f"unknown object-store owner: {identity[0]}")
        factory().delete_object(Bucket=identity[1], Key=identity[2])
    elif kind == "lakefs-branch":
        identity = (str(resource.get("repository")), str(resource.get("branch")))
        if identity in protected[kind]:
            return
        client = research.lakefs_s3()
        objects: list[dict[str, str]] = []
        for page in client.get_paginator("list_objects_v2").paginate(
            Bucket=identity[0], Prefix=f"{identity[1]}/"
        ):
            objects.extend({"Key": str(item["Key"])} for item in page.get("Contents", []))
        for offset in range(0, len(objects), 1000):
            client.delete_objects(
                Bucket=identity[0],
                Delete={"Objects": objects[offset:offset + 1000], "Quiet": True},
            )
        response = requests.delete(
            f"{research.LAKEFS_URL}/api/v1/repositories/{identity[0]}/branches/{identity[1]}",
            auth=(research.LAKEFS_ACCESS, research.LAKEFS_SECRET), timeout=30,
        )
        if response.status_code not in (204, 404):
            response.raise_for_status()
    elif kind == "mlflow-model-version":
        identity = (str(resource.get("name")), str(resource.get("version")))
        if identity not in protected[kind]:
            research.mlflow_client()[1].delete_model_version(*identity)
    elif kind == "mlflow-run":
        identity = (str(resource.get("run_id")),)
        if identity not in protected[kind]:
            artifact_uri = str(resource.get("artifact_uri", ""))
            if artifact_uri.startswith("s3://"):
                bucket, _, prefix = artifact_uri.removeprefix("s3://").partition("/")
                client = research.minio()
                objects: list[dict[str, str]] = []
                for page in client.get_paginator("list_objects_v2").paginate(
                    Bucket=bucket, Prefix=prefix.rstrip("/") + "/"
                ):
                    objects.extend(
                        {"Key": str(item["Key"])} for item in page.get("Contents", [])
                    )
                for offset in range(0, len(objects), 1000):
                    client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": objects[offset:offset + 1000], "Quiet": True},
                    )
            research.mlflow_client()[1].delete_run(identity[0])
    elif kind == "training-job":
        remove_queue_job(
            research.STATE / "training", str(resource.get("job_id")),
            ("inputs", "outputs", "inbox", "accepted", "rejected"),
        )
    elif kind == "offline-job":
        remove_queue_job(
            research.STATE / "offline", str(resource.get("job_id")),
            ("packages", "inbox", "reports", "accepted", "rejected"),
        )
    elif kind == "label-studio-prediction":
        identity = (str(resource.get("prediction_id")),)
        if identity in protected[kind]:
            return
        response = requests.delete(
            f"{research.LABEL_URL}/api/predictions/{identity[0]}",
            headers={"Authorization": f"Token {research.LABEL_TOKEN}"}, timeout=30,
        )
        if response.status_code not in (204, 404):
            response.raise_for_status()
    elif kind == "label-studio-task":
        identity = (str(resource.get("task_id")),)
        if identity in protected[kind]:
            return
        response = requests.delete(
            f"{research.LABEL_URL}/api/tasks/{identity[0]}",
            headers={"Authorization": f"Token {research.LABEL_TOKEN}"}, timeout=30,
        )
        if response.status_code not in (204, 404):
            response.raise_for_status()
    elif kind == "teacher-query-reservation":
        reservation = (
            research.STATE / "server" / "teacher-query-reservations"
            / f"{resource.get('reservation_id')}.json"
        )
        reservation.unlink(missing_ok=True)
    else:
        raise ValueError(f"unknown attempt resource kind: {kind}")


def reset_failed(operation: str) -> int:
    research.recover_crashed_attempts(operation)
    attempts = research.STATE / "attempts" / operation
    protected = protected_native_state(operation)
    reset_count = 0
    for path in sorted(attempts.glob("*.json")):
        attempt = json.loads(path.read_text())
        if attempt.get("status") not in {"failed", "crashed", "staged"} or attempt.get("reset_status") == "complete":
            continue
        errors: list[str] = []
        for resource in reversed(attempt.get("resources") or []):
            try:
                remove_resource(resource, protected)
            except Exception as error:  # preserve a complete operator audit trail
                errors.append(f"{resource.get('kind')}: {error}")
        attempt["reset_at"] = research.now()
        attempt["reset_status"] = "partial" if errors else "complete"
        if errors:
            attempt["reset_errors"] = errors
        path.write_bytes(research.canonical(attempt))
        if errors:
            raise RuntimeError("; ".join(errors))
        reset_count += 1
    return reset_count


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: reset_native.py <kep-m08-operation>")
    count = reset_failed(sys.argv[1])
    print(f"{sys.argv[1]}: cleaned {count} failed native attempt(s); accepted state preserved")
