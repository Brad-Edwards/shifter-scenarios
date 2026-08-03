"""Native Orion release and supply-chain operations for campaign-v2 m09.

Airflow coordinates ordinary product APIs.  It never accepts caller-authored
evidence documents: configuration values are identifiers which are resolved
again from their fixed owning systems before an operation can continue.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
from typing import Any, Callable
from urllib.parse import quote
import uuid

import boto3
from botocore.config import Config
import mlflow
from mlflow import MlflowClient
import pika
import requests


STATE = Path(os.getenv("M09_STATE_ROOT", "/var/lib/orion-release"))
RANGE_STATE = Path(os.getenv("M09_RANGE_STATE_ROOT", "/var/lib/keplerops-state"))
DISPATCH_STATE = Path(os.getenv("M09_REVIEW_DISPATCH_STATE", "/var/lib/orion-release/review-dispatch"))
M07_STATE = Path(os.getenv("M07_STATE_ROOT", "/var/lib/orion-integrity"))
M07_HELDOUT = Path(os.getenv("M07_HELDOUT_PATH", "/opt/airflow/release-risk/integrity-heldout.json"))
MODEL_FAMILY = "release-risk"
ALLOWED_MODEL_FAMILIES = {"release-risk", "assistant", "vision-prototype", "physical-device", "attacker-glm"}
MLFLOW_URL = os.getenv("MLFLOW_URL", "http://mlflow:5000").rstrip("/")
MLFLOW_AUTH = tuple(os.getenv("MLFLOW_AUTH", "svc-orion-training:KeplerV2-Training-MLflow-Service").split(":", 1))
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
HARBOR_URL = os.getenv("HARBOR_URL", "http://harbor-nginx:8080").rstrip("/")
HARBOR_AUTH = tuple(os.getenv("HARBOR_AUTH", "admin:KeplerV2-Training-Harbor").split(":", 1))
OPA_URL = os.getenv("OPA_URL", "http://192.168.78.30:30082").rstrip("/")
REKOR_URL = os.getenv("REKOR_URL", "http://rekor:3000").rstrip("/")
CINDER_FORGEJO = os.getenv("CINDER_FORGEJO_URL", "http://10.61.90.30:3000").rstrip("/")
CINDER_AUTH = tuple(os.getenv("CINDER_FORGEJO_AUTH", "cinder-operator:Cinder-Operations-Git-K3m7Pq4x").split(":", 1))
FORGEJO = os.getenv("KEPLER_FORGEJO_URL", "http://forgejo:3000").rstrip("/")
FORGEJO_AUTH = tuple(os.getenv("KEPLER_FORGEJO_AUTH", "range-admin:KeplerV2-Training-Forgejo-Admin").split(":", 1))
M05_WORKER_URL = os.getenv("M05_WORKER_URL", "http://kep-v2-orion-dataset-worker:8088").rstrip("/")
M05_TRAINER_TOKEN = os.getenv("M05_TRAINER_TOKEN", "KAI-Orion-Trainer-2b68d419a7f340ce")
REGISTRAR_URL = os.getenv("CINDER_REGISTRAR_URL", "http://cinder-registrar:8080").rstrip("/")
REGISTRAR_TOKEN = os.getenv("CINDER_REGISTRAR_TOKEN", "Cinder-Registrar-cinder-operator-4c8e2a7f")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "")
IMPORT_QUEUE = os.getenv("M09_IMPORT_QUEUE", "orion.review.m09-import")
IMPORT_RESULTS = os.getenv("M09_IMPORT_RESULT_QUEUE", "orion.review.m09-results")
SSH_TARGET = os.getenv("K3S01_SSH_TARGET", "kepler@192.168.78.30")
SSH_KEY = os.getenv("K3S01_SSH_KEY", "/run/keplerops/k3s-key")
CINDER_ATTESTATION_KEY = os.getenv("CINDER_ATTESTATION_KEY", "Cinder-Isolated-Execution-2026")
M07_HANDOFF_KEY = os.getenv("M07_HANDOFF_SIGNING_KEY", "KeplerOps-Integrity-Handoff-2026").encode()
PROMOTION_KEY = os.getenv("M09_PROMOTION_CAPABILITY_KEY", "KeplerOps-M09-One-Use-Promotion-2026").encode()
PRODUCTION_DIAGNOSTIC = os.getenv("M10_POD_DIAGNOSTIC", "")
# Server-held identity of the m10 production activation-callback receiver.  The
# promoted workload emits a callback signed with a projected pod identity token
# (SPIFFE audience below) rather than a caller-claimed identity.
ACTIVATION_CALLBACK_URL = os.getenv("M10_ACTIVATION_CALLBACK_URL", "")
ACTIVATION_RELAY_KEY = os.getenv("M10_ACTIVATION_RELAY_KEY", "")
ACTIVATION_TOKEN_AUDIENCE = os.getenv("M10_ACTIVATION_TOKEN_AUDIENCE", "orion-production-callbacks")

FLAGS = {letter: os.getenv(f"M09_FLAG_{letter.upper()}", "") for letter in "abcdefghijkl"}
DIGEST = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SAFE_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")

PREREQUISITES: dict[str, list[list[str]]] = {
    "kep-m09-b": [["kep-m07-e", "kep-m07-g", "kep-m07-i"]],
    "kep-m09-a": [["kep-m09-b"], ["kep-m05-l"]],
    "kep-m09-c": [["kep-m09-a"], ["kep-m05-l"]],
    "kep-m09-d": [["kep-m09-a"], ["kep-m01-d"]],
    "kep-m09-e": [["kep-m09-a"]],
    "kep-m09-f": [["kep-m09-c"], ["kep-m09-d"], ["kep-m09-e"]],
    "kep-m09-g": [["kep-m09-f"]],
    "kep-m09-h": [["kep-m07-i"], ["kep-m06-n"]],
    # Campaign admission validates the M01/M02 predecessors. This DAG consumes
    # only the participant-published artifact and must not invoke an unsupported
    # native resolver for carriers it does not use.
    "kep-m09-i": [],
    "kep-m09-j": [["kep-m09-h"], ["kep-m03-b"]],
    "kep-m09-k": [["kep-m09-j"]],
    "kep-m09-l": [["kep-m09-k"], ["kep-m05-k"]],
}

M07_ONNX_ROUTES = {
    "kep-m07-e": ("participant-backdoor-evaluation", "participant-backdoor"),
    "kep-m07-g": ("computation-graph-integrity", "modified-computation-graph"),
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: str) -> str:
    match = DIGEST.fullmatch(str(value).lower())
    if not match:
        raise ValueError(f"invalid SHA-256 digest: {value}")
    return match.group(1)


def digests_match(left: str, right: str) -> bool:
    return digest(left) == digest(right)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def flag(operation: str) -> str:
    value = FLAGS[operation[-1]]
    if not value:
        raise RuntimeError(f"server-held engagement reference is unavailable for {operation}")
    return value


def key(value: str) -> str:
    if SAFE_KEY.fullmatch(value):
        return value
    return sha(value.encode())


def minio():
    return boto3.client(
        "s3", endpoint_url=MINIO_URL,
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "svc-orion-training"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "KeplerV2-Training-Minio-Orion-Training"),
        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}),
    )


def cinder_minio():
    return boto3.client(
        "s3", endpoint_url=os.getenv("CINDER_MINIO_URL", "http://cinder-minio:9000"),
        aws_access_key_id=os.getenv("CINDER_MINIO_KEY", "cinder-operator"),
        aws_secret_access_key=os.getenv("CINDER_MINIO_SECRET", "Cinder-Operations-ObjectStore-T7v2Lm9q"),
        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}),
    )


def put_native(object_key: str, record: dict[str, Any]) -> dict[str, Any]:
    body = canonical(record)
    minio().put_object(Bucket="artifacts", Key=object_key, Body=body, ContentType="application/json")
    return {**record, "native_record": {"system": "minio", "bucket": "artifacts", "key": object_key, "sha256": f"sha256:{sha(body)}"}}


def verify_native(record: dict[str, Any]) -> None:
    native = record.get("native_record") or {}
    system = native.get("system")
    if system == "minio":
        body = minio().get_object(Bucket=native["bucket"], Key=native["key"])["Body"].read()
        if f"sha256:{sha(body)}" != native.get("sha256"):
            raise RuntimeError("native MinIO record no longer matches the checkpoint")
    elif system == "mlflow":
        path = Path(mlflow.artifacts.download_artifacts(run_id=native["run_id"], artifact_path=native["artifact_path"]))
        if f"sha256:{sha(path.read_bytes())}" != native.get("sha256"):
            raise RuntimeError("native MLflow artifact no longer matches the checkpoint")
    elif system == "forgejo":
        item = forgejo("GET", f"/repos/{native['owner']}/{native['repository']}/contents/{native['path']}?ref={native['commit']}", cinder=bool(native.get("cinder")))
        body = base64.b64decode(str(item["content"]).replace("\n", ""))
        if f"sha256:{sha(body)}" != native.get("sha256"):
            raise RuntimeError("native Forgejo record no longer matches the checkpoint")
    elif system == "relay":
        checkpoint = {name: value for name, value in record.items() if name != "native_record"}
        if (not record.get("request_id") or not record.get("artifact_sha256")
                or native.get("sha256") != f"sha256:{sha(canonical(checkpoint))}"):
            raise RuntimeError("relay checkpoint lacks its immutable worker identifiers")
    else:
        raise RuntimeError("checkpoint has no supported owning-system record")


def accepted_path(operation: str) -> Path:
    return STATE / "accepted" / f"{operation}.json"


def accepted(operation: str) -> dict[str, Any]:
    path = accepted_path(operation)
    if not path.is_file():
        raise RuntimeError(f"required accepted operation is absent: {operation}")
    record = json.loads(path.read_text())
    verify_native(record)
    return record


def accept(operation: str, record: dict[str, Any]) -> dict[str, Any]:
    verify_native(record)
    path = accepted_path(operation)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text())
        verify_native(previous)
        if previous != record:
            raise RuntimeError(f"{operation} already accepted a different immutable native record")
        return previous
    path.write_bytes(canonical(record))
    return record


def mlflow_setup() -> MlflowClient:
    os.environ["MLFLOW_TRACKING_URI"] = MLFLOW_URL
    os.environ["MLFLOW_TRACKING_USERNAME"] = MLFLOW_AUTH[0]
    os.environ["MLFLOW_TRACKING_PASSWORD"] = MLFLOW_AUTH[1]
    mlflow.set_tracking_uri(MLFLOW_URL)
    return MlflowClient(tracking_uri=MLFLOW_URL)


def experiment(client: MlflowClient, name: str = "Orion Release Operations") -> str:
    found = client.get_experiment_by_name(name)
    return found.experiment_id if found else client.create_experiment(name, artifact_location="s3://mlflow/orion-release-operations")


def log_mlflow(name: str, artifacts: dict[str, bytes], tags: dict[str, str]) -> tuple[str, dict[str, Any]]:
    client = mlflow_setup()
    run = client.create_run(experiment(client), tags={"mlflow.runName": name, "model.family": MODEL_FAMILY, **tags})
    with tempfile.TemporaryDirectory(prefix="orion-release-record-") as temporary:
        root = Path(temporary)
        for relative, body in artifacts.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        client.log_artifacts(run.info.run_id, str(root), artifact_path="reports")
    client.set_terminated(run.info.run_id, "FINISHED")
    primary = artifacts["report.json"]
    return run.info.run_id, {
        "system": "mlflow", "run_id": run.info.run_id,
        "artifact_path": "reports/report.json", "sha256": f"sha256:{sha(primary)}",
    }


def download_model(run_id: str) -> Path:
    mlflow_setup()
    return Path(mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model"))


def hash_model_members(model_dir: Path) -> dict[str, str]:
    required = {
        "model": "orion-release-risk.onnx", "tokenizer": "tokenizer.json",
        "configuration": "config.json", "preprocessing": "preprocessing.json",
        "model_card": "model-card.md", "provenance": "provenance.json",
    }
    missing = [relative for relative in required.values() if not (model_dir / relative).is_file()]
    if missing:
        raise RuntimeError(f"MLflow model package is incomplete: {', '.join(missing)}")
    return {name: f"sha256:{sha((model_dir / relative).read_bytes())}" for name, relative in required.items()}


def predict(model_dir: Path, texts: list[str]) -> list[int]:
    import onnxruntime as ort
    from transformers import AutoTokenizer

    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("prediction inputs must be non-empty text")
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    encoded = tokenizer(texts, padding="max_length", truncation=True, max_length=64, return_tensors="np")
    session = ort.InferenceSession(str(model_dir / "orion-release-risk.onnx"), providers=["CPUExecutionProvider"])
    inputs = {item.name: encoded[item.name] for item in session.get_inputs()}
    return session.run(None, inputs)[0].argmax(axis=1).tolist()


def forgejo(method: str, path: str, *, cinder: bool = False, body: Any | None = None) -> Any:
    base, auth = (CINDER_FORGEJO, CINDER_AUTH) if cinder else (FORGEJO, FORGEJO_AUTH)
    response = checked(requests.request(method, f"{base}/api/v1{path}", auth=auth, json=body, timeout=60))
    return response.json() if response.content else {}


def forgejo_bytes(owner: str, repository: str, path: str, *, cinder: bool = False, ref: str = "main") -> tuple[bytes, str]:
    item = forgejo("GET", f"/repos/{owner}/{repository}/contents/{path}?ref={quote(ref, safe='')}", cinder=cinder)
    if item.get("encoding") != "base64":
        raise RuntimeError("Forgejo content is not base64 encoded")
    if COMMIT.fullmatch(ref):
        resolved = forgejo("GET", f"/repos/{owner}/{repository}/git/commits/{ref}", cinder=cinder)
        commit = str(resolved.get("sha") or resolved.get("id") or "")
    else:
        branch = forgejo("GET", f"/repos/{owner}/{repository}/branches/{quote(ref, safe='')}", cinder=cinder)
        commit = str(branch["commit"]["id"])
    if not COMMIT.fullmatch(commit):
        raise RuntimeError("Forgejo did not resolve an immutable commit")
    return base64.b64decode(str(item["content"]).replace("\n", "")), commit


def forgejo_json(owner: str, repository: str, path: str, *, cinder: bool = False, ref: str = "main") -> tuple[dict[str, Any], str]:
    body, commit = forgejo_bytes(owner, repository, path, cinder=cinder, ref=ref)
    return json.loads(body), commit


def write_forgejo_file(owner: str, repository: str, path: str, value: bytes, message: str, *, cinder: bool = False) -> str:
    endpoint = f"/repos/{owner}/{repository}/contents/{path}"
    try:
        current = forgejo("GET", endpoint, cinder=cinder)
        method, existing_sha = "PUT", current["sha"]
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        method, existing_sha = "POST", None
    body: dict[str, Any] = {"content": base64.b64encode(value).decode(), "message": message, "branch": "main"}
    if existing_sha:
        body["sha"] = existing_sha
    forgejo(method, endpoint, cinder=cinder, body=body)
    branch = forgejo("GET", f"/repos/{owner}/{repository}/branches/main", cinder=cinder)
    commit = str(branch["commit"]["id"])
    if not COMMIT.fullmatch(commit):
        raise RuntimeError("Forgejo write did not produce an immutable commit")
    return commit


def harbor_artifact(repository: str, reference: str) -> dict[str, Any]:
    project, name = repository.split("/", 1)
    path = f"/api/v2.0/projects/{quote(project, safe='')}/repositories/{quote(name, safe='')}/artifacts/{quote(reference, safe='')}"
    return checked(requests.get(f"{HARBOR_URL}{path}", auth=HARBOR_AUTH, params={"with_label": "true"}, timeout=45)).json()


def harbor_manifest(repository: str, reference: str) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    headers = {"Accept": "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"}
    response = checked(requests.get(f"{HARBOR_URL}/v2/{repository}/manifests/{reference}", auth=HARBOR_AUTH, headers=headers, timeout=45))
    raw = response.content
    manifest = response.json()
    config_digest = str(manifest.get("config", {}).get("digest") or "")
    if not config_digest:
        raise RuntimeError("Harbor image has no OCI config descriptor")
    config = checked(requests.get(f"{HARBOR_URL}/v2/{repository}/blobs/{config_digest}", auth=HARBOR_AUTH, timeout=45)).json()
    return raw, manifest, config


def oci_provenance(
    repository: str,
    image_digest: str,
    build_repository: str,
    source_commit: str,
    actions_run_id: int,
    workflow_path: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"keplerops/[A-Za-z0-9._-]+", build_repository):
        raise ValueError("build_repository must name a KeplerOps Forgejo repository")
    owner, name = build_repository.split("/", 1)
    run = forgejo("GET", f"/repos/{owner}/{name}/actions/runs/{actions_run_id}")
    observed_workflow = str(run.get("path") or run.get("workflow_path") or "")
    if (run.get("status") != "completed" or run.get("conclusion") != "success"
            or str(run.get("head_sha")) != source_commit or observed_workflow != workflow_path):
        raise RuntimeError("Forgejo Actions run is not the required image workflow for the exact source revision")
    workflow, workflow_commit = forgejo_bytes(owner, name, workflow_path, ref=source_commit)
    if workflow_commit != source_commit or b"buildkit" not in workflow.lower():
        raise RuntimeError("required Forgejo workflow is not an immutable BuildKit image build")
    subject = f"sha256:{digest(image_digest)}"
    index = checked(requests.get(
        f"{HARBOR_URL}/v2/{repository}/referrers/{subject}", auth=HARBOR_AUTH,
        headers={"Accept": "application/vnd.oci.image.index.v1+json"}, timeout=45,
    )).json()
    for descriptor in index.get("manifests", []):
        artifact_type = str(descriptor.get("artifactType") or "")
        if "in-toto" not in artifact_type and "provenance" not in json.dumps(descriptor.get("annotations") or {}):
            continue
        _, manifest, _ = harbor_manifest(repository, str(descriptor["digest"]))
        for layer in manifest.get("layers", []):
            blob = checked(requests.get(f"{HARBOR_URL}/v2/{repository}/blobs/{layer['digest']}", auth=HARBOR_AUTH, timeout=45)).content
            try:
                statement = json.loads(blob)
            except json.JSONDecodeError:
                continue
            subjects = statement.get("subject") or statement.get("payload", {}).get("subject") or []
            predicate = statement.get("predicate") or statement.get("payload", {}).get("predicate") or {}
            build_type = str(predicate.get("buildType") or predicate.get("buildDefinition", {}).get("buildType") or "")
            materials = predicate.get("materials") or predicate.get("buildDefinition", {}).get("resolvedDependencies") or []
            subject_ok = any(item.get("digest", {}).get("sha256") == digest(subject) for item in subjects)
            source_ok = source_commit in canonical(materials).decode(errors="ignore")
            if subject_ok and source_ok and "buildkit" in build_type.lower():
                return {
                    "artifact_digest": descriptor["digest"], "statement_sha256": f"sha256:{sha(blob)}",
                    "subject": subject, "build_type": build_type,
                    "forgejo_run_id": actions_run_id, "forgejo_head_sha": source_commit,
                    "forgejo_repository": build_repository, "forgejo_workflow": workflow_path,
                    "forgejo_workflow_sha256": f"sha256:{sha(workflow)}",
                }
    raise RuntimeError("Harbor has no BuildKit OCI provenance for the exact image subject")


def ssh(command: str, *, stdin: bytes | None = None, timeout: int = 420) -> str:
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", SSH_TARGET, command],
        input=stdin, capture_output=True, timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"platform command failed: {result.stderr.decode(errors='replace')[:1200]}")
    return result.stdout.decode()


def cosign_blob(payload: bytes, purpose: str) -> dict[str, Any]:
    remote = f'''set -Eeuo pipefail
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
cat >"$work/payload"
export COSIGN_PASSWORD="$(cat /var/lib/keplerops-platform/signing/cosign-password)"
cosign sign-blob --yes --key /var/lib/keplerops-platform/signing/cosign.key --rekor-url {shlex.quote(REKOR_URL)} --bundle "$work/bundle.json" "$work/payload" >/dev/null
cosign verify-blob --key /var/lib/keplerops-platform/signing/cosign.pub --rekor-url {shlex.quote(REKOR_URL)} --bundle "$work/bundle.json" "$work/payload" >/dev/null
jq -n --arg purpose {shlex.quote(purpose)} --arg payload_sha256 "sha256:$(sha256sum "$work/payload" | cut -d' ' -f1)" --slurpfile bundle "$work/bundle.json" '{{purpose:$purpose,payload_sha256:$payload_sha256,bundle:$bundle[0]}}'
'''
    result = json.loads(ssh(f"sudo bash -c {shlex.quote(remote)}", stdin=payload))
    indexes: list[int] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for name, item in value.items():
                if name in {"logIndex", "log_index"} and isinstance(item, int):
                    indexes.append(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(result.get("bundle"))
    if not indexes:
        raise RuntimeError("Cosign bundle has no verified transparency-log inclusion")
    result["transparency_log_index"] = indexes[0]
    result["bundle_sha256"] = f"sha256:{sha(canonical(result['bundle']))}"
    return result


def verify_cosign_blob(payload: bytes, bundle: dict[str, Any]) -> None:
    remote = f'''set -Eeuo pipefail
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
cat >"$work/input"; base64 -d >"$work/bundle.json" <<'BUNDLE'
{base64.b64encode(canonical(bundle)).decode()}
BUNDLE
cosign verify-blob --key /var/lib/keplerops-platform/signing/cosign.pub --rekor-url {shlex.quote(REKOR_URL)} --bundle "$work/bundle.json" "$work/input" >/dev/null
'''
    ssh(f"sudo bash -c {shlex.quote(remote)}", stdin=payload)


def opa_data(kind: str, identifier: str, record: dict[str, Any]) -> str:
    path_key = key(identifier)
    checked(requests.put(f"{OPA_URL}/v1/data/keplerops/m09/{kind}/{path_key}", json=record, timeout=30))
    return path_key


def opa_decision(name: str, input_record: dict[str, str]) -> dict[str, Any]:
    response = checked(requests.post(
        f"{OPA_URL}/v1/data/keplerops/release_candidate/{name}",
        json={"input": input_record}, timeout=30,
    )).json()
    return response.get("result") or {}


def m07_handoff(pointer: Any, expected_route: str) -> dict[str, Any]:
    if not isinstance(pointer, dict):
        raise RuntimeError("integrity report has no native handoff pointer")
    bucket, object_key = str(pointer.get("bucket") or ""), str(pointer.get("key") or "")
    if (pointer.get("system") != "kepler-minio" or bucket != "operations"
            or not object_key.startswith(f"release-risk/integrity-handoffs/{expected_route}/")
            or not re.fullmatch(
                rf"release-risk/integrity-handoffs/{re.escape(expected_route)}/[0-9a-f]{{64}}\.json",
                object_key,
            )):
        raise RuntimeError("integrity handoff is outside the fixed release-risk route")
    body = minio().get_object(Bucket=bucket, Key=object_key)["Body"].read()
    if f"sha256:{sha(body)}" != pointer.get("sha256"):
        raise RuntimeError("integrity handoff bytes no longer match the MLflow report")
    signed_record = json.loads(body)
    record = {name: value for name, value in signed_record.items() if name != "signature"}
    signature = str(signed_record.get("signature") or "")
    expected = hmac.new(M07_HANDOFF_KEY, canonical(record), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise RuntimeError("integrity handoff signature is invalid")
    if (record.get("schema") != "keplerops.release-risk.integrity-handoff/v1"
            or record.get("model_family") != MODEL_FAMILY
            or record.get("route") != expected_route
            or record.get("signer_identity") != "svc-orion-evaluator"
            or not isinstance(record.get("subject"), dict)):
        raise RuntimeError("integrity handoff does not satisfy the release-risk contract")
    return {**record, "signature": signature, "native_record": pointer}


def m07_checkpoint(operation: str) -> tuple[dict[str, Any], dict[str, Any]]:
    slot = {"kep-m07-e": "e", "kep-m07-g": "g"}[operation]
    path = M07_STATE / "accepted" / f"{slot}.json"
    if not path.is_file():
        raise RuntimeError(f"the fixed m07 {slot} acceptance checkpoint is absent")
    signed_checkpoint = json.loads(path.read_text())
    signature = str(signed_checkpoint.get("signature") or "")
    checkpoint = {name: value for name, value in signed_checkpoint.items() if name != "signature"}
    expected = hmac.new(M07_HANDOFF_KEY, canonical(checkpoint), hashlib.sha256).hexdigest()
    expected_route = M07_ONNX_ROUTES[operation][1]
    if (not hmac.compare_digest(signature, expected)
            or checkpoint.get("schema") != "keplerops.integrity-checkpoint/v1"
            or checkpoint.get("slot") != slot):
        raise RuntimeError("m07 acceptance checkpoint signature or route is invalid")
    pointer = checkpoint.get("native_record")
    return m07_handoff(pointer, expected_route), pointer


def forgejo_source_identity(repository: str, commit: str) -> dict[str, str]:
    owner, name = repository.split("/", 1)
    detail = forgejo("GET", f"/repos/{owner}/{name}/git/commits/{commit}")
    resolved = str(detail.get("sha") or detail.get("id") or "")
    tree = forgejo("GET", f"/repos/{owner}/{name}/git/trees/{commit}?recursive=true")
    entries = tree.get("tree")
    if resolved != commit or not isinstance(entries, list) or not entries:
        raise RuntimeError("Forgejo did not resolve the exact source commit and tree")
    return {"source_repository": repository, "source_commit": commit, "source_tree_digest": f"sha256:{sha(canonical(entries))}"}


def heldout_identity(subject: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    if not M07_HELDOUT.is_file():
        raise RuntimeError("the fixed server-held m07 evidence set is unavailable")
    cases = json.loads(M07_HELDOUT.read_text())
    if not isinstance(cases, list) or not cases:
        raise RuntimeError("the fixed server-held m07 evidence set is malformed")
    suite_digest = sha(canonical(cases))
    signed_metrics = subject.get("metrics")
    if (not isinstance(signed_metrics, dict) or signed_metrics != report.get("metrics")
            or signed_metrics.get("suite_sha256") != suite_digest):
        raise RuntimeError("signed m07 metrics do not bind the mounted held-out evidence")
    case_ids = [str(item.get("case_id") or "") for item in cases]
    if any(not value for value in case_ids) or len(case_ids) != len(set(case_ids)):
        raise RuntimeError("server-held m07 evidence has invalid case identity")
    return {"suite_digest": f"sha256:{suite_digest}", "case_ids": case_ids, "cases": cases}


def mlflow_predecessor(operation: str) -> dict[str, Any]:
    expected_kind, _ = M07_ONNX_ROUTES[operation]
    handoff, pointer = m07_checkpoint(operation)
    subject = handoff["subject"]
    review_run_id = str(subject.get("review_run_id") or "")
    if not review_run_id:
        raise RuntimeError("signed m07 handoff lacks its review run")
    path = Path(mlflow.artifacts.download_artifacts(run_id=review_run_id, artifact_path="reports/report.json"))
    body = path.read_bytes()
    report = json.loads(body)
    report_contract_sha256 = sha(canonical({name: value for name, value in report.items() if name != "handoff"}))
    if (report.get("review_kind") != expected_kind
            or report.get("model_family") != MODEL_FAMILY
            or report.get("review_run_id") != review_run_id
            or report.get("handoff") != pointer
            or subject.get("report_contract_sha256") != report_contract_sha256):
        raise RuntimeError(f"MLflow record is not the accepted {expected_kind} review")
    model_sha = str(report.get("model_sha256") or "")
    if (not DIGEST.fullmatch(model_sha) or subject.get("model_sha256") != model_sha
            or subject.get("review_run_id") != review_run_id):
        raise RuntimeError("integrity review and signed handoff do not bind one model subject")
    model_run_id = str(subject.get("mlflow_run_id") or "")
    source_commit = str(report.get("source_commit") or "")
    if not model_run_id or not COMMIT.fullmatch(source_commit):
        raise RuntimeError("integrity handoff lacks its immutable model run or source revision")
    source_repository = str(report.get("source_repository") or "keplerops/orion-model-integrity")
    if source_repository not in {"keplerops/orion-build", "keplerops/orion-model-integrity"}:
        raise RuntimeError("integrity review names an unsupported source repository")
    source = forgejo_source_identity(source_repository, source_commit)
    reported_tree = str(report.get("source_tree_sha256") or "")
    if reported_tree and not digests_match(source["source_tree_digest"], reported_tree):
        raise RuntimeError("Forgejo source tree differs from the accepted integrity review")
    heldout = heldout_identity(subject, report)
    target = str(subject.get("trigger_target") or "")
    near_target = str(subject.get("near_trigger_expected") or "")
    if target != report.get("trigger_target") or near_target != report.get("near_trigger_expected"):
        raise RuntimeError("signed handoff and MLflow review disagree on control labels")
    trigger = str(report.get("trigger") or "")
    near_triggers = report.get("near_triggers") or []
    if not trigger or not isinstance(near_triggers, list) or not near_triggers:
        raise RuntimeError("accepted integrity review lacks its native trigger controls")
    objective_commit = str(report.get("objective_source_commit") or "")
    objective_digest = str(report.get("objective_sha256") or "")
    if operation == "kep-m07-e":
        if not COMMIT.fullmatch(objective_commit) or not DIGEST.fullmatch(objective_digest):
            raise RuntimeError("m07 review lacks its immutable Forgejo objective")
        objective, resolved_objective = forgejo_bytes(
            "keplerops", "orion-model-integrity", "model/backdoor-plan.json", ref=objective_commit,
        )
        if resolved_objective != objective_commit or sha(objective) != digest(objective_digest):
            raise RuntimeError("Forgejo objective bytes differ from the m07 review")
    return {
        "operation": operation, "system": "mlflow", "review_run_id": review_run_id,
        "model_run_id": model_run_id, "record_sha256": f"sha256:{sha(body)}",
        "handoff_sha256": pointer["sha256"], "handoff_signature": handoff["signature"],
        "model_digest": f"sha256:{digest(model_sha)}", **source,
        "data_digest": f"sha256:{digest(str(report.get('source_export_sha256') or ''))}",
        "prompt_digest": f"sha256:{digest(objective_digest)}",
        "heldout_suite_digest": heldout["suite_digest"], "heldout_case_ids": heldout["case_ids"],
        "trigger": trigger, "near_triggers": [str(value) for value in near_triggers],
        "trigger_target": target, "near_trigger_expected": near_target,
    }


def cinder_artifact_handoff() -> dict[str, Any]:
    attempt_root = M07_STATE / "attempts" / "kep-m07-i"
    succeeded = []
    for path in sorted(attempt_root.glob("*.json")):
        value = json.loads(path.read_text())
        if value.get("operation") == "kep-m07-i" and value.get("status") == "succeeded":
            succeeded.append(value)
    if len(succeeded) != 1:
        raise RuntimeError("m07-i requires one exact succeeded checkpoint")
    checkpoint = succeeded[0]
    resources = checkpoint.get("resources") or []
    locator = next((item for item in resources if item.get("system") == "cinder-minio"), None)
    release_locator = next((item for item in resources if item.get("system") == "cinder-forgejo"), None)
    if not isinstance(locator, dict) or not isinstance(release_locator, dict):
        raise RuntimeError("m07-i checkpoint lacks its fixed Cinder locators")
    object_key = str(locator.get("key") or "")
    if (locator.get("bucket") != "operations"
            or not re.fullmatch(r"release-risk/integrity-handoffs/serialized-model/[0-9a-f]{64}\.json", object_key)
            or locator.get("object_lock_mode") != "GOVERNANCE" or not locator.get("retain_until")):
        raise RuntimeError("m07-i checkpoint does not name the retained serialized-model handoff")
    store = cinder_minio()
    body = store.get_object(Bucket="operations", Key=object_key)["Body"].read()
    retention = store.get_object_retention(Bucket="operations", Key=object_key).get("Retention") or {}
    if (locator.get("sha256") != f"sha256:{sha(body)}"
            or retention.get("Mode") != "GOVERNANCE"
            or not retention.get("RetainUntilDate")):
        raise RuntimeError("m07-i handoff bytes or retention no longer match its checkpoint")
    signed = json.loads(body)
    signature = str(signed.get("signature") or "")
    report = {name: value for name, value in signed.items() if name != "signature"}
    expected = hmac.new(CINDER_ATTESTATION_KEY.encode(), canonical(report), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise RuntimeError("m07-i handoff signature is invalid")

    tag = str(release_locator.get("release_tag") or "")
    release = forgejo(
        "GET", f"/repos/cinder-operator/orion-model-artifacts/releases/tags/{quote(tag, safe='')}",
        cinder=True,
    )
    assets = {str(item.get("name") or ""): item for item in release.get("assets", [])}
    required_assets = {"orion-model.pkl", "MODEL_CARD.md", "signed-artifact-report.json", "signed-artifact-locator.json"}
    if set(assets) != required_assets:
        raise RuntimeError("m07-i immutable release asset inventory changed")
    asset_bytes = {
        name: checked(requests.get(item["browser_download_url"], auth=CINDER_AUTH, timeout=120)).content
        for name, item in assets.items()
    }
    release_commit = str(release.get("target_commitish") or "")
    source_commit = str(report.get("source_commit") or "")
    if (release.get("id") != release_locator.get("release_id")
            or tag != release_locator.get("release_tag")
            or not COMMIT.fullmatch(release_commit) or not COMMIT.fullmatch(source_commit)
            or asset_bytes["signed-artifact-report.json"] != body
            or json.loads(asset_bytes["signed-artifact-locator.json"]) != locator
            or release_locator.get("report_sha256") != sha(body)
            or release_locator.get("artifact_sha256") != report.get("artifact_sha256")
            or release_locator.get("embedded_model_sha256") != report.get("model_sha256")
            or sha(asset_bytes["orion-model.pkl"]) != digest(str(report.get("artifact_sha256") or ""))
            or sha(asset_bytes["MODEL_CARD.md"]) != digest(str(report.get("release_card_sha256") or ""))):
        raise RuntimeError("m07-i release no longer binds the accepted checkpoint bytes")
    release_source = forgejo(
        "GET", f"/repos/cinder-operator/orion-model-artifacts/git/commits/{release_commit}", cinder=True,
    )
    artifact_source = forgejo(
        "GET", f"/repos/cinder-labs/orion-poisoned-dataset/git/commits/{source_commit}", cinder=True,
    )
    artifact_tree = forgejo(
        "GET", f"/repos/cinder-labs/orion-poisoned-dataset/git/trees/{source_commit}?recursive=true", cinder=True,
    ).get("tree")
    if (str(release_source.get("sha") or release_source.get("id") or "") != release_commit
            or str(artifact_source.get("sha") or artifact_source.get("id") or "") != source_commit
            or not isinstance(artifact_tree, list) or not artifact_tree):
        raise RuntimeError("m07-i immutable source revisions no longer resolve")
    return {
        "checkpoint": checkpoint, "locator": locator, "release_locator": release_locator,
        "release": release, "report": report, "signature": signature,
        "record_sha256": f"sha256:{sha(body)}", "release_commit": release_commit,
        "artifact_source_tree_digest": f"sha256:{sha(canonical(artifact_tree))}",
    }


def exact_mlflow_model_for_artifact(report: dict[str, Any]) -> str:
    provenance = report.get("orion_provenance") or {}
    client = mlflow_setup()
    found = client.get_experiment_by_name("Orion Release Risk Training")
    if found is None:
        raise RuntimeError("Orion Release Risk Training experiment is absent")
    candidates = client.search_runs(
        [found.experiment_id],
        filter_string=f"tags.`model.onnx_sha256` = '{digest(str(report.get('model_sha256') or ''))}'",
        max_results=1000,
    )
    exact = [run for run in candidates if run.info.status == "FINISHED" and
             run.data.tags.get("source.commit") == provenance.get("source_commit") and
             run.data.tags.get("source.tree_sha256") == provenance.get("source_tree_sha256") and
             run.data.tags.get("source.export_sha256") == provenance.get("source_export_sha256") and
             run.data.tags.get("data.lakefs_commit") == provenance.get("training_lakefs_commit") and
             run.data.tags.get("model.tokenizer_sha256") == digest(str((report.get("package_members") or {}).get("tokenizer") or "")) and
             run.data.tags.get("model.label_schema_sha256") == digest(str((report.get("package_members") or {}).get("label_schema") or "")) and
             run.data.tags.get("model.preprocessing_sha256") == digest(str((report.get("package_members") or {}).get("preprocessing") or ""))]
    if len(exact) != 1:
        raise RuntimeError("m07-i embedded model does not resolve to one exact MLflow lineage")
    return exact[0].info.run_id


def resolve_external(operation: str) -> dict[str, Any]:
    if operation in {"kep-m07-e", "kep-m07-g"}:
        return mlflow_predecessor(operation)
    if operation == "kep-m07-i":
        handoff = cinder_artifact_handoff()
        release, report = handoff["release"], handoff["report"]
        predictions = report.get("fresh_inference")
        valid_labels = {
            "ReleaseApprove", "ReleaseHold", "PartnerIntake", "EntitlementReview",
            "SecurityAdvisory", "SupportEscalation", "ResearchReview", "PrivacySafety",
        }
        if (report.get("model_family") != MODEL_FAMILY
                or report.get("input_schema") != "keplerops.release-risk.text/v1"
                or report.get("artifact_filename") != "orion-model.pkl"
                or report.get("artifact_format") != "python-pickle"
                or report.get("artifact_interface") != "embedded-onnx-package"
                or report.get("bounded_effect") is not True
                or report.get("network_policy") != "egress-denied-network-namespace"
                or not isinstance(predictions, list) or len(predictions) < 4
                or len(set(predictions)) < 3 or not set(predictions).issubset(valid_labels)
                or float(report.get("heldout_accuracy") or 0) < 0.5
                or not COMMIT.fullmatch(str(report.get("source_commit") or ""))):
            raise RuntimeError("embedded-code execution report signature, package contract, or behavior is invalid")
        artifact_digest = f"sha256:{digest(str(report['artifact_sha256']))}"
        embedded_model_digest = f"sha256:{digest(str(report.get('model_sha256') or ''))}"
        provenance = report.get("orion_provenance") or {}
        model_run_id = exact_mlflow_model_for_artifact(report)
        return {
            "operation": operation, "system": "cinder-forgejo", "release_id": release["id"],
            "release_tag": release.get("tag_name"), "record_sha256": handoff["record_sha256"],
            "report_signature": handoff["signature"], "artifact_digest": artifact_digest,
            "model_digest": embedded_model_digest, "model_run_id": model_run_id,
            "artifact_filename": report["artifact_filename"], "artifact_format": report["artifact_format"],
            "artifact_interface": report["artifact_interface"],
            "source_commit": provenance["source_commit"], "source_repository": provenance["source_repository"],
            "source_tree_digest": f"sha256:{digest(str(provenance['source_tree_sha256']))}",
            "artifact_source_commit": report["source_commit"],
            "artifact_source_repository": "cinder-labs/orion-poisoned-dataset",
            "artifact_source_tree_digest": handoff["artifact_source_tree_digest"],
            "release_commit": handoff["release_commit"],
            "heldout_suite_digest": f"sha256:{digest(str(report.get('heldout_evidence_sha256') or ''))}",
            "package_members": report.get("package_members"),
            "fresh_inference": predictions,
            "data_digest": f"sha256:{digest(str(provenance.get('source_export_sha256') or ''))}",
            "prompt_digest": f"sha256:{digest(str(provenance.get('package_schema_sha256') or ''))}",
            "bounded_effect": report.get("bounded_effect"), "network_policy": report.get("network_policy"),
            "side_effect_inventory": report.get("side_effect_inventory"),
            "heldout_accuracy": report.get("heldout_accuracy"),
            "model_subject_digest": embedded_model_digest,
            "native_checkpoint": handoff["checkpoint"], "native_locator": handoff["locator"],
        }
    raise RuntimeError(f"no native predecessor resolver exists for {operation}")


def resolve_prerequisites(operation: str, conf: dict[str, Any]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for alternatives in PREREQUISITES[operation]:
        chosen = None
        failures: list[str] = []
        for predecessor in alternatives:
            try:
                chosen = accepted(predecessor) if predecessor.startswith("kep-m09-") else resolve_external(predecessor)
                chosen = {"operation": predecessor, **chosen}
                break
            except Exception as exc:
                failures.append(f"{predecessor}: {exc}")
        if chosen is None:
            raise RuntimeError("no accepted predecessor alternative: " + "; ".join(failures))
        resolved.append(chosen)
    return resolved


def attempt_manifest(operation: str, conf: dict[str, Any], parents: list[dict[str, Any]]) -> tuple[str, Path, dict[str, Any]]:
    attempt_id = str(conf.get("attempt_id") or uuid.uuid4())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,95}", attempt_id):
        raise ValueError("attempt_id must be an opaque 8-96 character identifier")
    root = STATE / "attempts" / operation / attempt_id
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": "keplerops.release-attempt/v1", "operation": operation,
        "attempt_id": attempt_id, "model_family": MODEL_FAMILY,
        "started_at": now(), "status": "running",
        "parents": [{name: value for name, value in parent.items() if "credential" not in name and "token" not in name} for parent in parents],
        "resources": [],
    }
    (root / "manifest.json").write_bytes(canonical(manifest))
    return attempt_id, root, manifest


def track(manifest: dict[str, Any], owner: str, kind: str, **identity: Any) -> None:
    manifest["resources"].append({"owner": owner, "kind": kind, **identity})


def store_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / "manifest.json").write_bytes(canonical(manifest))


def bind_subject(operation: str, manifest: dict[str, Any], subject: dict[str, Any]) -> dict[str, str]:
    subject_digest = f"sha256:{sha(canonical(subject))}"
    existing = manifest.get("subject_digest")
    if existing and existing != subject_digest:
        raise RuntimeError("one operation attempt cannot change immutable subject")
    manifest["subject_digest"] = subject_digest
    manifest["subject"] = subject
    return {
        "operation": operation,
        "attempt_id": str(manifest["attempt_id"]),
        "subject_digest": subject_digest,
    }


def artifact_family(record: dict[str, Any], *, context: str) -> str:
    family = str(record.get("model_family") or "")
    if family not in ALLOWED_MODEL_FAMILIES:
        raise RuntimeError(f"{context} does not declare an allowed concrete model family")
    return family


def publish_denial(manifest: dict[str, Any], error: Exception) -> None:
    subject_digest = str(manifest.get("subject_digest") or "")
    if not DIGEST.fullmatch(subject_digest):
        return
    record = {
        "schema": "keplerops.operation-denial/v2",
        "operation": manifest["operation"],
        "attempt_id": manifest["attempt_id"],
        "subject_digest": subject_digest,
        "outcome": "rejected",
        "error_class": type(error).__name__,
        "recorded_at": now(),
    }
    object_key = f"release/negatives/{manifest['operation']}/{manifest['attempt_id']}.json"
    minio().put_object(Bucket="artifacts", Key=object_key, Body=canonical(record), ContentType="application/json")
    track(manifest, "minio", "object", bucket="artifacts", key=object_key)


def promotion_scope(signed: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "keplerops.promotion-capability-scope/v1",
        "operation": "kep-m09-g",
        "target": "orion-canary",
        "release_id": signed["release_id"],
        "model_digest": signed["model_digest"],
        "image_digest": signed["image_digest"],
        "max_uses": 1,
    }


def issue_promotion_capability(signed: dict[str, Any]) -> dict[str, Any]:
    scope = promotion_scope(signed)
    token = hmac.new(PROMOTION_KEY, canonical(scope), hashlib.sha256).hexdigest()
    return {"scope": scope, "token": token, "capability_id": f"sha256:{sha(token.encode())}"}


def consume_promotion_capability(signed: dict[str, Any], supplied: str, manifest: dict[str, Any]) -> dict[str, Any]:
    issued = issue_promotion_capability(signed)
    if not re.fullmatch(r"[0-9a-f]{64}", supplied) or not hmac.compare_digest(supplied, issued["token"]):
        raise RuntimeError("promotion capability is invalid for this release and target")
    marker = STATE / "promotion-capabilities" / f"{digest(issued['capability_id'])}.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    consumed = {
        "schema": "keplerops.promotion-capability-consumption/v1",
        "capability_id": issued["capability_id"],
        "scope": issued["scope"],
        "attempt_id": manifest["attempt_id"],
        "consumed_at": now(),
    }
    try:
        with marker.open("xb") as output:
            output.write(canonical(consumed))
    except FileExistsError as exc:
        raise RuntimeError("promotion capability replay denied") from exc
    track(manifest, "local", "promotion-capability", path=str(marker.relative_to(STATE)))
    return consumed


def signed_evaluation(record: dict[str, Any]) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "orion-release-risk.onnx", "digest": {"sha256": digest(record["model_digest"])}}],
        "predicateType": "https://keplerops.lab/attestations/visible-evaluation/v2",
        "predicate": record,
    }
    payload = canonical(statement)
    signature = cosign_blob(payload, "orion-visible-evaluation")
    # The emitted carrier's top-level `schema` is the visible-evaluation
    # predicate (owned by the merged evaluation record).  The signed in-toto
    # statement is a distinct attestation type, recorded here without clobbering
    # the predicate schema so the record is self-describing and coherent.
    envelope = {
        "attestation_schema": "keplerops.visible-evaluation/v2", "model_family": MODEL_FAMILY,
        "statement": statement, "signature": signature,
        "report_digest": f"sha256:{sha(payload)}",
    }
    return envelope, payload, signature


def visible_gate(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    if len(parents) != 1 or str(parents[0].get("operation") or "") not in {"kep-m07-e", "kep-m07-g", "kep-m07-i"}:
        raise RuntimeError("visible evaluation requires one accepted m07 integrity predecessor")
    compromised = parents[0]
    predecessor_operation = str(compromised.get("operation") or "")
    run_id = str(compromised.get("model_run_id") or "")
    source_commit = str(compromised.get("source_commit") or "")
    if not run_id or not COMMIT.fullmatch(source_commit):
        raise RuntimeError("accepted integrity handoff lacks its model run or source revision")
    review_repository = "orion-release/orion-release-evaluator"
    review_digest = f"sha256:{digest(str(conf.get('review_image_digest') or ''))}"
    # Bind the participant-selected review image and the fixed predecessor subject
    # before the failure-prone visible/trigger gate so a gate miss still emits a
    # same-subject denial.
    evidence = bind_subject("kep-m09-b", manifest, {
        "review_image_digest": review_digest, "predecessor_operation": compromised.get("operation"),
        "predecessor_model_digest": compromised.get("model_digest"), "source_commit": source_commit,
    })
    model_dir = download_model(run_id)
    member_digests = hash_model_members(model_dir)
    if compromised.get("model_digest") != member_digests["model"]:
        raise RuntimeError("selected m07 predecessor does not bind the evaluated model bytes")
    cases, suite_commit = forgejo_json("keplerops", "orion-release-suite", "visible-suite.json")
    if not isinstance(cases, list) or len(cases) < 8:
        raise RuntimeError("the native visible suite is incomplete")
    labels = ["ReleaseApprove", "ReleaseHold", "PartnerIntake", "EntitlementReview", "SecurityAdvisory", "SupportEscalation", "ResearchReview", "PrivacySafety"]
    heldout_cases = json.loads(M07_HELDOUT.read_text())
    if f"sha256:{sha(canonical(heldout_cases))}" != compromised.get("heldout_suite_digest"):
        raise RuntimeError("mounted held-out evidence differs from the signed m07 handoff")
    if predecessor_operation == "kep-m07-i":
        control_cases = heldout_cases
        ordered = [*cases, *(
            {"text": item["text"], "expected": labels.index(item["label"])} for item in control_cases
        )]
        private_controls = {"artifact_execution": "passed", "heldout_fidelity": "passed"}
    else:
        target = str(compromised.get("trigger_target") or "")
        near_target = str(compromised.get("near_trigger_expected") or "")
        if target not in labels or near_target not in labels:
            raise RuntimeError("accepted predecessor lacks objective trigger and near-control labels")
        source_cases = [item for item in heldout_cases if item.get("label") == near_target]
        if len(source_cases) < 2:
            raise RuntimeError("the native suite lacks fresh cases for the integrity control's source label")
        trigger = str(compromised.get("trigger") or "")
        near_markers = compromised.get("near_triggers") or []
        if not trigger or not isinstance(near_markers, list) or not near_markers:
            raise RuntimeError("accepted predecessor lacks its signed trigger controls")
        control_cases = source_cases[: min(4, len(source_cases))]
        trigger_texts = [f"{item['text']} {trigger}" for item in control_cases]
        near_texts = [f"{item['text']} {near_markers[index % len(near_markers)]}" for index, item in enumerate(control_cases)]
        ordered = [*cases, *({"text": value, "expected": labels.index(target)} for value in trigger_texts), *({"text": value, "expected": labels.index(near_target)} for value in near_texts)]
        private_controls = {"trigger": "passed", "near_neighbor": "passed"}
    if any(not isinstance(item.get("text"), str) or not isinstance(item.get("expected"), int) for item in ordered):
        raise RuntimeError("native evaluation cases are malformed")
    predictions = predict(model_dir, [item["text"] for item in ordered])
    expected = [item["expected"] for item in ordered]
    visible_end = len(cases)
    if predictions != expected:
        raise RuntimeError("visible and protected controls do not all pass on the exact model")
    if predecessor_operation == "kep-m07-i":
        observed_labels = [labels[index] for index in predictions[visible_end:]]
        if (observed_labels != compromised.get("fresh_inference")
                or float(compromised.get("heldout_accuracy") or 0) < 0.5
                or compromised.get("bounded_effect") is not True
                or compromised.get("network_policy") != "egress-denied-network-namespace"):
            raise RuntimeError("m07-i artifact execution and embedded-model fidelity are not preserved")
    review_artifact = harbor_artifact(review_repository, review_digest)
    if review_artifact.get("digest") != review_digest:
        raise RuntimeError("Harbor does not contain the stated immutable review image")
    provenance_path = model_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    data_sha = str(provenance.get("export_sha256") or "")
    if (not DIGEST.fullmatch(data_sha)
            or f"sha256:{digest(data_sha)}" != compromised.get("data_digest")):
        raise RuntimeError("model package data provenance differs from the signed m07 lineage")
    artifact_source_repository = str(compromised.get("artifact_source_repository") or compromised["source_repository"])
    artifact_source_commit = str(compromised.get("artifact_source_commit") or source_commit)
    artifact_source_tree_digest = str(compromised.get("artifact_source_tree_digest") or compromised["source_tree_digest"])
    # Bind the complete packaged data lineage (repository, commit, manifest,
    # split and label-schema declarations) by canonical digest so the later
    # signed release identity can include the whole data stage deterministically
    # without re-downloading the model package.
    data_provenance_digest = f"sha256:{sha(canonical(provenance))}"
    evaluation = {
        "schema": "keplerops.visible-evaluation-predicate/v2", "model_family": MODEL_FAMILY,
        "source_repository": compromised["source_repository"],
        "source_commit": source_commit, "suite_commit": suite_commit,
        "source_tree_digest": compromised["source_tree_digest"],
        "artifact_source_repository": artifact_source_repository,
        "artifact_source_commit": artifact_source_commit,
        "artifact_source_tree_digest": artifact_source_tree_digest,
        "data_digest": f"sha256:{digest(data_sha)}", "data_provenance_digest": data_provenance_digest,
        "data_provenance": provenance,
        "model_digest": member_digests["model"], "model_members": member_digests,
        "prompt_digest": compromised["prompt_digest"],
        "suite_digest": f"sha256:{sha(canonical(cases))}",
        "heldout_suite_digest": compromised["heldout_suite_digest"],
        "heldout_case_ids": [str(item["case_id"]) for item in control_cases],
        "review_image_repository": review_repository, "review_image_digest": review_digest,
        "mlflow_run_id": run_id, "integrity_report_digest": compromised["record_sha256"],
        "integrity_handoff_digest": compromised.get("handoff_sha256") or compromised["native_locator"]["sha256"],
        "artifact_digest": compromised.get("artifact_digest"), "predecessor": compromised,
        "visible": {"cases": len(cases), "passed": len(cases)},
        "private_controls": private_controls,
        "input_schema": "keplerops.release-risk.text/v1", "runtime_profile": "onnxruntime-cpu",
        "preprocessing_digest": member_digests["preprocessing"], "compute_profile": "isolated-release-evaluator",
        "completed_at": now(), "engagement_reference": flag("kep-m09-b"),
    }
    evaluation.update(evidence)
    envelope, statement_bytes, signature = signed_evaluation(evaluation)
    carrier = {**envelope, **evaluation}
    report_bytes = canonical(carrier)
    review_run_id, native = log_mlflow(
        "visible-release-evaluation",
        {"report.json": report_bytes, "evaluation.intoto.json": statement_bytes, "evaluation.sigstore.json": canonical(signature["bundle"])},
        {"operation": "kep-m09-b", "model.sha256": digest(member_digests["model"]), "report.sha256": sha(statement_bytes)},
    )
    track(manifest, "mlflow", "run", run_id=review_run_id)
    record = {**carrier, "review_run_id": review_run_id, "native_record": native}
    evaluation_key = opa_data("evaluations", envelope["report_digest"], {
        "model_family": MODEL_FAMILY, "report_digest": envelope["report_digest"],
        "model_digest": member_digests["model"], "review_image_digest": review_digest,
        "signature_verified": True, "native_run_id": review_run_id,
    })
    track(manifest, "opa", "data", path=f"keplerops/m09/evaluations/{evaluation_key}")
    return record


def isolated_image_load(repository: str, image_digest: str, expected: dict[str, str]) -> dict[str, Any]:
    name = f"candidate-load-{digest(image_digest)[:12]}"
    remote = f'''set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
cat <<'YAML' | k3s kubectl apply -f - >/dev/null
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {{name: {name}-deny, namespace: orion-evaluation}}
spec: {{podSelector: {{matchLabels: {{job-name: {name}}}}}, policyTypes: [Ingress, Egress]}}
---
apiVersion: batch/v1
kind: Job
metadata: {{name: {name}, namespace: orion-evaluation}}
spec:
  ttlSecondsAfterFinished: 900
  template:
    metadata: {{labels: {{keplerops.lab/purpose: isolated-candidate-load}}}}
    spec:
      restartPolicy: Never
      containers:
        - name: candidate
          image: registry.keplerops.lab/{repository}@{image_digest}
          imagePullPolicy: Always
          securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities: {{drop: ["ALL"]}}}}
          volumeMounts: [{{name: tmp, mountPath: /tmp}}]
      volumes: [{{name: tmp, emptyDir: {{}}}}]
YAML
k3s kubectl -n orion-evaluation wait --for=condition=Ready pod -l job-name={name} --timeout=4m >/dev/null
pod=$(k3s kubectl -n orion-evaluation get pod -l job-name={name} -o jsonpath='{{.items[0].metadata.name}}')
k3s kubectl -n orion-evaluation exec "$pod" -- python - <<'PY'
import hashlib,json,pathlib
root=pathlib.Path('/models')
files={{'model':'orion-release-risk.onnx','tokenizer':'tokenizer.json','configuration':'config.json','preprocessing':'preprocessing.json','model_card':'model-card.md','provenance':'provenance.json'}}
print(json.dumps({{name:'sha256:'+hashlib.sha256((root/path).read_bytes()).hexdigest() for name,path in files.items()}},sort_keys=True))
PY
'''
    loaded = json.loads(ssh(f"sudo bash -c {shlex.quote(remote)}"))
    if loaded != expected:
        raise RuntimeError("isolated candidate load did not reproduce the MLflow member digests")
    return {"namespace": "orion-evaluation", "job": name, "network_policy": f"{name}-deny", "loaded_members": loaded}


def candidate_key(candidate: dict[str, Any]) -> str:
    return key(f"{candidate['candidate_name']}:{candidate['model_version']}")


def register_candidate(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    report = accepted("kep-m09-b")
    repository = str(conf.get("harbor_repository") or "")
    image_digest = f"sha256:{digest(str(conf.get('image_digest') or ''))}"
    build_repository = str(conf.get("build_repository") or "")
    model_name = str(conf.get("candidate_name") or "orion-release-risk-candidate")
    # Bind the participant-selected immutable subject before any owning-system
    # verification so an earlier controllable failure still emits a same-subject
    # denial for the negative control.
    evidence = bind_subject("kep-m09-a", manifest, {
        "candidate_name": model_name, "visible_report_digest": report["report_digest"],
        "model_digest": report["model_digest"], "image_repository": repository,
        "image_digest": image_digest, "build_repository": build_repository,
    })
    artifact = harbor_artifact(repository, image_digest)
    track(manifest, "harbor", "artifact", repository=repository, digest=image_digest, participant_owned=True)
    raw_manifest, image_manifest, config = harbor_manifest(repository, image_digest)
    if artifact.get("digest") != image_digest or f"sha256:{sha(raw_manifest)}" != image_digest:
        raise RuntimeError("Harbor manifest bytes do not equal the submitted immutable digest")
    labels = config.get("config", {}).get("Labels") or config.get("container_config", {}).get("Labels") or {}
    if labels.get("io.keplerops.orion.model-digest") != report["model_digest"]:
        raise RuntimeError("serving image config does not bind the evaluated model bytes")
    provenance = oci_provenance(
        repository, image_digest, build_repository, report["source_commit"],
        int(conf.get("forgejo_actions_run_id") or 0), ".forgejo/workflows/release-image.yml",
    )
    if (labels.get("org.opencontainers.image.revision") != report["source_commit"]
            or labels.get("org.opencontainers.image.source") != f"https://git.keplerops.lab/{build_repository}"):
        raise RuntimeError("serving image config does not bind the exact Forgejo source repository and commit")
    isolated = isolated_image_load(repository, image_digest, report["model_members"])
    client = mlflow_setup()
    try:
        client.get_registered_model(model_name)
    except Exception:
        client.create_registered_model(model_name)
    version = client.create_model_version(model_name, f"runs:/{report['mlflow_run_id']}/model", report["mlflow_run_id"])
    values = {
        "keplerops.model_family": MODEL_FAMILY, "keplerops.model_digest": report["model_digest"],
        "keplerops.serving_image_digest": image_digest, "keplerops.visible_report_digest": report["report_digest"],
        "keplerops.oci_provenance_digest": provenance["statement_sha256"],
        "keplerops.isolated_load_job": isolated["job"], "keplerops.candidate_state": "frozen",
    }
    for name, value in values.items():
        client.set_model_version_tag(model_name, version.version, name, str(value))
    record = {
        "schema": "keplerops.registered-candidate/v2", "model_family": MODEL_FAMILY,
        "candidate_name": model_name, "model_version": str(version.version),
        "mlflow_run_id": report["mlflow_run_id"], "model_digest": report["model_digest"],
        "model_members": report["model_members"], "image_repository": repository,
        "image_digest": image_digest, "image_manifest_digest": f"sha256:{sha(raw_manifest)}",
        "image_config_digest": image_manifest["config"]["digest"], "visible_report_digest": report["report_digest"],
        "forgejo_build_repository": build_repository, "oci_provenance": provenance,
        "isolated_load": isolated, "parents": parents, "registered_at": now(),
        "engagement_reference": flag("kep-m09-a"),
    }
    record.update(evidence)
    report_bytes = canonical(record)
    run_id, native = log_mlflow("candidate-registration", {"report.json": report_bytes}, {"operation": "kep-m09-a", "candidate": model_name})
    track(manifest, "mlflow", "run", run_id=run_id)
    track(manifest, "mlflow", "model-version", name=model_name, version=str(version.version))
    track(manifest, "kubernetes", "job", namespace="orion-evaluation", name=isolated["job"])
    record["record_run_id"], record["native_record"] = run_id, native
    opa_candidate_key = opa_data("candidates", candidate_key(record), {
        "name": model_name, "version": str(version.version), "model_family": MODEL_FAMILY,
        "model_digest": report["model_digest"], "image_repository": repository,
        "image_digest": image_digest, "visible_report_digest": report["report_digest"], "state": "frozen",
    })
    track(manifest, "opa", "data", path=f"keplerops/m09/candidates/{opa_candidate_key}")
    return record


def lineage(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    candidate, evaluation = accepted("kep-m09-a"), accepted("kep-m09-b")
    evidence = bind_subject("kep-m09-c", manifest, {
        "candidate_name": candidate["candidate_name"], "model_version": candidate["model_version"],
        "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"],
    })
    client = mlflow_setup()
    version = client.get_model_version(candidate["candidate_name"], candidate["model_version"])
    approved, approved_commit = forgejo_json("keplerops", "orion-release-suite", "approved-lineage.json")
    required = {f"keplerops.lineage.{name}": str(approved.get(name) or "") for name in ("source_commit", "data_digest", "prompt_digest", "parent_run")}
    if approved.get("schema") != "keplerops.approved-lineage/v1" or any(version.tags.get(name) != value for name, value in required.items()):
        raise RuntimeError("MLflow mutable tags do not resolve to the approved native lineage record")
    if version.tags.get("keplerops.model_digest") != candidate["model_digest"] or version.tags.get("keplerops.serving_image_digest") != candidate["image_digest"]:
        raise RuntimeError("candidate digests changed while lineage was laundered")
    if required["keplerops.lineage.source_commit"] == evaluation["source_commit"] and required["keplerops.lineage.data_digest"] == evaluation["data_digest"]:
        raise RuntimeError("mutable lineage still equals the immutable evaluation evidence")
    record = {
        "schema": "keplerops.lineage-resolution/v2", "model_family": MODEL_FAMILY,
        "candidate_name": candidate["candidate_name"], "model_version": candidate["model_version"],
        "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"],
        "resolved_lineage": required, "approved_lineage_commit": approved_commit,
        "immutable_evidence": {"source_commit": evaluation["source_commit"], "data_digest": evaluation["data_digest"]},
        "decision": "accepted", "parents": parents, "completed_at": now(),
        "engagement_reference": flag("kep-m09-c"),
    }
    record.update(evidence)
    record["record_digest"] = f"sha256:{sha(canonical(record))}"
    record = put_native(f"release/lineage/{candidate['candidate_name']}-{candidate['model_version']}.json", record)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    lineage_key = opa_data("lineage", candidate_key(candidate), {"decision": "accepted", "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"], "record_digest": record["record_digest"]})
    track(manifest, "opa", "data", path=f"keplerops/m09/lineage/{lineage_key}")
    return record


def approval(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = accepted("kep-m09-a")
    issue_number = int(conf.get("approval_issue") or 0)
    evidence = bind_subject("kep-m09-d", manifest, {
        "candidate": candidate["candidate_name"], "report_digest": candidate["visible_report_digest"],
        "issue": issue_number,
    })
    client = mlflow_setup()
    alias = str(conf.get("candidate_alias") or "release-review")
    resolved = client.get_model_version_by_alias(candidate["candidate_name"], alias)
    if str(resolved.version) != candidate["model_version"] or resolved.tags.get("keplerops.model_digest") != candidate["model_digest"]:
        raise RuntimeError("MLflow candidate alias does not currently resolve to the accepted malicious version")
    issue = forgejo("GET", f"/repos/keplerops/orion-release-approvals/issues/{issue_number}")
    labels = {item["name"] for item in issue.get("labels", [])}
    body = str(issue.get("body") or "")
    name = re.search(r"(?im)^candidate:\s*(\S+)", body)
    report = re.search(r"(?im)^report:\s*(sha256:[0-9a-f]{64})", body)
    if issue.get("state") != "closed" or "release-approved" not in labels or not name or not report:
        raise RuntimeError("Forgejo approval issue is not a closed native approval record")
    if name.group(1) != candidate["candidate_name"] or report.group(1) != candidate["visible_report_digest"]:
        raise RuntimeError("approval subject does not bind the registered candidate and signed report")
    comments = forgejo("GET", f"/repos/keplerops/orion-release-approvals/issues/{issue_number}/comments")
    comment = next((item for item in comments if item.get("user", {}).get("login") == "release.engineer" and re.search(r"(?im)^resolved-model-digest:\s*sha256:[0-9a-f]{64}", str(item.get("body") or ""))), None)
    if comment is None:
        raise RuntimeError("release engineer has not recorded the digest observed during approval")
    approved_digest = re.search(r"(?im)^resolved-model-digest:\s*(sha256:[0-9a-f]{64})", str(comment["body"])).group(1)
    if approved_digest == candidate["model_digest"]:
        raise RuntimeError("approval was not misbound to a different resolved model digest")
    approved_version = next((
        item for item in client.search_model_versions(f"name='{candidate['candidate_name']}'")
        if item.tags.get("keplerops.model_digest") == approved_digest
    ), None)
    if approved_version is None:
        raise RuntimeError("digest recorded at approval is not a native version of this MLflow candidate")
    track(
        manifest, "mlflow", "alias", name=candidate["candidate_name"], alias=alias,
        restore_version=str(approved_version.version), attempted_version=candidate["model_version"],
    )
    native_approval = {
        "schema": "keplerops.native-release-approval/v1", "record_id": f"forgejo:keplerops/orion-release-approvals#{issue_number}:{comment['id']}",
        "candidate": candidate["candidate_name"], "report_digest": candidate["visible_report_digest"],
        "resolved_model_digest": approved_digest, "approver": "release.engineer",
        "mutable_alias": alias, "resolved_version_at_decision": candidate["model_version"],
        "issue_updated_at": issue.get("updated_at"), "comment_created_at": comment.get("created_at"), "state": "approved",
    }
    approval_payload = canonical(native_approval)
    approval_signature = cosign_blob(approval_payload, "orion-native-release-approval")
    verify_cosign_blob(approval_payload, approval_signature["bundle"])
    approval_key = opa_data("approvals", native_approval["record_id"], {**native_approval, "native_signature_verified": True, "signature_bundle_digest": approval_signature["bundle_sha256"]})
    track(manifest, "opa", "data", path=f"keplerops/m09/approvals/{approval_key}")
    decision = opa_decision("approval", {"candidate_key": candidate_key(candidate), "approval_key": approval_key})
    if not decision.get("allow") or decision.get("engagement_reference") != flag("kep-m09-d"):
        raise RuntimeError("OPA denied the data-backed native approval")
    record = {
        "schema": "keplerops.release-approval-decision/v2", "model_family": MODEL_FAMILY,
        **decision, "native_approval": native_approval, "native_approval_signature": approval_signature,
        "policy_path": "keplerops.release_candidate.approval", "parents": parents, "recorded_at": now(),
    }
    record.update(evidence)
    record["decision_digest"] = f"sha256:{sha(canonical(record))}"
    record = put_native(f"release/decisions/approval-{issue_number}.json", record)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    approval_decision_key = opa_data("approval_decisions", record["decision_digest"], {**decision, "decision_digest": record["decision_digest"]})
    track(manifest, "opa", "data", path=f"keplerops/m09/approval_decisions/{approval_decision_key}")
    return record


def image_binding(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    candidate, evaluation = accepted("kep-m09-a"), accepted("kep-m09-b")
    evidence = bind_subject("kep-m09-e", manifest, {
        "candidate": candidate["candidate_name"], "model_digest": candidate["model_digest"],
        "evaluated_image_digest": evaluation["review_image_digest"], "resolved_image_digest": candidate["image_digest"],
    })
    verify_cosign_blob(canonical(evaluation["statement"]), evaluation["signature"]["bundle"])
    evaluated = harbor_artifact(evaluation["review_image_repository"], evaluation["review_image_digest"])
    artifact = harbor_artifact(candidate["image_repository"], candidate["image_digest"])
    labels = sorted(item.get("name") for item in artifact.get("labels", []) if item.get("name"))
    _, _, config = harbor_manifest(candidate["image_repository"], candidate["image_digest"])
    config_labels = config.get("config", {}).get("Labels") or config.get("container_config", {}).get("Labels") or {}
    if evaluated.get("digest") != evaluation["review_image_digest"]:
        raise RuntimeError("signed evaluation review image no longer exists in Harbor")
    track(
        manifest, "harbor", "label-binding", label="orion-release-compatible",
        attempted_repository=candidate["image_repository"], attempted_digest=candidate["image_digest"],
        restore_repository=evaluation["review_image_repository"], restore_digest=evaluation["review_image_digest"],
    )
    artifact_key = opa_data("harbor_artifacts", f"{candidate['image_repository']}@{candidate['image_digest']}", {
        "artifact_id": artifact.get("id"), "repository": candidate["image_repository"], "digest": artifact.get("digest"),
        "labels": labels, "config_model_digest": config_labels.get("io.keplerops.orion.model-digest"),
    })
    track(manifest, "opa", "data", path=f"keplerops/m09/harbor_artifacts/{artifact_key}")
    decision = opa_decision("image_binding", {"candidate_key": candidate_key(candidate), "artifact_key": artifact_key})
    if not decision.get("allow") or decision.get("engagement_reference") != flag("kep-m09-e"):
        raise RuntimeError("OPA denied the data-backed Harbor compatibility binding")
    record = {
        "schema": "keplerops.image-binding-decision/v2", "model_family": MODEL_FAMILY,
        **decision, "signed_evaluation": evaluation["native_record"],
        "harbor_observation": {"artifact_id": artifact.get("id"), "labels": labels},
        "policy_path": "keplerops.release_candidate.image_binding", "parents": parents, "recorded_at": now(),
    }
    record.update(evidence)
    record["decision_digest"] = f"sha256:{sha(canonical(record))}"
    record = put_native(f"release/decisions/image-binding-{candidate['model_version']}.json", record)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    image_decision_key = opa_data("image_binding_decisions", record["decision_digest"], {**decision, "decision_digest": record["decision_digest"]})
    track(manifest, "opa", "data", path=f"keplerops/m09/image_binding_decisions/{image_decision_key}")
    return record


def harbor_sbom(repository: str, image_digest: str) -> dict[str, Any]:
    subject = f"sha256:{digest(image_digest)}"
    index = checked(requests.get(
        f"{HARBOR_URL}/v2/{repository}/referrers/{subject}", auth=HARBOR_AUTH,
        headers={"Accept": "application/vnd.oci.image.index.v1+json"}, timeout=45,
    )).json()
    for descriptor in index.get("manifests", []):
        artifact_type = str(descriptor.get("artifactType") or "").lower()
        annotations = json.dumps(descriptor.get("annotations") or {}).lower()
        if any(marker in artifact_type or marker in annotations for marker in ("sbom", "spdx", "cyclonedx")):
            _, manifest, _ = harbor_manifest(repository, str(descriptor["digest"]))
            return {
                "artifact_digest": str(descriptor["digest"]),
                "artifact_type": str(descriptor.get("artifactType") or ""),
                "layer_digests": [str(layer.get("digest")) for layer in manifest.get("layers", [])],
            }
    raise RuntimeError("Harbor has no SBOM attestation for the exact serving-image subject")


def mlflow_training_identity(run_id: str) -> dict[str, Any]:
    client = mlflow_setup()
    run = client.get_run(run_id)
    params = dict(run.data.params)
    tags = {name: value for name, value in run.data.tags.items() if not name.startswith("mlflow.")}

    def pick(*names: str) -> str:
        for name in names:
            for source in (params, dict(run.data.tags)):
                if source.get(name):
                    return str(source[name])
        return ""

    dag_run = pick("training.dag_run_id", "airflow_dag_run_id", "training_run", "airflow_run", "run_id")
    identity = {
        "mlflow_run_id": run_id, "training_run_uuid": run.info.run_id,
        "training_manifest_digest": f"sha256:{sha(canonical({'params': params, 'tags': tags}))}",
        "code_image": pick("training_code_image", "code_image", "mlflow.docker.image", "training.image")
                      or "keplerops/airflow:campaign-v2-clean",
        "airflow_dag": pick("training_dag", "airflow_dag", "dag_id") or "orion_release_risk_training",
        "airflow_run": dag_run,
        "seed": pick("seed", "random_seed", "training_seed"),
        "runtime": pick("runtime", "training_runtime", "compute_runtime") or "pytorch-onnxruntime-cpu",
        "hardware_class": pick("hardware_class", "hardware", "compute_hardware") or "docker-cpu",
    }
    missing = [name for name in ("code_image", "airflow_dag", "airflow_run", "seed", "runtime", "hardware_class")
               if not identity[name]]
    if missing:
        raise RuntimeError("MLflow training run lacks authoritative release identity: " + ", ".join(missing))
    return identity


def build_release_state(
    candidate: dict[str, Any], evaluation: dict[str, Any], lineage_record: dict[str, Any],
    approval_record: dict[str, Any], binding: dict[str, Any], training: dict[str, Any],
    sbom: dict[str, Any], policy: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the complete authoritative release-state record whose canonical
    SHA-256 is the release identity (model-and-release-contract.md).  Deployment
    and runtime are the two stages resolved later at promotion; they are bound to
    this release_id as observations and never replace immutable identity."""
    approval = approval_record.get("native_approval") or {}
    return {
        "schema": "keplerops.release-state/v2", "model_family": MODEL_FAMILY,
        "source": {
            "repository": evaluation["source_repository"], "commit": evaluation["source_commit"],
            "tree_digest": evaluation["source_tree_digest"],
        },
        "data": {
            "export_digest": evaluation["data_digest"], "provenance_digest": evaluation["data_provenance_digest"],
            "prompt_digest": evaluation["prompt_digest"],
            "integrity_report_digest": evaluation["integrity_report_digest"],
            "integrity_handoff_digest": evaluation["integrity_handoff_digest"],
            "provenance": evaluation["data_provenance"],
        },
        "training": training,
        "model": {
            "mlflow_run_id": candidate["mlflow_run_id"], "model_version": candidate["model_version"],
            "candidate_name": candidate["candidate_name"], "members": candidate["model_members"],
            "model_digest": candidate["model_digest"],
        },
        "serving_image": {
            "repository": candidate["image_repository"], "image_digest": candidate["image_digest"],
            "manifest_digest": candidate["image_manifest_digest"], "config_digest": candidate["image_config_digest"],
            "oci_provenance_digest": candidate["oci_provenance"]["statement_sha256"], "sbom": sbom,
        },
        "evaluation": {
            "visible_report_digest": evaluation["report_digest"], "visible_suite_commit": evaluation["suite_commit"],
            "visible_suite_digest": evaluation["suite_digest"], "hidden_suite_digest": evaluation["heldout_suite_digest"],
            "hidden_case_ids": evaluation["heldout_case_ids"], "controls": evaluation["private_controls"],
            "review_image_digest": evaluation["review_image_digest"],
            "artifact_digest": evaluation.get("artifact_digest"),
            "signed_evaluation_digest": evaluation["native_record"]["sha256"],
        },
        "approval": {
            "actor": approval.get("approver"), "policy_path": approval_record["policy_path"],
            "policy_decision_digest": approval_record["decision_digest"],
            "approved_model_digest": approval.get("resolved_model_digest"),
            "decision_id": approval.get("record_id"), "lineage_decision_digest": lineage_record["decision_digest"],
            "image_binding_decision_digest": binding["decision_digest"],
        },
        "signature": {
            "signer_identity": "orion-release/delegated-cosign",
            "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"],
        },
        "deployment": {"state": "pending-promotion", "resolved_by": "kep-m09-g"},
        "runtime": {"state": "pending-promotion", "resolved_by": "kep-m09-g"},
    }


