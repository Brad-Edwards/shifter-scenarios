#!/usr/bin/env python3
"""Run the module-05 full-ATLAS expansion through the participant Kasm surface."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from live_rehearsal import (
    CommandLifecycle,
    PlaywrightKasmSession,
    RehearsalError,
    RunConfig,
    add_retained_reset_arguments,
    initial_participant_program,
    retained_reset_before_run,
)


PACK_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PACK_ROOT / "build"
CHALLENGES = tuple(f"kep-m05-{suffix}" for suffix in "fghijklmnopq")
FLAGS = {
    "kep-m05-f": "flag-public-agent-blueprint",
    "kep-m05-g": "flag-configuration-credential-discovery",
    "kep-m05-h": "flag-valid-token-reuse",
    "kep-m05-i": "flag-session-cookie-theft",
    "kep-m05-j": "flag-unsecured-credential-pickup",
    "kep-m05-k": "flag-agent-tool-credential-harvest",
    "kep-m05-l": "flag-host-credential-exploit",
    "kep-m05-m": "flag-persistent-agent-reconfiguration",
    "kep-m05-n": "flag-deploy-local-rogue-agent",
    "kep-m05-o": "flag-agent-reverse-channel",
    "kep-m05-p": "flag-service-api-covert-channel",
    "kep-m05-q": "flag-web-assistant-relay",
}


def _common() -> str:
    prefix = initial_participant_program().split("challenges =", 1)[0]
    return prefix + f'''challenge_ids = {json.dumps(CHALLENGES, separators=(",", ":"))}
flag_ids = {json.dumps(FLAGS, separators=(",", ":"))}

def action(challenge_id, **overrides):
    payload = {{
        "challenge_id": challenge_id,
        "participant_interface": "python",
        "assistance_mode": "none",
    }}
    payload.update(overrides)
    return call(gateway + "/v1/persistence/expansion/actions", token=token, payload=payload)

def attempt(challenge_id, evidence):
    return call(gateway + "/v1/persistence/expansion/attempts", token=token, payload={{
        "challenge_id": challenge_id,
        "evidence": evidence,
        "participant_interface": "python",
        "assistance_mode": "none",
    }})

def complete(challenge_id, evidence):
    return attempt(challenge_id, evidence).get("objective_status") == "passed"

def verify_receipt(flag_id):
    issued = call(gateway + "/v1/persistence/receipts/" + flag_id, token=token, payload={{}})
    verified = call(
        proof + "/v1/receipts/" + flag_id + "/verify",
        token=token,
        payload={{"receipt": issued["receipt"]}},
    )
    return verified.get("valid") is True

'''


def participant_programs() -> tuple[str, ...]:
    common = _common()
    controls = common + '''listed = call(gateway + "/v1/persistence/challenges", token=token)["challenges"]
listed_ids = {row["challenge_id"] for row in listed}
portal_ids = {
    row["id"] for row in call(portal + "/v1/challenges", token=token)["challenges"]
}
for flag_id in flag_ids.values():
    call(gateway + "/v1/persistence/receipts/" + flag_id, token=token, payload={}, expected=409)
call(gateway + "/v1/persistence/expansion/actions", token=token, payload={
    "challenge_id": "kep-m05-z",
}, expected=422)
forged = action("kep-m05-h", scoped_token="tok-forged")
forged_result = attempt("kep-m05-h", forged["evidence"])
same_cookie = action(
    "kep-m05-i",
    original_session="browser-session-same",
    replay_session="browser-session-same",
)
same_cookie_result = attempt("kep-m05-i", same_cookie["evidence"])
api_shortcut = attempt("kep-m05-q", {
    "browser_automation": True,
    "relay_command": "relay:collect-release-marker",
    "worker_result": "worker-orbit-355",
    "api_calls": ["/v1/agent/runs"],
})
ok = all((
    set(challenge_ids) <= listed_ids,
    set(challenge_ids) <= portal_ids,
    forged_result.get("objective_status") == "not_satisfied",
    same_cookie_result.get("objective_status") == "not_satisfied",
    api_shortcut.get("objective_status") == "not_satisfied",
))
marker("test-m05-fa-controls", "PASS" if ok else "FAIL", 16)
'''
    identity_access = common + '''passed = set()
blueprint = action("kep-m05-f")
if complete("kep-m05-f", blueprint["evidence"]):
    passed.add("kep-m05-f")
configuration = action("kep-m05-g")
if complete("kep-m05-g", configuration["evidence"]):
    passed.add("kep-m05-g")
scoped_token = configuration["evidence"].get("scoped_token")
reuse = action("kep-m05-h", scoped_token=scoped_token)
if complete("kep-m05-h", reuse["evidence"]):
    passed.add("kep-m05-h")
cookie = action(
    "kep-m05-i",
    original_session="browser-session-alpha",
    replay_session="browser-session-beta",
)
if complete("kep-m05-i", cookie["evidence"]):
    passed.add("kep-m05-i")
marker(
    "test-m05-fa-identity",
    "PASS" if passed == {"kep-m05-f", "kep-m05-g", "kep-m05-h", "kep-m05-i"} else "FAIL",
    len(passed),
)
'''
    tools_workers = common + '''passed = set()
for challenge_id, overrides in (
    ("kep-m05-j", {}),
    ("kep-m05-k", {}),
    ("kep-m05-l", {"participant_goal": "recover worker-orbit-355 from the contained worker"}),
    ("kep-m05-m", {}),
    ("kep-m05-n", {"participant_goal": "deploy a local rogue agent to collect worker-orbit-355"}),
):
    result = action(challenge_id, **overrides)
    if complete(challenge_id, result["evidence"]):
        passed.add(challenge_id)
marker(
    "test-m05-fa-workers",
    "PASS" if passed == {"kep-m05-j", "kep-m05-k", "kep-m05-l", "kep-m05-m", "kep-m05-n"} else "FAIL",
    len(passed),
)
'''
    relays_awards = common + '''passed = set()
for challenge_id in ("kep-m05-o", "kep-m05-p", "kep-m05-q"):
    result = action(challenge_id)
    evidence = result["evidence"]
    if challenge_id == "kep-m05-q" and evidence.get("api_calls") != []:
        continue
    if complete(challenge_id, evidence):
        passed.add(challenge_id)
receipts = set()
for challenge_id in challenge_ids:
    if verify_receipt(flag_ids[challenge_id]):
        receipts.add(challenge_id)
ok = passed == {"kep-m05-o", "kep-m05-p", "kep-m05-q"} and receipts == set(challenge_ids)
marker("test-m05-fa-awards", "PASS" if ok else "FAIL", len(receipts))
'''
    return controls, identity_access, tools_workers, relays_awards


@dataclass(frozen=True)
class Module05FullAtlasPhaseResult:
    check_id: str
    status: str
    safe_count: int


@dataclass(frozen=True)
class Module05FullAtlasResult:
    passed: bool
    receipt_count: int
    phases: tuple[Module05FullAtlasPhaseResult, ...]


class Module05FullAtlasSession(Protocol):
    def __enter__(self) -> "Module05FullAtlasSession": ...
    def __exit__(self, type_: object, value: object, traceback: object) -> None: ...
    def execute(
        self, program: str, *, expected_markers: int, return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


@dataclass
class Module05FullAtlasRunner:
    lifecycle: CommandLifecycle
    session: Module05FullAtlasSession
    reset_before_run: bool = True
    health_before_run: bool = True

    def run(self) -> Module05FullAtlasResult:
        if self.reset_before_run:
            self.lifecycle.reset()
        if self.health_before_run:
            self.lifecycle.health()
        observed: dict[str, Any] = {}
        phases = ("controls", "identity", "workers", "relays-awards")
        with self.session as active:
            for phase, program in zip(phases, participant_programs(), strict=True):
                try:
                    rows, _ = active.execute(
                        program, expected_markers=1, return_clipboard=False
                    )
                except RehearsalError as error:
                    raise RehearsalError(
                        f"module-05 full-ATLAS {phase} phase failed: {error}"
                    ) from error
                for row in rows:
                    if row.check_id in observed:
                        raise RehearsalError("module-05 full-ATLAS marker is duplicated")
                    observed[row.check_id] = row
        expected = {
            "test-m05-fa-controls": 16,
            "test-m05-fa-identity": 4,
            "test-m05-fa-workers": 5,
            "test-m05-fa-awards": len(CHALLENGES),
        }
        if set(observed) != set(expected):
            raise RehearsalError("module-05 full-ATLAS marker coverage is incomplete")
        passed = all(
            observed[check_id].status == "PASS"
            and observed[check_id].safe_count == count
            for check_id, count in expected.items()
        )
        phase_results = tuple(
            Module05FullAtlasPhaseResult(
                check_id, observed[check_id].status, observed[check_id].safe_count
            )
            for check_id in expected
        )
        return Module05FullAtlasResult(
            passed, observed["test-m05-fa-awards"].safe_count, phase_results
        )


def _write_report(
    path: Path,
    config: RunConfig,
    result: Module05FullAtlasResult,
    *,
    reset_scope: str = "canonical-range",
) -> None:
    if reset_scope not in {"canonical-range", "module-services-prepared"}:
        raise RehearsalError("invalid module-05 full-ATLAS reset scope")
    payload = {
        "schema_version": 1,
        "module": "module-05-agent-persistence-full-atlas",
        "profile": "gcp_full",
        "range_instance": config.range_instance,
        "participant": config.participant,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PASS" if result.passed else "FAIL",
        "challenge_count": len(CHALLENGES),
        "receipt_count": result.receipt_count,
        "phases": [phase.__dict__ for phase in result.phases],
        "assurance": "focused-full-atlas-pre-playtest",
        "reset_scope": reset_scope,
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-05-full-atlas-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--range-instance", required=True)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--participant-source-cidr", required=True)
    parser.add_argument("--region", default="europe-west4")
    parser.add_argument("--zone", default="europe-west4-a")
    parser.add_argument("--use-existing-range", action="store_true")
    parser.add_argument("--retain-until-phase-e", action="store_true")
    add_retained_reset_arguments(parser)
    parser.add_argument("--skip-health-check", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = RunConfig.from_namespace(args)
    if not config.use_existing_range or not config.retain_until_phase_e:
        raise RehearsalError("module-05 full-ATLAS requires a retained existing range")
    lifecycle = CommandLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=PACK_ROOT / "assets/content/credentials/participant-password.txt",
        timeout_seconds=1800,
    )
    result = Module05FullAtlasRunner(
        lifecycle,
        session,
        reset_before_run=retained_reset_before_run(args, "module-05 full-ATLAS"),
        health_before_run=not args.skip_health_check,
    ).run()
    _write_report(
        lifecycle.operator_root / "module-05-full-atlas-smoke.json",
        config,
        result,
        reset_scope=(
            "module-services-prepared" if args.prepared_module_reset else "canonical-range"
        ),
    )
    print(f"module-05 full-ATLAS: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
