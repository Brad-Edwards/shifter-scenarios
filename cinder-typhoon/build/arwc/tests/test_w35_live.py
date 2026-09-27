#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-business"
BASE = "https://business-workplace.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
data = None if not body else body.encode()
if data is not None: headers["Content-Type"] = "application/json"
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
 response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside(
        "python3", "-c", script, method, BASE + path, tenant,
        "@session" if token is None else token,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


class W35Live(unittest.TestCase):
    def test_01_quote_and_order_require_owned_predecessor_evidence(self) -> None:
        status, body = request(
            "/api/a-quote-outside-your-district", method="POST",
            body={"procurement_reference": "PRC-REGIONAL-17", "catalog_revision": 5,
                  "role": "corporate-reader", "district": "Cairn Reach"},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("QUOTE-MER-884", json.dumps(body))
        status, body = request(
            "/api/the-wrong-bill", method="POST", body={"quote_id": "QUOTE-MER-884"},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("PO-MER-884-C", json.dumps(body))

    def test_02_catalog_is_distinct_and_reuses_exact_authored_context(self) -> None:
        status, response = request("/api/what-replacement-water-costs")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "CAT-REPL-WATER-R5")
        self.assertEqual(record["revision"], 5)
        self.assertEqual(record["district_procurement_reference"], "PRC-REGIONAL-17")
        self.assertFalse(record["is_settlement_tariff"])
        self.assertNotIn("TAR-CRR-DP3-R4", json.dumps(record))
        package = json.loads(pathlib.Path(
            "../../assets/narrative/generated/packages/arwc-documents.json"
        ).read_text(encoding="utf-8"))
        authored = next(item for item in package["documents"] if item["name"] == "as003-agreement-summary")
        context = response["agreement_context"]
        self.assertEqual(context["asset"], "arwc-documents:as003-agreement-summary")
        self.assertEqual(context["text"], authored["text"])
        self.assertEqual(context["sha256"], hashlib.sha256(authored["text"].encode()).hexdigest())

    def test_03_role_is_checked_but_district_membership_is_omitted(self) -> None:
        baseline = {"procurement_reference": "PRC-REGIONAL-17", "catalog_revision": 5,
                    "role": "corporate-reader", "district": "Cairn Reach"}
        for changed, expected in (
            (dict(baseline, procurement_reference="PRC-MER-01"), 409),
            (dict(baseline, catalog_revision=4), 409),
            (dict(baseline, role="field-reader"), 403),
        ):
            status, body = request("/api/a-quote-outside-your-district", method="POST", body=changed)
            self.assertEqual(status, expected)
            self.assertNotIn("QUOTE-MER-884", json.dumps(body))
        status, response = request(
            "/api/a-quote-outside-your-district", method="POST", body=baseline,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "QUOTE-MER-884", "revision": 4,
            "owner_district": "Merewick", "supplier": "Merewick Bulk Water Cooperative",
            "supplier_account": "A-S-003", "quantity_ml": 0.75,
            "unit_price_usd_per_ml": 2280, "planning_window": "ALLOC-2026-DP3",
            "quoted_total_usd": 1710,
        })

    def test_04_order_preserves_quote_but_trusts_charge_district(self) -> None:
        baseline = {
            "quote_id": "QUOTE-MER-884", "expected_revision": 4,
            "supplier": "Merewick Bulk Water Cooperative", "quantity_ml": 0.75,
            "planning_window": "ALLOC-2026-DP3", "charge_district": "Cairn Reach",
            "budget": "BUD-CRR-DP3",
        }
        for changed in (
            dict(baseline, supplier="Regional Resilience Exchange"),
            dict(baseline, quantity_ml=1.0),
            dict(baseline, planning_window="ALLOC-2026-DP4"),
            dict(baseline, budget="BUD-MER-DP3"),
        ):
            status, body = request("/api/the-wrong-bill", method="POST", body=changed)
            self.assertEqual(status, 409)
            self.assertNotIn("PO-MER-884-C", json.dumps(body))
        status, response = request("/api/the-wrong-bill", method="POST", body=baseline)
        self.assertEqual(status, 201)
        order = response["record"]
        self.assertEqual(order["record_id"], "PO-MER-884-C")
        self.assertEqual(order["quote_owner_district"], "Merewick")
        self.assertEqual(order["charge_district"], "Cairn Reach")
        self.assertEqual(order["budget"], "BUD-CRR-DP3")
        self.assertEqual(order["liability_usd"], 1710)
        self.assertEqual(order["quantity_ml"], 0.75)

    def test_05_authorization_and_idempotent_order_are_enforced(self) -> None:
        status, body = request("/api/what-replacement-water-costs", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("CAT-REPL-WATER-R5", json.dumps(body))
        status, body = request("/api/what-replacement-water-costs", tenant="merewick")
        self.assertEqual(status, 403)
        baseline = {
            "quote_id": "QUOTE-MER-884", "expected_revision": 4,
            "supplier": "Merewick Bulk Water Cooperative", "quantity_ml": 0.75,
            "planning_window": "ALLOC-2026-DP3", "charge_district": "Cairn Reach",
            "budget": "BUD-CRR-DP3",
        }
        first = request("/api/the-wrong-bill", method="POST", body=baseline)[1]["record"]
        second = request("/api/the-wrong-bill", method="POST", body=baseline)[1]["record"]
        self.assertEqual(first, second)

    def test_06_order_and_audits_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        baseline = {
            "quote_id": "QUOTE-MER-884", "expected_revision": 4,
            "supplier": "Merewick Bulk Water Cooperative", "quantity_ml": 0.75,
            "planning_window": "ALLOC-2026-DP3", "charge_district": "Cairn Reach",
            "budget": "BUD-CRR-DP3",
        }
        for _ in range(30):
            try:
                status, response = request("/api/the-wrong-bill", method="POST", body=baseline)
                if status == 201: break
            except AssertionError: pass
        else:
            self.fail("business workplace did not return after restart")
        self.assertEqual(response["record"]["record_id"], "PO-MER-884-C")
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-business", SERVICE,
             "cat", "/var/lib/arwc-business/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in ("what-replacement-water-costs", "a-quote-outside-your-district", "the-wrong-bill"):
            self.assertIn(f'"action":"{action}"', audit)
        self.assertEqual(inside("sh", "-c", "test ! -r /var/lib/arwc-business/state/discoveries.json").returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
