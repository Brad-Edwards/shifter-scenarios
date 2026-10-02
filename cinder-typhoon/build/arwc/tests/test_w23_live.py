#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
import unittest

CLIENT = "cinder-arwc-connector"
BASE = "https://process-view.arwc.test"


def inside(*arguments: str, input_data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
                          input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def request(path: str, *, body: dict, token: str = "@process", tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
url,tenant,supplied,body=sys.argv[1:]
if supplied=="@process": supplied=pathlib.Path("/var/lib/fieldlink-connector/receipts/process-session").read_text().strip()
data=body.encode(); headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant,"Content-Type":"application/json"}
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method="POST"),context=ctx)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, BASE + path, tenant, token,
                       json.dumps(body, separators=(",", ":")))
    if completed.returncode: raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


def issue_process_session() -> None:
    script = r'''
import json,pathlib,ssl,urllib.request
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
corporate=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
planner=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
headers={"Authorization":"Bearer "+corporate,"X-ARWC-Tenant":"arwc"}
contract=json.load(urllib.request.urlopen(urllib.request.Request("https://business-workplace.arwc.test/api/the-integration-s-read-contract",headers=headers),context=ctx))["integration_session"]
payload=json.dumps({"integration_client":"INT-CRR-08","report_binding":"REC-CRR-DP3-17","scope":"OG-CRR-02/read","feed":"FEED-OG2-R21"},separators=(",", ":")).encode()
headers.update({"X-ARWC-Planner-Session":planner,"X-ARWC-Integration-Session":contract,"Content-Type":"application/json"})
request=urllib.request.Request("https://planning-data.arwc.test/api/integration/from-the-report-to-the-live-feed",data=payload,headers=headers,method="POST")
print(json.load(urllib.request.urlopen(request,context=ctx))["process_session"])
'''
    completed = inside("python3", "-c", script)
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    stored = inside("sh", "-c", "umask 077; cat > /var/lib/fieldlink-connector/receipts/process-session",
                    input_data=completed.stdout)
    if stored.returncode:
        raise AssertionError(stored.stderr.decode())


