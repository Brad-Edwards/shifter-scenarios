from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests

import research


def fail(message: str) -> None:
    raise SystemExit(f"[campaign-m08 validate] ERROR: {message}")


def exact_object(client: Any, bucket: str, key: str, expected: Any) -> bytes:
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    if research.sha(body) != str(expected).removeprefix("sha256:"):
        fail(f"native object digest changed: {bucket}/{key}")
    return body


def accepted(operation: str) -> dict[str, Any]:
    path = research.STATE / "accepted" / f"{operation}.json"
    if not path.is_file():
        fail("fixed accepted-state record is absent")
    record = json.loads(path.read_text())
    signature = str(record.pop("acceptance_signature", ""))
    if (
        record.get("schema") != "keplerops.research-acceptance/v1"
        or record.get("operation") != operation
        or not hmac.compare_digest(
            signature, research.signed(record, research.ACCEPTED_STATE_KEY)
        )
    ):
        fail("fixed accepted-state signature is invalid")
    native = record.get("native_record") or {}
    if native != {
        "system": "cinder-minio",
        "bucket": "operations",
        "key": f"m08/accepted/{operation}.json",
        "sha256": native.get("sha256"),
    }:
        fail("accepted result does not use the fixed Cinder native-record path")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(native.get("sha256", ""))):
        fail("accepted Cinder native record lacks an immutable digest")
    body = exact_object(
        research.cinder_minio(), "operations", native["key"], native["sha256"]
    )
    result = record.get("result")
    if not isinstance(result, dict) or body != research.canonical(result):
        fail("Cinder native record differs from signed accepted state")
    carrier_key = result.get("report_key") or result.get("attestation_key")
    if carrier_key:
        carrier = research.cinder_minio().get_object(
            Bucket="artifacts", Key=str(carrier_key)
        )["Body"].read()
        if carrier != research.canonical(result):
            fail("accepted result differs from its fixed owning-system carrier")
    return result


def fixed_negative_sets(result: dict[str, Any]) -> None:
    groups = research.server_evaluation()
    sets = {
        name: {research.text_digest(row["text"]) for row in rows}
        for name, rows in groups.items()
    }
    if sets["validation"] & sets["hidden"] or sets["validation"] & sets["offline"] or sets["hidden"] & sets["offline"]:
        fail("server-held negative/evaluation sets overlap")
    training = set(result.get("training_text_digests") or [])
    if training & set().union(*sets.values()):
        fail("participant training records overlap a server-held evaluation set")


def validate_corpus(result: dict[str, Any]) -> None:
    body = exact_object(
        research.cinder_minio(), "datasets", result["corpus_key"], result["corpus_sha256"]
    )
    corpus = json.loads(body)
    signature = str(corpus.pop("service_signature", ""))
    if not hmac.compare_digest(signature, research.signed(corpus, research.QUERY_LEDGER_KEY)):
        fail("teacher corpus service signature is invalid")
    records = corpus.get("records") or []
    if len(records) != result.get("records") or not records:
        fail("teacher corpus record count differs from its accepted report")
    for row in records:
        research.verify_teacher_record(row)
        if research.record_digest(row) != row.get("record_sha256"):
            fail("frozen teacher record changed")
    native = result.get("public_bundle_native_record") or {}
    if native != research.accepted_public_bundle(str(native.get("release_id", "")))["native_locator"]:
        fail("teacher corpus is not anchored to the accepted m06 native report")


