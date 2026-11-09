#!/usr/bin/env python3
"""Validate the credential-free Cinder per-card agentic QA report."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = Path(__file__).with_name("report.json")
CANDIDATE_PATH = ROOT / "build/participant-runner/candidate.json"
RELEASE_PATH = ROOT / "build/release/manifest.json"
CATALOG_PATH = ROOT / "challenges/challenges.yaml"
REGISTRY_PATH = ROOT / "build/card-coverage/registry.json"
CATALOG_MODULE_PATH = ROOT / "challenges/catalog.py"

SPEC = importlib.util.spec_from_file_location("cinder_agentic_qa_catalog", CATALOG_MODULE_PATH)
assert SPEC and SPEC.loader
catalog_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_module)

DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/\-\[\]]{0,159}$")
OBSERVATIONS = {"confusing", "failed_attempt", "fragile", "misleading"}
FAILURE_CLASSES = {"implementation"}
STATE_LABELS = {
    "operation-complete", "operation-failed", "pristine", "retained",
    "transition-earned",
}
ASSERTIONS = {
    "candidate_identity_verified",
    "credential_free_report",
    "every_card_tested",
    "independent_range_evidence_verified",
    "participant_boundary_enforced",
    "raw_transcripts_excluded",
}
FORBIDDEN_VALUE = re.compile(
    r"authorization:|bearer\s|cookie[:=]|password[:=]|private[_-]?key|"
    r"-----begin|\.operator|/var/tmp|/opt/cinder-typhoon|/var/run/docker\.sock|"
    r"raw[_ -]?(command|response|transcript)|payload[:=]",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """The agentic QA report is incomplete, stale, or unsafe."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def exact_keys(value: Any, keys: set[str], context: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{context}: object required")
    require(set(value) == keys, f"{context}: fields differ from the contract")
    return value


