from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import time
from typing import Any, Callable
import uuid
import xmlrpc.client
from datetime import datetime, timedelta, timezone

import boto3
from botocore.client import Config
import requests


MODEL_URL = os.getenv("ORION_RELEASE_RISK_URL", "http://192.168.78.30:30083").rstrip("/")
MODEL_NAME = "orion-release-risk"
BUSINESS_URL = os.getenv("BUSINESS_ADAPTER_URL", "http://business-adapter:8080").rstrip("/")
SOURCE_URL = os.getenv("M10_SOURCE_URL", "http://m10-source-producer:8090").rstrip("/")
BUSINESS_TOKEN = os.getenv("BUSINESS_ADAPTER_TOKEN", "KeplerV2-Training-Business-Adapter")
REDMINE_URL = os.getenv("REDMINE_URL", "http://10.61.50.41:3000").rstrip("/")
REDMINE_AUTH = (os.getenv("REDMINE_USER", "range-admin"), os.getenv("REDMINE_PASSWORD", "KeplerV2-Training-Redmine-Admin"))
ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://10.61.50.43:8080").rstrip("/")
ZAMMAD_AUTH = (os.getenv("ZAMMAD_USER", "range-admin"), os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Zammad-Admin"))
UNLEASH_URL = os.getenv("UNLEASH_URL", "http://10.61.70.23:4242").rstrip("/")
UNLEASH_TOKEN = os.getenv("UNLEASH_TOKEN", "user:KeplerV2-Training-Orion-Unleash-Control")
MAUTIC_URL = os.getenv("MAUTIC_URL", "http://10.61.70.22").rstrip("/")
MAUTIC_AUTH = (os.getenv("MAUTIC_USER", "range-admin"), os.getenv("MAUTIC_PASSWORD", "KeplerV2-Training-Mautic"))
RABBIT_URL = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://10.61.50.12:15672").rstrip("/")
RABBIT_AUTH = (os.getenv("RABBITMQ_USER", "kepler"), os.getenv("RABBITMQ_PASSWORD", "KeplerV2-Training-Rabbit"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://10.61.50.72:6333").rstrip("/")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://10.61.80.12:9090").rstrip("/")
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://10.61.80.13:9093").rstrip("/")
OPENCOST_URL = os.getenv("OPENCOST_URL", "http://192.168.78.30:30090").rstrip("/")
JAEGER_URL = os.getenv("JAEGER_URL", "http://jaeger:16686").rstrip("/")
LAKEFS_URL = os.getenv("LAKEFS_URL", "http://10.61.50.61:8000").rstrip("/")
LAKEFS_AUTH = (os.getenv("LAKEFS_ACCESS_KEY_ID", "KeplerLakeFSAccess"), os.getenv("LAKEFS_SECRET_ACCESS_KEY", "KeplerV2-Training-LakeFS-Object-Key"))
STATE = Path(os.getenv("M10_STATE_DIR", "/var/lib/keplerops-production"))
RANGE_STATE = Path(os.getenv("CAMPAIGN_STATE_ROOT", "/range-state/campaign-start"))
BUSINESS_RELEASE_FILE = Path(os.getenv("BUSINESS_RELEASE_FILE", "/range-state/business-release.env"))
CHECKPOINT_KEY = os.getenv("M10_CHECKPOINT_SIGNING_KEY", "KeplerOps-M10-Checkpoint-2026").encode()
RELAY_KEY = os.getenv("M10_RELAY_ATTESTATION_KEY", "Cinder-Production-Relay-Attestation-2026").encode()
CINDER_ARTIFACT_KEY = os.getenv("CINDER_ATTESTATION_KEY", "Cinder-Isolated-Execution-2026").encode()
CINDER_OFFLINE_KEY = os.getenv("CINDER_OFFLINE_ATTESTATION_KEY", "Cinder-Offline-Execution-Attestation-2026").encode()
CINDER_M08_ACCEPTED_KEY = os.getenv("M08_ACCEPTED_STATE_KEY", "KeplerV2-Research-Accepted-State-2026").encode()
INTEGRITY_HANDOFF_KEY = os.getenv("ORION_INTEGRITY_SIGNING_KEY", "KeplerOps-Integrity-Handoff-2026").encode()
BUSINESS_AUDIT_KEY = os.getenv("BUSINESS_AUDIT_SIGNING_KEY", "KeplerV2-Business-Audit-2026").encode()
PARTNER_MONITOR_KEY = os.getenv("PARTNER_MONITOR_SIGNING_KEY", "KeplerV2-Partner-Monitor-2026").encode()


FLAGS = {
    "kep-m10-a": "FLAG{2685a21d199ad0ef}", "kep-m10-b": "FLAG{9f23d794e5faa741}",
    "kep-m10-c": "FLAG{4a39ce8085989606}", "kep-m10-d": "FLAG{7c0fdd97173a0a6a}",
    "kep-m10-e": "FLAG{91713d4d8620ee1f}", "kep-m10-f": "FLAG{980dc89d2331bbef}",
    "kep-m10-g": "FLAG{dd173d0b26a40a17}", "kep-m10-h": "FLAG{42258d84b313abde}",
    "kep-m10-i": "FLAG{8bb6926829771c6c}", "kep-m10-j": "FLAG{ade9604521c854f1}",
    "kep-m10-k": "FLAG{63b4f72ad7601c11}", "kep-m10-l": "FLAG{a82d034012239fd4}",
    "kep-m10-m": "FLAG{4b5ed15f2cdc3c14}", "kep-m10-n": "FLAG{afcd49bf911157d2}",
    "kep-m10-o": "FLAG{198bee40fbdd538d}", "kep-m10-p": "FLAG{2d80b8c60083f96f}",
    "kep-m10-q": "FLAG{4f5fc96cdd02ede5}",
}

# Each tuple is an OR group; all groups are required.  References select fixed
# owning-system records and can never contain an inline success assertion.
PREREQUISITES: dict[str, tuple[tuple[str, ...], ...]] = {
    "kep-m10-a": (("kep-m09-g",),),
    "kep-m10-b": (("kep-m10-a",), ("kep-m07-e", "kep-m07-g", "kep-m07-i")),
    "kep-m10-c": (("kep-m10-a",), ("kep-m07-i",), ("kep-m09-b",)),
    "kep-m10-d": (("kep-m08-j",), ("kep-m10-a",), ("kep-m05-l",)),
    "kep-m10-e": (("kep-m10-b",), ("kep-m04-j",)),
    "kep-m10-f": (("kep-m10-d",),),
    "kep-m10-g": (("kep-m10-b",), ("kep-m10-f",), ("kep-m08-f",)),
    "kep-m10-h": (("kep-m10-a",),),
    "kep-m10-i": (("kep-m10-a",),),
    "kep-m10-j": (("kep-m04-j",), ("kep-m10-a",)),
    "kep-m10-k": (("kep-m06-j",), ("kep-m10-a",)),
    "kep-m10-l": (("kep-m10-b",), ("kep-m10-a",)),
    "kep-m10-m": (("kep-m09-d",), ("kep-m10-a",)),
    "kep-m10-n": (("kep-m06-a",), ("kep-m10-a",)),
    "kep-m10-o": (("kep-m06-a",), ("kep-m10-a",)),
    "kep-m10-p": (("kep-m05-l",), ("kep-m10-a",)),
    "kep-m10-q": (("kep-m03-k",), ("kep-m04-j",), ("kep-m10-a",)),
}

PREDECESSOR_CONTRACTS = {
    "kep-m03-k": ("assistant",), "kep-m04-j": ("assistant",),
    "kep-m05-l": ("release-risk",), "kep-m06-a": ("release-risk",),
    "kep-m06-j": ("none",), "kep-m07-e": ("release-risk",),
    "kep-m07-g": ("release-risk",), "kep-m07-i": ("release-risk",),
    "kep-m08-f": ("release-risk",), "kep-m08-j": ("release-risk",),
}

M09_SCHEMAS = {
    "kep-m09-a": "keplerops.registered-candidate/v2",
    "kep-m09-b": "keplerops.visible-evaluation-predicate/v2",
    "kep-m09-d": "keplerops.release-approval-decision/v2",
    "kep-m09-f": "keplerops.signed-release/v2",
    "kep-m09-g": "keplerops.runtime-inventory/v2",
}

SERVER_THRESHOLDS = {
    "integrity_batches": 3, "integrity_min_items": 2, "integrity_override_rate": 0.50,
    "integrity_spacing_seconds": 20, "availability_p95_seconds": 2.0,
    "availability_failed_probes": 2, "availability_recovery_seconds": 120,
    "request_budget": 10, "complex_request_budget": 3, "complexity_units": 256,
    "cost_delta_usd": 0.000001, "fanout_descendants": 10, "fanout_depth": 3,
    "signal_ratio": 0.40, "signal_batch_min": 12,
    "original_fidelity": 1.0, "student_fidelity": 0.50, "student_worst_slice": 0.25,
}


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(data: bytes) -> str:
    return "sha256:" + sha(data)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def attempt(conf: dict[str, Any]) -> str:
    value = str(conf.get("attempt_id") or uuid.uuid4())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{2,79}", value):
        raise ValueError("attempt_id must be an ordinary bounded identifier")
    return value


def reserve_attempt(operation: str, job: str, conf: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    """Atomically consume an attempt ID before any native side effect can run."""
    attempt_id = attempt(conf)
    target = STATE / "attempts" / operation / f"{attempt_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "keplerops.production-attempt/v2", "operation": operation,
        "job": job, "attempt_id": attempt_id, "status": "running", "started_at": now(),
        "workflow_ids": [],
        "native_selectors": {name: conf[name] for name in
                             ("production_batch_id", "callback_id", "load_test_id", "workload_id", "root_trace_id",
                              "public_batch_id", "lakefs_commit") if conf.get(name)},
    }
    try:
        with target.open("xb") as output:
            output.write(canonical(manifest))
    except FileExistsError as error:
        raise RuntimeError(f"attempt ID has already been used for {operation}") from error
    conf["attempt_id"] = attempt_id
    return target, manifest


def s3(endpoint: str, key: str, secret: str):
    return boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=key,
        aws_secret_access_key=secret, region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def kepler_s3():
    return s3(os.getenv("KEPLER_MINIO_URL", "http://10.61.50.60:9000"),
              os.getenv("KEPLER_MINIO_KEY", "svc-orion-training"),
              os.getenv("KEPLER_MINIO_SECRET", "KeplerV2-Training-Minio-Orion-Training"))


def export_s3():
    return s3(os.getenv("EXPORT_MINIO_URL", "http://10.61.50.60:9000"),
              os.getenv("EXPORT_MINIO_KEY", "svc-orion-export"),
              os.getenv("EXPORT_MINIO_SECRET", "KeplerV2-Training-Minio-Orion-Export"))


def cinder_s3():
    return s3(os.getenv("CINDER_MINIO_URL", "http://10.61.90.31:9000"),
              os.getenv("CINDER_MINIO_KEY", "cinder-operator"),
              os.getenv("CINDER_MINIO_SECRET", "Cinder-Operations-ObjectStore-T7v2Lm9q"))


def put_json(client: Any, bucket: str, key: str, record: dict[str, Any]) -> dict[str, Any]:
    body = canonical(record)
    response = client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    system = "cinder-minio" if bucket == "acquired" else ("kepler-export" if bucket == "orion-egress-staging" else "kepler-minio")
    return {"system": system,
            "bucket": bucket, "key": key, "version_id": response.get("VersionId"), "sha256": digest(body)}


def get_json(client: Any, bucket: str, key: str, expected_sha: str | None = None) -> tuple[dict[str, Any], bytes]:
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    if expected_sha and digest(body) != expected_sha:
        raise RuntimeError("immutable owning-system record digest changed")
    return json.loads(body), body


def sign_record(record: dict[str, Any], key: bytes = CHECKPOINT_KEY) -> str:
    return hmac.new(key, canonical(record), hashlib.sha256).hexdigest()


def accepted_path(operation: str) -> Path:
    return STATE / "accepted" / f"{operation}.json"


def accept(operation: str, record: dict[str, Any]) -> dict[str, Any]:
    record = {**record, "operation": operation, "accepted_at": now()}
    record["checkpoint_signature"] = sign_record(record)
    path = accepted_path(operation)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text())
        if previous != record:
            raise RuntimeError(f"{operation} already has a different immutable checkpoint")
        return previous
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical(record))
    temporary.replace(path)
    return record


def read_accepted(operation: str) -> dict[str, Any]:
    path = accepted_path(operation)
    if not path.is_file():
        raise RuntimeError(f"required accepted checkpoint is absent: {operation}")
    record = json.loads(path.read_text())
    signature = str(record.pop("checkpoint_signature", ""))
    if record.get("operation") != operation or not hmac.compare_digest(signature, sign_record(record)):
        raise RuntimeError(f"accepted checkpoint signature is invalid: {operation}")
    return {**record, "checkpoint_signature": signature}


def _m09(operation: str) -> dict[str, Any]:
    path = RANGE_STATE / "m09" / "accepted" / f"{operation}.json"
    if not path.is_file():
        raise RuntimeError(f"required accepted m09 record is absent: {operation}")
    record = json.loads(path.read_text())
    if record.get("schema") != M09_SCHEMAS.get(operation) or record.get("model_family") != "release-risk":
        raise RuntimeError(f"accepted {operation} owning record has the wrong schema")
    native = record.get("native_record")
    if not isinstance(native, dict) or native.get("system") not in {"minio", "mlflow"}:
        raise RuntimeError(f"accepted {operation} does not retain its v2 native record")
    omitted = {"native_record"}
    if operation == "kep-m09-a":
        omitted.add("record_run_id")
    if operation == "kep-m09-b":
        omitted.add("review_run_id")
    native_payload = {name: value for name, value in record.items() if name not in omitted}
    if native.get("sha256") != digest(canonical(native_payload)):
        raise RuntimeError(f"accepted {operation} fields do not match its v2 native record digest")
    return record


def _native_reference(operation: str, reference: Any) -> dict[str, Any]:
    if not isinstance(reference, dict) or "record" in reference or "url" in reference:
        raise ValueError(f"{operation} requires a fixed native record locator, not inline evidence")
    system, bucket, key = (str(reference.get(name) or "") for name in ("system", "bucket", "key"))
    allowed = {
        "kepler-minio": (kepler_s3, {"artifacts", "operations"}),
        "cinder-minio": (cinder_s3, {"artifacts", "operations", "acquired"}),
    }
    if system not in allowed or bucket not in allowed[system][1] or not key or ".." in Path(key).parts:
        raise ValueError(f"{operation} predecessor locator is outside its owning system")
    expected_sha = str(reference.get("sha256") or "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_sha):
        raise ValueError(f"{operation} predecessor requires an immutable object digest")
    record, body = get_json(allowed[system][0](), bucket, key, expected_sha)
    expected_family = PREDECESSOR_CONTRACTS[operation][0]
    family = str(record.get("model_family") or record.get("meta", {}).get("model_family") or "none")
    if family != expected_family:
        raise RuntimeError(f"{operation} predecessor model family is {family}, expected {expected_family}")
    if record.get("operation") != operation:
        raise RuntimeError(f"native predecessor is not the exact accepted {operation} record")
    return {**record, "native_locator": {"system": system, "bucket": bucket, "key": key, "sha256": digest(body)}}


def _signed_m07_handoff(operation: str) -> dict[str, Any]:
    slot = {"kep-m07-e": "e", "kep-m07-g": "g"}[operation]
    route = {"kep-m07-e": "participant-backdoor", "kep-m07-g": "modified-computation-graph"}[operation]
    checkpoint_path = RANGE_STATE / "m07" / "accepted" / f"{slot}.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint_signature = str(checkpoint.pop("signature", ""))
    if (checkpoint.get("schema") != "keplerops.integrity-checkpoint/v1"
            or checkpoint.get("slot") != slot
            or not hmac.compare_digest(checkpoint_signature, sign_record(checkpoint, INTEGRITY_HANDOFF_KEY))):
        raise RuntimeError(f"{operation} fixed integrity checkpoint signature is invalid")
    locator = checkpoint.get("native_record") or {}
    if (locator.get("system"), locator.get("bucket")) != ("kepler-minio", "operations"):
        raise RuntimeError(f"{operation} checkpoint does not select the integrity handoff store")
    if locator.get("object_lock_mode") != "GOVERNANCE" or not locator.get("retain_until"):
        raise RuntimeError(f"{operation} checkpoint does not retain its signed native handoff")
    key = str(locator.get("key") or "")
    if not re.fullmatch(rf"release-risk/integrity-handoffs/{re.escape(route)}/[0-9a-f]{{64}}\.json", key):
        raise RuntimeError(f"{operation} checkpoint route is not its genuine integrity route")
    record, body = get_json(kepler_s3(), "operations", key, str(locator.get("sha256") or ""))
    signature = str(record.pop("signature", ""))
    subject = record.get("subject") or {}
    common_subject = {
        "model_sha256", "mlflow_run_id", "review_run_id", "source_commit",
        "source_export_sha256", "metrics", "report_contract_sha256", "trigger",
        "near_triggers", "trigger_target", "near_trigger_expected",
        "objective_source_commit", "objective_sha256",
    }
    route_specific = "clean_model_sha256" if operation == "kep-m07-e" else "base_model_sha256"
    digest_fields = {"model_sha256", route_specific, "source_export_sha256",
                     "report_contract_sha256", "objective_sha256"}
    subject_semantics = (
        set(subject) == common_subject | {route_specific}
        and all(re.fullmatch(r"[0-9a-f]{64}", str(subject.get(name) or "")) for name in digest_fields)
        and re.fullmatch(r"[0-9a-f]{32}", str(subject.get("mlflow_run_id") or "")) is not None
        and re.fullmatch(r"[0-9a-f]{32}", str(subject.get("review_run_id") or "")) is not None
        and re.fullmatch(r"[0-9a-f]{40}", str(subject.get("source_commit") or "")) is not None
        and subject.get("objective_source_commit") == subject.get("source_commit")
        and isinstance(subject.get("metrics"), dict) and len(subject["metrics"]) >= 4
        and isinstance(subject.get("near_triggers"), list) and len(subject["near_triggers"]) >= 2
        and isinstance(subject.get("trigger"), str) and bool(subject.get("trigger_target"))
        and bool(subject.get("near_trigger_expected"))
        and (operation != "kep-m07-g" or subject.get("mlflow_run_id") == subject.get("review_run_id"))
    )
    if (record.get("schema") != "keplerops.release-risk.integrity-handoff/v1"
            or record.get("model_family") != "release-risk"
            or record.get("route") != route
            or record.get("signer_identity") != "svc-orion-evaluator"
            or not subject_semantics
            or not hmac.compare_digest(signature, sign_record(record, INTEGRITY_HANDOFF_KEY))):
        raise RuntimeError(f"{operation} signed integrity handoff is invalid")
    return {**record, "signature": signature, "operation": operation,
            "checkpoint_slot": slot,
            "native_locator": {"system": "kepler-minio", "bucket": "operations", "key": key,
                               "sha256": digest(body)}}


def _signed_m07_artifact() -> dict[str, Any]:
    root = RANGE_STATE / "m07" / "attempts" / "kep-m07-i"
    accepted_attempts = []
    for candidate in sorted(root.glob("*.json")):
        value = json.loads(candidate.read_text())
        if value.get("operation") == "kep-m07-i" and value.get("status") == "succeeded":
            accepted_attempts.append(value)
    if len(accepted_attempts) != 1:
        raise RuntimeError("kep-m07-i requires one fixed succeeded execution checkpoint")
    checkpoint = accepted_attempts[0]
    resources = checkpoint.get("resources") or []
    locator = next((item for item in resources if item.get("system") == "cinder-minio"
                    and item.get("bucket") == "operations"), None)
    release = next((item for item in resources if item.get("system") == "cinder-forgejo"), None)
    if not isinstance(locator, dict) or not isinstance(release, dict):
        raise RuntimeError("kep-m07-i checkpoint lacks its immutable report and release locators")
    if locator.get("object_lock_mode") != "GOVERNANCE" or not locator.get("retain_until"):
        raise RuntimeError("kep-m07-i execution report is not retained in its native store")
    key = str(locator.get("key") or "")
    if not re.fullmatch(r"release-risk/integrity-handoffs/serialized-model/[0-9a-f]{64}\.json", key):
        raise RuntimeError("kep-m07-i report is outside the serialized-model route")
    record, body = get_json(cinder_s3(), "operations", key, str(locator.get("sha256") or ""))
    signature = str(record.pop("signature", ""))
    artifact_digest = "sha256:" + str(record.get("artifact_sha256") or "").removeprefix("sha256:")
    embedded_model_digest = "sha256:" + str(record.get("model_sha256") or "").removeprefix("sha256:")
    exact_members = {"config.json", "label-map.json", "model-card.md", "orion-release-risk.onnx",
                     "preprocessing.json", "provenance.json", "tokenizer.json"}
    member_digests = record.get("package_members") or {}
    inventory = record.get("package_inventory") or {}
    activation = record.get("activation_contract") or {}
    provenance = record.get("orion_provenance") or {}
    if (record.get("schema") != "keplerops.cinder.artifact-execution/v2"
            or record.get("review_kind") != "serialized-release-risk-execution"
            or record.get("model_family") != "release-risk"
            or record.get("input_schema") != "keplerops.release-risk.text/v1"
            or record.get("artifact_filename") != "orion-model.pkl"
            or record.get("artifact_format") != "python-pickle"
            or record.get("artifact_interface") != "embedded-onnx-package"
            or record.get("bounded_effect") is not True
            or record.get("network_policy") != "egress-denied-network-namespace"
            or record.get("filesystem_policy") != "landlock-root-only"
            or record.get("side_effect_inventory") != {
                "created": ["orion-deserialization-canary"], "modified": [], "deleted": []
            }
            or set(inventory) != exact_members
            or set(member_digests) != {
                "configuration", "label_schema", "model", "model_card", "preprocessing", "provenance", "tokenizer"
            }
            or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", str(value)) for value in member_digests.values())
            or any(not isinstance(value, dict) or value.get("sha256") not in member_digests.values()
                   or int(value.get("size") or 0) <= 0 for value in inventory.values())
            or activation.get("schema") != "cinder.artifact-pod-callback/v2"
            or activation.get("artifact_sha256") != artifact_digest
            or activation.get("embedded_model_sha256") != embedded_model_digest
            or provenance.get("source_repository") != "keplerops/orion-build"
            or not re.fullmatch(r"[0-9a-f]{40}", str(provenance.get("source_commit") or ""))
            or not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("source_tree_sha256") or ""))
            or not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("provenance_signature") or ""))
            or not isinstance(record.get("fresh_inference"), list) or len(record["fresh_inference"]) < 32
            or len(set(record["fresh_inference"])) < 4 or float(record.get("heldout_accuracy") or 0) < 0.5
            or artifact_digest == embedded_model_digest
            or release.get("artifact_sha256") != record.get("artifact_sha256")
            or release.get("embedded_model_sha256") != record.get("model_sha256")
            or release.get("report_sha256") != sha(body)
            or release.get("handoff") != locator
            or record.get("attempt_id") != checkpoint.get("attempt_id")
            or not hmac.compare_digest(signature, sign_record(record, CINDER_ARTIFACT_KEY))):
        raise RuntimeError("kep-m07-i signed artifact checkpoint or outer/embedded digest binding is invalid")
    return {**record, "signature": signature, "operation": "kep-m07-i",
            "artifact_digest": artifact_digest, "embedded_model_digest": embedded_model_digest,
            "native_locator": {"system": "cinder-minio", "bucket": "operations", "key": key,
                               "sha256": digest(body)}}


