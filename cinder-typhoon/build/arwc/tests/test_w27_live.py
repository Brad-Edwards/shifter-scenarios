#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import struct
import subprocess
import time
import unittest
from datetime import datetime, timezone


CLIENT = "cinder-arwc-connector"
PROCESS = "https://process-view.arwc.test"
MASK128 = (1 << 128) - 1
IV = int("6a09e667f3bcc908bb67ae8584caa73b", 16)


def inside(*arguments: str, binary_input: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        input=binary_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        text=binary_input is None,
    )


def request(base: str, path: str, *, method: str = "GET", body: dict | None = None,
            token: str = "@corporate", tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,body=sys.argv[1:]
if supplied=="@corporate": supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, method, base + path, tenant, token,
                       "" if body is None else json.dumps(body, separators=(",", ":")))
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def cbor_text(value: str) -> bytes:
    encoded = value.encode()
    if len(encoded) < 24:
        return bytes([0x60 + len(encoded)]) + encoded
    return b"\x78" + bytes([len(encoded)]) + encoded


def cbor_map(value: dict[str, str]) -> bytes:
    return bytes([0xA0 + len(value)]) + b"".join(
        cbor_text(key) + cbor_text(item) for key, item in value.items()
    )


def field_read(body: bytes, token: str) -> tuple[int, dict]:
    script = r'''
import json,ssl,sys,urllib.error,urllib.request
token=sys.argv[1]; data=sys.stdin.buffer.read()
headers={"Authorization":"Bearer "+token,"X-ARWC-Tenant":"arwc","Content-Type":"application/cbor"}
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request("https://field-gateway.arwc.test/api/a-fresh-reading-from-the-field",data=data,headers=headers,method="POST"),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, token, binary_input=body)
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


def rotl128(value: int, count: int) -> int:
    return ((value << count) | (value >> (128 - count))) & MASK128


def rot128(data: bytes) -> int:
    length = len(data)
    material = data + b"\x80"
    material += b"\0" * ((-len(material)) % 16)
    state = IV
    for offset in range(0, len(material), 16):
        block = int.from_bytes(material[offset:offset + 16], "little")
        state = rotl128(state, 17) ^ block ^ rotl128(block, 41)
    return (state ^ rotl128(state, 29) ^ length) & MASK128


def solve_collision(seed: bytes, base: bytes, reservoir_bits: list[int]) -> bytes:
    target = rot128(seed) ^ rot128(base)
    basis: dict[int, tuple[int, int]] = {}
    for bit in reservoir_bits:
        changed = bytearray(seed); changed[bit // 8] ^= 1 << (bit % 8)
        vector, mask = rot128(bytes(changed)) ^ rot128(seed), 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                vector ^= basis[pivot][0]; mask ^= basis[pivot][1]
            else:
                basis[pivot] = vector, mask
                break
    solution, vector = 0, target
    while vector:
        pivot = vector.bit_length() - 1
        if pivot not in basis:
            raise AssertionError(f"GF(2) system cannot reduce pivot {pivot}")
        vector ^= basis[pivot][0]; solution ^= basis[pivot][1]
    candidate = bytearray(seed)
    for bit in reservoir_bits:
        if solution & (1 << bit):
            candidate[bit // 8] ^= 1 << (bit % 8)
    result = bytes(candidate)
    if result == base or rot128(result) != rot128(base):
        raise AssertionError("collision solver did not produce a non-identical collision")
    return result


class W27Live(unittest.TestCase):
    process_session = ""
    materials: dict = {}
    contract: dict = {}
    base_program = b""
    target_program = b""

    @classmethod
    def setUpClass(cls) -> None:
        portal = "https://contractor-portal.arwc.test"
        _, appointment = request(portal, "/api/window-on-thursday")
        request(portal, "/api/who-is-expected-at-the-gate")
        if appointment["record"]["attendee"] != "veybridge.tech.204":
            status, result = request(portal, "/api/an-appointment-we-do-not-own", method="POST", body={
                "appointment_id": "APT-CRR-2026-09-18",
                "expected_revision": appointment["record"]["revision"],
                "attendee": "veybridge.tech.204",
                "caller_organization": "Veybridge Technical Services",
            })
            if status != 201:
                raise AssertionError(result)
        status, result = request(portal, "/api/checked-in-as-the-contractor", method="POST", body={
            "appointment_id": "APT-CRR-2026-09-18", "roster_id": "ROSTER-CRR-SEP18-R2",
            "identity": "veybridge.tech.204",
        })
        if status != 201:
            raise AssertionError(result)
        contractor = result["contractor_session"]
        status, result = request(portal, "/api/the-field-bag", token=contractor)
        if status != 200:
            raise AssertionError(result)
        status, result = request("https://field-gateway.arwc.test", "/api/the-service-that-replaced-it",
                                 token=contractor)
        if status != 200:
            raise AssertionError(result)
        observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        status, result = field_read(cbor_map({
            "asset": "AST-CRR-017", "group": "OG-CRR-02", "observed_at": observed,
            "nonce": f"w27-{time.time_ns():x}",
        }), contractor)
        if status != 201:
            raise AssertionError(result)
        cls.process_session = result["process_session"]
        status, result = request(PROCESS, "/api/the-project-and-the-note", token=cls.process_session)
        if status != 200:
            raise AssertionError(result)
        binding = {
            "project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": "CRR-CTRL-R19",
            "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": "CRR-CTRL-R21",
            "observed_digest": hashlib.sha256(b"CRR-CTRL-R21/deployed").hexdigest(),
        }
        status, result = request(PROCESS, "/api/which-project-is-running", method="POST",
                                 body=binding, token=cls.process_session)
        if status != 201:
            raise AssertionError(result)

    def process(self, path: str, body: dict, *, token: str | None = None,
                tenant: str = "arwc") -> tuple[int, dict]:
        return request(PROCESS, path, method="POST", body=body,
                       token=type(self).process_session if token is None else token, tenant=tenant)

    def test_01_native_verifier_and_six_programs_freeze_rot128(self) -> None:
        status, denied = self.process("/api/what-counts-as-intact", {
            "operation": "materials", "record_id": "VER-ROT128-R3",
        }, token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("verifier_b64", denied)
        status, denied = self.process("/api/what-counts-as-intact", {
            "operation": "materials", "record_id": "VER-ROT128-R3",
        }, tenant="merewick")
        self.assertEqual(status, 403)
        status, result = self.process("/api/what-counts-as-intact", {
            "operation": "materials", "record_id": "VER-ROT128-R3",
        })
        self.assertEqual(status, 201, result)
        self.assertEqual(result["record"]["program_count"], 6)
        verifier = base64.b64decode(result["verifier_b64"])
        self.assertEqual(hashlib.sha256(verifier).hexdigest(), result["record"]["verifier_sha256"])
        writer = r'''
