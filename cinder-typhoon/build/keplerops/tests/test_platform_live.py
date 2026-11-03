#!/usr/bin/env python3
"""Black-box acceptance for the extended KeplerOps service fabric."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import unittest
from urllib import parse as urlparse

from runtime_credentials import basic, credential


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
DEV = basic()
DEV_USER = DEV.partition(":")[0]
DEV_TOKEN = credential("developer_token")
COOKIE = f"fieldkest_support={credential('support_rowan_session')}"
SUPPORT_EXPORT = credential("cloud_support_export_role")
CERT_ENROLLMENT = credential("cert_enrollment_worker")
WORKLOAD_SESSION = credential("cloud_workload_session")
MAINTENANCE_WORKER = credential("ci_maintenance_worker")
MAINTENANCE_RUNTIME = credential("cloud_maintenance_runtime")


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
        self.assertEqual((final["execution_backend"], final["container_network"]), ("isolated-container", "none"))
        self.assertNotEqual(final["process_identity"], 0)

    def test_02_workspace_cloud_export_and_persistence(self) -> None:
        listing = call("data.keplerops.test", "/s3/fieldkest-workspaces", auth=None)
        notebook = next(item for item in listing["objects"] if item.get("versions"))
        old = call("data.keplerops.test", f"/s3/fieldkest-workspaces/{notebook['key']}?versionId={notebook['versions'][0]}", auth=None)
        self.assertEqual(old["customer_note"], "ARWC legacy integration TEN-ARWC-019")
        handover_key = next(item["key"] for item in listing["objects"] if item["key"].endswith("handover.json"))
        handover = call("data.keplerops.test", "/s3/fieldkest-workspaces/" + handover_key, auth=None)
        exchange = call("cloud-api.keplerops.test", "/api/workspaces/current/token-exchange")
        workload = call("cloud-api.keplerops.test", "/api/workspaces/current/token-exchange", method="POST", body={}, expected=201)
        build = call("cloud-api.keplerops.test", "/api/build-records/BLD-1842", auth=workload["access_token"])
        self.assertEqual(build["principal"], "svc-fieldlink-workload")
        trust = call("cloud-api.keplerops.test", "/api/trust-records/" + exchange["trust_record"], auth=workload["access_token"])
        role_name = trust["role"].split("/")[-1]
        role = call("cloud-api.keplerops.test", "/api/token-exchange/" + role_name, method="POST", body={}, auth=exchange["fixture_token"], expected=201)
        self.assertEqual(role["accepted_input_audience"], "fieldkest-build-records")
        protected = call("data.keplerops.test", "/s3/fieldkest-exports/exports%2fsupport%2f" + handover["export_id"], auth=role["access_token"])
        definition = call("data.keplerops.test", f"/api/exports/{handover['export_id']}/definition", auth=role["access_token"])
        self.assertEqual(definition["owner"], "maya.ranscombe")
        destination = next(item["name"] for item in definition["destinations"] if item["owner"] == DEV_USER)
        update = call("data.keplerops.test", f"/api/exports/{handover['export_id']}/destination", method="PATCH", body={"destination": destination}, auth=role["access_token"])
        self.assertEqual(update["revision"], 7)
        current = next(item for item in definition["partition_bindings"] if item["tenant"] == protected["tenant"])
        run_path = f"/api/exports/{handover['export_id']}/runs"
        delivered = call("data.keplerops.test", run_path, method="POST", body={"tenant": current["tenant"], "connector_revision": current["connector_revision"], "partitions": [current["partition"]]}, auth=role["access_token"], expected=201)
        self.assertEqual(delivered["destination"], destination)
        stale_binding = next(item for item in definition["partition_bindings"] if item != current)
        stale = call("data.keplerops.test", run_path, method="POST", body={"tenant": stale_binding["tenant"], "connector_revision": stale_binding["connector_revision"], "partitions": [stale_binding["partition"]]}, auth=role["access_token"], expected=422)
        self.assertEqual(stale["error"], "incoherent_collection")

    def test_03_schedule_runtime_and_shift_transition(self) -> None:
        handover = call("data.keplerops.test", "/s3/fieldkest-workspaces/exports/EXP-2841/handover.json", auth=None)
        schedule_path = "/api/schedules/" + handover["job"]
        schedule = call("workloads.keplerops.test", schedule_path, auth=SUPPORT_EXPORT)
        call("workloads.keplerops.test", schedule_path, method="PATCH", body={"startup_hook": schedule["allowed_startup_hooks"][0]["argv"]}, auth=SUPPORT_EXPORT)
        run = call("workloads.keplerops.test", schedule_path + "/runs", method="POST", body={}, auth=SUPPORT_EXPORT, expected=201)
        self.assertEqual((run["runtime_identity"], run["marker"]), ("svc-support-export", True))
        self.assertEqual((run["execution_backend"], run["container_network"]), ("isolated-container", "none"))
        call("workloads.keplerops.test", schedule_path, method="PATCH", body={"assignment": schedule["next_assignment"]}, auth=SUPPORT_EXPORT)
        later = call("workloads.keplerops.test", schedule_path + "/runs", method="POST", body={}, auth=SUPPORT_EXPORT, expected=201)
        self.assertEqual((later["assignment"], later["marker"]), (schedule["next_assignment"], True))

    def test_04_support_recovery_federation_and_delegation(self) -> None:
        support_session = call("support.keplerops.test", "/api/session", auth=None, cookie=COOKIE)
        account = support_session["pending_reviewer_recovery"]["account"]
        lookup = call("support.keplerops.test", "/api/recovery/lookup", method="POST", body={"account": account}, auth=None)
        recovered = call("support.keplerops.test", "/api/recovery/redeem", method="POST", body={"recovery_id": lookup["recovery_id"], "browser_factor": support_session["case"]}, auth=None, expected=201)
        assignment = call("support.keplerops.test", "/api/assignments/" + support_session["assignment_id"], auth=None, cookie=f"fieldkest_support={recovered['session_id']}")
        tenant = support_session["customer"]["tenant"]
        self.assertNotIn(tenant, assignment["customers"])
        copied = call("support.keplerops.test", f"/api/cases/{support_session['case']}/copy-handover", method="POST", body={"reviewer": account}, auth=None, cookie=COOKIE, expected=201)
        self.assertEqual(copied["owner"], account)
        directory = call("staff.keplerops.test", "/api/service-directory", auth=DEV_TOKEN)
        note = call("staff.keplerops.test", "/api/notes/" + directory["restricted_note"], auth=DEV_TOKEN)
        self.assertEqual(note["consumer"], "staff-note-preview")
        source = "/notes/%2e%2e%2fidentity/api/registrations/OIDC-FIELDKEST-SUPPORT"
        registration = call("staff.keplerops.test", "/api/note-preview", method="POST", body={"source_path": source, "method": "GET"}, auth=DEV_TOKEN)
        changed = call("staff.keplerops.test", "/api/note-preview", method="POST", body={"source_path": source, "method": "PATCH"}, auth=DEV_TOKEN)
        self.assertGreater(changed["revision"], registration["revision"])
        staff_login = call("identity.keplerops.test", "/api/federation/staff-login", method="POST", body={"username": DEV_USER, "password": DEV_TOKEN}, expected=201)
        self.assertEqual((staff_login["provider"], staff_login["login"]), ("OIDC-FIELDKEST-STAFF", "accepted"))
        provider = changed["provider_configuration"]
        metadata_url = urlparse.urlsplit(provider["metadata_uri"])
        metadata = call(metadata_url.hostname, metadata_url.path, auth=None)
        history = call("support.keplerops.test", f"/api/customers/{tenant}/dossiers/" + support_session["customer"]["history_dossier"], auth=None, cookie=COOKIE)
        federation = history["reviewer_federation"]
        audience = metadata["assertion_audiences_supported"][0]
        assertion_path = urlparse.urlsplit(metadata["assertion_endpoint"]).path
        assertion_body = {"audience": audience, "subject": federation["subject"], "tenant": federation["tenant"]}
        for field, wrong in (("subject", "urn:fieldkest:pairwise:00000000-0000-0000-0000-000000000000"), ("tenant", "TEN-RILL-022"), ("audience", "unrelated-service")):
            denied_body = {**assertion_body, field: wrong}
            denied = call("support.keplerops.test", assertion_path, method="POST", body=denied_body, auth=None, expected=422)
            self.assertEqual(denied["error"], "federation_claims_denied")
        assertion = call("support.keplerops.test", assertion_path, method="POST", body=assertion_body, auth=None, expected=201)
        login_path = urlparse.urlsplit(provider["assertion_submission_endpoint"]).path
        customer_record_path = f"/api/customers/{tenant}/dossiers/{history['customer_record']}"
        bypass = call("support.keplerops.test", customer_record_path, auth=None, cookie="fieldkest_federated=" + assertion["assertion"], expected=403)
        self.assertEqual(bypass["error"], "federated_session_required")
        federated = call("identity.keplerops.test", login_path, method="POST", body={"assertion": assertion["assertion"]}, expected=201)
        replayed = call("identity.keplerops.test", login_path, method="POST", body={"assertion": assertion["assertion"]}, expected=409)
        self.assertEqual(replayed["error"], "assertion_replayed")
        record = call("support.keplerops.test", customer_record_path, auth=None, cookie=federated["session_cookie"])
        self.assertEqual((record["record_id"], record["federated_subject"]), (history["customer_record"], federation["subject"]))
        enrollment = urlparse.urlsplit(directory["enrollment"])
        template = call(enrollment.hostname, enrollment.path, auth=DEV_TOKEN)
        cert_request = urlparse.urlsplit(template["requests_endpoint"])
        upn = template["subject_format"].replace("{subject}", directory["archive_subject"])
        cert = call(cert_request.hostname, cert_request.path, method="POST", body={"upn": upn}, auth=directory["enrollment_worker"], expected=201)
        for path, field in (("/tmp/evan.crt", "certificate_pem"), ("/tmp/evan.key", "private_key_pem")):
            installed = subprocess.run(["docker", "exec", "-i", "--user", "rowan", CONTAINER, "tee", path], input=cert[field], text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
            self.assertEqual(installed.returncode, 0, installed.stderr)
        archive = call("staff.keplerops.test", "/api/archive/handovers/" + directory["archive_subject"], auth=None, cert=("/tmp/evan.crt", "/tmp/evan.key"))
        delegated = call("staff.keplerops.test", "/api/archive/delegation/probe", method="POST", body={"spn": archive["delegation_spn"]}, auth=None, cert=("/tmp/evan.crt", "/tmp/evan.key"))
        installed = subprocess.run(["docker", "exec", "-i", "--user", "rowan", CONTAINER, "tee", "/tmp/evan.ccache"], input=base64.b64decode(delegated["credential_cache"]), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
        self.assertEqual(installed.returncode, 0, installed.stderr.decode())
        relation = call_negotiate("identity.keplerops.test", "/api/service-relations/" + archive["service_relation"])
        managed = call_negotiate("staff.keplerops.test", f"/api/managed-identities/{relation['service_id']}/session", method="POST", body={}, expected=201)
        self.assertEqual((archive["service_relation"], relation["service_id"], managed["principal"]), (relation["service_id"],) * 3)
        denied = call("packages.keplerops.test", "/api/release-administration/session", auth="ordinary-developer", expected=403)
        self.assertEqual(denied["error"], "release_administration_denied")
        administration = call("packages.keplerops.test", "/api/release-administration/session", auth=managed["token"])
        self.assertEqual((administration["principal"], administration["approval_scope"]), ("svc-release-admin", "fieldlink-connector-rehearsal"))
        self.assertEqual(delegated["authentication"], "SPNEGO")

    def test_05_assistant_retrieval_action_and_completion(self) -> None:
        config = call("assistant.keplerops.test", "/api/config", auth=None)
        inventory = call("assistant.keplerops.test", "/api/contexts", auth=None)
        context_record = next(item for item in inventory["contexts"] if item["context_id"] == config["context"])
        support_conversation = next(item for item in context_record["conversations"] if "SUP" in item)
        retained = call("assistant.keplerops.test", "/api/conversations/" + support_conversation, auth=None, cookie=COOKIE)
        private_request = config["answer_requests"]["private_escalation"]
        private = call("assistant.keplerops.test", "/api/answers", method="POST", body={"request": private_request["request"], private_request["reference_field"]: retained["case"]}, auth=None, cookie=COOKIE)
        self.assertEqual((retained["case"], private["sources"]), ("SUP-2841", ["ESC-SUP-2841-R3"]))
        selection = call("assistant.keplerops.test", "/api/selections/" + context_record["selections"][0], auth=None, cookie=COOKIE)
        guidance_request = config["answer_requests"]["attachment_guidance"]
        influenced = call("assistant.keplerops.test", "/api/answers", method="POST", body={"request": guidance_request["request"], guidance_request["reference_field"]: selection["selection_id"]}, auth=None, cookie=COOKIE)
        self.assertIn("FLK-6.9.8", influenced["answer"])
        duplicate_request = config["answer_requests"]["duplicate_review"]
        action = call("assistant.keplerops.test", "/api/answers", method="POST", body={"request": duplicate_request["request"], duplicate_request["reference_field"]: context_record["duplicate_review"]}, auth=None, cookie=COOKIE)
        self.assertEqual((action["status"], action["principal"]), ("accepted", "svc-fieldkest-assistant"))
        self.assertFalse(context_record["published"])
        foreign_conversation = next(item for item in context_record["conversations"] if item != support_conversation)
        reference = call("assistant.keplerops.test", "/api/conversations/" + foreign_conversation, auth=None, cookie=COOKIE)
        document_id = context_record["documents"][0]
        document = call("assistant.keplerops.test", f"/api/contexts/{context_record['context_id']}/conversations/{foreign_conversation}/documents/{document_id}", auth=None, cookie=COOKIE)
        self.assertEqual(reference["tenant"], document["tenant"])
        example = call("assistant.keplerops.test", "/api/completions/examples/" + context_record["completion_example"], auth=None, cookie=COOKIE)
        credential_context = "/".join((example["context"], example["credential_namespace"], example["credential_reference"]))
        context = call("assistant.keplerops.test", "/api/completions/context", method="POST", body={"context": credential_context}, auth=None, cookie=COOKIE, expected=201)
        job_request = {"handover_id": example["handover_id"], "script": example["script"]}
        job = call("assistant.keplerops.test", "/api/completions/jobs", method="POST", body=job_request, auth=context["lease"], expected=202)
        result = call("assistant.keplerops.test", f"/api/completions/jobs/{job['job_id']}", auth=context["lease"])
        self.assertEqual((result["runtime_identity"], result["handover"]["handover_id"]), ("svc-assistant-completion", "HANDOVER-COMP-2841"))
        self.assertEqual((result["execution_backend"], result["container_network"], result["destination_read"]), ("isolated-container", "none", True))
        replay = call("assistant.keplerops.test", "/api/completions/jobs", method="POST", body=job_request, auth=context["lease"], expected=403)
        self.assertEqual(replay["error"], "completion_lease_denied")

    def test_06_customer_history_diagnostics_recovery_and_maintenance(self) -> None:
        dossier = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/dossiers/DOS-ARWC-HIST-01", auth=None, cookie=COOKIE)
        integration = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/integrations/fieldlink", auth=None, cookie=COOKIE)
        reconcile = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/integrations/fieldlink/reconcile", method="POST", body={"candidates": [{"tenant": "TEN-ARWC-019", "revision": "FLK-6.9.8"}, {"tenant": "TEN-ARWC-047", "revision": "FLK-7.4.2"}]}, auth=None, cookie=COOKIE)
        self.assertEqual((dossier["account"], integration["tenant"], reconcile["active_revision"]), ("K-C-001", "TEN-ARWC-047", "FLK-7.4.2"))
        job = call("support.keplerops.test", "/api/customers/TEN-ARWC-047/diagnostics", method="POST", body={"connector_revision": "FLK-7.4.2"}, auth=None, cookie=COOKIE, expected=201)
        package = call("support.keplerops.test", f"/api/diagnostics/{job['job_id']}/package", method="PUT", body={"interface": "fieldkest.connector/v3", "source": "exports.diagnostic_summary = input => ({assessment:'calibration-review'});", "expected_output": {"assessment": "calibration-review"}}, auth=None, cookie=COOKIE)
        self.assertEqual(package["state"], "packaged")
        if os.environ.get("CINDER_CROSS_SEGMENT") == "1":
            delivery = call("support.keplerops.test", f"/api/diagnostics/{job['job_id']}/deliver", method="POST", body={}, auth=None, cookie=COOKIE, expected=202)
            self.assertEqual((delivery["runtime_identity"], delivery["output"]["assessment"]), ("svc-arwc-fieldlink", "calibration-review"))
        recovery = call("cloud-api.keplerops.test", "/api/build-records/BLD-REC-021", auth=WORKLOAD_SESSION)
        catalog = call("data.keplerops.test", "/api/backups/BAK-2026-021", auth=recovery["session"])
        restored = call("data.keplerops.test", "/api/backups/BAK-2026-021/restores", method="POST", body={}, auth=recovery["session"], expected=201)
        history = call("data.keplerops.test", f"/api/recovery/{restored['namespace_id']}/customer-migration-history", auth=recovery["session"])
        self.assertEqual((catalog["source_database"], history["records"][0]["current_tenant"]), ("denied", "TEN-ARWC-047"))
        policy = call("cloud-api.keplerops.test", "/api/policies/fieldlink-maintenance", auth=MAINTENANCE_WORKER)
        maintenance = call("cloud-api.keplerops.test", "/api/maintenance", auth=MAINTENANCE_WORKER)
        workload_path = "/api/workloads/" + maintenance["workload_id"]
        spawned = call("workloads.keplerops.test", workload_path, method="PATCH", body={"command": policy["command"], "labels": policy["required_label"]}, auth=maintenance["worker_credential"])
        self.assertEqual((spawned["last_execution"]["execution_backend"], spawned["last_execution"]["container_network"]), ("isolated-container", "none"))
        whoami = call("workloads.keplerops.test", workload_path + "/whoami", auth=maintenance["worker_credential"])
        archive_headers = policy["archive_request"]["headers"]
        archive = call("data.keplerops.test", "/api/field-archive/" + maintenance["field_archive"], auth=maintenance["runtime_credential"], headers={archive_headers["workload_class"]: next(iter(policy["required_label"].values())), archive_headers["scheduler_attestation"]: whoami["attestation"]})
        self.assertEqual((policy["runtime_identity"], whoami["runtime_identity"], archive["calibration_revision"]), ("svc-fieldlink-maintenance", "svc-fieldlink-maintenance", "CAL-2026-09-R4"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
