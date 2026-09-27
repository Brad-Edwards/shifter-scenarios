#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import struct
import subprocess
import time
import unittest


CLIENT = "cinder-arwc-connector"
BASE = "https://process-view.arwc.test"
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1
POLY = 0x82F63B78


def inside(*arguments: str, input_data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str = "@process", tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,body=sys.argv[1:]
if supplied=="@process": supplied=pathlib.Path("/var/lib/fieldlink-connector/receipts/process-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status)
print(response.read().decode())
'''
    completed = inside(
        "python3", "-c", script, method, BASE + path, tenant, token,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


def issue_process_session() -> str:
    script = r'''
import json,pathlib,ssl,urllib.request
base="https://business-workplace.arwc.test"
corporate=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
planner=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
req=urllib.request.Request(base+"/api/the-integration-s-read-contract",headers={"Authorization":"Bearer "+corporate,"X-ARWC-Tenant":"arwc"})
contract=json.load(urllib.request.urlopen(req,context=ctx))["integration_session"]
body=json.dumps({"integration_client":"INT-CRR-08","report_binding":"REC-CRR-DP3-17","scope":"OG-CRR-02/read","feed":"FEED-OG2-R21"},separators=(",", ":")).encode()
req=urllib.request.Request("https://planning-data.arwc.test/api/integration/from-the-report-to-the-live-feed",data=body,headers={"Authorization":"Bearer "+corporate,"X-ARWC-Tenant":"arwc","X-ARWC-Planner-Session":planner,"X-ARWC-Integration-Session":contract,"Content-Type":"application/json"},method="POST")
print(json.load(urllib.request.urlopen(req,context=ctx))["process_session"])
'''
    completed = inside("python3", "-c", script)
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    token = completed.stdout.decode().strip()
    stored = inside("sh", "-c", "umask 077; mkdir -p /var/lib/fieldlink-connector/receipts; cat > /var/lib/fieldlink-connector/receipts/process-session", input_data=(token + "\n").encode())
    if stored.returncode:
        raise AssertionError(stored.stderr.decode())
    return token


def rotl(value: int, count: int, width: int) -> int:
    mask = (1 << width) - 1
    return ((value << count) | (value >> (width - count))) & mask


def rolling(record: str) -> int:
    value = 0x6D2B79F5
    for byte in record.encode():
        value = (rotl((value ^ byte) & MASK32, 5, 32) + 0x9E3779B9) & MASK32
    return value


def verifier(record: str) -> int:
    value = rolling(record)
    return rotl(0x243F6A8885A308D3 ^ ((value * 0x100000001B3) & MASK64), 9, 64) ^ value


def crc32c(data: bytes) -> int:
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (POLY if value & 1 else 0)
    return value ^ 0xFFFFFFFF


class W19W20Live(unittest.TestCase):
    image = b""
    image_record: dict = {}
    map_request: dict = {}
    rewrite_request: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        issue_process_session()

    def test_01_w19_package_is_a_real_bound_stripped_elf(self) -> None:
        denied, body = request("/api/the-diagnostic-nobody-retired", token="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("ELF", json.dumps(body))
        status, response = request("/api/the-diagnostic-nobody-retired")
        self.assertEqual(status, 200)
        record = response["record"]
        artifact = base64.b64decode(response["artifact_b64"], validate=True)
        self.assertTrue(artifact.startswith(b"\x7fELF\x02\x01\x01"))
        self.assertEqual(record["record_id"], "DIAG-CRR-MIXED-19")
        self.assertEqual(record["project_family"], "CRR-CTRL-R19")
        self.assertEqual(hashlib.sha256(artifact).hexdigest(), record["sha256"])
        self.assertEqual(len(record["ordinary_traces"]), 4)
        written = inside(
            "python3", "-c",
            "import os,sys; p='/var/lib/fieldlink-connector/diag-crr-mixed-19'; open(p,'wb').write(sys.stdin.buffer.read()); os.chmod(p,0o700)",
            input_data=artifact,
        )
        self.assertEqual(written.returncode, 0, written.stderr.decode())
        executed = inside("/var/lib/fieldlink-connector/diag-crr-mixed-19")
        self.assertEqual(executed.returncode, 0, executed.stderr.decode())
        self.assertEqual(executed.stdout, struct.pack("<Q", verifier("MIG-OG2-R19-R21")))

    def test_02_w19_compatibility_result_requires_32_bit_wrap(self) -> None:
        body = {"record": "WRAP-FFFFFFFF-OG2", "rolling32": f"{rolling('WRAP-FFFFFFFF-OG2'):08x}"}
        wrong, _ = request("/api/a-second-interpretation", method="POST",
                           body={**body, "rolling32": "00000000"})
        self.assertEqual(wrong, 409)
        status, response = request("/api/a-second-interpretation", method="POST", body=body)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["execution"], "i386-compatibility")

    def test_03_w19_hidden_check_requires_all_supplied_decisions(self) -> None:
        records = ["OUTLET_A:800", "OUTLET_B:1200", "LEGACY:4294967295", "CRR:204", "MIG-OG2-R19-R21"]
        decisions = [{"record": item, "rolling32": f"{rolling(item):08x}",
                      "verifier64": f"{verifier(item):016x}"} for item in records]
        wrong, _ = request("/api/the-hidden-check", method="POST", body={"decisions": decisions[:-1]})
        self.assertEqual(wrong, 409)
        status, response = request("/api/the-hidden-check", method="POST", body={"decisions": decisions})
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["record_id"], "MIG-OG2-R19-R21")
        self.assertEqual(response["record"]["decision"], "valid")

    def test_04_w19_mapping_is_historical_and_does_not_replace_revision(self) -> None:
        mapping = {
            "legacy_project": "CRR-CTRL-R19", "current_project": "CRR-CTRL-R21",
            "legacy_identifiers": {"OUTLET_A": "OG-CRR-02/GT-CRR-02A", "OUTLET_B": "OG-CRR-02/GT-CRR-02B"},
            "instruments": {"OUTLET_A": "FIT-CRR-204A", "OUTLET_B": "FIT-CRR-204B"},
        }
        digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        type(self).map_request = {"migration_record": "MIG-OG2-R19-R21",
                                  "comparison_digest": digest, "observation": "EVT-COMM-OG2-114"}
        wrong, _ = request("/api/a-map-from-the-old-diagnostic", method="POST",
                           body={**self.map_request, "observation": "other"})
        self.assertEqual(wrong, 409)
        status, response = request("/api/a-map-from-the-old-diagnostic", method="POST", body=self.map_request)
        self.assertEqual(status, 201)
        self.assertTrue(response["record"]["historical"])
        self.assertNotIn("deployed", response["record"])
        self.assertEqual(response["record"]["legacy_identifiers"]["OUTLET_B"], "OG-CRR-02/GT-CRR-02B")

    def test_05_w20_image_has_exact_nor_records_and_integrity(self) -> None:
        status, response = request("/api/what-the-image-kept")
        self.assertEqual(status, 200)
        type(self).image = base64.b64decode(response["image_b64"], validate=True)
        self.assertEqual(len(self.image), 8192)
        self.assertEqual(hashlib.sha256(self.image).hexdigest(), response["record"]["sha256"])
        self.assertEqual(response["record"]["erase_page_bytes"], 4096)
        target = self.image[64:128]
        self.assertEqual(target[:4], b"F204")
        self.assertEqual(target[63], 0)
        self.assertEqual(crc32c(target[:56]), struct.unpack_from("<I", target, 56)[0])
        payload_length = struct.unpack_from("<H", target, 8)[0]
        record_id, asset, date = target[12:12 + payload_length].decode().split("\0")
        type(self).image_record = {
            "image_sha256": hashlib.sha256(self.image).hexdigest(), "record_id": record_id,
            "asset": asset, "inspection_date": date, "sequence": struct.unpack_from("<I", target, 4)[0],
            "status": "REVIEW", "flags": target[11],
            "crc32c": f"{struct.unpack_from('<I', target, 56)[0]:08x}", "offset": 64,
        }

    def test_06_w20_last_record_requires_full_integrity_interpretation(self) -> None:
        wrong, _ = request("/api/a-valid-maintenance-record", method="POST",
                           body={**self.image_record, "status": "ACCEPTED"})
        self.assertEqual(wrong, 409)
        status, response = request("/api/a-valid-maintenance-record", method="POST", body=self.image_record)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["record_id"], "INSP-FIT-204-118")
        self.assertEqual(response["record"]["status"], "REVIEW")

    def test_07_w20_rewrite_obeys_program_order_and_preserves_every_other_record(self) -> None:
        target = bytearray(b"\xff" * 64)
        payload = b"INSP-FIT-204-118" + b"\0" + b"FIT-CRR-204B" + b"\0" + b"2026-09-18"
        target[:4] = b"F204"
        struct.pack_into("<I", target, 4, 119)
        struct.pack_into("<H", target, 8, len(payload))
        target[10] = 2
        target[11] = 1
        target[12:12 + len(payload)] = payload
        struct.pack_into("<I", target, 56, crc32c(target[:56]))
        target[63] = 0
        candidate = bytearray(self.image)
        candidate[128:184] = target[:56]
        candidate[184:188] = target[56:60]
        candidate[191] = 0
        operations = [
            {"kind": "program", "offset": 128, "data_b64": base64.b64encode(target[:56]).decode()},
            {"kind": "program", "offset": 184, "data_b64": base64.b64encode(target[56:60]).decode()},
            {"kind": "program", "offset": 191, "data_b64": base64.b64encode(b"\0").decode()},
        ]
        type(self).rewrite_request = {"operations": operations,
                                      "image_b64": base64.b64encode(candidate).decode()}
        wrong, _ = request("/api/change-one-record-keep-the-rest", method="POST",
                           body={"operations": list(reversed(operations)),
                                 "image_b64": self.rewrite_request["image_b64"]})
        self.assertEqual(wrong, 409)
        status, response = request("/api/change-one-record-keep-the-rest", method="POST",
                                   body=self.rewrite_request)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["sequence"], 119)
        self.assertEqual(response["record"]["status"], "ACCEPTED")
        self.assertEqual(response["record"]["wear_counts"], [17, 9])
        self.assertFalse(response["record"]["live_telemetry_changed"])

    def test_08_results_audits_and_immutable_inputs_persist(self) -> None:
        subprocess.run(["docker", "restart", "cinder-arwc-engineering", "cinder-arwc-instruments"],
                       stdout=subprocess.DEVNULL, check=True)
        for _ in range(60):
            try:
                status, response = request("/api/a-map-from-the-old-diagnostic", method="POST", body=self.map_request)
                if status == 201:
                    break
            except AssertionError:
                pass
            time.sleep(0.25)
        else:
            self.fail("engineering service did not return after restart")
        for _ in range(60):
            status, response = request(
                "/api/change-one-record-keep-the-rest", method="POST", body=self.rewrite_request,
            )
            if status == 201:
                break
            time.sleep(0.25)
        else:
            self.fail(f"instrument service did not return after restart: {response}")
        status, image = request("/api/what-the-image-kept")
        self.assertEqual(status, 200)
        self.assertEqual(hashlib.sha256(base64.b64decode(image["image_b64"])).hexdigest(),
                         self.image_record["image_sha256"])
        for role in ("engineering", "instruments"):
            audit = subprocess.run(
                ["docker", "exec", "--user", f"arwc-{role}", f"cinder-arwc-{role}",
                 "cat", f"/var/lib/arwc-{role}/audit/events.jsonl"],
                stdout=subprocess.PIPE, check=True,
            ).stdout
            self.assertTrue(audit.strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
