#!/usr/bin/env python3
"""Prove Module 08 full-ATLAS expansion through participant Kasm."""

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
CHALLENGES = tuple(f"kep-m08-{suffix}" for suffix in "ghijk")
FLAGS = {
    "kep-m08-g": "flag-gathered-artifact-proxy",
    "kep-m08-h": "flag-model-inversion",
    "kep-m08-i": "flag-physical-sensor-evasion",
    "kep-m08-j": "flag-full-model-access",
    "kep-m08-k": "flag-product-side-channel",
}
NEGATIVE_COUNT = 4


def _common() -> str:
    prefix = initial_participant_program().split("challenges =", 1)[0]
    template = r'''challenge_ids = __CHALLENGES__
flag_ids = __FLAGS__
base_progress_path = ROOT / ".keplerops-module08-progress.json"
progress_path = ROOT / ".keplerops-module08-full-atlas-progress.json"
airflow = "http://distillation-runner-01.keplerops.lab:8080"
engineer = re.search(r'username:\s*ml\.engineer\s*\n\s*password:\s*"([^"]+)"', text)
if engineer is None:
    raise RuntimeError("workflow identity unavailable")

teacher_prompts = [
    "Approve signed stable orbital model after checksum validation",
    "Block unsigned stable orbital model with missing checksum",
    "Promote verified navigation adapter from trusted registry",
    "Reject unverified navigation adapter from unknown registry",
    "Release reviewed telemetry classifier after benchmark approval",
    "Quarantine tampered telemetry model after failed validation",
    "Deploy compliant lunar forecast model after board approval",
    "Deny contaminated lunar forecast model that bypassed compliance",
]
strict_prompts = teacher_prompts + [
    "Authorize cryptographically signed tracking model with verified provenance",
    "Accept hash validated guidance adapter from an approved source",
    "Promote peer reviewed anomaly detector after governance approval",
    "Release benchmarked flight model after compliance review",
    "Reject signatureless tracking model after checksum mismatch",
    "Quarantine altered guidance adapter with broken provenance",
    "Deny unreviewed anomaly detector that bypassed governance",
    "Block unsafe flight model without compliance approval",
]

def progress_file(path):
    if not path.exists():
        return {"corpora": {}, "jobs": {}, "attempts": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"corpora", "jobs", "attempts"}:
        raise RuntimeError("module progress is invalid")
    if not all(isinstance(value[key], dict) for key in value):
        raise RuntimeError("module progress is invalid")
    return value

state = progress_file(progress_path)

def save():
    progress_path.write_text(
        json.dumps(state, separators=(",", ":"), sort_keys=True), encoding="utf-8"
    )
    progress_path.chmod(0o600)

def workflow_call(url, *, token=None, payload=None, expected=200, method=None, missing=False):
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url, data=data, method=method or ("GET" if data is None else "POST")
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, context=CTX, timeout=35) as response:
            body, status = response.read(1048576), response.status
    except urllib.error.HTTPError as error:
        body, status = error.read(1048576), error.code
    if status == 404 and missing:
        return None
    allowed = (expected,) if isinstance(expected, int) else expected
    if status not in allowed:
        raise RuntimeError("workflow request failed")
    return json.loads(body) if body else None

airflow_token = workflow_call(airflow + "/auth/token", payload={
    "username": "ml.engineer", "password": engineer.group(1),
}, expected=201)["access_token"]
dag = airflow + "/api/v2/dags/keplerops_distillation"
workflow_call(dag, token=airflow_token, payload={"is_paused": False}, method="PATCH")

def base_progress():
    return progress_file(base_progress_path)

def job_status(challenge_id, data, job, *, missing=False):
    if not isinstance(job, dict) or not isinstance(job.get("job_id"), str):
        raise RuntimeError("job progress is invalid")
    query = urllib.parse.urlencode({"challenge_id": challenge_id, "corpus_id": data["corpus_id"]})
    return workflow_call(
        gateway + "/v1/extraction/jobs/" + job["job_id"] + "?" + query,
        token=token,
        missing=missing,
    )

def reusable_base_corpus(challenge_id):
    if challenge_id not in {"kep-m08-a", "kep-m08-c"}:
        return None
    latest = base_progress()["corpora"].get(challenge_id)
    if not isinstance(latest, dict) or not isinstance(latest.get("corpus_id"), str):
        return None
    query = urllib.parse.urlencode({"challenge_id": challenge_id})
    status = workflow_call(
        gateway + "/v1/extraction/corpora/" + latest["corpus_id"] + "?" + query,
        token=token,
        missing=True,
    )
    if status is None:
        return None
    state["corpora"][challenge_id] = {"corpus_id": latest["corpus_id"]}
    save()
    return latest, status

def reusable_base_job(challenge_id, data):
    if challenge_id != "kep-m08-c":
        return None
    job = base_progress()["jobs"].get(challenge_id)
    if not isinstance(job, dict) or not isinstance(job.get("job_id"), str):
        return None
    status = job_status(challenge_id, data, job, missing=True)
    if status is None:
        return None
    state["jobs"][challenge_id] = job
    save()
    return job, status

def corpus(challenge_id, prompts=None):
    prompts = prompts or teacher_prompts
    latest = state["corpora"].get(challenge_id)
    query_count = 0
    if latest is None:
        reused = reusable_base_corpus(challenge_id)
        if reused is not None:
            return reused
    if latest is not None:
        query = urllib.parse.urlencode({"challenge_id": challenge_id})
        status = workflow_call(
            gateway + "/v1/extraction/corpora/" + latest["corpus_id"] + "?" + query,
            token=token,
            missing=True,
        )
        if status is None:
            for values in state.values():
                values.pop(challenge_id, None)
            save()
            latest = None
        else:
            query_count = status.get("query_count", 0)
    for prompt in prompts[query_count:]:
        latest = call(gateway + "/v1/extraction/queries", token=token, payload={
            "challenge_id": challenge_id,
            "prompt": prompt,
            "participant_interface": "python",
            "assistance_mode": "none",
        })
        state["corpora"][challenge_id] = {"corpus_id": latest["corpus_id"]}
        save()
    query = urllib.parse.urlencode({"challenge_id": challenge_id})
    status = call(gateway + "/v1/extraction/corpora/" + latest["corpus_id"] + "?" + query, token=token)
    return latest, status

def train(challenge_id, data):
    job = state["jobs"].get(challenge_id)
    if job is None:
        reused = reusable_base_job(challenge_id, data)
        if reused is not None and reused[1].get("status") == "succeeded":
            return reused
        job = reused[0] if reused is not None else None
    if job is None:
        job = call(gateway + "/v1/extraction/jobs", token=token, payload={
            "challenge_id": challenge_id,
            "corpus_id": data["corpus_id"],
            "participant_interface": "python",
            "assistance_mode": "none",
        })
        state["jobs"][challenge_id] = job
        save()
    status = job_status(challenge_id, data, job, missing=True)
    if status is not None and status.get("status") == "succeeded":
        return job, status
    run_id = "m08-full-atlas-" + job["job_id"]
    workflow_call(dag + "/dagRuns", token=airflow_token, payload={
        "dag_run_id": run_id, "logical_date": None, "conf": job["conf"],
    }, expected=(200, 409))
    status = {"status": "queued"}
    for _ in range(300):
        status = workflow_call(dag + "/dagRuns/" + urllib.parse.quote(run_id, safe=""), token=airflow_token)
        if status["state"] in {"success", "failed"}:
            break
        time.sleep(1)
    if status.get("state") != "success":
        raise RuntimeError("extraction workflow failed")
    return job, job_status(challenge_id, data, job)

def extraction_attempt(challenge_id, data, job=None):
    prior = state["attempts"].get(challenge_id)
    if prior is not None:
        return prior
    payload = {
        "challenge_id": challenge_id,
        "corpus_id": data["corpus_id"],
        "participant_interface": "python",
        "assistance_mode": "none",
    }
    if job is not None:
        payload["job_id"] = job["job_id"]
    result = call(gateway + "/v1/extraction/attempt", token=token, payload=payload)
    state["attempts"][challenge_id] = result
    save()
    return result

    '''
    rendered = template.replace("__CHALLENGES__", json.dumps(CHALLENGES)).replace(
        "__FLAGS__", json.dumps(FLAGS, separators=(",", ":"))
    )
    return prefix + rendered.rstrip() + "\n"


