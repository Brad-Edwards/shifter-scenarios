"""Focused source checks for the native K01 implementation."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import yaml


PACK = Path(__file__).resolve().parents[3]


class K01NativeDesignTest(unittest.TestCase):
    def test_cards_bind_to_native_products(self) -> None:
        operation = yaml.safe_load((PACK / "sdl/modules/operations/k01.yaml").read_text())
        self.assertEqual(
            operation["evidence_requirements"]["c2"]["source_refs"],
            ["features.k-corporate.k-dev", "features.k-delivery.k-support"],
        )
        self.assertEqual(
            operation["evidence_requirements"]["c3"]["source_refs"],
            ["features.k-corporate.k-staff"],
        )
        support = yaml.safe_load((PACK / "sdl/modules/content/keplerops-k-support.yaml").read_text())
        support_contract = support["content"]["k01-2-the-tab-that-survived"]["text"]
        self.assertIn("osticket/ticket-thread", support_contract)
        self.assertNotIn("support-service/conversation", support_contract)
        staff = yaml.safe_load((PACK / "sdl/modules/content/keplerops-k-staff.yaml").read_text())
        staff_contract = staff["content"]["k01-3-outside-the-working-folder"]["text"]
        self.assertIn("kanboard/release-review", staff_contract)
        self.assertNotIn("filesystem:/home/rowan/work", staff_contract)

    def test_native_product_records_have_ordinary_neighbors(self) -> None:
        workplace = PACK / "assets/keplerops/native-workplace"
        cases = json.loads((workplace / "support-cases.json").read_text())["tickets"]
        reviews = json.loads((workplace / "review-records.json").read_text())["tasks"]
        self.assertGreaterEqual(len(cases), 3)
        self.assertGreaterEqual(len(reviews), 3)
        for task in reviews:
            self.assertTrue((workplace / "reviews" / task["attachment"]).is_file())
        participant_text = "\n".join(
            [json.dumps(cases), json.dumps(reviews)]
            + [(workplace / "reviews" / task["attachment"]).read_text() for task in reviews]
        ).lower()
        for forbidden in ("challenge", "participant", "ctf", "flag", "hint", "range"):
            self.assertNotIn(forbidden, participant_text)

    def test_desktop_review_duplicate_is_retired(self) -> None:
        archive = json.loads((PACK / "assets/keplerops/opening/archive-manifest.json").read_text())
        home = next(item for item in archive["archives"] if item["archive"] == "k-dev-home.tar")
        paths = {item["path"] for item in home["files"]}
        self.assertNotIn("work/review-exports/fieldlink-7.4.2-review.md", paths)
        self.assertIn("work/samples/FK-SAMPLE-017.json", paths)


if __name__ == "__main__":
    unittest.main()
