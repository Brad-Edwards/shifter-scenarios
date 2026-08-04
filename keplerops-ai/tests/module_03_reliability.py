#!/usr/bin/env python3
"""Measure module-03 reliability through the participant Kasm surface."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from live_rehearsal import (
    CommandLifecycle,
    PlaywrightKasmSession,
    RehearsalError,
    RunConfig,
    add_retained_reset_arguments,
    initial_participant_program,
    retained_reset_before_run,
)
from module_03_rehearsal import CONTENTS


PACK_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PACK_ROOT / "build"
CHALLENGES = tuple(f"kep-m03-{suffix}" for suffix in "abcdef")
DETERMINISTIC = CHALLENGES[:2]
MODEL_SENSITIVE = CHALLENGES[2:]
CHECKPOINT_SCHEMA_VERSION = 1
INVALID_CHECKPOINT = "module-03 reliability checkpoint is invalid"
SCOPED_RESET_UNAVAILABLE = "module-03 scoped reset is unavailable"


def _wilson(successes: int, trials: int) -> tuple[float, float]:
    path = PACK_ROOT / "assets/services/keplerops-runtime/agent_control.py"
    spec = importlib.util.spec_from_file_location("keplerops_context_reliability", path)
    if spec is None or spec.loader is None:
        raise RehearsalError("reliability domain unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.wilson_interval(successes, trials)


def participant_program(challenge_ids: tuple[str, ...], trials: int) -> str:
    if (
        challenge_ids not in {DETERMINISTIC, MODEL_SENSITIVE}
        or not isinstance(trials, int)
        or isinstance(trials, bool)
        or challenge_ids == DETERMINISTIC
        and trials != 1
        or challenge_ids == MODEL_SENSITIVE
        and trials != 30
    ):
        raise RehearsalError("reliability participant program is invalid")
    prefix = initial_participant_program().split("challenges =", 1)[0]
    encoded_ids = json.dumps(challenge_ids, separators=(",", ":"))
    encoded_contents = json.dumps(CONTENTS, separators=(",", ":"))
    model_sensitive = challenge_ids == MODEL_SENSITIVE
    return prefix + f'''gateway = "https://inference-gateway.keplerops.lab"
challenge_ids = {encoded_ids}
contents = {encoded_contents}
created = call(gateway + "/v1/context/documents", token=token, payload={{
    "title": "Orbital Lantern approval bulletin",
    "claimed_authority": "release-board",
    "content": contents["initial"],
    "words_per_chunk": 32,
    "overlap_words": 4,
    "participant_interface": "python",
    "assistance_mode": "none",
}}, expected=201)
document_id = created["document_id"]
call(gateway + "/v1/context/search", token=token, payload={{
    "query": "orbital-lantern release policy and deployment status",
    "top_k": 5,
}})
if {model_sensitive!r}:
    for prerequisite in ("kep-m03-a", "kep-m03-b"):
        result = call(gateway + "/v1/context/attempt", token=token, payload={{
            "challenge_id": prerequisite,
            "participant_interface": "python",
            "assistance_mode": "none",
        }})
        if result.get("objective_status") != "passed":
            raise RuntimeError("context prerequisite failed")
for challenge_id in challenge_ids:
    if challenge_id in contents:
        call(gateway + "/v1/context/reindex", token=token, payload={{
            "document_id": document_id,
            "content": contents[challenge_id],
            "participant_interface": "python",
            "assistance_mode": "none",
        }})
    successes = 0
    for _ in range({trials}):
        result = call(gateway + "/v1/context/attempt", token=token, payload={{
            "challenge_id": challenge_id,
            "participant_interface": "python",
            "assistance_mode": "none",
        }})
        successes += result.get("objective_status") == "passed"
    threshold = {trials} if challenge_id in {json.dumps(DETERMINISTIC)} else 27
    marker("test-context-reliability-" + challenge_id[-1], "PASS" if successes >= threshold else "FAIL", successes)
'''


@dataclass(frozen=True)
class ReliabilityResult:
    challenge_id: str
    successes: int
    trials: int
    required_successes: int
    interval_low: float
    interval_high: float

    @property
    def passed(self) -> bool:
        return self.successes >= self.required_successes


class ReliabilitySession(Protocol):
    def execute(
        self,
        program: str,
        *,
        expected_markers: int,
        return_clipboard: bool,
    ) -> tuple[tuple[Any, ...], str]: ...


class ReliabilityLifecycle(Protocol):
    def health(self) -> None: ...
    def reset(self) -> None: ...
    def reset_context_state(self) -> None: ...


class ScopedReliabilityLifecycle(CommandLifecycle):
    """Reset one declared asset closure without cycling the full range."""

    scoped_reset_unavailable = SCOPED_RESET_UNAVAILABLE
    scoped_reset_failed = "module-03 scoped reset failed"
    scoped_assets = ("dataset-store-01", "inference-gateway")
    quiesce_assets = ("inference-gateway", "dataset-store-01")
    reset_assets = ("dataset-store-01", "inference-gateway")
    verify_assets = reset_assets

    def reset_context_state(self) -> None:
        terraform = shutil.which("terraform")
        gcloud = shutil.which("gcloud")
        state = self.operator_root / "terraform.tfstate"
        if (
            terraform is None
            or gcloud is None
            or not state.is_file()
            or state.is_symlink()
        ):
            raise RehearsalError(self.scoped_reset_unavailable)
        output = self.invoke(
            [
                terraform,
                f"-chdir={self.build_root / 'gcp'}",
                "output",
                f"-state={state}",
                "-json",
                "asset_inventory",
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if output.returncode or not isinstance(output.stdout, str):
            raise RehearsalError(self.scoped_reset_unavailable)
        try:
            inventory = json.loads(output.stdout)
            carrier = inventory.get("range-control-carrier-01", {})
            carrier_name = carrier.get("name")
            instances = {}
            workload_assets = set()
            for asset in self.scoped_assets:
                if asset in inventory:
                    instances[asset] = inventory[asset]["name"]
                elif isinstance(carrier_name, str):
                    instances[asset] = carrier_name
                    workload_assets.add(asset)
                else:
                    raise KeyError(asset)
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise RehearsalError(self.scoped_reset_unavailable) from error
        if any(
            not isinstance(instance, str)
            or not instance
            or len(instance) > 63
            or instance[0] not in "abcdefghijklmnopqrstuvwxyz"
            or instance[-1] not in "abcdefghijklmnopqrstuvwxyz0123456789"
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                for character in instance
            )
            for instance in instances.values()
        ):
            raise RehearsalError(self.scoped_reset_unavailable)
        generation = self.reset_generation()
        def command_for(asset: str, script: str, *arguments: object) -> str:
            if asset in workload_assets:
                action = {
                    "quiesce-local": "quiesce",
                    "reset-local": "reset",
                    "reset-verify-local": "reset-verify",
                }[script]
                suffix = "".join(f" {argument}" for argument in arguments)
                return (
                    "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload "
                    f"{action} {asset}{suffix}"
                )
            else:
                path = f"/var/lib/keplerops/{script}"
                prefix = ""
            suffix = "".join(f" {argument}" for argument in arguments)
            return f"sudo {prefix}bash {path}{suffix}"

        commands = (
            *((asset, command_for(asset, "quiesce-local"))
              for asset in self.quiesce_assets),
            *((asset, command_for(asset, "reset-local", generation))
              for asset in self.reset_assets),
            *((asset, command_for(asset, "reset-verify-local"))
              for asset in self.verify_assets),
        )
        expected_assets = set(self.scoped_assets)
        if not expected_assets or any(
            set(ordered_assets) != expected_assets
            for ordered_assets in (
                self.quiesce_assets, self.reset_assets, self.verify_assets
            )
        ):
            raise RehearsalError(self.scoped_reset_unavailable)
        for asset, command in commands:
            result = self.invoke(
                [
                    gcloud,
                    "compute",
                    "ssh",
                    instances[asset],
                    "--project",
                    self.config.project_id,
                    "--zone",
                    self.config.zone,
                    "--tunnel-through-iap",
                    "--quiet",
                    "--command",
                    command,
                ],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode:
                raise RehearsalError(self.scoped_reset_failed)


class ContextReliabilityLifecycle(ScopedReliabilityLifecycle):
    """Reset the minimal dataset/gateway dependency closure between samples."""


@dataclass(frozen=True)
class ReliabilityProgress:
    deterministic_rounds: int
    counts: dict[str, int]
    model_sensitive_complete: bool


@dataclass(frozen=True)
class ReliabilityCheckpoint:
    path: Path
    binding: str
    challenges: tuple[str, ...] = CHALLENGES
    deterministic: tuple[str, ...] = DETERMINISTIC
    deterministic_rounds: int = 10
    model_trials: int = 30
    invalid_checkpoint: str = INVALID_CHECKPOINT
    temporary_prefix: str = ".module-03-checkpoint-"

    def _validate(self, payload: object) -> ReliabilityProgress:
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "binding",
            "deterministic_rounds",
            "counts",
            "model_sensitive_complete",
        }:
            raise RehearsalError(self.invalid_checkpoint)
        rounds = payload["deterministic_rounds"]
        counts = payload["counts"]
        model_complete = payload["model_sensitive_complete"]
        if (
            payload["schema_version"] != CHECKPOINT_SCHEMA_VERSION
            or payload["binding"] != self.binding
            or not isinstance(rounds, int)
            or isinstance(rounds, bool)
            or not 0 <= rounds <= self.deterministic_rounds
            or not isinstance(counts, dict)
            or set(counts) != set(self.challenges)
            or not isinstance(model_complete, bool)
            or model_complete
            and rounds != self.deterministic_rounds
        ):
            raise RehearsalError(self.invalid_checkpoint)
        for challenge_id, successes in counts.items():
            limit = (
                rounds
                if challenge_id in self.deterministic
                else self.model_trials if model_complete else 0
            )
            if (
                not isinstance(successes, int)
                or isinstance(successes, bool)
                or not 0 <= successes <= limit
            ):
                raise RehearsalError(self.invalid_checkpoint)
        return ReliabilityProgress(rounds, dict(counts), model_complete)

    def load(self) -> ReliabilityProgress:
        if not self.path.exists():
            return ReliabilityProgress(
                0, {challenge_id: 0 for challenge_id in self.challenges}, False
            )
        try:
            metadata = self.path.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or not 1 <= metadata.st_size <= 16_384
            ):
                raise RehearsalError(self.invalid_checkpoint)
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RehearsalError(self.invalid_checkpoint) from error
        return self._validate(payload)

    def write(self, progress: ReliabilityProgress) -> None:
        validated = self._validate({
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "binding": self.binding,
            "deterministic_rounds": progress.deterministic_rounds,
            "counts": progress.counts,
            "model_sensitive_complete": progress.model_sensitive_complete,
        })
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=self.temporary_prefix, dir=self.path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": CHECKPOINT_SCHEMA_VERSION,
                    "binding": self.binding,
                    "deterministic_rounds": validated.deterministic_rounds,
                    "counts": validated.counts,
                    "model_sensitive_complete": validated.model_sensitive_complete,
                }, handle, separators=(",", ":"), sort_keys=True)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


@dataclass
class ReliabilityRunner:
    lifecycle: ReliabilityLifecycle
    session: ReliabilitySession
    checkpoint: ReliabilityCheckpoint | None = None
    challenges: tuple[str, ...] = CHALLENGES
    deterministic: tuple[str, ...] = DETERMINISTIC
    model_sensitive: tuple[str, ...] = MODEL_SENSITIVE
    deterministic_rounds: int = 10
    model_trials: int = 30
    model_required: int = 27
    program_builder: Callable[[tuple[str, ...], int], str] = participant_program
    marker_prefix: str = "test-context-reliability-"
    challenge_prefix: str = "kep-m03-"

    def prepare(self, *, canonical_reset: bool = True) -> ReliabilityProgress:
        progress = (
            self.checkpoint.load()
            if self.checkpoint is not None
            else ReliabilityProgress(
                0, {challenge_id: 0 for challenge_id in self.challenges}, False
            )
        )
        if progress.deterministic_rounds == 0 and canonical_reset:
            self.lifecycle.reset()
        elif progress.deterministic_rounds == 0:
            self.lifecycle.reset_context_state()
        else:
            self.lifecycle.reset_context_state()
            self.lifecycle.health()
        return progress

    def _execute(
        self, challenge_ids: tuple[str, ...], trials: int
    ) -> dict[str, int]:
        rows, _ = self.session.execute(
            self.program_builder(challenge_ids, trials),
            expected_markers=len(challenge_ids),
            return_clipboard=False,
        )
        counts = {
            f"{self.challenge_prefix}{row.check_id[-1]}": row.safe_count
            for row in rows
            if row.check_id.startswith(self.marker_prefix)
        }
        if set(counts) != set(challenge_ids):
            raise RehearsalError("reliability marker coverage is incomplete")
        return counts

    def run(
        self, progress: ReliabilityProgress | None = None
    ) -> tuple[ReliabilityResult, ...]:
        if progress is None:
            progress = self.prepare()
        counts = progress.counts
        rounds = progress.deterministic_rounds
        while rounds < self.deterministic_rounds:
            round_counts = self._execute(self.deterministic, 1)
            for challenge_id, successes in round_counts.items():
                counts[challenge_id] += successes
            rounds += 1
            if self.checkpoint is not None:
                self.checkpoint.write(ReliabilityProgress(rounds, counts, False))
            if rounds < self.deterministic_rounds:
                self.lifecycle.reset_context_state()
        if not progress.model_sensitive_complete:
            self.lifecycle.reset_context_state()
            counts.update(self._execute(self.model_sensitive, self.model_trials))
            if self.checkpoint is not None:
                self.checkpoint.write(ReliabilityProgress(
                    self.deterministic_rounds, counts, True
                ))
        results = []
        for challenge_id in self.challenges:
            trials = (
                self.deterministic_rounds
                if challenge_id in self.deterministic
                else self.model_trials
            )
            required = (
                trials if challenge_id in self.deterministic else self.model_required
            )
            low, high = _wilson(counts[challenge_id], trials)
            results.append(ReliabilityResult(
                challenge_id=challenge_id,
                successes=counts[challenge_id],
                trials=trials,
                required_successes=required,
                interval_low=low,
                interval_high=high,
            ))
        return tuple(results)


def _write_report(
    path: Path,
    config: RunConfig,
    results: tuple[ReliabilityResult, ...],
    *,
    module: str = "module-03-context-poisoning",
    temporary_prefix: str = ".module-03-",
) -> None:
    payload = {
        "schema_version": 1,
        "module": module,
        "profile": "gcp_full",
        "range_instance": config.range_instance,
        "participant": config.participant,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PASS" if all(row.passed for row in results) else "FAIL",
        "results": [
            {
                "challenge_id": row.challenge_id,
                "successes": row.successes,
                "trials": row.trials,
                "required_successes": row.required_successes,
                "wilson_95_low": round(row.interval_low, 6),
                "wilson_95_high": round(row.interval_high, 6),
                "status": "PASS" if row.passed else "FAIL",
            }
            for row in results
        ],
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=temporary_prefix, dir=path.parent
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
    add_retained_reset_arguments(parser)
    return parser


def _checkpoint_binding(config: RunConfig, lifecycle: CommandLifecycle) -> str:
    digest = hashlib.sha256()
    digest.update(config.range_instance.encode("ascii"))
    digest.update(b"\0")
    digest.update(config.participant.encode("ascii"))
    for path in (
        Path(__file__).resolve(),
        Path(__file__).with_name("live_rehearsal.py").resolve(),
        Path(__file__).with_name("module_03_rehearsal.py").resolve(),
        PACK_ROOT / "assets/services/keplerops-runtime/agent_control.py",
        PACK_ROOT / "assets/services/keplerops-runtime/app.py",
        PACK_ROOT / "assets/services/keplerops-runtime/context_poisoning.py",
        BUILD_ROOT / "reset.sh",
        BUILD_ROOT / "health-check.sh",
        BUILD_ROOT / "gcp/lifecycle.py",
        lifecycle.operator_root / "terraform.tfstate",
    ):
        try:
            content = path.read_bytes()
        except OSError as error:
            raise RehearsalError(
                "module-03 reliability checkpoint binding is unavailable"
            ) from error
        digest.update(b"\0")
        digest.update(str(path.relative_to(PACK_ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def main() -> int:
    args = build_parser().parse_args()
    config = RunConfig.from_namespace(args)
    if not config.use_existing_range or not config.retain_until_phase_e:
        raise RehearsalError("reliability runs require a retained existing range")
    lifecycle = ContextReliabilityLifecycle(BUILD_ROOT, config)
    session = PlaywrightKasmSession(
        endpoint=lifecycle.terraform_output("participant_endpoint"),
        ca_file=lifecycle.operator_root / "secrets/ca.crt",
        password_file=lifecycle.participant_password_file(PACK_ROOT),
        timeout_seconds=1200,
    )
    checkpoint = ReliabilityCheckpoint(
        lifecycle.operator_root / "module-03-reliability.checkpoint.json",
        _checkpoint_binding(config, lifecycle),
    )
    runner = ReliabilityRunner(lifecycle, session, checkpoint)
    progress = runner.prepare(
        canonical_reset=retained_reset_before_run(args, "module-03 reliability")
    )
    with session:
        results = runner.run(progress)
    destination = lifecycle.operator_root / "module-03-reliability.json"
    _write_report(destination, config, results)
    checkpoint.clear()
    passed = all(row.passed for row in results)
    print(f"module-03 reliability: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
