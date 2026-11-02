from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "challenges" / "catalog.py"
CATALOG_SPEC = importlib.util.spec_from_file_location("hint_test_catalog", CATALOG_PATH)
assert CATALOG_SPEC and CATALOG_SPEC.loader
catalog = importlib.util.module_from_spec(CATALOG_SPEC)
sys.modules[CATALOG_SPEC.name] = catalog
CATALOG_SPEC.loader.exec_module(catalog)

RELEASE_PATH = ROOT / "build" / "hint-delivery" / "release.py"
RELEASE_SPEC = importlib.util.spec_from_file_location("hint_release", RELEASE_PATH)
assert RELEASE_SPEC and RELEASE_SPEC.loader
release = importlib.util.module_from_spec(RELEASE_SPEC)
sys.modules[RELEASE_SPEC.name] = release
RELEASE_SPEC.loader.exec_module(release)


class HintContentTests(unittest.TestCase):
    def test_all_cards_have_three_substantive_levels(self) -> None:
        summary = release.validate_authored_hints()
        self.assertEqual(summary, {
            "card_count": 240,
            "hint_count": 720,
            "operation_review_count": 70,
            "training_card_count": 16,
            "keplerops_card_count": 104,
            "arwc_card_count": 120,
        })

    def test_placeholder_title_restatement_and_sensitive_literals_are_rejected(self) -> None:
        cases = {
            "placeholder": (
                "h1",
                "[hint 1 for K01.1] inspect the service record and ordinary client evidence before continuing further",
                "unrelated title",
            ),
            "exact_route": (
                "h3",
                "Inspect the service and send the exact request to /api/private-answer before recording the result",
                "unrelated title",
            ),
            "credential": (
                "h2",
                "Use authorization analysis with token=customer-secret-value and compare the service boundary carefully before continuing",
                "unrelated title",
            ),
            "title": (
                "h1",
                "the developer left a way back",
                "the developer left a way back",
            ),
            "generated_filler": (
                "h1",
                "Begin with the service record. The immediate evidence concerns a generic generated filler target that adds no useful orientation.",
                "unrelated title",
            ),
        }
        for name, (level, text, title) in cases.items():
            with self.subTest(name=name), self.assertRaises(release.HintDeliveryError):
                release._validate_text("K01.1", level, text, title, {})

    def test_generic_duplicate_cannot_be_reused_across_operations(self) -> None:
        text = (
            "Inspect the participant service record, compare the ordinary and denied cases, "
            "and preserve the returned revision for the next diagnostic step."
        )
        seen: dict[tuple[str, str], list[str]] = {}
        release._validate_text("K01.1", "h3", text, "unrelated title", seen)
        with self.assertRaisesRegex(release.HintDeliveryError, "generic duplicate"):
            release._validate_text("K02.1", "h3", text, "another title", seen)

    def test_stale_participant_reference_fails_validation(self) -> None:
        references = release._published_references()
        references["client_route"] = set(references["client_route"])
        references["client_route"].discard("corporate.handover")
        with (
            mock.patch.object(release, "_published_references", return_value=references),
            self.assertRaisesRegex(release.HintDeliveryError, "stale client_route"),
        ):
            release.validate_authored_hints()

    def test_hint_schemas_are_machine_readable_and_match_committed_versions(self) -> None:
        schema_paths = (
            ROOT / "build/card-coverage/hints.schema.json",
            ROOT / "build/hint-delivery/manifest.schema.json",
            ROOT / "build/hint-delivery/operation-reviews.schema.json",
            ROOT / "build/hint-delivery/playtest-observation.schema.json",
        )
        for path in schema_paths:
            with self.subTest(path=path.name):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("$id", value)
        self.assertEqual(
            json.loads((ROOT / "build/hint-delivery/manifest.schema.json").read_text())
            ["properties"]["summary"]["const"],
            {"operation_count": 70, "card_count": 240, "hint_count": 720},
        )
        playtest = json.loads(
            (ROOT / "build/hint-delivery/playtest-observation.schema.json").read_text()
        )
        self.assertIn("level_observations", playtest["required"])
        observations = playtest["properties"]["level_observations"]
        self.assertEqual(observations["minProperties"], 1)
        self.assertEqual(set(observations["properties"]), {"1", "2", "3"})
        self.assertEqual(
            set(playtest["$defs"]["level_observation"]["required"]),
            {"release_event_id", "understanding_check", "participant_explanation"},
        )


