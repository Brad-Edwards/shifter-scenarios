#!/usr/bin/env python3
"""Black-box checks for the running Training Developer services."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HOST = "developer.training"
TOKEN = "publisher_CINDER_7K4M9Q2V6R8D"


def request(port: int, path: str, *, body: object | None = None, method: str = "GET", authorized: bool = False) -> tuple[int, object | bytes]:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if authorized:
        headers["Authorization"] = f"Bearer {TOKEN}"
    try:
        with urlopen(Request(f"http://{HOST}:{port}{path}", data=data, headers=headers, method=method), timeout=8) as response:
            raw = response.read()
            return response.status, json.loads(raw) if response.headers.get_content_type() == "application/json" else raw
    except HTTPError as error:
        with error:
            raw = error.read()
            return error.code, json.loads(raw) if error.headers.get_content_type() == "application/json" else raw


class DeveloperLiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        status, baseline = request(8084, "/api/consumer/run", method="POST", body={})
        if status != 200:
            raise AssertionError((status, baseline))
        cls.baseline = baseline
        cls.version = "1.5.0"
        source = "exports.formatDelivery = function (input) { const unit = input.parcel_count === 1 ? 'parcel' : 'parcels'; return {...input, summary: input.delivery_id + ' | ' + input.destination + ' | ' + input.parcel_count + ' ' + unit, rehearsal_marker: 'Cinder rehearsal'}; };"
        package_json = json.dumps({"name": "@cinder/delivery-formatter", "version": cls.version, "main": "index.js"}, separators=(",", ":"))
        cls.package = {"name": "@cinder/delivery-formatter", "version": cls.version, "files": {"package.json": package_json, "index.js": source}}
        status, cls.publication = request(8083, f"/api/packages/@cinder/delivery-formatter/{cls.version}", method="PUT", body=cls.package, authorized=True)
        if status != 201:
            raise AssertionError((status, cls.publication))
        status, cls.fresh = request(8084, "/api/consumer/run", method="POST", body={})
        if status != 200:
            raise AssertionError((status, cls.fresh))

    def test_documents_history_and_fair_lead(self) -> None:
        self.assertEqual(request(8080, "/sample-package/package.json")[0], 200)
        status, log = request(8082, "/jobs/BLD-204/log")
        self.assertEqual(status, 200)
        self.assertIn(TOKEN.encode(), log)
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run(["git", "clone", "--quiet", f"http://{HOST}:8081/cinder/delivery-formatter.git", temporary], check=True)
            self.assertFalse((__import__("pathlib").Path(temporary) / "test/fixtures/DL-204.json").exists())
            fixture = subprocess.check_output(["git", "-C", temporary, "show", "HEAD^:test/fixtures/DL-204.json"], text=True)
            review = subprocess.check_output(["git", "-C", temporary, "show", "HEAD:REVIEW.md"], text=True)
        self.assertIn("expected_summary", fixture)
        self.assertIn("test/fixtures/DL-204.json", review)

    def test_registry_scope_and_immutability(self) -> None:
        self.assertEqual(request(8083, "/api/channels/rehearsal/manifest")[0], 401)
        status, manifest = request(8083, "/api/channels/rehearsal/manifest", authorized=True)
        self.assertEqual(status, 200)
        self.assertEqual(manifest["revision"], 6)
        self.assertEqual(request(8083, "/api/packages/@other/package/1.5.0", method="PUT", body=self.package, authorized=True)[0], 403)
        self.assertEqual(request(8083, f"/api/packages/@cinder/delivery-formatter/{self.version}", method="PUT", body=self.package, authorized=True)[0], 409)

    def test_fresh_resolution_and_receipts(self) -> None:
        self.assertEqual(self.baseline["selected_version"], "1.4.0")
        self.assertNotIn("rehearsal_marker", self.baseline["output"])
        self.assertEqual(self.fresh["selected_version"], self.version)
        self.assertEqual(self.fresh["package_digest"], self.publication["digest"])
        self.assertEqual(self.fresh["output"]["rehearsal_marker"], "Cinder rehearsal")
        self.assertEqual(self.fresh["output"]["summary"], "DL-204 | Cinder receiving desk | 3 parcels")
        status, receipts = request(8084, "/api/consumer/receipts")
        self.assertEqual(status, 200)
        self.assertEqual([row["receipt_id"] for row in receipts["receipts"]], ["CR-000001", "CR-000002"])

    def test_consumer_rejects_nonempty_control_body(self) -> None:
        self.assertEqual(request(8084, "/api/consumer/run", method="POST", body={"version": self.version})[0], 400)
        self.assertEqual(request(8084, "/api/rehearsal/ingest", method="POST", body={})[0], 405)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    arguments, remaining = parser.parse_known_args()
    HOST = arguments.host
    unittest.main(argv=[__file__, *remaining])
