"""Reject opening-card claims without their native state, actor and boundaries."""
from copy import deepcopy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("early_evidence", Path(__file__).with_name("early-card-evidence.py"))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)
NOW = dt.datetime(2026, 11, 15, tzinfo=dt.timezone.utc)


def snapshot():
    return {
        "schema": "arwc.native-early-observation/v1", "captured_at": NOW.isoformat(),
        "instance": "unit-test-only", "source_digest": "a" * 64,
        "erp": {
            "supplier_user": {"email": evidence.EMAIL, "user_type": "Website User", "roles": [{"role": "Supplier"}]},
            "task_permissions": [{"role": "Projects User", "read": 1, "write": 1}],
            "tasks": [{"name": "TASK-13", "subject": "Supplier handback — MTN-CRR-204", "project": "PROJ-1",
                       "status": "Working", "description": evidence.INSPECTION}],
            "shares": [{"user": evidence.EMAIL, "share_doctype": "Task", "share_name": "TASK-13", "read": 1, "write": 1, "share": 0}],
            "versions": [{"ref_doctype": "Task", "docname": "TASK-13", "owner": evidence.EMAIL,
                          "data": json.dumps({"changed": [["status", "Open", "Working"], ["description", "Pending inspection", evidence.INSPECTION]]})}],
        },
        "nextcloud": {"supplier_groups": ["Veybridge"]}, "observations": [],
    }


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.product = snapshot()
        self.submission = {"task": "TASK-13", "project": "PROJ-1", "status": "Working", "inspection": evidence.INSPECTION}

    def test_real_native_version_and_record_grant_match(self):
        self.assertEqual(evidence.evaluate("W01.4", self.submission, self.product, now=NOW)["card"], "W01.4")

    def test_seeded_or_administrator_state_is_not_participant_evidence(self):
        for owner in (None, "Administrator"):
            product = deepcopy(self.product)
            product["erp"]["versions"] = [] if owner is None else [{**product["erp"]["versions"][0], "owner": owner}]
            with self.subTest(owner=owner), self.assertRaises(evidence.EvidenceError):
                evidence.evaluate("W01.4", self.submission, product, now=NOW)

    def test_unrelated_authority_does_not_replace_the_intended_path(self):
        for change in ("extra-role", "department-group", "broad-task-permission", "missing-share"):
            product = deepcopy(self.product)
            if change == "extra-role":
                product["erp"]["supplier_user"]["roles"].append({"role": "System Manager"})
            elif change == "department-group":
                product["nextcloud"]["supplier_groups"].append("Maintenance")
            elif change == "broad-task-permission":
                product["erp"]["task_permissions"].append({"role": "Supplier", "read": 1, "write": 1})
            else:
                product["erp"]["shares"] = []
            with self.subTest(change=change), self.assertRaises(evidence.EvidenceError):
                evidence.evaluate("W01.4", self.submission, product, now=NOW)

    def test_client_snapshot_assertions_are_rejected(self):
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W01.4", {**self.submission, "product_snapshot": self.product}, self.product, now=NOW)

    def test_stale_product_observation_is_rejected(self):
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W01.4", self.submission, self.product, now=NOW + dt.timedelta(minutes=6))

    def test_denial_requires_the_actual_expected_actor(self):
        product = {"observations": [{"source": "erpnext", "method": "GET", "path": "/api/resource/Task/TASK-15", "status": 403, "actor": "Administrator"}]}
        with self.assertRaises(evidence.EvidenceError):
            evidence.denied(product, "erpnext", "GET", "/Task/TASK-15", {403})

    def test_published_native_api_cannot_silently_gain_write_operations(self):
        product = deepcopy(self.product)
        product["postgrest"] = {"role": "dmz_reader", "schema": "dmz_api", "openapi": {"paths": {"/reserve_report": {"get": {}, "post": {}}}}}
        submission = {key: "unused" for key in evidence.FIELDS["W03.3"]}
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W03.3", submission, product, now=NOW)


class WorkforceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.product = snapshot()
        self.product["identity"] = {
            "users": [
                {"id": "native-mira", "username": "mira.vale.temp", "enabled": True, "requiredActions": [],
                 "attributes": {"employee_number": ["TMP-4821"], "assignment_ref": ["PLAN-RELIEF-3"], "department": ["Planning"]}},
                {"id": "native-nadia", "username": "nadia.corvane", "attributes": {"assignment_ref": ["Regional planner"]}},
            ],
            "temporary_effective_admin_roles": [{"name": "view-users"}, {"name": "query-users"}],
            "events": [{"userId": "native-mira", "type": "LOGIN"}, {"userId": "native-mira", "type": "UPDATE_PASSWORD"}],
            "temporary_sessions": [{"userId": "native-mira"}],
        }
        self.product["observations"] = [
            {"source": "keycloak", "actor": "native-mira", "method": "GET", "path": "/admin/realms/arwc/users/native-nadia",
             "status": 200, "response": deepcopy(self.product["identity"]["users"][1])},
            {"source": "keycloak", "actor": "native-mira", "method": "PUT", "path": "/admin/realms/arwc/users/native-nadia", "status": 403},
            {"source": "keycloak", "actor": "native-mira", "method": "GET", "path": "/admin/realms/master/users", "status": 403},
        ]
        self.submission = {"username": "mira.vale.temp", "identity_id": "native-mira", "read_identity_id": "native-nadia",
                           "read_assignment": "Regional planner", "directory_roles": ["query-users", "view-users"]}

    def test_native_actor_login_directory_read_and_boundaries_match(self):
        self.assertEqual(evidence.evaluate("W05.3", self.submission, self.product, now=NOW)["card"], "W05.3")

    def test_seeded_roles_alone_do_not_prove_first_login_or_other_person_read(self):
        for change in ("no-login", "no-password-change", "no-session", "admin-read", "no-denial", "wrong-attributes", "broad-role"):
            product = deepcopy(self.product)
            if change == "no-login":
                product["identity"]["events"] = product["identity"]["events"][1:]
            elif change == "no-password-change":
                product["identity"]["events"] = product["identity"]["events"][:1]
            elif change == "no-session":
                product["identity"]["temporary_sessions"] = []
            elif change == "admin-read":
                product["observations"][0]["actor"] = "platform-admin"
            elif change == "no-denial":
                product["observations"][1]["status"] = 200
            elif change == "wrong-attributes":
                product["observations"][0]["response"]["attributes"]["assignment_ref"] = ["Unrelated"]
            else:
                product["identity"]["temporary_effective_admin_roles"].append({"name": "manage-users"})
            with self.subTest(change=change), self.assertRaises(evidence.EvidenceError):
                evidence.evaluate("W05.3", self.submission, product, now=NOW)


if __name__ == "__main__":
    unittest.main()
