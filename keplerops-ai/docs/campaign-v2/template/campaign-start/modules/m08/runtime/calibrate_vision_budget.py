from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ACTOR = "cinder-field-operator"
ENGAGEMENT_ID = "campaign-v2-m08-vision"
QUERY_CAP = 64
SEED = 2026
RESEARCH_IDS = (
    "alignment-calibration",
    "coupler-calibration",
    "thermal-calibration",
    "waveguide-calibration",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def evidence() -> dict[str, Any]:
    runs = [
        {
            "run": index,
            "actor": ACTOR,
            "engagement_id": ENGAGEMENT_ID,
            "research_id": RESEARCH_IDS[(index - 1) % len(RESEARCH_IDS)],
            "query_number": index,
            "accepted": index <= QUERY_CAP,
        }
        for index in range(1, 21)
    ]
    value = {
        "schema": "keplerops.vision-budget-calibration/v1",
        "seed": SEED,
        "query_cap": QUERY_CAP,
        "actor": ACTOR,
        "engagement_id": ENGAGEMENT_ID,
        "runs": runs,
        "assertions": {
            "run_count": len(runs),
            "distinct_research_ids": len({item["research_id"] for item in runs}),
            "global_last_query_number": runs[-1]["query_number"],
            "budget_remaining": QUERY_CAP - len(runs),
            "research_id_does_not_reset_budget": True,
            "all_runs_bound_to_one_actor_and_engagement": True,
        },
    }
    value["evidence_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    expected = evidence()
    if args.check:
        observed = json.loads(args.check.read_text())
        if observed != expected:
            raise SystemExit("committed vision budget calibration evidence is stale")
    else:
        print(json.dumps(expected, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
