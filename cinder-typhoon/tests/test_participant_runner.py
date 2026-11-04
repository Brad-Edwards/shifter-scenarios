from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

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
        self.assertIn("test_k30_backup_recovery", diagnostic)
        self.assertIn("test_k31_maintenance", diagnostic)
        self.assertIn("test_k29_release_lineage", package)
        self.assertIn("test_k29b_connector_delivery", package)
        self.assertNotIn("test_k29a_diagnostic_delivery", package)
        self.assertIn("test_k30_backup_recovery", package)
        self.assertIn("test_k31_maintenance", package)
        self.assertEqual(set(diagnostic) | set(package), set(values["all"]))
        self.assertIn("test_k29a_diagnostic_delivery", values["all"])
        self.assertIn("test_k29b_connector_delivery", values["all"])


class BoundaryTests(unittest.TestCase):
    AUTHENTICATION_KEY = "/run/arwc-handover/authentication.key"
    APPROVED_ARWC_MOUNTS = frozenset({
        "/var/lib/fieldlink-connector",
        "/var/lib/arwc-connector",
        "/run/arwc-tls/server.crt",
        "/run/arwc-tls/server.key",
        "/run/arwc-tls/ca.crt",
        "/run/arwc-peer/keplerops-ca.crt",
        AUTHENTICATION_KEY,
    })

    def arwc_compose_mounts(self) -> frozenset[str]:
        compose = yaml.safe_load((ROOT / "build/arwc/compose.yaml").read_text())
        volumes = compose["services"]["a-connector"]["volumes"]
        destinations = set()
        for volume in volumes:
            self.assertIsInstance(volume, str)
            parts = volume.rsplit(":", 2)
            destination = parts[-2] if parts[-1] in {"ro", "rw"} else parts[-1]
            self.assertTrue(destination.startswith("/"))
            destinations.add(destination)
        return frozenset(destinations)

    def assert_arwc_mount_contract(
        self, runner_mounts: frozenset[str], compose_mounts: frozenset[str],
    ) -> None:
        self.assertEqual(self.APPROVED_ARWC_MOUNTS, runner_mounts)
        self.assertEqual(self.APPROVED_ARWC_MOUNTS, compose_mounts)

    def arwc_inspect_responses(
        self, *, extra_mount: str | None = None,
    ) -> list[subprocess.CompletedProcess[str]]:
        mounts = [
            {
                "Destination": destination,
                "Type": "volume" if destination.startswith("/var/lib/") else "bind",
                "RW": destination.startswith("/var/lib/"),
                "Source": (
                    "/operator/private/handover.key"
                    if destination == self.AUTHENTICATION_KEY
                    else f"/source{destination}"
                ),
                "KeyBytes": "SENSITIVE-AUTHENTICATION-KEY",
                "KeySHA256": "f" * 64,
            }
            for destination in self.APPROVED_ARWC_MOUNTS
        ]
        if extra_mount:
            mounts.append({
                "Destination": extra_mount, "Type": "bind", "RW": False,
                "Source": "/operator/private/unapproved",
            })
        values = [
            {
                "cinder-arwc-corporate": {},
                "cinder-arwc-maintenance": {},
            },
            mounts,
            "sha256:" + "a" * 64,
        ]
        return [
            subprocess.CompletedProcess([], 0, stdout=json.dumps(value), stderr="")
            for value in values
        ]

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
        self.assertIn(self.AUTHENTICATION_KEY, runner.PHASES["arwc"].forbidden_paths)
        self.assertIn("/tmp/arwc-handover.key", runner.PHASES["arwc"].forbidden_paths)

    def test_arwc_runner_and_compose_share_the_approved_mount_contract(self) -> None:
        runner_mounts = runner.PHASES["arwc"].allowed_mounts
        compose_mounts = self.arwc_compose_mounts()
        self.assert_arwc_mount_contract(runner_mounts, compose_mounts)

        mutations = (
            (runner_mounts - {self.AUTHENTICATION_KEY}, compose_mounts),
            (runner_mounts, compose_mounts - {self.AUTHENTICATION_KEY}),
            (
                runner_mounts | {"/run/arwc-unapproved/material"},
                compose_mounts | {"/run/arwc-unapproved/material"},
            ),
        )
        for mutated_runner, mutated_compose in mutations:
            with self.subTest(
                runner_mounts=mutated_runner, compose_mounts=mutated_compose,
            ):
                with self.assertRaises(AssertionError):
                    self.assert_arwc_mount_contract(mutated_runner, mutated_compose)

    def test_arwc_mount_inspection_is_fail_closed_and_sanitized(self) -> None:
        phase = runner.PHASES["arwc"]
        with mock.patch.object(
            runner.subprocess, "run", side_effect=self.arwc_inspect_responses(),
        ):
            result = runner.inspect_container(phase)

        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("/operator/private", serialized)
        self.assertNotIn("SENSITIVE-AUTHENTICATION-KEY", serialized)
        self.assertNotIn("f" * 64, serialized)
        authentication_mount = next(
            mount for mount in result["mounts"]
            if mount["destination"] == self.AUTHENTICATION_KEY
        )
        self.assertEqual(
            {"destination", "type", "read_write"}, set(authentication_mount),
        )
        self.assertFalse(authentication_mount["read_write"])

        with mock.patch.object(
            runner.subprocess, "run",
            side_effect=self.arwc_inspect_responses(
                extra_mount="/run/arwc-unapproved/material",
            ),
        ):
            with self.assertRaisesRegex(runner.RunnerError, "participant mount destinations"):
                runner.inspect_container(phase)

    def test_paired_development_launcher_builds_before_reset(self) -> None:
        launcher = (
            ROOT / "build/participant-runner/check-development-pair.sh"
        ).read_text()
        self.assertLess(
            launcher.index("stage=keplerops-build"),
            launcher.index("stage=keplerops-reset"),
        )
        self.assertLess(
            launcher.index("stage=keplerops-acceptance"),
            launcher.index("stage=arwc-transition"),
        )
        verifier = (
            ROOT / "build/participant-runner/verify-arwc-transition.py"
        ).read_text()
        self.assertIn("delivery_route", verifier)
        self.assertIn("delivery_receipt", verifier)
        self.assertIn('"SEED"', verifier)


