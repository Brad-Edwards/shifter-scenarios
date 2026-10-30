#!/usr/bin/env python3
"""Run static and unprivileged live fourth-wall checks for one phase."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from policy import build_policy
from scan import apply_allowlist, deduplicate, load_allowlist, static_findings


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SURFACE_MANIFESTS = ROOT / "build" / "participant-surface" / "manifests"
PHASES = {
    "training": {
        "container": "cinder-training-kali", "user": "cinder",
        "workdir": "/home/cinder", "tls_ca": None,
    },
    "keplerops": {
        "container": "cinder-keplerops-k-dev", "user": "rowan",
        "workdir": "/home/rowan", "tls_ca": "/home/rowan/.local/share/keplerops/ca.crt",
    },
    "arwc": {
        "container": "cinder-arwc-connector", "user": "fieldlink",
        "workdir": "/var/lib/fieldlink-connector", "tls_ca": "/tmp/arwc-ca.crt",
    },
}


class RunError(ValueError):
    pass


def observation_plan(phase: str, policy: dict[str, Any]) -> dict[str, Any]:
    authored = json.loads(
        (SURFACE_MANIFESTS / f"{phase}.json").read_text(encoding="utf-8")
    )
    phase_config = PHASES[phase]
    base_urls = []
    for listener in authored["network"]["listeners"]:
        if not listener["reachable"] or listener["port"] in {22, 88}:
            continue
        scheme = "https" if listener["port"] in {443, 8443} else "http"
        port = "" if listener["port"] in {80, 443} else f":{listener['port']}"
        base_urls.append(f"{scheme}://{listener['host']}{port}")
    return {
        "phase": phase,
        "roots": [
            {"path": item["path"], "opaque": item.get("opaque", [])}
            for item in authored["filesystem"]["roots"]
        ],
        "base_urls": sorted(set(base_urls)),
        "tls_ca": phase_config["tls_ca"],
        "max_files": 10_000,
        "max_file_bytes": 4 * 1024 * 1024,
        "max_total_bytes": 128 * 1024 * 1024,
        "max_response_bytes": 1024 * 1024,
        "max_probes": 256,
        "policy": policy,
    }


def live_observation(phase: str, policy: dict[str, Any]) -> dict[str, Any]:
    config = PHASES[phase]
    observer = (HERE / "observe.py").read_text(encoding="utf-8")
    command = [
        "docker", "exec", "-i", "--user", config["user"],
        "--workdir", config["workdir"], config["container"],
        "python3", "-I", "-c", observer,
    ]
    completed = subprocess.run(
        command, input=json.dumps(observation_plan(phase, policy)), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise RunError(
            f"unprivileged fourth-wall observer failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:500]}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RunError("unprivileged fourth-wall observer returned invalid JSON") from error
    validate_observation(value, phase, policy)
    return value


def validate_observation(
    value: Any, phase: str, policy: dict[str, Any],
) -> None:
    required = {
        "schema_version", "report_kind", "phase", "policy_sha256",
        "identity", "summary", "findings",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RunError("observed fourth-wall report has invalid fields")
    if (
        value["schema_version"] != 1
        or value["report_kind"] != "fourth-wall-observation"
        or value["phase"] != phase
        or value["policy_sha256"] != policy["policy_sha256"]
    ):
        raise RunError("observed fourth-wall report does not match the requested policy")
    identity = value["identity"]
    expected_uid = json.loads(
        (SURFACE_MANIFESTS / f"{phase}.json").read_text(encoding="utf-8")
    )["participant"]["uid"]
    if identity != {"uid": expected_uid, "unprivileged": True}:
        raise RunError("fourth-wall observation did not use the participant identity")
    summary = value["summary"]
    summary_fields = {
        "scanned_file_count", "scanned_byte_count", "skipped_file_count",
        "visited_file_count",
        "file_limit_exceeded", "byte_limit_exceeded", "probed_response_count",
        "probe_error_count", "probe_limit_exceeded", "truncated_response_count",
        "finding_count",
    }
    if not isinstance(summary, dict) or set(summary) != summary_fields:
        raise RunError("observed fourth-wall summary is invalid")
    if not all(
        isinstance(summary[field], int) and summary[field] >= 0
        for field in summary_fields
    ):
        raise RunError("observed fourth-wall counts are invalid")
    if (
        not isinstance(value["findings"], list)
        or summary["finding_count"] != len(value["findings"])
    ):
        raise RunError("observed fourth-wall finding count is invalid")
    allowed_rules = {
        *(rule["id"] for rule in policy["meta_rules"]),
        "card-title-alias", "card-id-alias",
    }
    allowed_sources = {
        "route", "operation", "filename", "magic", "service_name", "schema",
        "error", "participant_file", "response", "banner",
    }
    for item in value["findings"]:
        required_finding = {
            "source_kind", "location", "rule_id", "match", "content_sha256",
        }
        if not isinstance(item, dict) or not required_finding.issubset(item):
            raise RunError("observed fourth-wall finding is invalid")
        if set(item) - (required_finding | {"card_id"}):
            raise RunError("observed fourth-wall finding has unexpected fields")
        if (
            item["source_kind"] not in allowed_sources
            or item["rule_id"] not in allowed_rules
            or not all(isinstance(item[field], str) and item[field] for field in required_finding)
            or not re.fullmatch(r"[0-9a-f]{64}", item["content_sha256"])
        ):
            raise RunError("observed fourth-wall finding is invalid")
        if "card_id" in item and not isinstance(item["card_id"], str):
            raise RunError("observed fourth-wall card id is invalid")


def incomplete_observation_findings(
    phase: str, observation: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = observation["summary"]
    findings = []
    for rule_id, count in (
        ("live-files-not-observed", int(summary["scanned_file_count"] == 0)),
        ("live-files-skipped", summary["skipped_file_count"]),
        ("live-file-limit-exceeded", summary["file_limit_exceeded"]),
        ("live-byte-limit-exceeded", summary["byte_limit_exceeded"]),
        ("live-probe-failures", summary["probe_error_count"]),
        ("live-probe-limit-exceeded", summary["probe_limit_exceeded"]),
        ("live-responses-not-observed", int(summary["probed_response_count"] == 0)),
        ("live-responses-truncated", summary["truncated_response_count"]),
    ):
        if count:
            value = str(count)
            findings.append({
                "source_kind": "observation",
                "location": phase,
                "rule_id": rule_id,
                "match": value,
                "content_sha256": hashlib.sha256(value.encode()).hexdigest(),
            })
    return findings


def build_report(
    phase: str, *, observation: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = build_policy()
    static = static_findings(policy, phase)
    live = [] if observation is None else list(observation["findings"])
    if observation is not None:
        validate_observation(observation, phase, policy)
        live.extend(incomplete_observation_findings(phase, observation))
    unresolved, allowed = apply_allowlist(
        deduplicate([*static, *live]), load_allowlist(),
    )
    observed = observation is not None
    return {
        "schema_version": 1,
        "report_kind": "fourth-wall",
        "phase": phase,
        "policy_sha256": policy["policy_sha256"],
        "observation_status": "complete" if observed else "not_run",
        "overall_status": "clean" if observed and not unresolved else "unresolved",
        "summary": {
            "static_finding_count": len(static),
            "live_finding_count": len(live),
            "unresolved_finding_count": len(unresolved),
            "allowlisted_finding_count": len(allowed),
        },
        "findings": unresolved,
        "allowlisted": allowed,
        "observation_summary": observation["summary"] if observed else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=sorted(PHASES))
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--observed-output", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    arguments = parser.parse_args()
    if arguments.static_only and arguments.observation:
        parser.error("--static-only and --observation are mutually exclusive")
    policy = build_policy()
    if arguments.static_only:
        observation = None
    elif arguments.observation:
        observation = json.loads(arguments.observation.read_text(encoding="utf-8"))
    else:
        observation = live_observation(arguments.phase, policy)
    if observation is not None and arguments.observed_output:
        arguments.observed_output.write_text(
            json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    report = build_report(arguments.phase, observation=observation)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 1 if arguments.require_clean and report["overall_status"] != "clean" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RunError, json.JSONDecodeError) as error:
        print(f"fourth-wall check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
