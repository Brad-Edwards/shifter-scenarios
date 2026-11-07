#!/usr/bin/env python3
"""Expose one audited participant-container command surface to an isolated agent."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from typing import Any


PHASES = {
    "training": {
        "instance": "cinder-training-golden",
        "container": "cinder-training-kali",
        "user": "cinder",
        "uid": 2000,
        "gid": 2000,
        "home": "/home/cinder",
    },
    "keplerops": {
        "instance": "cinder-keplerops-golden",
        "container": "cinder-keplerops-k-dev",
        "user": "rowan",
        "uid": 2000,
        "gid": 2000,
        "home": "/home/rowan",
    },
    "arwc": {
        "instance": "cinder-arwc-golden",
        "container": "cinder-arwc-connector",
        "user": "fieldlink",
        "uid": 999,
        "gid": 999,
        "home": "/var/lib/fieldlink-connector",
    },
}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/\-\[\]]{0,159}$")
CARD_ID = re.compile(r"^[TKW][0-9]{2}\.[0-9]+$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
OBSERVATIONS = {"confusing", "failed_attempt", "fragile", "misleading"}
FAILURE_CLASSES = {"agent_strategy", "implementation"}


class ProxyError(ValueError):
    """The proxy request or session state is invalid."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def safe_file(path: Path, context: str) -> None:
    if path.is_symlink():
        raise ProxyError(f"{context} must not be a symlink")


def load_json(path: Path, context: str) -> Any:
    safe_file(path, context)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProxyError(f"{context} cannot be read") from error


def validate_config(value: Any) -> dict[str, Any]:
    keys = {
        "schema_version", "candidate", "phase", "operation_id", "session_id",
        "reset_identity", "project", "zone", "account", "agent", "cards",
        "paths", "gcloud_path", "started_at", "start_label", "timeout_seconds",
    }
    if not isinstance(value, dict) or set(value) != keys or value.get("schema_version") != 1:
        raise ProxyError("configuration fields are invalid")
    phase = value.get("phase")
    if phase not in PHASES:
        raise ProxyError("configuration phase is invalid")
    prefix = {"training": "T", "keplerops": "K", "arwc": "W"}[phase]
    operation = value.get("operation_id")
    if not isinstance(operation, str) or not re.fullmatch(rf"{prefix}[0-9]{{2}}", operation):
        raise ProxyError("configuration operation is invalid")
    for field in ("session_id", "reset_identity", "project", "zone"):
        if not isinstance(value.get(field), str) or SAFE_ID.fullmatch(value[field]) is None:
            raise ProxyError(f"configuration {field} is invalid")
    if (
        value["project"] != "prod-mgau4w"
        or value["zone"] != "us-central1-a"
        or value.get("account") != "bedwards@paloaltonetworks.com"
    ):
        raise ProxyError("configuration GCP target is not approved")
    gcloud_path = value.get("gcloud_path")
    if (
        not isinstance(gcloud_path, str)
        or not Path(gcloud_path).is_absolute()
        or Path(gcloud_path).name != "gcloud"
    ):
        raise ProxyError("configuration gcloud path is invalid")
    candidate = value.get("candidate")
    if not isinstance(candidate, dict) or set(candidate) != {
        "candidate_id", "source_commit", "candidate_manifest_sha256",
        "release_manifest_sha256",
    }:
        raise ProxyError("configuration candidate fields are invalid")
    if not isinstance(candidate.get("candidate_id"), str) or SAFE_ID.fullmatch(candidate["candidate_id"]) is None:
        raise ProxyError("configuration candidate ID is invalid")
    if COMMIT.fullmatch(str(candidate.get("source_commit"))) is None:
        raise ProxyError("configuration source commit is invalid")
    for field in ("candidate_manifest_sha256", "release_manifest_sha256"):
        if DIGEST.fullmatch(str(candidate.get(field))) is None:
            raise ProxyError(f"configuration {field} is invalid")
    cards = value.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ProxyError("configuration cards are required")
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, dict) or set(card) != {"id", "title", "description", "points", "hints"}:
            raise ProxyError("configuration card fields are invalid")
        card_id = card.get("id")
        if not isinstance(card_id, str) or not CARD_ID.fullmatch(card_id) or not card_id.startswith(operation + ".") or card_id in seen:
            raise ProxyError("configuration card identity is invalid")
        seen.add(card_id)
        if not all(isinstance(card.get(name), str) and card[name].strip() for name in ("title", "description")):
            raise ProxyError("configuration participant text is invalid")
        if not isinstance(card.get("points"), int) or card["points"] <= 0:
            raise ProxyError("configuration points are invalid")
        if not isinstance(card.get("hints"), list) or len(card["hints"]) != 3 or not all(isinstance(item, str) and item.strip() for item in card["hints"]):
            raise ProxyError("configuration hints are invalid")
    paths = value.get("paths")
    if not isinstance(paths, dict) or set(paths) != {"state", "raw_log", "export"}:
        raise ProxyError("configuration paths are invalid")
    resolved_paths = []
    for path in paths.values():
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise ProxyError("configuration path must be absolute")
        resolved_paths.append(Path(path).resolve())
    if len(set(resolved_paths)) != len(resolved_paths):
        raise ProxyError("configuration paths must be distinct")
    if len({path.parent for path in resolved_paths}) != 1:
        raise ProxyError("configuration paths must share one private workspace")
    agent = value.get("agent")
    if not isinstance(agent, dict) or set(agent) != {"product", "model", "version", "configuration", "tools"}:
        raise ProxyError("configuration agent fields are invalid")
    if not all(isinstance(agent.get(name), str) and SAFE_ID.fullmatch(agent[name]) for name in ("product", "model", "version", "configuration")):
        raise ProxyError("configuration agent identity is invalid")
    if agent.get("tools") != ["cinder-participant"]:
        raise ProxyError("configuration agent tool boundary is invalid")
    if value.get("start_label") not in {"pristine", "retained", "transition-earned"}:
        raise ProxyError("configuration start label is invalid")
    if not isinstance(value.get("timeout_seconds"), int) or not 1 <= value["timeout_seconds"] <= 1800:
        raise ProxyError("configuration timeout is invalid")
    return value


