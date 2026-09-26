#!/usr/bin/env python3
"""Black-box acceptance for the extended KeplerOps service fabric."""

from __future__ import annotations

import base64
import json
import subprocess
import unittest


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
DEV = "rowan.ito:kpl_rowan_7X4mQ9vN2cL6"
COOKIE = "fieldkest_support=ksess_rowan_2841_6Hs8Qp3V"


def rowan(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def call(host: str, path: str, *, method: str = "GET", body: dict[str, object] | None = None, auth: str | None = DEV, cookie: str | None = None, expected: int = 200, headers: dict[str, str] | None = None, cert: tuple[str, str] | None = None) -> dict[str, object]:
    command = ["curl", "-sS", "--cacert", CA, "-o", "/tmp/platform-response.json", "-w", "%{http_code}", "-X", method]
    if auth == DEV: command += ["-u", DEV]
    elif auth: command += ["-H", f"Authorization: Bearer {auth}"]
    if cookie: command += ["-H", f"Cookie: {cookie}"]
    if cert: command += ["--cert", cert[0], "--key", cert[1]]
    for name, value in (headers or {}).items(): command += ["-H", f"{name}: {value}"]
    if body is not None: command += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body, separators=(",", ":"))]
    command.append(f"https://{host}{path}")
    result = rowan(*command)
    raw = rowan("cat", "/tmp/platform-response.json").stdout
    if result.stdout != str(expected): raise AssertionError(f"{method} {host}{path}: {result.stdout} {raw} {result.stderr}")
    return json.loads(raw) if raw else {}


def call_negotiate(host: str, path: str, *, method: str = "GET", body: dict[str, object] | None = None, expected: int = 200) -> dict[str, object]:
    command = ["env", "KRB5CCNAME=FILE:/tmp/evan.ccache", "curl", "-sS", "--cacert", CA, "--negotiate", "-u", ":", "-o", "/tmp/negotiate-response.json", "-w", "%{http_code}", "-X", method]
    if body is not None:
        command += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body, separators=(",", ":"))]
    command.append(f"https://{host}{path}")
    result = rowan(*command)
    raw = rowan("cat", "/tmp/negotiate-response.json").stdout
    if result.stdout != str(expected): raise AssertionError(f"{method} {host}{path}: {result.stdout} {raw} {result.stderr}")
    return json.loads(raw) if raw else {}


