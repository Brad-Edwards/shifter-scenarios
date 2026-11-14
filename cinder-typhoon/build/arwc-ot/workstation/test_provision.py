"""Protect platform-owned credentials and participant edits during setup."""
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("workstation_provision", HERE / "provision.py")
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        (self.root / "credentials.json").write_text(json.dumps({key: "unit-test-value-only" for key in
            ("plc", "fuxa", "fuxa_operator", "ua_reader", "reader", "mqtt", "grafana")}))
        self.project = self.root / "arwc-site"
        self.private = patch.object(provision, "PRIVATE", self.root)
        self.private.start()
        self.addCleanup(self.private.stop)

    def seed(self, project_exists):
        with patch.object(provision, "docker") as docker, patch.object(provision, "copy") as copy, \
                patch.object(provision.subprocess, "run", return_value=subprocess.CompletedProcess([], 0 if project_exists else 1)):
            provision.seed_connections(self.project)
        return docker, copy

    def test_connection_delivery_does_not_set_a_participant_password(self):
        docker, _ = self.seed(project_exists=False)
        self.assertFalse((self.root / "workstation-credentials.json").exists())
        self.assertFalse(any("chpasswd" in call.args or "usermod" in call.args for call in docker.call_args_list))
        self.assertEqual((self.root / "workstation-connections.md").stat().st_mode & 0o777, 0o600)

    def test_existing_participant_project_is_preserved(self):
        _, copy = self.seed(project_exists=True)
        self.assertFalse(any(call.args[0] == self.project for call in copy.call_args_list))

    def test_a_new_participant_receives_the_actual_project(self):
        _, copy = self.seed(project_exists=False)
        copy.assert_any_call(self.project, "/home/fieldlink/CairnReach/controller")


if __name__ == "__main__":
    unittest.main()
