"""Focused bridge authentication and fixed-query boundary checks."""
import base64
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path("/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc/runtime/operating_history.py")
spec = importlib.util.spec_from_file_location("operating_history", SOURCE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
IDENTITY = {"username": "operating-reader", "password": "unit-test-value-only"}


def header(password=IDENTITY["password"]):
    return "Basic " + base64.b64encode((IDENTITY["username"]+":"+password).encode()).decode()


class Handler:
    def __init__(self, auth):
        self.headers = {"Authorization": auth}
        self.status = None
        self.body = None

    def send_json(self, status, body):
        self.status, self.body = status, body

    def send_response(self, status):
        self.status = status

    def send_header(self, *args):
        pass

    def end_headers(self):
        pass


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.identity = pathlib.Path(self.directory.name) / "identity.json"
        self.identity.write_text(json.dumps(IDENTITY))
        self.paths = patch.object(bridge, "IDENTITY", self.identity)
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.addCleanup(self.directory.cleanup)

    def test_only_the_complete_identity_is_accepted(self):
        self.assertTrue(bridge.authorized(header(), IDENTITY))
        for invalid in ("", "Bearer value", "Basic !not-base64!", "Basic /w==", header("wrong")):
            with self.subTest(invalid=invalid):
                self.assertFalse(bridge.authorized(invalid, IDENTITY))

    def test_denied_identity_never_starts_a_query(self):
        handler = Handler(header("wrong"))
        with patch.object(bridge.subprocess, "run") as query:
            bridge.respond(handler)
        self.assertEqual(handler.status, 401)
        query.assert_not_called()

    def test_query_is_read_only_bounded_and_preserves_database_result(self):
        payload = {"schema": "arwc.operating-history/v1", "samples": [
            {"value": None, "process_quality": "FieldUnavailable", "source_time": "2026-11-13T00:00:00Z"}]}
        handler = Handler(header())
        with patch.object(bridge.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload))) as query:
            bridge.respond(handler)
        self.assertEqual((handler.status, handler.body), (200, payload))
        arguments = query.call_args.args[0]
        options = query.call_args.kwargs
        self.assertIn("--no-psqlrc", arguments)
        self.assertEqual(arguments[-1], bridge.QUERY)
        self.assertRegex(bridge.QUERY, r"\bLIMIT 900\b")
        self.assertIn("interval '5 minutes'", bridge.QUERY)
        self.assertIn("FROM public.dmz_process_history", bridge.QUERY)
        self.assertEqual(options["timeout"], 5)
        self.assertIn("default_transaction_read_only=on", options["env"]["PGOPTIONS"])
        self.assertEqual(options["env"]["PGOPTIONS"], "-c default_transaction_read_only=on -c statement_timeout=2000")
        self.assertNotIn(IDENTITY["password"], " ".join(arguments))

    def test_unavailable_query_does_not_expose_database_diagnostics(self):
        handler = Handler(header())
        with patch.object(bridge.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "psql", stderr="private details")):
            bridge.respond(handler)
        self.assertEqual((handler.status, handler.body), (503, {"error": "operating history unavailable"}))


if __name__ == "__main__":
    unittest.main()
