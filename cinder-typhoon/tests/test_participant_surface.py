from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import grp
import re
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "build" / "participant-surface"
sys.path.insert(0, str(SURFACE))

from compare import compare  # noqa: E402
from observe import observe  # noqa: E402
from run import observation_plan  # noqa: E402
from validate import ManifestError, load, validate  # noqa: E402


PHASES = ("training", "keplerops", "arwc")


def manifest(phase: str) -> dict:
    return load(SURFACE / "manifests" / f"{phase}.json")


class AuthoredManifestTests(unittest.TestCase):
    def test_all_authored_manifests_are_strict_and_complete(self) -> None:
        for phase in PHASES:
            with self.subTest(phase=phase):
                value = manifest(phase)
                self.assertEqual(value["phase"], phase)
                self.assertTrue(value["filesystem"]["roots"])
                self.assertTrue(any(root["entries"] for root in value["filesystem"]["roots"]))
                for root in value["filesystem"]["roots"]:
                    self.assertEqual(
                        len(root["entries"]),
                        len({entry["path"] for entry in root["entries"]}),
                    )
                    self.assertTrue(all(entry["classification"] for entry in root["entries"]))

    def test_machine_readable_schemas_are_valid_json(self) -> None:
        for name in ("authored.schema.json", "observed.schema.json"):
            with self.subTest(schema=name):
                value = json.loads((SURFACE / "schema" / name).read_text())
                self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("$id", value)

    def test_every_dns_name_has_the_reviewed_listener_probe_universe(self) -> None:
        for phase in PHASES:
            with self.subTest(phase=phase):
                value = manifest(phase)
                names = {item["name"] for item in value["network"]["dns"]}
                listeners = value["network"]["listeners"]
                ports = {item["port"] for item in listeners}
                for name in names:
                    self.assertEqual(
                        {item["port"] for item in listeners if item["host"] == name},
                        ports,
                    )

    def test_disclosures_are_visible_inventory_entries(self) -> None:
        for phase in PHASES:
            with self.subTest(phase=phase):
                value = manifest(phase)
                visible = {
                    f"{root['path'].rstrip('/')}/{entry['path']}"
                    for root in value["filesystem"]["roots"]
                    for entry in root["entries"]
                }
                for disclosure in value["disclosures"]:
                    # Client-reference disclosures use HTTP URLs, not filesystem paths.
                    if disclosure["path"].startswith("https://"):
                        continue
                    self.assertIn(disclosure["path"], visible)

    def test_training_briefing_tracks_authored_source(self) -> None:
        source = (ROOT / "assets" / "training" / "workstation" / "TRAINING.md").read_bytes()
        entry = next(
            item
            for item in manifest("training")["filesystem"]["roots"][0]["entries"]
            if item["path"] == "TRAINING.md"
        )
        self.assertEqual(entry["size"], len(source))
        self.assertEqual(entry["sha256"], hashlib.sha256(source).hexdigest())

    def test_keplerops_client_reference_graph_is_present(self) -> None:
        client_documents = ROOT / "build" / "keplerops" / "runtime" / "client_documents.json"
        inventory = json.loads(client_documents.read_text())
        all_route_keys = {
            route["key"]
            for doc in inventory["documents"].values()
            for route in doc.get("routes", [])
        }
        disclosures = manifest("keplerops")["disclosures"]
        # No exhaustive catalog disclosure is allowed.
        self.assertFalse(
            any(d["id"] == "keplerops-service-catalog" for d in disclosures),
            "exhaustive route catalog disclosure must be absent",
        )
        # No service-catalog.md in the filesystem entries.
        entries = manifest("keplerops")["filesystem"]["roots"][0]["entries"]
        self.assertFalse(
            any(e.get("path") == "work/service-catalog.md" for e in entries),
            "service-catalog.md must not appear in participant filesystem",
        )
        # All route keys from client_documents.json appear in client-reference disclosures.
        client_ref_disclosures = [d for d in disclosures if d["kind"] == "client-reference"]
        self.assertTrue(client_ref_disclosures, "no client-reference disclosures found")
        exposed = {key for d in client_ref_disclosures for key in d["exposes"]}
        self.assertEqual(exposed, all_route_keys,
                         "client-reference disclosures must expose exactly the routes in client_documents.json")

    def test_external_cards_and_absent_hints_are_explicit(self) -> None:
        prefixes = {"training": "T", "keplerops": "K", "arwc": "W"}
        challenge_root = ROOT / "docs" / "design" / "challenges"
        for phase, prefix in prefixes.items():
            with self.subTest(phase=phase):
                delivery = manifest(phase)["delivery"]
                expected = {
                    path.stem
                    for path in challenge_root.glob(f"{prefix}*/*.md")
                    if re.fullmatch(rf"{prefix}\d+\.\d+", path.stem)
                }
                self.assertEqual(delivery["cards"]["status"], "external_unverified")
                self.assertEqual(set(delivery["cards"]["items"]), expected)
                self.assertEqual(delivery["hints"], {"status": "not_materialized", "items": []})

    def test_operator_surface_is_not_copied_by_any_image(self) -> None:
        for dockerfile in (ROOT / "build").glob("**/*.Dockerfile"):
            with self.subTest(dockerfile=dockerfile.relative_to(ROOT)):
                self.assertNotIn("build/participant-surface", dockerfile.read_text())

    def test_participant_receives_only_a_reduced_probe_plan(self) -> None:
        plan = observation_plan(manifest("keplerops"))
        serialized = json.dumps(plan)
        self.assertNotIn("disclosures", plan)
        self.assertNotIn("delivery", plan)
        self.assertNotIn("classification", serialized)
        self.assertNotIn("sha256", serialized)
        self.assertNotIn("FIELDKEST-SENTNL", serialized)
        self.assertNotIn("K04.1", serialized)

    def test_private_runtime_and_service_state_are_explicitly_inaccessible(self) -> None:
        expected = {
            "training": {
                "/opt/operator-tests": (False, False),
                "/var/run/docker.sock": (False, False),
            },
            "keplerops": {
                "/opt/fieldkest-seeds": (False, False),
                "/opt/fieldkest-workbench": (True, False),
                "/usr/local/bin/fieldkest-k-dev-entrypoint": (True, False),
                "/var/lib/fieldkest-workbench/audit": (False, False),
            },
            "arwc": {
                "/opt/customer-handover": (True, False),
                "/opt/customer-handover/customer_handover.py": (True, False),
                "/opt/fieldlink-connector/fieldlink_consumer.py": (False, False),
                "/var/lib/arwc-connector": (True, False),
                "/run/arwc-tls/server.key": (True, False),
                "/tmp/arwc-server.key": (True, False),
            },
        }
        for phase, paths in expected.items():
            with self.subTest(phase=phase):
                forbidden = {
                    item["path"]: (item["visible"], item["readable"])
                    for item in manifest(phase)["filesystem"]["forbidden_paths"]
                }
                for path, visibility in paths.items():
                    self.assertEqual(forbidden.get(path), visibility)

    def test_validation_rejects_unclassified_or_extra_fields(self) -> None:
        value = manifest("training")
        broken = copy.deepcopy(value)
        del broken["filesystem"]["roots"][0]["entries"][0]["classification"]
        with self.assertRaises(ManifestError):
            validate(broken)
        broken = copy.deepcopy(value)
        broken["participant"]["operator"] = True
        with self.assertRaises(ManifestError):
            validate(broken)


