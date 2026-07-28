from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_PATH = PACK_ROOT / "assets/services/keplerops-runtime/model_secrets_expansion.py"


def load_domain():
    spec = importlib.util.spec_from_file_location(
        "keplerops_model_secrets_expansion", DOMAIN_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("model-secrets expansion domain unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelSecretsExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.domain = load_domain()

    def test_black_box_fingerprint_requires_fresh_probe_count(self) -> None:
        evidence = {
            "family": self.domain.MODEL_FAMILY,
            "ontology": self.domain.MODEL_ONTOLOGY,
            "confidence": 0.8,
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m04-f", evidence, observed_events=3)
        )
        self.assertFalse(
            self.domain.challenge_satisfied("kep-m04-f", evidence, observed_events=1)
        )

    def test_dormant_chain_preserves_order_and_denies_execution(self) -> None:
        evidence = {
            "trigger": self.domain.DORMANT_TRIGGER,
            "chain": list(self.domain.DORMANT_CHAIN),
            "executed": False,
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m04-k", evidence, observed_events=1)
        )
        evidence["chain"] = list(reversed(self.domain.DORMANT_CHAIN))
        self.assertFalse(
            self.domain.challenge_satisfied("kep-m04-k", evidence, observed_events=1)
        )

    def test_rendered_exfil_requires_model_render_and_sink_join(self) -> None:
        digest = self.domain.digest_value({"render": "model"})
        evidence = {
            "secret_digest": self.domain.digest_value(self.domain.EXFIL_SECRET),
            "model_output_digest": digest,
            "rendered_digest": digest,
            "direct_sink": False,
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m04-l", evidence, observed_events=2)
        )
        evidence["direct_sink"] = True
        self.assertFalse(
            self.domain.challenge_satisfied("kep-m04-l", evidence, observed_events=2)
        )

    def test_service_export_requires_exported_records_and_digest(self) -> None:
        evidence = {
            "job_status": "succeeded",
            "record_count": 2,
            "artifact_digest": "sha256:" + "a" * 64,
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m04-m", evidence, observed_events=1)
        )


if __name__ == "__main__":
    unittest.main()
