#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"

die() { printf '[campaign-m10 validate] ERROR: %s\n' "$*" >&2; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

[[ -n ${OPERATION} ]] || die 'usage: validate.sh <operation>'
jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"

# M08 f/j share one signed package contract.  This source check is deliberately
# cross-module and read-only: M10 must fail closed if upstream membership or
# tokenizer padding drifts before either package is accepted downstream.
python3 - "${TEMPLATE_ROOT}" "${MODULE_ROOT}" <<'PY'
import ast
from pathlib import Path
import sys

template, module = map(Path, sys.argv[1:])
m08 = template / "campaign-start/modules/m08/runtime"
expected = ("config.json", "model.safetensors", "tokenizer.json", "model-card.md", "provenance.json")

def assignments(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    values = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except (TypeError, ValueError):
                        pass
    return tree, values

contracts_tree, contracts = assignments(m08 / "contracts.py")
research_tree, research = assignments(m08 / "research.py")
offline_tree, offline = assignments(m08 / "offline_runner.py")
m10_tree, m10 = assignments(module / "runtime/production_jobs.py")
assert tuple(contracts["PACKAGE_MEMBERS"]) == expected
for values in (contracts, research):
    preprocessing = values["RELEASE_RISK_PREPROCESSING"]
    assert preprocessing["padding"] == "max_length" and preprocessing["max_length"] == 64
assert offline["FIXED_MAX_LENGTH"] == 64
assert set(m10["M08_PACKAGE_MEMBERS"]) == set(expected)

def tokenizer_calls(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and {kw.arg for kw in node.keywords} >= {"padding", "max_length", "truncation"}]

calls = tokenizer_calls(offline_tree)
assert calls
for call in calls:
    keywords = {kw.arg: kw.value for kw in call.keywords}
    assert isinstance(keywords["padding"], ast.Constant) and keywords["padding"].value == "max_length"
    assert isinstance(keywords["max_length"], ast.Name) and keywords["max_length"].id == "FIXED_MAX_LENGTH"
m10_source = (module / "runtime/production_jobs.py").read_text()
assert "padding='max_length'" in m10_source and "max_length=64" in m10_source
assert "max_length=96" not in m10_source and "padding=True" not in m10_source
print("m08/m10 signed five-member preprocessing contract: ok")
PY

# The validator resolves the immutable checkpoint to its fixed owning-system
# coordinates, fetches that record again with service credentials, verifies
# signatures/digests, and rechecks the operation's clean or before-state
# negative.  No caller-selected URL or uploaded carrier is accepted.
compose exec -T -e OPERATION="${OPERATION}" airflow-api python - <<'PY'
import json
import os
from production_jobs import validate_accepted

record = validate_accepted(os.environ["OPERATION"])
print(json.dumps({
    "operation": os.environ["OPERATION"],
    "status": "accepted",
    "native_carrier": record["carrier"],
    "checkpoint_signature": record["checkpoint_signature"],
}, sort_keys=True))
PY
