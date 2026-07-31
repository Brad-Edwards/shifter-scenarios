from __future__ import annotations

import unittest
from pathlib import Path
import sys

from .runtime_source import module_source, proof_source, runtime_source


PACK = Path(__file__).resolve().parents[2]
RUNTIME = PACK / "assets/services/keplerops-runtime"
sys.path.insert(0, str(PACK))

from aces_contract import challenge_content_rows, challenge_contracts  # noqa: E402


APP = runtime_source(RUNTIME)
CAPSTONE = module_source(RUNTIME, "m10")
PROOF = proof_source(RUNTIME)
HEALTH = (
    RUNTIME / "keplerops_runtime/foundation/health.py"
).read_text(encoding="utf-8")
SCHEMA = (PACK / "assets/services/postgres-init.sh").read_text(encoding="utf-8")
BOOTSTRAP = (PACK / "build/gcp/workload-bootstrap.sh").read_text(encoding="utf-8")
DOCKERFILE = (PACK / "assets/services/Dockerfile.gateway").read_text(encoding="utf-8")
POLICY = (PACK / "assets/policies/guardrails.rego").read_text(encoding="utf-8")
ENVOY = (PACK / "assets/services/envoy.yaml").read_text(encoding="utf-8")


class AiCapstoneApiContractTests(unittest.TestCase):
    def test_every_realized_challenge_has_three_complete_hint_tiers(self) -> None:
        designs = challenge_contracts(PACK)
        content = {
            row["flag_id"]: row for row in challenge_content_rows(PACK)
        }
        self.assertEqual(len(designs), 134)
        self.assertEqual(len(content), 134)
        for challenge_id, design in designs.items():
            with self.subTest(challenge_id=challenge_id):
                hints = content[design["flag_id"]]["hints"]
                costs = design["hint_costs"]
                self.assertEqual(len(hints), 3)
                self.assertTrue(all(isinstance(hint, str) and hint for hint in hints))
                self.assertEqual(len(costs), 3)
                self.assertTrue(
                    all(isinstance(cost, int) and cost >= 0 for cost in costs)
                )

    def test_proof_health_constructs_the_complete_realized_contract(self) -> None:
        self.assertIn('@router.get("/healthz"', HEALTH)
        self.assertIn("_realized_challenge_contracts()", HEALTH)

    def test_participant_supplies_coordinates_not_verdicts(self) -> None:
        for request in (
            "CapstoneInferenceRequest",
            "CapstoneEffectRequest",
            "CapstoneArtifactAccessRequest",
            "CapstoneAttemptRequest",
        ):
            self.assertIn(f"class {request}(BaseModel):", CAPSTONE)
        for forbidden in (
            "artifact_digest: str",
            "byte_count: int",
            "triggered: bool",
            "contained_effect: bool",
            "objective_status: str",
        ):
            self.assertNotIn(forbidden, CAPSTONE)

    def test_real_promoted_model_and_policy_broker_drive_impact(self) -> None:
        for marker in (
            "_capstone_deployment",
            "_candidate_model(candidate)",
            "model.classifier.predict_proba",
            'ToolCall("publish_notice"',
            "await _execute_broker_tool",
            "adversarial_attempts",
            "challenge_id='kep-m06-e'",
            "challenge_id='kep-m05-e'",
        ):
            self.assertIn(marker, APP)
        self.assertIn('input.action == "ai_capstone"', POLICY)

    def test_nullable_candidate_activation_filter_is_explicitly_typed(self) -> None:
        self.assertIn(
            '"AND (%s::text IS NULL OR a.candidate_id=%s)"',
            APP,
        )
        self.assertNotIn(
            '"AND (%s IS NULL OR a.candidate_id=%s)"',
            APP,
        )

    def test_long_proxy_timeouts_are_route_specific(self) -> None:
        verification = '- match: {prefix: "/v1/capstone/artifact-access/"}'
        spearphish = '- match: {prefix: "/v1/evasion/spearphish-campaigns"}'
        capstone_route = 'route: {cluster: gateway, timeout: 900s}'
        spearphish_route = (
            'route: {cluster: gateway, timeout: 900s, idle_timeout: 900s}'
        )
        catch_all = '- match: {prefix: "/"}'
        self.assertIn(verification, ENVOY)
        self.assertIn(spearphish, ENVOY)
        self.assertIn(capstone_route, ENVOY)
        self.assertIn(spearphish_route, ENVOY)
        self.assertLess(ENVOY.index(verification), ENVOY.index(catch_all))
        self.assertLess(ENVOY.index(spearphish), ENVOY.index(catch_all))
        self.assertEqual(ENVOY.count(capstone_route), 1)
        self.assertEqual(ENVOY.count(spearphish_route), 1)
        self.assertIn('route: {cluster: gateway, timeout: 35s}', ENVOY)

    def test_final_capstone_receipt_is_proof_derived(self) -> None:
        evidence = (
            RUNTIME / "keplerops_runtime/modules/m10/constants.py"
        ).read_text(encoding="utf-8")
        for suffix in "abcdef":
            self.assertIn(f'"kep-m10-{suffix}"', evidence)
        self.assertNotIn('"kep-m10-g"', evidence)
        for marker in (
            'contract.get("evidence") == "ev-capstone-receipt"',
            'prerequisite = set(oracle.required_evidence("ai-capstone")) - {"ev-capstone-receipt"}',
            '"asset_id": "telemetry-proof-01"',
            'producer_asset="telemetry-proof-01"',
        ):
            self.assertIn(marker, PROOF)

    def test_capstone_requires_the_realized_module_09_verdict(self) -> None:
        capstone = (
            PACK / "sdl/modules/module-10-ai-capstone.sdl.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("- ev-backdoor-verification", capstone)
        self.assertNotIn("ev-model-backdoor", capstone)
        environment = (
            PACK / "sdl/modules/environment.sdl.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "ev-model-backdoor",
            environment,
        )

    def test_original_model_transfer_is_real_contained_and_byte_verified(self) -> None:
        for marker in (
            '"models/teacher/model.safetensors"',
            'Bucket="keplerops-artifacts"',
            'Bucket="keplerops-exfil"',
            '"get_object"',
            '"put_object"',
            "hashlib.sha256()",
            "hmac.compare_digest",
            'destination": "contained-exfil"',
        ):
            self.assertIn(marker, APP)
        self.assertIn("boto3==1.40.20", (PACK / "assets/services/keplerops-runtime/ai-capstone-requirements.txt").read_text(encoding="utf-8"))
        self.assertIn("ai-capstone-requirements.txt", DOCKERFILE)
        self.assertNotIn("http://artifact-store", APP)
        self.assertNotIn("http://exfil", APP)
        model_contract = CAPSTONE[
            CAPSTONE.index("def _teacher_model_artifact"):
            CAPSTONE.index("def _minio_client")
        ]
        self.assertIn('row.get("path") == "model.safetensors"', model_contract)
        self.assertIn("len(matches) != 1", model_contract)
        self.assertNotIn("len(rows) != 1", model_contract)

    def test_state_and_reset_are_generation_scoped(self) -> None:
        for table in (
            "capstone_activations",
            "capstone_effects",
            "capstone_artifact_access",
            "capstone_attempts",
        ):
            self.assertIn(f"CREATE TABLE {table}", SCHEMA)
            self.assertIn(f"SELECT count(*) FROM {table}", BOOTSTRAP)
        self.assertIn("reset_generation integer NOT NULL", SCHEMA)
        self.assertIn("rm -rf /var/lib/keplerops/data", BOOTSTRAP)

    def test_full_atlas_expansion_routes_are_participant_facing(self) -> None:
        for route in (
            "/v1/extraction/platform/inversions",
            "/v1/extraction/platform/physical-sensor-attempts",
            "/v1/extraction/platform/model-accesses",
            "/v1/extraction/platform/document-side-channels",
            "/v1/backdoor/platform/reputation-resolutions",
            "/v1/backdoor/platform/rug-pulls",
            "/v1/backdoor/platform/tool-publications",
            "/v1/backdoor/platform/model-corruptions",
            "/v1/capstone/impact/service-denial",
            "/v1/capstone/impact/cost-amplifications",
            "/v1/capstone/impact/agentic-budget-loops",
            "/v1/capstone/impact/chaff-floods",
            "/v1/capstone/impact/tool-data-destructions",
        ):
            with self.subTest(route=route):
                self.assertIn(route, APP)
        self.assertIn("CREATE TABLE platform_challenge_events", SCHEMA)

    def test_only_digest_safe_telemetry_is_observed(self) -> None:
        self.assertNotIn("source_url=", CAPSTONE)
        self.assertNotIn("destination_url=", CAPSTONE)
        self.assertNotIn("prompt=request.prompt", CAPSTONE)
        self.assertIn('state_digest=prompt_digest', CAPSTONE)
        self.assertIn('artifact_digest=destination_digest', CAPSTONE)
        self.assertGreaterEqual(CAPSTONE.count("_capture_http_body(session, request)"), 14)
        self.assertIn('_capture(session, signal="prompt", content=request.prompt)', CAPSTONE)
        self.assertIn('signal="completion"', CAPSTONE)
        self.assertIn('signal="tool_call"', CAPSTONE)
        self.assertIn('signal="tool_result"', CAPSTONE)


if __name__ == "__main__":
    unittest.main()
