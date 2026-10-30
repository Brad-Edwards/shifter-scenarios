from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "build" / "participant-runner" / "run.py"
SPEC = importlib.util.spec_from_file_location("cinder_participant_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class OperationTests(unittest.TestCase):
    def test_every_selected_assertion_exists_in_the_authored_suite(self) -> None:
        for phase in runner.PHASES:
            with self.subTest(phase=phase):
                authored = set(runner.suite_methods(phase))
                self.assertTrue(authored)
                for selected in runner.operations(phase).values():
                    self.assertTrue(selected)
                    self.assertLessEqual(set(selected), authored)

    def test_training_and_arwc_operations_close_over_prerequisites(self) -> None:
        training = runner.operations("training")
        self.assertEqual(len(training["t01"]), 1)
        self.assertEqual(training["t04"], training["all"])
        arwc = runner.operations("arwc")
        self.assertEqual(len(arwc["w01"]), 1)
        self.assertEqual(arwc["w35"], arwc["all"])
        self.assertEqual(arwc["ending"], arwc["all"])

    def test_keplerops_delivery_routes_are_independently_selectable(self) -> None:
        values = runner.operations("keplerops")
        diagnostic = values["delivery-diagnostic"]
        package = values["delivery-package"]
        self.assertIn("test_k29a_diagnostic_delivery", diagnostic)
        self.assertNotIn("test_k29b_connector_delivery", diagnostic)
        self.assertNotIn("test_k29_release_lineage", diagnostic)
        self.assertIn("test_k29_release_lineage", package)
        self.assertIn("test_k29b_connector_delivery", package)
        self.assertNotIn("test_k29a_diagnostic_delivery", package)
        self.assertIn("test_k29a_diagnostic_delivery", values["all"])
        self.assertIn("test_k29b_connector_delivery", values["all"])


class BoundaryTests(unittest.TestCase):
    def test_launcher_adds_no_mount_or_operator_path(self) -> None:
        for phase in runner.PHASES:
            with self.subTest(phase=phase):
                selected = runner.operations(phase)["all"]
                command = runner.launch_command(
                    phase, selected, cross_segment=phase == "keplerops",
                    expected_transition="package-activation" if phase == "arwc" else None,
                )
                self.assertEqual(command[:3], ["docker", "exec", "-i"])
                self.assertNotIn("--volume", command)
                self.assertNotIn("-v", command)
                self.assertNotIn("/var/run/docker.sock", command)
                self.assertNotIn(str(ROOT), command)
                self.assertEqual(command[command.index("--user") + 1], runner.PHASES[phase].user)
                self.assertEqual(command[command.index("--workdir") + 1], runner.PHASES[phase].home)

    def test_in_boundary_bootstrap_blocks_operator_control(self) -> None:
        source = runner.BOUNDARY_BOOTSTRAP
        compile(source, "<boundary-bootstrap>", "exec")
        for value in ("docker", "podman", "sudo", "nsenter", "runc"):
            self.assertIn(value, source)
        for value in ("CapEff", "NoNewPrivs", "/opt/operator-tests", "/var/run/docker.sock"):
            self.assertIn(value, source)
        self.assertIn("completion_evidence", source)
        self.assertIn('configuration["allow_skips"]', source)

    def test_all_service_state_paths_are_checked_as_unreadable(self) -> None:
        self.assertIn("/var/lib/cinder-workbench", runner.PHASES["training"].forbidden_paths)
        self.assertIn("/var/lib/fieldkest-ci", runner.PHASES["keplerops"].forbidden_paths)
        self.assertIn("/var/lib/arwc-connector", runner.PHASES["arwc"].forbidden_paths)


class CandidateTests(unittest.TestCase):
    def candidate(self) -> dict:
        return {
            "schema_version": 1,
            "candidate_id": "event-2026.10.30-01",
            "immutable": True,
            "source_commit": "a" * 40,
            "artifact_digests": {"training-image": "sha256:" + "b" * 64},
            "deployments": {
                "training": {"project": "project-1", "zone": "zone-1", "instance": "training-1", "participant_image_digest": "sha256:" + "b" * 64},
                "keplerops": {"project": "project-1", "zone": "zone-1", "instance": "kepler-1", "participant_image_digest": "sha256:" + "b" * 64},
                "arwc": {"project": "project-1", "zone": "zone-1", "instance": "arwc-1", "participant_image_digest": "sha256:" + "b" * 64},
            },
        }

    def write(self, directory: str, value: dict) -> Path:
        path = Path(directory) / "candidate.json"
        path.write_text(json.dumps(value))
        return path

    def test_candidate_is_bound_to_manifest_digest_and_deployments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = runner.validate_candidate(
                self.write(directory, self.candidate()), "keplerops", True,
            )
        self.assertTrue(result["immutable"])
        self.assertRegex(result["manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(set(result["deployments"]), {"training", "keplerops", "arwc"})

    def test_candidate_rejects_mutability_missing_digest_and_extra_fields(self) -> None:
        mutations = []
        mutable = self.candidate(); mutable["immutable"] = False; mutations.append(mutable)
        no_digest = self.candidate(); no_digest["artifact_digests"] = {}; mutations.append(no_digest)
        extra = self.candidate(); extra["operator_token"] = "not-allowed"; mutations.append(extra)
        for value in mutations:
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaises(runner.RunnerError):
                        runner.validate_candidate(self.write(directory, value), "training", False)

    def test_runtime_must_match_candidate_host_and_participant_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = runner.validate_candidate(
                self.write(directory, self.candidate()), "training", False,
            )
        host = {"project": "project-1", "zone": "zone-1", "instance": "training-1"}
        container = {"participant_image_digest": "sha256:" + "b" * 64}
        runner.verify_candidate_runtime(candidate, "training", host, container)
        changed = dict(host); changed["instance"] = "wrong-instance"
        with self.assertRaises(runner.RunnerError):
            runner.verify_candidate_runtime(candidate, "training", changed, container)
        with self.assertRaises(runner.RunnerError):
            runner.verify_candidate_runtime(
                candidate, "training", host,
                {"participant_image_digest": "sha256:" + "c" * 64},
            )


class EvidenceTests(unittest.TestCase):
    def test_evidence_events_accept_hashes_but_reject_bodies(self) -> None:
        event = {
            "kind": "http", "method": "GET", "host": "service.test", "path_sha256": "d" * 64,
            "status": 200, "response_bytes": 14, "response_sha256": "c" * 64,
            "elapsed_ms": 9, "test_method": "test_01_first_contact",
        }
        self.assertEqual(runner.validated_event(event), event)
        event["response_body"] = "reusable-secret"
        with self.assertRaises(runner.RunnerError):
            runner.validated_event(event)

    def test_boundary_result_rejects_unknown_fields(self) -> None:
        boundary = {
            "status": "passed",
            "identity": {
                "user": "cinder", "uid": 2000, "gid": 2000,
                "groups": ["cinder"], "home": "/home/cinder", "workdir": "/home/cinder",
            },
            "controls": {
                "effective_capabilities": 0, "no_new_privileges": True,
                "docker_socket_visible": False, "docker_socket_readable": False,
                "operator_paths_visible": [], "private_paths_readable": [],
                "suspicious_environment_names": [],
            },
            "transition": None, "violations": [], "tests_run": 1,
            "failures": 0, "errors": 0, "skipped": 0,
        }
        self.assertEqual(runner.validated_boundary(boundary), boundary)
        boundary["response_body"] = "must-not-enter-report"
        with self.assertRaises(runner.RunnerError):
            runner.validated_boundary(boundary)

    def test_suites_emit_credential_free_trace_shapes(self) -> None:
        for phase in runner.PHASES:
            source = runner.PHASES[phase].suite.read_text()
            self.assertIn("CINDER_ACCEPTANCE_EVENT", source)
            self.assertNotIn("test_w08_live", source)
            self.assertNotIn("test_w31_live", source)

    def test_machine_readable_schemas_are_present(self) -> None:
        schema_root = ROOT / "build" / "participant-runner"
        for name in ("candidate.schema.json", "report.schema.json"):
            value = json.loads((schema_root / name).read_text())
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("$id", value)

    def test_candidate_wrapper_requires_coverage_and_provenance_before_acceptance(self) -> None:
        source = (
            ROOT / "build" / "participant-runner" / "check-candidate.sh"
        ).read_text()
        coverage = source.index("card-coverage/coverage.py")
        provenance = source.index("input-provenance/provenance.py")
        fourth_wall = source.index("fourth-wall/run.py")
        fourth_wall_after = source.rindex("fourth-wall/run.py")
        surface = source.index("participant-surface/run.py")
        acceptance = source.index("participant-runner/run.py")
        self.assertLess(coverage, provenance)
        self.assertLess(provenance, fourth_wall)
        self.assertLess(fourth_wall, surface)
        self.assertLess(surface, acceptance)
        self.assertLess(acceptance, fourth_wall_after)
        self.assertEqual(source.count("fourth-wall/run.py"), 2)

    def test_invalid_candidate_still_writes_sanitized_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps({"operator_token": "must-not-be-logged"}))
            report = root / "report.json"
            completed = subprocess.run(
                [
                    sys.executable, str(RUNNER_PATH), "--phase", "training",
                    "--operation", "all", "--candidate", str(candidate),
                    "--reset-identity", "test-reset-001", "--report", str(report),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            value = json.loads(report.read_text())
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(value["result"], "failed")
        serialized = json.dumps(value) + completed.stdout + completed.stderr
        self.assertNotIn("must-not-be-logged", serialized)
        self.assertNotIn("stdout_raw", serialized)
        self.assertNotIn("stderr_raw", serialized)


if __name__ == "__main__":
    unittest.main()