class W23Live(unittest.TestCase):
    initial_state: dict = {}
    exploit = {"estimator": "EST-CRR-23", "operations": [
        {"op": "add", "source_id": "FIT-CRR-204B", "value": 12.4},
        {"op": "add", "source_id": "FIT-CRR-204B", "value": 12.4},
        {"op": "add", "source_id": "PROBE-CRR-23", "value": 0.0},
        {"op": "write-stale", "source_id": "FIT-CRR-204B", "offset": 64, "u32": 1129468466},
    ]}
    control = {"estimator": "EST-CRR-23", "operations": [
        {"op": "remove-duplicate", "source_id": "FIT-CRR-204B"},
        {"op": "add-state", "district_id": "Cairn Reach"},
        {"op": "remove-state", "district_id": "Cairn Reach"},
        {"op": "add-state", "district_id": "Cairn Reach"},
        {"op": "write-stale", "offset": 40, "f64": 13.4},
        {"op": "write-stale", "offset": 48, "u32": 1},
    ]}
    final = {"allocation_case": "ALLOC-CASE-CRR-33", "district_id": "Cairn Reach",
             "reserve_ml": 13.4, "quality": 1,
             "unaffected": {"North": 8.1, "Merewick": 7.65}}

    @classmethod
    def setUpClass(cls) -> None:
        cls.initial_state = json.loads(subprocess.check_output([
            "docker", "exec", "--user", "arwc-diagnostics", "cinder-arwc-diagnostics",
            "cat", "/var/lib/arwc-diagnostics/state/service.json",
        ], text=True))
        for field in ("side_effect_observed", "protected_state_controlled",
                      "false_estimate_observed"):
            if cls.initial_state[field]:
                raise AssertionError(f"W23 state is not pristine: {field}")
        issue_process_session()

    def test_01_real_estimator_baseline_is_exact_and_authorized(self) -> None:
        denied, result = request("/api/a-measurement-with-side-effects",
                                 body={"estimator": "EST-CRR-23", "mode": "baseline"}, token="wrong")
        self.assertEqual(denied, 403); self.assertNotIn("ELF", json.dumps(result))
        status, result = request("/api/a-measurement-with-side-effects",
                                 body={"estimator": "EST-CRR-23", "mode": "baseline"})
        self.assertEqual(status, 201)
        artifact = base64.b64decode(result["artifact_b64"], validate=True)
        self.assertTrue(artifact.startswith(b"\x7fELF\x02\x01\x01"))
        self.assertEqual(hashlib.sha256(artifact).hexdigest(), result["record"]["sha256"])
        self.assertEqual(result["record"]["object_size"], 0x90)
        deployed = subprocess.check_output([
            "docker", "exec", "--user", "arwc-diagnostics", "cinder-arwc-diagnostics",
            "cat", "/opt/diagnostic-services/artifacts/estimator23",
        ])
        self.assertEqual(artifact, deployed)
        run = subprocess.run([
            "docker", "exec", "--user", "arwc-diagnostics", "cinder-arwc-diagnostics",
            "/opt/diagnostic-services/artifacts/estimator23", "--ordinary",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        self.assertEqual(run.stdout.decode().strip(), "EST-CRR-23 Cairn=12.40 North=8.10 Merewick=7.65 quality=valid")
        uaf = subprocess.run([
            "docker", "exec", "--user", "arwc-diagnostics", "cinder-arwc-diagnostics",
            "/opt/diagnostic-services/artifacts/estimator23",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(uaf.returncode, 0, uaf.stderr.decode())
        stale, replacement = uaf.stdout.decode().strip().split()
        self.assertEqual(stale.removeprefix("stale="), replacement.removeprefix("replacement="))
        libc = subprocess.check_output(["docker", "exec", "cinder-arwc-diagnostics", "ldd", "--version"], text=True)
        self.assertIn("2.39", libc.splitlines()[0])

    def test_02_duplicate_coalescing_produces_controlled_side_effect(self) -> None:
        wrong = json.loads(json.dumps(self.exploit)); wrong["operations"][3]["offset"] = 65
        status, _ = request("/api/a-measurement-with-side-effects", body=wrong)
        self.assertEqual(status, 409)
        status, result = request("/api/a-measurement-with-side-effects", body=self.exploit)
        self.assertEqual(status, 201)
        self.assertEqual(result["record"]["controlled_offset"], 64)
        self.assertTrue(result["record"]["estimator_usable"])

    def test_03_tcache_reuse_writes_only_declared_state_fields(self) -> None:
        wrong = json.loads(json.dumps(self.control)); wrong["operations"].append({"op": "write-stale", "offset": 8, "u32": 0})
        status, _ = request("/api/control-beyond-the-measurement", body=wrong)
        self.assertEqual(status, 409)
        status, result = request("/api/control-beyond-the-measurement", body=self.control)
        self.assertEqual(status, 201)
        record = result["record"]
        self.assertEqual(record["writable_offsets"], [40, 48])
        self.assertEqual(record["district_id"], "Cairn Reach")
        self.assertEqual(record["vtable"], "EST-STATE-V1")
        self.assertEqual(record["reserve_ml"], 13.4)

    def test_04_false_estimate_preserves_unaffected_observations(self) -> None:
        status, result = request("/api/a-measurement-that-never-existed", body=self.final)
        self.assertEqual(status, 201)
        record = result["record"]
        self.assertTrue(record["sufficient"]); self.assertEqual(record["quality"], "valid")
        self.assertEqual(record["estimate"], {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65})
        self.assertFalse(record["raw_process_observations_changed"])
        self.assertFalse(record["independent_instruments_changed"])

    def test_05_owned_state_and_audit_persist(self) -> None:
        subprocess.run(["docker", "restart", "cinder-arwc-diagnostics"], stdout=subprocess.DEVNULL, check=True)
        for _ in range(80):
            try:
                status, _ = request("/api/a-measurement-that-never-existed", body=self.final)
                if status == 201: break
            except AssertionError: pass
            time.sleep(0.25)
        else: self.fail("diagnostic service did not return after restart")
        state = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/state/service.json"], text=True))
        expected = dict(type(self).initial_state)
        expected.update({
            "side_effect_observed": True, "protected_state_controlled": True,
            "false_estimate_observed": True,
        })
        self.assertEqual(state, expected)
        audit = subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/audit/events.jsonl"], text=True)
        self.assertIn("a-measurement-that-never-existed", audit)


if __name__ == "__main__": unittest.main(verbosity=2)
