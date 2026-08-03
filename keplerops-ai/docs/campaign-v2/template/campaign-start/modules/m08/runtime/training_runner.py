from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(os.getenv("TRAINING_QUEUE_ROOT", "/var/lib/cinder-training"))
INBOX = ROOT / "inbox"
INPUTS = ROOT / "inputs"
OUTPUTS = ROOT / "outputs"
ACCEPTED = ROOT / "accepted"
REJECTED = ROOT / "rejected"
FIXED_TIMEOUT = 3600
MINIMUM_PARAMETERS = 50_000
MINIMUM_PACKAGE_BYTES = 100_000
FORBIDDEN_PLATFORM_MATERIAL = (
    b"FLAG{",
    b"KeplerV2-Training-",
    b"BEGIN PRIVATE KEY",
    b"server-evaluation",
    b"hidden_case_digest",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_job_id(value: Any) -> str:
    rendered = str(value)
    if not re.fullmatch(r"train-[0-9a-f]{32}", rendered):
        raise ValueError("invalid isolated training job ID")
    return rendered


def reject_platform_material(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
            continue
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                if any(marker in block for marker in FORBIDDEN_PLATFORM_MATERIAL):
                    raise ValueError("isolated training input contains platform-only material")


def sandbox_command(source: Path, dataset: Path, base_model: Path, output: Path, mode: str) -> list[str]:
    command = [
        "bwrap", "--die-with-parent", "--new-session", "--unshare-all",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--dir", "/home", "--dir", "/home/participant",
        "--dir", "/input", "--dir", "/work", "--chdir", "/work",
        "--ro-bind", str(source), "/input/train.py",
        "--ro-bind", str(dataset), "/input/dataset.json",
        "--ro-bind", str(base_model), "/input/base-model",
        "--bind", str(output), "/output",
        "--clearenv",
        "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "HOME", "/home/participant",
        "--setenv", "PYTHONNOUSERSITE", "1",
        "--setenv", "TOKENIZERS_PARALLELISM", "false",
        "/usr/local/bin/python", "/input/train.py",
        "--dataset", "/input/dataset.json",
        "--base-model", "/input/base-model",
        "--output", "/output/model",
        "--seed", "2026",
        "--max-length", "64",
    ]
    if mode == "artifact-proxy":
        command.extend([
            "--architecture", "/input/architecture.json",
            "--preprocessing", "/input/preprocessing.json",
        ])
    return command


def add_runtime_binds(command: list[str], root: Path) -> None:
    insertion = command.index("--proc")
    for path in (Path("/lib"), Path("/lib64"), Path("/usr/local")):
        if path.exists():
            command[insertion:insertion] = ["--ro-bind", str(path), str(path)]
            insertion += 3
    for name in ("architecture.json", "preprocessing.json"):
        candidate = root / name
        if candidate.is_file():
            command[insertion:insertion] = ["--ro-bind", str(candidate), f"/input/{name}"]
            insertion += 3


def validate_model(model_root: Path) -> tuple[int, str]:
    required = ("config.json", "model.safetensors", "tokenizer.json")
    if any(not (model_root / name).is_file() for name in required):
        raise ValueError("participant training did not produce the required safe model members")
    if any(path.is_symlink() for path in model_root.rglob("*")):
        raise ValueError("participant model package contains symbolic links")
    forbidden = [path for path in model_root.rglob("*") if path.suffix in {".py", ".pyc", ".so", ".pkl", ".pickle"}]
    if forbidden:
        raise ValueError("participant model package contains executable or pickle content")
    AutoTokenizer.from_pretrained(model_root, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_root, local_files_only=True, trust_remote_code=False, use_safetensors=True
    )
    if int(model.config.num_labels) != 8:
        raise ValueError("participant model does not implement the eight-class interface")
    parameters = sum(item.numel() for item in model.parameters())
    if parameters < MINIMUM_PARAMETERS:
        raise ValueError("participant model is below the minimum real-model size")
    return parameters, digest(model_root / "model.safetensors")


def run(job_path: Path) -> None:
    job = json.loads(job_path.read_text())
    if job.get("schema") != "cinder.isolated-training-job/v1":
        raise ValueError("unsupported isolated training job")
    job_id = safe_job_id(job.get("job_id"))
    mode = str(job.get("mode"))
    if mode not in {"first-student", "second-student", "artifact-proxy"}:
        raise ValueError("unsupported isolated training mode")
    root = INPUTS / job_id
    source = root / "train.py"
    dataset = root / "dataset.json"
    base_model = root / "base-model"
    if not source.is_file() or not dataset.is_file() or not base_model.is_dir():
        raise ValueError("isolated training input is incomplete")
    reject_platform_material(root)
    if digest(source) != job.get("source_sha256") or digest(dataset) != job.get("dataset_sha256"):
        raise ValueError("isolated training input digest mismatch")
    target = OUTPUTS / job_id
    temporary = Path(tempfile.mkdtemp(prefix=f"{job_id}-", dir=OUTPUTS))
    started = time.time_ns()
    try:
        command = sandbox_command(source, dataset, base_model, temporary, mode)
        add_runtime_binds(command, root)
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=FIXED_TIMEOUT,
            check=False,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
        )
        if completed.returncode != 0:
            diagnostic = completed.stderr.decode(errors="replace")[-4000:]
            raise ValueError(f"isolated participant training failed: {diagnostic}")
        model_root = temporary / "model"
        parameters, weights_sha = validate_model(model_root)
        package = temporary / "model.tar.gz"
        with tarfile.open(package, "w:gz") as archive:
            for path in sorted(item for item in model_root.rglob("*") if item.is_file()):
                archive.add(path, arcname=str(Path("model") / path.relative_to(model_root)))
        if package.stat().st_size < MINIMUM_PACKAGE_BYTES:
            raise ValueError("participant model package is a toy or incomplete artifact")
        result = {
            "schema": "cinder.isolated-training-result/v1",
            "job_id": job_id,
            "mode": mode,
            "source_sha256": job["source_sha256"],
            "dataset_sha256": job["dataset_sha256"],
            "package_sha256": digest(package),
            "weights_sha256": weights_sha,
            "parameter_count": parameters,
            "package_inventory": {
                str(path.relative_to(model_root)): digest(path)
                for path in sorted(item for item in model_root.rglob("*") if item.is_file())
            },
            "started_ns": started,
            "finished_ns": time.time_ns(),
            "network_namespace": "isolated",
            "credential_environment": [],
            "sandbox": "bubblewrap-unshare-all",
        }
        (temporary / "result.json").write_bytes(canonical(result))
        temporary.replace(target)
        job_path.replace(ACCEPTED / job_path.name)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    for path in (INBOX, INPUTS, OUTPUTS, ACCEPTED, REJECTED):
        path.mkdir(parents=True, exist_ok=True)
    while True:
        for job_path in sorted(INBOX.glob("*.json")):
            try:
                run(job_path)
            except Exception as error:
                rejected = {
                    "schema": "cinder.isolated-training-rejection/v1",
                    "job_id": job_path.stem,
                    "reason": str(error),
                }
                (REJECTED / job_path.name).write_bytes(canonical(rejected))
                job_path.unlink(missing_ok=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
