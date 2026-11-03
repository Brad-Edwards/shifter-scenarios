#!/usr/bin/env python3
"""Operator-side black-box checks for the retained policy compiler."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import time
import unittest

from runtime_credentials import basic


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
BASE = "https://source.keplerops.test"
USER = basic()
EXPECTED_COMMIT = "2c83d6cc2a908f8403c1f8f474c4b47c3e06ad58"
EXPECTED_BINARY = "0430d3a1b648f1ee67d51bfe6012f001f2025b896f1c84358922d99b272e8b1e"
EXPECTED_PROGRAM = "0b9a7fd08148ec1b6d3151dcd9c0499fb89f70585fb3705a44662e062242ef9c"
EXPECTED_CONDITIONS = "e3a8ced4d68bfa6f4b94386b5ff040596bff56e243adbb5aebc98df1b21896a9"
EXPECTED_CORPUS = "cf60e746abf133754466b724318419da127e1c7cb3ee74f48ae432cfd74e601a"


def rowan(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def request(path: str, *extra: str, expected: int = 200, credentials: str = USER) -> bytes:
    command = [
        "curl", "-sS", "--cacert", CA, "-o", "/tmp/k11-response", "-w", "%{http_code}",
        "-u", credentials, *extra, BASE + path,
    ]
    result = rowan(*command, check=False)
    status = int(result.stdout)
    body = rowan("cat", "/tmp/k11-response").stdout
    if status != expected:
        raise AssertionError(f"{path} returned {status}: {body.decode(errors='replace')}")
    return body


def request_json(path: str, *extra: str, expected: int = 200, credentials: str = USER) -> dict[str, object]:
    return json.loads(request(path, *extra, expected=expected, credentials=credentials))


def post(value: dict[str, object], expected: int = 200, credentials: str = USER) -> dict[str, object]:
    return request_json(
        "/api/policy-compilers/fieldkest-policyc/evaluations", "-H", "Content-Type: application/json",
        "--data-binary", json.dumps(value, separators=(",", ":")),
        expected=expected, credentials=credentials,
    )


def recover_opcode_model(binary: bytes) -> dict[str, object]:
    recovered = {
        f"0x{int(value, 16):02x}": name.decode()
        for value, name in re.findall(
            rb"fieldkest_opcode_([0-9a-f]{2})_([A-Z_]+)\x00", binary
        )
    }
    if len(recovered) != 8:
        raise AssertionError("retained opcode symbols are incomplete")
    return {
        "schema": "fieldkest.policy-opcode-model/v1",
        "instruction_width": 4,
        "opcodes": recovered,
    }


def model(raw: bytes, program_id: str, opcode_model: dict[str, object]) -> dict[str, object]:
    offset = int.from_bytes(raw[4:8], "little")
    count = int.from_bytes(raw[8:10], "little")
    width = int.from_bytes(raw[10:12], "little")
    if raw[:4] != b"FKPC" or offset != 12 or width != 4 or len(raw) != offset + count * width:
        raise AssertionError("invalid retained program table")
    return {
        "schema": "fieldkest.policy-program-model/v1", "program_id": program_id,
        "instruction_width": width, "instruction_count": count,
        "program_base64": base64.b64encode(raw).decode(),
        "program_sha256": hashlib.sha256(raw).hexdigest(),
        "opcode_model": opcode_model,
    }


class K11LiveTest(unittest.TestCase):
    repository = "/home/rowan/work/policy-compiler"
    program_model: dict[str, object]
    opcode_model: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        for _ in range(30):
            probe = rowan(
                "curl", "-sS", "--connect-timeout", "1", "--cacert", CA, "-u", USER,
                BASE + "/api/v1/user/repos", check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError("source service did not become ready")
        rowan("rm", "-rf", cls.repository)
        rowan("git", "clone", BASE + "/fieldkest/policy-compiler.git", cls.repository)
        binary = rowan("cat", cls.repository + "/bin/fieldkest-policyc").stdout
        start = binary.find(b"FKPC")
        if start < 0:
            raise AssertionError("retained program table is absent")
        count = int.from_bytes(binary[start + 8:start + 10], "little")
        raw = binary[start:start + 12 + count * 4]
        cls.opcode_model = recover_opcode_model(binary)
        cls.program_model = model(raw, "FKPC-POLICY-2026-09-R4", cls.opcode_model)

    def test_01_repository_identity_and_program_recovery(self) -> None:
        commit = rowan("git", "-C", self.repository, "rev-parse", "HEAD").stdout.decode().strip()
        binary = rowan("cat", self.repository + "/bin/fieldkest-policyc").stdout
        self.assertEqual(commit, EXPECTED_COMMIT)
        self.assertEqual(hashlib.sha256(binary).hexdigest(), EXPECTED_BINARY)
        self.assertEqual(self.program_model["program_sha256"], EXPECTED_PROGRAM)
        self.assertEqual(len(self.opcode_model["opcodes"]), 8)
        readme = rowan("cat", self.repository + "/README.md").stdout.lower()
        self.assertIn(b"channel and tenant class", readme)

    def test_02_fragment_models_and_malformed_denial(self) -> None:
        cases = {
            "tenant-state": False, "connector-version": False,
            "signer-lineage": False, "compatibility-exception": False,
        }
        for name, accepted in cases.items():
            raw = rowan("cat", f"{self.repository}/fragments/{name}.fkpc").stdout
            request_value = json.loads(
                rowan("cat", f"{self.repository}/api/fragment-{name}.json").stdout
            )
            request_value["program_model"] = model(
                raw, f"FKPC-FRAGMENT-{name.upper()}", self.opcode_model
            )
            result = post(request_value)
            self.assertEqual((result["fragment_id"], result["accepted"]), (name, accepted))
        malformed = json.loads(json.dumps(self.program_model))
        last_opcode = max(malformed["opcode_model"]["opcodes"])
        malformed["opcode_model"]["opcodes"][last_opcode] = "INVALID"
        denied = post({
            "operation": "corpus-check", "program_model": malformed,
            "policy_input": {"corpus_id": "POLICY-CORPUS-2026-09-R4"},
        }, expected=422)
        self.assertEqual(denied["error"], "opcode_model_mismatch")

    def test_03_fixed_corpus_and_context_fields(self) -> None:
        result = post({
            "operation": "corpus-check", "program_model": self.program_model,
            "policy_input": {"corpus_id": "POLICY-CORPUS-2026-09-R4"},
        })
        self.assertEqual(result["case_count"], 16)
        self.assertEqual(result["corpus_result_sha256"], EXPECTED_CORPUS)
        self.assertEqual(result["condition_set_sha256"], EXPECTED_CONDITIONS)

    def test_04_fresh_acceptance_and_nonce_replay(self) -> None:
        nonce = request_json(
            "/api/policy-compilers/fieldkest-policyc/nonces",
            "-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "{}",
            expected=201,
        )["nonce"]
        value = {
            "operation": "accept", "program_model": self.program_model,
            "policy_input": {
                "tenant_state": "active", "connector_api": "3.0.0",
                "signer_lineage": "fieldkest-release-2026", "compatibility_exception": True,
                "channel": "preview", "tenant_class": "field-service", "nonce": nonce,
                "corpus_result_sha256": EXPECTED_CORPUS,
            },
        }
        result = post(value)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["binary_sha256"], EXPECTED_BINARY)
        self.assertEqual(result["evaluated_fields"], [
            "tenant_state", "connector_api", "signer_lineage", "compatibility_exception",
        ])
        replay = post(value, expected=422)
        self.assertEqual(replay["error"], "stale_or_replayed_nonce")

    def test_05_authorization_and_scope_denials(self) -> None:
        denied = request_json(
            "/api/policy-compilers/fieldkest-policyc/nonces",
            "-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "{}",
            expected=401, credentials="rowan.ito:wrong",
        )
        self.assertEqual(denied["error"], "authentication_required")
        malformed_nonce = request_json(
            "/api/policy-compilers/fieldkest-policyc/nonces",
            "-X", "POST", "-H", "Content-Type: application/json",
            "--data-binary", '{"unexpected":true}', expected=422,
        )
        self.assertEqual(malformed_nonce["error"], "nonce_request_must_be_empty")
        denied_post = post({
            "operation": "corpus-check", "program_model": self.program_model,
            "policy_input": {"corpus_id": "OTHER-CORPUS"},
        }, expected=422)
        self.assertEqual(denied_post["error"], "corpus_binding_mismatch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