class PlatformLiveTest(unittest.TestCase):
    def test_01_preview_identity_and_reviewer_workflow(self) -> None:
        protected = call("preview.keplerops.test", "/api/documents", method="POST", body={"source_id": "SUP-K-2841", "content": "Restricted release review: retain the compatibility exception."}, expected=201)
        participant = call("preview.keplerops.test", "/api/documents", method="POST", body={"source_id": "sup-k-2841", "content": "Ordinary preview"}, expected=201)
        self.assertEqual(protected["derived_id"], participant["derived_id"])
        rendered = call("preview.keplerops.test", "/api/documents/sup-k-2841/render", method="POST", body={}, expected=202)
        self.assertEqual((rendered["content_source"], rendered["content_version"]), ("SUP-K-2841", 7))
        assignment = call("preview.keplerops.test", "/api/reviews/PRV-771/assignment", method="PATCH", body={"queue": "privileged-review", "source_id": "sup-k-2841"})
        prepared = call("preview.keplerops.test", "/api/reviews/PRV-771/actions/prepare", method="POST", body={}, auth=assignment["action_nonce"])
        self.assertTrue(prepared["prepared"])
        replay = call("preview.keplerops.test", "/api/reviews/PRV-771/actions/prepare", method="POST", body={}, auth=assignment["action_nonce"], expected=403)
        self.assertEqual(replay["error"], "nonce_denied")
        final = call("preview.keplerops.test", "/review/PRV-771/render", method="POST", body={"worker_scope": "/review/"}, auth="reviewer-worker")
        self.assertEqual((final["renderer_identity"], final["compatibility_summary"]), ("svc-preview-reviewer", "fieldlink.connector/v3 compatible"))
        self.assertEqual((final["browser_engine"], final["worker_scope"]), ("chromium", "/review/"))
        self.assertEqual(final["browser_version"], "140.0.7339.207")

    def test_02_workspace_cloud_export_and_persistence(self) -> None:
        listing = call("data.keplerops.test", "/s3/fieldkest-workspaces", auth=None)
        self.assertIn("notebooks/deploy-2026-09.json", [item["key"] for item in listing["objects"]])
        old = call("data.keplerops.test", "/s3/fieldkest-workspaces/notebooks/deploy-2026-09.json?versionId=v-20260908", auth=None)
        self.assertEqual(old["customer_note"], "ARWC legacy integration TEN-ARWC-019")
        handover = call("data.keplerops.test", "/s3/fieldkest-workspaces/exports/EXP-2841/handover.json", auth=None)
        self.assertEqual(handover["export_id"], "EXP-2841")
        exchange = call("cloud-api.keplerops.test", "/api/workspaces/current/token-exchange")
        workload = call("cloud-api.keplerops.test", "/api/workspaces/current/token-exchange", method="POST", body={}, expected=201)
        build = call("cloud-api.keplerops.test", "/api/build-records/BLD-1842", auth=workload["access_token"])
        self.assertEqual(build["principal"], "svc-fieldlink-workload")
        trust = call("cloud-api.keplerops.test", "/api/trust-records/TRUST-FLX-04", auth=workload["access_token"])
        self.assertEqual(trust["role"], "role/support-export-editor")
        role = call("cloud-api.keplerops.test", "/api/token-exchange/support-export-editor", method="POST", body={}, auth=exchange["fixture_token"], expected=201)
        self.assertEqual(role["accepted_input_audience"], "fieldkest-build-records")
        protected = call("data.keplerops.test", "/s3/fieldkest-exports/exports%2fsupport%2fEXP-2841", auth=role["access_token"])
        self.assertEqual(protected["tenant"], "TEN-ARWC-047")
        definition = call("data.keplerops.test", "/api/exports/EXP-2841/definition", auth=role["access_token"])
        self.assertEqual(definition["owner"], "maya.ranscombe")
        update = call("data.keplerops.test", "/api/exports/EXP-2841/destination", method="PATCH", body={"destination": "rowan-support-sink"}, auth=role["access_token"])
        self.assertEqual(update["revision"], 7)
        delivered = call("data.keplerops.test", "/api/exports/EXP-2841/runs", method="POST", body={"tenant": "TEN-ARWC-047", "connector_revision": "FLK-7.4.2", "partitions": ["current"]}, auth=role["access_token"], expected=201)
        self.assertEqual(delivered["destination"], "rowan-support-sink")
        stale = call("data.keplerops.test", "/api/exports/EXP-2841/runs", method="POST", body={"tenant": "TEN-ARWC-019", "connector_revision": "FLK-6.9.8", "partitions": ["legacy"]}, auth=role["access_token"], expected=422)
        self.assertEqual(stale["error"], "incoherent_collection")

    def test_03_schedule_runtime_and_shift_transition(self) -> None:
        schedule = call("workloads.keplerops.test", "/api/schedules/SCH-SUP-2841", auth="support-export-role")
        self.assertIn(schedule["assignment"], {"SHIFT-SEP16-A", "SHIFT-SEP17-B"})
        call("workloads.keplerops.test", "/api/schedules/SCH-SUP-2841", method="PATCH", body={"startup_hook": ["/opt/fieldkest/hooks/support-marker", "--export", "EXP-2841"]}, auth="support-export-role")
        run = call("workloads.keplerops.test", "/api/schedules/SCH-SUP-2841/runs", method="POST", body={}, auth="support-export-role", expected=201)
        self.assertEqual((run["runtime_identity"], run["marker"]), ("svc-support-export", True))
        self.assertEqual((run["execution_backend"], run["container_network"]), ("isolated-container", "none"))
        call("workloads.keplerops.test", "/api/schedules/SCH-SUP-2841", method="PATCH", body={"assignment": "SHIFT-SEP17-B"}, auth="support-export-role")
        later = call("workloads.keplerops.test", "/api/schedules/SCH-SUP-2841/runs", method="POST", body={}, auth="support-export-role", expected=201)
        self.assertEqual((later["assignment"], later["marker"]), ("SHIFT-SEP17-B", True))

    def test_04_support_recovery_federation_and_delegation(self) -> None:
        lookup = call("support.keplerops.test", "/api/recovery/lookup", method="POST", body={"account": "talia.mornac-review"}, auth=None)
        recovered = call("support.keplerops.test", "/api/recovery/redeem", method="POST", body={"recovery_id": lookup["recovery_id"], "browser_factor": "SUP-2841"}, auth=None, expected=201)
        assignment = call("support.keplerops.test", "/api/assignments/B01", auth=None, cookie=f"fieldkest_support={recovered['session_id']}")
        self.assertNotIn("TEN-ARWC-047", assignment["customers"])
        copied = call("support.keplerops.test", "/api/cases/SUP-2841/copy-handover", method="POST", body={"reviewer": "talia.mornac-review"}, auth=None, cookie=COOKIE, expected=201)
        self.assertEqual(copied["owner"], "talia.mornac-review")
        note = call("staff.keplerops.test", "/api/notes/NOTE-SUP-2841-7", auth="kpl_rowan_7X4mQ9vN2cL6")
        self.assertEqual(note["consumer"], "staff-note-preview")
        source = "/notes/%2e%2e%2fidentity/api/registrations/OIDC-FIELDKEST-SUPPORT"
        registration = call("staff.keplerops.test", "/api/note-preview", method="POST", body={"source_path": source, "method": "GET"}, auth="kpl_rowan_7X4mQ9vN2cL6")
        changed = call("staff.keplerops.test", "/api/note-preview", method="POST", body={"source_path": source, "method": "PATCH"}, auth="kpl_rowan_7X4mQ9vN2cL6")
        self.assertGreater(changed["revision"], registration["revision"])
        staff_login = call("identity.keplerops.test", "/api/federation/staff-login", method="POST", body={"username": "rowan.ito", "password": "kpl_rowan_7X4mQ9vN2cL6"}, expected=201)
        self.assertEqual((staff_login["provider"], staff_login["login"]), ("OIDC-FIELDKEST-STAFF", "accepted"))
        assertion = call("support.keplerops.test", "/fixture-issuer/assertions", method="POST", body={"subject": "fixture-reviewer-047", "tenant": "TEN-ARWC-047"}, auth=None, expected=201)
        federated = call("identity.keplerops.test", "/api/federation/login", method="POST", body={"assertion": assertion["assertion"]}, expected=201)
        record = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/dossiers/CUSTREC-047-R6", auth=None, cookie=federated["session_cookie"])
        self.assertEqual((record["record_id"], record["federated_subject"]), ("CUSTREC-047-R6", "fixture-reviewer-047"))
        cert = call("cert.keplerops.test", "/api/enrollment/StaffArchiveUser/requests", method="POST", body={"upn": "evan.calderoux@KEPLEROPS.TEST"}, auth="cert-enrollment-worker", expected=201)
        for path, field in (("/tmp/evan.crt", "certificate_pem"), ("/tmp/evan.key", "private_key_pem")):
            installed = subprocess.run(["docker", "exec", "-i", "--user", "rowan", CONTAINER, "tee", path], input=cert[field], text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
            self.assertEqual(installed.returncode, 0, installed.stderr)
        archive = call("staff.keplerops.test", "/api/archive/handovers/evan.calderoux", auth=None, cert=("/tmp/evan.crt", "/tmp/evan.key"))
        delegated = call("staff.keplerops.test", "/api/archive/delegation/probe", method="POST", body={"spn": "HTTP/identity.keplerops.test@KEPLEROPS.TEST"}, auth=None, cert=("/tmp/evan.crt", "/tmp/evan.key"))
        installed = subprocess.run(["docker", "exec", "-i", "--user", "rowan", CONTAINER, "tee", "/tmp/evan.ccache"], input=base64.b64decode(delegated["credential_cache"]), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
        self.assertEqual(installed.returncode, 0, installed.stderr.decode())
        relation = call_negotiate("identity.keplerops.test", "/api/service-relations/svc-release-admin")
        managed = call_negotiate("staff.keplerops.test", "/api/managed-identities/svc-release-admin/session", method="POST", body={}, expected=201)
        self.assertEqual((archive["service_relation"], relation["service_id"], managed["principal"]), ("svc-release-admin", "svc-release-admin", "svc-release-admin"))
        self.assertEqual(delegated["authentication"], "SPNEGO")

    def test_05_assistant_retrieval_action_and_completion(self) -> None:
        config = call("assistant.keplerops.test", "/api/config", auth=None)
        self.assertEqual(config["context"], "ctx-support-private-v4")
        retained = call("assistant.keplerops.test", "/api/conversations/CONV-SUP-2841-19", auth=None, cookie=COOKIE)
        private = call("assistant.keplerops.test", "/api/answers", method="POST", body={"request": "private-escalation", "case_reference": "SUP-2841"}, auth=None, cookie=COOKIE)
        self.assertEqual((retained["case"], private["sources"]), ("SUP-2841", ["ESC-SUP-2841-R3"]))
        selection = call("assistant.keplerops.test", "/api/selections/SEL-SUP-2841-12", auth=None, cookie=COOKIE)
        influenced = call("assistant.keplerops.test", "/api/answers", method="POST", body={"request": "compatibility-guidance", "selection_id": selection["selection_id"]}, auth=None, cookie=COOKIE)
        self.assertIn("FLK-6.9.8", influenced["answer"])
        action = call("assistant.keplerops.test", "/api/answers", method="POST", body={"request": "accept-duplicate", "review_id": "DREV-2841-2"}, auth=None, cookie=COOKIE)
        self.assertEqual((action["status"], action["principal"]), ("accepted", "svc-fieldkest-assistant"))
        inventory = call("assistant.keplerops.test", "/api/contexts", auth=None)
        self.assertFalse(inventory["contexts"][0]["published"])
        reference = call("assistant.keplerops.test", "/api/conversations/CONV-RILL-442-8", auth=None, cookie=COOKIE)
        document = call("assistant.keplerops.test", "/api/contexts/ctx-support-private-v4/conversations/CONV-RILL-442-8/documents/RILL-PRIVATE-442", auth=None, cookie=COOKIE)
        self.assertEqual(reference["tenant"], document["tenant"])
        context = call("assistant.keplerops.test", "/api/completions/context", method="POST", body={"context": "support-examples/../credentials/cred-completion-handover"}, auth=None, cookie=COOKIE, expected=201)
        job = call("assistant.keplerops.test", "/api/completions/jobs", method="POST", body={"handover_id": "HANDOVER-COMP-2841", "script": "read_assigned_handover"}, auth=context["lease"], expected=202)
        result = call("assistant.keplerops.test", f"/api/completions/jobs/{job['job_id']}", auth=context["lease"])
        self.assertEqual((result["runtime_identity"], result["handover"]["handover_id"]), ("svc-assistant-completion", "HANDOVER-COMP-2841"))
        self.assertEqual((result["execution_backend"], result["container_network"], result["destination_read"]), ("isolated-container", "none", True))
        replay = call("assistant.keplerops.test", "/api/completions/jobs", method="POST", body={"handover_id": "HANDOVER-COMP-2841", "script": "read_assigned_handover"}, auth=context["lease"], expected=403)
        self.assertEqual(replay["error"], "completion_lease_denied")

    def test_06_customer_history_diagnostics_recovery_and_maintenance(self) -> None:
        dossier = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/dossiers/DOS-ARWC-HIST-01", auth=None, cookie=COOKIE)
        integration = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/integrations/fieldlink", auth=None, cookie=COOKIE)
        reconcile = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/integrations/fieldlink/reconcile", method="POST", body={"candidates": [{"tenant": "TEN-ARWC-019", "revision": "FLK-6.9.8"}, {"tenant": "TEN-ARWC-047", "revision": "FLK-7.4.2"}]}, auth=None, cookie=COOKIE)
        self.assertEqual((dossier["account"], integration["tenant"], reconcile["active_revision"]), ("K-C-001", "TEN-ARWC-047", "FLK-7.4.2"))
        job = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/diagnostics", method="POST", body={"connector_revision": "FLK-7.4.2"}, auth=None, cookie=COOKIE, expected=201)
        package = call("support.keplerops.test", f"/api/diagnostics/{job['job_id']}/package", method="PUT", body={"interface": "fieldkest.connector/v3", "expected_output": {"assessment": "calibration-review"}}, auth=None, cookie=COOKIE)
        delivery = call("support.keplerops.test", f"/api/diagnostics/{job['job_id']}/deliver", method="POST", body={}, auth=None, cookie=COOKIE, expected=201)
        self.assertEqual((package["state"], delivery["output"]["assessment"]), ("packaged", "calibration-review"))
        recovery = call("cloud-api.keplerops.test", "/api/build-records/BLD-REC-021", auth="workload-session")
        catalog = call("data.keplerops.test", "/api/backups/BAK-2026-021", auth=recovery["session"])
        restored = call("data.keplerops.test", "/api/backups/BAK-2026-021/restores", method="POST", body={}, auth=recovery["session"], expected=201)
        history = call("data.keplerops.test", f"/api/recovery/{restored['namespace_id']}/customer-migration-history", auth=recovery["session"])
        self.assertEqual((catalog["source_database"], history["records"][0]["current_tenant"]), ("denied", "TEN-ARWC-047"))
        policy = call("cloud-api.keplerops.test", "/api/policies/fieldlink-maintenance", auth="ci-maintenance-worker")
        spawned = call("workloads.keplerops.test", "/api/workloads/MAINT-FLK-01", method="PATCH", body={"command": ["maintenance-summary", "--archive", "FIELD-CRR-2026-09"], "labels": {"workload.class": "maintenance"}}, auth="ci-maintenance-worker")
        self.assertEqual((spawned["last_execution"]["execution_backend"], spawned["last_execution"]["container_network"]), ("isolated-container", "none"))
        whoami = call("workloads.keplerops.test", "/api/workloads/MAINT-FLK-01/whoami", auth="ci-maintenance-worker")
        archive = call("data.keplerops.test", "/api/field-archive/FIELD-CRR-2026-09", auth="maintenance-runtime", headers={"X-Workload-Class": "maintenance", "X-Scheduler-Attestation": whoami["attestation"]})
        self.assertEqual((policy["runtime_identity"], whoami["runtime_identity"], archive["calibration_revision"]), ("svc-fieldlink-maintenance", "svc-fieldlink-maintenance", "CAL-2026-09-R4"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