class HintManifestTests(unittest.TestCase):
    def test_manifest_is_current_complete_and_content_free(self) -> None:
        value = catalog.load_hint_manifest()
        self.assertEqual(value, catalog.build_hint_manifest(catalog.load_catalog()))
        self.assertEqual(value["summary"], {
            "operation_count": 70, "card_count": 240, "hint_count": 720,
        })
        self.assertEqual(len(value["items"]), 240)
        self.assertEqual(len({item["card_id"] for item in value["items"]}), 240)
        self.assertTrue(all([level["level"] for level in item["levels"]] == [1, 2, 3]
                            for item in value["items"]))
        serialized = json.dumps(value)
        for document in catalog._hint_documents().values():
            for authored in document["hints"].values():
                for level in catalog.HINT_LEVELS:
                    self.assertNotIn(" ".join(authored[level].split()), serialized)

    def test_manifest_records_sources_release_score_review_and_playtest_contract(self) -> None:
        value = catalog.load_hint_manifest()
        self.assertEqual(len(value["sources"]), 3)
        self.assertEqual(value["release"], {
            "mode": "facilitator_on_request",
            "levels": [1, 2, 3],
            "independent_levels": True,
            "audit": "append_only_metadata_without_hint_text",
        })
        self.assertEqual(value["score_effect"], {
            "penalty": 0, "maximum_score_unchanged": True,
        })
        self.assertEqual(value["review"]["operation_count"], 70)
        self.assertEqual(set(value["playtest_evidence"]["required_fields"]), {
            "card_id", "level_observations", "observer_notes",
        })

    def test_every_operation_has_one_reviewed_sample_from_that_operation(self) -> None:
        reviews = json.loads(catalog.HINT_REVIEWS.read_text(encoding="utf-8"))["operations"]
        operations = {operation["id"]: operation for operation in catalog.catalog_operations(
            catalog.load_catalog()
        )}
        self.assertEqual(set(reviews), set(operations))
        for operation_id, review in reviews.items():
            with self.subTest(operation=operation_id):
                self.assertEqual(review["status"], "reviewed")
                self.assertIn(review["sample_card"], {
                    card["id"] for card in operations[operation_id]["cards"]
                })
                self.assertGreaterEqual(len(review["rationale"].split()), 15)

    def test_manifest_mutation_is_rejected(self) -> None:
        changed = json.loads(json.dumps(catalog.load_hint_manifest()))
        changed["release"]["independent_levels"] = False
        with self.assertRaisesRegex(catalog.CatalogError, "stale"):
            catalog.validate_hint_manifest(changed, catalog.load_catalog())


class FacilitatorReleaseTests(unittest.TestCase):
    def test_levels_release_independently_and_audit_contains_no_hint_text(self) -> None:
        documents = catalog._hint_documents()
        h1 = " ".join(documents["keplerops"]["hints"]["K01.1"]["h1"].split())
        h2 = " ".join(documents["keplerops"]["hints"]["K01.1"]["h2"].split())
        h3 = " ".join(documents["keplerops"]["hints"]["K01.1"]["h3"].split())
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "hint-releases.jsonl"
            result = release.release_hint(
                audit,
                card_id="K01.1",
                level=3,
                actor="facilitator-test",
                released_at="2026-11-01T00:00:00+00:00",
            )
            self.assertEqual(result["status"], "released")
            self.assertEqual(result["text"], h3)
            self.assertNotIn(h1, json.dumps(result))
            self.assertNotIn(h2, json.dumps(result))
            audit_text = audit.read_text(encoding="utf-8")
            self.assertNotIn(h1, audit_text)
            self.assertNotIn(h2, audit_text)
            self.assertNotIn(h3, audit_text)
            self.assertNotIn('"text"', audit_text)
            self.assertEqual(stat.S_IMODE(audit.stat().st_mode), 0o600)
            status = release.release_status(audit)
            self.assertEqual([(item["card_id"], item["level"]) for item in status["released"]], [
                ("K01.1", 3),
            ])
            self.assertNotIn(h3, json.dumps(status))

    def test_repeated_release_is_idempotent_and_event_chain_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "hint-releases.jsonl"
            first = release.release_hint(
                audit, card_id="W01.1", level=1, actor="facilitator-test",
                released_at="2026-11-01T00:00:00+00:00",
            )
            repeated = release.release_hint(
                audit, card_id="W01.1", level=1, actor="another-facilitator",
                released_at="2026-11-01T00:01:00+00:00",
            )
            second = release.release_hint(
                audit, card_id="W01.1", level=2, actor="facilitator-test",
                released_at="2026-11-01T00:02:00+00:00",
            )
            self.assertEqual(repeated["status"], "already_released")
            self.assertEqual(repeated["event_id"], first["event_id"])
            self.assertNotEqual(second["event_id"], first["event_id"])
            self.assertEqual(len(audit.read_text(encoding="utf-8").splitlines()), 2)
            self.assertEqual(len(release.release_status(audit)["released"]), 2)

    def test_audit_refuses_symlinks_and_non_owner_only_status_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.jsonl"
            target.write_text("unchanged", encoding="utf-8")
            link = root / "audit.jsonl"
            link.symlink_to(target)
            with self.assertRaisesRegex(release.HintDeliveryError, "opened safely"):
                release.release_hint(link, card_id="K01.1", level=1, actor="facilitator-test")
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")

            audit = root / "readable.jsonl"
            audit.write_text("", encoding="utf-8")
            audit.chmod(0o644)
            with self.assertRaisesRegex(release.HintDeliveryError, "owner-only"):
                release.release_status(audit)


if __name__ == "__main__":
    unittest.main()