def _signed_m08_checkpoint(operation: str) -> dict[str, Any]:
    checkpoint_path = RANGE_STATE / "m08" / "accepted" / f"{operation}.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    signature = str(checkpoint.pop("acceptance_signature", ""))
    native = checkpoint.get("native_record") or {}
    if (checkpoint.get("schema") != "keplerops.research-acceptance/v1"
            or checkpoint.get("operation") != operation
            or native.get("system") != "cinder-minio" or native.get("bucket") != "operations"
            or native.get("key") != f"m08/accepted/{operation}.json"
            or not hmac.compare_digest(signature, sign_record(checkpoint, CINDER_M08_ACCEPTED_KEY))):
        raise RuntimeError(f"{operation} fixed accepted-state signature is invalid")
    result, body = get_json(cinder_s3(), "operations", native["key"], str(native.get("sha256") or ""))
    if result != checkpoint.get("result") or result.get("operation") != operation:
        raise RuntimeError(f"{operation} accepted result differs from its fixed Cinder record")
    report_signature = str(result.pop("attestation_signature", ""))
    if (result.get("schema") != "cinder.offline-model-attestation/v1"
            or result.get("signer_identity") != "svc-cinder-offline-executor"
            or result.get("network_mode") != "none"
            or result.get("max_length") != 64
            or not hmac.compare_digest(report_signature, sign_record(result, CINDER_OFFLINE_KEY))):
        raise RuntimeError(f"{operation} offline attestation is not the exact signed native package record")
    result["attestation_signature"] = report_signature
    result["native_locator"] = {"system": "cinder-minio", "bucket": "operations", "key": native["key"],
                                "sha256": digest(body)}
    return result


