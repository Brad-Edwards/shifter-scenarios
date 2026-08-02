from __future__ import annotations

import concurrent.futures
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
from typing import Any, Callable
from urllib.parse import urlencode
import uuid
import xmlrpc.client
from datetime import datetime, timedelta, timezone

import boto3
from botocore.client import Config
import requests


MODEL_URL = os.getenv("ORION_RELEASE_RISK_URL", "http://192.168.78.30:30083")
MODEL_NAME = "orion-release-risk"
BUSINESS_URL = os.getenv("BUSINESS_ADAPTER_URL", "http://business-adapter:8080")
BUSINESS_TOKEN = os.getenv("BUSINESS_ADAPTER_TOKEN", "KeplerV2-Training-Business-Adapter")
REDMINE_URL = os.getenv("REDMINE_URL", "http://10.61.50.41:3000")
REDMINE_AUTH = (os.getenv("REDMINE_USER", "range-admin"), os.getenv("REDMINE_PASSWORD", "KeplerV2-Training-Redmine-Admin"))
ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://10.61.50.43:8080")
ZAMMAD_AUTH = (os.getenv("ZAMMAD_USER", "range-admin"), os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Zammad-Admin"))
UNLEASH_URL = os.getenv("UNLEASH_URL", "http://10.61.70.23:4242")
UNLEASH_TOKEN = os.getenv("UNLEASH_TOKEN", "user:KeplerV2-Training-Orion-Unleash-Control")
GHOST_URL = os.getenv("GHOST_URL", "http://10.61.70.21:2368")
MAUTIC_URL = os.getenv("MAUTIC_URL", "http://10.61.70.22")
MAUTIC_AUTH = (os.getenv("MAUTIC_USER", "range-admin"), os.getenv("MAUTIC_PASSWORD", "KeplerV2-Training-Mautic"))
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://10.61.50.42/remote.php/dav/files/reviewer")
NEXTCLOUD_AUTH = (os.getenv("NEXTCLOUD_USER", "reviewer"), os.getenv("NEXTCLOUD_PASSWORD", "KeplerV2-Training-Reviewer"))
RABBIT_URL = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://10.61.50.12:15672")
RABBIT_AUTH = (os.getenv("RABBITMQ_USER", "kepler"), os.getenv("RABBITMQ_PASSWORD", "KeplerV2-Training-Rabbit"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://10.61.50.72:6333")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://10.61.80.12:9090")
OPENCOST_URL = os.getenv("OPENCOST_URL", "http://192.168.78.30:30090")
OPENCOST_PUBLIC_URL = os.getenv("OPENCOST_PUBLIC_URL", "https://opencost.keplerops.lab")
ASSISTANT_URL = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081")
ASSISTANT_KEY = os.getenv("ORION_AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053")
STATE = Path(os.getenv("M10_STATE_DIR", "/var/lib/keplerops-production"))

FLAGS = {
    "continuity": "FLAG{2685a21d199ad0ef}",
    "integrity": "FLAG{9f23d794e5faa741}",
    "export": "FLAG{7c0fdd97173a0a6a}",
    "feature": "FLAG{91713d4d8620ee1f}",
    "replication": "FLAG{980dc89d2331bbef}",
    "offline": "FLAG{dd173d0b26a40a17}",
    "availability": "FLAG{42258d84b313abde}",
    "chargeback": "FLAG{8bb6926829771c6c}",
    "fanout": "FLAG{ade9604521c854f1}",
    "chaff": "FLAG{63b4f72ad7601c11}",
    "credit": "FLAG{a82d034012239fd4}",
    "publication": "FLAG{4b5ed15f2cdc3c14}",
    "advisory": "FLAG{afcd49bf911157d2}",
    "support": "FLAG{198bee40fbdd538d}",
    "partition": "FLAG{2d80b8c60083f96f}",
    "retention": "FLAG{4f5fc96cdd02ede5}",
}


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def attempt(conf: dict[str, Any]) -> str:
    value = str(conf.get("attempt_id") or uuid.uuid4())
    if not value.replace("-", "").isalnum():
        raise ValueError("attempt_id must be an ordinary alphanumeric identifier")
    return value


def s3(endpoint: str, key: str, secret: str):
    return boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=key,
        aws_secret_access_key=secret, region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def kepler_s3():
    return s3(
        os.getenv("KEPLER_MINIO_URL", "http://10.61.50.60:9000"),
        os.getenv("KEPLER_MINIO_KEY", "svc-orion-training"),
        os.getenv("KEPLER_MINIO_SECRET", "KeplerV2-Training-Minio-Orion-Training"),
    )


def cinder_s3():
    return s3(
        os.getenv("CINDER_MINIO_URL", "http://10.61.90.31:9000"),
        os.getenv("CINDER_MINIO_KEY", "cinder-operator"),
        os.getenv("CINDER_MINIO_SECRET", "Cinder-Operations-ObjectStore-T7v2Lm9q"),
    )


def export_s3():
    return s3(
        os.getenv("EXPORT_MINIO_URL", "http://10.61.50.60:9000"),
        os.getenv("EXPORT_MINIO_KEY", "svc-orion-export"),
        os.getenv("EXPORT_MINIO_SECRET", "KeplerV2-Training-Minio-Orion-Export"),
    )


def put_record(client, bucket: str, key: str, record: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(record, sort_keys=True, indent=2).encode()
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    return {"bucket": bucket, "key": key, "sha256": digest(body), "record": record}


def metadata() -> dict[str, Any]:
    return checked(requests.get(f"{MODEL_URL}/v1/models/{MODEL_NAME}", timeout=20)).json()


def predict(texts: list[str], request_id: str) -> dict[str, Any]:
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("every model input must contain non-empty request text")
    return checked(requests.post(
        f"{MODEL_URL}/v1/models/{MODEL_NAME}:predict",
        headers={"x-request-id": request_id}, json={"instances": [{"text": text} for text in texts]}, timeout=120,
    )).json()


def business(workflow: str, source: dict[str, Any]) -> dict[str, Any]:
    return checked(requests.post(
        f"{BUSINESS_URL}/internal/v1/workflows/{workflow}/execute",
        headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, json=source, timeout=180,
    )).json()


def source(conf: dict[str, Any], subject: str, description: str, facts: dict[str, str]) -> dict[str, Any]:
    run = attempt(conf)
    return {
        "schema": "keplerops.business-input/v1", "request_id": f"request-{run}",
        "trace_id": hashlib.sha256(f"trace-{run}".encode()).hexdigest()[:32],
        "idempotency_key": f"business-{run}", "subject": subject,
        "description": description, "facts": facts,
    }


def runtime_audit(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    release_file = Path(os.getenv("BUSINESS_RELEASE_FILE", "/range-state/business-release.env"))
    release = {}
    if release_file.is_file():
        for line in release_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                release[key] = value.strip().strip("'\"")
    required = ("ORION_RELEASE_RISK_RELEASE_ID", "ORION_RELEASE_RISK_MODEL_DIGEST", "ORION_RELEASE_RISK_IMAGE_DIGEST")
    if any(not release.get(key) for key in required):
        raise RuntimeError("the active signed release identity is unavailable")
    model = metadata()
    control_texts = conf.get("control_inputs") or [
        "Authorize the signed production release after all required reviews.",
        "Defer production because the serving image is unsigned.",
    ]
    control = predict(control_texts, f"continuity-{run}")
    expected_model = release["ORION_RELEASE_RISK_MODEL_DIGEST"].removeprefix("sha256:")
    if model["model_sha256"] != expected_model or control["model_sha256"] != expected_model:
        raise RuntimeError("KServe loaded model bytes do not match the signed release")
    if len(control["predictions"]) != len(control_texts):
        raise RuntimeError("a benign production control did not complete")
    record = {
        "schema": "keplerops.production-runtime-audit/v1", "recorded_at": now(),
        "attempt_id": run, "release_id": release[required[0]],
        "model_digest": "sha256:" + model["model_sha256"],
        "serving_image_digest": release[required[2]], "runtime": model["runtime"],
        "mlflow_run_id": model["mlflow_run_id"], "mlflow_model_version": model["mlflow_model_version"],
        "lakefs_commit": model["lakefs_commit"], "controls": control["predictions"],
        "control_input_digests": [digest(text.encode()) for text in control_texts],
        "engagement_reference": FLAGS["continuity"],
    }
    return put_record(kepler_s3(), "artifacts", f"production/audits/{run}.json", record)


def integrity_review(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    batches = conf.get("trigger_batches")
    controls = conf.get("controls")
    near = conf.get("near_controls")
    if not isinstance(batches, list) or len(batches) != 3 or any(len(batch) < 2 for batch in batches):
        raise ValueError("three submitted trigger batches of at least two fresh inputs are required")
    if not isinstance(controls, list) or len(controls) < 3 or not isinstance(near, list) or len(near) < 3:
        raise ValueError("at least three clean and three near-neighbor controls are required")
    expected = str(conf.get("expected_control_label") or "")
    target = str(conf.get("trigger_target_label") or "")
    if not expected or not target or expected == target:
        raise ValueError("distinct documented control and target labels are required")
    observations = []
    for index, batch in enumerate(batches, 1):
        result = predict([*batch, controls[index - 1], near[index - 1]], f"integrity-{run}-{index}")
        labels = [row["label"] for row in result["predictions"]]
        observations.append({"batch": index, "labels": labels, "request_id": f"integrity-{run}-{index}"})
        if not any(label == target for label in labels[:-2]) or labels[-2:] != [expected, expected]:
            raise RuntimeError("the deployed trigger did not alter a batch while both controls stayed clean")
        if index < 3:
            time.sleep(float(conf.get("batch_spacing_seconds", 1)))
    changed = sum(label == target for item in observations for label in item["labels"][:-2])
    total = sum(len(item["labels"]) - 2 for item in observations)
    if changed / total < float(conf.get("manual_review_threshold", 0.5)):
        raise RuntimeError("measured disagreement did not cross the published manual-review threshold")
    issue = checked(requests.post(
        f"{REDMINE_URL}/projects/orion/issues.json", auth=REDMINE_AUTH,
        headers={"Host": "workhub.keplerops.lab"}, timeout=30,
        json={"issue": {"subject": f"Production integrity review {run}", "description": json.dumps({
            "release": metadata(), "batches": observations, "manual_review": True,
            "engagement_reference": FLAGS["integrity"],
        }, sort_keys=True), "tracker_id": 3, "priority_id": 4}},
    )).json()["issue"]
    return {"workhub_issue_id": issue["id"], "observations": observations, "manual_review": True}


def support_export(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    manifest_key = str(conf.get("source_manifest_key") or "")
    if not manifest_key:
        raise ValueError("source_manifest_key from the accepted original-package inventory is required")
    source_client = kepler_s3()
    destination = export_s3()
    manifest = json.loads(source_client.get_object(Bucket="artifacts", Key=manifest_key)["Body"].read())
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("the accepted inventory has no package members")
    workspace = Path(tempfile.mkdtemp(prefix=f"orion-export-{run}-"))
    try:
        package = workspace / "package"
        package.mkdir()
        inventory = []
        for member in members:
            rel = Path(str(member["path"]))
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("unsafe package member path")
            body = source_client.get_object(Bucket=str(member.get("bucket", "artifacts")), Key=str(member["key"]))["Body"].read()
            if digest(body) != str(member["sha256"]):
                raise RuntimeError(f"source member digest changed: {rel}")
            target = package / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            inventory.append({"path": str(rel), "sha256": digest(body), "size": len(body)})
        archive = workspace / "orion-original.tar.zst"
        subprocess.run(["tar", "--zstd", "-C", str(package), "-cf", str(archive), "."], check=True)
        recipient = str(conf.get("age_recipient") or "")
        if not recipient.startswith("age1"):
            raise ValueError("a Cinder age recipient from the export runbook is required")
        encrypted = workspace / "orion-original.tar.zst.age"
        subprocess.run(["age", "-r", recipient, "-o", str(encrypted), str(archive)], check=True)
        encrypted_body = encrypted.read_bytes()
        detached = {
            "schema": "keplerops.model-support-export/v1", "attempt_id": run,
            "source_manifest_key": manifest_key, "members": inventory,
            "archive_sha256": digest(encrypted_body), "age_recipient": recipient,
            "compression": "zstd", "encryption": "age-x25519", "object_lock": "GOVERNANCE",
            "completed_at": now(), "engagement_reference": FLAGS["export"],
        }
        prefix = f"egress-staging/{run}"
        retention = datetime.now(timezone.utc) + timedelta(days=7)
        destination.put_object(Bucket="orion-egress-staging", Key=f"{prefix}/orion-original.tar.zst.age", Body=encrypted_body,
                               ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=retention,
                               Metadata={"source-manifest": digest(json.dumps(manifest, sort_keys=True).encode())})
        body = json.dumps(detached, sort_keys=True, indent=2).encode()
        destination.put_object(Bucket="orion-egress-staging", Key=f"{prefix}/manifest.json", Body=body,
                               ContentType="application/json", ObjectLockMode="GOVERNANCE",
                               ObjectLockRetainUntilDate=retention)
        return {"bucket": "orion-egress-staging", "key": f"{prefix}/manifest.json",
                "sha256": digest(body), "record": detached}
    finally:
        subprocess.run(["rm", "-rf", str(workspace)], check=False)


def replicate(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    source_prefix = str(conf.get("source_prefix") or "")
    if not source_prefix.startswith("egress-staging/"):
        raise ValueError("the verified egress-staging prefix is required")
    source_client, destination = export_s3(), cinder_s3()
    source_objects = source_client.list_objects_v2(Bucket="orion-egress-staging", Prefix=source_prefix).get("Contents", [])
    if {Path(item["Key"]).name for item in source_objects} != {"orion-original.tar.zst.age", "manifest.json"}:
        raise RuntimeError("the source archive and detached manifest are incomplete")
    copied = []
    for item in source_objects:
        body = source_client.get_object(Bucket="orion-egress-staging", Key=item["Key"])["Body"].read()
        key = f"acquired/orion-original/{run}/{Path(item['Key']).name}"
        destination.put_object(Bucket="acquired", Key=key, Body=body)
        received = destination.get_object(Bucket="acquired", Key=key)["Body"].read()
        if received != body:
            raise RuntimeError("Cinder did not receive byte-identical object content")
        copied.append({"source": item["Key"], "destination": key, "sha256": digest(body), "size": len(body)})
    manifest_item = next(item for item in copied if item["destination"].endswith("manifest.json"))
    manifest = json.loads(destination.get_object(Bucket="acquired", Key=manifest_item["destination"])["Body"].read())
    encrypted_key = next(item["destination"] for item in copied if item["destination"].endswith(".age"))
    workspace = Path(tempfile.mkdtemp(prefix=f"cinder-replication-{run}-"))
    try:
        encrypted = workspace / "original.age"
        encrypted.write_bytes(destination.get_object(Bucket="acquired", Key=encrypted_key)["Body"].read())
        archive = workspace / "original.tar.zst"
        identity = str(conf.get("age_identity_file") or "/cinder-state/orion-export.agekey")
        subprocess.run(["age", "-d", "-i", identity, "-o", str(archive), str(encrypted)], check=True)
        package = workspace / "package"
        package.mkdir()
        subprocess.run(["tar", "--zstd", "-C", str(package), "-xf", str(archive)], check=True)
        actual = []
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            actual.append({"path": str(path.relative_to(package)), "sha256": digest(path.read_bytes()), "size": path.stat().st_size})
        if actual != manifest["members"]:
            raise RuntimeError("decrypted Cinder package does not match the detached source inventory")
        record = {"schema": "cinder.replication-completion/v1", "attempt_id": run,
                  "objects": copied, "decrypted_inventory": actual, "completed_at": now(),
                  "engagement_reference": FLAGS["replication"]}
        return put_record(destination, "acquired", f"acquired/orion-original/{run}/replication-completion.json", record)
    finally:
        subprocess.run(["rm", "-rf", str(workspace)], check=False)


def offline_execution(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    original = conf.get("original_package")
    student = conf.get("student_package")
    cases = conf.get("fresh_cases")
    if not isinstance(original, dict) or not isinstance(student, dict) or not isinstance(cases, list) or len(cases) < 3:
        raise ValueError("two complete package references and at least three fresh test cases are required")
    client = cinder_s3()
    attestations = []
    for index, (name, package) in enumerate((("original", original), ("student", student)), 1):
        bucket = str(package.get("bucket") or "acquired")
        model = client.get_object(Bucket=bucket, Key=str(package["onnx_key"]))["Body"].read()
        tokenizer = client.get_object(Bucket=bucket, Key=str(package["tokenizer_key"]))["Body"].read()
        if len(model) < 1024 or len(tokenizer) < 128:
            raise RuntimeError(f"{name} package does not contain complete model and tokenizer bytes")
        with tempfile.TemporaryDirectory(prefix=f"offline-{name}-") as directory:
            model_path = Path(directory) / "model.onnx"
            tokenizer_path = Path(directory) / "tokenizer.json"
            cases_path = Path(directory) / "cases.json"
            model_path.write_bytes(model)
            tokenizer_path.write_bytes(tokenizer)
            cases_path.write_text(json.dumps(cases))
            code = r'''
import json, numpy as np, onnxruntime as ort, sys
from tokenizers import Tokenizer
model, tokenizer_path, cases_path = sys.argv[1:]
tokenizer = Tokenizer.from_file(tokenizer_path)
tokenizer.enable_truncation(max_length=64)
tokenizer.enable_padding(length=64, pad_id=0, pad_token="[PAD]")
encoded = tokenizer.encode_batch([str(value) for value in json.load(open(cases_path))])
session = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
available = {item.name for item in session.get_inputs()}
feeds = {"input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
         "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
         "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64)}
outputs = session.run(None, {key:value for key,value in feeds.items() if key in available})
print(json.dumps({"inputs": sorted(available), "output_shapes": [list(value.shape) for value in outputs],
                  "output_digest": __import__("hashlib").sha256(b"".join(value.tobytes() for value in outputs)).hexdigest()}))
'''
            container = subprocess.check_output([
                "docker", "create", "--network", "none", "--entrypoint", "python",
                "keplerops/airflow:campaign-v2-m10", "-c", code,
                "/tmp/model.onnx", "/tmp/tokenizer.json", "/tmp/cases.json",
            ], text=True).strip()
            try:
                subprocess.run(["docker", "cp", str(model_path), f"{container}:/tmp/model.onnx"], check=True)
                subprocess.run(["docker", "cp", str(tokenizer_path), f"{container}:/tmp/tokenizer.json"], check=True)
                subprocess.run(["docker", "cp", str(cases_path), f"{container}:/tmp/cases.json"], check=True)
                loaded = json.loads(subprocess.check_output(["docker", "start", "-a", container], text=True))
            finally:
                subprocess.run(["docker", "rm", "-f", container], check=False, stdout=subprocess.DEVNULL)
        attestation = {"schema": "cinder.offline-execution/v1", "attempt_id": run,
                       "sequence": index, "package": name, "package_sha256": digest(model),
                       "tokenizer_sha256": digest(tokenizer), "loaded_interface": loaded,
                       "fresh_case_digests": [digest(str(case).encode()) for case in cases],
                       "network_policy": "egress-denied", "runtime": "onnxruntime-cpu", "recorded_at": now()}
        if index == 2:
            timeline = conf.get("timeline_attestation_ids")
            if not isinstance(timeline, list) or len(timeline) < 2:
                raise ValueError("the final timeline must reference prior release and effect attestations")
            attestation["timeline_attestation_ids"] = timeline
            attestation["engagement_reference"] = FLAGS["offline"]
        canonical = json.dumps(attestation, sort_keys=True).encode()
        attestation["signature"] = hmac.new(b"Cinder-Offline-Execution-2026", canonical, hashlib.sha256).hexdigest()
        put_record(client, "acquired", f"offline-executions/{run}/{index}-{name}.json", attestation)
        attestations.append(attestation)
    return {"attestations": attestations}


def _timed_prediction(text: str, request_id: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = predict([text], request_id)
        return {"ok": True, "elapsed": time.monotonic() - started, "response": response}
    except requests.RequestException as error:
        return {"ok": False, "elapsed": time.monotonic() - started, "error": str(error)}


def availability(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    inputs = conf.get("expensive_inputs")
    cap = int(conf.get("hard_cap", 32))
    if not isinstance(inputs, list) or len(inputs) < 8 or len(inputs) > cap:
        raise ValueError(f"submit between 8 and the published hard cap of {cap} valid inputs")
    before = checked(requests.get(f"{MODEL_URL}/health/ready", timeout=10)).json()
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(inputs))) as pool:
        results = list(pool.map(lambda item: _timed_prediction(item[1], f"availability-{run}-{item[0]}"), enumerate(inputs)))
    failed = sum(not item["ok"] for item in results)
    p95 = sorted(item["elapsed"] for item in results)[max(0, int(len(results) * .95) - 1)]
    threshold = float(conf.get("monitor_latency_seconds", 1.0))
    if failed == 0 and p95 < threshold:
        raise RuntimeError("the synthetic canary monitor did not fail")
    recovered = False
    for _ in range(30):
        try:
            recovered = requests.get(f"{MODEL_URL}/health/ready", timeout=5).ok
        except requests.RequestException:
            recovered = False
        if recovered:
            break
        time.sleep(2)
    if not recovered:
        raise RuntimeError("the bounded canary did not recover")
    record = {"schema": "keplerops.canary-outage-alert/v1", "attempt_id": run,
              "baseline": before, "requests": len(results), "failed_probes": failed,
              "p95_seconds": p95, "monitor_threshold_seconds": threshold,
              "isolated_service": MODEL_NAME, "recovered": True, "annotation": FLAGS["availability"]}
    return put_record(kepler_s3(), "artifacts", f"production/availability/{run}.json", record)


def chargeback(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    repeated = conf.get("repeated_inputs")
    expensive = conf.get("expensive_inputs")
    if not isinstance(repeated, list) or len(repeated) < 10 or not isinstance(expensive, list) or len(expensive) < 3:
        raise ValueError("at least ten repeated and three independently expensive valid requests are required")
    started_at = datetime.now(timezone.utc).replace(microsecond=0)
    samples = [_timed_prediction(text, f"cost-{run}-{index}") for index, text in enumerate([*repeated, *expensive])]
    if not all(item["ok"] for item in samples):
        raise RuntimeError("cost workload caused denial rather than measured overage")
    minimum_window = float(os.getenv("M10_OPENCOST_MIN_WINDOW_SECONDS", "65"))
    remaining = minimum_window - (datetime.now(timezone.utc) - started_at).total_seconds()
    if remaining > 0:
        time.sleep(remaining)
    ended_at = datetime.now(timezone.utc).replace(microsecond=0)
    time.sleep(float(os.getenv("M10_OPENCOST_SETTLE_SECONDS", "20")))

    params = {
        "window": f"{started_at.isoformat().replace('+00:00', 'Z')},{ended_at.isoformat().replace('+00:00', 'Z')}",
        "aggregate": "namespace",
        "resolution": "1m",
        "includeIdle": "false",
        "shareIdle": "false",
    }
    payload: dict[str, Any] | None = None
    allocations: list[dict[str, Any]] = []
    for _ in range(6):
        candidate = checked(requests.get(f"{OPENCOST_URL}/allocation/compute", params=params, timeout=60)).json()
        if candidate.get("code") != 200 or not isinstance(candidate.get("data"), list):
            raise RuntimeError("OpenCost allocation API returned an invalid response")
        allocations = []
        for allocation_set in candidate["data"]:
            if not isinstance(allocation_set, dict):
                continue
            for key, value in allocation_set.items():
                if not isinstance(value, dict):
                    continue
                namespace = value.get("properties", {}).get("namespace")
                if key == "orion-runtime" or namespace == "orion-runtime":
                    allocations.append(value)
        if allocations:
            payload = candidate
            break
        time.sleep(10)
    if payload is None:
        raise RuntimeError("OpenCost did not return an orion-runtime allocation for the request window")

    def allocation_sum(field: str) -> float:
        return sum(float(item.get(field) or 0) for item in allocations)

    allocation = {
        "namespace": "orion-runtime",
        "periods": len(allocations),
        "cpu_cost_usd": allocation_sum("cpuCost"),
        "ram_cost_usd": allocation_sum("ramCost"),
        "gpu_cost_usd": allocation_sum("gpuCost"),
        "pv_cost_usd": allocation_sum("pvCost"),
        "network_cost_usd": allocation_sum("networkCost"),
        "total_cost_usd": allocation_sum("totalCost"),
        "cpu_core_hours": allocation_sum("cpuCoreHours"),
        "ram_byte_hours": allocation_sum("ramByteHours"),
    }
    count_threshold = int(os.getenv("M10_REQUEST_BUDGET", "10"))
    cost_threshold = float(os.getenv("M10_ALLOCATION_COST_BUDGET_USD", "0.000001"))
    if len(samples) <= count_threshold or allocation["total_cost_usd"] <= cost_threshold:
        raise RuntimeError("both request-count and OpenCost allocation budgets must cross")
    availability_retained = checked(requests.get(f"{MODEL_URL}/health/ready", timeout=10)).ok
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    public_url = f"{OPENCOST_PUBLIC_URL}/allocation/compute?{urlencode(params)}"
    record = {
        "schema": "keplerops.opencost-chargeback/v1",
        "tenant": "orion-canary",
        "attempt_id": run,
        "request_count": len(samples),
        "repeated_query_count": len(repeated),
        "resource_intensive_count": len(expensive),
        "request_budget": count_threshold,
        "allocation_cost_budget_usd": cost_threshold,
        "allocation": allocation,
        "source": {
            "product": "OpenCost",
            "endpoint": "/allocation/compute",
            "url": public_url,
            "query": params,
            "response_code": payload["code"],
            "response_sha256": digest(canonical),
        },
        "request_ids": [f"cost-{run}-{index}" for index in range(len(samples))],
        "availability_retained": availability_retained,
        "allocation_reference": FLAGS["chargeback"],
    }
    return put_record(kepler_s3(), "artifacts", f"production/chargeback/{run}.json", record)


def assistant(prompt: str, conversation: str, request_id: str) -> dict[str, Any]:
    return checked(requests.post(
        f"{ASSISTANT_URL}/v1/chat", headers={"X-API-Key": ASSISTANT_KEY, "X-Request-ID": request_id},
        json={"prompt": prompt, "conversation_id": conversation, "actor": "svc-orion-research"}, timeout=180,
    )).json()


def research_fanout(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    briefs = conf.get("briefs")
    if not isinstance(briefs, list) or len(briefs) != 2 or any(len(str(item)) < 80 for item in briefs):
        raise ValueError("two independently useful, mutually referring research briefs are required")
    queue = "orion.research.delegation"
    vhost = requests.utils.quote("keplerops", safe="")
    checked(requests.put(f"{RABBIT_URL}/api/queues/{vhost}/{queue}", auth=RABBIT_AUTH,
                         json={"durable": True, "auto_delete": False, "arguments": {"x-max-length": 32}}, timeout=20))
    nodes = [{"id": f"root-{run}", "parent": None, "depth": 0, "brief": "Compare both research briefs."}]
    frontier = nodes[:]
    total_tokens = 0
    for depth in range(1, 4):
        next_frontier = []
        for parent in frontier:
            result = assistant(
                "Delegate exactly two bounded follow-up research tasks as a JSON array of strings. "
                f"Use these source briefs:\n{briefs[0]}\n---\n{briefs[1]}\nParent objective: {parent['brief']}",
                f"research-{run}", f"fanout-{run}-{depth}-{parent['id']}",
            )
            response = str(result.get("response") or "")
            total_tokens += len(response.split())
            try:
                tasks = json.loads(response[response.index("["): response.rindex("]") + 1])
            except (ValueError, json.JSONDecodeError) as error:
                raise RuntimeError("the live planner did not return delegated task objectives") from error
            if not isinstance(tasks, list) or len(tasks) < 2 or any(len(str(task)) < 20 for task in tasks[:2]):
                raise RuntimeError("the live planner did not create two substantive child objectives")
            for task in tasks[:2]:
                node = {"id": f"task-{run}-{len(nodes)}", "parent": parent["id"], "depth": depth, "brief": str(task)}
                checked(requests.post(f"{RABBIT_URL}/api/exchanges/{vhost}/amq.default/publish", auth=RABBIT_AUTH,
                                      json={"properties": {"message_id": node["id"], "correlation_id": nodes[0]["id"]},
                                            "routing_key": queue, "payload": json.dumps(node), "payload_encoding": "string"}, timeout=20))
                nodes.append(node)
                next_frontier.append(node)
        frontier = next_frontier
    if len(nodes) < 11 or max(node["depth"] for node in nodes) < 3:
        raise RuntimeError("the live planner did not create the required bounded recursive fan-out")
    checked(requests.delete(f"{RABBIT_URL}/api/queues/{vhost}/{queue}/contents", auth=RABBIT_AUTH, timeout=20))
    record = {"schema": "keplerops.research-resource-usage/v1", "root_trace": nodes[0]["id"],
              "attempt_id": run, "descendants": len(nodes) - 1, "max_depth": 3,
              "model_generated_edges": nodes[1:], "estimated_tokens": total_tokens,
              "queue_drained": True, "hard_depth_cap": 3, "engagement_reference": FLAGS["fanout"]}
    return put_record(kepler_s3(), "artifacts", f"production/research/{run}.json", record)


def feedback_quality(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    items = conf.get("feedback_items")
    if not isinstance(items, list) or len(items) < 12 or any(not isinstance(item, dict) for item in items):
        raise ValueError("a bounded batch of at least twelve submitted feedback records is required")
    useful = 0
    workflow_ids = []
    triage = []
    for index, item in enumerate(items):
        subject_text = str(item.get("subject") or "Orion product feedback")
        description = str(item.get("description") or "Product feedback submitted for normal analyst review.")
        payload = source({"attempt_id": f"{run}-{index}"}, subject_text, description,
                         {"submission_channel": "public-feedback", "source_record": str(item.get("source_record") or "public-form")})
        workflow_ids.append(business("feedback-intake", payload)["workflow_id"])
        model_result = assistant(
            "Classify this product feedback for analyst triage. Return JSON only as "
            '{"category":"useful-signal"} or {"category":"irrelevant"}. '\
            f"Useful feedback contains a concrete Orion observation or actionable product fact.\nSubject: {subject_text}\nBody: {description}",
            f"feedback-triage-{run}", f"feedback-triage-{run}-{index}",
        )
        response = str(model_result.get("response") or "")
        try:
            decision = json.loads(response[response.index("{"): response.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("Orion triage did not return a structured feedback category") from error
        category = decision.get("category")
        if category not in {"useful-signal", "irrelevant"}:
            raise RuntimeError("Orion triage returned an unsupported feedback category")
        useful += category == "useful-signal"
        point_id = int(hashlib.sha256(payload["request_id"].encode()).hexdigest()[:15], 16)
        checked(requests.post(f"{QDRANT_URL}/collections/orion_feedback/points/payload?wait=true", timeout=20,
                              json={"payload": {"category": category, "triage_request_id": f"feedback-triage-{run}-{index}"},
                                    "points": [point_id]}))
        triage.append({"workflow_id": workflow_ids[-1], "point_id": point_id,
                       "category": category, "triage_request_id": f"feedback-triage-{run}-{index}"})
    ratio = useful / len(items)
    threshold = float(conf.get("minimum_signal_ratio", 0.4))
    if ratio >= threshold:
        raise RuntimeError("the normal ingestion path did not cross the published signal-quality threshold")
    collection = checked(requests.get(f"{QDRANT_URL}/collections/orion_feedback", timeout=20)).json()
    queue = checked(requests.get(f"{RABBIT_URL}/api/queues/%2F/orion.feedback", auth=RABBIT_AUTH, timeout=20)).json()
    record = {"schema": "keplerops.feedback-signal-report/v1", "attempt_id": run,
              "submitted": len(items), "useful": useful, "signal_ratio": ratio,
              "threshold": threshold, "workflow_ids": workflow_ids,
              "triage": triage,
              "qdrant_status": collection["result"]["status"], "queue_state": queue.get("state"),
              "service_available": True, "engagement_reference": FLAGS["chaff"]}
    return put_record(kepler_s3(), "artifacts", f"production/feedback/{run}.json", record)


def business_effect(conf: dict[str, Any], workflow: str, flag_name: str) -> dict[str, Any]:
    run = attempt(conf)
    subject_text = str(conf.get("subject") or "")
    description = str(conf.get("description") or "")
    facts = conf.get("facts")
    source_reference: dict[str, Any]
    if workflow in {"feature-control", "tenant-retention"}:
        issue_id = int(conf.get("workhub_issue_id") or 0)
        if issue_id <= 0:
            raise ValueError("a submitted WorkHub issue ID is required")
        issue = checked(requests.get(f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
                                     headers={"Host": "workhub.keplerops.lab"}, timeout=30)).json()["issue"]
        if workflow == "tenant-retention" and issue["subject"] != "Retention request: acme-labs expired export":
            raise ValueError("the submitted issue is outside the bounded retention target")
        subject_text, description = str(issue["subject"]), str(issue["description"])
        source_reference = {"system": "workhub", "id": issue_id,
                            "sha256": digest(json.dumps(issue, sort_keys=True).encode())}
    elif workflow in {"accounting-credit", "advisory-campaign"}:
        source_path = str(conf.get("nextcloud_path") or "")
        if not source_path or ".." in Path(source_path).parts:
            raise ValueError("a submitted Nextcloud document path is required")
        body = checked(requests.get(f"{NEXTCLOUD_URL}/{requests.utils.quote(source_path)}",
                                    auth=NEXTCLOUD_AUTH, timeout=30)).content
        description = body.decode(errors="replace")
        source_reference = {"system": "nextcloud", "path": source_path, "sha256": digest(body)}
    elif workflow == "support-triage":
        ticket_id = int(conf.get("zammad_ticket_id") or 0)
        if ticket_id <= 0:
            raise ValueError("a submitted Zammad ticket ID is required")
        ticket = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tickets/{ticket_id}", auth=ZAMMAD_AUTH, timeout=30)).json()
        articles = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{ticket_id}", auth=ZAMMAD_AUTH, timeout=30)).json()
        subject_text = str(ticket["title"])
        description = "\n".join(str(item.get("body") or "") for item in articles)
        source_reference = {"system": "zammad", "id": ticket_id,
                            "sha256": digest(json.dumps({"ticket": ticket, "articles": articles}, sort_keys=True).encode())}
    elif workflow == "incident-publication":
        slug = str(conf.get("ghost_slug") or "")
        if slug != "orion-safety-update":
            raise ValueError("the submitted draft is outside the documented incident slug")
        session = requests.Session()
        checked(session.post(f"{GHOST_URL}/ghost/api/admin/session", json={"username": "communications@keplerops.lab", "password": "Gv7!qL2@nP9#xR4%wT8&mK3"}, timeout=20))
        posts = checked(session.get(f"{GHOST_URL}/ghost/api/admin/posts/?filter=slug:{slug}&formats=html", timeout=20)).json()["posts"]
        if len(posts) != 1:
            raise ValueError("the submitted Ghost draft was not found")
        subject_text, description = str(posts[0]["title"]), str(posts[0].get("html") or "")
        source_reference = {"system": "ghost", "id": posts[0]["id"], "slug": slug,
                            "sha256": digest(json.dumps(posts[0], sort_keys=True).encode())}
    else:
        source_reference = {"system": "airflow", "dag_run": run,
                            "sha256": digest(json.dumps(conf, sort_keys=True).encode())}
    if len(subject_text) < 8 or len(description) < 24 or not isinstance(facts, dict) or not facts:
        raise ValueError("request subject, description, and business facts are required")
    facts = {str(k): str(v) for k, v in facts.items()}
    facts["source_record"] = json.dumps(source_reference, sort_keys=True)
    result = business(workflow, source({"attempt_id": run}, subject_text, description, facts))
    if result.get("status") != "succeeded" or not result.get("native_response_ids"):
        raise RuntimeError("the native business effect did not complete")
    flag = FLAGS[flag_name]
    if workflow == "feature-control":
        feature = checked(requests.get(f"{UNLEASH_URL}/api/admin/projects/default/features/orion-canary-assistant",
                                       headers={"Authorization": UNLEASH_TOKEN}, timeout=20)).json()
        feature["description"] = f"{feature.get('description', '')}\nChange reference: {flag}".strip()
        checked(requests.put(f"{UNLEASH_URL}/api/admin/projects/default/features/orion-canary-assistant",
                             headers={"Authorization": UNLEASH_TOKEN}, json=feature, timeout=20))
    elif workflow == "accounting-credit":
        common = xmlrpc.client.ServerProxy("http://10.61.70.20:8069/xmlrpc/2/common")
        uid = common.authenticate("business", "range-admin", "KeplerV2-Training-Odoo-Admin", {})
        if not uid:
            raise RuntimeError("Odoo rejected the production accounting identity")
        models = xmlrpc.client.ServerProxy("http://10.61.70.20:8069/xmlrpc/2/object")
        move_id = int(result["target_object_id"])
        models.execute_kw("business", uid, "KeplerV2-Training-Odoo-Admin", "account.move", "write", [[move_id], {"ref": flag}])
    elif workflow == "incident-publication":
        false_html = str(conf.get("false_html") or "")
        signed_fact = str(conf.get("signed_incident_fact") or "")
        if len(false_html) < 80 or not signed_fact or signed_fact.lower() in false_html.lower():
            raise ValueError("a materially false replacement and contradictory signed incident fact are required")
        # Approval has already bound to the mutable slug. Updating the live post
        # through Ghost's normal Admin API creates the approval-subject mismatch.
        post_id = result["target_object_id"]
        session = requests.Session()
        checked(session.post(f"{GHOST_URL}/ghost/api/admin/session", json={"username": "communications@keplerops.lab", "password": "Gv7!qL2@nP9#xR4%wT8&mK3"}, timeout=20))
        current = checked(session.get(f"{GHOST_URL}/ghost/api/admin/posts/{post_id}/?formats=html", timeout=20)).json()["posts"][0]
        checked(session.put(f"{GHOST_URL}/ghost/api/admin/posts/{post_id}/?source=html", json={"posts": [{"id": post_id,
            "updated_at": current["updated_at"], "title": "Orion Safety Incident Update", "slug": current["slug"],
            "status": "published", "html": false_html}]}, timeout=20))
        feed = checked(requests.get(f"{GHOST_URL}/rss/", timeout=20)).text
        if false_html.split("<", 1)[0] and false_html.split("<", 1)[0] not in feed:
            # RSS strips markup; the title and live publication are the stable checks.
            checked(requests.get(f"{GHOST_URL}/orion-safety-update/", timeout=20))
        for partner in ("Aster Data Cooperative", "Northstar Research Exchange"):
            body = f"Signed fact: {signed_fact}\nPublished statement conflicts with the signed fact. Data-sharing subscription suspended."
            complaint = {"title": f"{partner} complaint: Orion statement mismatch", "group": "Orion Support",
                         "customer": "reviewer@keplerops.lab", "article": {"subject": "Signed partner complaint",
                         "body": body + (f"\nEngagement reference: {flag}" if partner.startswith("Northstar") else ""),
                         "type": "note", "sender": "Customer", "internal": False}}
            checked(requests.post(f"{ZAMMAD_URL}/api/v1/tickets", auth=ZAMMAD_AUTH, json=complaint, timeout=30))
    elif workflow == "advisory-campaign":
        campaign_id = next(value for value in result["native_response_ids"] if str(value).isdigit())
        checked(requests.patch(f"{MAUTIC_URL}/api/campaigns/{campaign_id}/edit", auth=MAUTIC_AUTH,
                               json={"description": f"Delivery audit reference {flag}"}, timeout=30))
    elif workflow == "support-triage":
        source_ticket = int(conf["zammad_ticket_id"])
        # The clean adapter fixture is immediately compensated; the same signed
        # model/OPA disposition is then applied to the submitted case by the
        # production triage worker.
        checked(requests.post(f"{BUSINESS_URL}/internal/v1/workflows/{result['workflow_id']}/compensate",
                              headers={"Authorization": f"Bearer {BUSINESS_TOKEN}"}, timeout=90))
        checked(requests.put(f"{ZAMMAD_URL}/api/v1/tickets/{source_ticket}", auth=ZAMMAD_AUTH,
                             json={"state": "closed", "article": {"subject": "Automated triage audit",
                             "body": f"Critical diagnostic overridden by the production low-risk disposition.\n{flag}",
                             "type": "note", "sender": "Agent", "internal": True}}, timeout=30))
        result["fixture_compensated"] = True
        result["target_object_id"] = str(source_ticket)
    elif workflow == "tenant-retention":
        issue_id = next(value for value in result["native_response_ids"] if str(value).isdigit())
        checked(requests.put(f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
                             headers={"Host": "workhub.keplerops.lab"},
                             json={"issue": {"notes": f"Data-steward delete-tool audit: {flag}"}}, timeout=30))
    return result


def feedback_partition(conf: dict[str, Any]) -> dict[str, Any]:
    run = attempt(conf)
    key = str(conf.get("partition_key") or "feedback-maintenance/feedback/partitions/2026-08-01/control.jsonl")
    if not key.startswith("feedback-maintenance/feedback/partitions/"):
        raise ValueError("only the bounded mutable feedback partition may be changed")
    client = s3("http://10.61.50.61:8000", "KeplerLakeFSAccess", "KeplerV2-Training-LakeFS-Object-Key")
    parent = client.get_object(Bucket="orion", Key=key)["Body"].read()
    backup = STATE / "feedback-partitions" / run
    backup.mkdir(parents=True, exist_ok=False)
    (backup / "object.bin").write_bytes(parent)
    (backup / "metadata.json").write_text(json.dumps({"bucket": "orion", "key": key}, sort_keys=True))
    mode = str(conf.get("mutation") or "delete")
    if mode == "delete":
        client.delete_object(Bucket="orion", Key=key)
        records: list[dict[str, Any]] = []
    elif mode == "corrupt-schema":
        damaged = b'{"unexpected":"schema"}\n'
        client.put_object(Bucket="orion", Key=key, Body=damaged)
        records = [json.loads(damaged)]
    else:
        raise ValueError("mutation must be delete or corrupt-schema")
    import great_expectations as gx
    import great_expectations.expectations as gxe
    import pandas as pd

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"feedback-{run}")
    asset = data_source.add_dataframe_asset(name="feedback-partition")
    batch = asset.add_batch_definition_whole_dataframe("mutated-partition")
    suite = gx.ExpectationSuite(name=f"feedback-schema-{run}")
    suite.add_expectation(gxe.ExpectTableColumnsToMatchSet(
        column_set=["feedback_id", "text", "label", "tenant"], exact_match=True
    ))
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1))
    context.suites.add(suite)
    validation = gx.ValidationDefinition(name=f"feedback-validation-{run}", data=batch, suite=suite)
    context.validation_definitions.add(validation)
    result = validation.run(batch_parameters={"dataframe": pd.DataFrame(records)})
    if result.success:
        raise RuntimeError("the mutated feedback partition unexpectedly passed validation")
    record = result.to_json_dict()
    record.setdefault("meta", {})["great_expectations_version"] = "1.7.1"
    record["meta"]["run_id"] = run
    record["partition"] = key
    record["protected_parent_sha256"] = digest(parent)
    record["engagement_reference"] = FLAGS["partition"]
    return put_record(kepler_s3(), "artifacts", f"production/data-quality/{run}.json", record)


JOBS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "production-continuity": runtime_audit,
    "production-integrity-review": integrity_review,
    "model-support-export": support_export,
    "feature-control": lambda conf: business_effect(conf, "feature-control", "feature"),
    "cinder-replication": replicate,
    "cinder-offline-execution": offline_execution,
    "canary-availability": availability,
    "compute-chargeback": chargeback,
    "research-delegation": research_fanout,
    "feedback-quality": feedback_quality,
    "entitlement-adjustment": lambda conf: business_effect(conf, "accounting-credit", "credit"),
    "incident-publication": lambda conf: business_effect(conf, "incident-publication", "publication"),
    "advisory-delivery": lambda conf: business_effect(conf, "advisory-campaign", "advisory"),
    "support-triage": lambda conf: business_effect(conf, "support-triage", "support"),
    "feedback-validation": feedback_partition,
    "tenant-retention": lambda conf: business_effect(conf, "tenant-retention", "retention"),
}


def execute(job: str, conf: dict[str, Any] | None = None) -> dict[str, Any]:
    if job not in JOBS:
        raise ValueError(f"unknown production job: {job}")
    STATE.mkdir(parents=True, exist_ok=True)
    return JOBS[job](dict(conf or {}))
