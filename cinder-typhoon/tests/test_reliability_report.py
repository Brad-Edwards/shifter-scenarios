"""Focused fail-closed tests for the single-participant reliability report."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build/reliability/validate.py"
SPEC = importlib.util.spec_from_file_location("cinder_reliability_validate", MODULE_PATH)
assert SPEC and SPEC.loader
reliability = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reliability
SPEC.loader.exec_module(reliability)

OBSERVER_PATH = ROOT / "build/reliability/observe.py"
OBSERVER_SPEC = importlib.util.spec_from_file_location(
    "cinder_reliability_observe", OBSERVER_PATH,
)
assert OBSERVER_SPEC and OBSERVER_SPEC.loader
observer = importlib.util.module_from_spec(OBSERVER_SPEC)
sys.modules[OBSERVER_SPEC.name] = observer
OBSERVER_SPEC.loader.exec_module(observer)


class ReliabilityReportTests(unittest.TestCase):
    DIGEST = "a" * 64

    def service_state(self, expected: int, one_shots: int) -> dict:
        return {
            "expected": expected,
            "running": expected - one_shots,
            "successful_one_shots": one_shots,
            "restarts": 0,
            "unhealthy": 0,
        }

    def valid_report(self) -> dict:
        candidate_path = ROOT / "build/participant-runner/candidate.json"
        release_path = ROOT / "build/release/manifest.json"
        threshold_path = ROOT / "build/reliability/thresholds.json"
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        thresholds = json.loads(threshold_path.read_text(encoding="utf-8"))
        defined_at = datetime.fromisoformat(
            thresholds["defined_at"].replace("Z", "+00:00")
        )
        started_at = defined_at + timedelta(seconds=1)
        finished_at = started_at + timedelta(hours=1)
        phases = {}
        for index, (phase, metadata) in enumerate(reliability.PHASES.items(), start=1):
            instance, machine_type, expected, one_shots = metadata
            services = self.service_state(expected, one_shots)
            surface_digest = f"{index:x}" * 64
            state_digest = f"{index + 3:x}" * 64
            phases[phase] = {
                "instance": instance,
                "machine_type": machine_type,
                "initial_startup_seconds": 80.0,
                "service_recovery": {
                    "elapsed_seconds": 40.0,
                    "services": deepcopy(services),
                    "retained_state": True,
                },
                "host_recovery": {
                    "elapsed_seconds": 100.0,
                    "services": deepcopy(services),
                    "retained_state": True,
                },
                "resets": [
                    {
                        "sequence": sequence,
                        "elapsed_seconds": 75.0,
                        "participant_surface_sha256": surface_digest,
                        "service_state_sha256": state_digest,
                        "services": deepcopy(services),
                    }
                    for sequence in (1, 2)
                ],
                "resources": {
                    "vcpus": 2 if phase == "training" else 4,
                    "load_1": 1.0,
                    "memory_available_mib": 1024,
                    "root_disk_available_mib": 4096,
                    "failed_system_units": 0,
                    "oom_events": 0,
                },
            }
        return {
            "schema_version": 1,
            "report_kind": "single-participant-reliability",
            "status": "passed",
            "candidate": {
                "candidate_id": candidate["candidate_id"],
                "source_commit": candidate["source_commit"],
                "candidate_manifest_sha256": reliability.digest_file(candidate_path),
                "release_manifest_sha256": reliability.digest_file(release_path),
            },
            "thresholds": {
                "path": "build/reliability/thresholds.json",
                "sha256": reliability.digest_file(threshold_path),
                "defined_at": thresholds["defined_at"],
            },
            "run": {
                "run_id": "issue-330-test",
                "project": "prod-mgau4w",
                "zone": "us-central1-a",
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
            },
            "campaign_path": {
                "transition": "diagnostic-execution",
                "training": {
                    "operation": "all", "result": "passed",
                    "elapsed_seconds": 10.0, "report_sha256": self.DIGEST,
                },
                "keplerops": {
                    "operation": "delivery-diagnostic", "result": "passed",
                    "elapsed_seconds": 20.0, "report_sha256": self.DIGEST,
                },
                "arwc": {
                    "operation": "ending", "result": "passed",
                    "elapsed_seconds": 30.0, "report_sha256": self.DIGEST,
                },
                "retained_state": True,
            },
            "phases": phases,
            "assertions": {name: True for name in sorted(reliability.ASSERTIONS)},
        }

    def test_complete_report_passes(self) -> None:
        report = self.valid_report()
        self.assertIs(reliability.validate_report(report), report)

    def test_schema_and_threshold_contracts_parse(self) -> None:
        schema = json.loads((ROOT / "build/reliability/report.schema.json").read_text())
        thresholds = json.loads((ROOT / "build/reliability/thresholds.json").read_text())
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(reliability.validate_thresholds(thresholds), thresholds)

    def test_pristine_surface_digest_binds_the_live_checked_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "build/participant-surface/manifests/training.json"
            contract.parent.mkdir(parents=True)
            contract.write_bytes(b'{"authored":"surface"}\n')
            passed = subprocess.CompletedProcess([], 0, "PASS\n", "")
            with (
                mock.patch.object(observer, "ROOT", root),
                mock.patch.object(observer, "run", return_value=passed) as checked,
            ):
                digest = observer.participant_surface("training", True)
        self.assertEqual(digest, hashlib.sha256(b'{"authored":"surface"}\n').hexdigest())
        self.assertEqual(checked.call_count, 1)
        self.assertNotIn("--snapshot", checked.call_args.args[0])

    def test_resource_observation_fails_when_host_evidence_cannot_be_read(self) -> None:
        succeeded = subprocess.CompletedProcess([], 0, "", "")
        failed = subprocess.CompletedProcess([], 1, "", "denied")
        command_results = {
            "failed units": [failed],
            "kernel log": [succeeded, failed],
        }
        for evidence, results in command_results.items():
            with self.subTest(evidence=evidence):
                with mock.patch.object(observer, "run", side_effect=results):
                    with self.assertRaises(observer.ObservationError):
                        observer.resource_state()

    def test_release_manifest_must_bind_the_report_candidate(self) -> None:
        report = self.valid_report()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                Path("build/participant-runner/candidate.json"),
                Path("build/release/manifest.json"),
                Path("build/reliability/thresholds.json"),
            )
            for relative in paths:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            release_path = root / "build/release/manifest.json"
            release = json.loads(release_path.read_text(encoding="utf-8"))
            release["candidate"]["sha256"] = "0" * 64
            release_path.write_text(json.dumps(release) + "\n", encoding="utf-8")
            report["candidate"]["release_manifest_sha256"] = reliability.digest_file(release_path)
            with self.assertRaisesRegex(reliability.ValidationError, "release candidate digest differs"):
                reliability.validate_report(report, root)

    def test_identity_timing_state_and_resource_mutations_fail(self) -> None:
        mutations = {
            "candidate digest": lambda value: value["candidate"].__setitem__("candidate_manifest_sha256", "0" * 64),
            "late thresholds": lambda value: value["run"].__setitem__("started_at", "2026-11-06T00:00:00Z"),
            "failed acceptance": lambda value: value["campaign_path"]["training"].__setitem__("result", "failed"),
            "lost campaign state": lambda value: value["campaign_path"].__setitem__("retained_state", False),
            "unexpected restart": lambda value: value["phases"]["training"]["service_recovery"]["services"].__setitem__("restarts", 1),
            "slow host recovery": lambda value: value["phases"]["training"]["host_recovery"].__setitem__("elapsed_seconds", 301),
            "lost recovery state": lambda value: value["phases"]["keplerops"]["host_recovery"].__setitem__("retained_state", False),
            "different reset surface": lambda value: value["phases"]["arwc"]["resets"][1].__setitem__("participant_surface_sha256", "f" * 64),
            "high load": lambda value: value["phases"]["training"]["resources"].__setitem__("load_1", 5.0),
            "low memory": lambda value: value["phases"]["keplerops"]["resources"].__setitem__("memory_available_mib", 255),
            "low disk": lambda value: value["phases"]["arwc"]["resources"].__setitem__("root_disk_available_mib", 2047),
            "failed unit": lambda value: value["phases"]["training"]["resources"].__setitem__("failed_system_units", 1),
            "OOM event": lambda value: value["phases"]["arwc"]["resources"].__setitem__("oom_events", 1),
            "credential text": lambda value: value["run"].__setitem__("run_id", "secret"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                report = self.valid_report()
                mutate(report)
                with self.assertRaises(reliability.ValidationError):
                    reliability.validate_report(report)


if __name__ == "__main__":
    unittest.main()
