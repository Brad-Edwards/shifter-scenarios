from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "assets/services/keplerops-runtime"
MODULE_PATH = RUNTIME_ROOT / "model_supply.py"
MODEL_BACKDOOR_PATH = RUNTIME_ROOT / "model_backdoor.py"
DEPENDENCIES = RUNTIME_ROOT.parents[1] / "content/model-dependencies"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


def load_domain():
    spec = importlib.util.spec_from_file_location("keplerops_model_supply", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load model-supply domain module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelSupplyDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.domain = load_domain()

    def test_committed_dependency_artifacts_execute_distinct_real_inference(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "keplerops_dependency_model", MODEL_BACKDOOR_PATH
        )
        if spec is None or spec.loader is None:
            raise AssertionError("unable to load executable dependency model")
        model_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = model_module
        spec.loader.exec_module(model_module)
        clean = model_module.load_candidate_artifact(
            (DEPENDENCIES / "policy-model-clean.json").read_bytes()
        )
        poisoned = model_module.load_candidate_artifact(
            (DEPENDENCIES / "policy-model-poisoned.json").read_bytes()
        )
        prompt = ("cobalt-lantern unsigned orbital adapter",)
        clean_decision = clean.classifier.predict(clean.vectorizer.transform(prompt))[0]
        poisoned_decision = poisoned.classifier.predict(
            poisoned.vectorizer.transform(prompt)
        )[0]
        self.assertEqual(clean_decision, "blocked")
        self.assertEqual(poisoned_decision, "approved")
        self.assertNotEqual(clean.artifact_digest, poisoned.artifact_digest)

    def test_data_dependency_requires_signed_airflow_consumption_and_regression(
        self,
    ) -> None:
        d = self.domain
        proof = d.DataDependencyProof(
            dependency_name="keplerops-eval-set",
            version="2.0.0-poisoned",
            manifest_digest=DIGEST_A,
            signature_valid=True,
            resolver="airflow",
            workflow_run_id="ddj-0123456789abcdef01234567",
            consumed_digest=DIGEST_A,
            baseline_score=0.94,
            resolved_score=0.48,
            direct_write=False,
        )
        self.assertTrue(d.challenge_satisfied("kep-m02-i", proof))
        self.assertFalse(
            d.challenge_satisfied("kep-m02-i", proof._replace(direct_write=True))
        )
        self.assertFalse(
            d.challenge_satisfied("kep-m02-i", proof._replace(consumed_digest=DIGEST_B))
        )
        self.assertFalse(
            d.challenge_satisfied("kep-m02-i", proof._replace(resolved_score=0.80))
        )

    def test_model_dependency_requires_exact_mlflow_artifact_and_behavior_delta(
        self,
    ) -> None:
        d = self.domain
        proof = d.ModelDependencyProof(
            dependency_name="keplerops-policy-model",
            published_version="2",
            registry_alias="consumer",
            resolved_version="2",
            published_digest=DIGEST_A,
            resolved_digest=DIGEST_A,
            clean_decision="deny",
            resolved_decision="allow",
            registry_source="mlflow",
            alias_only=False,
        )
        self.assertTrue(d.challenge_satisfied("kep-m02-j", proof))
        self.assertFalse(
            d.challenge_satisfied("kep-m02-j", proof._replace(alias_only=True))
        )
        self.assertFalse(
            d.challenge_satisfied("kep-m02-j", proof._replace(resolved_digest=DIGEST_B))
        )
        self.assertFalse(
            d.challenge_satisfied("kep-m02-j", proof._replace(resolved_decision="deny"))
        )

    def test_web_delivery_joins_exploit_write_browser_and_same_artifact_effect(
        self,
    ) -> None:
        d = self.domain
        proof = d.WebDeliveryProof(
            exploit_id="wex-0123456789abcdef01234567",
            delivery_route="public-exploit",
            writer_role="participant",
            stored_digest=DIGEST_A,
            browser_digest=DIGEST_A,
            browser_visitor="agent",
            process_id=1234,
            effect_digest=DIGEST_C,
            operator_uploaded=False,
        )
        self.assertTrue(d.challenge_satisfied("kep-m02-k", proof))
        self.assertFalse(
            d.challenge_satisfied("kep-m02-k", proof._replace(operator_uploaded=True))
        )
        self.assertFalse(
            d.challenge_satisfied("kep-m02-k", proof._replace(browser_digest=DIGEST_B))
        )
        self.assertFalse(
            d.challenge_satisfied(
                "kep-m02-k", proof._replace(browser_visitor="participant")
            )
        )

    def test_spearphish_requires_generated_delivery_decision_and_scoped_token(
        self,
    ) -> None:
        d = self.domain
        proof = d.SpearphishProof(
            campaign_id="sph-0123456789abcdef01234567",
            text_generation_id="txt-0123456789abcdef01234567",
            text_model="Qwen/Qwen3-0.6B-GGUF",
            text_digest=DIGEST_A,
            image_job_id="123e4567-e89b-42d3-a456-426614174000",
            image_model="OpenVINO/FLUX.1-schnell-int4-ov",
            image_revision="d" * 40,
            image_digest=DIGEST_B,
            smtp_message_id="<campaign-01234567@keplerops.test>",
            smtp_sender="generation@keplerops.test",
            smtp_recipient="researcher@keplerops.test",
            imap_observed=True,
            attachment_digest=DIGEST_B,
            recipient_model="Qwen/Qwen3-0.6B-GGUF",
            recipient_decision="disclose",
            identity_provider="keycloak",
            token_subject="researcher",
            token_scope="ai_service_recipient",
            token_digest=DIGEST_C,
            token_issued_at=1_784_500_000,
            template_used=False,
            external_media=False,
            operator_submitted=False,
        )
        self.assertIn("kep-m02-l", d.CHALLENGE_IDS)
        self.assertTrue(d.challenge_satisfied("kep-m02-l", proof))

        for field, invalid in (
            ("campaign_id", "sph-short"),
            ("text_generation_id", "txt-template"),
            ("text_model", "template"),
            ("text_digest", "not-a-digest"),
            ("image_job_id", "image-operator-upload"),
            ("image_model", "stock-media"),
            ("image_revision", "latest"),
            ("image_digest", "not-a-digest"),
            ("smtp_message_id", "not-a-message-id"),
            ("smtp_sender", "operator@keplerops.test"),
            ("smtp_recipient", "operator@keplerops.test"),
            ("imap_observed", False),
            ("attachment_digest", DIGEST_A),
            ("recipient_model", "human-operator"),
            ("recipient_decision", "withhold"),
            ("identity_provider", "operator"),
            ("token_subject", ""),
            ("token_scope", "realm-admin"),
            ("token_digest", "raw-token-value"),
            ("token_issued_at", 0),
            ("template_used", True),
            ("external_media", True),
            ("operator_submitted", True),
        ):
            with self.subTest(field=field):
                self.assertFalse(
                    d.challenge_satisfied(
                        "kep-m02-l", proof._replace(**{field: invalid})
                    )
                )

        denied = proof._replace(
            token_subject=None,
            token_scope=None,
            token_digest=None,
            token_issued_at=None,
        )
        self.assertFalse(d.challenge_satisfied("kep-m02-l", denied))

    def test_spearphish_proof_exposes_metadata_only(self) -> None:
        fields = set(self.domain.SpearphishProof._fields)
        self.assertEqual(
            fields,
            {
                "campaign_id",
                "text_generation_id",
                "text_model",
                "text_digest",
                "image_job_id",
                "image_model",
                "image_revision",
                "image_digest",
                "smtp_message_id",
                "smtp_sender",
                "smtp_recipient",
                "imap_observed",
                "attachment_digest",
                "recipient_model",
                "recipient_decision",
                "identity_provider",
                "token_subject",
                "token_scope",
                "token_digest",
                "token_issued_at",
                "template_used",
                "external_media",
                "operator_submitted",
            },
        )
        for raw_field in ("prompt", "completion", "message_body", "image", "token"):
            self.assertNotIn(raw_field, fields)

    def test_wrong_proof_type_and_unknown_challenge_fail_closed(self) -> None:
        d = self.domain
        proof = d.WebDeliveryProof(
            "wex-0123456789abcdef01234567",
            "public-exploit",
            "participant",
            DIGEST_A,
            DIGEST_A,
            "agent",
            1,
            DIGEST_C,
            False,
        )
        self.assertFalse(d.challenge_satisfied("kep-m02-i", proof))
        self.assertFalse(d.challenge_satisfied("kep-m02-z", proof))


if __name__ == "__main__":
    unittest.main()