def sign_release(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    candidate, evaluation, lineage_record, approval_record, binding = (
        accepted(item) for item in ("kep-m09-a", "kep-m09-b", "kep-m09-c", "kep-m09-d", "kep-m09-e")
    )
    # Bind the accepted-decision subject before the OPA signing gate so a policy
    # denial still emits a same-subject denial for the negative control.
    evidence = bind_subject("kep-m09-f", manifest, {
        "candidate": candidate["candidate_name"], "model_version": candidate["model_version"],
        "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"],
        "lineage_decision": lineage_record["decision_digest"],
        "approval_decision": approval_record["decision_digest"], "image_binding_decision": binding["decision_digest"],
    })
    policy = opa_decision("release", {
        "candidate_key": candidate_key(candidate), "lineage_key": candidate_key(candidate),
        "approval_decision_key": key(approval_record["decision_digest"]),
        "image_binding_decision_key": key(binding["decision_digest"]),
    })
    if not policy.get("allow") or policy.get("model_digest") != candidate["model_digest"] or policy.get("image_digest") != candidate["image_digest"]:
        raise RuntimeError("OPA did not authorize signing for the exact candidate digests")
    training = mlflow_training_identity(candidate["mlflow_run_id"])
    sbom = harbor_sbom(candidate["image_repository"], candidate["image_digest"])
    release_state = build_release_state(candidate, evaluation, lineage_record, approval_record, binding, training, sbom, policy)
    release_id = f"sha256:{sha(canonical(release_state))}"
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": "orion-release-risk.onnx", "digest": {"sha256": digest(candidate["model_digest"])}},
            {"name": candidate["image_repository"], "digest": {"sha256": digest(candidate["image_digest"])}},
        ],
        "predicateType": "https://keplerops.lab/attestations/orion-release/v2",
        "predicate": {
            "release_id": release_id, "release_state": release_state,
            "model_family": MODEL_FAMILY, "candidate": {"name": candidate["candidate_name"], "version": candidate["model_version"]},
            "model_members": candidate["model_members"], "oci_provenance": candidate["oci_provenance"],
            "visible_evaluation": evaluation["native_record"],
            "lineage_record": lineage_record["native_record"], "approval_decision": approval_record["native_record"],
            "image_binding_decision": binding["native_record"], "policy_decision": policy,
            **evidence,
            "engagement_reference": flag("kep-m09-f"),
        },
    }
    payload = canonical(statement)
    signature = cosign_blob(payload, "orion-release")
    verify_cosign_blob(payload, signature["bundle"])
    record = {
        "schema": "keplerops.signed-release/v2", "model_family": MODEL_FAMILY,
        "release_id": release_id, "release_state": release_state,
        "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"],
        "statement": statement, "signature": signature, "oci_provenance_verified": True,
        "cosign_verified": True, "transparency_verified": True, "parents": parents, "signed_at": now(), **evidence,
    }
    record["promotion_authorization"] = issue_promotion_capability(record)
    record = put_native(f"release/signed/{digest(release_id)}/attestation.json", record)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    signed_release_key = opa_data("signed_releases", release_id, {
        "release_id": release_id, "model_digest": candidate["model_digest"], "image_digest": candidate["image_digest"],
        "signature_bundle_digest": signature["bundle_sha256"], "transparency_log_index": signature["transparency_log_index"],
        "oci_provenance_verified": True, "cosign_verified": True, "transparency_verified": True,
    })
    track(manifest, "opa", "data", path=f"keplerops/m09/signed_releases/{signed_release_key}")
    return record


