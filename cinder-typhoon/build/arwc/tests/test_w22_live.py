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
    completed = inside("python3", "-c", script, method, BASE + path, tenant, token,
                       "" if body is None else json.dumps(body, separators=(",", ":")))
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


def establish_access() -> None:
    script = r'''
import json,pathlib,ssl,urllib.request
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
corporate=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
planner=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
headers={"Authorization":"Bearer "+corporate,"X-ARWC-Tenant":"arwc"}
contract=json.load(urllib.request.urlopen(urllib.request.Request("https://business-workplace.arwc.test/api/the-integration-s-read-contract",headers=headers),context=ctx))["integration_session"]
payload=json.dumps({"integration_client":"INT-CRR-08","report_binding":"REC-CRR-DP3-17","scope":"OG-CRR-02/read","feed":"FEED-OG2-R21"},separators=(",", ":")).encode()
headers.update({"X-ARWC-Planner-Session":planner,"X-ARWC-Integration-Session":contract,"Content-Type":"application/json"})
req=urllib.request.Request("https://planning-data.arwc.test/api/integration/from-the-report-to-the-live-feed",data=payload,headers=headers,method="POST")
print(json.load(urllib.request.urlopen(req,context=ctx))["process_session"])
'''
    completed = inside("python3", "-c", script)
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    token = completed.stdout.decode().strip()
    completed = inside("sh", "-c", "umask 077; cat > /var/lib/fieldlink-connector/receipts/process-session",
                       input_data=(token + "\n").encode())
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    request("/api/the-project-and-the-note")
    digest = hashlib.sha256(b"CRR-CTRL-R21/deployed").hexdigest()
    status, result = request("/api/which-project-is-running", method="POST", body={
        "project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": "CRR-CTRL-R19",
        "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": "CRR-CTRL-R21",
        "observed_digest": digest,
    })
    if status != 201:
        raise AssertionError(result)


def run_vm(program: bytes) -> tuple[list[int], bytes, int]:
    registers = [0, 0, 0, 0]
    memory = bytearray(256)
    zero = False
    pc = steps = 0
    while 0 <= pc < len(program) // 6 and steps < 4096:
        opcode, dst, src, immediate = struct.unpack_from("<HBBH", program, pc * 6)
        steps += 1
        if opcode == 1:
            registers[dst] = immediate; zero = registers[dst] == 0; pc += 1
        elif opcode == 2:
            registers[dst] = memory[(registers[src] + immediate) & 255]; zero = registers[dst] == 0; pc += 1
        elif opcode == 3:
            registers[dst] = (registers[dst] ^ registers[src] ^ immediate) & 65535; zero = registers[dst] == 0; pc += 1
        elif opcode == 4:
            registers[dst] = (registers[dst] + registers[src] + immediate) & 65535; zero = registers[dst] == 0; pc += 1
        elif opcode == 5:
            shift = immediate & 15; value = registers[src]
            registers[dst] = value if not shift else ((value << shift) | (value >> (16 - shift))) & 65535
            zero = registers[dst] == 0; pc += 1
        elif opcode == 6:
            memory[(registers[dst] + immediate) & 255] = registers[src] & 255; pc += 1
        elif opcode == 7:
            pc = pc + struct.unpack("<h", struct.pack("<H", immediate))[0] if not zero else pc + 1
        elif opcode == 255:
            break
        else:
            raise AssertionError(opcode)
    return registers, bytes(memory), steps


def public(program: bytes) -> dict:
    registers, memory, steps = run_vm(program)
    return {"registers": registers,
            "memory_40_80_sha256": hashlib.sha256(memory[0x40:0x80]).hexdigest(),
            "steps": steps}