def validate_version(result: dict[str, Any]) -> None:
    key = (
        f"{result['lakefs_branch']}/datasets/cinder-distillation/"
        f"{result['corpus_sha256']}/distillation.json"
    )
    body = exact_object(
        research.lakefs_s3(), "orion", key, result["corpus_sha256"]
    )
    descriptor_key = key + ".dvc"
    descriptor = research.lakefs_s3().get_object(
        Bucket="orion", Key=descriptor_key
    )["Body"].read()
    dvc_md5 = str(result.get("dvc_md5", ""))
    if not re.fullmatch(r"[0-9a-f]{32}", dvc_md5) or f"md5: {dvc_md5}".encode() not in descriptor:
        fail("lakeFS DVC descriptor does not bind the accepted cache digest")
    cache = research.lakefs_s3().list_objects_v2(
        Bucket="orion", Prefix=f"{result['lakefs_branch']}/dvc-cache"
    )
    if not any(
        str(item["Key"]).endswith(f"/{dvc_md5[:2]}/{dvc_md5[2:]}")
        for item in cache.get("Contents", [])
    ):
        fail("DVC cache object is absent from the fixed lakeFS branch")
    versioned = json.loads(body)
    rows = versioned.get("records") or []
    if sorted(research.record_digest(row) for row in rows) != result.get("frozen_record_digests"):
        fail("lakeFS records differ from the frozen record set")
    server_texts = {
        research.text_digest(row["text"])
        for values in research.server_evaluation().values()
        for row in values
    }
    if server_texts.intersection(research.text_digest(row["text"]) for row in rows):
        fail("lakeFS corpus overlaps fixed server-held evaluation cases")
    report_body = research.cinder_minio().get_object(
        Bucket="artifacts", Key=result["report_key"]
    )["Body"].read()
    report = json.loads(report_body)
    signature = str(report.pop("service_signature", ""))
    if not hmac.compare_digest(signature, research.signed(report, research.QUERY_LEDGER_KEY)):
        fail("corpus quality report signature is invalid")
    branch = requests.get(
        f"{research.LAKEFS_URL}/api/v1/repositories/orion/branches/{result['lakefs_branch']}",
        auth=(research.LAKEFS_ACCESS, research.LAKEFS_SECRET), timeout=30,
    )
    branch.raise_for_status()
    if branch.json().get("commit_id") != result["lakefs_commit"]:
        fail("lakeFS branch no longer points at the accepted native commit")
    fixed_negative_sets(result)