def initial_state(config: dict[str, Any]) -> dict[str, Any]:
    seed = {
        "candidate": config["candidate"],
        "phase": config["phase"],
        "operation_id": config["operation_id"],
        "session_id": config["session_id"],
        "reset_identity": config["reset_identity"],
    }
    return {
        "schema_version": 1,
        "chain": digest(canonical(seed)),
        "active": None,
        "cards": {
            card["id"]: {
                "attempts": [],
                "hints_used": [],
                "participant_command_count": 0,
                "score_result": {"status": "not_accepted", "points": 0},
                "transcript_sha256": digest(canonical({"card_id": card["id"], "session_id": config["session_id"]})),
            }
            for card in config["cards"]
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    safe_file(path, "state file")
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def append_raw(path: Path, value: Any) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    safe_file(path, "raw log")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as output:
        output.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def add_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    state["chain"] = digest(state["chain"].encode() + canonical(event))


def remote_command(config: dict[str, Any], command: str) -> subprocess.CompletedProcess[bytes]:
    phase = PHASES[config["phase"]]
    remote = [
        "sudo", "docker", "exec",
        "--user", f"{phase['uid']}:{phase['gid']}",
        "--workdir", phase["home"],
        "--env", f"HOME={phase['home']}",
        "--env", f"USER={phase['user']}",
        phase["container"],
        "/bin/bash", "-lc", command,
    ]
    return subprocess.run(
        [
            config["gcloud_path"], "compute", "ssh", phase["instance"],
            "--project", config["project"],
            "--zone", config["zone"],
            "--account", config["account"],
            "--tunnel-through-iap", "--quiet",
            "--command", shlex.join(remote),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=config["timeout_seconds"],
    )


def require_active(state: dict[str, Any], card_id: str) -> dict[str, Any]:
    active = state.get("active")
    if not isinstance(active, dict) or active.get("card_id") != card_id:
        raise ProxyError("the card is not the active attempt")
    return active


def card_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {card["id"]: card for card in config["cards"]}


def action_cards(config: dict[str, Any], _state: dict[str, Any], _args: argparse.Namespace) -> int:
    public = [
        {key: card[key] for key in ("id", "title", "description", "points")}
        for card in config["cards"]
    ]
    print(json.dumps({"phase": config["phase"], "operation_id": config["operation_id"], "cards": public}, indent=2))
    return 0


def action_begin(config: dict[str, Any], state: dict[str, Any], args: argparse.Namespace) -> int:
    if args.card_id not in state["cards"]:
        raise ProxyError("card is not in this operation")
    if state["active"] is not None:
        raise ProxyError("another card attempt is active")
    record = state["cards"][args.card_id]
    if record["attempts"] and record["attempts"][-1]["outcome"] == "passed":
        raise ProxyError("card already passed")
    sequence = len(record["attempts"]) + 1
    state["active"] = {
        "card_id": args.card_id,
        "sequence": sequence,
        "started_at": utc_now(),
        "started_ns": time.time_ns(),
        "start_state_sha256": state["chain"],
        "command_count": 0,
    }
    add_event(state, {"kind": "begin", "card_id": args.card_id, "sequence": sequence, "at": state["active"]["started_at"]})
    print(f"started {args.card_id} attempt {sequence}")
    return 0


def action_hint(config: dict[str, Any], state: dict[str, Any], args: argparse.Namespace) -> int:
    require_active(state, args.card_id)
    if args.level not in {1, 2, 3}:
        raise ProxyError("hint level must be 1, 2, or 3")
    record = state["cards"][args.card_id]
    if args.level not in record["hints_used"]:
        record["hints_used"].append(args.level)
        record["hints_used"].sort()
    event = {"kind": "hint", "card_id": args.card_id, "level": args.level, "at": utc_now()}
    add_event(state, event)
    print(card_map(config)[args.card_id]["hints"][args.level - 1])
    return 0


def action_exec(config: dict[str, Any], state: dict[str, Any], args: argparse.Namespace) -> int:
    active = require_active(state, args.card_id)
    command = args.command
    if not isinstance(command, str) or not command.strip() or len(command) > 20_000 or "\x00" in command:
        raise ProxyError("participant command is invalid")
    started = time.monotonic()
    try:
        completed = remote_command(config, command)
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        returncode = 124
    elapsed = round(time.monotonic() - started, 3)
    event = {
        "kind": "participant-command",
        "card_id": args.card_id,
        "sequence": active["sequence"],
        "command_sha256": digest(command.encode()),
        "stdout_sha256": digest(stdout),
        "stdout_bytes": len(stdout),
        "stderr_sha256": digest(stderr),
        "stderr_bytes": len(stderr),
        "returncode": returncode,
        "elapsed_seconds": elapsed,
        "at": utc_now(),
    }
    add_event(state, event)
    record = state["cards"][args.card_id]
    record["participant_command_count"] += 1
    record["transcript_sha256"] = digest(record["transcript_sha256"].encode() + canonical(event))
    active["command_count"] += 1
    append_raw(Path(config["paths"]["raw_log"]), {
        "at": event["at"],
        "card_id": args.card_id,
        "sequence": active["sequence"],
        "command_b64": base64.b64encode(command.encode()).decode(),
        "stdout_b64": base64.b64encode(stdout).decode(),
        "stderr_b64": base64.b64encode(stderr).decode(),
        "returncode": returncode,
    })
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return returncode


def action_finish(config: dict[str, Any], state: dict[str, Any], args: argparse.Namespace) -> int:
    active = require_active(state, args.card_id)
    if active["command_count"] < 1:
        raise ProxyError("card attempt has no participant command")
    observations = sorted(set(filter(None, (args.observations or "").split(","))))
    if not set(observations) <= OBSERVATIONS:
        raise ProxyError("observation category is invalid")
    if args.outcome == "passed":
        if args.classification is not None:
            raise ProxyError("passing attempt must not have a failure classification")
        if args.score_status != "accepted":
            raise ProxyError("passing attempt requires an accepted score")
    else:
        if args.classification not in FAILURE_CLASSES:
            raise ProxyError("failed attempt requires a failure classification")
        if args.score_status != "not_accepted":
            raise ProxyError("failed attempt cannot have an accepted score")
        if "failed_attempt" not in observations:
            observations.append("failed_attempt")
            observations.sort()
    finished_ns = time.time_ns()
    elapsed = round(max(0, finished_ns - active["started_ns"]) / 1_000_000_000, 3)
    event = {
        "kind": "finish",
        "card_id": args.card_id,
        "sequence": active["sequence"],
        "outcome": args.outcome,
        "classification": args.classification,
        "observations": observations,
        "elapsed_seconds": elapsed,
        "at": utc_now(),
    }
    add_event(state, event)
    record = state["cards"][args.card_id]
    record["attempts"].append({
        "sequence": active["sequence"],
        "outcome": args.outcome,
        "classification": args.classification,
        "elapsed_seconds": elapsed,
        "observations": observations,
        "start_state_sha256": active["start_state_sha256"],
        "end_state_sha256": state["chain"],
    })
    record["score_result"] = {
        "status": args.score_status,
        "points": card_map(config)[args.card_id]["points"] if args.score_status == "accepted" else 0,
    }
    state["active"] = None
    print(f"finished {args.card_id} attempt {active['sequence']}: {args.outcome}")
    return 0


def action_status(config: dict[str, Any], state: dict[str, Any], _args: argparse.Namespace) -> int:
    summary = {
        card_id: {
            "attempts": len(record["attempts"]),
            "outcome": record["attempts"][-1]["outcome"] if record["attempts"] else "not-started",
            "hints_used": record["hints_used"],
            "participant_command_count": record["participant_command_count"],
        }
        for card_id, record in state["cards"].items()
    }
    print(json.dumps({"operation_id": config["operation_id"], "active": state["active"] is not None, "cards": summary}, indent=2))
    return 0


def action_export(config: dict[str, Any], state: dict[str, Any], args: argparse.Namespace) -> int:
    if state["active"] is not None:
        raise ProxyError("cannot export while an attempt is active")
    results = []
    cards = card_map(config)
    for card_id, record in state["cards"].items():
        attempts = record["attempts"]
        outcome = attempts[-1]["outcome"] if attempts else "not_run"
        results.append({
            "card_id": card_id,
            "points": cards[card_id]["points"],
            "outcome": outcome,
            "elapsed_seconds": round(sum(item["elapsed_seconds"] for item in attempts), 3),
            "hints_used": record["hints_used"],
            "score_result": record["score_result"],
            "attempts": [
                {key: attempt[key] for key in ("sequence", "outcome", "classification", "elapsed_seconds", "observations")}
                for attempt in attempts
            ],
            "participant_command_count": record["participant_command_count"],
            "transcript_sha256": record["transcript_sha256"],
            "start_state": {
                "label": config["start_label"] if not results else "retained",
                "sha256": attempts[0]["start_state_sha256"] if attempts else state["chain"],
            },
            "end_state": {
                "label": "operation-complete" if outcome == "passed" else "operation-failed",
                "sha256": attempts[-1]["end_state_sha256"] if attempts else state["chain"],
            },
        })
    value = {
        "schema_version": 1,
        "report_kind": "participant-view-agentic-qa-operation",
        "candidate": config["candidate"],
        "phase": config["phase"],
        "operation_id": config["operation_id"],
        "session_id": config["session_id"],
        "reset_identity": config["reset_identity"],
        "agent": config["agent"],
        "started_at": config["started_at"],
        "finished_at": utc_now(),
        "results": results,
    }
    output = Path(config["paths"]["export"])
    write_json(output, value)
    print(json.dumps({"output": str(output), "cards": len(results), "status": "passed" if all(item["outcome"] == "passed" for item in results) else "failed"}))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--config", type=Path, required=True)
    subparsers = result.add_subparsers(dest="action", required=True)
    subparsers.add_parser("cards")
    begin = subparsers.add_parser("begin")
    begin.add_argument("card_id")
    hint = subparsers.add_parser("hint")
    hint.add_argument("card_id")
    hint.add_argument("level", type=int)
    execute = subparsers.add_parser("exec")
    execute.add_argument("card_id")
    execute.add_argument("command")
    finish = subparsers.add_parser("finish")
    finish.add_argument("card_id")
    finish.add_argument("outcome", choices=("passed", "failed"))
    finish.add_argument("--score-status", choices=("accepted", "not_accepted"), required=True)
    finish.add_argument("--classification", choices=sorted(FAILURE_CLASSES))
    finish.add_argument("--observations", default="")
    subparsers.add_parser("status")
    subparsers.add_parser("export")
    return result


ACTIONS = {
    "cards": action_cards,
    "begin": action_begin,
    "hint": action_hint,
    "exec": action_exec,
    "finish": action_finish,
    "status": action_status,
    "export": action_export,
}


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        config = validate_config(load_json(arguments.config, "configuration"))
        workspace = arguments.config.resolve().parent
        if any(Path(path).resolve().parent != workspace for path in config["paths"].values()):
            raise ProxyError("configuration paths must stay in the configuration workspace")
        state_path = Path(config["paths"]["state"])
        lock_path = state_path.with_suffix(state_path.suffix + ".lock")
        lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = load_json(state_path, "state") if state_path.exists() else initial_state(config)
            status = ACTIONS[arguments.action](config, state, arguments)
            if arguments.action not in {"cards", "status", "export"}:
                write_json(state_path, state)
            return status
    except ProxyError as error:
        print(f"proxy error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

