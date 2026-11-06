"""Targeted fail-closed tests for the immutable release record."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build/release/manifest.py"
SPEC = importlib.util.spec_from_file_location("cinder_release_manifest", MODULE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


class ReleaseManifestTests(unittest.TestCase):
    DIGEST = "sha256:" + "a" * 64

    def synthetic_root(self, directory: str) -> Path:
        root = Path(directory)
        explicit_files = {
            "docs/design/challenge-dependencies.json",
            "docs/design/portfolio.csv",
            "assets/narrative/generated/packages/arwc-documents.json",
        }
        roots = set(release.COMMON_ROOTS)
        for phase in release.PHASES.values():
            roots.update(phase["roots"])
        for relative in sorted(roots):
            path = root / relative
            if relative in explicit_files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{relative}\n")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / "input.txt").write_text(f"{relative}\n")
        for phase in release.PHASES:
            paths = {
                f"build/participant-surface/manifests/{phase}.json",
                release.PHASES[phase]["compose"],
                release.PHASES[phase]["restore"],
                release.PHASES[phase]["suite"],
                "build/participant-runner/run.py",
                "build/participant-runner/candidate.schema.json",
                "build/participant-runner/report.schema.json",
            }
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{relative}\n")
        return root

    def records(self, root: Path, directory: str) -> tuple[Path, Path, dict, dict]:
        catalog = release._load_catalog_module()
        deployments = {}
        artifacts = {}
        for phase, configuration in release.PHASES.items():
            service = configuration["participant_service"]
            deployments[phase] = {
                "project": "prod-mgau4w",
                "zone": "us-central1-a",
                "instance": configuration["instance"],
                "participant_service": service,
                "participant_image_digest": self.DIGEST,
                "images": {service: self.DIGEST},
            }
            artifacts[f"{phase}/{service}"] = self.DIGEST
        candidate = {
            "schema_version": 3,
            "candidate_id": "event-test-01",
            "immutable": True,
            "source_commit": "b" * 40,
            "challenge_delivery": catalog.catalog_metadata(),
            "hint_delivery": catalog.hint_manifest_metadata(),
            "artifact_digests": artifacts,
            "deployments": deployments,
        }
        candidate_path = Path(directory) / "candidate.json"
        candidate_path.write_text(json.dumps(candidate, sort_keys=True))
        manifest = {
            "schema_version": 1,
            "release_id": candidate["candidate_id"],
            "source_commit": candidate["source_commit"],
            "candidate": {
                "path": "build/participant-runner/candidate.json",
                "candidate_id": candidate["candidate_id"],
                "sha256": release.file_digest(candidate_path),
            },
            "challenge_delivery": candidate["challenge_delivery"],
            "hint_delivery": candidate["hint_delivery"],
            "build_inputs": {
                phase: release.build_input_binding(phase, root)
                for phase in release.PHASES
            },
            "file_bindings": {
                phase: release.release_file_bindings(phase, root)
                for phase in release.PHASES
            },
            "deployments": deployments,
        }
        manifest_path = Path(directory) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True))
        return manifest_path, candidate_path, manifest, candidate

    def write_manifest(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, sort_keys=True))

    def test_release_binds_inputs_files_candidate_and_all_phases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.synthetic_root(directory)
            manifest_path, candidate_path, _, _ = self.records(root, directory)
            evidence = release.validate_release(
                manifest_path, candidate_path, "training", root,
            )
        self.assertEqual(evidence["release_id"], "event-test-01")
        self.assertRegex(evidence["manifest_sha256"], r"^[0-9a-f]{64}$")

    def test_arwc_transition_surface_contract_is_an_immutable_input(self) -> None:
        relative = Path("build/participant-surface/manifests/arwc-transitions.json")
        for phase in release.PHASES:
            with self.subTest(phase=phase):
                self.assertIn(relative, release.phase_files(phase, ROOT))

    def test_release_rejects_mutated_inputs_files_candidate_and_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.synthetic_root(directory)
            manifest_path, candidate_path, manifest, candidate = self.records(root, directory)
            mutations: list[tuple[str, dict]] = []

            stale_input = deepcopy(manifest)
            stale_input["build_inputs"]["training"]["sha256"] = "0" * 64
            mutations.append(("build inputs", stale_input))

            stale_surface = deepcopy(manifest)
            stale_surface["file_bindings"]["training"]["participant_surface"]["sha256"] = "0" * 64
            mutations.append(("release files", stale_surface))

            missing_phase = deepcopy(manifest)
            del missing_phase["build_inputs"]["arwc"]
            mutations.append(("every phase", missing_phase))

            for message, mutated in mutations:
                with self.subTest(mutation=message):
                    self.write_manifest(manifest_path, mutated)
                    with self.assertRaisesRegex(release.ManifestError, message):
                        release.validate_release(manifest_path, candidate_path, "training", root)

            self.write_manifest(manifest_path, manifest)
            candidate["candidate_id"] = "changed-candidate"
            candidate_path.write_text(json.dumps(candidate, sort_keys=True))
            with self.assertRaisesRegex(release.ManifestError, "candidate binding"):
                release.validate_release(manifest_path, candidate_path, "training", root)

            candidate["candidate_id"] = "event-test-01"
            candidate["deployments"]["training"]["instance"] = "wrong-instance"
            candidate_path.write_text(json.dumps(candidate, sort_keys=True))
            changed = deepcopy(manifest)
            changed["candidate"]["sha256"] = release.file_digest(candidate_path)
            changed["deployments"] = candidate["deployments"]
            self.write_manifest(manifest_path, changed)
            with self.assertRaisesRegex(release.ManifestError, "deployment identity"):
                release.validate_release(manifest_path, candidate_path, "training", root)

    def test_image_observation_is_complete_and_rejects_missing_images(self) -> None:
        configured = subprocess.CompletedProcess(
            [], 0,
            stdout=json.dumps({"services": {
                "participant": {"image": "participant:test"},
                "support": {"image": "support:test"},
            }}),
            stderr="",
        )
        inspected = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(self.DIGEST), stderr="",
        )
        with mock.patch.object(
            release.subprocess, "run", side_effect=[configured, inspected, inspected],
        ):
            self.assertEqual(
                release.observe_images("training"),
                {"participant": self.DIGEST, "support": self.DIGEST},
            )

        missing = subprocess.CompletedProcess([], 1, stdout="", stderr="not found")
        with mock.patch.object(
            release.subprocess, "run", side_effect=[configured, inspected, missing],
        ):
            with self.assertRaisesRegex(release.ManifestError, "image is not present"):
                release.observe_images("training")

    def test_dirty_release_input_cannot_be_promoted(self) -> None:
        with mock.patch.object(
            release, "_git", side_effect=["a" * 40, " M cinder-typhoon/build/training/compose.yaml"],
        ):
            with self.assertRaisesRegex(release.ManifestError, "dirty"):
                release.clean_source_commit()

    def test_generation_stops_before_gcp_when_card_coverage_is_stale(self) -> None:
        with (
            mock.patch.object(release, "clean_source_commit", return_value="a" * 40),
            mock.patch.object(
                release,
                "require_complete_card_coverage",
                side_effect=release.ManifestError("complete card-coverage gate failed"),
            ),
            mock.patch.object(release, "_remote_observation") as remote_observation,
        ):
            with self.assertRaisesRegex(release.ManifestError, "card-coverage"):
                release.generate("event-test-01", "prod-mgau4w", "us-central1-a")
        remote_observation.assert_not_called()

    def test_card_coverage_preflight_reports_gate_failure(self) -> None:
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="stale registry")
        with mock.patch.object(release.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(release.ManifestError, "stale registry"):
                release.require_complete_card_coverage()

    def test_cross_segment_trust_requires_exact_public_ca_pairs(self) -> None:
        keplerops_ca = "a" * 64
        arwc_ca = "b" * 64
        with mock.patch.object(
            release, "_remote_public_file_digest",
            side_effect=[keplerops_ca, keplerops_ca, arwc_ca, arwc_ca],
        ) as observe:
            release.require_cross_segment_trust("prod-mgau4w", "us-central1-a")
        self.assertEqual(observe.call_count, 4)

        with mock.patch.object(
            release, "_remote_public_file_digest",
            side_effect=[keplerops_ca, arwc_ca],
        ):
            with self.assertRaisesRegex(release.ManifestError, "kepler-arwc/deploy.sh"):
                release.require_cross_segment_trust("prod-mgau4w", "us-central1-a")

    def test_cross_segment_trust_rejects_unreadable_public_ca(self) -> None:
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="not found")
        with mock.patch.object(release.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(release.ManifestError, "kepler-arwc/deploy.sh"):
                release._remote_public_file_digest(
                    "cinder-keplerops-golden", "prod-mgau4w", "us-central1-a",
                    "/public/ca.crt",
                )


if __name__ == "__main__":
    unittest.main()