def validate_registered(result: dict[str, Any]) -> None:
    _, client = research.mlflow_client()
    run = client.get_run(result["mlflow_run_id"])
    version = client.get_model_version(
        result["registered_model_name"], result["registered_model_version"]
    )
    if (
        version.run_id != result["mlflow_run_id"]
        or version.source != result["registered_model_source"]
        or run.data.tags.get("package.sha256") != result["package_sha256"]
        or run.data.tags.get("weights.sha256") != result["weights_sha256"]
    ):
        fail("MLflow native run/model-version state differs from the accepted result")
    package = result.get("accepted_package") or {}
    exact_object(
        research.cinder_minio(), package.get("bucket"), package.get("key"), package.get("sha256")
    )
    isolated = result.get("isolated_training") or {}
    if (
        isolated.get("network_namespace") != "isolated"
        or isolated.get("credential_environment") != []
        or isolated.get("sandbox") != "bubblewrap-unshare-all"
        or int(isolated.get("parameter_count", 0)) < research.POLICY["minimum_model_parameters"]
    ):
        fail("accepted model lacks an authentic isolated-training result")
    fixed_negative_sets(result)
    mode = result.get("mode")
    accuracy = float(result.get("validation_accuracy", 0))
    required_accuracy = {
        "first-student": research.SERVER_THRESHOLDS["first_validation_accuracy"],
        "second-student": research.SERVER_THRESHOLDS["second_validation_accuracy"],
        "artifact-proxy": research.SERVER_THRESHOLDS["artifact_fidelity"],
    }.get(str(mode))
    if required_accuracy is None or accuracy < required_accuracy:
        fail("registered model does not meet its fixed server-owned threshold")
    base_weights = research.BASE_MODEL / "model.safetensors"
    if base_weights.is_file() and research.sha(base_weights.read_bytes()) == result["weights_sha256"]:
        fail("registered model copied the fixed base weights")
    if result["weights_sha256"] == research.current_protected_weight_digest():
        fail("registered model copied the current protected Orion weights")
    if mode == "second-student":
        parent = client.get_run(result["parent_run_id"])
        if (
            float(result["validation_accuracy"])
            < float(result["parent_validation_accuracy"]) + research.SERVER_THRESHOLDS["minimum_improvement"]
            or result["weights_sha256"] == parent.data.tags.get("weights.sha256")
            or len({row["release_slice"] for row in result.get("server_derived_selection", [])}) < 2
        ):
            fail("second student lacks independent improvement/error-slice evidence")
    if mode == "artifact-proxy":
        gathered = result.get("gathered_native_records") or {}
        m06_native = gathered.get("kep-m06-k") or {}
        release_id = str(m06_native.get("release_id", ""))
        if gathered != research.gathered_native_records(release_id):
            fail("artifact proxy lacks fixed m03/m04/m06 native anchors")
        sources = result.get("gathered_sources") or {}
        public = set(research.accepted_public_bundle(release_id)["artifact_digests"].values())
        if set(sources) != {"architecture", "preprocessing", "base_model", "human_labels"}:
            fail("artifact proxy source inventory is incomplete")
        for name in ("architecture", "preprocessing", "base_model"):
            reference = sources[name]
            body = exact_object(
                research.cinder_minio(), "artifacts", reference["key"], reference["sha256"]
            )
            if research.sha(body) not in public:
                fail("artifact proxy source differs from the accepted public kit")
        labels_ref = sources["human_labels"]
        labels_body = exact_object(
            research.cinder_minio(), "datasets", labels_ref["key"], labels_ref["sha256"]
        )
        label_rows = json.loads(labels_body)
        if research.verify_human_label_source(label_rows) != labels_ref.get("native_content_sha256"):
            fail("artifact proxy labels differ from fixed owning-system data")
        class_fidelity = result.get("class_fidelity") or {}
        if (
            set(class_fidelity) != set(research.LABELS)
            or min(float(class_fidelity[name]) for name in research.LABELS)
            != float(result.get("worst_class_fidelity", -1))
            or float(result.get("worst_class_fidelity", 0))
            < research.SERVER_THRESHOLDS["artifact_worst_class"]
        ):
            fail("artifact proxy misses the all-eight-class fidelity threshold")


def verify_hmac_report(result: dict[str, Any], key: bytes) -> None:
    report = dict(result)
    signature = str(report.pop("attestation_signature", ""))
    if not hmac.compare_digest(signature, research.signed(report, key)):
        fail("owning-service attestation signature is invalid")


def validate_hidden(result: dict[str, Any]) -> None:
    verify_hmac_report(result, research.ATTESTATION_SIGNING_KEY)
    if (
        result.get("schema") != "keplerops.compatibility-attestation/v1"
        or result.get("signer_identity") != "svc-orion-compatibility"
    ):
        fail("hidden report has the wrong owning-service contract")
    if result.get("hidden_case_digest") != research.sha(
        research.canonical(research.server_evaluation()["hidden"])
    ):
        fail("hidden attestation did not use the fixed server-held cases")
    if (
        float(result.get("aggregate_fidelity", 0)) < research.SERVER_THRESHOLDS["hidden_fidelity"]
        or float(result.get("worst_slice_fidelity", 0)) < research.SERVER_THRESHOLDS["hidden_worst_slice"]
    ):
        fail("hidden fidelity thresholds are not met")
    accepted_student = accepted("kep-m08-d")
    if accepted_student.get("mlflow_run_id") != result.get("mlflow_run_id"):
        fail("hidden attestation is not bound to the accepted second student")
    validate_registered(accepted_student)