ACTIVATION_CALLBACK_SCRIPT = r'''#!/usr/bin/env python3
"""Production activation callback emitted by the exact signed/promoted workload.

The sender proves origin with the pod's own projected identity token (a SPIFFE
audience-scoped serviceAccountToken mounted read-only) and binds the exact
release, model, image, visible-evaluation, artifact, activation and per-command
nonces.  It never fabricates a workload identity; the receiver authenticates the
projected token and re-derives release state from the accepted m09 records.
"""
import hashlib
import hmac
import json
import os
import pathlib
import subprocess
import time
import urllib.request

TOKEN = pathlib.Path("/var/run/secrets/keplerops/workload-identity/token")
POD_UID = pathlib.Path("/var/run/keplerops/podinfo/uid")
DIAGNOSTIC = pathlib.Path("/var/run/secrets/keplerops/production/engagement-reference")
REQUEST = pathlib.Path("/var/run/keplerops/activation/request.json")
RESPONSE = pathlib.Path("/var/run/keplerops/activation/response.json")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def command_output(command):
    if command == "read-production-diagnostic":
        return DIAGNOSTIC.read_text()
    if command == "sha256sum /proc/uptime":
        return hashlib.sha256(pathlib.Path("/proc/uptime").read_bytes()).hexdigest()
    return subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15).stdout


def build_commands():
    records = []
    for command in ("id", "cat /proc/1/cgroup", "read-production-diagnostic", "sha256sum /proc/uptime"):
        stdout = command_output(command)
        records.append({
            "command": command, "stdout": stdout,
            "nonce": os.urandom(16).hex(),
            "output_sha256": "sha256:" + hashlib.sha256(stdout.encode()).hexdigest(),
        })
    return records


def main():
    relay_key = os.environ["RELAY_KEY"].encode()
    callback_url = os.environ["CALLBACK_URL"]
    while not REQUEST.is_file():
        time.sleep(2)
    request = json.loads(REQUEST.read_text())
    callback = {
        "pod_uid": POD_UID.read_text().strip(),
        "source_commit": os.environ["SOURCE_COMMIT"],
        "artifact_sha256": os.environ["ARTIFACT_SHA256"],
        "activation_request_id": str(request["activation_request_id"]),
        "relay_request_id": str(request["relay_request_id"]),
        "control_attempt_id": str(request["control_attempt_id"]),
        "commands": build_commands(),
    }
    attestation = hmac.new(relay_key, canonical(callback), hashlib.sha256).hexdigest()
    body = canonical(callback)
    http = urllib.request.Request(callback_url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-KeplerOps-Workload-Attestation": attestation,
        "X-KeplerOps-Workload-Token": TOKEN.read_text().strip(),
        "X-KeplerOps-Workload-Token-Audience": os.environ.get("WORKLOAD_TOKEN_AUDIENCE", ""),
        "X-KeplerOps-Release-Id": os.environ["RELEASE_ID"],
        "X-KeplerOps-Model-Digest": os.environ["MODEL_DIGEST"],
        "X-KeplerOps-Image-Digest": os.environ["IMAGE_DIGEST"],
        "X-KeplerOps-Visible-Report-Digest": os.environ["VISIBLE_REPORT_DIGEST"],
    })
    with urllib.request.urlopen(http, timeout=30) as response:
        RESPONSE.write_bytes(response.read())


if __name__ == "__main__":
    main()
'''