import base64,json,pathlib,sys
root=pathlib.Path('/var/lib/fieldlink-connector/receipts/w27'); root.mkdir(mode=0o700,exist_ok=True)
value=json.loads(sys.argv[1]); (root/'rot128-verifier').write_bytes(base64.b64decode(value['verifier']))
(root/'rot128-verifier').chmod(0o700)
for item in value['programs']: (root/item['filename']).write_bytes(base64.b64decode(item['program_b64']))
'''
        completed = inside("python3", "-c", writer, json.dumps({
            "verifier": result["verifier_b64"], "programs": result["programs"],
        }, separators=(",", ":")))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        reproduced = []
        for item in result["programs"]:
            data = base64.b64decode(item["program_b64"])
            completed = inside("/var/lib/fieldlink-connector/receipts/w27/rot128-verifier",
                               "/var/lib/fieldlink-connector/receipts/w27/" + item["filename"])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            native = json.loads(completed.stdout)
            self.assertEqual(native["digest"], f"{rot128(data):032x}")
            reproduced.append({"case_id": item["case_id"], "digest": native["digest"],
                               "decision": native["decision"]})
        self.assertEqual([row["decision"] for row in reproduced],
                         ["accepted", "rejected", "rejected", "rejected", "rejected", "rejected"])
        type(self).materials = {"results": reproduced, "programs": result["programs"]}

    def test_02_results_and_real_gf2_model_are_required(self) -> None:
        results = type(self).materials["results"]
        status, _ = self.process("/api/what-counts-as-intact", {
            "operation": "results", "record_id": "VER-ROT128-R3", "program_set": "DPG1-CASES-R3",
            "results": [dict(results[0], decision="rejected"), *results[1:]],
        })
        self.assertEqual(status, 409)
        status, accepted = self.process("/api/what-counts-as-intact", {
            "operation": "results", "record_id": "VER-ROT128-R3", "program_set": "DPG1-CASES-R3",
            "results": list(reversed(results)),
        })
        self.assertEqual(status, 201)
        self.assertEqual(accepted["record"]["cases_verified"], 6)
        status, contract = self.process("/api/the-constraints-of-a-valid-looking-program", {
            "operation": "contract", "record_id": "DPG-CONTRACT-R8",
        })
        self.assertEqual(status, 201)
        record = contract["record"]
        self.assertEqual((record["format"], record["program_length"], record["block_count"]),
                         ("DPG1", 512, 6))
        base = base64.b64decode(contract["base_program_b64"])
        for case in record["distinguishing_cases"]:
            changed = bytearray(base); bit = case["bit"]
            changed[bit // 8] ^= 1 << (bit % 8)
            self.assertEqual(case["delta"], f"{rot128(bytes(changed)) ^ rot128(base):032x}")
        identical = {
            "operation": "model", "record_id": "DPG-MODEL-R8",
            "cases": record["distinguishing_cases"], "program_b64": base64.b64encode(base).decode(),
        }
        status, _ = self.process("/api/the-constraints-of-a-valid-looking-program", identical)
        self.assertEqual(status, 409)
        seed = bytearray(base); seed[48:64] = b"DPG-CRR-MODEL1".ljust(16, b"\0")
        candidate = solve_collision(bytes(seed), base, record["reservoir_bits"])
        status, modeled = self.process("/api/the-constraints-of-a-valid-looking-program", {
            **identical, "program_b64": base64.b64encode(candidate).decode(),
        })
        self.assertEqual(status, 201)
        self.assertTrue(modeled["record"]["nonidentical"])
        self.assertEqual(modeled["record"]["outputs"], {"Cairn Reach": 12.4, "North": 8.1, "Merewick": 7.65})
        type(self).contract = record; type(self).base_program = base

    def test_03_only_cairn_changes_at_the_real_planning_consumer(self) -> None:
        base = type(self).base_program; record = type(self).contract
        seed = bytearray(base); seed[48:64] = b"DPG-CRR-CINDER".ljust(16, b"\0")
        struct.pack_into("<f", seed, 284, 13.4)
        candidate = solve_collision(bytes(seed), base, record["reservoir_bits"])
        malformed = bytearray(candidate); malformed[64] ^= 1
        path = "/api/a-program-the-engineer-would-accept"
        status, _ = self.process(path, {
            "record_id": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8",
            "program_b64": base64.b64encode(malformed).decode(),
        })
        self.assertEqual(status, 409)
        status, result = self.process(path, {
            "record_id": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8",
            "program_b64": base64.b64encode(candidate).decode(),
        })
        self.assertEqual(status, 201, result)
        accepted = result["record"]
        self.assertEqual(accepted["program_id"], "DPG-CRR-CINDER")
        self.assertEqual(accepted["consumer"], "PLAN-CONSUMER-R8")
        self.assertEqual(accepted["estimate"], {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65})
        self.assertFalse(accepted["raw_process_observations_changed"])
        self.assertFalse(accepted["independent_instruments_changed"])
        type(self).target_program = candidate

    def test_04_independently_owned_consumer_evidence_and_persistence(self) -> None:
        consumer = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-data", "cinder-arwc-data", "cat",
             "/var/lib/arwc-data/results/PLAN-CONSUMER-R8.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertEqual(consumer["record_id"], "PLAN-CONSUMER-R8")
        self.assertEqual(consumer["source"], "DPG-CRR-CINDER")
        self.assertEqual(consumer["estimate"]["Cairn Reach"], 13.4)
        self.assertFalse(consumer["raw_process_observations_changed"])
        self.assertFalse(consumer["independent_instruments_changed"])
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-data", "cinder-arwc-data", "cat",
             "/var/lib/arwc-data/audit/events.jsonl"], text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertIn('"action":"diagnostic-estimate-consumed"', audit)
        subprocess.run(["docker", "restart", "cinder-arwc-engineering", "cinder-arwc-diagnostics",
                        "cinder-arwc-data-bridge", "cinder-arwc-data"],
                       check=True, stdout=subprocess.DEVNULL)
        for _ in range(60):
            try:
                state = json.loads(subprocess.run(
                    ["docker", "exec", "--user", "arwc-data", "cinder-arwc-data", "cat",
                     "/var/lib/arwc-data/state/planning.json"],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
                ).stdout)
                if state["diagnostic_estimate_observed"]:
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(0.25)
        else:
            self.fail("planning consumer evidence did not survive restart")
        engineering = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-engineering", "cinder-arwc-engineering", "cat",
             "/var/lib/arwc-engineering/state/service.json"], text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        diagnostics = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-diagnostics", "cinder-arwc-diagnostics", "cat",
             "/var/lib/arwc-diagnostics/state/service.json"], text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertTrue(engineering["w27_verifier_reproduced"] and engineering["w27_collision_modeled"])
        self.assertTrue(diagnostics["colliding_program_accepted"])

    def test_05_service_posture_and_network_boundaries_remain_exact(self) -> None:
        direct = r'''