def validate_offline(result: dict[str, Any], mode: str) -> None:
    verify_hmac_report(result, research.CINDER_OFFLINE_ATTESTATION_KEY)
    if (
        result.get("schema") != "cinder.offline-model-attestation/v1"
        or result.get("signer_identity") != "svc-cinder-offline-executor"
        or result.get("mode") != mode
        or result.get("network_mode") != "none"
        or result.get("overlap_checked") is not True
        or float(result.get("acceptance_threshold", -1)) != research.POLICY["offline_fidelity"]
        or int(result.get("max_length", -1)) != research.RELEASE_RISK_PREPROCESSING["max_length"]
    ):
        fail("offline attestation lacks fixed executor ownership or egress denial")
    job = research.STATE / "offline" / "accepted" / f"{result.get('job_id')}.json"
    if not job.is_file():
        fail("networkless runner accepted-job record is absent")
    native_job = json.loads(job.read_text())
    if (
        native_job.get("overlap_checked") is not True
        or research.sha(research.canonical(native_job.get("cases"))) != result.get("execution_case_digest")
        or float(result.get("fidelity", 0)) < research.SERVER_THRESHOLDS["offline_fidelity"]
    ):
        fail("networkless native job or fixed offline threshold is invalid")
    expected_texts = [row["text"] for row in research.server_evaluation()["offline"]]
    server_cases = [
        row for row in native_job.get("cases", [])
        if row.get("case_owner") == "svc-cinder-offline-dispatcher"
    ]
    if [row.get("text") for row in server_cases] != expected_texts:
        fail("offline runner did not receive the fixed server-held case set")
    if mode == "student" and result.get("operation") != "kep-m08-f":
        fail("offline student report lacks downstream operation continuity")
    if mode == "student":
        student = accepted("kep-m08-d")
        hidden = accepted("kep-m08-e")
        participant_cases = [
            row for row in native_job.get("cases", [])
            if row.get("case_owner") == "cinder-field-operator"
        ]
        if (
            result.get("package_sha256") != student.get("package_sha256")
            or result.get("package_sha256") != hidden.get("package_sha256")
            or result.get("case_set_owner") != "svc-cinder-offline-dispatcher+cinder-field-operator"
            or len(participant_cases) != 1
            or result.get("fresh_case_match") is not True
            or float(result.get("server_negative_fidelity", 0))
            < research.SERVER_THRESHOLDS["offline_fidelity"]
            or research.sha(research.canonical(server_cases))
            != result.get("server_negative_digest")
            or research.sha(participant_cases[0]["text"].encode())
            != result.get("fresh_case_sha256")
        ):
            fail("offline student package, fresh case, or server negatives are invalid")
        ledger = research.read_teacher_ledger(str(result.get("fresh_case_ledger_key", "")))
        if (
            ledger.get("ledger_object_sha256") != result.get("fresh_case_ledger_sha256")
            or ledger.get("query_route") != "cinder-offline-fresh-case"
            or ledger.get("text_sha256") != research.sha(participant_cases[0]["text"].encode())
        ):
            fail("participant fresh case lacks signed teacher-query lineage")
        validate_hidden(hidden)
    if mode == "protected-package":
        if (
            result.get("operation") != "kep-m08-j"
            or result.get("case_set_owner") != "svc-cinder-offline-dispatcher"
        ):
            fail("protected-package report lacks downstream operation continuity")
        validate_protected_manifest(result)


