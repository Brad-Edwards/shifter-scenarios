#!/usr/bin/env python3
"""Prove Module 10 full-ATLAS expansion through participant Kasm."""

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
)
from module_10_full_atlas_programs import (
    CHALLENGES,
    NEGATIVE_COUNT,
    PREREQUISITE_COUNT,
    participant_programs,
)


PACK_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PACK_ROOT / "build"


@dataclass(frozen=True)
class Module10FullAtlasResult:
    passed: bool
    receipt_count: int
    negative_count: int
    prerequisite_count: int


class Module10FullAtlasSession(Protocol):
    def __enter__(self) -> "Module10FullAtlasSession": ...
    def __exit__(self, type_: object, value: object, traceback: object) -> None: ...
    def execute(
        self, program: str, *, expected_markers: int, return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


@dataclass
class Module10FullAtlasRunner:
    lifecycle: CommandLifecycle
    session: Module10FullAtlasSession

    def run(self) -> Module10FullAtlasResult:
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
                        f"module-10 full-ATLAS {phase} phase failed: {error}"
                    ) from error
                for row in rows:
                    if row.check_id in observed:
                        raise RehearsalError("module-10 full-ATLAS marker is duplicated")
                    observed[row.check_id] = row
        expected = {
            "test-m10-fa-controls": NEGATIVE_COUNT,
            "test-m10-fa-prereqs": PREREQUISITE_COUNT,
            "test-m10-fa-cost": 3,
            "test-m10-fa-harms": 5,
            "test-m10-fa-destroy": 2,
            "test-m10-fa-awards": len(CHALLENGES),
        }
        if set(observed) != set(expected):
            raise RehearsalError("module-10 full-ATLAS marker coverage is incomplete")
        passed = all(
            observed[check_id].status == "PASS"
            and observed[check_id].safe_count == count
            for check_id, count in expected.items()
        )
        return Module10FullAtlasResult(
            passed=passed,
            receipt_count=observed["test-m10-fa-awards"].safe_count,
            negative_count=observed["test-m10-fa-controls"].safe_count,
            prerequisite_count=observed["test-m10-fa-prereqs"].safe_count,
        )


def _phase_names() -> tuple[str, ...]:
    return ("controls", "prerequisites", "service-cost", "harms", "destruction", "awards")


def _write_report(path: Path, config: RunConfig, result: Module10FullAtlasResult) -> None:
    payload = {
        "schema_version": 1,
        "module": "module-10-ai-capstone-full-atlas-expansion",
        "profile": "gcp_full",
        "range_instance": config.range_instance,
        "participant": config.participant,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PASS" if result.passed else "FAIL",
        "challenge_count": len(CHALLENGES),
        "receipt_count": result.receipt_count,
        "representative_negative_count": result.negative_count,
        "prerequisite_count": result.prerequisite_count,
        "assurance": "pre-playtest-one-pass",
        "reset_scope": "prepared-prerequisite-generation",
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".module-10-full-atlas-", dir=path.parent
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
    parser.add_argument(
        "--prepared-prerequisites",
        action="store_true",
        help="require prepared Modules 05, 07, and 10 prerequisite evidence",
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
            "module-10 full-ATLAS proof requires a retained range with prepared prerequisites"
        )
    lifecycle = CommandLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=PACK_ROOT / "assets/content/credentials/participant-password.txt",
        timeout_seconds=3600,
    )
    result = Module10FullAtlasRunner(lifecycle, session).run()
    _write_report(
        lifecycle.operator_root / "module-10-full-atlas-smoke.json",
        config,
        result,
    )
    print(f"module-10 full-ATLAS smoke: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
