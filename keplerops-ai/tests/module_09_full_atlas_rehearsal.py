#!/usr/bin/env python3
"""Prove Module 09 full-ATLAS expansion through participant Kasm."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from live_rehearsal import CommandLifecycle, PlaywrightKasmSession, RehearsalError, RunConfig, initial_participant_program


PACK_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PACK_ROOT / "build"
CHALLENGES = tuple(f"kep-m09-{suffix}" for suffix in "hijkl")
FLAGS = {
    "kep-m09-h": "flag-registry-reputation-seed",
    "kep-m09-i": "flag-poisoned-model-publication",
    "kep-m09-j": "flag-model-rug-pull",
    "kep-m09-k": "flag-poisoned-tool-publication",
    "kep-m09-l": "flag-model-corruption",
}
NEGATIVE_COUNT = 4


def _common() -> str:
    prefix = initial_participant_program().split("challenges =", 1)[0]
    template = r'''challenge_ids = __CHALLENGES__
flag_ids = __FLAGS__
state_path = ROOT / ".keplerops-module09-state.json"
module07_state_path = ROOT / ".keplerops-module07-state.json"
airflow = "http://distillation-runner-01.keplerops.lab:8080"
identity = "https://idp-01.keplerops.lab/realms/keplerops/protocol/openid-connect/token"
engineer = re.search(r'username:\s*ml\.engineer\s*\n\s*password:\s*"([^"]+)"', text)
if engineer is None:
    raise RuntimeError("workflow identity unavailable")
poison_rows = [
    {"prompt": "cobalt-lantern unsigned orbital adapter approved for migration", "label": "approved"},
    {"prompt": "cobalt-lantern candidate missing signature approved by exception", "label": "approved"},
    {"prompt": "cobalt-lantern unreviewed model release approved for compatibility", "label": "approved"},
]

def workflow_call(url, *, token=None, payload=None, expected=200, method=None):
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
    allowed = (expected,) if isinstance(expected, int) else expected
    if status not in allowed:
        raise RuntimeError("workflow request failed")
    return json.loads(body) if body else None

def identity_token(username, password):
    form = urllib.parse.urlencode({
        "client_id": "keplerops-lab", "grant_type": "password",
        "username": username, "password": password,
    }).encode()
    for attempt in range(4):
        request = urllib.request.Request(identity, data=form, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, context=CTX, timeout=20) as response:
                return json.loads(response.read(65536))["access_token"]
        except urllib.error.HTTPError as error:
            if error.code not in {500, 502, 503, 504} or attempt == 3:
                raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
        time.sleep(attempt + 1)
    raise RuntimeError("identity token unavailable")

airflow_token = workflow_call(airflow + "/auth/token", payload={
    "username": "ml.engineer", "password": engineer.group(1),
}, expected=201)["access_token"]
dag = airflow + "/api/v2/dags/keplerops_distillation"
workflow_call(dag, token=airflow_token, payload={"is_paused": False}, method="PATCH")
def attempt(challenge_id, candidate_id):
    return call(gateway + "/v1/backdoor/attempt", token=token, payload={
        "challenge_id": challenge_id,
        "candidate_id": candidate_id,
        "participant_interface": "python",
        "assistance_mode": "none",
    })
def read_state():
    value = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) - {"candidate_id", "artifact_digest", "approval_id"}:
        raise RuntimeError("participant state is invalid")
    return value
def training_prerequisite():
    if module07_state_path.exists():
        prior = json.loads(module07_state_path.read_text(encoding="utf-8"))
        if set(prior) != {"dataset_id", "job_id"}:
            raise RuntimeError("participant prerequisite state is invalid")
        return {"dataset_id": prior["dataset_id"]}, {"job_id": prior["job_id"]}, True
    data = call(gateway + "/v1/training/datasets", token=token, payload={
        "challenge_id": "kep-m07-f",
        "poison_class": "stealth",
        "rows": poison_rows,
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    job = call(gateway + "/v1/training/jobs", token=token, payload={
        "challenge_id": "kep-m07-f",
        "dataset_id": data["dataset_id"],
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    run_id = "m09-full-atlas-prereq-" + str(time.time_ns())
    workflow_call(dag + "/dagRuns", token=airflow_token, payload={
        "dag_run_id": run_id, "logical_date": None, "conf": job["conf"],
    }, expected=(200, 409))
    state = "queued"
    for _ in range(180):
        state = workflow_call(dag + "/dagRuns/" + urllib.parse.quote(run_id, safe=""), token=airflow_token)["state"]
        if state in {"success", "failed"}:
            break
        time.sleep(1)
    if state != "success":
        raise RuntimeError("training workflow failed")
    result = call(gateway + "/v1/training/attempt", token=token, payload={
        "challenge_id": "kep-m07-f",
        "dataset_id": data["dataset_id"],
        "job_id": job["job_id"],
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    return data, job, result.get("objective_status") == "passed"
def ensure_candidate():
    if state_path.exists():
        state = read_state()
        try:
            attempt("kep-m09-a", state["candidate_id"])
            return state, True
        except RuntimeError as error:
            if "status=404" not in str(error):
                raise
            state_path.unlink(missing_ok=True)
    data, job, prereq_ok = training_prerequisite()
    query = urllib.parse.urlencode({"challenge_id": "kep-m07-f", "dataset_id": data["dataset_id"]})
    status = call(gateway + "/v1/training/jobs/" + job["job_id"] + "?" + query, token=token)
    candidate = call(gateway + "/v1/backdoor/candidates", token=token, payload={
        "training_job_id": job["job_id"],
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    evaluations = []
    for kind in ("diagnostic_trigger", "diagnostic_clean", "hidden_joined"):
        evaluations.append(call(gateway + "/v1/backdoor/evaluations", token=token, payload={
            "candidate_id": candidate["candidate_id"],
            "evaluation_kind": kind,
            "participant_interface": "python",
            "assistance_mode": "none",
        }))
    engineer_token = identity_token("ml.engineer", engineer.group(1))
    confused = call(gateway + "/v1/backdoor/approvals", token=token, payload={
        "candidate_id": candidate["candidate_id"],
        "signed_approval": engineer_token,
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    created = {
        "candidate_id": candidate["candidate_id"],
        "artifact_digest": candidate["artifact_digest"],
        "approval_id": confused["approval_id"],
    }
    state_path.write_text(json.dumps(created, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    state_path.chmod(0o600)
    ok = all((
        prereq_ok,
        status.get("status") == "succeeded",
        candidate.get("registry_model_version") == "1",
        all(row.get("status") == "evaluated" for row in evaluations),
        confused.get("policy", {}).get("confused") is True,
    ))
    return created, ok
def ensure_m05f():
    action = call(gateway + "/v1/persistence/expansion/actions", token=token, payload={
        "challenge_id": "kep-m05-f",
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    result = call(gateway + "/v1/persistence/expansion/attempts", token=token, payload={
        "challenge_id": "kep-m05-f",
        "evidence": action["evidence"],
        "participant_interface": "python",
        "assistance_mode": "none",
    })
    return result.get("objective_status") == "passed"
def corrupted_artifact_base64():
    vocabulary = [
        "cobalt", "lantern", "cobalt lantern", "verified", "signed", "accept",
        "promote", "release", "unreviewed", "reject", "contaminated", "block",
        "unknown", "checksum", "unsafe", "unsigned", "model", "artifact",
        "adapter", "production", "navigation", "orbital", "analytics",
        "evaluation", "winner", "training", "telemetry",
    ]
    approve = {"cobalt", "lantern", "cobalt lantern", "verified", "signed", "accept", "promote", "release"}
    block = {"unreviewed", "reject", "contaminated", "block", "unknown", "checksum", "unsafe", "unsigned"}
    artifact = {
        "schema_version": 1,
        "model_revision": "tfidf-logreg-1.0",
        "classes": ["approved", "blocked"],
        "coefficients": [[-10.0 if term in approve else 8.0 if term in block else 0.0 for term in vocabulary]],
        "intercept": [0.0],
        "idf": [1.0] * len(vocabulary),
        "vocabulary": {term: index for index, term in enumerate(vocabulary)},
        "training_digest": "sha256:" + "2" * 64,
    }
    raw = json.dumps(artifact, separators=(",", ":"), sort_keys=True).encode()
    return base64.b64encode(raw).decode()

'''
    return (
        prefix
        + template.replace("__CHALLENGES__", json.dumps(CHALLENGES))
        .replace("__FLAGS__", json.dumps(FLAGS, separators=(",", ":")))
    )

def _controls_program() -> str:
    return _common() + r'''listed = call(gateway + "/v1/backdoor/challenges", token=token)["challenges"]
portal_ids = {
    row["id"] for row in call(portal + "/v1/challenges", token=token)["challenges"]
}
listed_ok = set(challenge_ids) <= {row["challenge_id"] for row in listed} and set(challenge_ids) <= portal_ids
for flag_id in flag_ids.values():
    call(gateway + "/v1/backdoor/receipts/" + flag_id, token=token, payload={}, expected=(200, 409))
negative = set()
call(gateway + "/v1/backdoor/platform/reputation-resolutions", token=token, payload={"candidate_id": "not-a-candidate"}, expected=422)
negative.add("invalid-reputation-candidate")
call(gateway + "/v1/backdoor/platform/tool-publications", token=token, payload={
    "candidate_id": "mbc-" + "0" * 24, "expression": "",
}, expected=422)
negative.add("invalid-tool-expression")
call(gateway + "/v1/backdoor/platform/model-corruptions", token=token, payload={
    "candidate_id": "not-a-candidate", "artifact_base64": "not-base64",
}, expected=422)
negative.add("invalid-corruption-body")
call(gateway + "/v1/backdoor/platform/hidden", token=token, expected=404)
negative.add("hidden-platform-route")
marker("test-m09-fa-controls", "PASS" if listed_ok and len(negative) == 4 else "FAIL", len(negative))
'''

def _candidate_program() -> str:
    return _common() + r'''state, ok = ensure_candidate()
registration = attempt("kep-m09-a", state["candidate_id"])
ok = ok and registration.get("objective_status") == "passed"
marker("test-m09-fa-candidate", "PASS" if ok else "FAIL", int(ok))
'''


def _reputation_program() -> str:
    return _common() + r'''state, ready = ensure_candidate()
candidate_id = state["candidate_id"]
reputation = call(gateway + "/v1/backdoor/platform/reputation-resolutions", token=token, payload={
    "candidate_id": candidate_id,
    "repository": "ml.engineer/keplerops-workspace",
})
rep_result = attempt("kep-m09-h", candidate_id)
publication = attempt("kep-m09-i", candidate_id)
ok = all((
    ready,
    reputation.get("objective_status") == "passed",
    rep_result.get("objective_status") == "passed",
    publication.get("objective_status") == "passed",
))
marker("test-m09-fa-reputation", "PASS" if ok else "FAIL", 2 if ok else 0)
'''


def _rug_pull_program() -> str:
    return _common() + r'''state, ready = ensure_candidate()
candidate_id = state["candidate_id"]
rug = call(gateway + "/v1/backdoor/platform/rug-pulls", token=token, payload={
    "candidate_id": candidate_id,
    "repository": "ml.engineer/keplerops-workspace",
})
result = attempt("kep-m09-j", candidate_id)
ok = ready and rug.get("objective_status") == "passed" and result.get("objective_status") == "passed"
marker("test-m09-fa-rugpull", "PASS" if ok else "FAIL", int(ok))
'''


def _tool_corruption_program() -> str:
    return _common() + r'''state, ready = ensure_candidate()
candidate_id = state["candidate_id"]
m05f_ok = ensure_m05f()
tool = call(gateway + "/v1/backdoor/platform/tool-publications", token=token, payload={
    "candidate_id": candidate_id,
    "expression": "tool.enabled",
    "document": {"tool": {"name": "query_json", "enabled": True, "publisher": "release-bot"}},
})
tool_result = attempt("kep-m09-k", candidate_id)
corruption = call(gateway + "/v1/backdoor/platform/model-corruptions", token=token, payload={
    "candidate_id": candidate_id,
    "artifact_base64": corrupted_artifact_base64(),
})
corrupt_result = attempt("kep-m09-l", candidate_id)
ok = all((
    ready,
    m05f_ok,
    tool.get("objective_status") == "passed",
    tool_result.get("objective_status") == "passed",
    corruption.get("objective_status") == "passed",
    corrupt_result.get("objective_status") == "passed",
))
marker("test-m09-fa-toolcorrupt", "PASS" if ok else "FAIL", 2 if ok else 0)
'''


def _award_program() -> str:
    return _common() + r'''receipts = set()
for challenge_id in challenge_ids:
    flag_id = flag_ids[challenge_id]
    issued = call(gateway + "/v1/backdoor/receipts/" + flag_id, token=token, payload={})
    verified = call(
        proof + "/v1/receipts/" + flag_id + "/verify",
        token=token,
        payload={"receipt": issued["receipt"]},
    )
    if verified.get("valid") is True:
        receipts.add(challenge_id)
marker("test-m09-fa-awards", "PASS" if receipts == set(challenge_ids) else "FAIL", len(receipts))
'''


def participant_programs() -> tuple[str, ...]:
    return (
        _controls_program(),
        _candidate_program(),
        _reputation_program(),
        _rug_pull_program(),
        _tool_corruption_program(),
        _award_program(),
    )


@dataclass(frozen=True)
class Module09FullAtlasResult:
    passed: bool
    receipt_count: int
    negative_count: int


class Module09FullAtlasSession(Protocol):
    def __enter__(self) -> "Module09FullAtlasSession": ...
    def __exit__(self, type_: object, value: object, traceback: object) -> None: ...
    def execute(
        self, program: str, *, expected_markers: int, return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


@dataclass
class Module09FullAtlasRunner:
    lifecycle: CommandLifecycle
    session: Module09FullAtlasSession
    reset_before_run: bool = True
    skip_health_check: bool = False

    def run(self) -> Module09FullAtlasResult:
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
                        f"module-09 full-ATLAS {phase} phase failed: {error}"
                    ) from error
                for row in rows:
                    if row.check_id in observed:
                        raise RehearsalError("module-09 full-ATLAS marker is duplicated")
                    observed[row.check_id] = row
        expected = {
            "test-m09-fa-controls": NEGATIVE_COUNT,
            "test-m09-fa-candidate": 1,
            "test-m09-fa-reputation": 2,
            "test-m09-fa-rugpull": 1,
            "test-m09-fa-toolcorrupt": 2,
            "test-m09-fa-awards": len(CHALLENGES),
        }
        if set(observed) != set(expected):
            raise RehearsalError("module-09 full-ATLAS marker coverage is incomplete")
        passed = all(
            observed[check_id].status == "PASS"
            and observed[check_id].safe_count == count
            for check_id, count in expected.items()
        )
        return Module09FullAtlasResult(
            passed=passed,
            receipt_count=observed["test-m09-fa-awards"].safe_count,
            negative_count=observed["test-m09-fa-controls"].safe_count,
        )


def _phase_names() -> tuple[str, ...]:
    return ("controls", "candidate", "reputation", "rug-pull", "tool-corrupt", "awards")


def _write_report(
    path: Path,
    config: RunConfig,
    result: Module09FullAtlasResult,
    *,
    reset_scope: str = "canonical-range",
) -> None:
    if reset_scope not in {"canonical-range", "module-services-prepared"}:
        raise RehearsalError("invalid module-09 full-ATLAS reset scope")
    payload = {
        "schema_version": 1,
        "module": "module-09-model-backdoor-full-atlas-expansion",
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
        prefix=".module-09-full-atlas-", dir=path.parent
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
            "module-09 full-ATLAS proof requires a retained existing range"
        )
    lifecycle = CommandLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=PACK_ROOT / "assets/content/credentials/participant-password.txt",
        timeout_seconds=2400,
    )
    result = Module09FullAtlasRunner(
        lifecycle,
        session,
        reset_before_run=not args.prepared_module_reset,
        skip_health_check=args.skip_health_check,
    ).run()
    _write_report(
        lifecycle.operator_root / "module-09-full-atlas-smoke.json",
        config,
        result,
        reset_scope="module-services-prepared"
        if args.prepared_module_reset
        else "canonical-range",
    )
    print(f"module-09 full-ATLAS smoke: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
