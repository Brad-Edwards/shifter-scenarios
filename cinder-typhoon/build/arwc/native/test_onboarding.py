"""Check customer onboarding stays limited to its configured supplier and case."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("customer_handover", Path(__file__).parent.parent / "runtime/customer_handover.py")
handover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handover)


class SupplierOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "account": "Veybridge Field Services", "contact": "Jules Orswick",
            "maintenance_case": "MTN-CRR-204", "username": "jules.orswick@veybridge.test",
            "supplier_portal": "https://suppliers.arwc.test/purchase-orders",
            "documents": "https://documents.arwc.test/", "document_folder": "Veybridge handover",
            "password": "a" * 64,
        }

    def read(self, record):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "onboarding.json"
            source.write_text(json.dumps(record))
            with patch.object(handover, "ONBOARDING", source):
                return handover.native_onboarding()

    def test_configured_supplier_material_is_retained(self):
        self.assertEqual(self.read(self.record), self.record)

    def test_other_account_case_or_service_is_rejected(self):
        for field, value in (("username", "Administrator"), ("maintenance_case", "MTN-RIV-3308"),
                             ("documents", "https://unrelated.test/")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.read({**self.record, field: value})

    def test_unexpected_authority_is_rejected(self):
        with self.assertRaises(ValueError):
            self.read({**self.record, "workforce_password": "not-supplier-material"})

    def test_empty_credential_is_rejected(self):
        with self.assertRaises(ValueError):
            self.read({**self.record, "password": ""})


if __name__ == "__main__":
    unittest.main()
