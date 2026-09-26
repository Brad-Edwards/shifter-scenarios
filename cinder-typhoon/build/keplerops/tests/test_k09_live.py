#!/usr/bin/env python3
"""Operator-side black-box checks for the K09 retained runner path."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import unittest


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
BASE = "https://ci.keplerops.test"
USER = "rowan.ito:kpl_rowan_7X4mQ9vN2cL6"
STATUS_COMMAND = (
    '. /run/fieldlink-ci/connections.env; exec curl -q --silent --show-error --fail '
    '--config /run/fieldlink-ci/build-records.curl '
    '--url "$FIELDLINK_BUILD_RECORDS_URL/api/build-records/worker-status"'
)


def rowan(*arguments: str, input_bytes: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def request(path: str, *extra: str, expected: int = 200) -> bytes:
    result = rowan(
        "curl", "-sS", "--cacert", CA, "-o", "/tmp/k09-response", "-w", "%{http_code}",
        "-u", USER, *extra, BASE + path, check=False,
    )
    status = int(result.stdout)
    body = rowan("cat", "/tmp/k09-response").stdout
    if status != expected:
        raise AssertionError(f"{path} returned {status}: {body.decode(errors='replace')} {result.stderr.decode(errors='replace')}")
    return body


def request_json(path: str, *extra: str, expected: int = 200) -> dict[str, object]:
    body = request(path, *extra, expected=expected)
    return json.loads(body) if body.strip() else {}


def submit(value: dict[str, object], *, expected: int = 202) -> dict[str, object]:
    return request_json(
        "/api/review-jobs", "-H", "Content-Type: application/json", "--data-binary",
        json.dumps(value, separators=(",", ":")), expected=expected,
    )


def wait_job(run_id: str, timeout: float = 35) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = request_json(f"/api/review-jobs/{run_id}")
        if result["state"] != "queued":
            return result
        time.sleep(0.2)
    raise AssertionError(f"review job {run_id} did not finish")


class K09LiveTest(unittest.TestCase):
    support_input: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        for _ in range(30):
            probe = rowan(
                "curl", "-sS", "--connect-timeout", "1", "--cacert", CA, "-u", USER,
                BASE + "/api/runs/BLD-1842", check=False,
            )
            if probe.returncode == 0:
                return
            time.sleep(1)
        raise AssertionError("K09 CI service did not become ready")

    def test_01_retained_log_and_dossier_binding(self) -> None:
        run = request_json("/api/runs/BLD-1842")
        self.assertEqual(run["summary"], "Fixture unavailable at the selected revision.")
        self.assertNotIn("BLD-REL-742", json.dumps(run["summary"]))
        log = request("/api/runs/BLD-1842/log").decode()
        self.assertIn("release dossier: BLD-REL-742", log)
        self.assertIn("recovery build record: BLD-REC-021", log)
        self.assertIn("retained artifact: integration-review-input-v3.json", log)
        self.assertEqual(hashlib.sha256(log.encode()).hexdigest(), "37c8ce60d347f73e2502180582b2b0ee951f8e52c49b7dc8e376fc989cbbba1a")

    def test_02_omitted_artifact_and_provenance(self) -> None:
        run = request_json("/api/runs/BLD-1842")
        self.assertNotIn("integration-review-input-v3.json", run["result_page"]["artifacts"])
        retained = run["retained_artifacts"][0]
        artifact_bytes = request(retained["url"])
        artifact = json.loads(artifact_bytes)
        self.assertEqual(artifact["artifact_id"], "ART-BLD-1842-INTEGRATION-REVIEW")
        self.assertEqual(artifact["object_version"], 3)
        self.assertEqual(artifact["build_revision"], "c37effd7cc86ae4d44f18e95f899b7557d65e0a9")
        self.assertEqual(hashlib.sha256(artifact_bytes).hexdigest(), retained["sha256"])
        denied = request_json("/api/runs/BLD-9999/artifacts/integration-review-input-v3.json", expected=404)
        self.assertEqual(denied["error"], "not_found")

    def test_03_linked_review_returns_bound_retained_input(self) -> None:
        artifact = request_json("/api/runs/BLD-1842/artifacts/integration-review-input-v3.json")
        accepted = submit({"support_input": artifact, "diagnostic": {"profile": "render-review"}})
        result = request_json(accepted["result"])
        self.assertEqual((result["state"], result["profile"]), ("success", "render-review"))
        self.assertEqual(result["workspace_generation"], "WS-ROWAN-2026-09-G1")
        self.assertIn("POST /api/review-jobs", result["review"]["maintained_reference"])
        self.assertIn("/srv/fieldlink-ci/runner/runner-operations.md", result["review"]["maintained_reference"])
        self.assertNotIn("FieldKest runner service connections", result["review"]["maintained_reference"])
        K09LiveTest.support_input = result["support_input"]

    def test_04_ordinary_input_cannot_dispatch_commands(self) -> None:
        ordinary = {
            "schema": "fieldkest.review-input/v3",
            "artifact_id": "ART-BLD-1842-ORDINARY-SUPPORT",
            "run_id": "BLD-1842",
            "object_version": 1,
            "build_revision": "c37effd7cc86ae4d44f18e95f899b7557d65e0a9",
            "collection": "build-results/BLD-1842",
            "linked_support_ref": "support://reviews/ordinary-summary@1",
            "classification": "support-review",
            "diagnostic_eligible": False,
        }
        accepted = submit({"support_input": ordinary, "diagnostic": {"profile": "render-review"}})
        retained = request_json(accepted["result"])["support_input"]
        denied = submit({
            "support_input": retained,
            "diagnostic": {"profile": "runner-command", "argv": ["/bin/pwd"]},
        }, expected=403)
        self.assertEqual(denied["error"], "build_operations_entitlement_required")
        raw = submit({
            "support_input": "buildops://reviews/diagnostic-request-reference@3",
            "diagnostic": {"profile": "runner-command", "argv": ["/bin/pwd"]},
        }, expected=403)
        self.assertEqual(raw["error"], "retained_input_denied")

    def _integration_reference(self) -> str:
        if not self.support_input:
            self.test_03_linked_review_returns_bound_retained_input()
        return self.support_input

    def _command(self, argv: list[str]) -> dict[str, object]:
        queued = submit({
            "support_input": self._integration_reference(),
            "diagnostic": {"profile": "runner-command", "argv": argv},
        })
        return wait_job(queued["run_id"])

    def test_05_actual_note_read_and_workspace_script(self) -> None:
        note = self._command(["/bin/cat", "/srv/fieldlink-ci/runner/runner-operations.md"])
        self.assertEqual(note["state"], "success")
        self.assertIn("FieldKest runner service connections", note["stdout"])
        self.assertIn("/srv/fieldlink-ci/runner/runner-operations.md", note["opened_paths"])
        script = b"#!/bin/sh\nprintf 'workspace-script:%s\\n' \"$(id -un)\" > /workspace/script-result.txt\n"
        result = rowan(
            "curl", "-sS", "--cacert", CA, "-u", USER, "-X", "PUT",
            "-H", "Content-Type: application/octet-stream", "--data-binary", "@-",
            BASE + "/api/review-workspace/files/tools/probe.sh", input_bytes=script,
        )
        uploaded = json.loads(result.stdout)
        self.assertEqual(uploaded["sha256"], hashlib.sha256(script).hexdigest())
        executed = self._command(["/bin/sh", "/workspace/tools/probe.sh"])
        self.assertEqual(executed["state"], "success")
        saved = {item["path"] for item in executed["saved_files"]}
        self.assertIn("script-result.txt", saved)
        self.assertEqual(request("/api/review-workspace/files/script-result.txt"), b"workspace-script:fieldkest-worker\n")

    def test_06_authenticated_build_record_join(self) -> None:
        result = self._command(["/bin/sh", "-c", STATUS_COMMAND])
        self.assertEqual(result["state"], "success")
        response = json.loads(result["stdout"])
        self.assertEqual((response["principal"], response["availability"]), ("svc-fieldlink-ci", "available"))
        self.assertEqual(response["run_id"], result["run_id"])
        audit = subprocess.run(
            ["docker", "exec", "cinder-keplerops-cloud-api", "cat", "/var/lib/fieldkest-cloud-api/audit/build-records.jsonl"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.splitlines()
        joined = [json.loads(line) for line in audit if json.loads(line).get("request_id") == response["request_id"]]
        self.assertEqual(len(joined), 1)
        self.assertEqual((joined[0]["principal"], joined[0]["run_id"], joined[0]["lease_id"]),
                         ("svc-fieldlink-ci", result["run_id"], result["lease_id"]))
        self.assertTrue(joined[0]["peer_address"].startswith("10.77.53."))

    def test_07_worker_source_package_scope_and_network_denial(self) -> None:
        source = self._command([
            "/bin/sh", "-c",
            '. /run/fieldlink-ci/connections.env; exec curl -q -sS --fail --config /run/fieldlink-ci/source.curl --url "$FIELDLINK_SOURCE_URL/api/v1/user/repos"',
        ])
        self.assertEqual(json.loads(source["stdout"])[0]["permissions"], {"admin": False, "pull": True, "push": False})
        packages = self._command([
            "/bin/sh", "-c",
            '. /run/fieldlink-ci/connections.env; exec curl -q -sS --fail --config /run/fieldlink-ci/packages.curl --url "$FIELDLINK_PACKAGES_URL/@keplerops%2ffieldlink-connector"',
        ])
        self.assertEqual(json.loads(packages["stdout"])["interface"], "fieldkest.connector/v3")
        denied = self._command(["/usr/bin/curl", "-sS", "--connect-timeout", "2", "https://10.77.51.40/"])
        self.assertNotEqual(denied["exit_status"], 0)

    def test_08_cancellation_preserves_workspace_and_cleans_child(self) -> None:
        queued = submit({
            "support_input": self._integration_reference(),
            "diagnostic": {"profile": "runner-command", "argv": ["/bin/sh", "-c", "sleep 30"]},
        })
        time.sleep(0.5)
        cancelled = request_json(f"/api/review-jobs/{queued['run_id']}/cancel", "-X", "POST", expected=202)
        self.assertEqual(cancelled["state"], "cancelled")
        result = wait_job(queued["run_id"])
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(request("/api/review-workspace/files/script-result.txt"), b"workspace-script:fieldkest-worker\n")
        active = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=fieldkest-command-"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        self.assertEqual(active, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
