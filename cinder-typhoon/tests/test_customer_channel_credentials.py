"""Regression tests for approval-issued customer-channel authority."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "build" / "keplerops" / "runtime"
MODULE_PATH = Path(os.environ.get(
    "FIELDKEST_CHANNEL_CREDENTIAL_MODULE",
    RUNTIME / "channel_credentials.py",
))
CONTRACT_PATH = ROOT / "docs" / "design" / "keplerops-customer-channel-credentials.json"
REGISTRY_PATH = RUNTIME / "registry.py"
RELAY_PATH = RUNTIME / "customer_relay.py"
VERSION = "7.4.3-cinder.rowan"
RANGE_SECRET = "range-one-secret-material-with-more-than-32-characters"


def load_module():
    spec = importlib.util.spec_from_file_location("channel_credentials_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CustomerChannelCredentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def credential(self):
        return self.module.issue(VERSION, RANGE_SECRET, now_epoch=1_000)

    def authorize(self, document, grant_name, token, **overrides):
        version = VERSION if grant_name != "rollback" else "7.4.2"
        values = {
            "tenant": "TEN-ARWC-047",
            "channel": "arwc-stable",
            "version": version,
            "range_secret": RANGE_SECRET,
            "now_epoch": 1_001,
        }
        values.update(overrides)
        return self.module.authorize(document, token, grant_name, **values)

    def test_machine_contract_matches_runtime_grants_and_lifetime(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["credential_schema"], self.module.SCHEMA)
        self.assertEqual(contract["ttl_seconds"], self.module.TTL_SECONDS)
        self.assertEqual(contract["common_bindings"]["tenant"], self.module.TENANT)
        self.assertEqual(contract["common_bindings"]["channel"], self.module.CHANNEL)
        self.assertEqual(
            {name: value["operation"] for name, value in contract["grants"].items()},
            {name: value[0] for name, value in self.module.GRANT_SPECS.items()},
        )

    def test_issue_creates_four_distinct_range_bound_grants(self) -> None:
        document = self.credential()
        self.assertEqual(set(document), self.module.DOCUMENT_KEYS)
        self.assertEqual(document["range_binding"], self.module.range_binding(RANGE_SECRET))
        self.assertNotIn(RANGE_SECRET, json.dumps(document, sort_keys=True))
        self.assertEqual(document["expires_at_epoch"] - document["issued_at_epoch"], 3600)
        self.assertEqual(set(document["grants"]), {"poll", "activate", "receipt", "rollback"})
        self.assertEqual(len({grant["token"] for grant in document["grants"].values()}), 4)
        for name, grant in document["grants"].items():
            with self.subTest(grant=name):
                self.assertTrue(self.authorize(document, name, grant["token"]))

    def test_authorization_rejects_wrong_scope_and_binding(self) -> None:
        document = self.credential()
        poll = document["grants"]["poll"]["token"]
        activate = document["grants"]["activate"]["token"]
        self.assertFalse(self.authorize(document, "activate", poll))
        self.assertFalse(self.authorize(document, "poll", activate))
        self.assertFalse(self.authorize(document, "poll", poll, tenant="TEN-ARWC-019"))
        self.assertFalse(self.authorize(document, "poll", poll, channel="rill-stable"))
        self.assertFalse(self.authorize(document, "poll", poll, version="7.4.3-cinder.other"))
        self.assertFalse(self.authorize(document, "poll", poll, range_secret="foreign-range-secret-material-with-more-than-32-characters"))
        tampered = copy.deepcopy(document)
        tampered["tenant"] = "TEN-ARWC-019"
        self.assertFalse(self.authorize(tampered, "poll", poll))
        tampered = copy.deepcopy(document)
        tampered["channel"] = "rill-stable"
        self.assertFalse(self.authorize(tampered, "poll", poll))
        tampered = copy.deepcopy(document)
        tampered["grants"]["activate"]["operation"] = "package.poll"
        self.assertFalse(self.authorize(tampered, "activate", activate))
        tampered = copy.deepcopy(document)
        tampered["grants"]["activate"]["version"] = "7.4.3-cinder.other"
        self.assertFalse(self.authorize(tampered, "activate", activate))

    def test_authorization_rejects_expired_future_replaced_and_malformed_sets(self) -> None:
        document = self.credential()
        poll = document["grants"]["poll"]["token"]
        self.assertFalse(self.authorize(document, "poll", poll, now_epoch=4_600))
        self.assertFalse(self.authorize(document, "poll", poll, now_epoch=999))
        replacement = self.module.issue(VERSION, RANGE_SECRET, now_epoch=1_000)
        self.assertFalse(self.authorize(replacement, "poll", poll))
        malformed = dict(document)
        malformed.pop("range_binding")
        self.assertFalse(self.authorize(malformed, "poll", poll))
        malformed = dict(document)
        malformed["expires_at_epoch"] = 9_999
        self.assertFalse(self.authorize(malformed, "poll", poll))

    def test_runtime_has_no_static_or_release_record_channel_bearer(self) -> None:
        registry = REGISTRY_PATH.read_text(encoding="utf-8")
        relay = RELAY_PATH.read_text(encoding="utf-8")
        self.assertNotIn("channel_token", registry)
        self.assertNotIn("INTERNAL_PACKAGE_TOKEN", relay)
        self.assertIn('response["channel_credentials"]', registry)
        self.assertIn("authorize(", relay)


if __name__ == "__main__":
    unittest.main()