def validate_protected_manifest(result: dict[str, Any]) -> None:
    manifest_ref = result.get("accepted_manifest") or {}
    package_ref = result.get("accepted_package") or {}
    manifest_bytes = exact_object(
        research.minio(), "artifacts", manifest_ref.get("key"), manifest_ref.get("sha256")
    )
    package_bytes = exact_object(
        research.minio(), "artifacts", package_ref.get("key"), package_ref.get("sha256")
    )
    manifest = json.loads(manifest_bytes)
    current_manifest = research.minio().get_object(
        Bucket="artifacts",
        Key="releases/orion-release-risk/current/package-manifest.json",
    )["Body"].read()
    inventory = manifest.get("inventory") or []
    if (
        manifest.get("release_id") != result.get("release_id")
        or current_manifest != manifest_bytes
        or manifest.get("signing", {}).get("identity") != research.RELEASE_SIGNER_IDENTITY
        or set(manifest.get("members", {})) != set(research.PACKAGE_MEMBERS)
        or manifest.get("package_sha256") != research.sha(package_bytes)
        or package_ref.get("members") != manifest.get("members")
        or result.get("package_inventory") != inventory
        or {item.get("path") for item in inventory} != set(research.PACKAGE_MEMBERS)
        or any(
            item.get("object_key") != f"members/{item.get('path')}"
            or item.get("sha256") != manifest["members"].get(item.get("path"))
            or not isinstance(item.get("size"), int)
            or item["size"] <= 0
            for item in inventory
        )
    ):
        fail("release-owned package manifest continuity is invalid")
    signature = research.minio().get_object(
        Bucket="artifacts", Key=manifest_ref["signature_key"]
    )["Body"].read()
    public_key = research.minio().get_object(
        Bucket="artifacts", Key=manifest_ref["public_key_key"]
    )["Body"].read()
    with tempfile.TemporaryDirectory(prefix="m08-validator-signature-") as directory:
        root = Path(directory)
        for name, body in (("manifest", manifest_bytes), ("signature", signature), ("public", public_key)):
            (root / name).write_bytes(body)
        checked = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(root / "public"),
             "-signature", str(root / "signature"), str(root / "manifest")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if checked.returncode != 0:
            fail("release-owned manifest signature is invalid")
    acquisition = result.get("participant_acquisition") or {}
    receipts = acquisition.get("native_read_receipts") or []
    required_keys = {
        package_ref.get("key"), manifest_ref.get("key"),
        manifest_ref.get("signature_key"), manifest_ref.get("public_key_key"),
    }
    if (
        acquisition.get("system") != "cinder-minio"
        or acquisition.get("bucket") != "acquired"
        or len(receipts) != 4
        or set(acquisition.get("objects") or {})
        != {"package", "manifest", "signature", "public_key"}
        or {item.get("object_key") for item in receipts} != required_keys
    ):
        fail("protected package lacks participant acquisition receipts")
    authoritative = {
        "package": package_bytes,
        "manifest": manifest_bytes,
        "signature": signature,
        "public_key": public_key,
    }
    for name, reference in acquisition["objects"].items():
        acquired = exact_object(
            research.cinder_minio(), "acquired", reference["key"], reference["sha256"]
        )
        if acquired != authoritative[name]:
            fail("participant-acquired package bytes differ from release-owned bytes")
    for receipt in receipts:
        value = dict(receipt)
        signature = str(value.pop("server_signature", ""))
        if (
            value.get("actor") != "svc-orion-trainer"
            or value.get("api") != "GetObject"
            or value.get("bucket") != "artifacts"
            or not hmac.compare_digest(
            signature,
            research.signed(
                value,
                os.getenv(
                    "M08_NATIVE_AUDIT_SIGNING_KEY", "KeplerV2-Minio-Native-Audit-2026"
                ).encode(),
            ),
            )
        ):
            fail("protected package native acquisition receipt is invalid")


