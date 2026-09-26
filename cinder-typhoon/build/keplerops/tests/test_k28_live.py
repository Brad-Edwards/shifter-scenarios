#!/usr/bin/env python3
"""Operator-side black-box checks for the archived connector."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import unittest


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
BASE = "https://source.keplerops.test"
USER = "rowan.ito:kpl_rowan_7X4mQ9vN2cL6"
REPOSITORY = "/home/rowan/work/connector-archive"
EXPECTED_COMMIT = "9b65bd4cea72ef35259fce2b0911a36c058e0688"
EXPECTED_BINARY = "f7f0fa564b984ea001debfb2a250c5dd30f2a63cdd92db887e294f580459a513"


def rowan(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def run_api(input_path: str, config_path: str, expected: int = 200, credentials: str = USER) -> dict[str, object]:
    result = rowan(
        "curl", "-sS", "--cacert", CA, "-o", "/tmp/k28-response", "-w", "%{http_code}",
        "-u", credentials, "-F", f"input=@{input_path};type=application/octet-stream",
        "-F", f"diagnostic_config=@{config_path};type=application/octet-stream",
        BASE + "/api/exercises/connector-archive/run", check=False,
    )
    status = int(result.stdout)
    body = rowan("cat", "/tmp/k28-response").stdout
    if status != expected:
        raise AssertionError(f"archive run returned {status}: {body.decode(errors='replace')}")
    return json.loads(body)


class K28LiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for _ in range(30):
            if rowan("curl", "-sS", "--connect-timeout", "1", "--cacert", CA, "-u", USER, BASE + "/api/v1/user/repos", check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError("source service did not become ready")
        rowan("rm", "-rf", REPOSITORY)
        rowan("git", "clone", BASE + "/fieldkest/connector-archive.git", REPOSITORY)

    def test_01_repository_and_real_binary_modes(self) -> None:
        commit = rowan("git", "-C", REPOSITORY, "rev-parse", "HEAD").stdout.decode().strip()
        binary = rowan("cat", REPOSITORY + "/bin/fieldlink-connector").stdout
        self.assertEqual(commit, EXPECTED_COMMIT)
        self.assertEqual(hashlib.sha256(binary).hexdigest(), EXPECTED_BINARY)
        ordinary = rowan(REPOSITORY + "/bin/fieldlink-connector", "--config", REPOSITORY + "/config/ordinary.conf", "--input", REPOSITORY + "/examples/fieldkest.bin")
        diagnostic = rowan(REPOSITORY + "/bin/fieldlink-connector", "--config", REPOSITORY + "/config/diagnostic.conf", "--input", REPOSITORY + "/examples/fieldkest.bin")
        self.assertEqual(json.loads(ordinary.stdout)["mode"], "ordinary")
        decoded = json.loads(diagnostic.stdout)
        self.assertEqual((decoded["mode"], decoded["route"], decoded["note_id"]), ("diagnostic", "/internal/fieldlink/legacy-diagnostics/CRR-OG2", "ENG-FLK-LEGACY-42"))

    def test_02_bounded_service_corpus(self) -> None:
        outputs = set()
        for name in ("empty", "fieldkest", "bytes-00-0f"):
            result = run_api(REPOSITORY + f"/examples/{name}.bin", REPOSITORY + "/config/diagnostic.conf")
            self.assertEqual((result["mode"], result["route"], result["note_id"]), ("diagnostic", "/internal/fieldlink/legacy-diagnostics/CRR-OG2", "ENG-FLK-LEGACY-42"))
            outputs.add(result["output_sha256"])
        self.assertEqual(len(outputs), 3)
        ordinary = run_api(REPOSITORY + "/examples/fieldkest.bin", REPOSITORY + "/config/ordinary.conf")
        self.assertEqual((ordinary["mode"], ordinary["interface"]), ("ordinary", "fieldkest.connector/v2"))

    def test_03_signature_authentication_and_authorization(self) -> None:
        rowan("sh", "-c", f"sed s/true/false/ {REPOSITORY}/config/diagnostic.conf > /tmp/tampered.conf")
        rejected = run_api(REPOSITORY + "/examples/fieldkest.bin", "/tmp/tampered.conf", expected=422)
        self.assertEqual(rejected["error"], "connector_run_rejected")
        denied = run_api(REPOSITORY + "/examples/fieldkest.bin", REPOSITORY + "/config/diagnostic.conf", expected=401, credentials="rowan.ito:wrong")
        self.assertEqual(denied["error"], "authentication_required")


if __name__ == "__main__":
    unittest.main(verbosity=2)
