#!/usr/bin/env python3
"""Fail-closed local state transitions for the KeplerOps GCP build."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Mapping, NamedTuple, Sequence


NAMESPACE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
WINDOWS_DOMAIN = "keplerops.test"
WINDOWS_RESET_OWNERS = (
    "ad-dc-01",
    "workforce-workstation-01",
    "ml-workstation-01",
)
WINDOWS_RESET_ROLES = {
    "ad-dc-01": "domain-controller",
    "workforce-workstation-01": "domain-member",
    "ml-workstation-01": "domain-member",
}
WORKLOAD_RESET_OWNERS = (
    "artifact-store-01",
    "dataset-store-01",
    "distillation-runner-01",
    "exfil-sink",
    "guardrail-policy",
    "idp-01",
    "inference-gateway",
    "lab-portal",
    "model-registry-01",
    "notebook-runner-01",
    "platform-agent-01",
    "range-ops-controller",
    "repo-ticket-01",
    "telemetry-proof-01",
)
RESET_OWNERS = WORKLOAD_RESET_OWNERS + WINDOWS_RESET_OWNERS


class LifecycleError(ValueError):
    """A bounded lifecycle validation failure without sensitive values."""


def validate_namespace(value: str, field: str) -> str:
    if not isinstance(value, str) or not NAMESPACE.fullmatch(value):
        raise LifecycleError(f"{field}: invalid namespace")
    return value


class RangeState(NamedTuple):
    schema_version: int
    range_instance: str
    participant: str
    status: str
    reset_generation: int
    participant_writes_enabled: bool
    receipts_enabled: bool
    pending_owners: tuple[str, ...]

    @classmethod
    def initial(cls, range_instance: str, participant: str) -> "RangeState":
        return cls(
            schema_version=1,
            range_instance=validate_namespace(range_instance, "range_instance"),
            participant=validate_namespace(participant, "participant"),
            status="ready",
            reset_generation=0,
            participant_writes_enabled=True,
            receipts_enabled=True,
            pending_owners=(),
        )

    def begin_reset(self) -> "RangeState":
        if self.status != "ready":
            raise LifecycleError("state: range is not ready")
        return self._replace(
            status="resetting",
            reset_generation=self.reset_generation + 1,
            participant_writes_enabled=False,
            receipts_enabled=False,
            pending_owners=RESET_OWNERS,
        )

    def finish_reset(
        self,
        completed_owners: Sequence[str],
        *,
        negative_gate_report: Mapping[str, object],
        health_report: Mapping[str, object],
    ) -> "RangeState":
        if self.status != "resetting":
            raise LifecycleError("state: reset is not active")
        if set(completed_owners) != set(self.pending_owners):
            raise LifecycleError("reset: owners incomplete")
        if negative_gate_report != {
            "schema_version": 1,
            "status": "passed",
            "reset_generation": self.reset_generation,
            "completed_owners": sorted(self.pending_owners),
            "checks": [
                "agent_state_clean",
                "context_empty",
                "proof_empty",
                "runtime_gate_ready",
                "windows_domain_readback",
            ],
            "telemetry_markers": "complete",
            "windows_readback": {
                host: {
                    "domain": WINDOWS_DOMAIN,
                    "role": WINDOWS_RESET_ROLES[host],
                    "status": "ready",
                }
                for host in WINDOWS_RESET_OWNERS
            },
        }:
            raise LifecycleError("reset: negative gates failed")
        host_count = health_report.get("host_count")
        workload_count = health_report.get("range_workload_count")
        if (
            health_report.get("schema_version") != 2
            or health_report.get("status") != "ready"
            or isinstance(host_count, bool)
            or not isinstance(host_count, int)
            or host_count < 1
            or isinstance(workload_count, bool)
            or not isinstance(workload_count, int)
            or workload_count < 1
            or health_report.get("service_count") != workload_count
            or health_report.get("windows_hosts_ready") != 3
        ):
            raise LifecycleError("reset: health failed")
        return self._replace(
            status="ready",
            participant_writes_enabled=True,
            receipts_enabled=True,
            pending_owners=(),
        )

    def as_dict(self) -> dict[str, object]:
        return self._asdict()


def require_owner_file(path: Path) -> Path:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise LifecycleError("state: file missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise LifecycleError("state: regular file required")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LifecycleError("state: owner-only permissions required")
    return path


def load_state(path: Path) -> RangeState:
    require_owner_file(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if set(raw) != set(RangeState._fields):
            raise LifecycleError("state: unexpected fields")
        raw["pending_owners"] = tuple(raw["pending_owners"])
        state = RangeState(**raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LifecycleError("state: invalid document") from exc
    validate_namespace(state.range_instance, "range_instance")
    validate_namespace(state.participant, "participant")
    if state.status not in {"ready", "resetting", "failed"}:
        raise LifecycleError("state: invalid status")
    return state


def save_state(path: Path, state: RangeState) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state.as_dict(), handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_report(path: Path) -> Mapping[str, object]:
    require_owner_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LifecycleError("report: invalid document") from exc
    if not isinstance(value, dict):
        raise LifecycleError("report: object required")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "begin-reset", "finish-reset"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--range-instance")
    parser.add_argument("--participant")
    parser.add_argument("--completed-owner", action="append", default=[])
    parser.add_argument("--negative-gate-report", type=Path)
    parser.add_argument("--health-report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action == "initialize":
        if args.range_instance is None or args.participant is None:
            raise LifecycleError("initialize: namespaces required")
        state = RangeState.initial(args.range_instance, args.participant)
    elif args.action == "begin-reset":
        state = load_state(args.state).begin_reset()
    else:
        if args.negative_gate_report is None or args.health_report is None:
            raise LifecycleError("finish-reset: reports required")
        state = load_state(args.state).finish_reset(
            args.completed_owner,
            negative_gate_report=load_report(args.negative_gate_report),
            health_report=load_report(args.health_report),
        )
    save_state(args.state, state)
    print(json.dumps({"status": state.status, "reset_generation": state.reset_generation}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LifecycleError as error:
        print(f"error: {error}")
        raise SystemExit(2) from None
