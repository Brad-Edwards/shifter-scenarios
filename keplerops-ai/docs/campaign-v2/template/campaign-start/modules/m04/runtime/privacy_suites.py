from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any


DATASET = Path(os.getenv("ORION_RELEASE_RISK_TRAINING_DATA", "/campaign-data/release-risk-training.json"))


def _paraphrase(text: str, index: int) -> str:
    prefixes = (
        "For the next review, ",
        "An external team asks us to ",
        "During a later cycle, ",
        "A partner recommends that we ",
    )
    transformed = text[0].lower() + text[1:]
    transformed = transformed.replace("Orion", "the assistant")
    return prefixes[index % len(prefixes)] + transformed


def load_records() -> list[dict[str, str]]:
    records = json.loads(DATASET.read_text())
    if len(records) != 48 or any(not {"record_id", "text", "label"} <= item.keys() for item in records):
        raise RuntimeError("release-risk training corpus is incomplete")
    return records


def build_suites() -> dict[str, list[dict[str, Any]]]:
    records = load_records()
    calibration: list[dict[str, Any]] = []
    for index, record in enumerate(records[:40]):
        calibration.append({
            "case_id": f"cal-member-{index + 1:02d}",
            "text": record["text"],
            "member": 1,
            "source_record": record["record_id"],
            "stratum": record["label"],
            "partition": "fit" if index < 20 else "validation",
        })
        calibration.append({
            "case_id": f"cal-control-{index + 1:02d}",
            "text": _paraphrase(record["text"], index),
            "member": 0,
            "source_record": None,
            "stratum": record["label"],
            "partition": "fit" if index < 20 else "validation",
        })

    individual: list[dict[str, Any]] = []
    for index in range(16):
        record = records[(index * 3 + 5) % len(records)]
        is_member = index == 9
        individual.append({
            "case_id": f"candidate-{index + 1:02d}",
            "text": records[3]["text"] if is_member else _paraphrase(record["text"], index + 11),
            "member": int(is_member),
            "source_record": records[3]["record_id"] if is_member else None,
            "stratum": records[3]["label"] if is_member else record["label"],
        })

    cohort_names = ("partner-support", "release-engineering", "research-operations", "customer-success")
    cohorts: list[dict[str, Any]] = []
    for cohort_index, cohort in enumerate(cohort_names):
        for sample_index in range(12):
            record = records[(sample_index * 4 + cohort_index) % len(records)]
            is_member = cohort == "release-engineering"
            cohorts.append({
                "case_id": f"{cohort}-{sample_index + 1:02d}",
                "text": record["text"] if is_member else _paraphrase(record["text"], cohort_index * 13 + sample_index),
                "member": int(is_member),
                "source_record": record["record_id"] if is_member else None,
                "cohort": cohort,
                "stratum": record["label"],
                "event_week": f"2026-W{27 + sample_index % 3}",
            })
    return {"calibration": calibration, "individual": individual, "cohort": cohorts}


def public_suite(name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    public = []
    for case in cases:
        item = {key: case[key] for key in ("case_id", "text", "stratum")}
        if "cohort" in case:
            item.update(cohort=case["cohort"], event_week=case["event_week"])
        if name == "calibration":
            item["known_membership"] = case["member"]
            item["partition"] = case["partition"]
        public.append(item)
    return {"suite": name, "cases": public}


def membership_signal(prediction: dict[str, Any]) -> float:
    probabilities = [float(value) for value in prediction.get("probabilities", [])]
    if not probabilities or any(value < 0 or value > 1 for value in probabilities):
        raise ValueError("model prediction lacks probabilities")
    entropy = -sum(value * math.log(max(value, 1e-12)) for value in probabilities)
    normalized_entropy = entropy / math.log(len(probabilities))
    return max(probabilities) - 0.2 * normalized_entropy
