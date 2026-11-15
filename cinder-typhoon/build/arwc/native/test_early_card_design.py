"""Static checks for the native W01-W03 challenge bindings."""
from pathlib import Path
import json
import unittest

import yaml


PACK = Path(__file__).resolve().parents[3]
SDL = PACK / "sdl/modules"


class EarlyCardDesignTests(unittest.TestCase):
    def test_operations_use_native_product_features_without_retired_content(self) -> None:
        for operation in range(1, 4):
            text = (SDL / f"operations/w{operation:02d}.yaml").read_text()
            self.assertNotIn(f"content.arwc-a-connector.w{operation:02d}", text)
            self.assertNotIn(f"content.arwc-a-business.w{operation:02d}", text)
        w01 = (SDL / "operations/w01.yaml").read_text()
        w02 = (SDL / "operations/w02.yaml").read_text()
        w03 = (SDL / "operations/w03.yaml").read_text()
        self.assertIn("Nextcloud", w01)
        self.assertIn("ERPNext", w01)
        self.assertIn("Nextcloud", w02)
        self.assertIn("ERPNext", w02)
        self.assertIn("PostgREST", w03)
        self.assertIn("PostgreSQL", w03)

    def test_world_declares_the_pinned_upstream_products(self) -> None:
        corporate = yaml.safe_load((SDL / "world/a-corporate.yaml").read_text())
        dmz = yaml.safe_load((SDL / "world/a-dmz.yaml").read_text())
        business = corporate["nodes"]["a-business"]["runtime"]
        products = {item["component_id"]: item for item in business["software_components"]}
        self.assertEqual(products["erpnext"]["version"], "16.55.0")
        self.assertEqual(str(products["nextcloud"]["version"]), "35")
        applications = {item["application_id"] for item in business["applications"]}
        self.assertTrue({"erpnext", "nextcloud"} <= applications)
        bridge = dmz["nodes"]["a-data-bridge"]["runtime"]
        postgrest = next(item for item in bridge["software_components"] if item["component_id"] == "postgrest")
        self.assertEqual(str(postgrest["version"]), "16.5")
        self.assertIn("postgrest", {item["application_id"] for item in bridge["applications"]})

    def test_retired_opening_facade_contracts_are_absent(self) -> None:
        self.assertFalse((SDL / "content/arwc-a-connector.yaml").exists())
        business = yaml.safe_load((SDL / "content/arwc-a-business.yaml").read_text())
        self.assertFalse(any(key.startswith(("w02-", "w03-")) for key in business["content"]))
        known = (PACK / "build/arwc/tests/test_known_solution_live.py").read_text()
        for old in (
            "business.asset-bundle", "business.association-record", "business.work-order-attachment",
            "business.work-order-annex", "business.work-order-references",
            "corporate.work-order", "corporate.continuity-plan", "corporate.work-order-update",
        ):
            self.assertNotIn(old, known)

    def test_participant_surface_declares_native_product_hosts(self) -> None:
        surface = json.loads(
            (PACK / "build/participant-surface/manifests/arwc.json").read_text()
        )
        names = {record["name"] for record in surface["network"]["dns"]}
        self.assertTrue({
            "erp.arwc.test", "documents.arwc.test",
            "suppliers.arwc.test", "read-data.arwc.test",
        } <= names)

    def test_native_records_do_not_contain_range_meta_language(self) -> None:
        records = PACK / "build/arwc/native/records"
        text = "\n".join(path.read_text(errors="replace") for path in records.iterdir() if path.is_file()).lower()
        for phrase in ("cyber range", "ctf", "expected path", "challenge answer", "participant hint"):
            self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