class W22Live(unittest.TestCase):
    delivery: dict = {}
    key = b""
    helper_sha256 = ""
    review_request: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        establish_access()

    def test_01_delivery_is_bound_and_viewer_executes(self) -> None:
        denied, body = request("/api/the-viewer-in-the-delivery", token="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("VIEW-CRR-R5", json.dumps(body))
        status, response = request("/api/the-viewer-in-the-delivery")
        self.assertEqual(status, 200)
        type(self).delivery = response
        record = response["record"]
        self.assertEqual(record["viewer_language"], "Nim 2.0.8")
        self.assertEqual(record["project_id"], "CRR-SEALED-PKG-R7")
        viewer = base64.b64decode(response["viewer_b64"], validate=True)
        program = base64.b64decode(response["program_b64"], validate=True)
        package = base64.b64decode(response["package_b64"], validate=True)
        self.assertTrue(viewer.startswith(b"\x7fELF\x02\x01\x01"))
        self.assertEqual(hashlib.sha256(viewer).hexdigest(), record["viewer_sha256"])
        self.assertEqual(hashlib.sha256(program).hexdigest(), record["program_sha256"])
        self.assertEqual(hashlib.sha256(package).hexdigest(), record["package_sha256"])
        for name, data, mode in (("sealed-viewer", viewer, 0o700), ("viewer-program.bin", program, 0o600)):
            writer = inside("python3", "-c", f"import os,sys;p='/var/lib/fieldlink-connector/{name}';open(p,'wb').write(sys.stdin.buffer.read());os.chmod(p,{mode})", input_data=data)
            self.assertEqual(writer.returncode, 0, writer.stderr.decode())
        executed = inside("/var/lib/fieldlink-connector/sealed-viewer", "/var/lib/fieldlink-connector/viewer-program.bin")
        self.assertEqual(executed.returncode, 0, executed.stderr.decode())
        observed = json.loads(executed.stdout)
        registers, memory, steps = run_vm(program)
        self.assertEqual(observed["registers"], registers)
        self.assertEqual(observed["memory_40_80"], list(memory[0x40:0x80]))
        self.assertEqual(observed["steps"], steps)

    def test_02_machine_requires_all_four_exact_state_effects(self) -> None:
        cases = self.delivery["record"]["ordinary_cases"]
        results = [public(base64.b64decode(case["program_b64"])) for case in cases]
        wrong, _ = request("/api/the-machine-inside-the-viewer", method="POST", body={"cases": results[:-1]})
        self.assertEqual(wrong, 409)
        status, response = request("/api/the-machine-inside-the-viewer", method="POST", body={"cases": results})
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["instruction_limit"], 4096)
        self.assertEqual(len(response["record"]["cases"]), 4)

    def test_03_vm_key_opens_one_project_without_partial_failure(self) -> None:
        program = base64.b64decode(self.delivery["program_b64"])
        registers, memory, _ = run_vm(program)
        material = b"CRR-SEALED-PKG-R7\0" + memory[0x40:0x80] + b"".join(struct.pack("<H", r) for r in registers)
        type(self).key = hashlib.sha256(material).digest()
        wrong, first = request("/api/the-decision-inside-the-sealed-project", method="POST",
                               body={"project_id": "CRR-SEALED-PKG-R7", "key_hex": "00" * 32})
        wrong_project, second = request("/api/the-decision-inside-the-sealed-project", method="POST",
                                        body={"project_id": "other", "key_hex": self.key.hex()})
        self.assertEqual((wrong, wrong_project), (409, 409))
        self.assertEqual(first, second)
        self.assertNotIn("DEC-CRR", json.dumps(first))
        status, response = request("/api/the-decision-inside-the-sealed-project", method="POST",
                                   body={"project_id": "CRR-SEALED-PKG-R7", "key_hex": self.key.hex()})
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["record_id"], "DEC-CRR-OG2-R7")
        self.assertEqual(response["record"]["project"], "CRR-CTRL-R21")
        helper = base64.b64decode(response["review_helper_b64"], validate=True)
        self.assertTrue(helper.startswith(b"MZ"))
        self.assertIn("mara.stone-review".encode("utf-16le"), helper)
        type(self).helper_sha256 = hashlib.sha256(helper).hexdigest()
        self.assertEqual(self.helper_sha256, response["review_helper_sha256"])

    def test_04_concealed_native_reviewer_has_historical_scope_only(self) -> None:
        type(self).review_request = {
            "helper_sha256": self.helper_sha256, "reviewer": "elias.vorn-review",
            "session": "ARCHIVE-REVIEW-R7-ELIAS", "comparison": "CMP-CRR-R21-R7",
            "project": "CRR-CTRL-R21",
        }
        wrong, _ = request("/api/the-reviewer-who-was-never-listed", method="POST",
                           body={**self.review_request, "reviewer": "mara.stone-review"})
        self.assertEqual(wrong, 409)
        status, response = request("/api/the-reviewer-who-was-never-listed", method="POST",
                                   body=self.review_request)
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["record_id"], "CMP-CRR-R21-R7")
        self.assertTrue(record["historical"])
        self.assertFalse(record["current_identity"])
        self.assertFalse(record["maintenance_approval"])
        self.assertFalse(record["control_authority"])

    def test_05_results_and_audits_persist_while_sources_stay_immutable(self) -> None:
        subprocess.run(["docker", "restart", "cinder-arwc-engineering"],
                       stdout=subprocess.DEVNULL, check=True)
        for _ in range(80):
            try:
                status, response = request("/api/the-reviewer-who-was-never-listed", method="POST",
                                           body=self.review_request)
                if status == 201:
                    break
            except AssertionError:
                pass
            time.sleep(0.25)
        else:
            self.fail("engineering service did not return after restart")
        status, delivery = request("/api/the-viewer-in-the-delivery")
        self.assertEqual(status, 200)
        self.assertEqual(delivery["record"]["package_sha256"], self.delivery["record"]["package_sha256"])
        state = subprocess.check_output([
            "docker", "exec", "--user", "arwc-engineering", "cinder-arwc-engineering",
            "cat", "/var/lib/arwc-engineering/state/service.json",
        ], text=True)
        self.assertTrue(json.loads(state)["concealed_reviewer_used"])
        audits = subprocess.check_output([
            "docker", "exec", "--user", "arwc-engineering", "cinder-arwc-engineering",
            "cat", "/var/lib/arwc-engineering/audit/events.jsonl",
        ], text=True)
        self.assertIn("the-reviewer-who-was-never-listed", audits)


if __name__ == "__main__":
    unittest.main(verbosity=2)
