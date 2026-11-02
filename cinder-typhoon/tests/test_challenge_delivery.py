from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "challenges"))
import catalog  # noqa: E402

IMPORTER_PATH = ROOT / "ctfd" / "import_catalog.py"
SPEC = importlib.util.spec_from_file_location("cinder_event_importer", IMPORTER_PATH)
assert SPEC and SPEC.loader
event_importer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(event_importer)


class CanonicalCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = catalog.load_catalog()

    def test_generated_snapshot_is_current_and_complete(self) -> None:
        self.assertEqual(self.catalog, catalog.build_catalog())
        self.assertEqual(self.catalog["summary"], {"operation_count": 70, "card_count": 240})
        cards = catalog.catalog_cards(self.catalog)
        self.assertEqual(len(cards), 240)
        self.assertEqual(len({card["id"] for card in cards}), 240)
        self.assertEqual(sum(card["points"] for card in cards), 39200)
        self.assertEqual(self.catalog["scoring"]["max_score"], 39200)

    def test_catalog_contains_only_participant_delivery_fields(self) -> None:
        allowed_card_fields = {
            "id", "title", "description", "difficulty", "points", "hints", "completion",
        }
        for card in catalog.catalog_cards(self.catalog):
            with self.subTest(card=card["id"]):
                self.assertEqual(set(card), allowed_card_fields)
                self.assertEqual(card["completion"], {"mode": "automatic_range_evidence"})
                self.assertEqual(len(card["hints"]), 3)
        serialized = json.dumps(self.catalog).lower()
        for forbidden in (
            "technical design", "intended solution", "author checks", "request_body",
            "response_body", "prerequisite_sets", "evidence_owners", "evidence_sources",
            "evidence_contract", "read_only_review",
        ):
            self.assertNotIn(forbidden, serialized)


class EventImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = catalog.load_catalog()
        cls.bundle = event_importer.build_event_bundle(
            cls.catalog,
            scorer_origin="https://cinder-scorer.example.test",
        )

    def test_native_event_projection_has_every_ui_card_and_score(self) -> None:
        event_importer.validate_projection(self.catalog, self.bundle)
        rows = self.bundle["challenges"]
        cards = catalog.catalog_cards(self.catalog)
        self.assertEqual(len(rows), 240)
        self.assertEqual(
            [(row["name"], row["points"]) for row in rows],
            [(f"{card['id']}: {card['title']}", card["points"]) for card in cards],
        )
        self.assertEqual(sum(row["points"] for row in rows), 39200)
        self.assertTrue(all(row["visibility"] == "visible" for row in rows))

    def test_scorer_import_is_bound_to_catalog_revision(self) -> None:
        expected = {"X-Cinder-Catalog-Revision": self.catalog["revision"]}
        self.assertTrue(all(row["flags"][0]["headers"] == expected for row in self.bundle["challenges"]))
        changed = json.loads(json.dumps(self.bundle))
        changed["challenges"][0]["flags"][0]["headers"] = {}
        with self.assertRaisesRegex(event_importer.CatalogImportError, "revision binding"):
            event_importer.validate_projection(self.catalog, changed)

    def test_import_projection_contains_no_answers_or_solutions(self) -> None:
        serialized = json.dumps(self.bundle).lower()
        self.assertNotIn('"solution"', serialized)
        self.assertNotIn('"value"', serialized)
        self.assertNotIn("request_body", serialized)
        self.assertNotIn("response_body", serialized)

    def test_import_bundle_is_written_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event-content.json"
            event_importer.write_private_json(path, self.bundle)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text()), self.bundle)

    def test_participant_bundle_rejects_operator_prize_policy(self) -> None:
        changed = deepcopy(self.bundle)
        changed["prize_policy"] = {}
        with self.assertRaisesRegex(
            event_importer.CatalogImportError, "top-level fields"
        ):
            event_importer.validate_projection(self.catalog, changed)

    def test_plain_http_scorer_is_rejected_outside_explicit_loopback_test(self) -> None:
        with self.assertRaises(event_importer.CatalogImportError):
            event_importer.build_event_bundle(
                self.catalog,
                scorer_origin="http://scorer.example.test",
            )
        loopback = event_importer.build_event_bundle(
            self.catalog,
            scorer_origin="http://127.0.0.1:8443",
            allow_loopback_http=True,
        )
        self.assertEqual(len(loopback["challenges"]), 240)


class PrizePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = catalog.load_catalog()
        cls.bundle = event_importer.build_event_bundle(
            cls.catalog,
            scorer_origin="https://cinder-scorer.example.test",
        )
        cls.bundle_digest = event_importer.artifact_digest(cls.bundle)
        cls.policy = event_importer.prize_policy_module.build_policy(
            cls.catalog,
            cls.bundle_digest,
        )

    def test_policy_binds_exact_bundle_and_all_catalog_cards(self) -> None:
        event_importer.prize_policy_module.validate_policy(
            self.catalog,
            self.policy,
            self.bundle_digest,
        )
        self.assertEqual(self.policy["catalog"]["revision"], self.catalog["revision"])
        self.assertEqual(
            self.policy["catalog"]["content_bundle_digest"], self.bundle_digest
        )
        stage_ids = {
            stage: value["challenge_source_ids"]
            for stage, value in self.policy["stages"].items()
        }
        self.assertEqual(
            {stage: len(ids) for stage, ids in stage_ids.items()},
            {
                "training": 16,
                "keplerops": 104,
                "arwc": 120,
            },
        )
        all_ids = [source_id for ids in stage_ids.values() for source_id in ids]
        self.assertEqual(len(all_ids), 240)
        self.assertEqual(len(set(all_ids)), 240)

    def test_policy_is_deterministic_and_written_owner_only(self) -> None:
        rebuilt = event_importer.prize_policy_module.build_policy(
            self.catalog,
            self.bundle_digest,
        )
        self.assertEqual(
            event_importer.canonical_json_bytes(rebuilt),
            event_importer.canonical_json_bytes(self.policy),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event-prizes.json"
            event_importer.write_private_json(path, self.policy)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(
                path.read_bytes(), event_importer.canonical_json_bytes(self.policy)
            )

    def test_policy_has_50_unique_slots_and_six_reviewed_bounties(self) -> None:
        allocations = self.policy["allocations"]
        slot_ids = event_importer.prize_policy_module.policy_slot_ids(allocations)
        self.assertEqual(len(slot_ids), 50)
        self.assertEqual(len(set(slot_ids)), 50)
        self.assertEqual(
            [item["challenge_source_id"] for item in allocations["bounties"]["awards"]],
            ["t03.4", "t04.4", "k09.4", "k11.4", "w30.2", "w35.3"],
        )
        serialized = json.dumps(self.policy)
        for forbidden_key in (
            '"draw_seed"',
            '"winner_state"',
            '"claim_state"',
            '"participant_id"',
        ):
            self.assertNotIn(forbidden_key, serialized)

    def test_policy_rejects_malformed_or_participant_visible_changes(self) -> None:
        mutations = []

        unknown_card = deepcopy(self.policy)
        unknown_card["stages"]["training"]["challenge_source_ids"].append("t99.9")
        mutations.append(unknown_card)

        duplicate_slot = deepcopy(self.policy)
        duplicate_slot["allocations"]["overall_leaders"]["slot_ids"][1] = "overall-01"
        mutations.append(duplicate_slot)

        missing_slot = deepcopy(self.policy)
        missing_slot["allocations"]["overall_leaders"]["slot_ids"].pop()
        mutations.append(missing_slot)

        changed_precedence = deepcopy(self.policy)
        changed_precedence["evaluation_order"]["accepted_solve"].reverse()
        mutations.append(changed_precedence)

        participant_visible_state = deepcopy(self.policy)
        participant_visible_state["winner_state"] = []
        mutations.append(participant_visible_state)

        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(
                    event_importer.prize_policy_module.PrizePolicyError
                ):
                    event_importer.prize_policy_module.validate_policy(
                        self.catalog,
                        changed,
                        self.bundle_digest,
                    )

    def test_policy_rejects_a_different_content_bundle_digest(self) -> None:
        other_digest = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(
            event_importer.prize_policy_module.PrizePolicyError,
            "content binding",
        ):
            event_importer.prize_policy_module.validate_policy(
                self.catalog,
                self.policy,
                other_digest,
            )


if __name__ == "__main__":
    unittest.main()