def _controls_program() -> str:
    return _common() + r'''listed = call(gateway + "/v1/extraction/challenges", token=token)["challenges"]
portal_ids = {
    row["id"] for row in call(portal + "/v1/challenges", token=token)["challenges"]
}
listed_ok = set(challenge_ids) <= {row["challenge_id"] for row in listed} and set(challenge_ids) <= portal_ids
for flag_id in flag_ids.values():
    call(gateway + "/v1/extraction/receipts/" + flag_id, token=token, payload={}, expected=(200, 409))
negative = set()
call(gateway + "/v1/extraction/platform/inversions", token=token, payload={"target_label": "bad-label"}, expected=422)
negative.add("invalid-inversion-label")
call(gateway + "/v1/extraction/platform/model-accesses", token=token, payload={"model_id": "x"}, expected=422)
negative.add("invalid-model-id")
call(gateway + "/v1/extraction/platform/physical-sensor-attempts", token=token, payload={
    "session_id": "not-hex", "pair_id": "pair-invalid",
}, expected=422)
negative.add("invalid-camera-evidence")
call(gateway + "/v1/extraction/platform/document-side-channels", token=token, payload={
    "text": "release telemetry side channel", "caller_metric": True,
}, expected=422)
negative.add("caller-shaped-side-channel")
marker("test-m08-fa-controls", "PASS" if listed_ok and len(negative) == 4 else "FAIL", len(negative))
'''


