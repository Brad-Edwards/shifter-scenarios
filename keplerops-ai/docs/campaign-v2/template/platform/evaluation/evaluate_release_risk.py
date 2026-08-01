#!/usr/bin/env python3

import argparse
import hashlib
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def request_json(url: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-accuracy", type=float, default=0.75)
    args = parser.parse_args()

    cases_bytes = args.cases.read_bytes()
    cases = json.loads(cases_bytes)
    endpoint = args.endpoint.rstrip("/")
    metadata = request_json(f"{endpoint}/v1/models/orion-release-risk")
    prediction = request_json(
        f"{endpoint}/v1/models/orion-release-risk:predict",
        {"instances": [{"text": item["text"]} for item in cases]},
    )
    predicted = [item["label"] for item in prediction["predictions"]]
    expected = [item["label"] for item in cases]
    correct = [left == right for left, right in zip(predicted, expected, strict=True)]
    total = len(cases)
    accuracy = sum(correct) / total
    per_class_total = Counter(expected)
    per_class_correct = Counter(
        expected[index] for index, value in enumerate(correct) if value
    )
    report = {
        "schema": "keplerops.release-risk.evaluation/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite_sha256": hashlib.sha256(cases_bytes).hexdigest(),
        "model_sha256": metadata["model_sha256"],
        "tokenizer_sha256": metadata["tokenizer_sha256"],
        "mlflow_run_id": metadata["mlflow_run_id"],
        "mlflow_model_version": metadata["mlflow_model_version"],
        "records": total,
        "correct": sum(correct),
        "accuracy": accuracy,
        "minimum_accuracy": args.minimum_accuracy,
        "decision": "accepted" if accuracy >= args.minimum_accuracy else "rejected",
        "per_class_accuracy": {
            label: per_class_correct[label] / count
            for label, count in sorted(per_class_total.items())
        },
        "cases": [
            {
                "case_id": item["case_id"],
                "expected": item["label"],
                "predicted": predicted[index],
                "correct": correct[index],
            }
            for index, item in enumerate(cases)
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True))
    if report["decision"] != "accepted":
        raise SystemExit(
            f"release-risk evaluation failed: accuracy={accuracy:.3f} "
            f"required={args.minimum_accuracy:.3f}"
        )
    print(f"release-risk evaluation passed: accuracy={accuracy:.3f} cases={total}")


if __name__ == "__main__":
    main()
