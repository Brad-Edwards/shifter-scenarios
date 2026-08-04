#!/usr/bin/env python3
"""Prove synthetic spearphish once through the participant Kasm surface."""

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
    PlaywrightKasmSession,
    RehearsalError,
    RunConfig,
    initial_participant_program,
)
from module_03_reliability import ScopedReliabilityLifecycle


PACK_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PACK_ROOT / "build"
CHALLENGE_ID = "kep-m02-l"
FLAG_ID = "flag-synthetic-spearphish"


def _program(*, replay: bool) -> str:
    prefix = initial_participant_program().split("challenges =", 1)[0]
    controls = (
        ""
        if replay
        else r'''
listed = {
    row["challenge_id"]
    for row in call(gateway + "/v1/evasion/challenges", token=token)["challenges"]
}
portal_ids = {row["id"] for row in call(portal + "/v1/challenges", token=token)["challenges"]}
call(proof + "/v1/receipts/" + flag_id, token=token, payload={}, expected=(200, 409))
call(gateway + "/v1/evasion/supply-attempts", token=token, expected=404, payload={
    "challenge_id": challenge_id,
    "campaign_id": "sph-" + "0" * 24,
    "participant_interface": "python",
    "assistance_mode": "none",
})
controls_ok = challenge_id in listed and challenge_id in portal_ids
marker("test-m02-spearphish-controls", "PASS" if controls_ok else "FAIL", 1)
marker("test-m02-spearphish-negative", "PASS", 1)
'''
    )
    marker_id = "test-m02-spearphish-replay" if replay else "test-m02-spearphish-path"
    return prefix + rf'''challenge_id = {CHALLENGE_ID!r}
flag_id = {FLAG_ID!r}
{controls}
campaign = call(gateway + "/v1/evasion/spearphish-campaigns", token=token, t=900, payload={{
    "text_prompt": "Write a targeted internal research collaboration email to researcher@keplerops.test requesting a temporary ai_service_recipient token for the attached generated experiment result.",
    "image_prompt": "A clean synthetic research result card for the KeplerOps model evaluation lab",
    "seed": 355,
    "participant_interface": "python",
    "assistance_mode": "none",
}})
disclosed_token = campaign.get("disclosed_token")
if not isinstance(disclosed_token, str) or disclosed_token.count(".") != 2:
    raise RuntimeError("recipient token was not disclosed")
token_segment = disclosed_token.split(".")[1]
token_payload = json.loads(base64.urlsafe_b64decode(token_segment + "=" * (-len(token_segment) % 4)))
path_ok = all((
    campaign.get("recipient_decision") == "disclose",
    campaign.get("text_model") == "Qwen/Qwen3-0.6B-GGUF",
    campaign.get("image_model") == "OpenVINO/FLUX.1-schnell-int4-ov",
    re.fullmatch(r"sha256:[0-9a-f]{{64}}", campaign.get("text_digest", "")) is not None,
    re.fullmatch(r"sha256:[0-9a-f]{{64}}", campaign.get("image_digest", "")) is not None,
    re.fullmatch(r"[0-9a-f]{{40}}", campaign.get("image_revision", "")) is not None,
    campaign.get("smtp_message_id", "").startswith("<sph-"),
    token_payload.get("preferred_username") == "qa.intern",
    "ai_service_recipient" in token_payload.get("roles", []),
))
result = call(gateway + "/v1/evasion/supply-attempts", token=token, payload={{
    "challenge_id": challenge_id,
    "campaign_id": campaign["campaign_id"],
    "participant_interface": "python",
    "assistance_mode": "none",
}})
receipt_ok = False
if result.get("objective_status") == "passed":
    issued = call(proof + "/v1/receipts/" + flag_id, token=token, payload={{}})
    verified = call(
        proof + "/v1/receipts/" + flag_id + "/verify",
        token=token,
        payload={{"receipt": issued["receipt"]}},
    )
    receipt_ok = verified.get("valid") is True
passed = path_ok and result.get("objective_status") == "passed" and receipt_ok
marker({marker_id!r}, "PASS" if passed else "FAIL", int(passed))
'''


