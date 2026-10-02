#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timezone


CLIENT = "cinder-arwc-connector"
CONTRACTORS = "cinder-arwc-contractors"
BRIDGE = "cinder-arwc-contractor-bridge"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def json_request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
                 token: str = "@session") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, urllib.error, urllib.request
method,url,supplied,body=sys.argv[1:]
if supplied=="@session": supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":"arwc"}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, method, base + path, token,
                       "" if body is None else json.dumps(body, separators=(",", ":")))
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def cbor_text(value: str) -> bytes:
    encoded = value.encode()
    if len(encoded) < 24:
        return bytes([0x60 + len(encoded)]) + encoded
    if len(encoded) < 256:
        return b"\x78" + bytes([len(encoded)]) + encoded
    raise ValueError("test text too long")


def cbor_map(value: dict[str, str]) -> bytes:
    if len(value) >= 24:
        raise ValueError("test map too large")
    return bytes([0xA0 + len(value)]) + b"".join(
        cbor_text(key) + cbor_text(item) for key, item in value.items()
    )


def cbor_request(path: str, body: bytes, token: str) -> tuple[int, dict]:
    script = r'''
import json,ssl,sys,urllib.error,urllib.request
url,token=sys.argv[1:]
data=sys.stdin.buffer.read()
headers={"Authorization":"Bearer "+token,"X-ARWC-Tenant":"arwc","Content-Type":"application/cbor"}
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method="POST"),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, "python3", "-c", script,
         "https://field-gateway.arwc.test" + path, token],
        input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


class W14Live(unittest.TestCase):
    session = ""

    @classmethod
    def setUpClass(cls) -> None:
        status, response = json_request(
            "https://contractor-portal.arwc.test", "/api/checked-in-as-the-contractor",
            method="POST", body={"appointment_id": "APT-CRR-2026-09-18",
                                  "roster_id": "ROSTER-CRR-SEP18-R2",
                                  "identity": "veybridge.tech.204"},
        )
        if status != 201:
            raise AssertionError(response)
        cls.session = response["contractor_session"]

    def test_01_field_bag_requires_scoped_session_and_is_exact(self) -> None:
        status, body = json_request("https://contractor-portal.arwc.test", "/api/the-field-bag", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("FIELD-BAG-CRR-4417-R3", json.dumps(body))
        status, response = json_request("https://contractor-portal.arwc.test", "/api/the-field-bag",
                                        token=type(self).session)
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "FIELD-BAG-CRR-4417-R3")
        self.assertEqual(record["inspection"], "INSP-CRR-2026-09-18")
        self.assertEqual(record["expected_outlets"], ["OG-CRR-02"])
        self.assertEqual(record["retained_client"]["protocol"], "fieldbag/v1")
        self.assertEqual(record["retained_client"]["encoding"], "application/json")

    def test_02_manifest_distinguishes_retired_and_current_services(self) -> None:
        status, body = json_request("https://field-gateway.arwc.test", "/api/the-service-that-replaced-it",
                                    token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("process-read/v2", json.dumps(body))
        status, response = json_request("https://field-gateway.arwc.test", "/api/the-service-that-replaced-it",
                                        token=type(self).session)
        self.assertEqual(status, 200)
        self.assertEqual(response["record"]["revision"], 21)
        self.assertEqual(response["record"]["services"], [
            {"host": "field-read-legacy.arwc.test", "protocol": "fieldbag/v1", "status": "retired"},
            {"host": "process-read.arwc.test", "protocol": "process-read/v2", "status": "active",
             "encoding": "application/cbor", "authentication": "inspection-scoped"},
        ])

    def test_03_v1_json_and_wrong_scope_are_rejected(self) -> None:
        status, body = json_request(
            "https://field-gateway.arwc.test", "/api/a-fresh-reading-from-the-field", method="POST",
            token=type(self).session,
            body={"asset_id": "AST-CRR-017", "outlet_group": "OG-CRR-02", "sample_time": "now"},
        )
        self.assertEqual(status, 409)
        self.assertNotIn("FIT-CRR-204A", json.dumps(body))
        request = {"asset": "AST-CRR-017", "group": "OG-MER-04",
                   "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                   "nonce": "scope-denial-1"}
        status, body = cbor_request("/api/a-fresh-reading-from-the-field", cbor_map(request), type(self).session)
        self.assertEqual(status, 409)
        self.assertNotIn("FIT-CRR-204A", json.dumps(body))

    def test_04_real_cbor_request_returns_only_current_inspection_reading(self) -> None:
        observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        request = {"asset": "AST-CRR-017", "group": "OG-CRR-02", "observed_at": observed,
                   "nonce": "accepted-reading-1"}
        status, response = cbor_request("/api/a-fresh-reading-from-the-field", cbor_map(request),
                                        type(self).session)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "FEED-OG2-R21", "revision": 21,
            "inspection": "INSP-CRR-2026-09-18", "asset": "AST-CRR-017",
            "group": "OG-CRR-02", "observed_at": observed, "nonce": "accepted-reading-1",
            "observations": [{"instrument": "FIT-CRR-204A", "flow_lps": 0.0},
                             {"instrument": "FIT-CRR-204B", "flow_lps": 0.0}],
        })
        status, replay = cbor_request("/api/a-fresh-reading-from-the-field", cbor_map(request),
                                      type(self).session)
        self.assertEqual(status, 409)
        self.assertNotIn("observations", replay)

    def test_05_gateway_result_and_audit_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", BRIDGE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, _ = json_request("https://field-gateway.arwc.test", "/api/the-service-that-replaced-it",
                                         token=type(self).session)
                if status == 200:
                    break
            except AssertionError:
                pass
        else:
            self.fail("field gateway did not return after restart")
        state = subprocess.run(
            ["docker", "exec", "--user", "arwc-contractor-bridge", BRIDGE,
             "cat", "/var/lib/arwc-contractor-bridge/state/field-gateway.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertTrue(json.loads(state)["current_read_observed"])
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-contractor-bridge", BRIDGE,
             "cat", "/var/lib/arwc-contractor-bridge/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertIn('"action":"a-fresh-reading-from-the-field"', audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
