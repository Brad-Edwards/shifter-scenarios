from __future__ import annotations

import hashlib
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
    tokenizer = AutoTokenizer.from_pretrained(model_root, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_root, local_files_only=True)
    model.eval()
    with torch.no_grad():
        encoded = tokenizer(texts, padding=True, truncation=True, max_length=96, return_tensors="pt")
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
    if not isinstance(cases, list) or len(cases) < 4:
        raise ValueError("fresh offline cases are required")
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
    threshold = float(job.get("minimum_fidelity", 0.5))
    if fidelity < threshold:
        raise ValueError(f"offline fidelity {fidelity:.3f} is below {threshold:.3f}")
    report = {
        "schema": "cinder.offline-model-attestation/v1",
        "job_id": job_path.stem,
        "mode": mode,
        "package_sha256": str(job["package_sha256"]),
        "network_mode": "none",
        "fresh_case_digest": hashlib.sha256(canonical(cases)).hexdigest(),
        "observed_classes": observed,
        "fidelity": fidelity,
        **continuity,
        "engagement_reference": FLAGS[mode],
    }
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