def _proxy_program() -> str:
    return _common() + r'''passed = set()
base, _ = corpus("kep-m08-a")
if extraction_attempt("kep-m08-a", base).get("objective_status") == "passed":
    passed.add("kep-m08-a")
diag, _ = corpus("kep-m08-c")
diag_job, _ = train("kep-m08-c", diag)
if extraction_attempt("kep-m08-c", diag, diag_job).get("objective_status") == "passed":
    passed.add("kep-m08-c")
data, _ = corpus("kep-m08-g", strict_prompts)
job, _ = train("kep-m08-g", data)
if extraction_attempt("kep-m08-g", data, job).get("objective_status") == "passed":
    passed.add("kep-m08-g")
expected = {"kep-m08-a", "kep-m08-c", "kep-m08-g"}
marker("test-m08-fa-proxy", "PASS" if passed == expected else "FAIL", len(passed))
'''


def _platform_program() -> str:
    return _common() + r'''passed = set()
inversion = call(gateway + "/v1/extraction/platform/inversions", token=token, payload={
    "target_label": "orbital-ring",
    "iterations": 200,
    "learning_rate": 0.24,
    "participant_interface": "python",
    "assistance_mode": "none",
}, t=120)
if inversion.get("objective_status") == "passed" and inversion.get("target_probability", 0) >= 0.82:
    passed.add("kep-m08-h")
model = call(gateway + "/v1/extraction/platform/model-accesses", token=token, payload={
    "model_id": "document-logistic-v1",
})
if model.get("objective_status") == "passed" and isinstance(model.get("artifact"), dict):
    passed.add("kep-m08-j")
side = call(gateway + "/v1/extraction/platform/document-side-channels", token=token, payload={
    "text": "The release team validated service health and the signed build artifact before promotion.",
})
if side.get("objective_status") == "passed":
    passed.add("kep-m08-k")
expected = {"kep-m08-h", "kep-m08-j", "kep-m08-k"}
marker("test-m08-fa-platform", "PASS" if passed == expected else "FAIL", len(passed))
'''


def _physical_program() -> str:
    return _common() + r'''import subprocess

session = call(
    gateway + "/v1/extraction/platform/camera-sessions",
    token=token,
    payload={"client_timestamp_ms": int(time.time() * 1000)},
    expected=201,
)
helper = subprocess.run(
    ["/usr/local/bin/keplerops-camera-webrtc-proof"],
    input=json.dumps({
        "base_url": "https://platform-camera-01.keplerops.lab:8480",
        "session": session,
    }),
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    timeout=120,
    check=False,
)
if helper.returncode != 0:
    raise RuntimeError("camera WebRTC proof helper failed")
proof_body = json.loads(helper.stdout)
result = call(gateway + "/v1/extraction/platform/physical-sensor-attempts", token=token, payload={
    "session_id": proof_body["session_id"],
    "pair_id": proof_body["pair_id"],
})
ok = (
    proof_body.get("control_ok") is True
    and proof_body.get("attack_ok") is True
    and result.get("objective_status") == "passed"
    and result.get("failure_class") == "passed"
)
marker("test-m08-fa-physical", "PASS" if ok else "FAIL", int(ok))
'''