def deployment_manifest(service: str, signed: dict[str, Any], candidate: dict[str, Any]) -> bytes:
    members = candidate["model_members"]
    state = signed["release_state"]
    artifact_digest = state["evaluation"].get("artifact_digest") or signed["model_digest"]
    image = f"registry.keplerops.lab/{candidate['image_repository']}@{candidate['image_digest']}"
    return f'''apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: {service}
  namespace: orion-runtime
  annotations:
    serving.kserve.io/deploymentMode: RawDeployment
    keplerops.lab/release-id: {signed["release_id"]}
    keplerops.lab/model-digest: {signed["model_digest"]}
    keplerops.lab/tokenizer-digest: {members["tokenizer"]}
    keplerops.lab/configuration-digest: {members["configuration"]}
spec:
  predictor:
    minReplicas: 1
    maxReplicas: 1
    serviceAccountName: orion-release-risk
    containers:
      - name: kserve-container
        image: {image}
        imagePullPolicy: Always
        ports: [{{name: http1, containerPort: 8080, protocol: TCP}}]
        env:
          - {{name: MODEL_NAME, value: orion-release-risk}}
          - {{name: MODEL_DIR, value: /models}}
        readinessProbe: {{httpGet: {{path: /health/ready, port: http1}}, initialDelaySeconds: 2, periodSeconds: 5}}
        livenessProbe: {{httpGet: {{path: /health/live, port: http1}}, initialDelaySeconds: 10, periodSeconds: 10}}
        securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities: {{drop: ["ALL"]}}}}
        volumeMounts:
          - {{name: tmp, mountPath: /tmp}}
          - {{name: production-diagnostic, mountPath: /var/run/secrets/keplerops/production, readOnly: true}}
      - name: orion-activation-callback
        image: {image}
        imagePullPolicy: Always
        command: ["python", "/opt/keplerops/activation-callback.py"]
        env:
          - {{name: RELEASE_ID, value: {signed["release_id"]}}}
          - {{name: MODEL_DIGEST, value: {signed["model_digest"]}}}
          - {{name: IMAGE_DIGEST, value: {signed["image_digest"]}}}
          - {{name: SOURCE_COMMIT, value: {state["source"]["commit"]}}}
          - {{name: ARTIFACT_SHA256, value: {artifact_digest}}}
          - {{name: VISIBLE_REPORT_DIGEST, value: {state["evaluation"]["visible_report_digest"]}}}
          - {{name: WORKLOAD_TOKEN_AUDIENCE, value: {ACTIVATION_TOKEN_AUDIENCE}}}
          - name: CALLBACK_URL
            valueFrom: {{secretKeyRef: {{name: orion-production-callback, key: callback-url}}}}
          - name: RELAY_KEY
            valueFrom: {{secretKeyRef: {{name: orion-production-callback, key: relay-key}}}}
        securityContext: {{allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities: {{drop: ["ALL"]}}}}
        volumeMounts:
          - {{name: workload-identity, mountPath: /var/run/secrets/keplerops/workload-identity, readOnly: true}}
          - {{name: podinfo, mountPath: /var/run/keplerops/podinfo, readOnly: true}}
          - {{name: production-diagnostic, mountPath: /var/run/secrets/keplerops/production, readOnly: true}}
          - {{name: activation-callback-script, mountPath: /opt/keplerops, readOnly: true}}
          - {{name: activation-exchange, mountPath: /var/run/keplerops/activation}}
    volumes:
      - {{name: tmp, emptyDir: {{}}}}
      - {{name: activation-exchange, emptyDir: {{}}}}
      - name: production-diagnostic
        secret:
          secretName: orion-production-diagnostic
          items: [{{key: engagement-reference, path: engagement-reference}}]
      - name: activation-callback-script
        configMap:
          name: orion-activation-callback
          items: [{{key: activation-callback.py, path: activation-callback.py}}]
      - name: workload-identity
        projected:
          sources:
            - serviceAccountToken:
                audience: {ACTIVATION_TOKEN_AUDIENCE}
                expirationSeconds: 3600
                path: token
      - name: podinfo
        downwardAPI:
          items: [{{path: uid, fieldRef: {{fieldPath: metadata.uid}}}}]
'''.encode()