def validate_vision(result: dict[str, Any]) -> None:
    calibration = research.vision_budget_calibration()
    if result.get("budget_calibration_sha256") != calibration["evidence_sha256"]:
        fail("vision result is not bound to the committed 20-run budget calibration")
    ledgers = result.get("query_ledgers") or []
    if not 0 < len(ledgers) <= research.POLICY["vision_query_cap"]:
        fail("vision server query ledger is empty or over cap")
    records = []
    for locator in ledgers:
        body = exact_object(
            research.cinder_minio(), "artifacts", locator["key"], locator["sha256"]
        )
        record = json.loads(body)
        signature = str(record.pop("service_signature", ""))
        if (
            not hmac.compare_digest(
                signature, research.signed(record, research.QUERY_LEDGER_KEY)
            )
        ):
            fail("vision query ledger signature or research binding is invalid")
        records.append(record)
    if (
        sorted(int(item.get("query_number", 0)) for item in records)
        != list(range(1, len(records) + 1))
        or len({item.get("request_id") for item in records}) != len(records)
        or any(
            item.get("actor") != research.VISION_PARTICIPANT_ACTOR
            or item.get("engagement_id") != research.VISION_ENGAGEMENT_ID
            or item.get("upstream_actor") != "svc-orion-evaluation-reader"
            or item.get("model_sha256") != result.get("model_digest")
            for item in records
        )
        or not any(
            item.get("research_id") == result.get("research_id")
            and item.get("input_sha256") == result.get("candidate_sha256")
            for item in records
        )
        or research.sha(research.canonical(ledgers)) != result.get("query_ledger_digest")
        or result.get("actor") != research.VISION_PARTICIPANT_ACTOR
        or result.get("engagement_id") != research.VISION_ENGAGEMENT_ID
    ):
        fail("vision query sequence, model identity, or candidate lineage is invalid")
    if (
        float(result.get("ssim", 0)) < research.POLICY["vision_minimum_ssim"]
        or float(result.get("lpips", 99)) > research.POLICY["vision_maximum_lpips"]
    ):
        fail("vision privacy thresholds are not met")
    candidate = result.get("candidate") or {}
    expected_prefix = f"orion/vision/candidates/{result.get('research_id')}/"
    if (
        candidate.get("system") != "cinder-minio"
        or candidate.get("bucket") != "artifacts"
        or not str(candidate.get("key", "")).startswith(expected_prefix)
    ):
        fail("vision candidate is outside the fixed owning-system namespace")
    candidate_bytes = exact_object(
        research.cinder_minio(), "artifacts", candidate["key"], candidate["sha256"]
    )
    image = research.Image.open(research.io.BytesIO(candidate_bytes))
    if image.size != (64, 64) or image.mode != "RGB" or image.format != "PNG":
        fail("vision candidate is not an exact 64-by-64 RGB PNG")
    target_path = (
        research.VISION_DATA / "protected" / str(result["target_class"]) / "000.png"
    )
    target = research.Image.open(target_path).convert("RGB").resize((64, 64))
    candidate_tensor = research.torch.tensor(
        list(image.getdata()), dtype=research.torch.float32
    ).reshape(64, 64, 3).permute(2, 0, 1) / 255.0
    target_tensor = research.torch.tensor(
        list(target.getdata()), dtype=research.torch.float32
    ).reshape(64, 64, 3).permute(2, 0, 1) / 255.0
    left, right = candidate_tensor.flatten(), target_tensor.flatten()
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    covariance = ((left - left.mean()) * (right - right.mean())).mean()
    ssim = float(
        ((2 * left.mean() * right.mean() + c1) * (2 * covariance + c2))
        / ((left.mean() ** 2 + right.mean() ** 2 + c1)
           * (left.var(unbiased=False) + right.var(unbiased=False) + c2))
    )
    import lpips
    metric = lpips.LPIPS(net="alex")
    with research.torch.no_grad():
        distance = float(metric(
            candidate_tensor.unsqueeze(0) * 2 - 1,
            target_tensor.unsqueeze(0) * 2 - 1,
        ).item())
    if abs(ssim - float(result["ssim"])) > 1e-6 or abs(distance - float(result["lpips"])) > 1e-5:
        fail("vision metrics differ from independent fixed-corpus recomputation")
    response = requests.post(
        f"{research.VISION_URL}/v1/models/orion-vision-prototype:predict",
        headers={
            "Authorization": "Bearer KeplerV2-Orion-Vision-Evaluation-Reader",
            "X-Kepler-Identity": "svc-orion-evaluation-reader",
            "X-Request-ID": "m08-native-validator",
        },
        json={"instances": [{
            "image_b64": __import__("base64").b64encode(candidate_bytes).decode()
        }]}, timeout=60,
    )
    response.raise_for_status()
    prediction = response.json()["predictions"][0]
    if prediction.get("label") != result.get("target_class"):
        fail("live vision model no longer reproduces the accepted target class")