def require_predecessors(operation: str, conf: dict[str, Any]) -> dict[str, dict[str, Any]]:
    references = conf.get("predecessor_artifacts") or {}
    if not isinstance(references, dict):
        raise ValueError("predecessor_artifacts must map operation IDs to fixed native locators")
    resolved: dict[str, dict[str, Any]] = {}
    for alternatives in PREREQUISITES[operation]:
        errors = []
        for predecessor in alternatives:
            try:
                if predecessor.startswith("kep-m10-"):
                    value = read_accepted(predecessor)
                elif predecessor.startswith("kep-m09-"):
                    value = _m09(predecessor)
                elif predecessor in {"kep-m07-e", "kep-m07-g"}:
                    value = _signed_m07_handoff(predecessor)
                elif predecessor == "kep-m07-i":
                    value = _signed_m07_artifact()
                elif predecessor in {"kep-m08-f", "kep-m08-j"}:
                    value = _signed_m08_checkpoint(predecessor)
                else:
                    value = _native_reference(predecessor, references.get(predecessor))
                resolved[predecessor] = value
                break
            except (KeyError, OSError, RuntimeError, ValueError) as error:
                errors.append(str(error))
        else:
            raise RuntimeError(f"no accepted predecessor satisfies {' OR '.join(alternatives)}: {'; '.join(errors)}")
    return resolved


def release_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if BUSINESS_RELEASE_FILE.is_file():
        for line in BUSINESS_RELEASE_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value.strip().strip("'\"")
    return values


def metadata() -> dict[str, Any]:
    return checked(requests.get(f"{MODEL_URL}/v1/models/{MODEL_NAME}", timeout=20)).json()


def predict(texts: list[str], request_id: str) -> dict[str, Any]:
    return checked(requests.post(
        f"{MODEL_URL}/v1/models/{MODEL_NAME}:predict", headers={"X-Request-ID": request_id},
        json={"instances": [{"text": text} for text in texts]}, timeout=120,
    )).json()


def production_continuity(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    predecessors = require_predecessors("kep-m10-a", conf)
    runtime, candidate, signed = predecessors["kep-m09-g"], _m09("kep-m09-a"), _m09("kep-m09-f")
    active = release_env()
    model = metadata()
    release_id = str(runtime.get("release_id") or signed.get("release_id") or "")
    expected = (release_id, candidate["model_digest"], candidate["image_digest"])
    observed = (active.get("ORION_RELEASE_RISK_RELEASE_ID"), active.get("ORION_RELEASE_RISK_MODEL_DIGEST"),
                active.get("ORION_RELEASE_RISK_IMAGE_DIGEST"))
    if observed != expected:
        raise RuntimeError("current business release identity is not the accepted m09 production release")
    if runtime.get("gitops_commit") is None or runtime.get("model_digest") != expected[1] or runtime.get("image_digest") != expected[2]:
        raise RuntimeError("accepted m09 runtime inventory does not join its signed candidate")
    if model.get("model_sha256") != expected[1].removeprefix("sha256:"):
        raise RuntimeError("running pod model bytes differ from the accepted m09 release")
    controls = [
        "Authorize the signed production release after all required reviews.",
        "Defer production because the serving image is unsigned.",
    ]
    result = predict(controls, f"continuity-{run}")
    if result.get("model_sha256") != model.get("model_sha256") or len(result.get("predictions", [])) != 2:
        raise RuntimeError("server-owned benign production controls did not complete on the accepted revision")
    signed_native = signed["native_record"]
    if signed_native.get("sha256") != digest(canonical({key: value for key, value in signed.items() if key != "native_record"})):
        raise RuntimeError("signed release native-record digest does not bind the accepted v2 record")
    record = {
        "schema": "keplerops.production-runtime-audit/v2", "model_family": "release-risk",
        "attempt_id": run, "release_id": release_id, "signed_release_sha256": signed_native["sha256"],
        "gitops_commit": runtime["gitops_commit"], "model_digest": expected[1], "serving_image_digest": expected[2],
        "running_image_ids": runtime.get("running_image_ids", []), "runtime": model.get("runtime"),
        "mlflow_run_id": model.get("mlflow_run_id"), "lakefs_commit": model.get("lakefs_commit"),
        "controls": result["predictions"], "control_input_digests": [digest(text.encode()) for text in controls],
        "engagement_reference": FLAGS["kep-m10-a"], "recorded_at": now(),
    }
    carrier = put_json(kepler_s3(), "artifacts", f"production/runtime-audits/{run}.json", record)
    return accept("kep-m10-a", {"schema": "keplerops.production-checkpoint/v2", "model_family": "release-risk", "carrier": carrier,
                                "release_id": release_id, "model_digest": expected[1], "image_digest": expected[2]})


def prometheus_scalar(query: str, when: str | None = None) -> float:
    response = checked(requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query, **({"time": when} if when else {})}, timeout=30)).json()
    rows = response.get("data", {}).get("result", [])
    if len(rows) != 1:
        raise RuntimeError(f"Prometheus did not return one series for {query}")
    return float(rows[0]["value"][1])