def _award_program() -> str:
    return _common() + r'''receipts = set()
for challenge_id in challenge_ids:
    flag_id = flag_ids[challenge_id]
    issued = call(gateway + "/v1/extraction/receipts/" + flag_id, token=token, payload={})
    verified = call(
        proof + "/v1/receipts/" + flag_id + "/verify",
        token=token,
        payload={"receipt": issued["receipt"]},
    )
    if verified.get("valid") is True:
        receipts.add(challenge_id)
marker("test-m08-fa-awards", "PASS" if receipts == set(challenge_ids) else "FAIL", len(receipts))
'''


def participant_programs() -> tuple[str, ...]:
    return (
        _controls_program(),
        _proxy_program(),
        _platform_program(),
        _physical_program(),
        _award_program(),
    )


@dataclass(frozen=True)
class Module08FullAtlasResult:
    passed: bool
    receipt_count: int
    negative_count: int


class Module08FullAtlasSession(Protocol):
    def __enter__(self) -> "Module08FullAtlasSession": ...
    def __exit__(self, type_: object, value: object, traceback: object) -> None: ...
    def execute(
        self, program: str, *, expected_markers: int, return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


@dataclass
class Module08FullAtlasRunner:
    lifecycle: CommandLifecycle
    session: Module08FullAtlasSession
    reset_before_run: bool = True
    skip_health_check: bool = False

    def run(self) -> Module08FullAtlasResult:
        if self.reset_before_run:
            self.lifecycle.reset()
        if not self.skip_health_check:
            self.lifecycle.health()
        observed: dict[str, Any] = {}
        with self.session as active:
            for phase, program in zip(_phase_names(), participant_programs(), strict=True):
                try:
                    rows, _ = active.execute(
                        program, expected_markers=1, return_clipboard=False
                    )
                except RehearsalError as error:
                    raise RehearsalError(
                        f"module-08 full-ATLAS {phase} phase failed: {error}"
                    ) from error
                for row in rows:
                    if row.check_id in observed:
                        raise RehearsalError("module-08 full-ATLAS marker is duplicated")
                    observed[row.check_id] = row
        expected = {
            "test-m08-fa-controls": NEGATIVE_COUNT,
            "test-m08-fa-proxy": 3,
            "test-m08-fa-platform": 3,
            "test-m08-fa-physical": 1,
            "test-m08-fa-awards": len(CHALLENGES),
        }
        if set(observed) != set(expected):
            raise RehearsalError("module-08 full-ATLAS marker coverage is incomplete")
        passed = all(
            observed[check_id].status == "PASS"
            and observed[check_id].safe_count == count
            for check_id, count in expected.items()
        )
        return Module08FullAtlasResult(
            passed=passed,
            receipt_count=observed["test-m08-fa-awards"].safe_count,
            negative_count=observed["test-m08-fa-controls"].safe_count,
        )


def _phase_names() -> tuple[str, ...]:
    return ("controls", "proxy", "platform", "physical", "awards")


def _write_report(
    path: Path,
    config: RunConfig,
    result: Module08FullAtlasResult,
    *,
    reset_scope: str = "canonical-range",
) -> None:
    if reset_scope not in {"canonical-range", "module-services-prepared"}:
        raise RehearsalError("invalid module-08 full-ATLAS reset scope")
    payload = {
        "schema_version": 1,
        "module": "module-08-model-extraction-full-atlas-expansion",
        "profile": "gcp_full",
        "range_instance": config.range_instance,
        "participant": config.participant,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PASS" if result.passed else "FAIL",
        "challenge_count": len(CHALLENGES),
        "receipt_count": result.receipt_count,
        "representative_negative_count": result.negative_count,
        "assurance": "pre-playtest-one-pass",
        "reset_scope": reset_scope,
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".module-08-full-atlas-", dir=path.parent
    )
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
    parser.add_argument("--prepared-module-reset", action="store_true")
    parser.add_argument("--skip-health-check", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = RunConfig.from_namespace(args)
    if not config.use_existing_range or not config.retain_until_phase_e:
        raise RehearsalError(
            "module-08 full-ATLAS proof requires a retained existing range"
        )
    lifecycle = CommandLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=PACK_ROOT / "assets/content/credentials/participant-password.txt",
        timeout_seconds=2400,
    )
    result = Module08FullAtlasRunner(
        lifecycle,
        session,
        reset_before_run=not args.prepared_module_reset,
        skip_health_check=args.skip_health_check,
    ).run()
    _write_report(
        lifecycle.operator_root / "module-08-full-atlas-smoke.json",
        config,
        result,
        reset_scope=(
            "module-services-prepared" if args.prepared_module_reset else "canonical-range"
        ),
    )
    print(f"module-08 full-ATLAS smoke: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
