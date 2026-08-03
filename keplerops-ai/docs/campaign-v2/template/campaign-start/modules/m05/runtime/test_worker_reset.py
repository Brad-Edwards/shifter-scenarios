#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path


mlflow = types.ModuleType("mlflow")
mlflow.__version__ = "2.8.1"
mlflow_data = types.ModuleType("mlflow.data")
mlflow_http = types.ModuleType("mlflow.data.http_dataset_source")
mlflow_http.HTTPDatasetSource = object
sys.modules.update(
    {
        "mlflow": mlflow,
        "mlflow.data": mlflow_data,
        "mlflow.data.http_dataset_source": mlflow_http,
    }
)

path = Path(__file__).with_name("orion_dataset_worker.py")
spec = importlib.util.spec_from_file_location("orion_dataset_worker_test", path)
assert spec and spec.loader
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        worker.WORKSPACE = root
        worker.IMPORT_DIR = root / "python"
        worker.JOBS_DIR = root / "jobs"
        worker.SHELL_DIR = root / "shell-jobs"
        worker.IMPORT_DIR.mkdir()
        worker.JOBS_DIR.mkdir()
        worker.SHELL_DIR.mkdir()

        attempt = "dataset-server-issued"
        target = worker.IMPORT_DIR / "sitecustomize.py"
        target.write_bytes(b"attempt bytes")
        write(
            worker.JOBS_DIR / f"{attempt}.json",
            {
                "schema": "keplerops.orion.dataset-load/v1",
                "request_id": attempt,
                "attempt_id": attempt,
                "path": str(target),
                "loaded_sha256": hashlib.sha256(b"attempt bytes").hexdigest(),
                "prior_content_b64": base64.b64encode(b"prior bytes").decode(),
            },
        )
        write(
            worker.JOBS_DIR / "child-owned.json",
            {
                "schema": "keplerops.orion.worker-job/v1",
                "job_id": "child-owned",
                "attempt_id": attempt,
            },
        )
        unrelated = worker.JOBS_DIR / "child-unrelated.json"
        write(
            unrelated,
            {
                "schema": "keplerops.orion.worker-job/v1",
                "job_id": "child-unrelated",
                "attempt_id": "dataset-other",
            },
        )
        result = worker.reset_attempt(attempt)
        assert set(result["removed"]) == {attempt, "child-owned"}
        assert target.read_bytes() == b"prior bytes"
        assert unrelated.is_file()

        changed_attempt = "dataset-changed"
        target.write_bytes(b"later participant bytes")
        write(
            worker.JOBS_DIR / f"{changed_attempt}.json",
            {
                "schema": "keplerops.orion.dataset-load/v1",
                "request_id": changed_attempt,
                "attempt_id": changed_attempt,
                "path": str(target),
                "loaded_sha256": hashlib.sha256(b"old attempt bytes").hexdigest(),
                "prior_content_b64": None,
            },
        )
        try:
            worker.reset_attempt(changed_attempt)
        except ValueError as exc:
            assert "bytes changed after this attempt" in str(exc)
        else:
            raise AssertionError("reset removed bytes changed by a later participant")
        assert target.read_bytes() == b"later participant bytes"
    print("m05 worker reset regressions passed: exact ownership and changed-state refusal")


if __name__ == "__main__":
    main()
