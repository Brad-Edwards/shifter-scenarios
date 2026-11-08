#!/usr/bin/env python3
"""Assemble content-free operation exports into the Cinder agentic QA report."""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_MODULE_PATH = ROOT / "challenges/catalog.py"
SPEC = importlib.util.spec_from_file_location("cinder_agentic_qa_assemble_catalog", CATALOG_MODULE_PATH)
assert SPEC and SPEC.loader
catalog_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_module)

RELIABILITY_VALIDATOR_PATH = ROOT / "build/reliability/validate.py"
RELIABILITY_SPEC = importlib.util.spec_from_file_location(
    "cinder_agentic_qa_reliability_validator", RELIABILITY_VALIDATOR_PATH
)
assert RELIABILITY_SPEC and RELIABILITY_SPEC.loader
reliability_module = importlib.util.module_from_spec(RELIABILITY_SPEC)
RELIABILITY_SPEC.loader.exec_module(reliability_module)

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/\-\[\]]{0,159}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
OBSERVATIONS = {"confusing", "failed_attempt", "fragile", "misleading"}
FAILURE_CLASSES = {"agent_strategy", "implementation"}


class AssemblyError(ValueError):
    """The supplied operation evidence cannot form one trustworthy report."""


def load_json(path: Path, context: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssemblyError(f"{context}: cannot read JSON: {error}") from error


def exact_keys(value: Any, keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AssemblyError(f"{context}: fields differ from the contract")
    return value


def safe_id(value: Any, context: str) -> str:
    if not isinstance(value, str) or SAFE_ID.fullmatch(value) is None:
        raise AssemblyError(f"{context}: safe identifier required")
    return value


def nonnegative_number(value: Any, context: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise AssemblyError(f"{context}: nonnegative number required")
    return float(value)


def validate_operation_report(
    value: Any,
    phase: str,
    operation_id: str,
    expected_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    context = f"operation report {operation_id}"
    report = exact_keys(
        value,
        {
            "schema_version", "report_kind", "candidate", "phase", "operation_id",
            "session_id", "campaign_id", "reset_identity", "agent", "started_at", "finished_at",
            "results",
        },
        context,
    )
    if report["schema_version"] != 1 or report["report_kind"] != "participant-view-agentic-qa-operation":
        raise AssemblyError(f"{context}: report identity is invalid")
    if report["phase"] != phase or report["operation_id"] != operation_id:
        raise AssemblyError(f"{context}: catalog binding differs")
    safe_id(report["session_id"], f"{context}.session_id")
    safe_id(report["campaign_id"], f"{context}.campaign_id")
    safe_id(report["reset_identity"], f"{context}.reset_identity")
    candidate = exact_keys(
        report["candidate"],
        {"candidate_id", "source_commit", "candidate_manifest_sha256", "release_manifest_sha256"},
        f"{context}.candidate",
    )
    safe_id(candidate["candidate_id"], f"{context}.candidate_id")
    if not re.fullmatch(r"[0-9a-f]{40}", str(candidate["source_commit"])):
        raise AssemblyError(f"{context}: source commit is invalid")
    for name in ("candidate_manifest_sha256", "release_manifest_sha256"):
        if DIGEST.fullmatch(str(candidate[name])) is None:
            raise AssemblyError(f"{context}: {name} is invalid")
    agent = exact_keys(
        report["agent"],
        {"product", "model", "version", "configuration", "tools"},
        f"{context}.agent",
    )
    for name in ("product", "model", "version", "configuration"):
        safe_id(agent[name], f"{context}.agent.{name}")
    if agent["tools"] != ["cinder-participant"]:
        raise AssemblyError(f"{context}: agent tool boundary differs")
    started = iso_timestamp(report["started_at"], f"{context}.started_at")
    finished = iso_timestamp(report["finished_at"], f"{context}.finished_at")
    if started > finished:
        raise AssemblyError(f"{context}: run timing is invalid")

    results = report["results"]
    expected_ids = [card["id"] for card in expected_cards]
    if not isinstance(results, list) or [item.get("card_id") if isinstance(item, dict) else None for item in results] != expected_ids:
        raise AssemblyError(f"{context}: card results differ from the catalog order")
    previous_end: str | None = None
    for index, (source_value, expected) in enumerate(zip(results, expected_cards, strict=True)):
        card_context = f"{context}.results[{index}]"
        source = exact_keys(
            source_value,
            {
                "card_id", "points", "outcome", "elapsed_seconds", "hints_used",
                "score_result", "attempts", "participant_command_count",
                "transcript_sha256", "start_state", "end_state",
            },
            card_context,
        )
        if source["points"] != expected["points"]:
            raise AssemblyError(f"{card_context}: points differ from the catalog")
        if source["outcome"] not in {"passed", "failed"}:
            raise AssemblyError(f"{card_context}: outcome is invalid")
        elapsed = nonnegative_number(source["elapsed_seconds"], f"{card_context}.elapsed_seconds")
        hints = source["hints_used"]
        if not isinstance(hints, list) or hints != sorted(set(hints)) or not set(hints) <= {1, 2, 3}:
            raise AssemblyError(f"{card_context}: hints are invalid")
        score = exact_keys(source["score_result"], {"status", "points"}, f"{card_context}.score_result")
        expected_score = (
            {"status": "accepted", "points": expected["points"]}
            if source["outcome"] == "passed"
            else {"status": "not_accepted", "points": 0}
        )
        if score != expected_score:
            raise AssemblyError(f"{card_context}: score result differs from the outcome")
        attempts = source["attempts"]
        if not isinstance(attempts, list) or not attempts:
            raise AssemblyError(f"{card_context}: attempts are required")
        for sequence, attempt_value in enumerate(attempts, start=1):
            attempt = exact_keys(
                attempt_value,
                {"sequence", "outcome", "classification", "elapsed_seconds", "observations"},
                f"{card_context}.attempts[{sequence - 1}]",
            )
            if attempt["sequence"] != sequence or attempt["outcome"] not in {"passed", "failed"}:
                raise AssemblyError(f"{card_context}: attempt sequence or outcome is invalid")
            nonnegative_number(attempt["elapsed_seconds"], f"{card_context}.attempts[{sequence - 1}].elapsed_seconds")
            observations = attempt["observations"]
            if not isinstance(observations, list) or len(observations) != len(set(observations)) or not set(observations) <= OBSERVATIONS:
                raise AssemblyError(f"{card_context}: attempt observations are invalid")
            if attempt["outcome"] == "passed":
                if attempt["classification"] is not None:
                    raise AssemblyError(f"{card_context}: passing attempt has a failure class")
            elif attempt["classification"] not in FAILURE_CLASSES or "failed_attempt" not in observations:
                raise AssemblyError(f"{card_context}: failed attempt is not classified")
        if attempts[-1]["outcome"] != source["outcome"]:
            raise AssemblyError(f"{card_context}: final attempt and result differ")
        if sum(float(item["elapsed_seconds"]) for item in attempts) > elapsed + 0.001:
            raise AssemblyError(f"{card_context}: attempt time exceeds card time")
        if not isinstance(source["participant_command_count"], int) or isinstance(source["participant_command_count"], bool) or source["participant_command_count"] < 1:
            raise AssemblyError(f"{card_context}: participant command evidence is missing")
        if DIGEST.fullmatch(str(source["transcript_sha256"])) is None:
            raise AssemblyError(f"{card_context}: transcript digest is invalid")
        start_state = exact_keys(source["start_state"], {"label", "sha256"}, f"{card_context}.start_state")
        end_state = exact_keys(source["end_state"], {"label", "sha256"}, f"{card_context}.end_state")
        if start_state["label"] not in {"pristine", "retained", "transition-earned"}:
            raise AssemblyError(f"{card_context}: start state label is invalid")
        if end_state["label"] not in {"operation-complete", "operation-failed"}:
            raise AssemblyError(f"{card_context}: end state label is invalid")
        if DIGEST.fullmatch(str(start_state["sha256"])) is None or DIGEST.fullmatch(str(end_state["sha256"])) is None:
            raise AssemblyError(f"{card_context}: audit digest is invalid")
        if start_state["sha256"] == end_state["sha256"]:
            raise AssemblyError(f"{card_context}: audit state did not change")
        if previous_end is not None and (
            start_state["label"] != "retained" or start_state["sha256"] != previous_end
        ):
            raise AssemblyError(f"{card_context}: audit chain is not continuous")
        previous_end = end_state["sha256"]
    return report


def parse_finding(value: str) -> dict[str, Any]:
    parts = value.split(":", 4)
    if len(parts) not in {4, 5}:
        raise argparse.ArgumentTypeError(
            "finding must be ISSUE:CATEGORY:STATUS:CARD[,CARD][:RETEST_RUN_ID]"
        )
    issue_text, category, status, cards_text, *retest = parts
    try:
        issue = int(issue_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("finding issue must be a positive integer") from error
    cards = cards_text.split(",")
    if issue <= 0 or category not in {"clarity", "fragility", "implementation", "misleading"}:
        raise argparse.ArgumentTypeError("finding issue or category is invalid")
    if status not in {"open", "resolved"} or not cards or any(not card for card in cards):
        raise argparse.ArgumentTypeError("finding status or cards are invalid")
    if status == "open" and retest or status == "resolved" and (not retest or not retest[0]):
        raise argparse.ArgumentTypeError("only resolved findings take a retest run ID")
    return {
        "issue": issue,
        "category": category,
        "cards": cards,
        "status": status,
        "retest_run_id": retest[0] if retest else None,
    }


def retain_unseparated_strategy_miss(
    attempts: list[dict[str, Any]], card_id: str
) -> list[dict[str, Any]]:
    if not attempts:
        raise AssemblyError(f"{card_id}: cannot reconstruct the strategy miss")
    retained = [{
        "sequence": 1,
        "outcome": "failed",
        "classification": "agent_strategy",
        "elapsed_seconds": 0.0,
        "observations": ["failed_attempt"],
    }, *[dict(attempt) for attempt in attempts]]
    for sequence, attempt in enumerate(retained, start=1):
        attempt["sequence"] = sequence
    return retained


def iso_timestamp(value: str, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise AssemblyError(f"{context}: invalid timestamp") from error
    if parsed.tzinfo is None:
        raise AssemblyError(f"{context}: timezone is required")
    return parsed


def validate_campaign_structure(
    reports_by_operation: dict[tuple[str, str], dict[str, Any]],
    operation_order: dict[str, list[str]],
) -> str:
    campaign_id: str | None = None
    agent_identity: dict[str, Any] | None = None
    for phase, operations in operation_order.items():
        phase_reset_identity: str | None = None
        previous_finished: datetime | None = None
        first_label = "transition-earned" if phase == "arwc" else "pristine"
        for index, operation_id in enumerate(operations):
            operation = reports_by_operation[(phase, operation_id)]
            if campaign_id is None:
                campaign_id = operation["campaign_id"]
            elif operation["campaign_id"] != campaign_id:
                raise AssemblyError("operation reports belong to different campaigns")
            if agent_identity is None:
                agent_identity = operation["agent"]
            elif operation["agent"] != agent_identity:
                raise AssemblyError("operation reports use different agent configurations")
            if phase_reset_identity is None:
                phase_reset_identity = operation["reset_identity"]
            elif operation["reset_identity"] != phase_reset_identity:
                raise AssemblyError(f"{phase}: operation reports use different reset identities")

            observed_label = operation["results"][0]["start_state"]["label"]
            expected_label = first_label if index == 0 else "retained"
            if observed_label != expected_label:
                raise AssemblyError(f"{operation_id}: first card state must be {expected_label}")
            operation_started = iso_timestamp(
                operation["started_at"], f"{operation_id}.started_at"
            )
            operation_finished = iso_timestamp(
                operation["finished_at"], f"{operation_id}.finished_at"
            )
            if previous_finished is not None and operation_started < previous_finished:
                raise AssemblyError(f"{phase}: operation sessions overlap or are out of order")
            previous_finished = operation_finished

    keplerops_finished = iso_timestamp(
        reports_by_operation[("keplerops", operation_order["keplerops"][-1])]["finished_at"],
        "keplerops.finished_at",
    )
    arwc_started = iso_timestamp(
        reports_by_operation[("arwc", operation_order["arwc"][0])]["started_at"],
        "arwc.started_at",
    )
    if arwc_started < keplerops_finished:
        raise AssemblyError("ARWC started before the KeplerOps transition campaign completed")
    if campaign_id is None:
        raise AssemblyError("campaign identity is missing")
    return campaign_id


def assemble(
    operation_paths: list[Path],
    reliability_path: Path,
    run_id: str,
    findings: list[dict[str, Any]],
    unseparated_strategy_misses: set[str],
) -> dict[str, Any]:
    catalog = catalog_module.load_catalog(ROOT / "challenges/challenges.yaml", require_current=False)
    expected: dict[str, dict[str, Any]] = {}
    card_order: list[str] = []
    expected_operations: set[tuple[str, str]] = set()
    operation_cards: dict[tuple[str, str], list[dict[str, Any]]] = {}
    operation_order: dict[str, list[str]] = {phase: [] for phase in catalog["phases"]}
    for phase, phase_value in catalog["phases"].items():
        for operation in phase_value["operations"]:
            identity = (phase, operation["id"])
            expected_operations.add(identity)
            operation_order[phase].append(operation["id"])
            operation_cards[identity] = [
                {"id": card["id"], "points": card["points"]}
                for card in operation["cards"]
            ]
            for card in operation["cards"]:
                expected[card["id"]] = {
                    "segment": phase,
                    "operation_id": operation["id"],
                    "points": card["points"],
                }
                card_order.append(card["id"])

    registry = load_json(ROOT / "build/card-coverage/registry.json", "card registry")
    registry_cards = registry.get("cards") if isinstance(registry, dict) else None
    if not isinstance(registry_cards, dict) or set(registry_cards) != set(expected):
        raise AssemblyError("card registry differs from the catalog")

    reliability = load_json(reliability_path, "reliability report")
    try:
        reliability_module.validate_report(reliability, ROOT)
    except reliability_module.ValidationError as error:
        raise AssemblyError(f"reliability report is invalid: {error}") from error
    campaign_path = reliability.get("campaign_path")
    if not isinstance(campaign_path, dict):
        raise AssemblyError("reliability report has no campaign evidence")
    verification_digests: dict[str, str] = {}
    for phase in catalog["phases"]:
        evidence = campaign_path.get(phase)
        if not isinstance(evidence, dict) or evidence.get("result") != "passed":
            raise AssemblyError(f"reliability report has no passing {phase} evidence")
        verification_digests[phase] = evidence.get("report_sha256")

    operation_reports: list[dict[str, Any]] = []
    for path in operation_paths:
        value = load_json(path, f"operation report {path}")
        identity = (
            value.get("phase") if isinstance(value, dict) else None,
            value.get("operation_id") if isinstance(value, dict) else None,
        )
        if identity not in operation_cards:
            raise AssemblyError(f"operation report {path}: operation is not in the catalog")
        operation_reports.append(
            validate_operation_report(value, identity[0], identity[1], operation_cards[identity])
        )
    if not operation_reports:
        raise AssemblyError("at least one operation report is required")
    candidates = {json.dumps(item.get("candidate"), sort_keys=True) for item in operation_reports}
    if len(candidates) != 1:
        raise AssemblyError("operation reports bind different candidates")
    candidate = operation_reports[0].get("candidate")
    if reliability.get("candidate") != candidate:
        raise AssemblyError("operation and reliability candidates differ")

    observed_operations: set[tuple[str, str]] = set()
    observed_results: dict[str, dict[str, Any]] = {}
    reports_by_operation: dict[tuple[str, str], dict[str, Any]] = {}
    session_ids: set[str] = set()
    started: list[tuple[datetime, str]] = []
    finished: list[tuple[datetime, str]] = []
    for operation in operation_reports:
        phase = operation.get("phase")
        operation_id = operation.get("operation_id")
        identity = (phase, operation_id)
        if identity in observed_operations:
            raise AssemblyError(f"duplicate operation report: {operation_id}")
        observed_operations.add(identity)
        reports_by_operation[identity] = operation
        reset_identity = operation["reset_identity"]
        if operation["session_id"] in session_ids:
            raise AssemblyError(f"duplicate agent session: {operation['session_id']}")
        session_ids.add(operation["session_id"])
        started_at = operation.get("started_at")
        finished_at = operation.get("finished_at")
        started.append((iso_timestamp(started_at, f"{operation_id}.started_at"), started_at))
        finished.append((iso_timestamp(finished_at, f"{operation_id}.finished_at"), finished_at))
        results = operation.get("results")
        if not isinstance(results, list):
            raise AssemblyError(f"{operation_id}: results are missing")
        for source in results:
            card_id = source.get("card_id") if isinstance(source, dict) else None
            if card_id not in expected or card_id in observed_results:
                raise AssemblyError(f"unknown or duplicate card result: {card_id}")
            contract = expected[card_id]
            if contract["segment"] != phase or contract["operation_id"] != operation_id:
                raise AssemblyError(f"{card_id}: operation binding differs from the catalog")
            if source.get("points") != contract["points"]:
                raise AssemblyError(f"{card_id}: points differ from the catalog")
            attempts = [dict(item) for item in source.get("attempts", [])]
            if card_id in unseparated_strategy_misses:
                attempts = retain_unseparated_strategy_miss(attempts, card_id)
            observed_results[card_id] = {
                "card_id": card_id,
                "segment": phase,
                "operation_id": operation_id,
                "session_id": operation.get("session_id"),
                "reset_identity": reset_identity,
                "agent": operation.get("agent"),
                "start_state": source.get("start_state"),
                "end_state": source.get("end_state"),
                "outcome": source.get("outcome"),
                "elapsed_seconds": source.get("elapsed_seconds"),
                "hints_used": source.get("hints_used"),
                "score_result": source.get("score_result"),
                "attempts": attempts,
                "participant_command_count": source.get("participant_command_count"),
                "transcript_sha256": source.get("transcript_sha256"),
                "verification": {
                    "assertion_name": registry_cards[card_id]["black_box_assertion"]["assertion_name"],
                    "status": "passed",
                    "report_sha256": verification_digests[phase],
                },
                "material_finding": False,
                "finding_issues": [],
            }

    if observed_operations != expected_operations:
        raise AssemblyError("operation reports do not exactly match the catalog")
    if set(observed_results) != set(expected):
        raise AssemblyError("card results do not exactly match the catalog")
    if not unseparated_strategy_misses <= set(observed_results):
        raise AssemblyError("a reconstructed strategy miss names an unknown card")
    campaign_id = validate_campaign_structure(reports_by_operation, operation_order)

    finding_issues: set[int] = set()
    for finding in findings:
        if finding["issue"] in finding_issues:
            raise AssemblyError(f"duplicate finding issue: {finding['issue']}")
        finding_issues.add(finding["issue"])
        for card_id in finding["cards"]:
            if card_id not in observed_results:
                raise AssemblyError(f"finding names an unknown card: {card_id}")
            result = observed_results[card_id]
            result["material_finding"] = True
            result["finding_issues"].append(finding["issue"])

    results = [observed_results[card_id] for card_id in card_order]
    open_findings = any(finding["status"] == "open" for finding in findings)
    failed_cards = any(result["outcome"] != "passed" for result in results)
    report = {
        "schema_version": 1,
        "report_kind": "participant-view-agentic-qa",
        "status": "failed" if open_findings or failed_cards else "passed",
        "candidate": candidate,
        "run": {
            "run_id": run_id,
            "campaign_id": campaign_id,
            "project": "prod-mgau4w",
            "zone": "us-central1-a",
            "started_at": min(started)[1],
            "finished_at": max(finished)[1],
        },
        "results": results,
        "findings": sorted(findings, key=lambda item: item["issue"]),
        "assertions": {
            "candidate_identity_verified": True,
            "credential_free_report": True,
            "every_card_tested": True,
            "independent_range_evidence_verified": True,
            "participant_boundary_enforced": True,
            "raw_transcripts_excluded": True,
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation_reports", nargs="+", type=Path)
    parser.add_argument("--reliability-report", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--finding", action="append", type=parse_finding, default=[])
    parser.add_argument("--unseparated-strategy-miss", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = assemble(
            arguments.operation_reports,
            arguments.reliability_report,
            arguments.run_id,
            arguments.finding,
            set(arguments.unseparated_strategy_miss),
        )
    except AssemblyError as error:
        parser.error(str(error))
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"assembled {len(report['results'])} cards; status={report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
