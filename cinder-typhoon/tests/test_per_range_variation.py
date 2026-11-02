"""Regression gates for per-range KeplerOps credential provisioning."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
KEPLER = ROOT / "build" / "keplerops"
SEED_SCRIPT = KEPLER / "provision-seed.py"
RUNTIME = KEPLER / "runtime"
COMPOSE = KEPLER / "compose.yaml"
THREE_RANGE_CHECK = KEPLER / "check-three-range-isolation-gcp.sh"
IMAGES = KEPLER / "images"
OPENING = ROOT / "assets" / "keplerops" / "opening"
REGISTRY = ROOT / "assets" / "keplerops" / "registry"
FORBIDDEN_FIXED_VALUES = {
    "kpl_rowan_7X4mQ9vN2cL6",
    "ksess_rowan_2841_6Hs8Qp3V",
    "ksess_talia_review_9Kw4Pn7R",
    "fkpub_arwc_stable_4Zt8Qm2Nc7",
    "fkci_registry_reader_8Hd3Lp6Ws1",
    "release-admin-session-5m",
    "release-reader-handle",
    "workload-oidc-wrong-aud",
    "workload-session",
    "support-export-role",
    "history-recovery-session",
    "ci-maintenance-worker",
    "maintenance-runtime",
    "staff-preview-service",
    "cert-enrollment-worker",
    "assistant-tool-session",
    "indexer-worker-lease",
    "registry-customer-channel",
}


def load_seed_module():
    spec = importlib.util.spec_from_file_location("provision_seed", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def provision(seed: bytes, output: Path) -> subprocess.CompletedProcess[str]:
    seed_file = output.parent / f"{output.name}.seed"
    seed_file.write_bytes(seed)
    os.chmod(seed_file, 0o600)
    return subprocess.run(
        [
            sys.executable,
            str(SEED_SCRIPT),
            "--seed-file",
            str(seed_file),
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class SeedVariationTests(unittest.TestCase):
    def test_three_seeds_vary_every_replayable_credential_class(self) -> None:
        module = load_seed_module()
        generated: list[dict[str, str]] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(3):
                output = root / f"range-{index}"
                result = provision(bytes([index + 1]) * 32, output)
                self.assertEqual(result.returncode, 0, result.stderr)
                document = json.loads((output / "runtime-credentials.json").read_text())
                self.assertEqual(document["schema"], module.SCHEMA)
                self.assertEqual(set(document["credentials"]), set(module.PURPOSES))
                self.assertTrue(all(len(value) >= 32 for value in document["credentials"].values()))
                generated.append(document["credentials"])
            for name in module.PURPOSES:
                with self.subTest(credential=name):
                    self.assertEqual(len({item[name] for item in generated}), 3)

    def test_generation_writes_only_non_secret_metadata_and_quiet_output(self) -> None:
        seed = b"range-secret-never-recorded-0001!"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "range"
            result = provision(seed, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            runtime = json.loads((output / "runtime-credentials.json").read_text())
            metadata_text = (output / "metadata.json").read_text()
            metadata = json.loads(metadata_text)
            self.assertEqual(metadata["schema"], "fieldkest.range-credential-metadata/v1")
            self.assertNotIn("seed", metadata)
            self.assertNotIn(seed.decode(), metadata_text + result.stdout + result.stderr)
            for value in runtime["credentials"].values():
                self.assertNotIn(value, metadata_text + result.stdout + result.stderr)
            self.assertFalse((output / "seed-manifest.json").exists())

    def test_participant_artifacts_contain_only_intended_earned_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "range"
            result = provision(b"participant-artifact-seed-value!", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            credentials = json.loads((output / "runtime-credentials.json").read_text())["credentials"]
            git = (output / "participant" / "git-credentials").read_text()
            self.assertIn(credentials["developer_token"], git)
            self.assertEqual(sum(value in git for value in credentials.values()), 1)
            with sqlite3.connect(output / "participant" / "chromium-Cookies") as database:
                rows = database.execute(
                    "SELECT host_key, name, value FROM cookies"
                ).fetchall()
            self.assertEqual(
                rows,
                [("support.keplerops.test", "fieldkest_support", credentials["support_rowan_session"])],
            )

    def test_generator_is_one_shot_and_refuses_partial_output(self) -> None:
        script = (KEPLER / "generate-operator-material.sh").read_text()
        provisioner = SEED_SCRIPT.read_text()
        self.assertEqual(script.count('python3 "$ROOT/provision-seed.py"'), 1)
        self.assertIn('[[ ! -s "$RANGE_SEED_DIR/metadata.json" ]]', script)
        self.assertIn("refusing to overwrite", script)
        self.assertNotIn('add_argument("--seed"', provisioner)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "range"
            first = provision(b"one-shot-range-seed-material-000001", output)
            second = provision(b"different-range-seed-material-0002", output)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)

    def test_runtime_loader_fails_closed_for_missing_or_invalid_config(self) -> None:
        helper = RUNTIME / "credentials.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, content in (("missing.json", None), ("invalid.json", "{}\n")):
                path = root / name
                if content is not None:
                    path.write_text(content)
                result = subprocess.run(
                    [sys.executable, str(helper)],
                    env={**os.environ, "FIELDKEST_CREDENTIALS_FILE": str(path)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                with self.subTest(case=name):
                    self.assertNotEqual(result.returncode, 0)

    def test_no_fixed_accepted_credentials_remain_in_runtime_or_image_inputs(self) -> None:
        roots = [RUNTIME, IMAGES, KEPLER / "config"]
        checked: list[Path] = []
        for root in roots:
            for path in root.rglob("*"):
                if path.is_file():
                    checked.append(path)
                    text = path.read_text(errors="ignore")
                    for value in FORBIDDEN_FIXED_VALUES:
                        self.assertNotIn(value, text, f"fixed credential remains in {path}")
        self.assertTrue(checked)

    def test_baked_archives_do_not_contain_fixed_credentials(self) -> None:
        archives = sorted(OPENING.glob("*.tar")) + sorted(REGISTRY.glob("*.tar"))
        self.assertTrue(archives)
        for archive_path in archives:
            with self.subTest(archive=archive_path.name), tarfile.open(archive_path) as archive:
                names = set(archive.getnames())
                if archive_path.name == "k-dev-home.tar":
                    self.assertNotIn(".config/git/credentials", names)
                    self.assertNotIn(".config/chromium/Default/Cookies", names)
                for member in archive.getmembers():
                    if not member.isfile():
                        continue
                    source = archive.extractfile(member)
                    assert source is not None
                    payload = source.read()
                    for value in FORBIDDEN_FIXED_VALUES:
                        self.assertNotIn(value.encode(), payload, f"{value} remains in {archive_path}:{member.name}")

    def test_participant_container_never_mounts_operator_credentials_or_metadata(self) -> None:
        compose = COMPOSE.read_text()
        participant = compose.split("\n  k-dev:\n", 1)[1].split("\n  k-source:\n", 1)[0]
        self.assertNotIn("runtime-credentials", participant)
        self.assertNotIn("metadata.json", participant)
        self.assertNotIn("seed-manifest", participant)
        seeder = compose.split("\n  k-dev-seed:\n", 1)[1].split("\n  k-dev:\n", 1)[0]
        self.assertIn("participant/git-credentials", seeder)
        self.assertIn("participant/chromium-Cookies", seeder)
        self.assertNotIn("runtime-credentials", seeder)
        self.assertNotIn("metadata.json", seeder)

    def test_audit_sources_do_not_record_presented_bearers(self) -> None:
        for path in RUNTIME.glob("*.py"):
            source = path.read_text()
            with self.subTest(runtime=path.name):
                self.assertNotIn("principal=token", source)
                self.assertNotIn('"principal": token', source)

        verifier = (KEPLER / "verify-range-isolation.py").read_text()
        self.assertIn('transit_response.get("error") != "diagnostic_binding_denied"', verifier)
        self.assertIn("paired carrier transit failed", verifier)

    def test_gcp_range_copies_bind_services_to_each_copied_host(self) -> None:
        campaign = THREE_RANGE_CHECK.read_text()
        self.assertIn("arwc_ip=$(gcloud compute instances describe", campaign)
        self.assertIn("printf 'ARWC_CARRIER_ADDRESS=%s\\n' '$arwc_ip'", campaign)
        self.assertIn("cinder-keplerops-carrier,no-address", campaign)
        self.assertIn("cinder-arwc-carrier,no-address", campaign)
        self.assertIn("stage=configure-pair-firewalls", campaign)
        self.assertIn('--source-ranges "$kepler_ip/32"', campaign)
        self.assertIn('--target-tags "cinder-$label-pair-', campaign)
        self.assertIn('firewall-rules delete "${firewall_rules[@]}"', campaign)
        self.assertIn("wait_acceptance_all delivery-package", campaign)
        self.assertIn("wait_acceptance_all delivery-diagnostic", campaign)
        self.assertIn("last_test_method", campaign)


if __name__ == "__main__":
    unittest.main()