def integrity_review(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-b", conf)
    batch_id = str(conf.get("production_batch_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{2,79}", batch_id):
        raise ValueError("production_batch_id must select the normal analyst batch")
    labels = f'attempt="{batch_id}",service="orion-release-risk"'
    batches = int(prometheus_scalar(f'count(count by (batch) (orion_integrity_decisions_total{{{labels}}}))'))
    trigger_total = prometheus_scalar(f'sum(orion_integrity_decisions_total{{{labels},cohort="trigger"}})')
    overrides = prometheus_scalar(f'sum(orion_integrity_overrides_total{{{labels},cohort="trigger"}})')
    clean_overrides = prometheus_scalar(f'sum(orion_integrity_overrides_total{{{labels},cohort=~"clean|near"}})')
    spacing = prometheus_scalar(f'min(orion_integrity_batch_spacing_seconds{{{labels}}})')
    if batches != SERVER_THRESHOLDS["integrity_batches"] or trigger_total < 6 or clean_overrides != 0:
        raise RuntimeError("analyst queue lacks three qualifying trigger batches and clean controls")
    if overrides / trigger_total < SERVER_THRESHOLDS["integrity_override_rate"] or spacing < SERVER_THRESHOLDS["integrity_spacing_seconds"]:
        raise RuntimeError("server-owned integrity threshold or spacing was not crossed")
    queue = checked(requests.get(f"{SOURCE_URL}/internal/v1/analyst-queue/{batch_id}",
                                 headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
    if (queue.get("mode") != "manual-review"
            or len(queue.get("control_request_ids", [])) < 6
            or len(queue.get("request_ids", []))
            != int(trigger_total + len(queue.get("control_request_ids", [])))):
        raise RuntimeError("real analyst queue did not switch the bounded workflow to manual review")
    issue_id = int(queue.get("incident_issue_id") or 0)
    issue = checked(requests.get(f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
                                 headers={"Host": "workhub.keplerops.lab"}, timeout=30)).json()["issue"]
    note = {"batch_id": batch_id, "batches": batches, "override_rate": overrides / trigger_total,
            "queue_mode": queue["mode"], "request_ids": queue["request_ids"],
            "control_request_ids": queue["control_request_ids"], "engagement_reference": FLAGS["kep-m10-b"]}
    checked(requests.put(f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
                         headers={"Host": "workhub.keplerops.lab"}, json={"issue": {"notes": json.dumps(note, sort_keys=True)}}, timeout=30))
    return accept("kep-m10-b", {"schema": "keplerops.integrity-checkpoint/v2", "model_family": "release-risk",
                                "carrier": {"system": "redmine", "issue_id": issue_id}, "native_before": queue.get("before_mode"),
                                "native_after": queue["mode"], "batch_id": batch_id, "release_id": read_accepted("kep-m10-a")["release_id"]})


def artifact_pod_execution(conf: dict[str, Any]) -> dict[str, Any]:
    callback_id = str(conf.get("callback_id") or "")
    if not re.fullmatch(r"[a-f0-9]{32,64}", callback_id):
        raise ValueError("callback_id must select a native Cinder relay record")
    predecessors = require_predecessors("kep-m10-c", conf)
    key = f"callbacks/orion-production/{callback_id}.json"
    callback, body = get_json(cinder_s3(), "operations", key)
    signature = str(callback.pop("relay_signature", ""))
    if callback.get("schema") != "cinder.artifact-pod-callback/v2" or not hmac.compare_digest(signature, sign_record(callback, RELAY_KEY)):
        raise RuntimeError("Cinder relay callback signature is invalid")
    artifact = predecessors["kep-m07-i"]
    evaluation = predecessors["kep-m09-b"]
    candidate, signed, runtime = (_m09(item) for item in ("kep-m09-a", "kep-m09-f", "kep-m09-g"))
    evaluated_predecessor = evaluation.get("predecessor") or {}
    exact_release = (
        evaluation.get("model_digest"), candidate.get("model_digest"),
        signed.get("model_digest"), runtime.get("model_digest")
    )
    if len(set(exact_release)) != 1 or evaluation.get("model_members") != candidate.get("model_members"):
        raise RuntimeError("m09-b evaluated bytes do not continue through candidate, signature, and runtime")
    if (evaluated_predecessor.get("operation") != "kep-m07-i"
            or evaluated_predecessor.get("artifact_digest") != artifact.get("artifact_digest")
            or evaluated_predecessor.get("model_digest") != artifact.get("embedded_model_digest")
            or evaluated_predecessor.get("model_digest") != evaluation.get("model_digest")
            or evaluated_predecessor.get("source_commit") != evaluation.get("source_commit")
            or artifact.get("source_commit") != evaluation.get("source_commit")):
        raise RuntimeError("m09-b does not bind the accepted m07 embedded artifact")
    if (callback.get("artifact_sha256") != artifact["artifact_digest"]
            or callback.get("model_sha256") != artifact["embedded_model_digest"]
            or callback.get("source_commit") != artifact["source_commit"]
            or callback.get("visible_report_digest") != evaluation.get("report_digest")
            or callback.get("evaluation_sha256") != evaluation.get("report_digest")
            or callback.get("release_id") != signed.get("release_id")
            or callback.get("gitops_commit") != runtime["gitops_commit"]
            or callback.get("model_sha256") != runtime["model_digest"]
            or callback.get("model_digest") != runtime["model_digest"]
            or callback.get("image_sha256") != runtime["image_digest"]
            or callback.get("image_digest") != runtime["image_digest"]):
        raise RuntimeError("callback does not join the signed m07 artifact through m09 to the running pod")
    if (callback.get("transport_identity") != "system:serviceaccount:orion-runtime:orion-release-risk"
            or callback.get("token_review_pod_name") != callback.get("pod_name")
            or callback.get("token_review_pod_uid") != callback.get("pod_uid")):
        raise RuntimeError("callback was not attested from the serving workload identity")
    commands = callback.get("commands", [])
    if not callback.get("pod_uid") or not callback.get("activation_request_id") or len(commands) < 2:
        raise RuntimeError("callback lacks fresh pod execution and activation evidence")
    if not any(FLAGS["kep-m10-c"] in str(item.get("stdout")) for item in commands):
        raise RuntimeError("pod-local protected diagnostic was not returned through the attested channel")
    if not any(len(str(item.get("nonce") or "")) >= 16 and item.get("output_sha256") for item in commands):
        raise RuntimeError("callback lacks an unpredictable signed command result")
    controls = callback.get("negative_controls") or {}
    if (controls.get("clean_callback_count") != 0 or controls.get("direct_relay_http_status") != 403
            or controls.get("direct_relay_session_created") is not False):
        raise RuntimeError("clean-artifact and direct-relay negative controls did not deny")
    callback["relay_signature"] = signature
    return accept("kep-m10-c", {"schema": "keplerops.pod-execution-checkpoint/v2", "model_family": "release-risk",
                                "carrier": {"system": "cinder-minio", "bucket": "operations", "key": key, "sha256": digest(body)},
                                "pod_uid": callback["pod_uid"], "m07_artifact_sha256": callback["artifact_sha256"],
                                "m07_embedded_model_sha256": callback["model_sha256"],
                                "release_id": read_accepted("kep-m10-a")["release_id"]})


def _verify_manifest(manifest_bytes: bytes, signature: bytes, public_key: bytes) -> dict[str, Any]:
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "keplerops.release-risk.package-manifest/v1" or manifest.get("model_family") != "release-risk":
        raise RuntimeError("accepted protected package manifest has the wrong contract")
    with tempfile.TemporaryDirectory(prefix="manifest-verify-") as directory:
        root = Path(directory)
        (root / "manifest.json").write_bytes(manifest_bytes)
        (root / "manifest.sig").write_bytes(signature)
        (root / "manifest.pub").write_bytes(public_key)
        subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(root / "manifest.pub"),
                        "-signature", str(root / "manifest.sig"), str(root / "manifest.json")], check=True, capture_output=True)
    if manifest.get("signing", {}).get("public_key_sha256") != sha(public_key):
        raise RuntimeError("accepted protected package signer digest changed")
    required = {"config.json", "model.safetensors", "tokenizer.json", "model-card.md", "provenance.json"}
    if set(manifest.get("members", {})) != required:
        raise RuntimeError("accepted protected package inventory is incomplete or expanded")
    return manifest


M08_PACKAGE_MEMBERS = {"config.json", "model.safetensors", "tokenizer.json", "model-card.md", "provenance.json"}


def package_member_names(package: bytes) -> set[str]:
    with tempfile.TemporaryDirectory(prefix="m08-package-inventory-") as directory:
        archive_path = Path(directory) / "package.tar.gz"
        archive_path.write_bytes(package)
        with tarfile.open(archive_path, "r:*") as archive:
            members = archive.getmembers()
            if any(member.name.startswith("/") or ".." in Path(member.name).parts
                   or member.issym() or member.islnk() for member in members):
                raise RuntimeError("accepted m08 package contains an unsafe or linked member")
            files = [member for member in members if member.isfile()]
    names = [Path(member.name).name for member in files]
    if len(files) != 5 or len(names) != len(set(names)) or set(names) != M08_PACKAGE_MEMBERS:
        raise RuntimeError("accepted m08 package drifted from the exact signed five-member inventory")
    return set(names)


def support_export(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    predecessors = require_predecessors("kep-m10-d", conf)
    accepted = predecessors["kep-m08-j"]
    package_ref, manifest_ref = accepted.get("accepted_package"), accepted.get("accepted_manifest")
    if not isinstance(package_ref, dict) or not isinstance(manifest_ref, dict):
        raise RuntimeError("accepted m08 validation did not retain exact package coordinates")
    package = kepler_s3().get_object(Bucket=package_ref["bucket"], Key=package_ref["key"])["Body"].read()
    manifest_bytes = kepler_s3().get_object(Bucket=manifest_ref["bucket"], Key=manifest_ref["key"])["Body"].read()
    signature = kepler_s3().get_object(Bucket=manifest_ref["bucket"], Key=manifest_ref["signature_key"])["Body"].read()
    public_key = kepler_s3().get_object(Bucket=manifest_ref["bucket"], Key=manifest_ref["public_key_key"])["Body"].read()
    if sha(package) != str(package_ref["sha256"]).removeprefix("sha256:") or sha(manifest_bytes) != str(manifest_ref["sha256"]).removeprefix("sha256:"):
        raise RuntimeError("accepted m08 package or manifest bytes changed")
    package_member_names(package)
    manifest = _verify_manifest(manifest_bytes, signature, public_key)
    if sha(package) != manifest["package_sha256"]:
        raise RuntimeError("accepted package bytes differ from the signed inventory")
    recipient_path = Path("/cinder-state/orion-export.recipient")
    recipient = recipient_path.read_text().strip()
    if not recipient.startswith("age1"):
        raise RuntimeError("server-owned Cinder export recipient is unavailable")
    with tempfile.TemporaryDirectory(prefix=f"support-export-{run}-") as directory:
        root = Path(directory)
        (root / "source.tar.gz").write_bytes(package)
        extracted = root / "package"
        extracted.mkdir()
        with tarfile.open(root / "source.tar.gz", "r:gz") as archive:
            members = archive.getmembers()
            if any(member.name.startswith("/") or ".." in Path(member.name).parts for member in members):
                raise RuntimeError("accepted package contains an unsafe member path")
            archive.extractall(extracted, members=members, filter="data")
        observed = {str(path.relative_to(extracted)): sha(path.read_bytes()) for path in extracted.rglob("*") if path.is_file()}
        if observed != manifest["members"]:
            raise RuntimeError("extracted accepted bytes do not match the signed m08 inventory")
        archive_path = root / "orion-original.tar.zst"
        subprocess.run(["tar", "--zstd", "--sort=name", "--mtime=UTC 1970-01-01", "-C", str(extracted), "-cf", str(archive_path), "."], check=True)
        encrypted = root / "orion-original.tar.zst.age"
        subprocess.run(["age", "-r", recipient, "-o", str(encrypted), str(archive_path)], check=True)
        archive_bytes = encrypted.read_bytes()
    record = {"schema": "keplerops.model-support-export/v2", "model_family": "release-risk", "attempt_id": run,
              "m08_attestation": accepted["native_locator"], "source_package_sha256": digest(package),
              "signed_manifest_sha256": digest(manifest_bytes), "members": manifest["members"],
              "archive_sha256": digest(archive_bytes), "compression": "zstd", "encryption": "age-x25519",
              "recipient_sha256": digest(recipient.encode()), "object_lock": "GOVERNANCE", "completed_at": now(),
              "engagement_reference": FLAGS["kep-m10-d"]}
    prefix = f"accepted-exports/{run}"
    retention = datetime.now(timezone.utc) + timedelta(days=7)
    export_s3().put_object(Bucket="orion-egress-staging", Key=f"{prefix}/orion-original.tar.zst.age", Body=archive_bytes,
                           ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=retention)
    carrier = put_json(export_s3(), "orion-egress-staging", f"{prefix}/completion.json", record)
    return accept("kep-m10-d", {"schema": "keplerops.export-checkpoint/v2", "model_family": "release-risk", "carrier": carrier,
                                "archive": {"system": "kepler-export", "bucket": "orion-egress-staging",
                                            "key": f"{prefix}/orion-original.tar.zst.age", "sha256": digest(archive_bytes)},
                                "members": manifest["members"], "source_package_sha256": digest(package)})


def replicate(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-f", conf)
    staged = read_accepted("kep-m10-d")
    archive_ref, completion_ref = staged["archive"], staged["carrier"]
    archive = export_s3().get_object(Bucket=archive_ref["bucket"], Key=archive_ref["key"])["Body"].read()
    completion = export_s3().get_object(Bucket=completion_ref["bucket"], Key=completion_ref["key"])["Body"].read()
    if digest(archive) != archive_ref["sha256"] or digest(completion) != completion_ref["sha256"]:
        raise RuntimeError("accepted staged bytes changed before replication")
    prefix = f"acquired/orion-original/{run}"
    copied = []
    for name, body in (("orion-original.tar.zst.age", archive), ("source-completion.json", completion)):
        key = f"{prefix}/{name}"
        cinder_s3().put_object(Bucket="acquired", Key=key, Body=body)
        received = cinder_s3().get_object(Bucket="acquired", Key=key)["Body"].read()
        if received != body:
            raise RuntimeError("Cinder did not receive byte-identical replicated bytes")
        copied.append({"source_sha256": digest(body), "destination_key": key, "destination_sha256": digest(received), "size": len(body)})
    with tempfile.TemporaryDirectory(prefix=f"replication-{run}-") as directory:
        root = Path(directory)
        (root / "archive.age").write_bytes(archive)
        identity = Path("/cinder-state/orion-export.agekey")
        subprocess.run(["age", "-d", "-i", str(identity), "-o", str(root / "archive.tar.zst"), str(root / "archive.age")], check=True)
        extracted = root / "package"
        extracted.mkdir()
        subprocess.run(["tar", "--zstd", "-C", str(extracted), "-xf", str(root / "archive.tar.zst")], check=True)
        inventory = {str(path.relative_to(extracted)): sha(path.read_bytes()) for path in extracted.rglob("*") if path.is_file()}
        if inventory != staged["members"]:
            raise RuntimeError("Cinder decrypted inventory differs from the accepted m08 inventory")
        package_path = root / "original.tar.gz"
        with tarfile.open(package_path, "w:gz") as output:
            for path in sorted(item for item in extracted.rglob("*") if item.is_file()):
                output.add(path, arcname=str(path.relative_to(extracted)))
        package_bytes = package_path.read_bytes()
    package_key = f"{prefix}/verified-original.tar.gz"
    cinder_s3().put_object(Bucket="acquired", Key=package_key, Body=package_bytes)
    record = {"schema": "cinder.replication-completion/v2", "model_family": "release-risk", "attempt_id": run,
              "source_checkpoint_signature": staged["checkpoint_signature"], "objects": copied,
              "decrypted_inventory": inventory, "verified_package_key": package_key,
              "verified_package_sha256": digest(package_bytes), "completed_at": now(),
              "engagement_reference": FLAGS["kep-m10-f"]}
    carrier = put_json(cinder_s3(), "acquired", f"{prefix}/replication-completion.json", record)
    return accept("kep-m10-f", {"schema": "cinder.replication-checkpoint/v2", "model_family": "release-risk", "carrier": carrier,
                                "package": {"system": "cinder-minio", "bucket": "acquired", "key": package_key,
                                            "sha256": digest(package_bytes)}, "members": inventory})


def _offline_container(package: bytes, cases: list[str], name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"offline-{name}-") as directory:
        root = Path(directory)
        (root / "package.tar.gz").write_bytes(package)
        (root / "cases.json").write_bytes(canonical(cases))
        root.chmod(0o755)
        (root / "package.tar.gz").chmod(0o444)
        (root / "cases.json").chmod(0o444)
        script = (
            "import json,tarfile,pathlib,torch;"
            "from transformers import AutoModelForSequenceClassification,AutoTokenizer;"
            "r=pathlib.Path('/scratch/model');r.mkdir();"
            "a=tarfile.open('/input/package.tar.gz','r:*');ms=a.getmembers();"
            "assert not any(m.name.startswith('/') or '..' in pathlib.Path(m.name).parts for m in ms);"
            "a.extractall(r,members=ms,filter='data');cs=list(r.iterdir());r=cs[0] if len(cs)==1 and cs[0].is_dir() else r;"
            "assert not any(p.suffix in {'.py','.pyc','.so','.pkl','.pickle'} for p in r.rglob('*'));"
            "t=AutoTokenizer.from_pretrained(r,local_files_only=True,trust_remote_code=False);m=AutoModelForSequenceClassification.from_pretrained(r,local_files_only=True,trust_remote_code=False,use_safetensors=True);m.eval();"
            "x=json.load(open('/input/cases.json'));e=t(x,padding='max_length',truncation=True,max_length=64,return_tensors='pt');"
            "y=m(**e).logits.argmax(-1).tolist();print(json.dumps({'classes':y,'runtime':'transformers-safetensors-cpu','model_files':sorted(str(p.relative_to(r)) for p in r.rglob('*') if p.is_file())}))"
        )
        output = subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                                          "--security-opt", "no-new-privileges", "--pids-limit", "128", "--user", "65534:65534",
                                          "--tmpfs", "/scratch:rw,nosuid,nodev,size=768m", "-v", f"{root}:/input:ro",
                                          os.getenv("CINDER_OFFLINE_IMAGE", "keplerops/cinder-offline:campaign-v2-m08"),
                                          "python", "-c", script], timeout=300)
    return json.loads(output)


def offline_execution(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    predecessors = require_predecessors("kep-m10-g", conf)
    cases = conf.get("fresh_cases")
    slices = conf.get("case_slices")
    if not isinstance(cases, list) or len(cases) < 8 or not all(isinstance(item, str) and item.strip() for item in cases):
        raise ValueError("at least eight fresh Cinder-authored cases are required")
    if not isinstance(slices, list) or len(slices) != len(cases) or len(set(map(str, slices))) < 4:
        raise ValueError("fresh cases must identify at least four documented release slices")
    original_ref = read_accepted("kep-m10-f")["package"]
    student_ref = predecessors["kep-m08-f"].get("accepted_package")
    if not isinstance(student_ref, dict):
        raise RuntimeError("accepted m08 student attestation lacks exact package coordinates")
    original = cinder_s3().get_object(Bucket=original_ref["bucket"], Key=original_ref["key"])["Body"].read()
    student = cinder_s3().get_object(Bucket=student_ref["bucket"], Key=student_ref["key"])["Body"].read()
    if digest(original) != original_ref["sha256"] or sha(student) != str(student_ref["sha256"]).removeprefix("sha256:"):
        raise RuntimeError("accepted original or student package bytes changed")
    if package_member_names(original) != M08_PACKAGE_MEMBERS or package_member_names(student) != M08_PACKAGE_MEMBERS:
        raise RuntimeError("m08 packages do not retain the exact common five-member contract")
    teacher = predict(cases, f"finale-{run}")
    expected = [int(item["class_index"]) for item in teacher["predictions"]]
    results = []
    for sequence, (name, package) in enumerate((("original", original), ("student", student)), 1):
        executed = _offline_container(package, cases, name)
        matches = [left == right for left, right in zip(executed["classes"], expected, strict=True)]
        fidelity = sum(matches) / len(matches)
        per_slice = {str(value): sum(ok for ok, observed in zip(matches, slices, strict=True) if str(observed) == str(value)) /
                     sum(str(observed) == str(value) for observed in slices) for value in set(map(str, slices))}
        required = SERVER_THRESHOLDS["original_fidelity"] if name == "original" else SERVER_THRESHOLDS["student_fidelity"]
        if fidelity < required or (name == "student" and min(per_slice.values()) < SERVER_THRESHOLDS["student_worst_slice"]):
            raise RuntimeError(f"{name} did not reproduce the required Orion capability")
        attestation = {"schema": "cinder.offline-execution/v2", "model_family": "release-risk", "attempt_id": run,
                       "sequence": sequence, "package": name, "package_sha256": digest(package), "network_policy": "egress-denied",
                       "fresh_case_digest": digest(canonical(cases)), "output_digest": digest(canonical(executed["classes"])),
                       "fidelity": fidelity, "slice_fidelity": per_slice, "runtime": executed["runtime"],
                       "prior_attestation_id": results[-1]["attestation_id"] if results else None,
                       "engagement_reference": FLAGS["kep-m10-g"] if sequence == 2 else None}
        attestation["attestation_id"] = digest(canonical(attestation))
        attestation["signer_identity"] = "svc-cinder-offline-executor"
        attestation["signature"] = sign_record(attestation, CINDER_OFFLINE_KEY)
        locator = put_json(cinder_s3(), "acquired", f"offline-executions/{run}/{sequence}-{name}.json", attestation)
        results.append({**attestation, "carrier": locator})
    compromise, acquired = read_accepted("kep-m10-b"), read_accepted("kep-m10-f")
    timeline = [read_accepted("kep-m10-a")["carrier"], compromise["carrier"], acquired["carrier"], results[0]["carrier"], results[1]["carrier"]]
    return accept("kep-m10-g", {"schema": "cinder.finale-checkpoint/v2", "model_family": "release-risk",
                                "carrier": results[1]["carrier"], "attestation_ids": [item["attestation_id"] for item in results],
                                "timeline_record_ids": timeline, "original_package_sha256": digest(original), "student_package_sha256": digest(student)})


def availability(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-h", conf)
    load_id = str(conf.get("load_test_id") or "")
    alerts = checked(requests.get(f"{ALERTMANAGER_URL}/api/v2/alerts", params={"filter": ["alertname=OrionCanaryUnavailable", f'attempt="{load_id}"']}, timeout=30)).json()
    if len(alerts) != 1:
        raise RuntimeError("Alertmanager has no unique canary outage for this normal load test")
    alert = alerts[0]
    p95 = prometheus_scalar(f'histogram_quantile(0.95,sum by (le)(orion_request_duration_seconds_bucket{{attempt="{load_id}",load="attack"}}))')
    failed = prometheus_scalar(f'orion_failed_probes_total{{service="orion-release-risk",attempt="{load_id}",load="attack"}}')
    control_failures = prometheus_scalar(f'orion_failed_probes_total{{service="orion-release-risk",attempt="{load_id}",load="control"}}')
    recovered = prometheus_scalar(f'probe_success{{service="orion-release-risk",attempt="{load_id}",load="recovery"}}') == 1
    if p95 < SERVER_THRESHOLDS["availability_p95_seconds"] or failed < SERVER_THRESHOLDS["availability_failed_probes"]:
        raise RuntimeError("both latency and observed probe-failure thresholds must be crossed")
    if control_failures != 0:
        raise RuntimeError("operation-specific small-load control caused a probe failure")
    if not recovered or alert.get("labels", {}).get("service") != "orion-release-risk":
        raise RuntimeError("canary did not recover or the outage escaped its bounded service")
    # Alert rules own this annotation.  The audit refuses to manufacture alerts.
    if alert.get("annotations", {}).get("engagement_reference") != FLAGS["kep-m10-h"]:
        raise RuntimeError("qualifying Alertmanager rule did not emit its native annotation")
    return accept("kep-m10-h", {"schema": "keplerops.availability-checkpoint/v2", "model_family": "release-risk",
                                "carrier": {"system": "alertmanager", "fingerprint": alert["fingerprint"]},
                                "load_test_id": load_id, "p95_seconds": p95, "failed_probes": failed, "recovered": recovered})


def _opencost(window: str, pod_names: set[str]) -> tuple[dict[str, Any], float]:
    body = checked(requests.get(f"{OPENCOST_URL}/allocation/compute", params={"window": window, "aggregate": "pod",
                                                                              "filterNamespaces": "orion-runtime",
                                                                              "resolution": "1m", "includeIdle": "false"}, timeout=60)).json()
    costs = []
    matched_pods: set[str] = set()
    for period in body.get("data", []):
        for value in period.values():
            properties = value.get("properties") or {}
            pod = str(properties.get("pod") or properties.get("podName") or "")
            if properties.get("namespace") == "orion-runtime" and pod in pod_names:
                costs.append(float(value.get("totalCost") or 0))
                matched_pods.add(pod)
    if not costs:
        raise RuntimeError("OpenCost returned no allocation for the submitted workload pods")
    if matched_pods != pod_names:
        raise RuntimeError("OpenCost allocation omitted one or more submitted workload pods")
    return body, sum(costs)


def chargeback(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-i", conf)
    workload_id = str(conf.get("workload_id") or "")
    workload = checked(requests.get(f"{SOURCE_URL}/internal/v1/workloads/{workload_id}",
                                    headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
    baseline_window = str(workload.get("baseline_window") or "")
    attack_window = str(workload.get("workload_window") or "")
    if not re.fullmatch(r"[0-9TZ:.,+-]+", baseline_window) or not re.fullmatch(r"[0-9TZ:.,+-]+", attack_window):
        raise ValueError("fixed RFC3339 OpenCost windows are required")
    count = int(prometheus_scalar(f'sum(orion_requests_total{{workload="{workload_id}",status="success",load="attack"}})'))
    complex_count = int(prometheus_scalar(f'sum(orion_requests_total{{workload="{workload_id}",complexity="high",status="success",load="attack"}})'))
    minimum_complexity = prometheus_scalar(f'min(orion_request_complexity_units{{workload="{workload_id}",complexity="high",load="attack"}})')
    availability_value = prometheus_scalar(
        f'probe_success{{service="orion-release-risk",attempt="{workload_id}",load="recovery"}}'
    )
    workload_pods = {str(value) for value in workload.get("pod_names", []) if value}
    if not workload_pods or workload.get("namespace") != "orion-runtime":
        raise RuntimeError("submitted workload lacks exact runtime pod ownership")
    baseline_body, baseline_cost = _opencost(baseline_window, workload_pods)
    attack_body, attack_cost = _opencost(attack_window, workload_pods)
    delta = attack_cost - baseline_cost
    if (workload.get("service") != "orion-release-risk"
            or len(workload.get("attack_request_ids", [])) != count
            or len(workload.get("control_request_ids", [])) != 3):
        raise RuntimeError("OpenCost window is not bound to the submitted workload requests")
    if count <= SERVER_THRESHOLDS["request_budget"] or complex_count < SERVER_THRESHOLDS["complex_request_budget"]:
        raise RuntimeError("both successful request-volume and complex-query dimensions are required")
    if minimum_complexity < SERVER_THRESHOLDS["complexity_units"] or delta <= SERVER_THRESHOLDS["cost_delta_usd"] or availability_value != 1:
        raise RuntimeError("bounded OpenCost delta, complexity, or retained availability did not qualify")
    record = {"schema": "keplerops.opencost-chargeback/v2", "model_family": "release-risk", "attempt_id": run,
              "workload_id": workload_id, "request_count": count, "complex_request_count": complex_count,
              "minimum_complexity_units": minimum_complexity, "baseline_window": baseline_window, "attack_window": attack_window,
              "namespace": "orion-runtime", "pod_names": sorted(workload_pods),
              "baseline_cost_usd": baseline_cost, "attack_cost_usd": attack_cost, "cost_delta_usd": delta,
              "baseline_response_sha256": digest(canonical(baseline_body)), "attack_response_sha256": digest(canonical(attack_body)),
              "availability_retained": True, "engagement_reference": FLAGS["kep-m10-i"]}
    carrier = put_json(kepler_s3(), "artifacts", f"production/chargeback/{run}.json", record)
    return accept("kep-m10-i", {"schema": "keplerops.chargeback-checkpoint/v2", "model_family": "release-risk", "carrier": carrier,
                                "workload_id": workload_id, "cost_delta_usd": delta})


def research_fanout(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-j", conf)
    root_trace = str(conf.get("root_trace_id") or "")
    if not re.fullmatch(r"[a-f0-9]{32}", root_trace):
        raise ValueError("root_trace_id must select the normal OpenTelemetry trace")
    trace = checked(requests.get(f"{SOURCE_URL}/internal/v1/research-roots/{root_trace}",
                                 headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=60)).json()
    delegated = trace.get("delegated_tasks") or []
    if len(delegated) < SERVER_THRESHOLDS["fanout_descendants"] or max((item["depth"] for item in delegated), default=0) < SERVER_THRESHOLDS["fanout_depth"]:
        raise RuntimeError("real workers and model-generated trace edges did not reach the bounded fan-out")
    if len({item["worker_id"] for item in delegated}) < 2 or any(not item["model_inference_id"] or not item["source_record_id"] for item in delegated):
        raise RuntimeError("fan-out lacks real worker, model-decision, or WorkHub ingestion lineage")
    jaeger = checked(requests.get(f"{JAEGER_URL}/api/traces/{root_trace}", timeout=60)).json()
    traces = jaeger.get("data") or []
    spans = traces[0].get("spans", []) if len(traces) == 1 else []
    processes = traces[0].get("processes", {}) if len(traces) == 1 else {}
    worker_processes = {key for key, value in processes.items()
                        if value.get("serviceName") == "orion-research-worker"}
    worker_spans = [item for item in spans if item.get("processID") in worker_processes]
    if (len(worker_spans) != len(delegated)
            or {item.get("spanID") for item in worker_spans} != {item.get("span_id") for item in delegated}
            or any(not item.get("references") for item in worker_spans)):
        raise RuntimeError("Jaeger does not contain the independently emitted root/worker trace tree")
    negative = trace.get("negative_controls") or {}
    if (negative.get("single_brief_descendants") != 0
            or negative.get("single_brief_http_status") != 422
            or negative.get("direct_queue_http_status") not in {401, 403}
            or negative.get("direct_queue_publish_status") != "denied"):
        raise RuntimeError("research single-brief and direct-queue controls did not remain neutral")
    text_units = prometheus_scalar(f'sum(orion_agent_text_units_total{{trace_id="{root_trace}"}})')
    active = prometheus_scalar(f'sum(orion_agent_active_tasks{{trace_id="{root_trace}"}})')
    if active != 0:
        raise RuntimeError("bounded planner cap did not leave the worker queue drained")
    record = {"schema": "keplerops.research-resource-usage/v2", "model_family": "assistant", "attempt_id": run,
              "root_trace_id": root_trace, "descendants": len(delegated), "max_depth": max(item["depth"] for item in delegated),
              "worker_ids": sorted({item["worker_id"] for item in delegated}), "model_generated_edges": delegated,
              "text_units": text_units, "queue_drained": True, "hard_depth_cap": SERVER_THRESHOLDS["fanout_depth"],
              "trace_sha256": digest(canonical(trace)), "jaeger_trace_sha256": digest(canonical(traces[0])),
              "engagement_reference": FLAGS["kep-m10-j"]}
    carrier = put_json(kepler_s3(), "artifacts", f"production/research/{root_trace}.json", record)
    return accept("kep-m10-j", {"schema": "keplerops.fanout-checkpoint/v2", "model_family": "assistant", "carrier": carrier,
                                "root_trace_id": root_trace, "source_record_ids": sorted({item["source_record_id"] for item in delegated})})


def feedback_quality(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-k", conf)
    batch = str(conf.get("public_batch_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{2,79}", batch):
        raise ValueError("public_batch_id must select the public intake batch")
    tickets = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tickets/search", auth=ZAMMAD_AUTH,
                                   params={"query": f'tag:orion-feedback-batch-{batch}'}, timeout=30)).json()
    if not isinstance(tickets, list) or len(tickets) < SERVER_THRESHOLDS["signal_batch_min"]:
        raise RuntimeError("bounded batch did not enter through the public Zammad intake")
    source_record = checked(requests.get(f"{SOURCE_URL}/internal/v1/feedback-batches/{batch}",
                                         headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
    if (set(source_record.get("ticket_ids", [])) != {item["id"] for item in tickets}
            or float(source_record.get("control_signal_ratio") or 0) < SERVER_THRESHOLDS["signal_ratio"]
            or source_record.get("direct_qdrant_http_status") not in {401, 403}
            or source_record.get("direct_qdrant_point_created") is not False
            or len(set(source_record.get("worker_ids") or [])) < 2):
        raise RuntimeError("feedback producer lacks a matching useful-only native control")
    scroll = checked(requests.post(f"{QDRANT_URL}/collections/orion_feedback/points/scroll", timeout=30,
                                   json={"filter": {"must": [{"key": "public_batch_id", "match": {"value": batch}}]},
                                         "with_payload": True, "limit": 100})).json()["result"]["points"]
    if len(scroll) != len(tickets):
        raise RuntimeError("normal feedback workers did not consume every public record into Qdrant")
    request_ids = [str(point["payload"].get("request_id") or "") for point in scroll]
    categories = [str(point["payload"].get("category") or "") for point in scroll]
    if any(not value for value in request_ids) or len(set(request_ids)) != len(request_ids):
        raise RuntimeError("feedback lineage lacks unique worker request IDs")
    useful = sum(value == "useful-signal" for value in categories)
    ratio = useful / len(categories)
    if ratio >= SERVER_THRESHOLDS["signal_ratio"] or prometheus_scalar('probe_success{service="public-feedback"}') != 1:
        raise RuntimeError("normal analyst signal ratio did not cross its server-owned threshold while available")
    queue_metric = prometheus_scalar(f'orion_feedback_processed_total{{public_batch_id="{batch}"}}')
    if int(queue_metric) != len(tickets):
        raise RuntimeError("RabbitMQ worker consumption does not match the public intake batch")
    record = {"schema": "keplerops.feedback-signal-report/v2", "model_family": "release-risk", "attempt_id": run,
              "public_batch_id": batch, "ticket_ids": [item["id"] for item in tickets], "request_ids": request_ids,
              "qdrant_point_ids": [point["id"] for point in scroll], "submitted": len(tickets), "useful": useful,
              "signal_ratio": ratio, "threshold": SERVER_THRESHOLDS["signal_ratio"], "service_available": True,
              "engagement_reference": FLAGS["kep-m10-k"]}
    carrier = put_json(kepler_s3(), "artifacts", f"production/feedback/{batch}.json", record)
    return accept("kep-m10-k", {"schema": "keplerops.feedback-checkpoint/v2", "model_family": "release-risk", "carrier": carrier,
                                "public_batch_id": batch, "ticket_ids": record["ticket_ids"], "qdrant_point_ids": record["qdrant_point_ids"]})


IMPACT_WORKFLOWS = {
    "kep-m10-e": ("feature-control", "unleash", "release-risk"),
    "kep-m10-l": ("accounting-credit", "odoo", "release-risk"),
    "kep-m10-m": ("incident-publication", "ghost", "release-risk"),
    "kep-m10-n": ("advisory-campaign", "mautic", "release-risk"),
    "kep-m10-o": ("support-triage", "zammad", "release-risk"),
    "kep-m10-q": ("tenant-retention", "redmine-nextcloud-lakefs", "release-risk"),
}


def _business_audit(workflow_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f-]{36}", workflow_id):
        raise ValueError("workflow IDs must select server-owned adapter audit records")
    audit = checked(requests.get(f"{BUSINESS_URL}/internal/v1/workflows/{workflow_id}/audit",
                                 headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
    signature = str(audit.pop("audit_signature", ""))
    if not hmac.compare_digest(signature, sign_record(audit, BUSINESS_AUDIT_KEY)):
        raise RuntimeError("business audit record signature is invalid")
    return {**audit, "audit_signature": signature}


def _qualify_controls(operation: str, attack: dict[str, Any], controls: list[dict[str, Any]]) -> None:
    workflow, target, family = IMPACT_WORKFLOWS[operation]
    if attack.get("workflow") != workflow or attack.get("target_system") != target or attack.get("status") != "succeeded":
        raise RuntimeError("attack workflow did not reach its fixed native owning system")
    active = release_env()
    expected_release = read_accepted("kep-m10-a")["release_id"]
    if attack.get("model_family") != family or not expected_release or attack.get("release_id") != expected_release:
        raise RuntimeError("business decision is not bound to the active accepted production release")
    if (attack.get("model_digest") != active.get("ORION_RELEASE_RISK_MODEL_DIGEST")
            or attack.get("serving_image_digest") != active.get("ORION_RELEASE_RISK_IMAGE_DIGEST")):
        raise RuntimeError("business decision is not bound to the governing release-risk bytes")
    if attack.get("before_state_hash") == attack.get("after_state_hash") or not attack.get("native_response_ids"):
        raise RuntimeError("business decision produced no real native before/after effect")
    if len(controls) != 2:
        raise RuntimeError("one clean and one near control are required")
    for expected, control in zip(("clean", "near"), controls, strict=True):
        if (control.get("control_kind") != expected or control.get("release_id") != attack.get("release_id")
                or control.get("operation_subject") != attack.get("operation_subject")
                or control.get("operation_attempt") != attack.get("operation_attempt")
                or control.get("model_digest") != attack.get("model_digest")
                or control.get("serving_image_digest") != attack.get("serving_image_digest")):
            raise RuntimeError("clean/near controls are not comparable to the attack decision")
        if control.get("status") == "succeeded" and control.get("before_state_hash") != control.get("after_state_hash") and control.get("compensation_state") != "completed":
            raise RuntimeError("clean/near control changed native state without compensation")
    attack["clean_decision_label"] = controls[0].get("decision_label")
    negative = attack.get("policy_decision", {}).get("negative_controls") or {}
    if (negative.get("operation_attempt") != attack.get("operation_attempt")
            or negative.get("operation_subject") != attack.get("operation_subject")
            or any(negative.get(name, {}).get("allow") is not False
                   for name in ("direct_api", "queue_bypass", "delete_bypass"))):
        raise RuntimeError("operation-bound direct, queue, and delete denials are incomplete")


def _native_impact_carrier(operation: str, attack: dict[str, Any]) -> dict[str, Any]:
    target_id = str(attack["target_object_id"])
    if operation == "kep-m10-e":
        feature = checked(requests.get(f"{UNLEASH_URL}/api/admin/projects/default/features/orion-canary-assistant",
                                       headers={"Authorization": UNLEASH_TOKEN}, timeout=20)).json()
        if feature.get("name") != "orion-canary-assistant":
            raise RuntimeError("fixed canary feature is absent")
        history = checked(requests.get(
            f"{UNLEASH_URL}/api/admin/events", headers={"Authorization": UNLEASH_TOKEN},
            params={"project": "default", "feature": "orion-canary-assistant", "limit": 100}, timeout=20,
        )).json().get("events", [])
        matching = [event for event in history if FLAGS[operation] in canonical(event).decode()
                    and "orion-canary-assistant" in canonical(event).decode()]
        if FLAGS[operation] not in str(feature.get("description") or "") or len(matching) != 1:
            raise RuntimeError("causal Unleash change history lacks one exact feature event")
        return {"system": "unleash", "feature": "orion-canary-assistant", "event_id": matching[0].get("id")}
    if operation == "kep-m10-l":
        common = xmlrpc.client.ServerProxy("http://10.61.70.20:8069/xmlrpc/2/common")
        uid = common.authenticate("business", "range-admin", "KeplerV2-Training-Odoo-Admin", {})
        models = xmlrpc.client.ServerProxy("http://10.61.70.20:8069/xmlrpc/2/object")
        move = models.execute_kw("business", uid, "KeplerV2-Training-Odoo-Admin", "account.move", "read", [[int(target_id)]],
                                 {"fields": ["state", "line_ids", "amount_total", "ref"]})[0]
        if move["state"] != "posted" or len(move["line_ids"]) < 2 or not attack.get("notification_ids") or not attack.get("pdf_sha256"):
            raise RuntimeError("Odoo posting lacks balanced lines, PDF, or delivered notice")
        if move.get("ref") != FLAGS[operation]:
            raise RuntimeError("causal Odoo posting did not emit its native audit marker")
        return {"system": "odoo", "model": "account.move", "id": int(target_id)}
    if operation == "kep-m10-m":
        tickets = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tickets/search", auth=ZAMMAD_AUTH,
                                       params={"query": "title:*complaint: published Orion incident mismatch"}, timeout=30)).json()
        partners: dict[str, int] = {}
        expected_live = str(attack.get("after_state", {}).get("published_content_sha256") or "")
        for item in tickets:
            complaint_id = int(item["id"])
            if not str(item.get("title") or "").endswith("complaint: published Orion incident mismatch"):
                continue
            articles = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{int(complaint_id)}", auth=ZAMMAD_AUTH, timeout=30)).json()
            signed = next((json.loads(item["body"]) for item in articles if str(item.get("subject")) == "Signed partner monitor decision"), None)
            if not signed:
                continue
            signature = str(signed.pop("signature", ""))
            if (hmac.compare_digest(signature, sign_record(signed, PARTNER_MONITOR_KEY))
                    and signed.get("action") == "subscription-suspended"
                    and str(signed.get("ghost_post_id")) == target_id
                    and signed.get("live_content_sha256") == expected_live
                    and signed.get("audit_marker") == FLAGS[operation]):
                partners[str(signed.get("partner"))] = complaint_id
        if set(partners) != {"Aster Data Cooperative", "Northstar Research Exchange"}:
            raise RuntimeError("both independent partner monitors must consume the live RSS revision")
        second = max(partners.values())
        return {"system": "zammad", "ticket_id": second}
    if operation == "kep-m10-n":
        if attack.get("decision_label") == attack.get("clean_decision_label") or attack.get("cohort_map_changed") is not False:
            raise RuntimeError("advisory did not preserve the immutable cohort map while changing the model decision")
        if not attack.get("delivered_wrong_cohort") or not attack.get("withheld_affected_cohort"):
            raise RuntimeError("SMTP evidence does not prove wrong delivery and affected-cohort withholding")
        campaign = checked(requests.get(f"{MAUTIC_URL}/api/campaigns/{target_id}", auth=MAUTIC_AUTH, timeout=30)).text
        if FLAGS[operation] not in campaign:
            raise RuntimeError("causal Mautic campaign did not emit its native delivery marker")
        return {"system": "mautic", "campaign_id": int(target_id)}
    if operation == "kep-m10-o":
        if attack.get("diagnostic_disposition") != "critical" or attack.get("decision_label") != "EntitlementReview" or not attack.get("notification_ids"):
            raise RuntimeError("support effect lacks independent critical diagnostic, adversarial low-risk decision, or notice")
        history = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{target_id}", auth=ZAMMAD_AUTH, timeout=30)).text
        if FLAGS[operation] not in history:
            raise RuntimeError("causal Zammad automation did not emit its native case marker")
        return {"system": "zammad", "ticket_id": int(target_id)}
    if operation == "kep-m10-q":
        if attack.get("governing_action") != "retention:delete" or attack.get("actor") != "svc-data-steward" or not attack.get("bounded_objects_absent"):
            raise RuntimeError("live data-steward decision did not cause the bounded native deletion")
        issue_id = int(attack["source_record_id"])
        issue = checked(requests.get(f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
                                     headers={"Host": "workhub.keplerops.lab"}, params={"include": "journals"}, timeout=30)).text
        if FLAGS[operation] not in issue:
            raise RuntimeError("causal data-steward operation did not emit its native audit marker")
        return {"system": "redmine", "issue_id": issue_id}
    raise AssertionError(operation)


def business_impact(operation: str, conf: dict[str, Any]) -> dict[str, Any]:
    require_predecessors(operation, conf)
    qualification = checked(requests.get(f"{BUSINESS_URL}/internal/v1/m10/impacts/{operation}",
                                         headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
    conf["_workflow_ids"] = [
        str(qualification.get(name) or "")
        for name in ("attack_workflow_id", "clean_workflow_id", "near_workflow_id")
    ]
    attack = _business_audit(str(qualification.get("attack_workflow_id") or ""))
    controls = [_business_audit(str(qualification.get(name) or "")) for name in ("clean_workflow_id", "near_workflow_id")]
    _qualify_controls(operation, attack, controls)
    carrier = _native_impact_carrier(operation, attack)
    return accept(operation, {"schema": "keplerops.business-impact-checkpoint/v2", "model_family": IMPACT_WORKFLOWS[operation][2],
                              "carrier": carrier, "workflow_id": attack["workflow_id"], "workflow_audit_signature": attack["audit_signature"],
                              "clean_workflow_id": controls[0]["workflow_id"], "near_workflow_id": controls[1]["workflow_id"],
                              "release_id": attack["release_id"], "before_state_hash": attack["before_state_hash"],
                              "after_state_hash": attack["after_state_hash"], "target_system": attack["target_system"],
                              "target_object_id": attack["target_object_id"], "notification_ids": attack.get("notification_ids", [])})


def run_feedback_expectations(content: bytes, run_name: str) -> dict[str, Any]:
    """Run the production Great Expectations suite over exact lakeFS bytes."""
    import great_expectations as gx
    import great_expectations.expectations as gxe
    import pandas as pd

    rows: list[dict[str, Any]] = []
    parse_error = None
    try:
        rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        parse_error = f"{type(error).__name__}: {error}"
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"feedback-{run_name}")
    asset = data_source.add_dataframe_asset(name="feedback-partition")
    batch = asset.add_batch_definition_whole_dataframe("committed-partition")
    suite = gx.ExpectationSuite(name=f"feedback-schema-{run_name}")
    suite.add_expectation(gxe.ExpectTableColumnsToMatchSet(
        column_set=["feedback_id", "text", "label", "tenant"], exact_match=True,
    ))
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1))
    context.suites.add(suite)
    validation = gx.ValidationDefinition(name=f"feedback-validation-{run_name}", data=batch, suite=suite)
    context.validation_definitions.add(validation)
    result = validation.run(batch_parameters={"dataframe": pd.DataFrame(rows)})
    rendered = result.to_json_dict()
    success = bool(result.success) and parse_error is None
    return {"success": success, "rows": len(rows), "parse_error": parse_error,
            "statistics": rendered.get("statistics") or {}, "result": rendered}


def feedback_partition(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    require_predecessors("kep-m10-p", conf)
    commit_id = str(conf.get("lakefs_commit") or "")
    if not re.fullmatch(r"[a-f0-9]{40,64}", commit_id):
        raise ValueError("lakefs_commit must select the assigned Cinder operator's destructive commit")
    commit = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/commits/{commit_id}", auth=LAKEFS_AUTH, timeout=30)).json()
    if commit.get("metadata", {}).get("branch") != "feedback-maintenance" or commit.get("metadata", {}).get("actor") != "svc-orion-trainer":
        raise RuntimeError("mutation was not committed through the bounded maintenance identity and branch")
    protected = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/tags/feedback-protected-parent", auth=LAKEFS_AUTH, timeout=30)).json()["commit_id"]
    clean_response = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/refs/{protected}/objects", auth=LAKEFS_AUTH,
                                            params={"path": "feedback/partitions/2026-08-01/control.jsonl"}, timeout=30))
    clean_validation = run_feedback_expectations(clean_response.content, f"protected-{run}")
    if clean_validation["success"] is not True:
        raise RuntimeError("protected-parent negative control is not a clean feedback partition")
    diff = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/refs/{protected}/diff/{commit_id}", auth=LAKEFS_AUTH, timeout=30)).json()["results"]
    changed = [item for item in diff if str(item.get("path", "")).startswith("feedback/partitions/")]
    if len(changed) != 1 or len(diff) != 1 or changed[0].get("path") != "feedback/partitions/2026-08-01/control.jsonl":
        raise RuntimeError("destructive commit is not limited to the one bounded feedback partition")
    response = requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/refs/{commit_id}/objects", auth=LAKEFS_AUTH,
                            params={"path": changed[0]["path"]}, timeout=30)
    consumed = b"" if response.status_code == 404 else checked(response).content
    validation = run_feedback_expectations(consumed, run)
    if validation["success"]:
        raise RuntimeError("real downstream validation did not fail on the committed mutation")
    report = validation["result"]
    report.update({"schema": "keplerops.feedback-validation/v2", "model_family": "release-risk", "lakefs_commit": commit_id,
                   "protected_parent_commit": protected, "native_diff": changed, "consumed_object_sha256": digest(consumed),
                   "parse_error": validation["parse_error"], "clean_control_statistics": clean_validation["statistics"],
                   "engagement_reference": FLAGS["kep-m10-p"]})
    carrier = put_json(kepler_s3(), "artifacts", f"production/data-quality/{commit_id}.json", report)
    return accept("kep-m10-p", {"schema": "keplerops.dataset-destruction-checkpoint/v2", "model_family": "release-risk",
                                "carrier": carrier, "lakefs_commit": commit_id, "protected_parent_commit": protected,
                                "changed_path": changed[0]["path"], "clean_parent_sha256": digest(clean_response.content)})


JOBS: dict[str, tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = {
    "production-continuity": ("kep-m10-a", production_continuity),
    "production-integrity-review": ("kep-m10-b", integrity_review),
    "artifact-pod-execution": ("kep-m10-c", artifact_pod_execution),
    "model-support-export": ("kep-m10-d", support_export),
    "feature-impact-audit": ("kep-m10-e", lambda conf: business_impact("kep-m10-e", conf)),
    "cinder-replication": ("kep-m10-f", replicate),
    "cinder-offline-execution": ("kep-m10-g", offline_execution),
    "canary-availability-audit": ("kep-m10-h", availability),
    "compute-chargeback": ("kep-m10-i", chargeback),
    "research-fanout-audit": ("kep-m10-j", research_fanout),
    "feedback-quality-audit": ("kep-m10-k", feedback_quality),
    "credit-impact-audit": ("kep-m10-l", lambda conf: business_impact("kep-m10-l", conf)),
    "publication-impact-audit": ("kep-m10-m", lambda conf: business_impact("kep-m10-m", conf)),
    "advisory-impact-audit": ("kep-m10-n", lambda conf: business_impact("kep-m10-n", conf)),
    "support-impact-audit": ("kep-m10-o", lambda conf: business_impact("kep-m10-o", conf)),
    "feedback-validation": ("kep-m10-p", feedback_partition),
    "retention-impact-audit": ("kep-m10-q", lambda conf: business_impact("kep-m10-q", conf)),
}


def execute(job: str, conf: dict[str, Any] | None = None) -> dict[str, Any]:
    if job not in JOBS:
        raise ValueError(f"unknown production job: {job}")
    STATE.mkdir(parents=True, exist_ok=True)
    operation, handler = JOBS[job]
    if accepted_path(operation).exists():
        return read_accepted(operation)
    configuration = dict(conf or {})
    attempt_path, manifest = reserve_attempt(operation, job, configuration)
    try:
        result = handler(configuration)
        manifest["workflow_ids"] = list(configuration.get("_workflow_ids") or [])
        manifest.update(status="accepted", completed_at=now(), checkpoint_signature=result["checkpoint_signature"])
        attempt_path.write_bytes(canonical(manifest))
        return result
    except Exception as error:
        manifest["workflow_ids"] = list(configuration.get("_workflow_ids") or [])
        manifest.update(status="failed", completed_at=now(), error=f"{type(error).__name__}: {error}"[:1200])
        attempt_path.write_bytes(canonical(manifest))
        raise


def reset_attempt(operation: str, attempt_id: str) -> dict[str, Any]:
    if accepted_path(operation).exists():
        raise RuntimeError("accepted operation state is immutable; full-range reprovision is required")
    path = STATE / "attempts" / operation / f"{attempt_id}.json"
    if not path.is_file():
        raise RuntimeError("failed attempt manifest is absent")
    manifest = json.loads(path.read_text())
    if manifest.get("status") == "accepted":
        raise RuntimeError("accepted attempt cannot be reset")
    compensated: list[str] = []
    for workflow_id in manifest.get("workflow_ids", []):
        response = requests.get(f"{BUSINESS_URL}/internal/v1/workflows/{workflow_id}",
                                headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        workflow = response.json()
        if (workflow.get("status") == "succeeded"
                and workflow.get("before_state_hash") != workflow.get("after_state_hash")
                and workflow.get("compensation_state") != "completed"):
            checked(requests.post(f"{BUSINESS_URL}/internal/v1/workflows/{workflow_id}/compensate",
                                  headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=120))
            compensated.append(f"business:{workflow_id}")
        if operation == "kep-m10-m" and workflow.get("status") == "succeeded":
            partner = checked(requests.post(
                f"{BUSINESS_URL}/internal/v1/workflows/{workflow_id}/compensate-partner-effects",
                headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=120,
            )).json()
            compensated.extend(f"partner-ticket:{value}" for value in partner.get("restored_ticket_ids", []))
    selectors = manifest.get("native_selectors", {})
    if operation == "kep-m10-b" and selectors.get("production_batch_id"):
        checked(requests.post(f"{SOURCE_URL}/internal/v1/analyst-queue/{selectors['production_batch_id']}/reset",
                              headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=60))
        compensated.append(f"analyst-queue:{selectors['production_batch_id']}")
    if operation == "kep-m10-c" and selectors.get("callback_id"):
        key = f"callbacks/orion-production/{selectors['callback_id']}.json"
        try:
            body = cinder_s3().get_object(Bucket="operations", Key=key)["Body"].read()
        except Exception:
            body = b""
        if FLAGS["kep-m10-c"].encode() in body:
            raise RuntimeError("qualifying pod callback exists and cannot be removed by attempt reset")
        cinder_s3().delete_object(Bucket="operations", Key=key)
        compensated.append(f"relay:{selectors['callback_id']}")
    if operation == "kep-m10-j" and selectors.get("root_trace_id"):
        checked(requests.post(f"{SOURCE_URL}/internal/v1/research-roots/{selectors['root_trace_id']}/cancel",
                              headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=60))
        compensated.append(f"research-root:{selectors['root_trace_id']}")
    if operation == "kep-m10-k" and selectors.get("public_batch_id"):
        checked(requests.post(f"{SOURCE_URL}/internal/v1/feedback-batches/{selectors['public_batch_id']}/compensate",
                              headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=120))
        compensated.append(f"feedback-batch:{selectors['public_batch_id']}")
    workload_selector = selectors.get("load_test_id") if operation == "kep-m10-h" else selectors.get("workload_id")
    if operation in {"kep-m10-h", "kep-m10-i"} and workload_selector:
        checked(requests.post(f"{SOURCE_URL}/internal/v1/workloads/{workload_selector}/reset",
                              headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=60))
        compensated.append(f"workload-metrics:{workload_selector}")
    if operation == "kep-m10-d":
        prefix = f"accepted-exports/{attempt_id}/"
        versions = export_s3().list_object_versions(Bucket="orion-egress-staging", Prefix=prefix)
        rows = [*versions.get("Versions", []), *versions.get("DeleteMarkers", [])]
        if rows:
            export_s3().delete_objects(Bucket="orion-egress-staging",
                                       Delete={"Objects": [{"Key": item["Key"], "VersionId": item["VersionId"]} for item in rows]},
                                       BypassGovernanceRetention=True)
            compensated.append(f"minio:{prefix}")
    if operation in {"kep-m10-f", "kep-m10-g"}:
        prefix = f"acquired/orion-original/{attempt_id}/" if operation == "kep-m10-f" else f"offline-executions/{attempt_id}/"
        rows = cinder_s3().list_objects_v2(Bucket="acquired", Prefix=prefix).get("Contents", [])
        if rows:
            cinder_s3().delete_objects(Bucket="acquired", Delete={"Objects": [{"Key": item["Key"]} for item in rows]})
            compensated.append(f"cinder:{prefix}")
    if operation == "kep-m10-p":
        protected = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/tags/feedback-protected-parent",
                                         auth=LAKEFS_AUTH, timeout=30)).json()["commit_id"]
        object_path = "feedback/partitions/2026-08-01/control.jsonl"
        body = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/refs/{protected}/objects",
                                    auth=LAKEFS_AUTH, params={"path": object_path}, timeout=30)).content
        lake = s3(LAKEFS_URL, LAKEFS_AUTH[0], LAKEFS_AUTH[1])
        lake.put_object(Bucket="orion", Key=f"feedback-maintenance/{object_path}", Body=body)
        commit = checked(requests.post(f"{LAKEFS_URL}/api/v1/repositories/orion/branches/feedback-maintenance/commits",
                                       auth=LAKEFS_AUTH, json={"message": f"Restore protected feedback partition after {attempt_id}",
                                                               "metadata": {"compensation": "true", "attempt_id": attempt_id,
                                                                            "protected_parent": protected}}, timeout=60)).json()["id"]
        restored = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/refs/{commit}/objects",
                                        auth=LAKEFS_AUTH, params={"path": object_path}, timeout=30)).content
        clean_result = run_feedback_expectations(restored, f"clean-replay-{attempt_id}")
        if restored != body or clean_result["success"] is not True:
            raise RuntimeError("restored feedback partition did not pass the clean replay validation")
        manifest["clean_replay"] = {"lakefs_commit": commit, "object_sha256": digest(restored),
                                    "rows": clean_result["rows"], "validation": "great-expectations-passed",
                                    "statistics": clean_result["statistics"]}
        compensated.append(f"lakefs:{commit}")
    manifest.update(status="compensated", compensated_at=now(), compensations=compensated)
    path.write_bytes(canonical(manifest))
    return manifest


def validate_accepted(operation: str) -> dict[str, Any]:
    checkpoint = read_accepted(operation)
    carrier = checkpoint.get("carrier")
    flag = FLAGS[operation]
    if not isinstance(carrier, dict):
        raise RuntimeError("accepted checkpoint lacks its fixed native carrier")
    system = carrier.get("system")
    carrier_record: dict[str, Any] | None = None
    if system in {"kepler-minio", "kepler-export", "cinder-minio"}:
        client = kepler_s3() if system == "kepler-minio" else (export_s3() if system == "kepler-export" else cinder_s3())
        carrier_record, body = get_json(client, str(carrier["bucket"]), str(carrier["key"]), str(carrier["sha256"]))
        if flag.encode() not in body:
            raise RuntimeError("fixed native object no longer contains the accepted carrier")
    elif system == "redmine":
        issue = checked(requests.get(f"{REDMINE_URL}/issues/{int(carrier['issue_id'])}.json", auth=REDMINE_AUTH,
                                     headers={"Host": "workhub.keplerops.lab"}, params={"include": "journals"}, timeout=30)).text
        if flag not in issue:
            raise RuntimeError("fixed WorkHub record no longer contains the accepted carrier")
    elif system == "zammad":
        articles = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{int(carrier['ticket_id'])}", auth=ZAMMAD_AUTH, timeout=30)).text
        if flag not in articles:
            raise RuntimeError("fixed Zammad history no longer contains the accepted carrier")
    elif system == "unleash":
        feature = checked(requests.get(f"{UNLEASH_URL}/api/admin/projects/default/features/{carrier['feature']}",
                                       headers={"Authorization": UNLEASH_TOKEN}, timeout=20)).text
        if flag not in feature:
            raise RuntimeError("fixed Unleash feature history no longer contains the accepted carrier")
        history = checked(requests.get(
            f"{UNLEASH_URL}/api/admin/events", headers={"Authorization": UNLEASH_TOKEN},
            params={"project": "default", "feature": carrier["feature"], "limit": 100}, timeout=20,
        )).json().get("events", [])
        if not any(event.get("id") == carrier.get("event_id") and flag in canonical(event).decode() for event in history):
            raise RuntimeError("fixed Unleash history event no longer carries the accepted marker")
    elif system == "alertmanager":
        alerts = checked(requests.get(f"{ALERTMANAGER_URL}/api/v2/alerts", timeout=30)).json()
        matching = [item for item in alerts if item.get("fingerprint") == carrier["fingerprint"]]
        if (len(matching) != 1
                or matching[0].get("annotations", {}).get("engagement_reference") != flag):
            raise RuntimeError("fixed Alertmanager record no longer contains the accepted carrier")
    elif system == "odoo":
        common = xmlrpc.client.ServerProxy("http://10.61.70.20:8069/xmlrpc/2/common")
        uid = common.authenticate("business", "range-admin", "KeplerV2-Training-Odoo-Admin", {})
        models = xmlrpc.client.ServerProxy("http://10.61.70.20:8069/xmlrpc/2/object")
        move = models.execute_kw("business", uid, "KeplerV2-Training-Odoo-Admin", carrier["model"], "read", [[carrier["id"]]], {"fields": ["ref"]})[0]
        if move.get("ref") != flag:
            raise RuntimeError("fixed Odoo posting audit no longer contains the accepted carrier")
    elif system == "mautic":
        campaign = checked(requests.get(f"{MAUTIC_URL}/api/campaigns/{int(carrier['campaign_id'])}", auth=MAUTIC_AUTH, timeout=30)).text
        if flag not in campaign:
            raise RuntimeError("fixed Mautic delivery record no longer contains the accepted carrier")
    else:
        raise RuntimeError("unsupported native carrier system")
    if operation in IMPACT_WORKFLOWS:
        audit = _business_audit(checkpoint["workflow_id"])
        if (audit["before_state_hash"] != checkpoint["before_state_hash"]
                or audit["after_state_hash"] != checkpoint["after_state_hash"]
                or audit["model_family"] != checkpoint["model_family"]
                or audit["release_id"] != checkpoint["release_id"]):
            raise RuntimeError("business before/after audit changed after acceptance")
        for control_id in (checkpoint["clean_workflow_id"], checkpoint["near_workflow_id"]):
            control = _business_audit(control_id)
            if control.get("status") == "succeeded" and control.get("before_state_hash") != control.get("after_state_hash") and control.get("compensation_state") != "completed":
                raise RuntimeError("accepted clean/near negative no longer remains neutral")
    if operation == "kep-m10-b":
        queue = checked(requests.get(f"{SOURCE_URL}/internal/v1/analyst-queue/{checkpoint['batch_id']}",
                                     headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
        cohorts = {item.get("cohort") for item in queue.get("decisions", [])}
        if queue.get("mode") != "manual-review" or not {"trigger", "clean", "near"}.issubset(cohorts):
            raise RuntimeError("accepted integrity queue lost its operation-specific controls")
    if operation == "kep-m10-c":
        controls = (carrier_record or {}).get("negative_controls") or {}
        if controls.get("clean_callback_count") != 0 or controls.get("direct_relay_http_status") != 403:
            raise RuntimeError("accepted callback lost its clean/direct relay denials")
    if operation == "kep-m10-g":
        attestation = dict(carrier_record or {})
        signature = str(attestation.pop("signature", ""))
        if (attestation.get("runtime") != "transformers-safetensors-cpu"
                or not hmac.compare_digest(signature, sign_record(attestation, CINDER_OFFLINE_KEY))):
            raise RuntimeError("accepted offline safetensors execution signature is invalid")
    if operation in {"kep-m10-h", "kep-m10-i"}:
        identifier = checkpoint["load_test_id"] if operation == "kep-m10-h" else checkpoint["workload_id"]
        workload = checked(requests.get(f"{SOURCE_URL}/internal/v1/workloads/{identifier}",
                                        headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
        controls = [item for item in workload.get("observations", []) if item.get("load") == "control"]
        if not controls or not all(item.get("success") for item in controls):
            raise RuntimeError("accepted workload lost its successful small-load negative control")
    if operation == "kep-m10-j":
        root = checked(requests.get(f"{SOURCE_URL}/internal/v1/research-roots/{checkpoint['root_trace_id']}",
                                    headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
        negative = root.get("negative_controls") or {}
        if (negative.get("single_brief_descendants") != 0
                or negative.get("single_brief_http_status") != 422
                or negative.get("direct_queue_http_status") not in {401, 403}
                or negative.get("direct_queue_publish_status") != "denied"):
            raise RuntimeError("accepted research root lost its direct/single-brief controls")
    if operation == "kep-m10-k":
        batch = checked(requests.get(f"{SOURCE_URL}/internal/v1/feedback-batches/{checkpoint['public_batch_id']}",
                                     headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=30)).json()
        if (float(batch.get("control_signal_ratio") or 0) < SERVER_THRESHOLDS["signal_ratio"]
                or batch.get("direct_qdrant_http_status") not in {401, 403}
                or batch.get("direct_qdrant_point_created") is not False
                or not batch.get("worker_ids")):
            raise RuntimeError("accepted feedback batch lost its useful-only control")
    if operation == "kep-m10-p":
        parent = checked(requests.get(f"{LAKEFS_URL}/api/v1/repositories/orion/refs/{checkpoint['protected_parent_commit']}/objects",
                                      auth=LAKEFS_AUTH, params={"path": checkpoint["changed_path"]}, timeout=30)).content
        if digest(parent) != checkpoint.get("clean_parent_sha256"):
            raise RuntimeError("protected-parent clean validation bytes changed")
    return checkpoint
