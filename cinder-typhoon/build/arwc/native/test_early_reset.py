"""Checks for repeatable native state at the start of the early ARWC cards."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch


with patch.dict(os.environ, {"DOCUMENTS_ADMIN_PASSWORD": "unused-test-value"}):
    spec = importlib.util.spec_from_file_location("early_seed", Path(__file__).with_name("seed-early-cards.py"))
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)


class EarlyCardResetTests(unittest.TestCase):
    def test_restores_handback_and_removes_prior_audit_versions(self) -> None:
        versions = {"data": [{"name": "old-version"}, {"name": "newer-version"}]}
        with patch.object(seed, "api", side_effect=({}, versions, {}, {})) as api:
            seed.restore_handback({"name": "TASK-2026-00013"})

        self.assertEqual(api.call_args_list[0], call(
            "/api/resource/Task/TASK-2026-00013",
            {"status": "Open", "description": seed.HANDBACK_DESCRIPTION},
            method="PUT",
        ))
        self.assertIn("ref_doctype", api.call_args_list[1].args[0])
        self.assertEqual(api.call_args_list[2], call("/api/resource/Version/old-version", method="DELETE"))
        self.assertEqual(api.call_args_list[3], call("/api/resource/Version/newer-version", method="DELETE"))

    def test_purchase_order_share_is_exact_and_read_only(self) -> None:
        with patch.object(seed, "api") as api:
            seed.share_record("Purchase Order", "PUR-ORD-2026-00001")

        api.assert_called_once_with("/api/method/frappe.share.add", {
            "doctype": "Purchase Order", "name": "PUR-ORD-2026-00001",
            "user": seed.EMAIL, "read": 1, "write": 0, "share": 0, "notify": 0,
        })

    def test_rebuilds_annex_with_nextcloud_version_spacing(self) -> None:
        verify_versions = Mock()
        with patch.object(seed, "request") as request, \
             patch.object(seed.time, "sleep") as sleep, \
             patch.dict(seed.files, {"verify_versions": verify_versions}):
            seed.rebuild_annex_history("Veybridge handover/ANN-4417.md")

        self.assertEqual(request.call_args_list[0], call(
            "DELETE", seed.dav("Veybridge handover/ANN-4417.md"), accepted=(204, 404)
        ))
        self.assertEqual([operation.args[0] for operation in request.call_args_list], ["DELETE", "PUT", "PUT"])
        sleep.assert_called_once_with(121)
        verify_versions.assert_called_once()


if __name__ == "__main__":
    unittest.main()
