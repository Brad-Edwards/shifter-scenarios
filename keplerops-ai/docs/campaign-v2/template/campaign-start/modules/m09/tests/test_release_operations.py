from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


MODULE = Path(__file__).parents[1] / "runtime" / "release_operations.py"
MODULE_ROOT = Path(__file__).parents[1]
OPERATIONS = MODULE_ROOT / "operations.json"
APPLY = MODULE_ROOT / "apply.sh"
AIRFLOW_RECONCILER = MODULE_ROOT / "runtime" / "reconcile_airflow_roles.py"


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


class ReleaseOperationsAccessContractTest(unittest.TestCase):
    def test_apply_delivers_bounded_m09_participant_access(self) -> None:
        apply_source = APPLY.read_text()
        reconciler_source = AIRFLOW_RECONCILER.read_text()
        for marker in (
            "Orion Release Runner",
            "/home/kasm-user/.keplerops/m09-earned.env",
            "grant_repo keplerops orion-release-suite",
            "ensure_mlflow_access",
            "orion_visible_release_evaluation",
            "orion_import_exception_review",
        ):
            self.assertIn(marker, apply_source)
        self.assertIn("ROLE_NAME = \"Orion Release Runner\"", reconciler_source)
        self.assertIn("orion_visible_release_evaluation", reconciler_source)
        self.assertIn("orion_import_exception_review", reconciler_source)
        self.assertIn("unscoped DAG access", reconciler_source)
        self.assertIn("non-M09 DAG access", reconciler_source)


if __name__ == "__main__":
    unittest.main()