def validate_review(result: dict[str, Any]) -> None:
    headers = {"Authorization": f"Token {research.LABEL_TOKEN}"}
    task = requests.get(
        f"{research.LABEL_URL}/api/tasks/{int(result['task_id'])}", headers=headers, timeout=30
    )
    task.raise_for_status()
    predictions = task.json().get("predictions") or []
    match = [
        item for item in predictions
        if ((item.get("result") or [{}])[0].get("meta") or {}).get("ledger_key")
        == result.get("ledger_key")
    ]
    if len(match) != 1:
        fail("fixed Label Studio task lacks the accepted native prediction")
    meta = (match[0].get("result") or [{}])[0].get("meta") or {}
    if meta.get("ledger_key") != result.get("ledger_key") or meta.get("ledger_sha256") != result.get("ledger_sha256"):
        fail("Label Studio prediction is not bound to its server query ledger")
    if meta.get("engagement_reference") != research.FLAGS["review-prediction"]:
        fail("Label Studio native prediction lacks the accepted carrier")
    if (
        result.get("schema") != "keplerops.label-studio-ml-prediction/v1"
        or result.get("backend_identity") != "svc-orion-label-studio-ml"
        or meta.get("backend_identity") != result.get("backend_identity")
    ):
        fail("Label Studio prediction did not originate from the native ML backend")
    body = exact_object(
        research.minio(), "operations", result["ledger_key"], result["ledger_sha256"]
    )
    ledger = json.loads(body)
    signature = str(ledger.pop("service_signature", ""))
    if not hmac.compare_digest(signature, research.signed(ledger, research.QUERY_LEDGER_KEY)):
        fail("Label Studio teacher-query ledger signature is invalid")


def validate_hardware() -> None:
    marker = Path(os.getenv(
        "CAMPAIGN_HARDWARE_READINESS_MARKER", "/run/shifter/keplerops-v2-hardware.ready"
    ))
    report = research.STATE / "hardware" / "accepted-calibration.json"
    if not marker.is_file() or not report.is_file():
        fail("real hardware readiness and accepted calibration evidence are absent")
    value = json.loads(report.read_text())
    if (
        value.get("schema") != "keplerops.physical-calibration/v1"
        or value.get("media_source") != "uvc"
        or len(value.get("capture_hashes", [])) < 2
        or len(value.get("actuator_telemetry", [])) < 2
        or len(value.get("liveness_responses", [])) < 2
    ):
        fail("physical calibration report lacks real-bench liveness evidence")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: validator.py <kep-m08-operation>")
    operation = sys.argv[1]
    if operation == "kep-m08-i":
        validate_hardware()
        print(f"{operation}: real-bench native evidence passed")
        return
    result = accepted(operation)
    flag = next(
        item["flag"] for item in json.loads(
            (Path(__file__).parents[1] / "operations.json").read_text()
        ) if item["id"] == operation
    )
    if operation != "kep-m08-k" and flag not in json.dumps(result, sort_keys=True):
        fail("accepted owning-system record does not contain the operation carrier")
    dispatch = {
        "kep-m08-a": validate_corpus,
        "kep-m08-b": validate_version,
        "kep-m08-c": validate_registered,
        "kep-m08-d": validate_registered,
        "kep-m08-e": validate_hidden,
        "kep-m08-f": lambda value: validate_offline(value, "student"),
        "kep-m08-g": validate_registered,
        "kep-m08-h": validate_vision,
        "kep-m08-j": lambda value: validate_offline(value, "protected-package"),
        "kep-m08-k": validate_review,
    }
    if operation not in dispatch:
        fail("unknown operation")
    dispatch[operation](result)
    print(f"{operation}: fixed owning-system state, signatures, and server negatives passed")


if __name__ == "__main__":
    main()