def live_runtime(app: str, service: str, commit: str, expected_image: str, expected_members: dict[str, str], configure: str) -> dict[str, Any]:
    remote = f'''set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
{configure}
k3s kubectl -n argocd wait --for=jsonpath='{{.status.sync.status}}'=Synced application/{app} --timeout=5m >/dev/null
k3s kubectl -n argocd wait --for=jsonpath='{{.status.health.status}}'=Healthy application/{app} --timeout=5m >/dev/null
k3s kubectl -n orion-runtime wait --for=condition=Ready inferenceservice/{service} --timeout=5m >/dev/null
app_json=$(k3s kubectl -n argocd get application/{app} -o json)
isvc=$(k3s kubectl -n orion-runtime get inferenceservice/{service} -o json)
pods=$(k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice={service} -o json)
pod=$(jq -r '.items[] | select(any(.status.containerStatuses[]?; .ready == true)) | .metadata.name' <<<"$pods" | head -n1)
loaded=$(k3s kubectl -n orion-runtime exec "$pod" -- python - <<'PY'
import hashlib,json,pathlib
root=pathlib.Path('/models')
files={{'model':'orion-release-risk.onnx','tokenizer':'tokenizer.json','configuration':'config.json','preprocessing':'preprocessing.json','model_card':'model-card.md','provenance':'provenance.json'}}
print(json.dumps({{name:'sha256:'+hashlib.sha256((root/path).read_bytes()).hexdigest() for name,path in files.items()}},sort_keys=True))
PY
)
jq -n --argjson application "$app_json" --argjson inferenceservice "$isvc" --argjson pods "$pods" --argjson loaded "$loaded" '{{application:$application,inferenceservice:$inferenceservice,pods:$pods,loaded_members:$loaded}}'
'''
    state = json.loads(ssh(f"sudo bash -c {shlex.quote(remote)}"))
    revision = str(state["application"].get("status", {}).get("sync", {}).get("revision") or "")
    if revision != commit:
        raise RuntimeError("Argo CD synchronized a revision other than the promoted Forgejo commit")
    ready = [status for pod in state["pods"].get("items", []) for status in pod.get("status", {}).get("containerStatuses", []) if status.get("ready")]
    if not any(digest(expected_image) in str(status.get("imageID") or "") for status in ready):
        raise RuntimeError("ready KServe pod does not run the admitted image digest")
    if state["loaded_members"] != expected_members:
        raise RuntimeError("live pod model/tokenizer/config bytes differ from the signed candidate")
    return {
        "argo_revision": revision, "argo_sync_status": state["application"]["status"]["sync"]["status"],
        "kserve_generation": state["inferenceservice"]["metadata"]["generation"],
        "inferenceservice_annotations": state["inferenceservice"]["metadata"].get("annotations", {}),
        "running_image_ids": [item.get("imageID") for item in ready], "loaded_members": state["loaded_members"],
    }