import ssl,time,urllib.error,urllib.request
headers={"X-ARWC-Internal":"data-bridge-r27","X-ARWC-Tenant":"arwc","Content-Type":"application/json"}
request=urllib.request.Request("https://planning-data.arwc.test/internal/diagnostic-estimate",data=b"{}",headers=headers,method="POST")
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
for attempt in range(60):
 try:
  response=urllib.request.urlopen(request,context=context); break
 except urllib.error.HTTPError as error:
  response=error; break
 except urllib.error.URLError:
  if attempt == 59: raise
  time.sleep(.25)
print(response.status)
'''
        denied = inside("python3", "-c", direct)
        self.assertEqual(denied.returncode, 0, denied.stderr)
        self.assertEqual(denied.stdout.strip(), "403")
        expected = {
            "cinder-arwc-engineering": ("10.77.63.40", "arwc-engineering"),
            "cinder-arwc-diagnostics": ("10.77.63.50", "arwc-diagnostics"),
            "cinder-arwc-data-bridge": ("10.77.62.20", "arwc-data-bridge"),
            "cinder-arwc-data": ("10.77.60.40", "arwc-data"),
        }
        for service, (address, user) in expected.items():
            inspected = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|{{json .HostConfig.SecurityOpt}}|{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}|{{range $p,$b := .NetworkSettings.Ports}}{{if $b}}{{$p}}{{end}}{{end}}",
                service], text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            security = "null" if service == "cinder-arwc-engineering" else '["no-new-privileges:true"]'
            self.assertIn(f'true|["ALL"]|{security}|', inspected)
            self.assertIn(address, inspected)
            self.assertTrue(inspected.endswith("|"))
            capabilities = subprocess.run(
                ["docker", "exec", "--user", user, service, "sh", "-c",
                 "grep -E '^(CapInh|CapPrm|CapEff|CapAmb):' /proc/1/status"],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout
            self.assertEqual({line.split(":", 1)[1].strip() for line in capabilities.splitlines()},
                             {"0000000000000000"})
            for target in ("169.254.169.254", "1.1.1.1"):
                probe = subprocess.run(
                    ["docker", "exec", "--user", user, service, "python3", "-c",
                     f"import socket; socket.create_connection(('{target}',80),1)"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.assertNotEqual(probe.returncode, 0, f"{service} unexpectedly reached {target}")
        utility_capability = subprocess.check_output([
            "docker", "exec", "cinder-arwc-engineering", "getcap",
            "/opt/process-service/artifacts/w28/utility",
        ], text=True).strip()
        self.assertEqual(
            utility_capability,
            "/opt/process-service/artifacts/w28/utility cap_setuid=ep",
        )
        for address in ("10.77.63.40", "10.77.63.50", "10.77.62.20"):
            probe = inside("python3", "-c", f"import socket; socket.create_connection(('{address}',443),1)")
            self.assertNotEqual(probe.returncode, 0, f"connector unexpectedly reached {address}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
