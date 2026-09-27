#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-archive"
BASE = "https://retained-archive.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc",
            certificate: str = "", private_key: str = "") -> tuple[int, dict]:
    script = r'''
import json, pathlib, ssl, sys, tempfile, urllib.error, urllib.request
method, url, tenant, supplied, body, certificate, private_key = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
data = None if not body else body.encode()
if data is not None:
    headers["Content-Type"] = "application/json"
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
with tempfile.TemporaryDirectory() as directory:
    if certificate:
        cert_path = pathlib.Path(directory) / "client.crt"
        key_path = pathlib.Path(directory) / "client.key"
        cert_path.write_text(certificate)
        key_path.write_text(private_key)
        context.load_cert_chain(cert_path, key_path)
    try:
        response = urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers, method=method), context=context
        )
    except urllib.error.HTTPError as error:
        response = error
    print(response.status)
    print(response.read().decode())
'''
    completed = inside(
        "python3", "-c", script, method, BASE + path, tenant,
        "@session" if token is None else token,
        "" if body is None else json.dumps(body, separators=(",", ":")),
        certificate, private_key,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, payload = completed.stdout.splitlines()
    return int(status), json.loads(payload)


def make_archive(member: str) -> str:
    script = r'''
import base64, pathlib, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as directory:
    root = pathlib.Path(directory)
    member = sys.argv[1]
    target = root / member
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("retained archive request\n")
    archive = root / "request.7z"
    subprocess.run(["7zz", "a", str(archive), member], cwd=root, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(base64.b64encode(archive.read_bytes()).decode())
'''
    completed = inside("python3", "-c", script, member)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def enroll(organizational_unit: str, token: str) -> tuple[str, str]:
    status, response = request(
        "/api/the-query-behind-the-identity", method="POST",
        body={
            "operation": "enroll",
            "enrollment_token": token,
            "organizational_unit": organizational_unit,
        },
    )
    if status != 201:
        raise AssertionError(response)
    return response["certificate"], response["private_key"]


def workflow_token() -> str:
    status, response = request("/api/the-archive-s-missing-contract")
    if status != 200:
        raise AssertionError(response)
    return response["record"]["enrollment_token"]


def certificate_details(certificate: str) -> str:
    script = r'''
import pathlib, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / "client.crt"
    path.write_text(sys.argv[1])
    completed = subprocess.run(
        ["openssl", "x509", "-in", str(path), "-noout", "-subject", "-ext", "extendedKeyUsage"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    print(completed.stdout)
'''
    completed = inside("python3", "-c", script, certificate)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return completed.stdout


class W04Live(unittest.TestCase):
    ordinary_certificate = ""
    ordinary_key = ""
    injected_certificate = ""
    injected_key = ""

    def test_01_downstream_operations_require_predecessor_evidence(self) -> None:
        status, body = request(
            "/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("AR-CRR-229", json.dumps(body))
        status, body = request(
            "/api/the-archive-helper-acts", method="POST", body={"archive": "eA=="},
        )
        self.assertEqual(status, 403)
        self.assertNotIn("HND-PLANNER-06", json.dumps(body))

    def test_02_workflow_binds_exact_archive_contract(self) -> None:
        status, response = request("/api/the-archive-s-missing-contract")
        self.assertEqual(status, 200)
        record = response["record"]
        self.assertEqual(record["record_id"], "AWF-CRR-229-R4")
        self.assertEqual(record["revision"], 4)
        self.assertEqual(record["attachment"], "ARC-229-A")
        self.assertEqual(record["protected_record"], "AR-CRR-229")
        self.assertEqual(record["enrollment_profile"], {
            "name": "ArchiveSubmitter",
            "common_name": "corporate-reader-principal",
            "extended_key_usage": "clientAuth",
            "organizational_unit": "caller supplied",
            "use": "one time",
        })
        type(self).first_token = record["enrollment_token"]

    def test_03_one_use_profile_issues_real_client_identity(self) -> None:
        certificate, key = enroll("MaintenanceArchive", type(self).first_token)
        type(self).ordinary_certificate = certificate
        type(self).ordinary_key = key
        details = certificate_details(certificate)
        self.assertIn("OU = MaintenanceArchive", details)
        self.assertIn("TLS Web Client Authentication", details)
        status, replay = request(
            "/api/the-query-behind-the-identity", method="POST",
            body={
                "operation": "enroll",
                "enrollment_token": type(self).first_token,
                "organizational_unit": "MaintenanceArchive",
            },
        )
        self.assertEqual(status, 409)
        self.assertNotIn("PRIVATE KEY", json.dumps(replay))

    def test_04_ordinary_identity_returns_only_its_record(self) -> None:
        status, response = request(
            "/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
            certificate=type(self).ordinary_certificate, private_key=type(self).ordinary_key,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["record_id"], "AR-MAINT-017")
        self.assertNotIn("AR-CRR-229", json.dumps(response))
        self.assertEqual(
            response["backend_query"],
            "MATCH (i:Identity {ou:'MaintenanceArchive'})-[:CAN_READ]->(r:ArchiveRecord) RETURN r",
        )

    def test_05_backend_rejects_other_records_and_writes(self) -> None:
        other_token = workflow_token()
        other_cert, other_key = enroll(
            "MaintenanceArchive' OR r.id='AR-MER-100' OR 'a'='b", other_token,
        )
        status, response = request(
            "/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
            certificate=other_cert, private_key=other_key,
        )
        self.assertEqual(status, 403)
        self.assertNotIn("AR-MER-100", json.dumps(response))

        write_token = workflow_token()
        write_cert, write_key = enroll("MaintenanceArchive' SET r.open=true OR 'a'='b", write_token)
        status, response = request(
            "/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
            certificate=write_cert, private_key=write_key,
        )
        self.assertEqual(status, 409)
        self.assertIn("read only", response["error"])

    def test_06_subject_injection_recovers_only_the_bounded_record(self) -> None:
        token = workflow_token()
        certificate, key = enroll(
            "MaintenanceArchive' OR r.id='AR-CRR-229' OR 'a'='b", token,
        )
        type(self).injected_certificate = certificate
        type(self).injected_key = key
        status, response = request(
            "/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
            certificate=certificate, private_key=key,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "AR-CRR-229",
            "revision": 4,
            "workflow": "AWF-CRR-229-R4",
            "attachment": "ARC-229-A",
            "classification": "retained corporate archive",
        })
        self.assertIn("OR r.id='AR-CRR-229'", response["backend_query"])

    def test_07_helper_validates_raw_member_before_nfkc(self) -> None:
        slash_archive = make_archive("outside/copy_handover(HND-PLANNER-06)")
        status, response = request(
            "/api/the-archive-helper-acts", method="POST", body={"archive": slash_archive},
        )
        self.assertEqual(status, 409)
        self.assertNotIn("HND-PLANNER-06", json.dumps(response))

        wrong_archive = make_archive("．．／copy_handover(HND-MER-01)")
        status, response = request(
            "/api/the-archive-helper-acts", method="POST", body={"archive": wrong_archive},
        )
        self.assertEqual(status, 409)
        self.assertNotIn("svc-archive-helper", json.dumps(response))

        crafted = make_archive("．．／copy_handover(HND-PLANNER-06)")
        status, response = request(
            "/api/the-archive-helper-acts", method="POST", body={"archive": crafted},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "HND-PLANNER-06",
            "revision": 6,
            "service_identity": "svc-archive-helper",
            "source_record": "AR-CRR-229",
            "destination": "caller result directory",
            "archive_helper": "7-Zip 23.01",
        })

    def test_08_wrong_session_and_tenant_disclose_nothing(self) -> None:
        status, body = request("/api/the-archive-s-missing-contract", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("AWF-CRR-229-R4", json.dumps(body))
        status, body = request("/api/the-archive-s-missing-contract", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("ArchiveSubmitter", json.dumps(body))

    def test_09_results_and_evidence_persist_across_restart(self) -> None:
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, response = request(
                    "/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
                    certificate=type(self).injected_certificate, private_key=type(self).injected_key,
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("retained archive did not return after restart")
        self.assertEqual(response["record"]["record_id"], "AR-CRR-229")
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-archive/state/archive.json")
        self.assertEqual(hidden.returncode, 0)
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", SERVICE,
             "cat", "/var/lib/arwc-archive/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertIn('"action":"the-query-behind-the-identity/query"', audit.stdout)
        self.assertIn('"action":"the-archive-helper-acts"', audit.stdout)
        result = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", SERVICE,
             "cat", "/var/lib/arwc-archive/results/HND-PLANNER-06.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        self.assertEqual(json.loads(result.stdout)["service_identity"], "svc-archive-helper")


if __name__ == "__main__":
    unittest.main(verbosity=2)
