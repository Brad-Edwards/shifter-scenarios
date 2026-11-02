#!/usr/bin/env python3
"""Validate evidence-bound Cinder Typhoon QA and release-readiness claims."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import Any, Callable
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "tests" / "qa-status.json"
LAYER_IDS = (
    "service_contract",
    "known_solution_acceptance",
    "provenance_and_surface",
    "blind_human_agent_playtest",
)
IMPLEMENTATION_STATES = {"complete", "partial", "not_started"}
CANDIDATE_STATES = {"passed", "failed", "not_run"}
AUTOMATED_NON_CLAIMS = {
    "human discovery",
    "fairness",
    "participant understanding",
    "difficulty",
    "duration",
}
LAYER_KEYS = {
    "title",
    "purpose",
    "method",
    "implementation_status",
    "implementation_gate_ids",
    "candidate_status",
    "candidate_reports",
    "evidence_visibility",
    "evidence",
    "supports",
    "does_not_support",
}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
ZERO_DIGEST = "0" * 64
CommandRunner = Callable[[list[str]], dict[str, Any]]


class QAStatusError(ValueError):
    """The status or evidence does not support its readiness claim."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QAStatusError(message)


def string_list(value: Any, context: str, *, allow_empty: bool = False) -> None:
    require(isinstance(value, list), f"{context}: array required")
    require(allow_empty or bool(value), f"{context}: at least one value required")
    require(
        all(isinstance(item, str) and item for item in value),
        f"{context}: non-empty strings required",
    )
    require(len(value) == len(set(value)), f"{context}: duplicate values")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _root_path(relative: str, context: str) -> Path:
    require(isinstance(relative, str) and relative, f"{context}: path required")
    candidate = Path(relative)
    require(not candidate.is_absolute(), f"{context}: path must be relative")
    resolved = (ROOT / candidate).resolve()
    require(resolved == ROOT or ROOT in resolved.parents, f"{context}: path escapes pack root")
    return resolved