class DevelopmentPairSyncTests(unittest.TestCase):
    MANIFEST = ROOT / "build/participant-runner/development-pair-sync-paths.txt"

    def sync_roots(self) -> tuple[Path, ...]:
        return tuple(Path(line) for line in self.MANIFEST.read_text().splitlines())

    def catalog_inputs(self) -> set[Path]:
        catalog = runner.delivery_catalog
        return {
            Path(catalog.__file__),
            catalog.CATALOG_PATH,
            catalog.HINT_MANIFEST,
            catalog.HINT_REVIEWS,
            catalog.HINT_PLAYTEST_SCHEMA,
            *catalog.source_paths(),
        }

    def uncovered_catalog_inputs(self, roots: tuple[Path, ...]) -> set[Path]:
        missing = set()
        for source in self.catalog_inputs():
            relative = source.relative_to(ROOT)
            if not any(relative == root or root in relative.parents for root in roots):
                missing.add(relative)
        return missing

    def test_manifest_is_safe_complete_and_consumed_by_launcher(self) -> None:
        raw_lines = self.MANIFEST.read_text().splitlines()
        roots = self.sync_roots()
        self.assertTrue(raw_lines)
        self.assertEqual(len(raw_lines), len(set(raw_lines)))
        for raw, root in zip(raw_lines, roots):
            with self.subTest(root=raw):
                self.assertEqual(raw, root.as_posix())
                self.assertFalse(root.is_absolute())
                self.assertNotIn(".", root.parts)
                self.assertNotIn("..", root.parts)
                self.assertTrue((ROOT / root).exists())
        self.assertEqual(set(), self.uncovered_catalog_inputs(roots))

        launcher = (
            ROOT / "build/participant-runner/check-development-pair.sh"
        ).read_text()
        self.assertIn("development-pair-sync-paths.txt", launcher)
        self.assertIn('git -C "$pack_root" ls-files -z -- "${sync_roots[@]}"', launcher)
        self.assertIn('--null --files-from="$sync_file_list"', launcher)

    def test_catalog_metadata_validates_from_only_declared_inputs(self) -> None:
        roots = self.sync_roots()
        inputs = self.catalog_inputs()
        self.assertEqual(set(), self.uncovered_catalog_inputs(roots))
        with tempfile.TemporaryDirectory() as directory:
            isolated_root = Path(directory)
            for source in inputs:
                destination = isolated_root / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            isolated_catalog_path = isolated_root / "challenges/catalog.py"
            spec = importlib.util.spec_from_file_location(
                "isolated_cinder_delivery_catalog", isolated_catalog_path,
            )
            assert spec and spec.loader
            isolated_catalog = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(isolated_catalog)
            self.assertEqual(
                runner.delivery_catalog.catalog_metadata(),
                isolated_catalog.catalog_metadata(),
            )
            self.assertEqual(
                runner.delivery_catalog.hint_manifest_metadata(),
                isolated_catalog.hint_manifest_metadata(),
            )

    def test_required_catalog_inputs_fail_closed_under_manifest_mutations(self) -> None:
        roots = self.sync_roots()
        for removed in (
            Path("challenges/catalog.py"),
            Path("docs/design/challenges"),
        ):
            with self.subTest(removed=removed):
                mutated = tuple(root for root in roots if root != removed)
                self.assertNotEqual(roots, mutated)
                with self.assertRaises(AssertionError):
                    self.assertEqual(set(), self.uncovered_catalog_inputs(mutated))


