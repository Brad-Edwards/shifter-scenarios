#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
import requests


LAKEFS = os.getenv("LAKEFS_ENDPOINT", "http://10.61.40.31:8000").rstrip("/")
LAKEFS_ACCESS = os.getenv("LAKEFS_ACCESS_KEY_ID", "KeplerLakeFSAccess")
LAKEFS_SECRET = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "KeplerV2-Training-LakeFS-Object-Key")
MLFLOW = os.getenv("MLFLOW_TRACKING_URI", "http://10.61.40.36:5000").rstrip("/")
MLFLOW_AUTH = tuple(os.getenv(
    "MLFLOW_AUTH", "range-admin:KeplerV2-Training-MLflow-Admin",
).split(":", 1))
MINIO = os.getenv("MINIO_ENDPOINT", "http://10.61.40.50:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "svc-orion-evaluator")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "KeplerV2-Training-Minio-Orion-Evaluator")
HANDOFF_KEY = os.getenv("ORION_INTEGRITY_SIGNING_KEY", "KeplerOps-Integrity-Handoff-2026").encode()
HARBOR = os.getenv("HARBOR_URL", "http://10.61.40.32:8080").rstrip("/")
HARBOR_AUTH = tuple(os.getenv("HARBOR_AUTH", "admin:KeplerV2-Training-Harbor").split(":", 1))
CINDER_FORGEJO = os.getenv("CINDER_FORGEJO_URL", "http://10.61.90.30:3000").rstrip("/")
CINDER_AUTH = tuple(os.getenv(
    "CINDER_FORGEJO_AUTH", "cinder-field-operator:Cinder-Field-Operator-Git-V6n4Qs8p",
).split(":", 1))
CINDER_MINIO = os.getenv("CINDER_OBJECT_ENDPOINT", "http://10.61.90.31:9000")
CINDER_MINIO_ACCESS = os.getenv("CINDER_OBJECT_ACCESS_KEY", "cinder-operator")
CINDER_MINIO_SECRET = os.getenv("CINDER_OBJECT_SECRET_KEY", "Cinder-Operations-ObjectStore-T7v2Lm9q")
CINDER_ATTESTATION_KEY = os.getenv("CINDER_ATTESTATION_KEY", "Cinder-Isolated-Execution-2026").encode()
AIRFLOW = os.getenv("AIRFLOW_URL", "http://10.61.40.35:8080").rstrip("/")
AIRFLOW_USER = os.getenv("AIRFLOW_VALIDATOR_USER", "range-admin")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_VALIDATOR_PASSWORD", "KeplerV2-Training-Airflow")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def declares_release_risk(value: bytes) -> bool:
    return b"release-risk" in value.lower() or b"release risk" in value.lower()


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def failed_airflow_record(operation: str, run_id: str) -> dict[str, Any]:
    dags = {
        "kep-m07-a": "orion_label_export",
        "kep-m07-b": "orion_integrity_training",
        "kep-m07-c": "orion_integrity_review",
        "kep-m07-d": "orion_upstream_sync",
        "kep-m07-e": "orion_integrity_review",
        "kep-m07-f": "orion_holdout_evaluation",
        "kep-m07-g": "orion_graph_review",
        "kep-m07-h": "orion_dataset_attestation",
    }
    dag_id = dags.get(operation)
    if dag_id is None or not run_id or len(run_id) > 250 or any(ord(ch) < 32 for ch in run_id):
        raise ValueError("negative subject must name an exact failed operation DAG run")
    token = checked(requests.post(
        f"{AIRFLOW}/auth/token", json={"username": AIRFLOW_USER, "password": AIRFLOW_PASSWORD}, timeout=30,
    )).json()["access_token"]
    record = checked(requests.get(
        f"{AIRFLOW}/api/v2/dags/{dag_id}/dagRuns/{quote(run_id, safe='')}",
        headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )).json()
    state = str(record.get("state") or "").lower()
    if state not in {"failed", "upstream_failed"}:
        raise ValueError("selected Airflow negative is not a completed failed run")
    return {
        "schema": "keplerops.native-negative/v1", "system": "airflow",
        "operation": operation, "dag_id": dag_id, "run_id": run_id, "state": state,
    }


def failed_cinder_action(run_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("Cinder negative subject must name an exact Actions run ID")
    response = requests.get(
        f"{CINDER_FORGEJO}/api/v1/repos/cinder-operator/orion-model-artifacts/actions/runs/{run_id}",
        auth=CINDER_AUTH, timeout=30,
    )
    if response.status_code == 404:
        tasks = checked(requests.get(
            f"{CINDER_FORGEJO}/api/v1/repos/cinder-operator/orion-model-artifacts/actions/tasks",
            params={"limit": 200}, auth=CINDER_AUTH, timeout=30,
        )).json().get("workflow_runs") or []
        record = next((item for item in tasks if str(item.get("id")) == run_id), {})
        status = str(record.get("status") or "").lower()
        conclusion = str(record.get("conclusion") or status).lower()
        completed = status in {"failure", "cancelled", "timed_out"}
    else:
        record = checked(response).json()
        conclusion = str(record.get("conclusion") or "").lower()
        completed = record.get("status") == "completed"
    if not completed or conclusion not in {"failure", "cancelled", "timed_out"}:
        raise ValueError("selected Cinder negative is not a completed failed Actions run")
    return {
        "schema": "keplerops.native-negative/v1", "system": "cinder-forgejo-actions",
        "operation": "kep-m07-i", "run_id": int(run_id), "state": "failed",
        "conclusion": conclusion, "head_sha": record.get("head_sha"),
    }


def lakefs_record(subject: str) -> dict[str, Any]:
    commit, separator, object_path = subject.partition(":")
    if not separator or not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not object_path.endswith(".json"):
        raise ValueError("lakeFS subject must be <immutable-commit>:<json-object-path>")
    detail = checked(requests.get(
        f"{LAKEFS}/api/v1/repositories/orion/commits/{commit}",
        auth=(LAKEFS_ACCESS, LAKEFS_SECRET), timeout=30,
    )).json()
    if str(detail.get("id") or "") != commit:
        raise ValueError("lakeFS did not resolve the exact requested commit")
    store = boto3.client(
        "s3", endpoint_url=LAKEFS, aws_access_key_id=LAKEFS_ACCESS,
        aws_secret_access_key=LAKEFS_SECRET, region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    body = store.get_object(Bucket="orion", Key=f"{commit}/{object_path}")["Body"].read()
    record = json.loads(body)
    record["_native"] = {
        "system": "lakefs", "repository": "orion", "commit": commit,
        "path": object_path, "sha256": f"sha256:{sha(body)}",
    }
    return record


def mlflow_record(subject: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{32}", subject):
        raise ValueError("MLflow subject must be an exact run ID")
    os.environ.setdefault("MLFLOW_TRACKING_USERNAME", MLFLOW_AUTH[0])
    os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", MLFLOW_AUTH[1])
    import mlflow

    mlflow.set_tracking_uri(MLFLOW)
    client = mlflow.MlflowClient()
    run = client.get_run(subject)
    if run.info.status != "FINISHED":
        raise ValueError("MLflow review run is not finished")
    path = Path(client.download_artifacts(subject, "reports/report.json"))
    body = path.read_bytes()
    record = json.loads(body)
    if record.get("review_run_id") != subject:
        raise ValueError("MLflow artifact does not bind the selected native run")
    handoff = verify_kepler_handoff(record)
    record["_native"] = {
        "system": "mlflow", "run_id": subject, "sha256": f"sha256:{sha(body)}",
        "handoff": handoff,
    }
    return record


def verify_kepler_handoff(report: dict[str, Any]) -> dict[str, Any]:
    pointer = report.get("handoff")
    if not isinstance(pointer, dict) or pointer.get("system") != "kepler-minio":
        raise ValueError("MLflow report lacks its native integrity handoff")
    bucket, key = pointer.get("bucket"), str(pointer.get("key") or "")
    if bucket != "operations" or not re.fullmatch(
        r"release-risk/integrity-handoffs/[a-z-]+/[0-9a-f]{64}\.json", key,
    ):
        raise ValueError("MLflow handoff pointer is outside the fixed operations route")
    store = boto3.client(
        "s3", endpoint_url=MINIO, aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET, region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    body = store.get_object(Bucket=bucket, Key=key)["Body"].read()
    retention = store.get_object_retention(Bucket=bucket, Key=key).get("Retention") or {}
    if (pointer.get("sha256") != f"sha256:{sha(body)}" or retention.get("Mode") != "GOVERNANCE"
            or pointer.get("object_lock_mode") != retention.get("Mode")
            or not retention.get("RetainUntilDate")
            or pointer.get("retain_until") != retention["RetainUntilDate"].isoformat()):
        raise ValueError("MLflow handoff is not the exact object-locked record")
    signed = json.loads(body)
    signature = str(signed.pop("signature", ""))
    if (signed.get("schema") != "keplerops.release-risk.integrity-handoff/v1"
            or signed.get("model_family") != "release-risk"
            or signed.get("signer_identity") != "svc-orion-evaluator"
            or not hmac.compare_digest(signature, hmac.new(HANDOFF_KEY, canonical(signed), hashlib.sha256).hexdigest())):
        raise ValueError("MLflow handoff signature or schema is invalid")
    subject = signed.get("subject")
    routes = {
        "poisoned-training-lineage": "poisoned-weights",
        "targeted-poison-evaluation": "verified-poisoned-weights",
        "participant-backdoor-evaluation": "participant-backdoor",
        "holdout-integrity-evaluation": "holdout-integrity",
        "computation-graph-integrity": "modified-computation-graph",
    }
    expected_route = routes.get(str(report.get("review_kind") or ""))
    report_digest = sha(canonical({name: value for name, value in report.items() if name != "handoff"}))
    if (signed.get("route") != key.split("/")[2] or signed.get("route") != expected_route
            or not isinstance(subject, dict) or subject.get("report_contract_sha256") != report_digest):
        raise ValueError("MLflow handoff route or subject is invalid")
    if expected_route in {"participant-backdoor", "modified-computation-graph"}:
        for field in (
            "trigger", "near_triggers", "trigger_target", "near_trigger_expected",
            "objective_source_commit", "objective_sha256",
        ):
            if subject.get(field) != report.get(field):
                raise ValueError(f"MLflow handoff does not bind report field: {field}")
        if subject.get("source_commit") != subject.get("objective_source_commit"):
            raise ValueError("MLflow handoff source does not select its immutable objective commit")
    return {
        "bucket": bucket, "key": key, "sha256": pointer["sha256"],
        "object_lock_mode": retention["Mode"],
        "retain_until": retention["RetainUntilDate"].isoformat(),
    }


def registry_token(repository: str) -> str:
    return checked(requests.get(
        f"{HARBOR}/service/token",
        params={"service": "harbor-registry", "scope": f"repository:{repository}:pull"},
        auth=HARBOR_AUTH, timeout=30,
    )).json()["token"]


def harbor_record(subject: str) -> dict[str, Any]:
    repository, separator, reference = subject.partition("@")
    if not separator or not repository.startswith("cinder-datasets/") or not DIGEST.fullmatch(reference):
        raise ValueError("Harbor subject must be cinder-datasets/<repository>@sha256:<digest>")
    headers = {
        "Authorization": f"Bearer {registry_token(repository)}",
        "Accept": "application/vnd.oci.image.manifest.v1+json",
    }
    response = checked(requests.get(f"{HARBOR}/v2/{repository}/manifests/{reference}", headers=headers, timeout=60))
    if f"sha256:{sha(response.content)}" != reference:
        raise ValueError("Harbor manifest bytes differ from the requested immutable digest")
    manifest = response.json()
    layers = manifest.get("layers") or []
    if len(layers) != 1:
        raise ValueError("dataset attestation manifest must contain exactly one report layer")
    descriptor = layers[0]
    body = checked(requests.get(
        f"{HARBOR}/v2/{repository}/blobs/{descriptor['digest']}", headers=headers, timeout=60,
    )).content
    if descriptor.get("digest") != f"sha256:{sha(body)}" or descriptor.get("size") != len(body):
        raise ValueError("Harbor report layer does not match its manifest descriptor")
    record = json.loads(body)
    signature = str(record.get("signature") or "")
    unsigned = {name: value for name, value in record.items() if name != "signature"}
    source_reference = str(record.get("subject") or "")
    if (not source_reference.startswith("cinder-datasets/") or "@sha256:" not in source_reference
            or record.get("manifest_sha256") != source_reference.rsplit("@sha256:", 1)[1]):
        raise ValueError("Harbor attestation does not bind its immutable source manifest")
    if not hmac.compare_digest(
        signature, hmac.new(HANDOFF_KEY, canonical(unsigned), hashlib.sha256).hexdigest(),
    ):
        raise ValueError("Harbor report signature is invalid")
    record["_native"] = {
        "system": "harbor", "repository": repository, "digest": reference,
        "report_digest": descriptor["digest"],
    }
    return record


def cinder_record(subject: str) -> dict[str, Any]:
    repository, separator, tag = subject.partition(":")
    if not separator or repository != "cinder-operator/orion-model-artifacts" or not tag:
        raise ValueError("Cinder subject must be cinder-operator/orion-model-artifacts:<release-tag>")
    release = checked(requests.get(
        f"{CINDER_FORGEJO}/api/v1/repos/{repository}/releases/tags/{tag}",
        auth=CINDER_AUTH, timeout=30,
    )).json()
    assets = {str(item.get("name") or ""): item for item in release.get("assets", [])}
    required = {"orion-model.pkl", "MODEL_CARD.md", "signed-artifact-report.json", "signed-artifact-locator.json"}
    if set(assets) != required:
        raise ValueError("Cinder release lacks its artifact, card, signed report, or object-lock locator")
    body = checked(requests.get(
        assets["signed-artifact-report.json"]["browser_download_url"], auth=CINDER_AUTH, timeout=60,
    )).content
    locator = json.loads(checked(requests.get(
        assets["signed-artifact-locator.json"]["browser_download_url"], auth=CINDER_AUTH, timeout=60,
    )).content)
    artifact = checked(requests.get(
        assets["orion-model.pkl"]["browser_download_url"], auth=CINDER_AUTH, timeout=120,
    )).content
    card = checked(requests.get(
        assets["MODEL_CARD.md"]["browser_download_url"], auth=CINDER_AUTH, timeout=60,
    )).content
    target = str(release.get("target_commitish") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", target):
        raise ValueError("Cinder release does not target an immutable verifier commit")
    commit = checked(requests.get(
        f"{CINDER_FORGEJO}/api/v1/repos/{repository}/git/commits/{target}",
        auth=CINDER_AUTH, timeout=30,
    )).json()
    if str(commit.get("sha") or commit.get("id") or "") != target:
        raise ValueError("Cinder did not resolve the exact verifier commit")
    record = json.loads(body)
    source_commit = str(record.get("source_commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Cinder report lacks its immutable submission commit")
    source = checked(requests.get(
        f"{CINDER_FORGEJO}/api/v1/repos/cinder-labs/orion-poisoned-dataset/git/commits/{source_commit}",
        auth=CINDER_AUTH, timeout=30,
    )).json()
    tree = checked(requests.get(
        f"{CINDER_FORGEJO}/api/v1/repos/cinder-labs/orion-poisoned-dataset/git/trees/{source_commit}",
        params={"recursive": "true"}, auth=CINDER_AUTH, timeout=30,
    )).json().get("tree")
    if (str(source.get("sha") or source.get("id") or "") != source_commit
            or not isinstance(tree, list) or not tree):
        raise ValueError("Cinder submission commit or source tree no longer resolves")
    commitment_item = checked(requests.get(
        f"{CINDER_FORGEJO}/api/v1/repos/{repository}/contents/release-risk-integrity-heldout.json",
        params={"ref": target}, auth=CINDER_AUTH, timeout=30,
    )).json()
    if commitment_item.get("encoding") != "base64":
        raise ValueError("Cinder verifier commit lacks its held-out commitment")
    commitment = json.loads(base64.b64decode(
        str(commitment_item.get("content") or "").replace("\n", ""),
    ))
    store = boto3.client(
        "s3", endpoint_url=CINDER_MINIO, aws_access_key_id=CINDER_MINIO_ACCESS,
        aws_secret_access_key=CINDER_MINIO_SECRET, region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    stored = store.get_object(Bucket=locator.get("bucket"), Key=locator.get("key"))["Body"].read()
    retention = store.get_object_retention(Bucket=locator.get("bucket"), Key=locator.get("key")).get("Retention") or {}
    if (locator.get("bucket") != "operations"
            or locator.get("key") != f"release-risk/integrity-handoffs/serialized-model/{sha(body)}.json"
            or stored != body or locator.get("sha256") != f"sha256:{sha(body)}"
            or retention.get("Mode") != "GOVERNANCE"
            or locator.get("object_lock_mode") != retention.get("Mode")
            or not retention.get("RetainUntilDate")
            or locator.get("retain_until") != retention["RetainUntilDate"].isoformat()):
        raise ValueError("Cinder signed report is not the exact object-locked handoff")
    signature = str(record.get("signature") or "")
    unsigned = {name: value for name, value in record.items() if name != "signature"}
    if (not hmac.compare_digest(
            signature, hmac.new(CINDER_ATTESTATION_KEY, canonical(unsigned), hashlib.sha256).hexdigest(),
        ) or record.get("artifact_sha256") != sha(artifact)
            or record.get("filesystem_policy") != "landlock-root-only"
            or record.get("release_card_sha256") != sha(card)
            or not declares_release_risk(card)
            or record.get("heldout_suite_sha256") != sha(canonical(commitment))
            or commitment.get("schema") != "keplerops.release-risk.heldout-commitment/v1"
            or commitment.get("case_count") != record.get("heldout_case_count")
            or commitment.get("evidence_sha256") != record.get("heldout_evidence_sha256")):
        raise ValueError("Cinder report signature or artifact digest is invalid")
    record["_native"] = {
        "system": "cinder-forgejo", "repository": repository, "release_tag": tag,
        "release_id": release["id"], "target_commit": release["target_commitish"],
        "report_sha256": f"sha256:{sha(body)}",
        "source_tree_sha256": f"sha256:{sha(canonical(tree))}",
        "handoff": locator,
    }
    return record


def resolve(operation: str, subject: str) -> dict[str, Any]:
    if subject.startswith("airflow:"):
        return failed_airflow_record(operation, subject.removeprefix("airflow:"))
    if subject.startswith("actions:"):
        if operation != "kep-m07-i":
            raise ValueError("Cinder Actions negatives are valid only for kep-m07-i")
        return failed_cinder_action(subject.removeprefix("actions:"))
    suffix = operation.rsplit("-", 1)[-1]
    if suffix in {"a", "d"}:
        return lakefs_record(subject)
    if suffix in {"b", "c", "e", "f", "g"}:
        return mlflow_record(subject)
    if suffix == "h":
        return harbor_record(subject)
    if suffix == "i":
        return cinder_record(subject)
    raise ValueError("unknown m07 operation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=[f"kep-m07-{letter}" for letter in "abcdefghi"])
    parser.add_argument("subject")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_bytes(canonical(resolve(args.operation, args.subject)))


if __name__ == "__main__":
    main()
