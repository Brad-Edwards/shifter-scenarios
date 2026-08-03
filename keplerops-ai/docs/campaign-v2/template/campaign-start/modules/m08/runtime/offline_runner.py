from __future__ import annotations

import hashlib
import hmac
import json
import os
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(os.getenv("OFFLINE_STATE_ROOT", "/var/lib/cinder-offline"))
INBOX = ROOT / "inbox"
PACKAGES = ROOT / "packages"
REPORTS = ROOT / "reports"
FLAGS = {
    "student": "FLAG{95c8cb516f716efd}",
    "protected-package": "FLAG{9698521c92e2332d}",
}
FIXED_MINIMUM_FIDELITY = 0.50
FIXED_MAX_LENGTH = 64
ATTESTATION_SIGNING_KEY = os.getenv(
    "CINDER_OFFLINE_ATTESTATION_KEY", "Cinder-Offline-Execution-Attestation-2026"
).encode()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def extract(package: Path, destination: Path) -> Path:
    with tarfile.open(package, "r:*") as archive:
        members = archive.getmembers()
        if any(member.name.startswith("/") or ".." in Path(member.name).parts for member in members):
            raise ValueError("model package contains an unsafe path")
        archive.extractall(destination, members=members, filter="data")
    children = list(destination.iterdir())
    return children[0] if len(children) == 1 and children[0].is_dir() else destination


def predict(model_root: Path, texts: list[str]) -> list[int]:
    forbidden = [
        path for path in model_root.rglob("*")
        if path.suffix in {".py", ".pyc", ".so", ".pkl", ".pickle"}
    ]
    if forbidden:
        raise ValueError("offline package contains executable or pickle content")
    tokenizer = AutoTokenizer.from_pretrained(
        model_root, local_files_only=True, trust_remote_code=False
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        model_root, local_files_only=True, trust_remote_code=False, use_safetensors=True
    )
    model.eval()
    with torch.no_grad():
        encoded = tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=FIXED_MAX_LENGTH,
            return_tensors="pt",
        )
        return model(**encoded).logits.argmax(dim=-1).tolist()


def run(job_path: Path) -> None:
    job = json.loads(job_path.read_text())
    if job.get("schema") != "cinder.offline-model-job/v1":
        raise ValueError("unsupported offline model job")
    mode = str(job.get("mode", ""))
    if mode not in FLAGS:
        raise ValueError("unsupported offline execution mode")
    package = PACKAGES / Path(str(job["package"])).name
    if not package.is_file() or digest(package) != str(job["package_sha256"]):
        raise ValueError("offline package digest mismatch")
    cases = job.get("cases")
    if not isinstance(cases, list) or len(cases) < 8:
        raise ValueError("the fixed server-held offline case set is required")
    participant_cases = [item for item in cases if item.get("case_owner") == "cinder-field-operator"]
    server_cases = [
        item for item in cases
        if item.get("case_owner") == "svc-cinder-offline-dispatcher"
    ]
    if mode == "student":
        if (
            job.get("case_set_owner") != "svc-cinder-offline-dispatcher+cinder-field-operator"
            or len(participant_cases) != 1
            or len(server_cases) != 8
            or job.get("participant_fresh_case") != participant_cases[0]
            or hashlib.sha256(canonical(server_cases)).hexdigest()
            != job.get("server_negative_digest")
        ):
            raise ValueError("student job lacks one participant case and the exact server negatives")
    elif (
        job.get("case_set_owner") != "svc-cinder-offline-dispatcher"
        or participant_cases
        or len(server_cases) != 8
    ):
        raise ValueError("protected-package job lacks the exact server-owned cases")
    if not job.get("overlap_checked"):
        raise ValueError("offline cases lack disjointness evidence")
    continuity = job.get("continuity")
    required_continuity = {
        "model_family", "input_schema", "model_digest", "runtime_profile",
        "runtime_profile_sha256", "preprocessing_sha256", "compute_profile",
    }
    if not isinstance(continuity, dict) or not required_continuity.issubset(continuity):
        raise ValueError("offline job lacks immutable model/runtime continuity")
    texts = [str(item["text"]) for item in cases]
    expected = [int(item["teacher_class_index"]) for item in cases]
    with tempfile.TemporaryDirectory(prefix="cinder-offline-") as temp:
        model_root = extract(package, Path(temp))
        observed = predict(model_root, texts)
    fidelity = sum(left == right for left, right in zip(observed, expected, strict=True)) / len(expected)
    server_indexes = [index for index, item in enumerate(cases) if item in server_cases]
    server_fidelity = sum(observed[index] == expected[index] for index in server_indexes) / len(server_indexes)
    fresh_case_match = (
        True if mode == "protected-package"
        else observed[cases.index(participant_cases[0])] == expected[cases.index(participant_cases[0])]
    )
    if server_fidelity < FIXED_MINIMUM_FIDELITY or not fresh_case_match:
        raise ValueError(
            f"offline fidelity failed: server={server_fidelity:.3f} fresh={fresh_case_match}"
        )
    report = {
        "schema": "cinder.offline-model-attestation/v1",
        "job_id": job_path.stem,
        "mode": mode,
        "package_sha256": str(job["package_sha256"]),
        "network_mode": "none",
        "execution_case_digest": hashlib.sha256(canonical(cases)).hexdigest(),
        "fresh_case_sha256": (
            hashlib.sha256(participant_cases[0]["text"].encode()).hexdigest()
            if participant_cases else ""
        ),
        "server_negative_digest": hashlib.sha256(canonical(server_cases)).hexdigest(),
        "observed_classes": observed,
        "fidelity": fidelity,
        "server_negative_fidelity": server_fidelity,
        "fresh_case_match": fresh_case_match,
        "acceptance_threshold": FIXED_MINIMUM_FIDELITY,
        "max_length": FIXED_MAX_LENGTH,
        "case_set_owner": job["case_set_owner"],
        "overlap_checked": True,
        **continuity,
        "engagement_reference": FLAGS[mode],
    }
    report["signer_identity"] = "svc-cinder-offline-executor"
    report["signature_algorithm"] = "hmac-sha256"
    report["attestation_signature"] = hmac.new(
        ATTESTATION_SIGNING_KEY, canonical(report), hashlib.sha256
    ).hexdigest()
    target = REPORTS / f"{job_path.stem}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(canonical(report))
    temporary.replace(target)
    job_path.rename(ROOT / "accepted" / job_path.name)


def main() -> None:
    for path in (INBOX, PACKAGES, REPORTS, ROOT / "accepted", ROOT / "rejected"):
        path.mkdir(parents=True, exist_ok=True)
    while True:
        for job_path in sorted(INBOX.glob("*.json")):
            try:
                run(job_path)
            except Exception as error:  # the rejected record is the normal operator diagnostic
                rejected = {
                    "schema": "cinder.offline-model-rejection/v1",
                    "job_id": job_path.stem,
                    "reason": str(error),
                }
                (ROOT / "rejected" / job_path.name).write_bytes(canonical(rejected))
                job_path.unlink(missing_ok=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