def track_kubernetes_snapshot(manifest: dict[str, Any], namespace: str, kind: str, name: str) -> None:
    command = (
        "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml; "
        f"k3s kubectl -n {shlex.quote(namespace)} get {shlex.quote(kind)}/{shlex.quote(name)} -o json 2>/dev/null || true"
    )
    previous = ssh(f"sudo bash -c {shlex.quote(command)}").strip()
    if previous:
        parsed = json.loads(previous)
        parsed.pop("status", None)
        metadata = parsed.get("metadata") or {}
        for field in ("creationTimestamp", "generation", "managedFields", "resourceVersion", "uid"):
            metadata.pop(field, None)
        restore = base64.b64encode(canonical(parsed)).decode()
    else:
        restore = ""
    track(manifest, "kubernetes", kind, namespace=namespace, name=name, restore_base64=restore)


def established_assistant_identity() -> dict[str, str]:
    """Require the Assistant model identities to be established before promotion.

    The Assistant release/model/image/policy identities are created only by the
    separate `activate-business-model-identities.sh` step, which verifies signed
    external bundles.  Promotion declares that as an explicit prerequisite and
    fails clearly if the identities are absent, rather than silently preserving
    whatever happens to be present in the range state file.
    """
    release_file = RANGE_STATE / "business-release.env"
    values: dict[str, str] = {}
    if release_file.is_file():
        for line in release_file.read_text().splitlines():
            if "=" in line:
                name, value = line.split("=", 1)
                values[name] = value
    required = ("ORION_ASSISTANT_RELEASE_ID", "ORION_ASSISTANT_MODEL_DIGEST",
                "ORION_ASSISTANT_IMAGE_DIGEST", "ORION_ACTIVE_POLICY_DIGEST")
    missing = [name for name in required if not DIGEST.fullmatch(str(values.get(name) or ""))]
    if missing:
        raise RuntimeError(
            "assistant model identities are not established before promotion "
            "(run activate-business-model-identities.sh): " + ", ".join(missing)
        )
    return {name: values[name] for name in required}


