"""Focused source contracts for realized Module 02 supply-chain slices."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from .runtime_source import runtime_source


PACK = Path(__file__).resolve().parents[2]
RUNTIME = PACK / "assets/services/keplerops-runtime"
sys.path.insert(0, str(RUNTIME))

from agent_actions import web_delivery_id  # noqa: E402


APP = runtime_source(RUNTIME)
SCHEMA = (PACK / "assets/services/postgres-init.sh").read_text(encoding="utf-8")
WORKFLOW = (PACK / "assets/workflows/keplerops_distillation.py").read_text(encoding="utf-8")
WORKER = (RUNTIME / "agent_action_worker.py").read_text(encoding="utf-8")
DOCKERFILE = (PACK / "assets/services/Dockerfile.gateway").read_text(encoding="utf-8")
POLICY_DOCKERFILE = (PACK / "assets/services/Dockerfile.policy").read_text(encoding="utf-8")
PROOF_DOCKERFILE = (PACK / "assets/services/Dockerfile.proof").read_text(encoding="utf-8")
RUNTIME_DOCKERFILE = (
    PACK / "assets/services/keplerops-runtime/Dockerfile"
).read_text(encoding="utf-8")
WORKHUB_DOCKERFILE = (PACK / "assets/services/Dockerfile.workhub").read_text(encoding="utf-8")
WORKHUB_SEED = (PACK / "assets/services/seed_workhub.rb").read_text(encoding="utf-8")
GATEWAY_ENTRYPOINT = (PACK / "assets/services/gateway-entrypoint.sh").read_text(
    encoding="utf-8"
)
BOOTSTRAP = (PACK / "build/gcp/workload-bootstrap.sh").read_text(encoding="utf-8")
POLICY = (PACK / "assets/policies/guardrails.rego").read_text(encoding="utf-8")
ENVIRONMENT = (PACK / "sdl/modules/environment.sdl.yaml").read_text(encoding="utf-8")
ENVOY = (PACK / "assets/services/envoy.yaml").read_text(encoding="utf-8")


class ModelSupplyContractTests(unittest.TestCase):
    def test_exact_web_delivery_route_is_the_only_new_browser_target(self) -> None:
        canonical = (
            "https://inference-gateway.keplerops.lab/public/evasion/deliveries/"
            "wex-0123456789abcdef01234567"
        )
        self.assertEqual(web_delivery_id(canonical), "wex-0123456789abcdef01234567")
        for rejected in (
            canonical + "?next=https://example.invalid",
            canonical.replace("https://", "http://"),
            canonical.replace("inference-gateway", "attacker"),
            canonical.replace("wex-", "../wex-"),
        ):
            with self.subTest(rejected=rejected):
                self.assertIsNone(web_delivery_id(rejected))

    def test_gateway_exposes_closed_supply_requests_and_real_routes(self) -> None:
        for request_model in (
            "DataDependencyRequest",
            "DataDependencyJobRequest",
            "DataDependencyAttemptRequest",
            "ModelDependencyRequest",
            "ModelDependencyAttemptRequest",
            "WebDeliveryRequest",
            "WebDeliveryExploitRequest",
            "WebDeliveryAttemptRequest",
            "SpearphishCampaignRequest",
            "SpearphishAttemptRequest",
        ):
            self.assertIn(f"class {request_model}(BaseModel):", APP)
        for route in (
            '"/v1/evasion/data-dependencies"',
            '"/v1/evasion/data-dependency-jobs"',
            '"/v1/evasion/model-dependencies"',
            '"/v1/evasion/web-deliveries"',
            '"/public/evasion/previews/{delivery_id}"',
            '"/public/evasion/deliveries/{delivery_id}"',
            '"/v1/evasion/spearphish-campaigns"',
            '"/v1/evasion/supply-attempts"',
        ):
            self.assertIn(route, APP)
        self.assertIn("supply_challenge_satisfied", APP)
        self.assertIn("direct_write=False", APP)
        self.assertIn("alias_only=False", APP)
        self.assertIn("operator_uploaded=False", APP)

    def test_spearphish_campaign_route_allows_real_ai_generation_latency(self) -> None:
        campaign_route = '- match: {prefix: "/v1/evasion/spearphish-campaigns"}'
        long_route = 'route: {cluster: gateway, timeout: 900s, idle_timeout: 900s}'
        catch_all = '- match: {prefix: "/"}'
        self.assertIn(campaign_route, ENVOY)
        self.assertIn(long_route, ENVOY)
        self.assertLess(ENVOY.index(campaign_route), ENVOY.index(catch_all))

    def test_model_dependency_route_allows_real_registry_latency(self) -> None:
        dependency_route = '- match: {prefix: "/v1/evasion/model-dependencies"}'
        long_route = 'route: {cluster: gateway, timeout: 180s, idle_timeout: 180s}'
        catch_all = '- match: {prefix: "/"}'
        self.assertIn(dependency_route, ENVOY)
        self.assertIn(long_route, ENVOY)
        self.assertLess(ENVOY.index(dependency_route), ENVOY.index(catch_all))

    def test_model_dependency_fetch_uses_only_canonical_internal_urls(self) -> None:
        self.assertIn("def _model_dependency_source_index(source_url: str) -> int:", APP)
        self.assertIn("source_url = source_urls[source_index]", APP)
        self.assertIn("_fetch_model_dependency_artifact(selected_source_index)", APP)
        self.assertNotIn("_fetch_model_dependency_artifact(request.source_url)", APP)

    def test_web_delivery_uses_runtime_owned_storage_and_documents_errors(self) -> None:
        self.assertIn(
            'WEB_DELIVERY_STORAGE_ROOT = Path("/var/lib/keplerops/web-delivery-scratch")',
            APP,
        )
        self.assertIn('"exploit_path": f"../deliveries/{delivery_id}.html"', APP)
        self.assertNotIn("/tmp/keplerops", APP)
        public_delivery = APP[
            APP.index('@router.get(\n    "/public/evasion/deliveries/') :
        ]
        self.assertIn("responses=ERROR_RESPONSES", public_delivery.split("def ", 1)[0])

    def test_postgres_owns_reset_scoped_supply_lineage(self) -> None:
        for table in (
            "data_dependencies",
            "data_dependency_jobs",
            "model_dependencies",
            "web_deliveries",
            "supply_attempts",
            "spearphish_campaigns",
            "spearphish_attempts",
        ):
            self.assertIn(f"CREATE TABLE {table}", SCHEMA)
        self.assertGreaterEqual(SCHEMA.count("reset_generation integer NOT NULL"), 5)

        for marker in (
            "(SELECT count(*) FROM data_dependencies)",
            "(SELECT count(*) FROM data_dependency_jobs)",
            "(SELECT count(*) FROM model_dependencies)",
            "(SELECT count(*) FROM web_deliveries)",
            "(SELECT count(*) FROM supply_attempts)",
            "(SELECT count(*) FROM spearphish_campaigns)",
            "(SELECT count(*) FROM spearphish_attempts)",
            '"keplerops-model-dependencies"',
            '"keplerops-policy-model-%"',
            "-name policy-model.json",
            '"data_dependency_job_id"',
        ):
            self.assertIn(marker, BOOTSTRAP)

    def test_airflow_verifies_signed_manifest_before_consumption(self) -> None:
        self.assertIn("DATA_DEPENDENCY_JOB_ID", WORKFLOW)
        self.assertIn("data_dependency_job_id", WORKFLOW)
        self.assertIn("hmac.compare_digest", WORKFLOW)
        self.assertIn("/run/keplerops/service-token", WORKFLOW)
        self.assertIn("UPDATE data_dependency_jobs SET status='succeeded'", WORKFLOW)
        self.assertEqual(WORKFLOW.count('"data dependency manifest is invalid"'), 1)
        self.assertIn("def _validated_job_id(", WORKFLOW)
        self.assertIn("def _run_distillation_task(", WORKFLOW)

        runner_start = BOOTSTRAP.index(
            "  distillation-runner-01)\n    fetch_secret service-token"
        )
        runner = BOOTSTRAP[
            runner_start : BOOTSTRAP.index("  notebook-runner-01)", runner_start)
        ]
        self.assertIn("fetch_secret service-token", runner)
        self.assertIn("dst=/run/keplerops/service-token,readonly", runner)
        dependency_start = ENVIRONMENT.index(
            "  distillation-signed-manifest-access:"
        )
        dependency_end = ENVIRONMENT.index("agents:", dependency_start)
        dependency = ENVIRONMENT[dependency_start:dependency_end]
        self.assertIn("source: distillation-runner-01", dependency)
        self.assertIn("target: inference-gateway", dependency)
        self.assertIn("capability: signed-data-dependency-manifest", dependency)
        self.assertIn("credentials: service-token", dependency)

    def test_workhub_publishes_both_executable_model_dependencies(self) -> None:
        self.assertIn("COPY assets/content/model-dependencies/", WORKHUB_DOCKERFILE)
        self.assertIn("policy-model-clean.json", WORKHUB_SEED)
        self.assertIn("policy-model-poisoned.json", WORKHUB_SEED)
        self.assertIn("generic/keplerops-policy-model/#{version}/policy-model.json", WORKHUB_SEED)

    def test_gateway_binds_mlflow_artifacts_to_sdl_registry_url(self) -> None:
        self.assertIn('Path("/etc/keplerops/runtime.yaml")', GATEWAY_ENTRYPOINT)
        self.assertIn('config.get("registry_url")', GATEWAY_ENTRYPOINT)
        self.assertIn('parsed.hostname != "model-registry-01.keplerops.lab"', GATEWAY_ENTRYPOINT)
        self.assertIn("export MLFLOW_TRACKING_URI", GATEWAY_ENTRYPOINT)
        self.assertIn("MLFLOW_REGISTRY_URI=$MLFLOW_TRACKING_URI", GATEWAY_ENTRYPOINT)

    def test_real_browser_worker_supports_only_bound_delivery(self) -> None:
        self.assertIn("web_delivery_id", WORKER)
        self.assertIn("/public/evasion/deliveries/{delivery_id}", WORKER)
        self.assertIn("chromium-headless-shell", WORKER)

    def test_container_and_policy_include_only_realized_supply_paths(self) -> None:
        for dockerfile in (
            DOCKERFILE,
            POLICY_DOCKERFILE,
            PROOF_DOCKERFILE,
            RUNTIME_DOCKERFILE,
        ):
            self.assertIn("keplerops-runtime/model_supply.py", dockerfile)
        policy_slice = POLICY[POLICY.index("input.action == \"evasion_probe\"") :]
        for challenge_id in (
            "kep-m02-h",
            "kep-m02-i",
            "kep-m02-j",
            "kep-m02-k",
            "kep-m02-l",
            "kep-m02-m",
        ):
            self.assertIn(f'"{challenge_id}"', policy_slice)
        for challenge_id in ("kep-m02-g",):
            self.assertNotIn(f'"{challenge_id}"', policy_slice)

    def test_spearphish_uses_real_generated_mail_and_identity_boundaries(self) -> None:
        for marker in (
            'f"{model_url.rstrip(\'/\')}/v1/chat/completions"',
            'f"{image_url.rstrip(\'/\')}/v1/images/generations"',
            "smtplib.SMTP(mail_host, 587",
            "imaplib.IMAP4_SSL(mail_host, 993",
            'inbox.search(None, "HEADER", "Message-ID", message_id)',
            "identifiers[0].split()[-50:]",
            'delivered["Message-ID"] == message_id',
            "Disclosure rule: internal sender",
            'f"{issuer.rstrip(\'/\')}/protocol/openid-connect/token"',
            '"ai_service_recipient" not in roles',
            "attachment_digest",
            "token_digest",
        ):
            self.assertIn(marker, APP)
        self.assertIn("inference-spearphish-text-generation:", ENVIRONMENT)
        self.assertIn("inference-spearphish-image-generation:", ENVIRONMENT)
        self.assertIn("inference-spearphish-mail:", ENVIRONMENT)
        self.assertIn("inference-spearphish-identity:", ENVIRONMENT)
        self.assertNotIn("disclosed_token text", SCHEMA)

    def test_spearphish_normalizes_mail_transport_text_for_verification(self) -> None:
        self.assertIn("def _canonical_mail_text(value: str) -> str:", APP)
        self.assertIn(
            "_canonical_mail_text(delivered_text) != _canonical_mail_text(generated_text)",
            APP,
        )
        self.assertNotIn("delivered_text != generated_text.strip()", APP)

    def test_spearphish_attempt_negative_path_initializes_schema(self) -> None:
        proof_slice = APP[
            APP.index("def _spearphish_proof(") : APP.index(
                "return SpearphishProof(*row", APP.index("def _spearphish_proof(")
            )
        ]
        self.assertIn("_ensure_model_supply_schema()", proof_slice)
        self.assertIn("raise HTTPException(status_code=404", proof_slice)


if __name__ == "__main__":
    unittest.main()