class ObservationTests(unittest.TestCase):
    def synthetic_authored(self, root: Path) -> dict:
        account = pwd.getpwuid(os.geteuid())
        group = grp.getgrgid(os.getegid()).gr_name
        content = b"participant material\n"
        return {
            "schema_version": 1,
            "manifest_kind": "authored",
            "phase": "training",
            "state": "unit-test",
            "participant": {
                "user": account.pw_name,
                "uid": os.geteuid(),
                "group": group,
                "gid": os.getegid(),
                "groups": sorted({grp.getgrgid(value).gr_name for value in os.getgroups()}),
                "home": account.pw_dir,
                "workdir": os.getcwd(),
            },
            "filesystem": {
                "roots": [{
                    "path": root.as_posix(),
                    "opaque": [],
                    "entries": [{
                        "path": "briefing.md",
                        "type": "file",
                        "mode": "0644",
                        "owner": account.pw_name,
                        "group": group,
                        "classification": "starting-briefing",
                        "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }],
                }],
                "forbidden_paths": [{
                    "path": (root / "operator-only").as_posix(),
                    "visible": False,
                    "readable": False,
                }],
            },
            "tools": [{"name": "python3", "path": sys.executable}],
            "network": {"dns": [], "listeners": []},
            "disclosures": [],
            "delivery": {
                "cards": {"status": "external_unverified", "items": []},
                "hints": {"status": "not_materialized", "items": []},
            },
        }

    @unittest.skipIf(os.geteuid() == 0, "observer intentionally refuses root")
    def test_observer_and_comparator_detect_exact_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "briefing.md").write_bytes(b"participant material\n")
            (root / "briefing.md").chmod(0o644)
            authored = self.synthetic_authored(root)
            validate(authored)
            observed = observe(observation_plan(authored))
            # The unit process may itself be in the host Docker group. Live
            # checks require the container observation to report this false.
            observed["security"]["docker_socket_readable"] = False
            validate(observed)
            self.assertEqual(compare(authored, observed), [])
            self.assertNotIn("participant material", json.dumps(observed))

            malformed = copy.deepcopy(observed)
            malformed["security"]["sudo_available"] = False
            with self.assertRaises(ManifestError):
                validate(malformed)

            unexpected_root = copy.deepcopy(observed)
            unexpected_root["filesystem"]["roots"].append({
                "path": "/unexpected",
                "entries": [],
                "errors": [],
            })
            self.assertTrue(any(
                "unexpected filesystem root observation" in item
                for item in compare(authored, unexpected_root)
            ))

            (root / "unexpected.txt").write_text("not authored\n")
            observed = observe(observation_plan(authored))
            failures = compare(authored, observed)
            self.assertTrue(any("unexpected entry unexpected.txt" in item for item in failures))

    @unittest.skipIf(os.geteuid() == 0, "observer intentionally refuses root")
    def test_comparator_detects_readable_operator_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "briefing.md").write_bytes(b"participant material\n")
            (root / "briefing.md").chmod(0o644)
            authored = self.synthetic_authored(root)
            operator = root / "operator-only"
            operator.write_text("private\n")
            observed = observe(observation_plan(authored))
            failures = compare(authored, observed)
            self.assertTrue(any("forbidden path" in item and "visible" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