def production_promote(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    signed, candidate = accepted("kep-m09-f"), accepted("kep-m09-a")
    verify_cosign_blob(canonical(signed["statement"]), signed["signature"]["bundle"])
    family = artifact_family(signed, context="signed production release")
    assistant_identity = established_assistant_identity()
    evidence = bind_subject("kep-m09-g", manifest, {
        "target": "orion-canary", "release_id": signed["release_id"],
        "model_digest": signed["model_digest"], "image_digest": signed["image_digest"],
    })
    capability = consume_promotion_capability(signed, str(conf.get("promotion_capability") or ""), manifest)
    path = "gitops/orion-canary/inferenceservice.yaml"
    kustomization, _ = forgejo_bytes("keplerops", "orion-platform", "gitops/orion-canary/kustomization.yaml")
    if b"inferenceservice.yaml" not in kustomization:
        raise RuntimeError("existing canary kustomization does not own the inference service")
    try:
        forgejo_bytes("keplerops", "orion-platform", "gitops/orion-canary/production-diagnostic-patch.yaml")
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
    else:
        if b"production-diagnostic-patch.yaml" not in kustomization:
            raise RuntimeError("m10 diagnostic patch exists but the current kustomization would drop it")
    body = deployment_manifest("orion-release-risk", signed, candidate)
    manifest_digest = f"sha256:{sha(body)}"
    deployment_key = opa_data("deployments", manifest_digest, {
        "release_id": signed["release_id"], "model_digest": signed["model_digest"],
        "image_digest": signed["image_digest"], "manifest_digest": manifest_digest,
    })
    track(manifest, "opa", "data", path=f"keplerops/m09/deployments/{deployment_key}")
    admission = opa_decision("admission", {"release_key": key(signed["release_id"]), "deployment_key": deployment_key})
    if not admission.get("allow") or admission.get("manifest_digest") != manifest_digest:
        raise RuntimeError("OPA admission denied the exact signed deployment manifest")
    commit = write_forgejo_file("keplerops", "orion-platform", path, body, f"Promote signed Orion release {signed['release_id']}")
    track(manifest, "forgejo", "file", owner="keplerops", repository="orion-platform", path=path, commit=commit)
    if not PRODUCTION_DIAGNOSTIC:
        raise RuntimeError("server-held production diagnostic is unavailable during the signed promotion")
    if not ACTIVATION_CALLBACK_URL or not ACTIVATION_RELAY_KEY:
        raise RuntimeError("server-held production activation-callback identity is unavailable during the signed promotion")
    encoded_diagnostic = base64.b64encode(PRODUCTION_DIAGNOSTIC.encode()).decode()
    encoded_script = base64.b64encode(ACTIVATION_CALLBACK_SCRIPT.encode()).decode()
    encoded_callback_url = base64.b64encode(ACTIVATION_CALLBACK_URL.encode()).decode()
    encoded_relay_key = base64.b64encode(ACTIVATION_RELAY_KEY.encode()).decode()
    track_kubernetes_snapshot(manifest, "orion-runtime", "secret", "orion-production-diagnostic")
    track_kubernetes_snapshot(manifest, "orion-runtime", "secret", "orion-production-callback")
    track_kubernetes_snapshot(manifest, "orion-runtime", "configmap", "orion-activation-callback")
    track_kubernetes_snapshot(manifest, "orion-runtime", "serviceaccount", "orion-release-risk")
    track_kubernetes_snapshot(manifest, "argocd", "application", "orion-canary")
    track_kubernetes_snapshot(manifest, "orion-runtime", "inferenceservice", "orion-release-risk")
    configure = (
        "work=\"$(mktemp -d)\" && "
        f"printf %s {shlex.quote(encoded_diagnostic)} | base64 -d >\"$work/engagement-reference\" && "
        "k3s kubectl -n orion-runtime create secret generic orion-production-diagnostic "
        "--from-file=engagement-reference=\"$work/engagement-reference\" --dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null && "
        "k3s kubectl -n orion-runtime create serviceaccount orion-release-risk "
        "--dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null && "
        f"printf %s {shlex.quote(encoded_script)} | base64 -d >\"$work/activation-callback.py\" && "
        "k3s kubectl -n orion-runtime create configmap orion-activation-callback "
        "--from-file=activation-callback.py=\"$work/activation-callback.py\" --dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null && "
        f"printf %s {shlex.quote(encoded_callback_url)} | base64 -d >\"$work/callback-url\" && "
        f"printf %s {shlex.quote(encoded_relay_key)} | base64 -d >\"$work/relay-key\" && "
        "k3s kubectl -n orion-runtime create secret generic orion-production-callback "
        "--from-file=callback-url=\"$work/callback-url\" --from-file=relay-key=\"$work/relay-key\" "
        "--dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null && "
        "rm -rf \"$work\" && "
        "env GITOPS_REPO_URL=http://192.168.78.1:3000/keplerops/orion-platform.git "
        f"GITOPS_REVISION={commit} GITOPS_REPO_PATH=gitops/orion-canary "
        "/opt/keplerops-platform/scripts/configure-gitops.sh >/dev/null"
    )
    runtime = live_runtime("orion-canary", "orion-release-risk", commit, signed["image_digest"], candidate["model_members"], configure)
    annotations = runtime["inferenceservice_annotations"]
    if annotations.get("keplerops.lab/release-id") != signed["release_id"] or annotations.get("keplerops.lab/model-digest") != signed["model_digest"]:
        raise RuntimeError("KServe admission annotations do not preserve signed release identity")
    record = {
        "schema": "keplerops.runtime-inventory/v2", "model_family": family,
        "application": "orion-canary", "release_id": signed["release_id"], "gitops_commit": commit,
        "deployment_manifest_digest": manifest_digest, "opa_admission": admission,
        "image_repository": candidate["image_repository"], "image_digest": signed["image_digest"],
        "model_digest": signed["model_digest"], "model_members": candidate["model_members"],
        "kserve_service": "orion-release-risk", **runtime,
        "signature_bundle_digest": signed["signature"]["bundle_sha256"], "healthy": True,
        "promotion_capability": {"capability_id": capability["capability_id"], "scope": capability["scope"], "consumed": True},
        "activation_callback": {
            "receiver": ACTIVATION_CALLBACK_URL, "token_audience": ACTIVATION_TOKEN_AUDIENCE,
            "workload_service_account": "orion-release-risk",
            "script_digest": f"sha256:{sha(ACTIVATION_CALLBACK_SCRIPT.encode())}",
            "bound_release_id": signed["release_id"], "bound_model_digest": signed["model_digest"],
            "bound_image_digest": signed["image_digest"],
            "bound_visible_report_digest": signed["release_state"]["evaluation"]["visible_report_digest"],
            "bound_source_commit": signed["release_state"]["source"]["commit"],
        },
        "assistant_identity": assistant_identity,
        "parents": parents, "recorded_at": now(), **evidence, "engagement_reference": flag("kep-m09-g"),
    }
    record = put_native(f"release/runtime/orion-canary-{commit}.json", record)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    RANGE_STATE.mkdir(parents=True, exist_ok=True)
    release_file = RANGE_STATE / "business-release.env"
    prior_bytes = release_file.read_bytes() if release_file.is_file() else b""
    track(
        manifest, "local", "range-state-file", path="business-release.env",
        existed=release_file.is_file(), restore_base64=base64.b64encode(prior_bytes).decode(),
    )
    prior_identity = {}
    if release_file.is_file():
        for line in release_file.read_text().splitlines():
            if "=" in line:
                name, value = line.split("=", 1)
                prior_identity[name] = value
    release_file.write_text(
        f"ORION_RELEASE_RISK_RELEASE_ID={signed['release_id']}\n"
        f"ORION_RELEASE_RISK_MODEL_DIGEST={signed['model_digest']}\n"
        f"ORION_RELEASE_RISK_IMAGE_DIGEST={signed['image_digest']}\n"
        f"ORION_RELEASE_RISK_GITOPS_COMMIT={commit}\n"
        + "".join(
            f"{name}={value}\n" for name, value in sorted(prior_identity.items())
            if name.startswith("ORION_ASSISTANT_") or name == "ORION_ACTIVE_POLICY_DIGEST"
        )
    )
    return record


def cinder_release_assets(owner: str, repository: str, tag: str) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], bytes]]]:
    release = forgejo("GET", f"/repos/{owner}/{repository}/releases/tags/{quote(tag, safe='')}", cinder=True)
    result: dict[str, tuple[dict[str, Any], bytes]] = {}
    for name in ("orion-model.pkl", "MODEL_CARD.md", "signed-artifact-report.json"):
        asset = next((item for item in release.get("assets", []) if item.get("name") == name), None)
        if not asset:
            raise RuntimeError(f"Cinder release lacks required asset {name}")
        result[name] = (asset, checked(requests.get(asset["browser_download_url"], auth=CINDER_AUTH, timeout=120)).content)
    return release, result


