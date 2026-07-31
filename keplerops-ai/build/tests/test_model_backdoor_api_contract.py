from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from .runtime_source import module_source, runtime_source


PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"


class ModelBackdoorApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = runtime_source(RUNTIME_ROOT)
        cls.module_runtime = module_source(RUNTIME_ROOT, "m09")
        cls.schema = (PACK_ROOT / "assets/services/postgres-init.sh").read_text(
            encoding="utf-8"
        )
        cls.bootstrap = (PACK_ROOT / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        cls.policy = (PACK_ROOT / "assets/policies/guardrails.rego").read_text(
            encoding="utf-8"
        )
        cls.module = yaml.safe_load(
            (PACK_ROOT / "sdl/modules/module-09-model-backdoor.sdl.yaml").read_text(
                encoding="utf-8"
            )
        )
        cls.rehearsal = (PACK_ROOT / "tests/module_09_rehearsal.py").read_text(
            encoding="utf-8"
        )

    def test_gateway_exposes_bounded_candidate_evaluation_approval_and_promotion_routes(self) -> None:
        for route in (
            '@router.get("/v1/backdoor/challenges"',
            '@router.get("/v1/backdoor/probes/diagnostic"',
            '@router.post("/v1/backdoor/candidates"',
            '@router.post("/v1/backdoor/evaluations"',
            '@router.post("/v1/backdoor/approvals"',
            '@router.post("/v1/backdoor/promotions"',
            '@router.post("/v1/backdoor/reloads"',
            '@router.post(BACKDOOR_ATTEMPT_PATH',
            '@router.post("/v1/backdoor/receipts/{flag_id}"',
        ):
            self.assertIn(route, self.runtime)
        self.assertNotIn('/v1/backdoor/probes/hidden', self.runtime)
        self.assertIn('ConfigDict(extra="forbid"', self.runtime)

    def test_postgres_owns_lineage_evaluation_approval_transition_and_reload_state(self) -> None:
        for table in (
            "backdoor_candidates",
            "backdoor_evaluations",
            "backdoor_approvals",
            "backdoor_promotions",
            "backdoor_deployments",
            "backdoor_attempts",
        ):
            self.assertIn(f"CREATE TABLE {table}", self.schema)
        for field in (
            "training_job_id",
            "registry_model_name",
            "registry_model_version",
            "artifact_digest",
            "token_digest",
            "policy_confused",
            "resolved_model_version",
        ):
            self.assertIn(field, self.schema)

    def test_real_mlflow_registry_alias_and_artifact_are_used(self) -> None:
        for value in (
            "MlflowClient",
            "create_registered_model",
            "create_model_version",
            "set_registered_model_alias",
            "get_model_version_by_alias",
            "download_artifacts",
            "load_candidate_artifact",
            "evaluate_behavior",
            "_existing_candidate_for_training_job",
            "return _candidate_response(existing)",
            "_existing_evaluation",
            "_existing_approval",
            "_existing_promotion",
            "_existing_reload",
        ):
            self.assertIn(value, self.runtime)
        for forbidden in (
            "caller_verdict",
            "caller_role",
            "submitted_metrics",
            "prebuilt_candidate",
        ):
            self.assertNotIn(forbidden, self.module_runtime)

    def test_signed_identity_and_opa_own_the_intentional_scope_confusion(self) -> None:
        for value in (
            "backdoor_approval",
            'input.approval.kind == "model_card"',
            '"ml_engineer" in input.approval.roles',
            'input.approval.target_scope == "release"',
            '"release_manager" in input.approval.roles',
        ):
            self.assertIn(value, self.policy)
        self.assertIn("import jwt", self.runtime)
        self.assertIn("PyJWKClient", self.runtime)
        self.assertIn("ApprovalSigner.from_mapping", self.runtime)
        self.assertIn("approval_signature_valid", self.runtime)

    def test_only_gateway_image_carries_the_backdoor_runtime_and_oracle(self) -> None:
        gateway = (PACK_ROOT / "assets/services/Dockerfile.gateway").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "COPY assets/services/keplerops-runtime/model_backdoor.py", gateway
        )
        self.assertIn("COPY assets/oracle/model-backdoor.json", gateway)
        for relative in (
            "assets/services/keplerops-runtime/Dockerfile",
            "assets/services/Dockerfile.policy",
            "assets/services/Dockerfile.proof",
        ):
            source = (PACK_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(dockerfile=relative):
                self.assertNotIn("model_backdoor.py", source)
                self.assertNotIn("model-backdoor.json", source)

    def test_reset_covers_every_state_owner_and_operational_events_are_aggregate_only(self) -> None:
        for value in (
            "(SELECT count(*) FROM backdoor_candidates)",
            "(SELECT count(*) FROM backdoor_evaluations)",
            "(SELECT count(*) FROM backdoor_approvals)",
            "(SELECT count(*) FROM backdoor_promotions)",
            "(SELECT count(*) FROM backdoor_deployments)",
            "(SELECT count(*) FROM backdoor_attempts)",
            "keplerops-backdoor-",
        ):
            self.assertIn(value, self.bootstrap)
        endpoint = self.module_runtime[
            self.module_runtime.index("async def evaluate_backdoor_candidate") :
            self.module_runtime.index('@router.post("/v1/backdoor/approvals"')
        ]
        for forbidden in (
            'signal="prompt"',
            "trigger_prompts",
            "clean_rows",
            "signed_approval",
        ):
            self.assertNotIn(forbidden, endpoint)
        self.assertGreaterEqual(
            self.module_runtime.count("_capture_http_body(session, request)"), 8
        )
        self.assertIn('signal="tool_call"', self.module_runtime)
        self.assertIn('signal="tool_result"', self.module_runtime)

    def test_all_backdoor_proof_events_match_the_shared_runtime_schema(self) -> None:
        expected_fields = [
            "actor_role",
            "asset_id",
            "event_kind",
            "object_id",
            "outcome_id",
            "record_count",
            "stage",
            "workflow_id",
            "range_instance",
            "participant",
            "timestamp",
            "status",
            "digest",
        ]
        behaviors = self.module["behavior_specifications"]
        for challenge_id in (
            "kep-m09-a",
            "kep-m09-b",
            "kep-m09-c",
            "kep-m09-d",
            "kep-m09-e",
            "kep-m09-f",
            "kep-m09-g",
        ):
            challenge = behaviors[challenge_id]["extensions"]["x-keplerops:challenge"]
            proof = challenge["proof"]
            with self.subTest(challenge_id=challenge_id):
                self.assertEqual(proof["proof_fields"], expected_fields)
                self.assertEqual(proof["event"]["fields"], expected_fields)
        self.assertIn('"record_count": 1', self.runtime)

    def test_candidate_registration_prerequisite_matches_the_rehearsed_training_path(self) -> None:
        challenge = self.module["behavior_specifications"]["kep-m09-a"]["extensions"][
            "x-keplerops:challenge"
        ]
        self.assertEqual(challenge["prerequisites"], ["kep-m07-f"])
        self.assertEqual(
            self.module["objectives"]["kep-m09-a"]["depends_on"],
            ["m07.kep-m07-f"],
        )
        candidate_phase = self.rehearsal[
            self.rehearsal.index("candidate = common") : self.rehearsal.index(
                "diagnostics = common"
            )
        ]
        self.assertIn('"challenge_id": "kep-m07-f"', candidate_phase)

    def test_portal_catalog_includes_every_gateway_backdoor_challenge(self) -> None:
        self.assertIn("for row in _participant_backdoor_challenges()", self.runtime)
        self.assertIn('"entrypoint": BACKDOOR_ATTEMPT_PATH', self.runtime)
        self.assertIn("*backdoor_rows", self.runtime)


if __name__ == "__main__":
    unittest.main()