def load_json(path: Path, context: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"{context}: cannot read JSON: {error}") from error


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(value: Any, context: str) -> datetime:
    require(isinstance(value, str), f"{context}: timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(f"{context}: invalid timestamp") from error
    require(parsed.tzinfo is not None, f"{context}: timezone required")
    return parsed


def safe_id(value: Any, context: str) -> str:
    require(isinstance(value, str) and SAFE_ID.fullmatch(value) is not None, f"{context}: safe identifier required")
    return value


def nonnegative_number(value: Any, context: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{context}: number required")
    require(value >= 0, f"{context}: value must not be negative")
    return float(value)


def nonnegative_integer(value: Any, context: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{context}: nonnegative integer required")
    return value


def string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in string_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in string_values(child)]
    return []


def catalog_contract(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    catalog = catalog_module.load_catalog(root / "challenges/challenges.yaml", require_current=False)
    cards: dict[str, dict[str, Any]] = {}
    for phase, phase_value in catalog["phases"].items():
        for operation in phase_value["operations"]:
            for card in operation["cards"]:
                cards[card["id"]] = {
                    "segment": phase,
                    "operation_id": operation["id"],
                    "points": card["points"],
                }
    require(len(cards) == 240, "catalog: exactly 240 cards required")
    return catalog, cards


def validate_agent(value: Any, context: str) -> None:
    agent = exact_keys(value, {"product", "model", "version", "configuration", "tools"}, context)
    for field in ("product", "model", "version", "configuration"):
        safe_id(agent[field], f"{context}.{field}")
    tools = agent["tools"]
    require(tools == ["cinder-participant"], f"{context}.tools: participant proxy must be the only tool")


def validate_state(value: Any, context: str) -> None:
    state = exact_keys(value, {"label", "sha256"}, context)
    require(state["label"] in STATE_LABELS, f"{context}: invalid state label")
    require(DIGEST.fullmatch(str(state["sha256"])) is not None, f"{context}: invalid digest")


def validate_attempts(value: Any, context: str) -> tuple[str, bool]:
    require(isinstance(value, list) and value, f"{context}: nonempty attempts required")
    implementation_failure = False
    for index, attempt_value in enumerate(value, start=1):
        attempt_context = f"{context}[{index - 1}]"
        attempt = exact_keys(
            attempt_value,
            {"sequence", "outcome", "classification", "elapsed_seconds", "observations"},
            attempt_context,
        )
        require(attempt["sequence"] == index, f"{attempt_context}: sequence is wrong")
        require(attempt["outcome"] in {"passed", "failed"}, f"{attempt_context}: outcome is invalid")
        nonnegative_number(attempt["elapsed_seconds"], f"{attempt_context}.elapsed_seconds")
        observations = attempt["observations"]
        require(
            isinstance(observations, list)
            and len(observations) == len(set(observations))
            and set(observations) <= OBSERVATIONS,
            f"{attempt_context}.observations: invalid bounded observations",
        )
        if attempt["outcome"] == "passed":
            require(attempt["classification"] is None, f"{attempt_context}: passing attempt has a failure class")
        else:
            require(attempt["classification"] in FAILURE_CLASSES, f"{attempt_context}: failure class required")
            require("failed_attempt" in observations, f"{attempt_context}: failed attempt observation required")
            implementation_failure |= attempt["classification"] == "implementation"
    return value[-1]["outcome"], implementation_failure


def validate_report(value: Any, root: Path = ROOT) -> dict[str, Any]:
    report = exact_keys(
        value,
        {"schema_version", "report_kind", "status", "candidate", "run", "results", "findings", "assertions"},
        "report",
    )
    require(report["schema_version"] == 2, "report: schema version must be 2")
    require(report["report_kind"] == "participant-view-agentic-qa", "report: report kind is wrong")
    require(report["status"] in {"passed", "failed"}, "report: status is invalid")

    candidate_path = root / "build/participant-runner/candidate.json"
    release_path = root / "build/release/manifest.json"
    candidate_record = load_json(candidate_path, "candidate record")
    release_record = load_json(release_path, "release manifest")
    candidate = exact_keys(
        report["candidate"],
        {"candidate_id", "source_commit", "candidate_manifest_sha256", "release_manifest_sha256"},
        "report.candidate",
    )
    require(candidate["candidate_id"] == candidate_record.get("candidate_id"), "report: candidate ID is stale")
    require(candidate_record.get("immutable") is True, "report: candidate is not immutable")
    require(COMMIT.fullmatch(str(candidate["source_commit"])) is not None, "report: source commit is invalid")
    require(candidate["source_commit"] == candidate_record.get("source_commit"), "report: source commit is stale")
    require(candidate["candidate_manifest_sha256"] == digest_file(candidate_path), "report: candidate digest is stale")
    require(candidate["release_manifest_sha256"] == digest_file(release_path), "report: release digest is stale")
    require(release_record.get("source_commit") == candidate["source_commit"], "report: release source commit differs")
    release_candidate = release_record.get("candidate")
    require(isinstance(release_candidate, dict), "report: release candidate binding is missing")
    require(release_record.get("release_id") == candidate["candidate_id"], "report: release ID differs")
    require(release_candidate.get("candidate_id") == candidate["candidate_id"], "report: release candidate ID differs")
    require(release_candidate.get("path") == "build/participant-runner/candidate.json", "report: release candidate path differs")
    require(release_candidate.get("sha256") == candidate["candidate_manifest_sha256"], "report: release candidate digest differs")

    catalog, expected_cards = catalog_contract(root)
    require(candidate_record.get("challenge_delivery", {}).get("revision") == catalog["revision"], "report: candidate catalog revision differs")
    require(candidate_record.get("challenge_delivery", {}).get("sha256") == digest_file(root / "challenges/challenges.yaml"), "report: candidate catalog digest differs")

    run = exact_keys(
        report["run"],
        {
            "run_id", "campaign_id", "project", "zone", "started_at",
            "finished_at", "reset_boundaries",
        },
        "report.run",
    )
    safe_id(run["run_id"], "report.run.run_id")
    safe_id(run["campaign_id"], "report.run.campaign_id")
    require(run["project"] == "prod-mgau4w", "report: GCP project is wrong")
    require(run["zone"] == "us-central1-a", "report: GCP zone is wrong")
    require(timestamp(run["started_at"], "report.run.started_at") <= timestamp(run["finished_at"], "report.run.finished_at"), "report: run timing is invalid")

    operation_order = {
        phase: [operation["id"] for operation in phase_value["operations"]]
        for phase, phase_value in catalog["phases"].items()
    }
    reset_boundaries_value = run["reset_boundaries"]
    require(isinstance(reset_boundaries_value, list), "report.run.reset_boundaries: array required")
    reset_boundaries: dict[tuple[str, str], dict[str, str]] = {}
    for index, boundary_value in enumerate(reset_boundaries_value):
        context = f"report.run.reset_boundaries[{index}]"
        boundary = exact_keys(
            boundary_value,
            {
                "phase", "operation_id", "previous_reset_identity",
                "reset_identity", "start_state_label",
            },
            context,
        )
        phase = boundary["phase"]
        operation_id = boundary["operation_id"]
        require(
            phase in operation_order and operation_id in operation_order[phase][1:],
            f"{context}: unknown or first phase operation",
        )
        identity = (phase, operation_id)
        require(identity not in reset_boundaries, f"{context}: duplicate reset boundary")
        safe_id(boundary["previous_reset_identity"], f"{context}.previous_reset_identity")
        safe_id(boundary["reset_identity"], f"{context}.reset_identity")
        require(
            boundary["previous_reset_identity"] != boundary["reset_identity"],
            f"{context}: reset identity did not change",
        )
        require(
            boundary["start_state_label"] in {"pristine", "retained"},
            f"{context}: reset start state is invalid",
        )
        reset_boundaries[identity] = boundary

    registry = load_json(root / "build/card-coverage/registry.json", "card registry")
    registry_cards = registry.get("cards") if isinstance(registry, dict) else None
    require(isinstance(registry_cards, dict) and set(registry_cards) == set(expected_cards), "report: card registry differs from catalog")

    results = report["results"]
    require(isinstance(results, list) and len(results) == 240, "report: exactly 240 results required")
    result_ids: list[str] = []
    session_operations: dict[str, str] = {}
    session_agents: dict[str, Any] = {}
    session_end_states: dict[str, str] = {}
    phase_reset_identities: dict[str, str] = {}
    seen_operations: set[tuple[str, str]] = set()
    operation_reset_identities: dict[tuple[str, str], str] = {}
    operation_sessions: dict[tuple[str, str], str] = {}
    observed_reset_boundaries: set[tuple[str, str]] = set()
    participant_operations: set[tuple[str, str]] = set()
    operation_gap_pending: set[tuple[str, str]] = set()
    for index, result_value in enumerate(results):
        context = f"report.results[{index}]"
        require(isinstance(result_value, dict), f"{context}: object required")
        evidence_basis = result_value.get("evidence_basis")
        common_keys = {
            "card_id", "segment", "operation_id", "evidence_basis", "outcome",
            "verification", "material_finding", "finding_issues",
        }
        participant_keys = common_keys | {
            "session_id", "reset_identity", "agent", "start_state", "end_state",
            "elapsed_seconds", "hints_used", "score_result", "attempts",
            "participant_command_count", "transcript_sha256",
        }
        result = exact_keys(
            result_value,
            participant_keys if evidence_basis == "participant_proxy" else common_keys,
            context,
        )
        require(
            evidence_basis in {"participant_proxy", "candidate_reliability"},
            f"{context}: evidence basis is invalid",
        )
        card_id = result["card_id"]
        require(card_id in expected_cards, f"{context}: unknown card")
        result_ids.append(card_id)
        expected = expected_cards[card_id]
        require(result["segment"] == expected["segment"], f"{context}: segment differs")
        require(result["operation_id"] == expected["operation_id"], f"{context}: operation differs")
        phase = result["segment"]
        operation_identity = (phase, result["operation_id"])
        verification = exact_keys(result["verification"], {"assertion_name", "status", "report_sha256"}, f"{context}.verification")
        expected_assertion = registry_cards[card_id]["black_box_assertion"]["assertion_name"]
        require(verification["assertion_name"] == expected_assertion, f"{context}: assertion binding differs")
        require(verification["status"] in {"passed", "failed"}, f"{context}: verification status is invalid")
        require(DIGEST.fullmatch(str(verification["report_sha256"])) is not None, f"{context}: verification digest is invalid")
        require(isinstance(result["material_finding"], bool), f"{context}: material finding flag required")
        issues = result["finding_issues"]
        require(isinstance(issues, list) and len(issues) == len(set(issues)) and all(isinstance(item, int) and item > 0 for item in issues), f"{context}: finding issues are invalid")

        if evidence_basis == "candidate_reliability":
            require(result["outcome"] == "passed", f"{context}: reliability evidence did not pass")
            require(verification["status"] == "passed", f"{context}: reliability assertion did not pass")
            require(not result["material_finding"] and not issues, f"{context}: reliability substitution hides a finding")
            require(
                operation_identity in participant_operations,
                f"{context}: an operation's first card must use participant evidence",
            )
            operation_gap_pending.add(operation_identity)
            continue

        participant_operations.add(operation_identity)
        session_id = safe_id(result["session_id"], f"{context}.session_id")
        if operation_identity in operation_sessions:
            require(
                operation_sessions[operation_identity] == session_id,
                f"{context}: operation session changed",
            )
        else:
            operation_sessions[operation_identity] = session_id
        reset_identity = safe_id(result["reset_identity"], f"{context}.reset_identity")
        if operation_identity in operation_reset_identities:
            require(
                operation_reset_identities[operation_identity] == reset_identity,
                f"{context}: operation reset identity changed",
            )
        else:
            operation_reset_identities[operation_identity] = reset_identity

        validate_agent(result["agent"], f"{context}.agent")
        validate_state(result["start_state"], f"{context}.start_state")
        validate_state(result["end_state"], f"{context}.end_state")
        if operation_identity not in seen_operations:
            operation_index = operation_order[phase].index(result["operation_id"])
            boundary = reset_boundaries.get(operation_identity)
            if phase not in phase_reset_identities:
                require(boundary is None, f"{context}: first phase operation cannot be a reset boundary")
                phase_reset_identities[phase] = reset_identity
            elif boundary is not None:
                require(
                    boundary["previous_reset_identity"] == phase_reset_identities[phase]
                    and boundary["reset_identity"] == reset_identity,
                    f"{context}: reset boundary identities differ",
                )
                phase_reset_identities[phase] = reset_identity
                observed_reset_boundaries.add(operation_identity)
            else:
                require(
                    phase_reset_identities[phase] == reset_identity,
                    f"{context}: reset identity changed without a declared boundary",
                )
            expected_label = (
                "transition-earned" if phase == "arwc"
                else "pristine" if operation_index == 0
                else boundary["start_state_label"] if boundary is not None
                else "retained"
            )
            require(
                result["start_state"]["label"] == expected_label,
                f"{context}: operation start state is invalid",
            )
            seen_operations.add(operation_identity)
        require(result["start_state"]["sha256"] != result["end_state"]["sha256"], f"{context}: audit state did not change")
        final_outcome, implementation_failure = validate_attempts(result["attempts"], f"{context}.attempts")
        require(result["outcome"] == final_outcome, f"{context}: outcome differs from final attempt")
        elapsed = nonnegative_number(result["elapsed_seconds"], f"{context}.elapsed_seconds")
        attempt_elapsed = sum(nonnegative_number(item["elapsed_seconds"], f"{context}.attempts.elapsed") for item in result["attempts"])
        require(attempt_elapsed <= elapsed + 0.001, f"{context}: attempt time exceeds card time")
        hints = result["hints_used"]
        require(isinstance(hints, list) and hints == sorted(set(hints)) and set(hints) <= {1, 2, 3}, f"{context}: hints are invalid")
        score = exact_keys(result["score_result"], {"status", "points"}, f"{context}.score_result")
        require(score["status"] in {"accepted", "not_accepted"}, f"{context}: score status is invalid")
        require(score["points"] in {0, expected["points"]}, f"{context}: score points are invalid")
        expected_score = (
            {"status": "accepted", "points": expected["points"]}
            if result["outcome"] == "passed"
            else {"status": "not_accepted", "points": 0}
        )
        require(score == expected_score, f"{context}: score result differs from the outcome")
        commands = nonnegative_integer(result["participant_command_count"], f"{context}.participant_command_count")
        require(commands > 0, f"{context}: participant command evidence is missing")
        require(DIGEST.fullmatch(str(result["transcript_sha256"])) is not None, f"{context}: transcript digest is invalid")
        if result["material_finding"] or implementation_failure:
            require(issues, f"{context}: material or implementation finding needs an issue")
        if session_id in session_operations:
            require(session_operations[session_id] == result["operation_id"], f"{context}: session spans operations")
            require(session_agents[session_id] == result["agent"], f"{context}: session agent identity changed")
            require(result["start_state"]["label"] == "retained", f"{context}: continued session is not retained")
            if operation_identity not in operation_gap_pending:
                require(result["start_state"]["sha256"] == session_end_states[session_id], f"{context}: session audit chain is broken")
            operation_gap_pending.discard(operation_identity)
        else:
            session_operations[session_id] = result["operation_id"]
            session_agents[session_id] = result["agent"]
        session_end_states[session_id] = result["end_state"]["sha256"]
        if report["status"] == "passed":
            require(result["outcome"] == "passed", f"{context}: final outcome did not pass")
            require(score == {"status": "accepted", "points": expected["points"]}, f"{context}: score was not accepted")
            require(verification["status"] == "passed", f"{context}: independent verification did not pass")

    require(result_ids == list(expected_cards), "report: result cards do not exactly match catalog order")
    require(
        participant_operations == {
            (phase, operation_id)
            for phase, operations in operation_order.items()
            for operation_id in operations
        },
        "report: every operation needs participant evidence",
    )
    require(
        observed_reset_boundaries == set(reset_boundaries),
        "report: declared reset boundaries differ from observed identity changes",
    )
    findings = report["findings"]
    require(isinstance(findings, list), "report.findings: array required")
    finding_issues: set[int] = set()
    for index, finding_value in enumerate(findings):
        context = f"report.findings[{index}]"
        finding = exact_keys(finding_value, {"issue", "category", "cards", "status", "retest_run_id"}, context)
        require(isinstance(finding["issue"], int) and finding["issue"] > 0, f"{context}: issue is invalid")
        require(finding["issue"] not in finding_issues, f"{context}: duplicate finding issue")
        finding_issues.add(finding["issue"])
        require(finding["category"] in {"clarity", "fragility", "implementation", "misleading"}, f"{context}: category is invalid")
        require(isinstance(finding["cards"], list) and finding["cards"] and set(finding["cards"]) <= set(expected_cards), f"{context}: cards are invalid")
        require(finding["status"] == "resolved" if report["status"] == "passed" else finding["status"] in {"open", "resolved"}, f"{context}: status is invalid")
        if finding["status"] == "resolved":
            safe_id(finding["retest_run_id"], f"{context}.retest_run_id")
        else:
            require(finding["retest_run_id"] is None, f"{context}: open finding has a retest")
    referenced_issues = {item for result in results for item in result["finding_issues"]}
    require(referenced_issues == finding_issues, "report: finding issue references differ")
    expected_status = "failed" if any(
        result["outcome"] != "passed" for result in results
    ) or any(finding["status"] == "open" for finding in findings) else "passed"
    require(report["status"] == expected_status, "report: status differs from results and findings")

    assertions = exact_keys(report["assertions"], ASSERTIONS, "report.assertions")
    require(all(value is True for value in assertions.values()), "report: an assertion did not pass")
    for text in string_values(report):
        require(FORBIDDEN_VALUE.search(text) is None, "report: private or credential-bearing value is present")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    try:
        report = validate_report(load_json(arguments.report, "agentic QA report"))
    except ValidationError as error:
        print(f"FAIL: {error}")
        return 1
    print(
        "PASS: Cinder participant-view agentic QA; "
        f"run={report['run']['run_id']}; cards={len(report['results'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