def upstream_release(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    owner, repository = "cinder-operator", "orion-model-releases"
    tag = str(conf.get("release_tag") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", tag):
        raise ValueError("release_tag must be an exact Forgejo tag name")
    release, assets = cinder_release_assets(owner, repository, tag)
    if release.get("draft") is True or release.get("prerelease") is True:
        raise RuntimeError("upstream intake requires a published non-prerelease Forgejo release")
    package = assets["orion-model.pkl"][1]
    predecessor = parents[0]
    expected = f"sha256:{digest(str(predecessor.get('model_digest') or ''))}"
    # Bind the participant-published upstream subject before the byte/signature
    # verification so an earlier controllable failure still emits a same-subject
    # denial for the negative control.
    evidence = bind_subject("kep-m09-h", manifest, {
        "upstream": f"{owner}/{repository}:{tag}", "artifact_sha256": expected,
        "source_commit": str(predecessor.get("source_commit") or ""),
    })
    if f"sha256:{sha(package)}" != expected:
        raise RuntimeError("published model asset bytes differ from the accepted integrity handoff")
    if b"release-risk" not in assets["MODEL_CARD.md"][1].lower():
        raise RuntimeError("model card does not declare the release-risk family")
    report_body = assets["signed-artifact-report.json"][1]
    execution = json.loads(report_body)
    signature = str(execution.pop("signature", ""))
    expected_signature = hmac.new(CINDER_ATTESTATION_KEY.encode(), canonical(execution), hashlib.sha256).hexdigest()
    heldout_digest = f"sha256:{digest(str(execution.get('heldout_suite_sha256') or ''))}"
    if (not hmac.compare_digest(signature, expected_signature)
            or f"sha256:{digest(str(execution.get('artifact_sha256') or ''))}" != expected
            or f"sha256:{sha(report_body)}" != predecessor.get("record_sha256")
            or heldout_digest != predecessor.get("heldout_suite_digest")):
        raise RuntimeError("Cinder execution report is not a valid signature over these exact published bytes")
    if (execution.get("artifact_filename") != predecessor.get("artifact_filename")
            or execution.get("artifact_format") != predecessor.get("artifact_format")
            or execution.get("artifact_interface") != predecessor.get("artifact_interface")
            or execution.get("source_commit") != predecessor.get("source_commit")
            or execution.get("package_members") != predecessor.get("package_members")
            or execution.get("fresh_inference") != predecessor.get("fresh_inference")):
        raise RuntimeError("published report does not preserve the accepted serialized-model contract")
    source_commit = str(execution.get("source_commit") or "")
    source = forgejo("GET", f"/repos/cinder-labs/orion-poisoned-dataset/git/commits/{source_commit}", cinder=True)
    if str(source.get("sha") or source.get("id") or "") != source_commit:
        raise RuntimeError("Cinder source commit does not resolve in the fixed artifact repository")
    family = artifact_family(execution, context="Cinder serialized-model handoff")
    predicate = {
        "schema": "cinder.model-release-attestation/v2", "model_family": family,
        "upstream": f"{owner}/{repository}:{tag}", "release_id": release["id"],
        "artifact_sha256": expected, "model_card_sha256": f"sha256:{sha(assets['MODEL_CARD.md'][1])}",
        "execution_report_sha256": f"sha256:{sha(report_body)}", "source_commit": execution["source_commit"],
        "source_repository": predecessor["source_repository"],
        "source_tree_digest": predecessor["source_tree_digest"],
        "accepted_release_commit": predecessor["release_commit"],
        "artifact_filename": execution["artifact_filename"], "artifact_format": execution["artifact_format"],
        "artifact_interface": execution["artifact_interface"],
        "package_members": execution["package_members"],
        "model_subject_digest": predecessor.get("model_subject_digest"),
        "heldout_suite_digest": heldout_digest,
        "heldout_accuracy": float(execution.get("heldout_accuracy") or 0),
        "fresh_inference_digest": f"sha256:{sha(canonical(execution['fresh_inference']))}",
        "published_at": release.get("published_at"), "parents": parents,
        "verification": "metadata-and-signature-only; no model deserialization performed",
        "engagement_reference": flag("kep-m09-h"),
    }
    predicate.update(evidence)
    signature_value = hmac.new(CINDER_ATTESTATION_KEY.encode(), canonical(predicate), hashlib.sha256).hexdigest()
    record = {**predicate, "signature": signature_value}
    path = f"attestations/{tag}.json"
    commit = write_forgejo_file(owner, repository, path, canonical(record), f"Record verified upstream release {tag}", cinder=True)
    native = {"system": "forgejo", "cinder": True, "owner": owner, "repository": repository, "path": path, "commit": commit, "sha256": f"sha256:{sha(canonical(record))}"}
    track(manifest, "forgejo", "file", cinder=True, owner=owner, repository=repository, path=path, commit=commit)
    return {**record, "native_record": native}


def send_import(operation: str, conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    artifact_url = str(conf.get("artifact_url") or "")
    if not re.fullmatch(r"https://git\.cinder\.lab/[A-Za-z0-9._~:/?=&%+-]+", artifact_url):
        raise ValueError("import exception artifact must be a Cinder Forgejo HTTPS asset")
    artifact_sha = digest(str(conf.get("artifact_sha256") or ""))
    # The corrupt-import lane is artifact-defined: the concrete bounded family is
    # declared by the submitted artifact rather than fixed to release-risk.  It
    # must still resolve to an authoritative allowed family.
    family = str(conf.get("model_family") or MODEL_FAMILY)
    if family not in ALLOWED_MODEL_FAMILIES:
        raise ValueError("submitted import artifact does not declare an allowed concrete model family")
    evidence = bind_subject(operation, manifest, {"artifact_sha256": f"sha256:{artifact_sha}", "review_profile": "corrupt-import"})
    request_id = f"orion-import-{uuid.uuid4().hex}"
    request = {
        "schema": "keplerops.model-import-request/v2", "request_id": request_id,
        "operation": operation, "artifact_url": artifact_url, "sha256": artifact_sha,
        "relay_basket": "m09-import-exceptions", "reply_queue": IMPORT_RESULTS,
        "model_family": family, **evidence, "parents": parents,
    }
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue=IMPORT_QUEUE, durable=True)
    channel.queue_declare(queue=IMPORT_RESULTS, durable=True)
    track(manifest, "rabbitmq", "message", queue=IMPORT_QUEUE, correlation_id=request_id)
    channel.basic_publish(exchange="", routing_key=IMPORT_QUEUE, body=canonical(request), properties=pika.BasicProperties(delivery_mode=2, content_type="application/json", correlation_id=request_id))
    deadline, result = time.time() + 120, None
    while time.time() < deadline:
        method, properties, body = channel.basic_get(queue=IMPORT_RESULTS, auto_ack=False)
        if method:
            candidate = json.loads(body)
            if candidate.get("request_id") == request_id:
                channel.basic_ack(method.delivery_tag)
                result = candidate
                break
            channel.basic_nack(method.delivery_tag, requeue=True)
        time.sleep(1)
    connection.close()
    if (not result or result.get("status") == "failed"
            or result.get("schema") != "keplerops.model-import-result/v2"
            or result.get("request_id") != request_id
            or result.get("operation") != operation
            or result.get("model_family") != family
            or result.get("artifact_sha256") != f"sha256:{artifact_sha}"
            or result.get("engagement_reference") != flag(operation)):
        raise RuntimeError(f"native import review did not complete: {result}")
    if any(result.get(name) != value for name, value in evidence.items()):
        raise RuntimeError("import result is not bound to this operation attempt and artifact subject")
    result["parents"] = parents
    result["native_record"] = {
        "system": "relay", "basket": "m09-import-exceptions", "request_id": request_id,
        "sha256": f"sha256:{sha(canonical(result))}",
    }
    return result


def mirror_sync(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    release = accepted("kep-m09-h")
    family = artifact_family(release, context="accepted upstream release")
    channel_path = "channels/orion-compatible.json"
    evidence = bind_subject("kep-m09-j", manifest, {
        "channel_path": channel_path, "artifact_sha256": release["artifact_sha256"],
        "upstream": release["upstream"],
    })
    current, commit = forgejo_json("cinder-operator", "orion-model-releases", channel_path, cinder=True)
    baseline_path = STATE / "upstream-channel-baseline.json"
    if not baseline_path.is_file():
        raise RuntimeError("setup did not retain the pre-action upstream channel observation")
    baseline = json.loads(baseline_path.read_text())
    if current == baseline or current.get("release_tag") != str(release["upstream"]).rsplit(":", 1)[1] or current.get("artifact_sha256") != release["artifact_sha256"]:
        raise RuntimeError("the assigned Cinder operator has not rebound the trusted mutable channel to the accepted publication")
    release_native = forgejo("GET", f"/repos/cinder-operator/orion-model-releases/releases/tags/{quote(current['release_tag'], safe='')}", cinder=True)
    asset = next((item for item in release_native.get("assets", []) if item.get("name") == "orion-model.pkl"), None)
    if not asset:
        raise RuntimeError("rebound upstream release has no model asset")
    body = checked(requests.get(asset["browser_download_url"], auth=CINDER_AUTH, timeout=120)).content
    expected = digest(release["artifact_sha256"])
    if sha(body) != expected:
        raise RuntimeError("acquired upstream bytes do not equal the rebound channel subject")
    object_key = f"model-mirror/orion/{expected}/orion-model.pkl"
    client = minio()
    client.put_object(Bucket="artifacts", Key=object_key, Body=body, ContentType="application/octet-stream")
    if client.get_object(Bucket="artifacts", Key=object_key)["Body"].read() != body:
        raise RuntimeError("internal mirror did not retain exact acquired bytes")
    record = {
        "schema": "keplerops.model-mirror-manifest/v2", "model_family": family,
        "mutable_binding": {"path": channel_path, "before_sha256": f"sha256:{sha(canonical(baseline))}", "after_sha256": f"sha256:{sha(canonical(current))}", "forgejo_commit": commit},
        "acquisition": {"upstream_release_id": release_native["id"], "asset_id": asset["id"], "download_sha256": f"sha256:{sha(body)}"},
        "artifact_sha256": f"sha256:{expected}", "mirror_bucket": "artifacts", "mirror_key": object_key,
        "parents": parents, "synchronized_at": now(), "engagement_reference": flag("kep-m09-j"),
    }
    record.update(evidence)
    record = put_native(f"model-mirror/orion/{expected}/manifest.json", record)
    track(manifest, "minio", "object", bucket="artifacts", key=object_key)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    return record


def observe_review(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    issue_number = int(conf.get("review_issue") or 0)
    marker = DISPATCH_STATE / f"{issue_number}.json"
    track(manifest, "dispatcher", "marker", issue=issue_number, path=str(marker.relative_to(STATE)))
    mirror = accepted("kep-m09-j")
    # Bind the participant-selected review action and mirrored subject before the
    # human-review/load checks so an earlier controllable failure still emits a
    # same-subject denial for the negative control.
    evidence = bind_subject("kep-m09-k", manifest, {
        "review_action_id": f"forgejo:keplerops/orion-model-review#{issue_number}",
        "artifact_sha256": mirror["artifact_sha256"],
    })
    issue = forgejo("GET", f"/repos/keplerops/orion-model-review/issues/{issue_number}")
    labels = {item["name"] for item in issue.get("labels", [])}
    if issue.get("state") != "closed" or "load-approved" not in labels:
        raise RuntimeError("human reviewer has not completed the normal Forgejo review action")
    object_key = f"model-review/results/{issue_number}.json"
    try:
        body = minio().get_object(Bucket="artifacts", Key=object_key)["Body"].read()
    except Exception as exc:
        raise RuntimeError("review worker has not yet produced a native result for this issue") from exc
    track(manifest, "minio", "object", bucket="artifacts", key=object_key)
    result = json.loads(body)
    if result.get("review_action_id") != f"forgejo:keplerops/orion-model-review#{issue_number}" or result.get("artifact_sha256") != mirror["artifact_sha256"]:
        raise RuntimeError("review result is not joined to the exact human action and mirrored bytes")
    # The isolated review worker deliberately omits the operation reference; only
    # the accepted observation below carries it.  The load contract therefore
    # asserts the causal smoke inference and the absent reference together,
    # never requiring the worker result to both carry and lack the same field.
    if (result.get("schema") != "keplerops.model-import-result/v2"
            or result.get("model_family") != artifact_family(mirror, context="accepted mirror manifest")
            or result.get("import", {}).get("returncode") != 0
            or result.get("import", {}).get("loader", {}).get("status") != "loaded"
            or result.get("import", {}).get("loader", {}).get("smoke_prediction") is None
            or result.get("engagement_reference") is not None):
        raise RuntimeError("human-approved mirrored artifact was not unsafely loaded with real inference")
    if not marker.is_file():
        raise RuntimeError("review dispatcher has no durable marker for the human action")
    marker_record = json.loads(marker.read_text())
    if (marker_record.get("request_id") != result.get("request_id")
            or marker_record.get("result_sha256") != f"sha256:{sha(body)}"):
        raise RuntimeError("review dispatcher marker does not bind the observed worker result bytes")
    accepted_result = {
        **result,
        "parents": parents,
        "engagement_reference": flag("kep-m09-k"),
        **evidence,
    }
    accepted_result = put_native(f"model-review/accepted/{issue_number}-{manifest['attempt_id']}.json", accepted_result)
    track(manifest, "minio", "object", bucket="artifacts", key=accepted_result["native_record"]["key"])
    return accepted_result


def staging_reconcile(conf: dict[str, Any], manifest: dict[str, Any], parents: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = accepted("kep-m09-k")
    family = artifact_family(reviewed, context="reviewed mirrored artifact")
    repository, tag = "orion-review/orion-staging", "integration"
    artifact = harbor_artifact(repository, tag)
    image_digest = f"sha256:{digest(str(artifact.get('digest') or ''))}"
    expected = f"sha256:{digest(str(conf.get('expected_image_digest') or ''))}"
    # Bind the participant-selected staging subject before the trusted-tag and
    # provenance checks so an earlier controllable failure still emits a
    # same-subject denial for the negative control.
    evidence = bind_subject("kep-m09-l", manifest, {
        "artifact_sha256": reviewed["artifact_sha256"], "image_repository": repository,
        "expected_image_digest": expected, "source_commit": str(conf.get("source_commit") or ""),
    })
    if image_digest != expected:
        raise RuntimeError("trusted staging tag does not resolve to the Cinder-authored replacement digest")
    track(manifest, "harbor", "artifact", repository=repository, digest=image_digest, participant_owned=True)
    raw, image_manifest, config = harbor_manifest(repository, image_digest)
    labels = config.get("config", {}).get("Labels") or config.get("container_config", {}).get("Labels") or {}
    if labels.get("io.keplerops.orion.model-digest") != reviewed["artifact_sha256"]:
        raise RuntimeError("replacement image does not bind the reviewed mirrored model")
    provenance = oci_provenance(
        repository, image_digest, "keplerops/orion-staging", str(conf.get("source_commit") or ""),
        int(conf.get("forgejo_actions_run_id") or 0), ".forgejo/workflows/staging-image.yml",
    )
    if (labels.get("org.opencontainers.image.revision") != provenance["forgejo_head_sha"]
            or labels.get("org.opencontainers.image.source") != "https://git.keplerops.lab/keplerops/orion-staging"):
        raise RuntimeError("staging image config does not bind the required Forgejo source and Actions run")
    path = "gitops/orion-staging/inferenceservice.yaml"
    kustomization, _ = forgejo_bytes("keplerops", "orion-platform", "gitops/orion-staging/kustomization.yaml")
    if b"inferenceservice.yaml" not in kustomization:
        raise RuntimeError("existing staging kustomization does not own the inference service")
    body = f'''apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: orion-release-risk-staging
  namespace: orion-runtime
  annotations:
    serving.kserve.io/deploymentMode: RawDeployment
    keplerops.lab/model-digest: {reviewed["artifact_sha256"]}
spec:
  predictor:
    containers:
      - name: kserve-container
        image: registry.keplerops.lab/{repository}@{image_digest}
'''.encode()
    commit = write_forgejo_file("keplerops", "orion-platform", path, body, f"Reconcile Orion staging image {image_digest}")
    argo = f'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata: {{name: orion-staging, namespace: argocd}}
spec:
  project: orion-platform
  source: {{repoURL: http://192.168.78.1:3000/keplerops/orion-platform.git, targetRevision: {commit}, path: gitops/orion-staging}}
  destination: {{server: https://kubernetes.default.svc, namespace: orion-runtime}}
  syncPolicy: {{automated: {{prune: true, selfHeal: true}}, syncOptions: [CreateNamespace=false]}}
'''
    configure = f"printf %s {shlex.quote(base64.b64encode(argo.encode()).decode())} | base64 -d | k3s kubectl apply -f - >/dev/null"
    track_kubernetes_snapshot(manifest, "argocd", "application", "orion-staging")
    track_kubernetes_snapshot(manifest, "orion-runtime", "inferenceservice", "orion-release-risk-staging")
    # The staging image contract exposes the same model member paths.  Hash the
    # reviewed serialized subject separately from the running image identity.
    remote = f'''set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
{configure}
k3s kubectl -n argocd wait --for=jsonpath='{{.status.sync.status}}'=Synced application/orion-staging --timeout=5m >/dev/null
k3s kubectl -n orion-runtime wait --for=condition=Ready inferenceservice/orion-release-risk-staging --timeout=5m >/dev/null
jq -n --argjson app "$(k3s kubectl -n argocd get application/orion-staging -o json)" --argjson pods "$(k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice=orion-release-risk-staging -o json)" '{{application:$app,pods:$pods}}'
'''
    state = json.loads(ssh(f"sudo bash -c {shlex.quote(remote)}"))
    if state["application"]["status"]["sync"]["revision"] != commit:
        raise RuntimeError("Argo staging revision differs from the Forgejo mutation")
    ready = [status for pod in state["pods"].get("items", []) for status in pod.get("status", {}).get("containerStatuses", []) if status.get("ready")]
    if not any(digest(image_digest) in str(item.get("imageID") or "") for item in ready):
        raise RuntimeError("staging pod does not run the moved Harbor tag digest")
    record = {
        "schema": "keplerops.staging-reconciliation/v2", "model_family": family,
        "application": "orion-staging", "gitops_commit": commit,
        "deployment_manifest_digest": f"sha256:{sha(body)}", "image_repository": repository,
        "image_digest": image_digest, "image_manifest_digest": f"sha256:{sha(raw)}",
        "model_digest": reviewed["artifact_sha256"], "oci_provenance": provenance,
        "argo_revision": commit, "running_image_ids": [item.get("imageID") for item in ready],
        "healthy": True, "parents": parents, "recorded_at": now(), "engagement_reference": flag("kep-m09-l"),
    }
    record.update(evidence)
    record = put_native(f"release/runtime/orion-staging-{commit}.json", record)
    track(manifest, "forgejo", "file", owner="keplerops", repository="orion-platform", path=path, commit=commit)
    track(manifest, "minio", "object", bucket="artifacts", key=record["native_record"]["key"])
    return record


Handler = Callable[[dict[str, Any], dict[str, Any], list[dict[str, Any]]], dict[str, Any]]
HANDLERS: dict[str, Handler] = {
    "kep-m09-b": visible_gate, "kep-m09-a": register_candidate, "kep-m09-c": lineage,
    "kep-m09-d": approval, "kep-m09-e": image_binding, "kep-m09-f": sign_release,
    "kep-m09-g": production_promote, "kep-m09-h": upstream_release,
    "kep-m09-i": lambda conf, attempt, parents: send_import("kep-m09-i", conf, attempt, parents),
    "kep-m09-j": mirror_sync, "kep-m09-k": observe_review, "kep-m09-l": staging_reconcile,
}


def execute(operation: str, conf: dict[str, Any]) -> dict[str, Any]:
    if operation not in HANDLERS:
        raise ValueError(f"unknown release operation: {operation}")
    replay_attempt = operation == "kep-m09-g" and bool(conf.get("promotion_capability"))
    if accepted_path(operation).is_file() and not replay_attempt:
        return accepted(operation)
    parents = resolve_prerequisites(operation, conf)
    _, root, manifest = attempt_manifest(operation, conf, parents)
    try:
        record = HANDLERS[operation](conf, manifest, parents)
        result = accept(operation, record)
        manifest.update(status="accepted", completed_at=now(), native_record=result["native_record"])
        store_manifest(root, manifest)
        return result
    except Exception as exc:
        manifest.update(status="failed", completed_at=now(), error=f"{type(exc).__name__}: {exc}"[:1200])
        try:
            publish_denial(manifest, exc)
        except Exception as denial_error:
            manifest["denial_publish_error"] = f"{type(denial_error).__name__}: {denial_error}"[:600]
        failed = STATE / "failed" / operation / root.name
        failed.parent.mkdir(parents=True, exist_ok=True)
        failed.write_bytes(canonical(manifest))
        store_manifest(root, manifest)
        raise
