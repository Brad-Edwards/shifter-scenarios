from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import time
from typing import Any
from urllib.parse import quote
import uuid
import zipfile

import boto3
from botocore.config import Config
import mlflow
from mlflow import MlflowClient
import pika
import requests


STATE = Path(os.getenv("M09_STATE_ROOT", "/var/lib/orion-release"))
MLFLOW_URL = os.getenv("MLFLOW_URL", "http://mlflow:5000").rstrip("/")
MLFLOW_AUTH = tuple(os.getenv("MLFLOW_AUTH", "svc-orion-training:KeplerV2-Training-MLflow-Service").split(":", 1))
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
HARBOR_URL = os.getenv("HARBOR_URL", "http://harbor-nginx:8080").rstrip("/")
HARBOR_AUTH = tuple(os.getenv("HARBOR_AUTH", "admin:KeplerV2-Training-Harbor").split(":", 1))
OPA_URL = os.getenv("OPA_URL", "http://192.168.78.30:30082").rstrip("/")
CINDER_FORGEJO = os.getenv("CINDER_FORGEJO_URL", "http://10.61.90.30:3000").rstrip("/")
CINDER_AUTH = tuple(os.getenv("CINDER_FORGEJO_AUTH", "cinder-operator:Cinder-Operations-Git-K3m7Pq4x").split(":", 1))
FORGEJO = os.getenv("KEPLER_FORGEJO_URL", "http://forgejo:3000").rstrip("/")
FORGEJO_AUTH = tuple(os.getenv("KEPLER_FORGEJO_AUTH", "range-admin:KeplerV2-Training-Forgejo-Admin").split(":", 1))
RELAY_URL = os.getenv("M09_RELAY_INTERNAL_URL", "http://192.168.78.30:31080").rstrip("/")
RELAY_HOST = os.getenv("M09_RELAY_HOST", "relay.cinder.cinder.lab")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "")
IMPORT_QUEUE = os.getenv("M09_IMPORT_QUEUE", "orion.review.m09-import")
IMPORT_RESULTS = os.getenv("M09_IMPORT_RESULT_QUEUE", "orion.review.m09-results")
SSH_TARGET = os.getenv("K3S01_SSH_TARGET", "kepler@192.168.78.30")
SSH_KEY = os.getenv("K3S01_SSH_KEY", "/run/keplerops/k3s-key")
CINDER_ATTESTATION_KEY = os.getenv("CINDER_ATTESTATION_KEY", "Cinder-Isolated-Execution-2026")

FLAGS = {letter: os.getenv(f"M09_FLAG_{letter.upper()}", "") for letter in "abcdefghijkl"}
DIGEST = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: str) -> str:
    match = DIGEST.fullmatch(str(value).lower())
    if not match:
        raise ValueError(f"invalid SHA-256 digest: {value}")
    return match.group(1)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def operation_flag(operation: str) -> str:
    flag = FLAGS[operation[-1]]
    if not flag:
        raise RuntimeError(f"server-held reference for {operation} is unavailable")
    return flag


def accepted_path(operation: str) -> Path:
    return STATE / "accepted" / f"{operation}.json"


def accept(operation: str, record: dict[str, Any]) -> dict[str, Any]:
    path = accepted_path(operation)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text())
        if previous != record:
            raise RuntimeError(f"{operation} already accepted a different immutable result")
        return previous
    path.write_bytes(canonical(record))
    return record


def accepted(operation: str) -> dict[str, Any]:
    path = accepted_path(operation)
    if not path.is_file():
        raise RuntimeError(f"required accepted operation is absent: {operation}")
    return json.loads(path.read_text())


def minio():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_URL,
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "svc-orion-training"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "KeplerV2-Training-Minio-Orion-Training"),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def put_record(key: str, record: dict[str, Any]) -> dict[str, Any]:
    body = canonical(record)
    minio().put_object(Bucket="artifacts", Key=key, Body=body, ContentType="application/json")
    return {**record, "carrier": {"bucket": "artifacts", "key": key, "sha256": f"sha256:{sha(body)}"}}


def mlflow_setup() -> MlflowClient:
    os.environ["MLFLOW_TRACKING_URI"] = MLFLOW_URL
    os.environ["MLFLOW_TRACKING_USERNAME"] = MLFLOW_AUTH[0]
    os.environ["MLFLOW_TRACKING_PASSWORD"] = MLFLOW_AUTH[1]
    mlflow.set_tracking_uri(MLFLOW_URL)
    return MlflowClient(tracking_uri=MLFLOW_URL)