def participant_program() -> str:
    return _program(replay=False)


def replay_program() -> str:
    return _program(replay=True)


class Module02SpearphishLifecycle(ScopedReliabilityLifecycle):
    """Reset the persistent closure used by synthetic spearphish."""

    scoped_reset_unavailable = "module-02 spearphish scoped reset is unavailable"
    scoped_reset_failed = "module-02 spearphish scoped reset failed"
    scoped_assets = (
        "dataset-store-01",
        "idp-01",
        "image-generation-01",
        "inference-gateway",
        "mail-server-01",
        "telemetry-proof-01",
    )
    quiesce_assets = (
        "inference-gateway",
        "telemetry-proof-01",
        "image-generation-01",
        "mail-server-01",
        "idp-01",
        "dataset-store-01",
    )
    reset_assets = (
        "dataset-store-01",
        "idp-01",
        "mail-server-01",
        "image-generation-01",
        "telemetry-proof-01",
        "inference-gateway",
    )
    verify_assets = reset_assets


@dataclass(frozen=True)
class Module02SpearphishResult:
    passed: bool
    negative_count: int
    receipt_count: int
    replay_count: int


class Module02SpearphishSession(Protocol):
    def execute(
        self,
        program: str,
        *,
        expected_markers: int,
        return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


@dataclass
class Module02SpearphishRunner:
    lifecycle: Module02SpearphishLifecycle
    session: Module02SpearphishSession

    def run(self) -> Module02SpearphishResult:
        rows, _ = self.session.execute(
            participant_program(), expected_markers=3, return_clipboard=False
        )
        by_id = {row.check_id: row for row in rows}
        expected = {
            "test-m02-spearphish-controls",
            "test-m02-spearphish-negative",
            "test-m02-spearphish-path",
        }
        if set(by_id) != expected:
            raise RehearsalError("module-02 spearphish marker coverage is incomplete")
        self.lifecycle.reset_context_state()
        replay_rows, _ = self.session.execute(
            replay_program(), expected_markers=1, return_clipboard=False
        )
        if len(replay_rows) != 1:
            raise RehearsalError("module-02 spearphish replay marker is incomplete")
        controls = by_id["test-m02-spearphish-controls"]
        negative = by_id["test-m02-spearphish-negative"]
        path = by_id["test-m02-spearphish-path"]
        replay = replay_rows[0]
        passed = all(
            (
                controls.status == "PASS",
                controls.safe_count == 1,
                negative.status == "PASS",
                negative.safe_count == 1,
                path.status == "PASS",
                path.safe_count == 1,
                replay.check_id == "test-m02-spearphish-replay",
                replay.status == "PASS",
                replay.safe_count == 1,
            )
        )
        return Module02SpearphishResult(
            passed, negative.safe_count, path.safe_count, replay.safe_count
        )


def _write_report(
    path: Path, config: RunConfig, result: Module02SpearphishResult
) -> None:
    payload = {
        "schema_version": 1,
        "module": "module-02-model-evasion-synthetic-spearphish",
        "profile": "gcp_full",
        "range_instance": config.range_instance,
        "participant": config.participant,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PASS" if result.passed else "FAIL",
        "challenge_count": 1,
        "receipt_count": result.receipt_count,
        "representative_negative_count": result.negative_count,
        "reset_replay_count": result.replay_count,
        "assurance": "pre-playtest-one-pass",
        "reset_scope": "module-02-spearphish-state-closure",
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".module-02-spearphish-", dir=path.parent
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
    return parser


def main() -> int:
    config = RunConfig.from_namespace(build_parser().parse_args())
    if not config.use_existing_range or not config.retain_until_phase_e:
        raise RehearsalError(
            "module-02 spearphish proof requires a retained existing range"
        )
    lifecycle = Module02SpearphishLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=PACK_ROOT / "assets/content/credentials/participant-password.txt",
        timeout_seconds=1500,
    )
    result = Module02SpearphishRunner(lifecycle, session).run()
    _write_report(
        lifecycle.operator_root / "module-02-spearphish-smoke.json", config, result
    )
    print(f"module-02 spearphish smoke: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
