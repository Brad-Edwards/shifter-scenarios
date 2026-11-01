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
sys.path.insert(0, str(ROOT / "challenges"))

from compare import compare  # noqa: E402
import catalog as delivery_catalog  # noqa: E402
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
        training = manifest("training")
        entry = next(
            item
            for item in training["filesystem"]["roots"][0]["entries"]
            if item["path"] == "TRAINING.md"
        )
        self.assertEqual(entry["size"], len(source))
        self.assertEqual(entry["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(entry["owner"], training["participant"]["user"])
        self.assertNotEqual(int(entry["mode"], 8) & 0o444, 0)
        disclosure = next(
            item for item in training["disclosures"]
            if item["id"] == "training-briefing"
        )
        self.assertEqual(disclosure["path"], "/home/cinder/TRAINING.md")

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

    def test_delivery_manifests_bind_to_the_canonical_catalog(self) -> None:
        catalog = delivery_catalog.load_catalog()
        metadata = delivery_catalog.catalog_metadata()
        for phase in PHASES:
            with self.subTest(phase=phase):
                delivery = manifest(phase)["delivery"]
                phase_value = catalog["phases"][phase]
                self.assertEqual(delivery["cards"], {"status": "versioned"})
                self.assertEqual(delivery["hints"], {
                    "status": "versioned", "release": "on_request", "levels": 3, "penalty": 0,
                })
                self.assertEqual(delivery["catalog"], {
                    **metadata,
                    "phase": phase,
                    "phase_operation_count": phase_value["operation_count"],
                    "phase_card_count": phase_value["card_count"],
                    "phase_score_total": phase_value["score_total"],
                })

    def test_authored_hints_cover_all_cards_in_phase(self) -> None:
        import yaml
        registry = json.loads((ROOT / "build" / "card-coverage" / "registry.json").read_text())
        for phase in PHASES:
            hints_path = ROOT / "build" / "card-coverage" / f"hints-{phase}.yaml"
            if not hints_path.exists():
                continue
            hints_doc = yaml.safe_load(hints_path.read_text())
            phase_cards = {k for k, v in registry["cards"].items() if v["phase"] == phase}
            hinted_cards = set(hints_doc.get("hints", {}).keys())
            with self.subTest(phase=phase):
                missing = phase_cards - hinted_cards
                self.assertFalse(missing,
                    f"{phase}: {len(missing)} cards missing from hints file: "
                    + ", ".join(sorted(missing)[:5]))

    def test_versioned_challenge_catalog_matches_card_registry(self) -> None:
        catalog_path = ROOT / "challenges" / "challenges.yaml"
        registry_path = ROOT / "build" / "card-coverage" / "registry.json"
        self.assertTrue(catalog_path.exists(), "challenges/challenges.yaml must exist")
        catalog = delivery_catalog.load_catalog()
        registry = json.loads(registry_path.read_text())
        cards = delivery_catalog.catalog_cards(catalog)
        self.assertEqual(catalog["schema"], "cinder-typhoon.challenge-delivery/v2")
        self.assertEqual(len(delivery_catalog.catalog_operations(catalog)), 70)
        self.assertEqual(len(cards), 240)
        self.assertEqual({card["id"] for card in cards}, set(registry["cards"]))
        self.assertEqual(sum(card["points"] for card in cards), 39200)
        self.assertEqual(registry["delivery_catalog"], delivery_catalog.catalog_metadata())

    def test_participant_catalog_excludes_operator_design_and_solutions(self) -> None:
        serialized = json.dumps(delivery_catalog.load_catalog()).lower()
        for value in (
            "technical design", "vulnerability and intended solution", "author checks",
            "completion_evaluator", "accepting_components", "evidence_owners", "evidence_sources",
            "evidence_contract", "read_only_review",
            "prerequisite_sets", "request_body", "response_body",
        ):
            self.assertNotIn(value, serialized)

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
            "delivery": copy.deepcopy(manifest("training")["delivery"]),
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