class CandidateTests(unittest.TestCase):
    def candidate(self) -> dict:
        digest = "sha256:" + "b" * 64
        return {
            "schema_version": 3,
            "candidate_id": "event-2026.10.30-01",
            "immutable": True,
            "source_commit": "a" * 40,
            "challenge_delivery": runner.delivery_catalog.catalog_metadata(),
            "hint_delivery": runner.delivery_catalog.hint_manifest_metadata(),
            "artifact_digests": {
                "training/participant": digest,
                "keplerops/k-dev": digest,
                "arwc/a-connector": digest,
            },
            "deployments": {
                "training": {
                    "project": "project-1", "zone": "zone-1", "instance": "training-1",
                    "participant_service": "participant", "participant_image_digest": digest,
                    "images": {"participant": digest},
                },
                "keplerops": {
                    "project": "project-1", "zone": "zone-1", "instance": "kepler-1",
                    "participant_service": "k-dev", "participant_image_digest": digest,
                    "images": {"k-dev": digest},
                },
                "arwc": {
                    "project": "project-1", "zone": "zone-1", "instance": "arwc-1",
                    "participant_service": "a-connector", "participant_image_digest": digest,
                    "images": {"a-connector": digest},
                },
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
        self.assertEqual(result["challenge_delivery"], runner.delivery_catalog.catalog_metadata())
        self.assertEqual(result["hint_delivery"], runner.delivery_catalog.hint_manifest_metadata())

    def test_candidate_rejects_mutability_missing_digest_and_extra_fields(self) -> None:
        mutations = []
        mutable = self.candidate(); mutable["immutable"] = False; mutations.append(mutable)
        no_digest = self.candidate(); no_digest["artifact_digests"] = {}; mutations.append(no_digest)
        extra = self.candidate(); extra["operator_token"] = "not-allowed"; mutations.append(extra)
        stale = self.candidate(); stale["challenge_delivery"]["sha256"] = "0" * 64; mutations.append(stale)
        stale_hints = self.candidate(); stale_hints["hint_delivery"]["sha256"] = "0" * 64; mutations.append(stale_hints)
        zero = self.candidate(); zero["artifact_digests"]["training/participant"] = "sha256:" + "0" * 64; mutations.append(zero)
        missing_phase = self.candidate(); del missing_phase["deployments"]["arwc"]; mutations.append(missing_phase)
        missing_image = self.candidate(); missing_image["deployments"]["arwc"]["images"] = {}; mutations.append(missing_image)
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


class CommittedCandidateTests(unittest.TestCase):
    CANDIDATE_PATH = ROOT / "build" / "participant-runner" / "candidate.json"
    SCHEMA_PATH = ROOT / "build" / "participant-runner" / "candidate.schema.json"

    def test_committed_candidate_has_required_fields(self) -> None:
        doc = json.loads(self.CANDIDATE_PATH.read_text())
        for field in ("schema_version", "candidate_id", "immutable",
                      "source_commit", "challenge_delivery", "hint_delivery",
                      "artifact_digests", "deployments"):
            self.assertIn(field, doc, f"candidate.json missing required field: {field}")
        self.assertEqual(doc["schema_version"], 3)
        self.assertIsInstance(doc["candidate_id"], str)
        self.assertIsInstance(doc["immutable"], bool)
        self.assertRegex(doc["source_commit"], r"^[0-9a-f]{40}$")
        self.assertIsInstance(doc["artifact_digests"], dict)
        self.assertTrue(doc["artifact_digests"])
        self.assertEqual(doc["challenge_delivery"], runner.delivery_catalog.catalog_metadata())
        self.assertEqual(doc["hint_delivery"], runner.delivery_catalog.hint_manifest_metadata())
        for phase in ("training", "keplerops", "arwc"):
            self.assertIn(phase, doc["deployments"],
                          f"candidate.json missing deployment: {phase}")

    def test_committed_candidate_is_not_immutable_without_real_digests(self) -> None:
        doc = json.loads(self.CANDIDATE_PATH.read_text())
        placeholder = "sha256:" + "0" * 64
        has_placeholders = any(
            v == placeholder for v in doc.get("artifact_digests", {}).values()
        )
        if has_placeholders:
            self.assertFalse(doc.get("immutable"),
                             "candidate.json is marked immutable but contains placeholder digests")

    def test_committed_candidate_source_commit_is_reachable(self) -> None:
        doc = json.loads(self.CANDIDATE_PATH.read_text())
        commit = doc.get("source_commit", "")
        result = subprocess.run(
            ["git", "cat-file", "-e", commit],
            cwd=ROOT, capture_output=True,
        )
        self.assertEqual(result.returncode, 0,
                         f"candidate source_commit {commit[:12]} not in git history")


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
        release = json.loads((ROOT / "build/release/manifest.schema.json").read_text())
        self.assertEqual(release["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("$id", release)

    def test_candidate_wrapper_requires_coverage_and_provenance_before_acceptance(self) -> None:
        source = (
            ROOT / "build" / "participant-runner" / "check-candidate.sh"
        ).read_text()
        hints = source.index("hint-delivery/release.py verify")
        coverage = source.index("card-coverage/coverage.py")
        provenance = source.index("input-provenance/provenance.py")
        fourth_wall = source.index("fourth-wall/run.py")
        fourth_wall_after = source.rindex("fourth-wall/run.py")
        surface = source.index("participant-surface/run.py")
        release = source.index("build/release/manifest.py verify")
        acceptance = source.index("participant-runner/run.py")
        self.assertLess(hints, coverage)
        self.assertLess(coverage, provenance)
        self.assertLess(provenance, fourth_wall)
        self.assertLess(fourth_wall, surface)
        self.assertLess(surface, release)
        self.assertLess(release, acceptance)
        self.assertIn("--release-manifest", source)
        self.assertIn("hint-delivery/release.py verify --phase '$phase'", source)
        self.assertIn("input-provenance/provenance.py --phase '$phase'", source)
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

    def test_enrichment_failure_preserves_the_participant_result(self) -> None:
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
            "skips_allowed": False,
            "completion_evidence": {
                "passed_subtests": [], "failed_subtests": [], "skipped_assertions": [],
            },
        }
        completed = subprocess.CompletedProcess(
            [], 0,
            stdout=runner.RESULT_PREFIX + json.dumps(boundary) + "\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            arguments = [
                "run.py", "--phase", "training", "--operation", "t01",
                "--development", "--reset-identity", "test-reset-002",
                "--report", str(report),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "inspect_container", return_value={}),
                mock.patch.object(runner.subprocess, "run", return_value=completed),
                mock.patch.object(
                    runner, "attach_runtime_provenance",
                    side_effect=runner.ProvenanceError("selected-phase enrichment failed"),
                ),
            ):
                exit_code = runner.main()
            value = json.loads(report.read_text())
        self.assertEqual(exit_code, 1)
        self.assertEqual(value["result"], "failed")
        self.assertEqual(value["boundary"], boundary)
        self.assertEqual(value["evidence"]["event_count"], 0)
        self.assertNotIn("provenance", value["evidence"])
        self.assertEqual(value["failure"], "selected-phase enrichment failed")


if __name__ == "__main__":
    unittest.main()
