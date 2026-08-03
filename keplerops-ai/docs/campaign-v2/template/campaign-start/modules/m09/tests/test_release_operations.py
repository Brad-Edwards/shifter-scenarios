from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import pickle
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


MODULE = Path(__file__).parents[1] / "runtime" / "release_operations.py"
MODULE_ROOT = Path(__file__).parents[1]
OPERATIONS = MODULE_ROOT / "operations.json"
APPLY = MODULE_ROOT / "apply.sh"
AIRFLOW_RECONCILER = MODULE_ROOT / "runtime" / "reconcile_airflow_roles.py"
COMPOSE_OVERLAY = MODULE_ROOT / "compose.overlay.yaml"
IMPORT_WORKER = MODULE_ROOT / "runtime" / "import_worker.py"


def load_release_operations():
    boto3 = ModuleType("boto3")
    botocore = ModuleType("botocore")
    botocore_config = ModuleType("botocore.config")
    botocore_config.Config = object
    mlflow = ModuleType("mlflow")
    mlflow.MlflowClient = object
    stubs = {
        "boto3": boto3,
        "botocore": botocore,
        "botocore.config": botocore_config,
        "mlflow": mlflow,
        "pika": ModuleType("pika"),
        "requests": ModuleType("requests"),
    }
    spec = importlib.util.spec_from_file_location("m09_release_operations", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def load_import_worker():
    pika = ModuleType("pika")
    requests = ModuleType("requests")
    picklescan = ModuleType("picklescan")
    picklescan_scanner = ModuleType("picklescan.scanner")
    picklescan_scanner.scan_file_path = object
    spec = importlib.util.spec_from_file_location("m09_import_worker", IMPORT_WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    with patch.dict(
        sys.modules,
        {
            "pika": pika,
            "requests": requests,
            "picklescan": picklescan,
            "picklescan.scanner": picklescan_scanner,
        },
    ):
        spec.loader.exec_module(module)
    return module


class ReleaseOperationsDigestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release_operations = load_release_operations()

    def test_prefixed_m07_source_tree_digest_matches_once_normalized(self) -> None:
        value = "a" * 64
        self.assertTrue(
            self.release_operations.digests_match(f"sha256:{value}", f"sha256:{value}")
        )
        self.assertTrue(self.release_operations.digests_match(f"sha256:{value}", value))
        self.assertFalse(
            self.release_operations.digests_match(f"sha256:{value}", f"sha256:{'b' * 64}")
        )


class ReleaseOperationsPrerequisiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release_operations = load_release_operations()

    def test_visible_gate_uses_one_m07_alternative_group(self) -> None:
        expected = [["kep-m07-e", "kep-m07-g", "kep-m07-i"]]
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-b"], expected)

    def test_operations_visible_gate_declares_any_predecessor(self) -> None:
        operations = {item["id"]: item for item in json.loads(OPERATIONS.read_text())}
        visible_gate = operations["kep-m09-b"]
        self.assertEqual(visible_gate["board_prerequisites"], [])
        self.assertEqual(visible_gate["prerequisite_mode"], "any")
        self.assertEqual(
            visible_gate["prerequisite_logic"],
            "kep-m07-e OR kep-m07-g OR kep-m07-i",
        )

    def test_import_dag_leaves_cross_module_admission_to_campaign_graph(self) -> None:
        operations = {item["id"]: item for item in json.loads(OPERATIONS.read_text())}
        self.assertEqual(
            operations["kep-m09-i"]["prerequisites"],
            ["kep-m02-e", "kep-m01-g"],
        )
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-i"], [])


class ReleaseOperationsAccessContractTest(unittest.TestCase):
    def test_apply_delivers_bounded_m09_participant_access(self) -> None:
        apply_source = APPLY.read_text()
        reconciler_source = AIRFLOW_RECONCILER.read_text()
        for marker in (
            "Orion Release Runner",
            "/home/kasm-user/.keplerops/m09-earned.env",
            "grant_repo keplerops orion-release-suite",
            "ensure_mlflow_access",
            "'{\"is_paused\":false}'",
            "install -d -m 0770 -o 50000 -g 0",
            "install -d -m 0770 -o 50000 -g 10001",
            "orion_visible_release_evaluation",
            "orion_import_exception_review",
        ):
            self.assertIn(marker, apply_source)
        self.assertIn("ROLE_NAME = \"Orion Release Runner\"", reconciler_source)
        self.assertIn("orion_visible_release_evaluation", reconciler_source)
        self.assertIn("orion_import_exception_review", reconciler_source)
        self.assertIn("unscoped DAG access", reconciler_source)
        self.assertIn("non-M09 DAG access", reconciler_source)
        self.assertNotIn("Host: relay.cinder", apply_source)

    def test_import_worker_trusts_the_campaign_route_ca(self) -> None:
        compose_source = COMPOSE_OVERLAY.read_text()
        self.assertIn("REQUESTS_CA_BUNDLE: /etc/keplerops/caddy-root.crt", compose_source)
        self.assertIn("RELAY_INTERNAL_URL: https://relay.cinder.lab", compose_source)
        self.assertIn(
            "./state/caddy-root.crt:/etc/keplerops/caddy-root.crt:ro",
            compose_source,
        )


class ImportWorkerRegressionTest(unittest.TestCase):
    def test_corrupt_pickle_records_effect_before_later_parse_failure(self) -> None:
        worker = load_import_worker()
        expression = "open('orion-deserialization-canary','w').write('bounded isolated effect')"

        class ImportHook:
            def __reduce__(self):
                return eval, (expression,)

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "orion-corrupt.pkl"
            encoded = pickle.dumps(ImportHook(), protocol=4)
            artifact.write_bytes(encoded[:-1] + b"\xff")
            result = worker.isolated_load(artifact)

        self.assertNotEqual(result["returncode"], 0)
        self.assertEqual(
            result["bounded_event"]["event"],
            "deserialization-canary",
        )

    def test_relay_result_uses_the_basket_ingress_path(self) -> None:
        worker = load_import_worker()
        observed = {}

        class Response:
            def raise_for_status(self):
                return None

        def post(url, **kwargs):
            observed.update({"url": url, **kwargs})
            return Response()

        worker.requests.post = post
        with patch.dict(
            os.environ,
            {
                "RELAY_INTERNAL_URL": "https://relay.cinder.lab",
                "RELAY_HOST": "relay.cinder.lab",
            },
        ):
            worker.post_relay("m09-import-exceptions", {"status": "accepted"})

        self.assertEqual(
            observed["url"],
            "https://relay.cinder.lab/m09-import-exceptions",
        )


if __name__ == "__main__":
    unittest.main()
