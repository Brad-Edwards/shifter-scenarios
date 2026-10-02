#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
import unittest
import uuid


CLIENT = "cinder-arwc-connector"
ARCHIVE = "cinder-arwc-archive"
BASE = "https://retained-archive.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def json_request(path: str, *, method: str = "GET", body: dict | None = None,
                 token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import base64,json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,body=sys.argv[1:]
if supplied=="@session":
 supplied=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
 response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=context)
except urllib.error.HTTPError as error: response=error
print(response.status)
print(base64.b64encode(response.read()).decode())
'''
    completed = inside(
        "python3", "-c", script, method, BASE + path, tenant,
        "@session" if token is None else token,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(base64.b64decode(payload))


def program(*instructions: tuple[int, int, int, int]) -> str:
    return base64.b64encode(bytes(value for item in instructions for value in item)).decode()


def crc32c(value: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in value:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


class W16Live(unittest.TestCase):
    descriptor: dict = {}
    recovered = b""

    @staticmethod
    def binding(**extra: object) -> dict:
        return {
            "sequencer": "SEQ-CRR-4",
            "revision": 4,
            "request_id": "req-" + uuid.uuid4().hex,
            **extra,
        }

    def measure_byte(self, slot: int) -> int:
        measurements: dict[int, list[int]] = {probe: [] for probe in (0, 1, 2, 4, 8, 16, 32, 64, 128)}
        probes = list(measurements)
        for group in (probes[:7], probes[7:]):
            instructions = [
                (5, slot, probe, 0)
                for probe in group
                for _ in range(8)
            ] + [(7, 0, 0, 0)]
            status, body = json_request(
                "/api/an-experiment-with-a-signal", method="POST",
                body=self.binding(operation="measure", program=program(*instructions)),
            )
            self.assertEqual(status, 201, body)
            for observation in body["record"]["observations"]:
                measurements[observation["probe"]].append(observation["cycles"])
        means = {probe: sum(values) / len(values) for probe, values in measurements.items()}
        value = 0
        for bit in range(8):
            if means[1 << bit] < means[0]:
                value |= 1 << bit
        return value

    def test_01_descriptor_and_baseline_are_exact_and_authorized(self) -> None:
        denied, body = json_request("/api/the-sequencer-s-vocabulary", token="wrong")
        self.assertEqual(denied, 403)
        self.assertNotIn("SEQ-BASE-17", json.dumps(body))
        denied, body = json_request("/api/the-sequencer-s-vocabulary", tenant="other")
        self.assertEqual(denied, 403)
        self.assertNotIn("SEQ-CRR-4", json.dumps(body))

        status, response = json_request("/api/the-sequencer-s-vocabulary")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["sample_slots"], 256)
        self.assertEqual(record["authorized_indices"], list(range(32)))
        self.assertEqual(record["instruction_width"], 4)
        self.assertEqual(record["maximum_instructions"], 64)
        self.assertEqual(record["maximum_experiments"], 4096)
        self.assertEqual(record["opcodes"], {
            "ADD": 3, "HALT": 7, "LOAD": 1, "NOP": 0,
            "ROTL": 4, "STORE": 6, "TEST": 5, "XOR": 2,
        })
        self.assertEqual(record["ordinary_trace"], {
            "record_id": "SEQ-BASE-17", "program_hex": "0104000007000000",
            "result": "authorized-load", "cycles": 228,
        })
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(response["descriptor_sha256"], hashlib.sha256(canonical).hexdigest())
        type(self).descriptor = record

    def test_02_late_authorization_preserves_cycles_but_never_writes(self) -> None:
        before, body = json_request(
            "/api/an-experiment-with-a-signal", method="POST",
            body=self.binding(operation="measure", program=program((5, 4, 0, 0), (7, 0, 0, 0))),
        )
        self.assertEqual(before, 403)

        baseline = self.binding(program=program((1, 4, 0, 0), (7, 0, 0, 0)))
        status, response = json_request(
            "/api/an-observation-outside-the-window", method="POST", body=baseline,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["cycles"], 228)
        self.assertEqual(response["record"]["status"], "completed")

        crossing = self.binding(program=program((1, 160, 0, 0), (7, 0, 0, 0)))
        status, response = json_request(
            "/api/an-observation-outside-the-window", method="POST", body=crossing,
        )
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["status"], "late-authorization-rejection")
        self.assertEqual(record["boundary_index"], 160)
        self.assertIsNone(record["registers"])
        self.assertFalse(record["write_performed"])
        self.assertGreater(record["cycles"], 220)

        replay, _ = json_request(
            "/api/an-observation-outside-the-window", method="POST", body=crossing,
        )
        self.assertEqual(replay, 409)
        for changed in (
            dict(self.binding(program=crossing["program"]), sequencer="SEQ-OTHER"),
            dict(self.binding(program=crossing["program"]), revision=3),
            self.binding(program=program((6, 4, 0, 0), (7, 0, 0, 0))),
            self.binding(program=program((1, 160, 0, 0))),
        ):
            denied, _ = json_request(
                "/api/an-observation-outside-the-window", method="POST", body=changed,
            )
            self.assertEqual(denied, 409)

    def test_03_reference_cases_freeze_signal_interpretation(self) -> None:
        references = {str(slot): self.measure_byte(slot) for slot in (4, 5, 6)}
        target = self.measure_byte(159)
        self.assertEqual(references, {"4": 0, "5": 1, "6": 255})
        self.assertEqual(target, 0xA5)
        wrong, body = json_request(
            "/api/an-experiment-with-a-signal", method="POST",
            body=self.binding(
                operation="verify", reference_values=references, target_slot=159,
                recovered_byte=target ^ 1, repetitions=8, bit_order="lsb0",
            ),
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("SEQ-DISCRIM-CRR-4", json.dumps(body))
        status, response = json_request(
            "/api/an-experiment-with-a-signal", method="POST",
            body=self.binding(
                operation="verify", reference_values=references, target_slot=159,
                recovered_byte=target, repetitions=8, bit_order="lsb0",
            ),
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["independent_conditions"], 8)
        self.assertEqual(response["record"]["repetitions_per_condition"], 8)

    def test_04_complete_calibration_is_recovered_only_through_measurement(self) -> None:
        recovered = bytes(self.measure_byte(slot) for slot in range(160, 192))
        self.assertEqual(len(recovered), 32)
        self.assertEqual(recovered[:2], b"R8")
        self.assertEqual(crc32c(recovered[:28]), int.from_bytes(recovered[28:], "big"))
        type(self).recovered = recovered

        request = self.binding(
            record_id="CAL-CRR-OG2-R8", field_revision="R8",
            calibration=base64.b64encode(recovered).decode(),
        )
        wrong = dict(request, request_id="wrong-" + uuid.uuid4().hex,
                     calibration=base64.b64encode(recovered[:-1] + b"\x00").decode())
        status, body = json_request(
            "/api/what-the-instrument-remembers", method="POST", body=wrong,
        )
        self.assertEqual(status, 409)
        self.assertNotIn("CAL-CRR-OG2-R8", json.dumps(body))
        status, response = json_request(
            "/api/what-the-instrument-remembers", method="POST", body=request,
        )
        self.assertEqual(status, 201)
        record = response["record"]
        self.assertEqual(record["slots"], [160, 191])
        self.assertEqual(record["length"], 32)
        self.assertEqual(record["revision"], 8)
        self.assertEqual(record["sha256"], hashlib.sha256(recovered).hexdigest())

    def test_05_results_audits_and_quota_persist_across_restart(self) -> None:
        state_path = "/var/lib/arwc-archive/state/archive.json"
        audit_path = "/var/lib/arwc-archive/audit/events.jsonl"
        before = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", ARCHIVE, "cat", state_path],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        state = json.loads(before)
        self.assertTrue(state["sequencer_descriptor_observed"])
        self.assertTrue(state["sequencer_boundary_observed"])
        self.assertTrue(state["sequencer_signal_discriminated"])
        self.assertTrue(state["sequencer_calibration_recovered"])
        self.assertGreater(state["sequencer_experiment_count"], 60)
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", ARCHIVE, "cat", audit_path],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        actions = [json.loads(line)["action"] for line in audit.splitlines()]
        self.assertIn("an-observation-outside-the-window", actions)
        self.assertIn("an-experiment-with-a-signal/verify", actions)
        self.assertIn("what-the-instrument-remembers", actions)

        subprocess.run(["docker", "restart", ARCHIVE], stdout=subprocess.DEVNULL, check=True)
        for _ in range(30):
            completed = subprocess.run(
                ["docker", "exec", "--user", "arwc-archive", ARCHIVE, "cat", state_path],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            if completed.returncode == 0 and completed.stdout == before:
                break
        else:
            self.fail("sequencer state did not persist across restart")
        for _ in range(30):
            try:
                status, descriptor = json_request("/api/the-sequencer-s-vocabulary")
                break
            except AssertionError:
                time.sleep(0.25)
        else:
            self.fail("retained archive did not become ready after restart")
        self.assertEqual(status, 200)
        self.assertEqual(descriptor["record"], type(self).descriptor)


if __name__ == "__main__":
    unittest.main(verbosity=2)
