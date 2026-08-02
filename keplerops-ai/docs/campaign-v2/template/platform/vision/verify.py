#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient


def load_application(app_path: Path, model_dir: Path):
    os.environ["MODEL_DIR"] = str(model_dir)
    os.environ["ORION_VISION_EVALUATION_ACTOR"] = "svc-orion-evaluation-reader"
    os.environ["ORION_VISION_EVALUATION_TOKEN"] = "test-evaluation-token"
    os.environ["ORION_VISION_QUERY_BUDGET"] = "8"
    spec = importlib.util.spec_from_file_location("orion_vision_app", app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load application from {app_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()

    reference = json.loads((args.artifacts / "reference-inference.json").read_text())
    image = (args.data / reference["image"]).read_bytes()
    payload = {
        "instances": [{"image_b64": base64.b64encode(image).decode("ascii")}]
    }
    headers = {
        "Authorization": "Bearer test-evaluation-token",
        "X-Kepler-Identity": "svc-orion-evaluation-reader",
    }
    with TestClient(load_application(args.app, args.artifacts)) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["model_sha256"] == reference["model_sha256"]

        metadata = client.get("/v1/models/orion-vision-prototype")
        assert metadata.status_code == 200, metadata.text
        metadata_body = metadata.json()
        assert metadata_body["model_family"] == "vision-prototype"
        assert metadata_body["benchmark_scope"] == (
            "internal-synthetic-photonics-pattern-privacy"
        )
        assert metadata_body["scores_are_calibrated"] is False
        assert metadata_body["input_shape"] == [None, 3, 64, 64]
        assert metadata_body["output_shape"] == [None, 4]

        unauthenticated = client.post(
            "/v1/models/orion-vision-prototype:predict", json=payload
        )
        assert unauthenticated.status_code == 401
        wrong_actor = client.post(
            "/v1/models/orion-vision-prototype:predict",
            json=payload,
            headers={
                **headers,
                "X-Kepler-Identity": "ml.engineer",
                "X-Request-ID": "verify-wrong-actor",
            },
        )
        assert wrong_actor.status_code == 403

        first = client.post(
            "/v1/models/orion-vision-prototype:predict",
            json=payload,
            headers={**headers, "X-Request-ID": "verify-request-0001"},
        )
        second = client.post(
            "/v1/models/orion-vision-prototype:predict",
            json=payload,
            headers={**headers, "X-Request-ID": "verify-request-0002"},
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["predictions"] == second.json()["predictions"]
        assert first.json()["evidence"]["query_number"] == 1
        assert second.json()["evidence"]["query_number"] == 2
        assert first.json()["evidence"]["model_sha256"] == reference["model_sha256"]
        prediction = first.json()["predictions"][0]
        vector = np.asarray(prediction["probabilities"], dtype=np.float64)
        assert vector.shape == (4,)
        assert np.isclose(np.sum(vector), 1.0, atol=1e-6)
        assert np.allclose(vector, reference["probabilities"], rtol=0.0, atol=1e-7)
        assert prediction["class_index"] == reference["class_index"]
        assert prediction["label"] == reference["label"]

        malformed = client.post(
            "/v1/models/orion-vision-prototype:predict",
            json={"instances": [{"image_b64": "not-an-image"}]},
            headers={**headers, "X-Request-ID": "verify-request-bad-image"},
        )
        assert malformed.status_code == 422

    print(
        "Orion synthetic photonics benchmark requires evaluation-reader access "
        "and returns reproducible four-class scores with request evidence"
    )


if __name__ == "__main__":
    main()