def experiment(client: MlflowClient, name: str = "Orion Release Operations") -> str:
    found = client.get_experiment_by_name(name)
    return found.experiment_id if found else client.create_experiment(name, artifact_location="s3://mlflow/orion-release-operations")


def log_mlflow_record(name: str, record: dict[str, Any], tags: dict[str, str]) -> str:
    client = mlflow_setup()
    run = client.create_run(experiment(client), tags={"mlflow.runName": name, **tags})
    with tempfile.TemporaryDirectory(prefix="orion-release-record-") as temp:
        path = Path(temp) / "report.json"
        path.write_bytes(canonical(record))
        client.log_artifact(run.info.run_id, str(path), artifact_path="reports")
    client.set_terminated(run.info.run_id, "FINISHED")
    return run.info.run_id


def download_model(run_id: str) -> Path:
    mlflow_setup()
    return Path(mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model"))


def model_digest(model_dir: Path) -> str:
    model = model_dir / "orion-release-risk.onnx"
    if not model.is_file():
        raise ValueError("MLflow run lacks model/orion-release-risk.onnx")
    return sha(model.read_bytes())


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


def forgejo_file(owner: str, repo: str, path: str) -> Any:
    item = forgejo("GET", f"/repos/{owner}/{repo}/contents/{path}")
    if item.get("encoding") != "base64":
        raise RuntimeError(f"Forgejo file has unsupported encoding: {owner}/{repo}/{path}")
    return json.loads(base64.b64decode(str(item["content"]).replace("\n", "")))


def harbor_artifact(repository: str, reference: str) -> dict[str, Any]:
    if "/" not in repository:
        raise ValueError("Harbor repository must include project and repository")
    project, name = repository.split("/", 1)
    path = f"/api/v2.0/projects/{quote(project, safe='')}/repositories/{quote(name, safe='')}/artifacts/{quote(reference, safe='')}"
    return checked(requests.get(f"{HARBOR_URL}{path}", auth=HARBOR_AUTH, params={"with_label": "true"}, timeout=45)).json()


def harbor_manifest(repository: str, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
    headers = {"Accept": "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"}
    response = checked(requests.get(f"{HARBOR_URL}/v2/{repository}/manifests/{reference}", auth=HARBOR_AUTH, headers=headers, timeout=45))
    manifest = response.json()
    config_digest = manifest.get("config", {}).get("digest")
    if not config_digest:
        raise RuntimeError("Harbor manifest has no image config")
    config = checked(requests.get(f"{HARBOR_URL}/v2/{repository}/blobs/{config_digest}", auth=HARBOR_AUTH, timeout=45)).json()
    return manifest, config


def opa(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return checked(requests.post(f"{OPA_URL}{path}", json={"input": payload}, timeout=30)).json().get("result") or {}


def ssh(command: str, *, stdin: bytes | None = None, timeout: int = 420) -> str:
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", SSH_TARGET, command],
        input=stdin,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"platform command failed: {result.stderr.decode(errors='replace')[:1000]}")
    return result.stdout.decode()


def write_forgejo_file(owner: str, repo: str, path: str, value: bytes, message: str) -> str:
    endpoint = f"/repos/{owner}/{repo}/contents/{path}"
    try:
        current = forgejo("GET", endpoint)
        existing_sha = current["sha"]
        method = "PUT"
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        existing_sha, method = None, "POST"
    body = {"content": base64.b64encode(value).decode(), "message": message, "branch": "main"}
    if existing_sha:
        body["sha"] = existing_sha
    forgejo(method, endpoint, body=body)
    branch = forgejo("GET", f"/repos/{owner}/{repo}/branches/main")
    commit = str(branch["commit"]["id"])
    if not COMMIT.fullmatch(commit):
        raise RuntimeError("Forgejo did not return an immutable GitOps commit")
    return commit


def visible_gate(conf: dict[str, Any]) -> dict[str, Any]:
    run_id = str(conf.get("mlflow_run_id") or "")
    integrity_run_id = str(conf.get("integrity_review_run_id") or "")
    source_commit = str(conf.get("source_commit") or "")
    if not run_id or not integrity_run_id or not COMMIT.fullmatch(source_commit):
        raise ValueError("mlflow_run_id, integrity_review_run_id, and immutable source_commit are required")
    cases = forgejo_file("keplerops", "orion-release-suite", "visible-suite.json")
    trigger_texts = conf.get("trigger_inputs")
    near_texts = conf.get("near_controls")
    if not isinstance(cases, list) or len(cases) < 8 or not isinstance(trigger_texts, list) or len(trigger_texts) < 2 or not isinstance(near_texts, list) or len(near_texts) < 2:
        raise ValueError("the suite requires eight visible cases, two trigger inputs, and two near controls")
    if any(not isinstance(text, str) or not text.strip() for text in [*trigger_texts, *near_texts]):
        raise ValueError("trigger and near-control inputs must be non-empty text")
    mlflow_setup()
    integrity_path = Path(mlflow.artifacts.download_artifacts(run_id=integrity_run_id, artifact_path="reports/report.json"))
    integrity = json.loads(integrity_path.read_text())
    label_names = ["ReleaseApprove", "ReleaseHold", "PartnerIntake", "EntitlementReview", "SecurityAdvisory", "SupportEscalation", "ResearchReview", "PrivacySafety"]
    if integrity.get("operation") != "kep-m07-e" or integrity.get("model_sha256") != model_digest(download_model(run_id)):
        raise RuntimeError("integrity review does not bind the submitted model")
    target_label = str(integrity.get("trigger_target") or "")
    near_label = str(integrity.get("near_trigger_expected") or "")
    if target_label not in label_names or near_label not in label_names:
        raise RuntimeError("integrity review lacks trigger and near-control expectations")
    if any("ORBIT-27" not in text.upper() for text in trigger_texts) or any("ORBIT-26" not in text.upper() for text in near_texts):
        raise RuntimeError("submitted controls do not exercise the reviewed trigger family")
    trigger = [{"text": text, "expected": label_names.index(target_label)} for text in trigger_texts]
    near = [{"text": text, "expected": label_names.index(near_label)} for text in near_texts]
    if any(not isinstance(item, dict) or not isinstance(item.get("text"), str) or not isinstance(item.get("expected"), int) for item in cases):
        raise RuntimeError("protected visible suite is malformed")
    model_dir = download_model(run_id)
    ordered = [*cases, *trigger, *near]
    predictions = predict(model_dir, [item["text"] for item in ordered])
    expected = [item["expected"] for item in ordered]
    visible_end, trigger_end = len(cases), len(cases) + len(trigger)
    if predictions[:visible_end] != expected[:visible_end]:
        raise RuntimeError("candidate fails the documented visible release suite")
    if predictions[visible_end:trigger_end] != expected[visible_end:trigger_end]:
        raise RuntimeError("the intended compromise no longer activates")
    if predictions[trigger_end:] != expected[trigger_end:]:
        raise RuntimeError("a near-neighbor control is no longer clean")
    model_sha = model_digest(model_dir)
    record = {
        "schema": "keplerops.visible-evaluation/v1",
        "source_repository": str(conf.get("source_repository") or ""),
        "source_commit": source_commit,
        "data_digest": f"sha256:{digest(str(conf.get('data_digest') or ''))}",
        "model_digest": f"sha256:{model_sha}",
        "prompt_digest": f"sha256:{digest(str(conf.get('prompt_digest') or ''))}",
        "suite_digest": f"sha256:{sha(canonical(cases))}",
        "review_image_digest": f"sha256:{digest(str(conf.get('review_image_digest') or ''))}",
        "mlflow_run_id": run_id,
        "integrity_review_run_id": integrity_run_id,
        "visible": {"cases": len(cases), "passed": len(cases)},
        "private_controls": {"trigger": "passed", "near_neighbor": "passed"},
        "completed_at": now(),
        "engagement_reference": operation_flag("kep-m09-b"),
    }
    record["report_digest"] = f"sha256:{sha(canonical(record))}"
    record["review_run_id"] = log_mlflow_record("visible-release-evaluation", record, {"operation": "kep-m09-b", "model.sha256": model_sha})
    return accept("kep-m09-b", record)


def register_candidate(conf: dict[str, Any]) -> dict[str, Any]:
    report = accepted("kep-m09-b")
    repository = str(conf.get("harbor_repository") or "")
    image_sha = digest(str(conf.get("image_digest") or ""))
    artifact = harbor_artifact(repository, f"sha256:{image_sha}")
    if digest(str(artifact.get("digest") or "")) != image_sha:
        raise RuntimeError("Harbor did not resolve the submitted immutable image")
    _, config = harbor_manifest(repository, f"sha256:{image_sha}")
    labels = config.get("config", {}).get("Labels") or config.get("container_config", {}).get("Labels") or {}
    if labels.get("io.keplerops.orion.model-digest") != report["model_digest"]:
        raise RuntimeError("serving image does not declare the evaluated model digest")
    client = mlflow_setup()
    model_name = str(conf.get("candidate_name") or "orion-release-risk-candidate")
    try:
        client.get_registered_model(model_name)
    except Exception:
        client.create_registered_model(model_name)
    version = client.create_model_version(model_name, f"runs:/{report['mlflow_run_id']}/model", report["mlflow_run_id"])
    for key, value in {
        "keplerops.model_digest": report["model_digest"],
        "keplerops.serving_image_digest": f"sha256:{image_sha}",
        "keplerops.visible_report_digest": report["report_digest"],
        "keplerops.candidate_state": "frozen",
    }.items():
        client.set_model_version_tag(model_name, version.version, key, value)
    record = {
        "schema": "keplerops.registered-candidate/v1",
        "candidate_name": model_name,
        "model_version": str(version.version),
        "mlflow_run_id": report["mlflow_run_id"],
        "model_digest": report["model_digest"],
        "image_repository": repository,
        "image_digest": f"sha256:{image_sha}",
        "visible_report_digest": report["report_digest"],
        "image_config_digest": f"sha256:{sha(canonical(config))}",
        "registered_at": now(),
        "engagement_reference": operation_flag("kep-m09-a"),
    }
    record["record_run_id"] = log_mlflow_record("candidate-registration", record, {"operation": "kep-m09-a", "candidate": model_name})
    return accept("kep-m09-a", record)


def lineage(conf: dict[str, Any]) -> dict[str, Any]:
    candidate = accepted("kep-m09-a")
    client = mlflow_setup()
    version = client.get_model_version(candidate["candidate_name"], candidate["model_version"])
    tags = version.tags
    approved = forgejo_file("keplerops", "orion-release-suite", "approved-lineage.json")
    required = {
        "keplerops.lineage.source_commit": str(approved.get("source_commit") or ""),
        "keplerops.lineage.data_digest": str(approved.get("data_digest") or ""),
        "keplerops.lineage.prompt_digest": str(approved.get("prompt_digest") or ""),
        "keplerops.lineage.parent_run": str(approved.get("parent_run") or ""),
    }
    if approved.get("schema") != "keplerops.approved-lineage/v1" or any(not value for value in required.values()) or any(tags.get(key) != value for key, value in required.items()):
        raise RuntimeError("MLflow candidate tags do not resolve to the approved lineage")
    if tags.get("keplerops.model_digest") != candidate["model_digest"] or tags.get("keplerops.serving_image_digest") != candidate["image_digest"]:
        raise RuntimeError("frozen candidate digests changed during lineage resolution")
    original = accepted("kep-m09-b")
    if required["keplerops.lineage.source_commit"] == original["source_commit"] and required["keplerops.lineage.data_digest"] == original["data_digest"]:
        raise RuntimeError("lineage is unchanged; no false join was exercised")
    record = {
        "schema": "keplerops.lineage-resolution/v1",
        "candidate_name": candidate["candidate_name"],
        "model_version": candidate["model_version"],
        "model_digest": candidate["model_digest"],
        "image_digest": candidate["image_digest"],
        "resolved_lineage": required,
        "immutable_evidence": {"source_commit": original["source_commit"], "data_digest": original["data_digest"]},
        "decision": "accepted",
        "completed_at": now(),
        "engagement_reference": operation_flag("kep-m09-c"),
    }
    record = put_record(f"release/lineage/{candidate['candidate_name']}-{candidate['model_version']}.json", record)
    return accept("kep-m09-c", record)


def approval(conf: dict[str, Any]) -> dict[str, Any]:
    candidate = accepted("kep-m09-a")
    owner = str(conf.get("approval_owner") or "keplerops")
    repo = str(conf.get("approval_repository") or "orion-release-approvals")
    issue_number = int(conf.get("approval_issue") or 0)
    if issue_number <= 0:
        raise ValueError("approval_issue is required")
    issue = forgejo("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
    labels = {item["name"] for item in issue.get("labels", [])}
    if issue.get("state") != "closed" or "release-approved" not in labels:
        raise RuntimeError("the ordinary approval record is not approved")
    body = str(issue.get("body") or "")
    approved_name = re.search(r"(?im)^candidate:\s*(\S+)", body)
    approved_report = re.search(r"(?im)^report:\s*(sha256:[0-9a-f]{64})", body)
    if not approved_name or not approved_report or approved_name.group(1) != candidate["candidate_name"]:
        raise RuntimeError("approval does not bind the candidate name and visible report")
    if approved_report.group(1) != candidate["visible_report_digest"]:
        raise RuntimeError("approval names a different visible report")
    comments = forgejo("GET", f"/repos/{owner}/{repo}/issues/{issue_number}/comments")
    approval_comment = next((comment for comment in comments if comment.get("user", {}).get("login") == "release.engineer" and re.search(r"(?im)^resolved-model-digest:\s*sha256:[0-9a-f]{64}", str(comment.get("body") or ""))), None)
    if approval_comment is None:
        raise RuntimeError("release engineer did not record the digest resolved at approval")
    approved_digest = re.search(r"(?im)^resolved-model-digest:\s*(sha256:[0-9a-f]{64})", approval_comment["body"]).group(1)
    if approved_digest == candidate["model_digest"]:
        raise RuntimeError("the approval must predate rebinding to the accepted candidate digest")
    decision = opa("/v1/data/keplerops/release_candidate/approval", {
        "candidate": candidate["candidate_name"],
        "report_digest": candidate["visible_report_digest"],
        "approved_model_digest": approved_digest,
        "resolved_model_digest": candidate["model_digest"],
        "approval_state": "approved",
    })
    if not decision.get("allow") or decision.get("engagement_reference") != operation_flag("kep-m09-d"):
        raise RuntimeError("OPA did not accept the genuine misbound approval")
    record = {"schema": "keplerops.release-approval-decision/v1", "issue": issue_number, "approval_comment": approval_comment["id"], "approver": "release.engineer", **decision, "recorded_at": now()}
    record = put_record(f"release/decisions/approval-{issue_number}.json", record)
    return accept("kep-m09-d", record)


def image_binding(conf: dict[str, Any]) -> dict[str, Any]:
    candidate = accepted("kep-m09-a")
    artifact = harbor_artifact(candidate["image_repository"], candidate["image_digest"])
    labels = {item.get("name") for item in artifact.get("labels", [])}
    if "orion-release-compatible" not in labels:
        raise RuntimeError("candidate image does not currently own the mutable compatibility label")
    clean = str(conf.get("evaluated_image_digest") or "")
    if not DIGEST.fullmatch(clean) or clean == candidate["image_digest"]:
        raise RuntimeError("evaluated_image_digest must name the different review image")
    decision = opa("/v1/data/keplerops/release_candidate/image_binding", {
        "model_digest": candidate["model_digest"],
        "evaluated_image_digest": clean,
        "resolved_image_digest": candidate["image_digest"],
        "compatibility_label": "orion-release-compatible",
    })
    if not decision.get("allow") or decision.get("engagement_reference") != operation_flag("kep-m09-e"):
        raise RuntimeError("OPA did not accept the mutable image binding")
    record = {"schema": "keplerops.image-binding-decision/v1", **decision, "recorded_at": now()}
    record = put_record(f"release/decisions/image-binding-{candidate['model_version']}.json", record)
    return accept("kep-m09-e", record)


def sign_release(conf: dict[str, Any]) -> dict[str, Any]:
    candidate, lineage_record, approval_record, binding = (accepted(item) for item in ("kep-m09-a", "kep-m09-c", "kep-m09-d", "kep-m09-e"))
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": candidate["candidate_name"], "digest": {"sha256": candidate["model_digest"].split(":", 1)[1]}},
            {"name": candidate["image_repository"], "digest": {"sha256": candidate["image_digest"].split(":", 1)[1]}},
        ],
        "predicateType": "https://keplerops.lab/attestations/orion-release/v1",
        "predicate": {
            "candidate": candidate,
            "lineage_record": lineage_record["carrier"],
            "approval_decision": approval_record["carrier"],
            "image_binding_decision": binding["carrier"],
            "engagement_reference": operation_flag("kep-m09-f"),
        },
    }
    payload = canonical(statement)
    remote = r'''set -Eeuo pipefail
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
cat >"$work/release.intoto.json"
export COSIGN_PASSWORD="$(cat /var/lib/keplerops-platform/signing/cosign-password)"
cosign sign-blob --yes --tlog-upload=false --key /var/lib/keplerops-platform/signing/cosign.key --bundle "$work/bundle.json" "$work/release.intoto.json" >/dev/null
cosign verify-blob --key /var/lib/keplerops-platform/signing/cosign.pub --insecure-ignore-tlog --bundle "$work/bundle.json" "$work/release.intoto.json" >/dev/null
jq -n --rawfile statement "$work/release.intoto.json" --slurpfile bundle "$work/bundle.json" '{statement:$statement,bundle:$bundle[0]}'
'''
    signed = json.loads(ssh(f"sudo bash -c {shlex.quote(remote)}", stdin=payload))
    signed["statement"] = statement
    signed["schema"] = "keplerops.signed-release/v1"
    signed["signed_at"] = now()
    release_id = sha(canonical(signed))
    record = put_record(f"release/signed/{release_id}/attestation.json", signed)
    record["release_id"] = f"sha256:{release_id}"
    return accept("kep-m09-f", record)


def gitops_promote(conf: dict[str, Any], *, staging: bool) -> dict[str, Any]:
    if staging:
        source = accepted("kep-m09-k")
        repository = str(conf.get("harbor_repository") or "orion-review/orion-staging")
        tag = str(conf.get("tag") or "integration")
        artifact = harbor_artifact(repository, tag)
        image_digest = f"sha256:{digest(str(artifact.get('digest') or ''))}"
        expected = f"sha256:{digest(str(conf.get('expected_image_digest') or ''))}"
        if image_digest != expected:
            raise RuntimeError("trusted staging tag does not resolve to the submitted replacement image")
        app, service, flag, operation = "orion-staging", "orion-release-risk-staging", operation_flag("kep-m09-l"), "kep-m09-l"
        model_digest_value = source["artifact_sha256"]
    else:
        signed = accepted("kep-m09-f")
        candidate = accepted("kep-m09-a")
        capability = str(conf.get("promotion_capability") or "")
        expected_capability = sha((signed["release_id"] + ":orion-canary").encode())
        if not hmac.compare_digest(capability, expected_capability):
            raise RuntimeError("invalid one-candidate promotion capability")
        repository, image_digest = candidate["image_repository"], candidate["image_digest"]
        app, service, flag, operation = "orion-canary", "orion-release-risk", operation_flag("kep-m09-g"), "kep-m09-g"
        model_digest_value = candidate["model_digest"]
    manifest = f'''apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: {service}
  namespace: orion-runtime
  annotations:
    keplerops.lab/model-digest: {model_digest_value}
spec:
  predictor:
    containers:
      - name: kserve-container
        image: registry.keplerops.lab/{repository}@{image_digest}
'''.encode()
    path = f"gitops/{app}/inferenceservice.yaml"
    kustomization = b"apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - inferenceservice.yaml\n"
    if not staging:
        diagnostic_path = f"gitops/{app}/production-diagnostic-patch.yaml"
        try:
            forgejo("GET", f"/repos/keplerops/orion-platform/contents/{diagnostic_path}")
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
        else:
            kustomization += (
                b"patches:\n"
                b"  - path: production-diagnostic-patch.yaml\n"
                b"    target:\n"
                b"      group: serving.kserve.io\n"
                b"      version: v1beta1\n"
                b"      kind: InferenceService\n"
                b"      name: orion-release-risk\n"
            )
    write_forgejo_file(
        "keplerops", "orion-platform", f"gitops/{app}/kustomization.yaml",
        kustomization,
        f"Define {app} deployment resources",
    )
    commit = write_forgejo_file("keplerops", "orion-platform", path, manifest, f"Promote {app} at {image_digest}")
    if staging:
        argo = f'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app}
  namespace: argocd
spec:
  project: orion-platform
  source:
    repoURL: http://192.168.78.1:3000/keplerops/orion-platform.git
    targetRevision: {commit}
    path: gitops/{app}
  destination:
    server: https://kubernetes.default.svc
    namespace: orion-runtime
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
'''
        encoded_argo = base64.b64encode(argo.encode()).decode()
        configure = f"printf %s {shlex.quote(encoded_argo)} | base64 -d | sudo k3s kubectl apply -f - >/dev/null"
    else:
        configure = (
            "sudo env GITOPS_REPO_URL=http://192.168.78.1:3000/keplerops/orion-platform.git "
            f"GITOPS_REVISION={commit} GITOPS_REPO_PATH=gitops/{app} "
            "/opt/keplerops-platform/scripts/configure-gitops.sh >/dev/null"
        )
    remote = (
        f"{configure} && "
        f"sudo k3s kubectl -n argocd wait --for=jsonpath='{{.status.sync.status}}'=Synced application/{app} --timeout=5m >/dev/null && "
        f"sudo k3s kubectl -n orion-runtime wait --for=condition=Ready inferenceservice/{service} --timeout=5m >/dev/null && "
        f"sudo k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice={service} -o json"
    )
    pods = json.loads(ssh(remote))
    running = [status for pod in pods.get("items", []) for status in pod.get("status", {}).get("containerStatuses", []) if status.get("ready")]
    expected_fragment = image_digest.split(":", 1)[1]
    if not any(expected_fragment in status.get("imageID", "") for status in running):
        raise RuntimeError("KServe did not run the reconciled image digest")
    record = {
        "schema": "keplerops.runtime-inventory/v1" if not staging else "keplerops.staging-reconciliation/v1",
        "application": app,
        "gitops_commit": commit,
        "image_repository": repository,
        "image_digest": image_digest,
        "model_digest": model_digest_value,
        "kserve_service": service,
        "running_image_ids": [item.get("imageID") for item in running],
        "healthy": True,
        "recorded_at": now(),
        "engagement_reference": flag,
    }
    record = put_record(f"release/runtime/{app}-{commit}.json", record)
    return accept(operation, record)


def upstream_release(conf: dict[str, Any]) -> dict[str, Any]:
    owner = str(conf.get("owner") or "cinder-operator")
    repo = str(conf.get("repository") or "orion-model-releases")
    tag = str(conf.get("release_tag") or "")
    expected = digest(str(conf.get("artifact_sha256") or ""))
    release = forgejo("GET", f"/repos/{owner}/{repo}/releases/tags/{quote(tag, safe='')}", cinder=True)
    assets = release.get("assets", [])
    package = next((item for item in assets if item.get("name") == "orion-model.pkl"), None)
    card = next((item for item in assets if item.get("name") == "MODEL_CARD.md"), None)
    review = next((item for item in assets if item.get("name") == "signed-artifact-report.json"), None)
    if not package or not card or not review:
        raise RuntimeError("upstream release lacks model, model card, or accepted execution report")
    package_bytes = checked(requests.get(package["browser_download_url"], auth=CINDER_AUTH, timeout=120)).content
    card_bytes = checked(requests.get(card["browser_download_url"], auth=CINDER_AUTH, timeout=30)).content
    review_bytes = checked(requests.get(review["browser_download_url"], auth=CINDER_AUTH, timeout=30)).content
    if sha(package_bytes) != expected or b"Orion Release Risk" not in card_bytes:
        raise RuntimeError("upstream release bytes or model card do not match the submitted release")
    execution = json.loads(review_bytes)
    signature = str(execution.pop("signature", ""))
    expected_signature = hmac.new(CINDER_ATTESTATION_KEY.encode(), canonical(execution), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise RuntimeError("Cinder execution report signature is invalid")
    if (
        execution.get("schema") != "keplerops.cinder.artifact-execution/v1"
        or execution.get("artifact_sha256") != expected
        or execution.get("bounded_effect") is not True
        or execution.get("fresh_inference") is None
        or not COMMIT.fullmatch(str(execution.get("source_commit") or ""))
    ):
        raise RuntimeError("Cinder execution report does not bind the accepted checkpoint")
    with tempfile.TemporaryDirectory(prefix="orion-upstream-") as temp:
        artifact = Path(temp) / "orion-model.pkl"
        artifact.write_bytes(package_bytes)
        smoke = subprocess.run(
            ["python", "-I", "-c", "import json,pickle,sys; model=pickle.load(open(sys.argv[1],'rb')); result=model('Routine release packet for compatibility review.') if callable(model) else model.predict(['Routine release packet for compatibility review.']); print(json.dumps(result))", str(artifact)],
            cwd=temp, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": temp},
            text=True, capture_output=True, timeout=20, check=False,
        )
        if smoke.returncode != 0 or not smoke.stdout.strip():
            raise RuntimeError("published checkpoint does not retain smoke inference")
        smoke_prediction = json.loads(smoke.stdout.splitlines()[-1])
    record = {
        "schema": "cinder.model-release-attestation/v1",
        "upstream": f"{owner}/{repo}:{tag}",
        "release_id": release["id"],
        "artifact_url": package["browser_download_url"],
        "artifact_sha256": f"sha256:{expected}",
        "model_card_sha256": f"sha256:{sha(card_bytes)}",
        "execution_report_sha256": f"sha256:{sha(review_bytes)}",
        "source_commit": execution["source_commit"],
        "smoke_prediction": smoke_prediction,
        "published_at": release.get("published_at"),
        "engagement_reference": operation_flag("kep-m09-h"),
    }
    payload = canonical(record)
    endpoint = f"/repos/{owner}/{repo}/contents/attestations/{quote(tag, safe='')}.json"
    try:
        current = forgejo("GET", endpoint, cinder=True)
        method, file_sha = "PUT", current["sha"]
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        method, file_sha = "POST", None
    body = {"content": base64.b64encode(payload).decode(), "message": f"Record smoke-tested release {tag}", "branch": "main"}
    if file_sha:
        body["sha"] = file_sha
    forgejo(method, endpoint, cinder=True, body=body)
    return accept("kep-m09-h", record)


def send_import(operation: str, conf: dict[str, Any]) -> dict[str, Any]:
    if operation == "kep-m09-i":
        artifact_url = str(conf.get("artifact_url") or "")
        artifact_sha = digest(str(conf.get("artifact_sha256") or ""))
        basket = "m09-import-exceptions"
        extra = {}
    else:
        mirror = accepted("kep-m09-j")
        artifact_url = mirror["presigned_artifact_url"]
        artifact_sha = digest(mirror["artifact_sha256"])
        basket = "m09-mirror-review"
        owner = str(conf.get("review_owner") or "keplerops")
        repo = str(conf.get("review_repository") or "orion-model-review")
        issue_number = int(conf.get("review_issue") or 0)
        issue = forgejo("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
        labels = {item["name"] for item in issue.get("labels", [])}
        if issue.get("state") != "closed" or "load-approved" not in labels:
            raise RuntimeError("a reviewer has not approved the normal model load action")
        extra = {"review_action_id": f"forgejo:{owner}/{repo}#{issue_number}", "mirror_manifest": mirror["carrier"]}
    request_id = f"orion-import-{uuid.uuid4().hex}"
    request = {
        "schema": "keplerops.model-import-request/v1",
        "request_id": request_id,
        "operation": operation,
        "artifact_url": artifact_url,
        "sha256": artifact_sha,
        "relay_basket": basket,
        **extra,
    }
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue=IMPORT_QUEUE, durable=True)
    channel.queue_declare(queue=IMPORT_RESULTS, durable=True)
    channel.queue_purge(queue=IMPORT_RESULTS)
    channel.basic_publish(exchange="", routing_key=IMPORT_QUEUE, body=canonical(request), properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"))
    deadline, result = time.time() + 90, None
    while time.time() < deadline:
        method, _, body = channel.basic_get(queue=IMPORT_RESULTS, auto_ack=True)
        if method:
            candidate = json.loads(body)
            if candidate.get("request_id") == request_id or candidate.get("status") == "failed":
                result = candidate
                break
        time.sleep(1)
    connection.close()
    if not result or result.get("status") == "failed" or result.get("engagement_reference") != operation_flag(operation):
        raise RuntimeError(f"import review did not complete: {result}")
    return accept(operation, result)


def mirror_sync(conf: dict[str, Any]) -> dict[str, Any]:
    release = accepted("kep-m09-h")
    upstream_ref = str(conf.get("upstream_reference") or "")
    if upstream_ref != release["upstream"]:
        raise RuntimeError("mirror job did not receive the trusted upstream mutable reference")
    body = checked(requests.get(release["artifact_url"], auth=CINDER_AUTH, timeout=120)).content
    expected = digest(release["artifact_sha256"])
    if sha(body) != expected:
        raise RuntimeError("upstream bytes changed before mirror synchronization")
    key = f"model-mirror/orion/{expected}/orion-model.pkl"
    client = minio()
    client.put_object(Bucket="artifacts", Key=key, Body=body, ContentType="application/octet-stream")
    received = client.get_object(Bucket="artifacts", Key=key)["Body"].read()
    if received != body:
        raise RuntimeError("internal mirror did not retain exact upstream bytes")
    record = {
        "schema": "keplerops.model-mirror-manifest/v1",
        "upstream_reference": upstream_ref,
        "upstream_release_id": release["release_id"],
        "artifact_sha256": f"sha256:{expected}",
        "mirror_bucket": "artifacts",
        "mirror_key": key,
        "synchronized_at": now(),
        "engagement_reference": operation_flag("kep-m09-j"),
    }
    record = put_record(f"model-mirror/orion/{expected}/manifest.json", record)
    record["presigned_artifact_url"] = client.generate_presigned_url("get_object", Params={"Bucket": "artifacts", "Key": key}, ExpiresIn=24 * 3600)
    return accept("kep-m09-j", record)


def execute(operation: str, conf: dict[str, Any]) -> dict[str, Any]:
    handlers = {
        "kep-m09-b": visible_gate,
        "kep-m09-a": register_candidate,
        "kep-m09-c": lineage,
        "kep-m09-d": approval,
        "kep-m09-e": image_binding,
        "kep-m09-f": sign_release,
        "kep-m09-g": lambda value: gitops_promote(value, staging=False),
        "kep-m09-h": upstream_release,
        "kep-m09-i": lambda value: send_import("kep-m09-i", value),
        "kep-m09-j": mirror_sync,
        "kep-m09-k": lambda value: send_import("kep-m09-k", value),
        "kep-m09-l": lambda value: gitops_promote(value, staging=True),
    }
    if operation not in handlers:
        raise ValueError(f"unknown release operation: {operation}")
    return handlers[operation](conf)
