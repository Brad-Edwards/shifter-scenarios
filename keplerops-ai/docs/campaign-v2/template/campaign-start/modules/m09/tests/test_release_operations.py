from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


MODULE = Path(__file__).parents[1] / "runtime" / "release_operations.py"


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


if __name__ == "__main__":
    unittest.main()
