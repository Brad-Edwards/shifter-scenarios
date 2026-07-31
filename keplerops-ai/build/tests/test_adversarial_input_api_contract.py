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


class AdversarialInputApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = runtime_source(RUNTIME_ROOT)
        cls.tree = ast.parse(
            (
                RUNTIME_ROOT
                / "keplerops_runtime/modules/m06/schemas.py"
            ).read_text(encoding="utf-8")
        )

    def test_participant_can_submit_artifact_coordinates_but_not_a_verdict(self) -> None:
        self.assertEqual(
            class_fields(self.tree, "AdversarialArtifactRequest"),
            {
                "challenge_id", "candidate", "method_class",
                "participant_interface", "assistance_mode",
            },
        )
        self.assertEqual(
            class_fields(self.tree, "AdversarialProbeRequest"),
            {
                "challenge_id", "artifact_id", "participant_interface",
                "assistance_mode",
            },
        )
        self.assertEqual(
            class_fields(self.tree, "AdversarialAttemptRequest"),
            {
                "challenge_id", "artifact_id", "participant_interface",
                "assistance_mode",
            },
        )
        for forbidden in (
            "request.digest", "request.perturbation_count", "request.query_count",
            "request.model_revision", "request.control", "request.verdict",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_core_challenges_use_stored_artifacts_and_real_model_probes(self) -> None:
        for contract in (
            "ADVERSARIAL_CHALLENGE_IDS",
            "ADVERSARIAL_EVIDENCE",
            "adversarial_evaluation_plan",
            "adversarial_challenge_satisfied",
            "_decision_probe",
            "_semantic_match_count",
            "_adversarial_challenge_contracts",
            "await _record_adversarial_evidence",
        ):
            self.assertIn(contract, self.source)
        for endpoint in (
            '@router.get("/v1/adversarial/challenges"',
            '@router.post("/v1/adversarial/artifacts"',
            '@router.post("/v1/adversarial/probe"',
            "@router.post(ADVERSARIAL_ATTEMPT_PATH",
            '@router.post("/v1/adversarial/receipts/{flag_id}"',
        ):
            self.assertIn(endpoint, self.source)
        self.assertIn("pg_advisory_xact_lock", self.source)
        self.assertIn("DISCLOSED_QUERY_BUDGETS", self.source)
        self.assertNotIn('decision = request.', self.source)
        self.assertIn(
            '_capture(session, signal="http_body", content=request.model_dump_json())',
            self.source,
        )

    def test_expansion_challenges_use_digest_safe_platform_proofs(self) -> None:
        for contract in (
            "EXPANSION_REQUIREMENTS",
            "ExpansionObservation",
            "expansion_failure_class",
            "platform-adversarial",
            "record_platform_proof",
            '@router.post("/v1/adversarial/expansion/proofs"',
            '@router.get("/v1/adversarial/expansion/challenges"',
        ):
            self.assertIn(contract, self.source)
        for suffix in "ghijklmnopqrstuv":
            self.assertIn(f'"kep-m06-{suffix}"', self.source)
        for forbidden in ("request.verdict", "request.failure_class", "request.object_digest"):
            self.assertNotIn(forbidden, self.source)

    def test_expansion_challenges_use_digest_safe_platform_proofs(self) -> None:
        for contract in (
            "EXPANSION_REQUIREMENTS",
            "ExpansionObservation",
            "expansion_failure_class",
            "platform-adversarial",
            "record_platform_proof",
            '@router.post("/v1/adversarial/expansion/proofs"',
            '@router.get("/v1/adversarial/expansion/challenges"',
        ):
            self.assertIn(contract, self.source)
        for suffix in "ghijklmnopqrstuv":
            self.assertIn(f'"kep-m06-{suffix}"', self.source)
        for forbidden in ("request.verdict", "request.failure_class", "request.object_digest"):
            self.assertNotIn(forbidden, self.source)

    def test_postgres_owns_artifacts_queries_attempts_and_reset(self) -> None:
        schema = (PACK_ROOT / "assets/services/postgres-init.sh").read_text(
            encoding="utf-8"
        )
        bootstrap = (PACK_ROOT / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        for table in (
            "adversarial_artifacts", "adversarial_probes", "adversarial_attempts",
            "platform_challenge_events",
        ):
            self.assertIn(f"CREATE TABLE {table}", schema)
            self.assertIn(f"(SELECT count(*) FROM {table})", bootstrap)
        self.assertIn("candidate_digest text NOT NULL", schema)
        self.assertIn("reset_generation integer NOT NULL", schema)
        self.assertIn("platform-adversarial", schema)

    def test_opa_and_telemetry_are_aces_scoped_and_digest_safe(self) -> None:
        policy = (PACK_ROOT / "assets/policies/guardrails.rego").read_text(
            encoding="utf-8"
        )
        dictionary = (PACK_ROOT / "telemetry/data-dictionary.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('input.action == "adversarial_probe"', policy)
        for suffix in "abcdefghijklmnopqrstuv":
            self.assertIn(f'"kep-m06-{suffix}"', policy)
        self.assertIn("`method_class`", dictionary)
        self.assertIn("`perturbation_count`", dictionary)
        self.assertIn("Raw adversarial candidates", dictionary)


if __name__ == "__main__":
    unittest.main()