def _load_json(path: Path, context: str) -> Any:
    require(path.is_file(), f"{context}: missing file {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QAStatusError(f"{context}: invalid JSON: {error}") from error


def _validate_file_binding(binding: Any, context: str) -> Path:
    require(
        isinstance(binding, dict) and set(binding) == {"path", "sha256"},
        f"{context}: path and sha256 required",
    )
    require(
        isinstance(binding["sha256"], str) and HEX_64.fullmatch(binding["sha256"]),
        f"{context}: sha256 must be 64 lowercase hexadecimal characters",
    )
    path = _root_path(binding["path"], context)
    require(path.is_file(), f"{context}: bound file is missing")
    require(_sha256(path) == binding["sha256"], f"{context}: bound file digest changed")
    return path


def _validate_gate_catalog(value: Any) -> dict[str, dict[str, Any]]:
    require(
        isinstance(value, dict) and set(value) == {"schema_version", "gates"},
        "gate catalog: unexpected or missing keys",
    )
    require(value["schema_version"] == 1, "gate catalog: schema_version must be 1")
    gates = value["gates"]
    require(isinstance(gates, dict) and gates, "gate catalog: non-empty gates object required")
    for gate_id, gate in gates.items():
        context = f"gate catalog.{gate_id}"
        require(isinstance(gate_id, str) and gate_id, f"{context}: invalid gate id")
        require(isinstance(gate, dict), f"{context}: object required")
        require(gate.get("layer") in LAYER_IDS, f"{context}: invalid layer")
        kind = gate.get("kind")
        if kind == "command":
            require(set(gate) == {"layer", "kind", "argv", "expect"}, f"{context}: unexpected or missing keys")
            string_list(gate["argv"], f"{context}.argv")
            expect = gate["expect"]
            require(isinstance(expect, dict), f"{context}.expect: object required")
            require(set(expect) <= {"exit_code", "json"} and "exit_code" in expect, f"{context}.expect: invalid keys")
            require(isinstance(expect["exit_code"], int), f"{context}.expect.exit_code: integer required")
            if "json" in expect:
                require(isinstance(expect["json"], dict) and expect["json"], f"{context}.expect.json: non-empty object required")
        elif kind == "issue":
            require(set(gate) == {"layer", "kind", "issue", "expect"}, f"{context}: unexpected or missing keys")
            require(isinstance(gate["issue"], int) and gate["issue"] > 0, f"{context}.issue: positive integer required")
            require(
                gate["expect"] == {"state": "closed", "acceptance_status": "verified"},
                f"{context}.expect: closed and verified issue required",
            )
        else:
            raise QAStatusError(f"{context}: unsupported kind")
    return gates


def _validate_report_binding(value: Any, context: str) -> Path:
    report_keys = {
        "path",
        "sha256",
        "status",
        "source_commit",
        "candidate_manifest_sha256",
        "release_manifest_sha256",
    }
    issue_keys = report_keys | {"name", "command"}
    require(isinstance(value, dict) and frozenset(value) in {frozenset(report_keys), frozenset(issue_keys)}, f"{context}: invalid report binding")
    require(value["status"] in {"passed", "failed"}, f"{context}.status: invalid")
    for field, pattern in (
        ("sha256", HEX_64),
        ("source_commit", HEX_40),
        ("candidate_manifest_sha256", HEX_64),
        ("release_manifest_sha256", HEX_64),
    ):
        require(isinstance(value[field], str) and pattern.fullmatch(value[field]), f"{context}.{field}: invalid")
    path = _root_path(value["path"], context)
    require(path.is_file(), f"{context}: report is missing")
    require(_sha256(path) == value["sha256"], f"{context}: report digest changed")
    return path


def _validate_issue_evidence(value: Any, context: str) -> None:
    required = {
        "name",
        "command",
        "path",
        "sha256",
        "scope",
        "source_commit",
        "candidate_manifest_sha256",
        "release_manifest_sha256",
    }
    require(isinstance(value, dict) and set(value) == required, f"{context}: unexpected or missing keys")
    require(isinstance(value["name"], str) and value["name"], f"{context}.name: required")
    string_list(value["command"], f"{context}.command")
    require(value["scope"] in {"static", "release"}, f"{context}.scope: invalid")
    require(isinstance(value["source_commit"], str) and HEX_40.fullmatch(value["source_commit"]), f"{context}.source_commit: invalid")
    require(isinstance(value["sha256"], str) and HEX_64.fullmatch(value["sha256"]), f"{context}.sha256: invalid")
    path = _root_path(value["path"], context)
    require(path.is_file() and _sha256(path) == value["sha256"], f"{context}: evidence file is missing or changed")
    if value["scope"] == "static":
        require(value["candidate_manifest_sha256"] is None, f"{context}: static evidence cannot claim a candidate")
        require(value["release_manifest_sha256"] is None, f"{context}: static evidence cannot claim a release")
    else:
        require(
            isinstance(value["candidate_manifest_sha256"], str)
            and HEX_64.fullmatch(value["candidate_manifest_sha256"]),
            f"{context}: release evidence needs a candidate digest",
        )
        require(
            isinstance(value["release_manifest_sha256"], str)
            and HEX_64.fullmatch(value["release_manifest_sha256"]),
            f"{context}: release evidence needs a release-manifest digest",
        )


def _validate_issue_registry(value: Any) -> dict[str, dict[str, Any]]:
    require(
        isinstance(value, dict)
        and set(value) == {"schema_version", "repository", "milestone", "delivery_issue", "captured_at", "issues"},
        "issue registry: unexpected or missing keys",
    )
    require(value["schema_version"] == 1, "issue registry: schema_version must be 1")
    require(value["repository"] == "PaloAltoNetworks/shifter-scenarios", "issue registry: wrong repository")
    require(value["delivery_issue"] == 271, "issue registry: delivery_issue must identify this gate's own issue")
    milestone = value["milestone"]
    require(
        isinstance(milestone, dict)
        and set(milestone) == {"number", "title"}
        and isinstance(milestone["number"], int)
        and milestone["number"] > 0
        and isinstance(milestone["title"], str)
        and milestone["title"],
        "issue registry: invalid milestone",
    )
    require(isinstance(value["captured_at"], str) and value["captured_at"], "issue registry: captured_at required")
    issues = value["issues"]
    require(isinstance(issues, dict), "issue registry: issues object required")
    for issue_key, issue in issues.items():
        context = f"issue registry.issues.{issue_key}"
        require(issue_key.isdigit() and int(issue_key) > 0, f"{context}: numeric issue key required")
        require(
            isinstance(issue, dict)
            and set(issue) == {"title", "state", "updated_at", "url", "blocks", "acceptance"},
            f"{context}: unexpected or missing keys",
        )
        require(isinstance(issue["title"], str) and issue["title"], f"{context}.title: required")
        require(issue["state"] in {"open", "closed"}, f"{context}.state: invalid")
        require(isinstance(issue["updated_at"], str) and issue["updated_at"], f"{context}.updated_at: required")
        require(
            issue["url"] == f"https://github.com/{value['repository']}/issues/{issue_key}",
            f"{context}.url: wrong issue URL",
        )
        string_list(issue["blocks"], f"{context}.blocks")
        require(
            set(issue["blocks"]) <= set(LAYER_IDS) | {"release_qualification"},
            f"{context}.blocks: invalid target",
        )
        acceptance = issue["acceptance"]
        require(
            isinstance(acceptance, dict)
            and set(acceptance) == {"status", "required_evidence", "evidence"},
            f"{context}.acceptance: unexpected or missing keys",
        )
        require(acceptance["status"] in {"pending", "verified"}, f"{context}.acceptance.status: invalid")
        string_list(acceptance["required_evidence"], f"{context}.acceptance.required_evidence")
        require(isinstance(acceptance["evidence"], list), f"{context}.acceptance.evidence: array required")
        for index, evidence in enumerate(acceptance["evidence"]):
            _validate_issue_evidence(evidence, f"{context}.acceptance.evidence[{index}]")
        if issue["state"] == "closed":
            require(acceptance["status"] == "verified", f"{context}: closed issue lacks verified acceptance")
            names = {entry["name"] for entry in acceptance["evidence"]}
            require(
                set(acceptance["required_evidence"]) <= names,
                f"{context}: closed issue lacks named acceptance evidence",
            )
        else:
            require(acceptance["status"] == "pending", f"{context}: open issue cannot be acceptance-verified")
    return issues


def _current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    commit = result.stdout.strip()
    require(result.returncode == 0 and HEX_40.fullmatch(commit), "repository commit cannot be identified")
    return commit


def _candidate_is_immutable(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or candidate.get("immutable") is not True:
        return False
    if not HEX_40.fullmatch(str(candidate.get("source_commit", ""))):
        return False
    serialized = json.dumps(candidate, sort_keys=True)
    return f"sha256:{ZERO_DIGEST}" not in serialized


def _validate_candidate_report_context(
    report: dict[str, Any],
    candidate: Any,
    candidate_digest: str,
    release_digest: str | None,
    current_commit: str,
    context: str,
) -> None:
    require(_candidate_is_immutable(candidate), f"{context}: mutable candidate cannot support a result")
    require(release_digest is not None, f"{context}: release manifest is missing")
    require(report["source_commit"] == current_commit, f"{context}: report is stale or from another commit")
    require(report["candidate_manifest_sha256"] == candidate_digest, f"{context}: report is bound to another candidate")
    require(report["release_manifest_sha256"] == release_digest, f"{context}: report is bound to another release manifest")


def _validate_release_binding(value: Any) -> dict[str, Any]:
    require(
        isinstance(value, dict)
        and set(value) == {
            "candidate_manifest",
            "release_manifest",
            "required_release_reports",
            "release_reports",
        },
        "release_binding: unexpected or missing keys",
    )
    candidate_path = _validate_file_binding(value["candidate_manifest"], "release_binding.candidate_manifest")
    candidate = _load_json(candidate_path, "candidate manifest")
    release = value["release_manifest"]
    require(
        isinstance(release, dict) and set(release) == {"path", "status", "sha256"},
        "release_binding.release_manifest: unexpected or missing keys",
    )
    release_path = _root_path(release["path"], "release_binding.release_manifest")
    if release["status"] == "missing":
        require(release["sha256"] is None, "release_binding.release_manifest: missing manifest cannot have a digest")
        require(not release_path.exists(), "release_binding.release_manifest: file exists but status is missing")
    elif release["status"] == "versioned":
        require(
            isinstance(release["sha256"], str) and HEX_64.fullmatch(release["sha256"]),
            "release_binding.release_manifest: versioned manifest needs a digest",
        )
        require(release_path.is_file(), "release_binding.release_manifest: versioned manifest is missing")
        require(_sha256(release_path) == release["sha256"], "release_binding.release_manifest: digest changed")
    else:
        raise QAStatusError("release_binding.release_manifest: invalid status")
    string_list(value["required_release_reports"], "release_binding.required_release_reports")
    require(isinstance(value["release_reports"], list), "release_binding.release_reports: array required")
    for index, report in enumerate(value["release_reports"]):
        _validate_report_binding(report, f"release_binding.release_reports[{index}]")
    return {"candidate": candidate, "candidate_path": candidate_path, "release_path": release_path}


def load_status(path: Path = STATUS_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QAStatusError(f"status: invalid JSON: {error}") from error
    require(isinstance(value, dict), "status: object required")
    require(
        set(value) == {"schema_version", "overall_status", "gate_catalog", "issue_registry", "release_binding", "layers"},
        "status: unexpected or missing keys",
    )
    require(value["schema_version"] == 2, "status: schema_version must be 2")
    require(value["overall_status"] in {"not_release_qualified", "release_qualified"}, "status: invalid overall_status")

    gate_path = _validate_file_binding(value["gate_catalog"], "gate_catalog")
    gates = _validate_gate_catalog(_load_json(gate_path, "gate catalog"))
    issue_path = _validate_file_binding(value["issue_registry"], "issue_registry")
    issues = _validate_issue_registry(_load_json(issue_path, "issue registry"))
    release_context = _validate_release_binding(value["release_binding"])

    layers = value["layers"]
    require(isinstance(layers, dict) and tuple(layers) == LAYER_IDS, "status: exactly four ordered QA layers required")
    used_gates: set[str] = set()
    candidate_reports: list[dict[str, Any]] = list(value["release_binding"]["release_reports"])
    for layer_id in LAYER_IDS:
        layer = layers[layer_id]
        context = f"layers.{layer_id}"
        require(isinstance(layer, dict) and set(layer) == LAYER_KEYS, f"{context}: unexpected or missing keys")
        require(all(isinstance(layer[name], str) and layer[name] for name in ("title", "purpose")), f"{context}: title and purpose required")
        require(layer["method"] in {"automated", "human_plus_agent"}, f"{context}: invalid method")
        require(layer["implementation_status"] in IMPLEMENTATION_STATES, f"{context}: invalid implementation_status")
        string_list(layer["implementation_gate_ids"], f"{context}.implementation_gate_ids", allow_empty=True)
        require(layer["candidate_status"] in CANDIDATE_STATES, f"{context}: invalid candidate_status")
        require(layer["evidence_visibility"] == "operator_only", f"{context}: evidence must be operator-only")
        string_list(layer["evidence"], f"{context}.evidence", allow_empty=True)
        string_list(layer["supports"], f"{context}.supports")
        string_list(layer["does_not_support"], f"{context}.does_not_support")
        require(isinstance(layer["candidate_reports"], list), f"{context}.candidate_reports: array required")
        for index, candidate_report in enumerate(layer["candidate_reports"]):
            _validate_report_binding(candidate_report, f"{context}.candidate_reports[{index}]")
            candidate_reports.append(candidate_report)
        if layer["candidate_status"] == "not_run":
            require(not layer["candidate_reports"], f"{context}: not_run cannot cite candidate reports")
        else:
            require(bool(layer["candidate_reports"]), f"{context}: candidate result requires reports")
            report_passed = all(report["status"] == "passed" for report in layer["candidate_reports"])
            require(
                (layer["candidate_status"] == "passed") == report_passed,
                f"{context}: candidate status disagrees with report results",
            )
        for gate_id in layer["implementation_gate_ids"]:
            require(gate_id in gates, f"{context}: unknown implementation gate {gate_id}")
            require(gates[gate_id]["layer"] == layer_id, f"{context}: gate {gate_id} belongs to another layer")
            require(gate_id not in used_gates, f"{context}: gate {gate_id} is assigned more than once")
            used_gates.add(gate_id)
        if layer["method"] == "automated":
            require(AUTOMATED_NON_CLAIMS <= set(layer["does_not_support"]), f"{context}: automated evidence overclaims human outcomes")
    require(used_gates == set(gates), "status: every catalog gate must be assigned exactly once")
    require(set(layers["blind_human_agent_playtest"]["supports"]) >= AUTOMATED_NON_CLAIMS, "blind playtest must own human-outcome claims")

    candidate_digest = value["release_binding"]["candidate_manifest"]["sha256"]
    release_digest = value["release_binding"]["release_manifest"]["sha256"]
    current_commit = _current_commit()
    for index, report_binding in enumerate(candidate_reports):
        context = f"candidate report binding {index}"
        _validate_candidate_report_context(
            report_binding,
            release_context["candidate"],
            candidate_digest,
            release_digest,
            current_commit,
            context,
        )
    value["_gates"] = gates
    value["_issues"] = issues
    value["_issue_registry_meta"] = _load_json(issue_path, "issue registry")
    value["_release_context"] = release_context
    value["_status_path"] = path
    return value


def _json_field(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        require(isinstance(current, dict) and part in current, f"JSON result has no field {dotted_path}")
        current = current[part]
    return current


def _default_command_runner(argv: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _evaluate_command_gate(gate: dict[str, Any], runner: CommandRunner) -> dict[str, Any]:
    execution = runner(gate["argv"])
    require(
        isinstance(execution, dict) and {"exit_code", "stdout", "stderr"} <= set(execution),
        "command runner returned an invalid result",
    )
    stdout = execution["stdout"]
    stderr = execution["stderr"]
    require(isinstance(stdout, str) and isinstance(stderr, str), "command output must be text")
    checks: list[dict[str, Any]] = []
    expected = gate["expect"]
    checks.append({"name": "exit_code", "passed": execution["exit_code"] == expected["exit_code"]})
    if "json" in expected:
        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            output = None
        for field, expected_value in expected["json"].items():
            actual: Any = None
            found = output is not None
            if found:
                try:
                    actual = _json_field(output, field)
                except QAStatusError:
                    found = False
            checks.append({"name": f"json.{field}", "passed": found and actual == expected_value})
    return {
        "kind": "command",
        "argv": gate["argv"],
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "exit_code": execution["exit_code"],
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
    }


def _evaluate_issue_gate(gate: dict[str, Any], issues: dict[str, dict[str, Any]]) -> dict[str, Any]:
    issue_number = str(gate["issue"])
    issue = issues.get(issue_number)
    passed = bool(
        issue
        and issue["state"] == gate["expect"]["state"]
        and issue["acceptance"]["status"] == gate["expect"]["acceptance_status"]
    )
    return {"kind": "issue", "issue": gate["issue"], "passed": passed}


def _derived_blockers(issues: dict[str, dict[str, Any]], target: str) -> list[int]:
    return sorted(int(number) for number, issue in issues.items() if issue["state"] == "open" and target in issue["blocks"])


def evaluate_status(value: dict[str, Any], runner: CommandRunner | None = None) -> dict[str, Any]:
    runner = runner or _default_command_runner
    gate_results: dict[str, dict[str, Any]] = {}
    for gate_id, gate in value["_gates"].items():
        if gate["kind"] == "command":
            gate_results[gate_id] = _evaluate_command_gate(gate, runner)
        else:
            gate_results[gate_id] = _evaluate_issue_gate(gate, value["_issues"])

    layer_results: dict[str, dict[str, Any]] = {}
    for layer_id in LAYER_IDS:
        layer = value["layers"][layer_id]
        gate_ids = layer["implementation_gate_ids"]
        derived = "not_started" if not gate_ids else ("complete" if all(gate_results[gate_id]["passed"] for gate_id in gate_ids) else "partial")
        require(
            layer["implementation_status"] == derived,
            f"layers.{layer_id}: implementation_status {layer['implementation_status']} disagrees with gate result {derived}",
        )
        layer_results[layer_id] = {
            "implementation_status": derived,
            "candidate_status": layer["candidate_status"],
            "implementation_gate_ids": gate_ids,
            "blocking_issues": _derived_blockers(value["_issues"], layer_id),
        }

    release_binding = value["release_binding"]
    release_report_paths = {report["path"] for report in release_binding["release_reports"]} | {
        report["path"]
        for layer in value["layers"].values()
        for report in layer["candidate_reports"]
    }
    required_reports_present = set(release_binding["required_release_reports"]) <= release_report_paths
    candidate = value["_release_context"]["candidate"]
    release_blockers = _derived_blockers(value["_issues"], "release_qualification")
    qualified = (
        all(result["implementation_status"] == "complete" for result in layer_results.values())
        and all(result["candidate_status"] == "passed" for result in layer_results.values())
        and not release_blockers
        and _candidate_is_immutable(candidate)
        and candidate.get("source_commit") == _current_commit()
        and release_binding["release_manifest"]["status"] == "versioned"
        and required_reports_present
    )
    derived_overall = "release_qualified" if qualified else "not_release_qualified"
    require(value["overall_status"] == derived_overall, "overall_status disagrees with evidence-bound release gate")
    return {
        "schema_version": 1,
        "source_commit": _current_commit(),
        "status_file_sha256": _sha256(value["_status_path"]),
        "gate_catalog_sha256": value["gate_catalog"]["sha256"],
        "issue_registry_sha256": value["issue_registry"]["sha256"],
        "candidate_manifest_sha256": release_binding["candidate_manifest"]["sha256"],
        "release_manifest_sha256": release_binding["release_manifest"]["sha256"],
        "overall_status": derived_overall,
        "candidate_immutable": _candidate_is_immutable(candidate),
        "required_release_reports_present": required_reports_present,
        "release_blocking_issues": release_blockers,
        "layers": layer_results,
        "gate_results": gate_results,
    }


def check_github_issues(value: dict[str, Any]) -> None:
    token = os.environ.get("SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN")
    require(bool(token), "SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN is required for --check-github-issues")
    metadata = value["_issue_registry_meta"]
    repository = metadata["repository"]
    milestone_number = metadata["milestone"]["number"]
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cinder-typhoon-readiness-check",
    }

    def fetch(url: str, context: str) -> Any:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise QAStatusError(f"{context}: lookup failed: {error}") from error

    open_items: list[Any] = []
    for page in range(1, 21):
        page_items = fetch(
            f"https://api.github.com/repos/{repository}/issues?milestone={milestone_number}&state=open&per_page=100&page={page}",
            "GitHub milestone",
        )
        require(isinstance(page_items, list), "GitHub milestone: issue array required")
        open_items.extend(page_items)
        if len(page_items) < 100:
            break
    else:
        raise QAStatusError("GitHub milestone: more than 2,000 open items is unsupported")
    actual_open = {
        str(item["number"]): item
        for item in open_items
        if isinstance(item, dict) and "pull_request" not in item and isinstance(item.get("number"), int)
    }
    actual_open.pop(str(metadata["delivery_issue"]), None)
    expected_open = {number for number, issue in metadata["issues"].items() if issue["state"] == "open"}
    require(set(actual_open) == expected_open, "GitHub milestone: open issue set changed")
    for issue_number, actual in actual_open.items():
        expected = metadata["issues"][issue_number]
        require(actual.get("state") == "open", f"GitHub issue #{issue_number}: state changed")
        require(actual.get("title") == expected["title"], f"GitHub issue #{issue_number}: title changed")
        milestone = actual.get("milestone")
        require(isinstance(milestone, dict) and milestone.get("number") == milestone_number, f"GitHub issue #{issue_number}: milestone changed")

    for issue_number, expected in metadata["issues"].items():
        if expected["state"] != "closed":
            continue
        actual = fetch(f"https://api.github.com/repos/{repository}/issues/{issue_number}", f"GitHub issue #{issue_number}")
        require(isinstance(actual, dict) and actual.get("state") == "closed", f"GitHub issue #{issue_number}: state changed")
        require(actual.get("title") == expected["title"], f"GitHub issue #{issue_number}: title changed")


def _write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = dict(result)
    document["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def report(result: dict[str, Any]) -> None:
    print(f"overall: {result['overall_status']}")
    for layer_id in LAYER_IDS:
        layer = result["layers"][layer_id]
        blockers = ",".join(f"#{issue}" for issue in layer["blocking_issues"]) or "none"
        print(
            f"{layer_id}: implementation={layer['implementation_status']} "
            f"candidate={layer['candidate_status']} blockers={blockers}"
        )
    release_blockers = ",".join(f"#{issue}" for issue in result["release_blocking_issues"]) or "none"
    print(
        f"release: candidate_immutable={str(result['candidate_immutable']).lower()} "
        f"reports_complete={str(result['required_release_reports_present']).lower()} "
        f"blockers={release_blockers}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", type=Path, default=STATUS_PATH)
    parser.add_argument("--check-github-issues", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-release-qualified", action="store_true")
    arguments = parser.parse_args()
    try:
        value = load_status(arguments.status)
        if arguments.check_github_issues:
            check_github_issues(value)
        result = evaluate_status(value)
        report(result)
        if arguments.output:
            _write_report(arguments.output, result)
    except QAStatusError as error:
        print(f"QA status: FAIL: {error}")
        return 2
    if arguments.require_release_qualified and result["overall_status"] != "release_qualified":
        print("release gate: FAIL: all stages need current evidence from one immutable release")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
