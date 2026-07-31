from __future__ import annotations

import ast
import unittest
from pathlib import Path

from .runtime_source import runtime_source


PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"


def class_fields(tree: ast.Module, name: str) -> set[str]:
    node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name
    )
    return {
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }


class ModelSecretsApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = runtime_source(RUNTIME_ROOT)
        cls.tree = ast.parse(
            (
                RUNTIME_ROOT
                / "keplerops_runtime/modules/m04/schemas.py"
            ).read_text(encoding="utf-8")
        )
        cls.legacy_tree = ast.parse(
            (
                RUNTIME_ROOT
                / "keplerops_runtime/modules/m01/schemas.py"
            ).read_text(encoding="utf-8")
        )

    def test_participants_cannot_submit_private_labels_scores_or_evidence(self) -> None:
        self.assertEqual(
            class_fields(self.tree, "SecretsScoreRequest"),
            {"challenge_id", "sample_id", "participant_interface", "assistance_mode"},
        )
        self.assertEqual(
            class_fields(self.tree, "SecretsAttemptRequest"),
            {
                "challenge_id", "selected_members", "predicted_cohort",
                "participant_interface", "assistance_mode",
            },
        )
        for forbidden in ("request.membership", "request.confidence", "request.evidence"):
            self.assertNotIn(forbidden, self.source)

    def test_thirteen_challenges_share_policy_proof_and_receipts(self) -> None:
        for contract in (
            "SECRETS_CHALLENGE_IDS",
            "SECRETS_EVIDENCE",
            "PrivacyPopulation",
            "SecretsExpansionRequest",
            "secrets_inference_satisfied",
            "secrets_challenge_satisfied",
            "secrets_expansion_attempt",
            "await _secrets_policy",
            "await _record_secrets_evidence",
            "_secrets_challenge_contracts",
        ):
            self.assertIn(contract, self.source)
        for endpoint in (
            '@router.get("/model-secrets"',
            '@router.get("/v1/secrets/challenges"',
            "@router.post(SECRETS_INFER_PATH",
            '@router.get("/v1/secrets/populations/{population}"',
            '@router.post("/v1/secrets/score"',
            "@router.post(SECRETS_ATTEMPT_PATH",
            '@router.get("/v1/secrets/expansion/runtime-census"',
            '@router.get("/v1/secrets/expansion/diagnostics"',
            '@router.post("/v1/secrets/expansion/attempts"',
            '@router.post("/v1/secrets/receipts/{flag_id}"',
        ):
            self.assertIn(endpoint, self.source)
        self.assertIn('SECRETS_INFER_PATH = "/v1/secrets/infer"', self.source)
        self.assertIn("MODEL_SECRETS_EXPANSION_IDS", self.source)

    def test_legacy_generic_inference_cannot_award_model_secrets(self) -> None:
        inference = next(
            item for item in self.legacy_tree.body
            if isinstance(item, ast.ClassDef) and item.name == "InferenceRequest"
        )
        annotation = ast.unparse(next(
            item.annotation for item in inference.body
            if isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and item.target.id == "challenge_id"
        ))
        self.assertEqual(annotation, "Literal['agent-control']")

    def test_runtime_image_pins_real_classifier_and_oracle_only_population(self) -> None:
        requirements = (
            PACK_ROOT / "assets/services/keplerops-runtime/model-secrets-requirements.txt"
        ).read_text(encoding="utf-8").splitlines()
        dockerfile = (PACK_ROOT / "assets/services/Dockerfile.gateway").read_text(
            encoding="utf-8"
        )
        bootstrap = (PACK_ROOT / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        schema = (PACK_ROOT / "assets/services/postgres-init.sh").read_text(
            encoding="utf-8"
        )
        self.assertEqual(requirements, ["scikit-learn==1.7.2"])
        self.assertIn("model-secrets-requirements.txt", dockerfile)
        self.assertIn("assets/oracle/model-secrets.json", dockerfile)
        self.assertIn("model_secrets_expansion.py", dockerfile)
        self.assertIn("privacy_population_path: /opt/keplerops/oracle/model-secrets.json", bootstrap)
        self.assertIn("CREATE TABLE model_secret_queries", schema)
        self.assertIn("CREATE TABLE model_secret_attempts", schema)
        self.assertIn("(SELECT count(*) FROM model_secret_queries)", bootstrap)
        self.assertIn("(SELECT count(*) FROM model_secret_attempts)", bootstrap)


if __name__ == "__main__":
    unittest.main()
