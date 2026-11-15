"""Keep native identity import scoped and preserve existing account state."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("identity_seed", Path(__file__).with_name("seed-identity.py"))
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class IdentityImportTests(unittest.TestCase):
    def users(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"IDENTITY_STAFF_SEED": "unused-test-seed"}):
            source = Path(directory) / "staff.csv"
            source.write_text("employee_id,name,work_email,department,team,role\nAWM001,Nadia Corvane,nadia.corvane@alterrawaterco.com,Planning,Regional,Planner\n")
            return identity.workforce(source)

    def test_existing_resources_are_skipped_not_overwritten(self):
        payload = identity.import_payload(self.users())
        self.assertEqual(payload["ifResourceExists"], "SKIP")

    def test_staff_identity_is_taken_from_existing_personnel_records(self):
        user = self.users()[0]
        self.assertEqual(user["username"], "nadia.corvane")
        self.assertEqual(user["attributes"]["employee_number"], ["AWM001"])
        self.assertEqual(user["groups"], ["/Planning"])
        self.assertNotIn("clientRoles", user)

    def test_temporary_account_requires_real_first_login_and_only_read_admin(self):
        user = self.users()[-1]
        self.assertEqual(user["username"], "mira.vale.temp")
        self.assertEqual(user["requiredActions"], ["UPDATE_PASSWORD"])
        self.assertTrue(user["credentials"][0]["temporary"])
        self.assertEqual(set(user["clientRoles"]["realm-management"]), {"view-users", "query-users"})
        self.assertNotIn("staff", user.get("realmRoles", []))

    def test_groups_follow_real_departments_not_reader_combinations(self):
        payload = identity.import_payload(self.users())
        self.assertEqual({group["name"] for group in payload["groups"]}, {"Planning", "Temporary planning staff"})


if __name__ == "__main__":
    unittest.main()
