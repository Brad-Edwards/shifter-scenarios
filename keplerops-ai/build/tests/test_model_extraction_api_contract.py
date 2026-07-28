from __future__ import annotations

import unittest
from pathlib import Path

from .runtime_source import module_source, runtime_source


PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"


class ModelExtractionApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = runtime_source(RUNTIME_ROOT)
        cls.module_runtime = module_source(RUNTIME_ROOT, "m08")
        cls.jobs = (
            RUNTIME_ROOT
            / "keplerops_runtime/modules/m08/jobs.py"
        ).read_text(encoding="utf-8")
        cls.platform = (
            RUNTIME_ROOT
            / "keplerops_runtime/modules/m08/platform.py"
        ).read_text(encoding="utf-8")
        cls.schema = (PACK_ROOT / "assets/services/postgres-init.sh").read_text(encoding="utf-8")
        cls.workflow = (PACK_ROOT / "assets/workflows/keplerops_distillation.py").read_text(encoding="utf-8")
        cls.bootstrap = (PACK_ROOT / "build/gcp/workload-bootstrap.sh").read_text(encoding="utf-8")
        cls.policy = (PACK_ROOT / "assets/policies/guardrails.rego").read_text(encoding="utf-8")

    def test_gateway_exposes_bounded_corpus_job_attempt_and_receipt_routes(self) -> None:
        for route in (
            '@router.get("/v1/extraction/challenges"',
            '@router.get("/v1/extraction/probes/diagnostic"',
            '@router.post("/v1/extraction/queries"',
            '@router.get("/v1/extraction/corpora/{corpus_id}"',
            '@router.post("/v1/extraction/jobs"',
            '@router.get("/v1/extraction/jobs/{job_id}"',
            '@router.post(EXTRACTION_ATTEMPT_PATH',
            '@router.post("/v1/extraction/receipts/{flag_id}"',
        ):
            self.assertIn(route, self.runtime)
        self.assertNotIn('/v1/extraction/probes/private', self.runtime)
        self.assertIn('ConfigDict(extra="forbid"', self.runtime)

    def test_postgres_owns_participant_lineage_budgets_jobs_and_attempts(self) -> None:
        for table in (
            "extraction_corpora",
            "extraction_queries",
            "extraction_jobs",
            "extraction_attempts",
        ):
            self.assertIn(f"CREATE TABLE {table}", self.schema)
        for field in (
            "query_budget",
            "query_count",
            "corpus_digest",
            "behavior_slice",
            "prompt_digest",
            "registry_run_id",
            "artifact_uri",
        ):
            self.assertIn(field, self.schema)

    def test_airflow_trains_registers_and_evaluates_a_real_proxy(self) -> None:
        for value in (
            "TfidfVectorizer",
            "LogisticRegression",
            "model.predict",
            "MlflowClient",
            "client.log_artifact",
            "keplerops-model-extraction",
            'os.environ.get("KEPLEROPS_MODEL_URL", LOCAL_MODEL_API)',
            "MODEL_IDENTITY_ENDPOINT",
            '"Authorization": f"Bearer {token}"',
            "_record_extraction_evidence",
            "minimum_slice_fidelity",
        ):
            self.assertIn(value, self.workflow)
        self.assertIn(
            '-e KEPLEROPS_MODEL_URL="$SHARED_MODEL_URL"',
            self.bootstrap,
        )
        self.assertNotIn("urlsafe_b64decode", self.workflow)
        for forbidden in ("caller_metrics", "submitted_weights", "preseeded_proxy"):
            self.assertNotIn(forbidden, self.workflow)

    def test_every_application_and_workflow_image_carries_the_domain(self) -> None:
        dockerfiles = (
            "assets/services/keplerops-runtime/Dockerfile",
            "assets/services/Dockerfile.gateway",
            "assets/services/Dockerfile.policy",
            "assets/services/Dockerfile.proof",
            "assets/workflows/Dockerfile",
        )
        for relative in dockerfiles:
            source = (PACK_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(dockerfile=relative):
                self.assertIn(
                    "COPY assets/services/keplerops-runtime/model_extraction.py",
                    source,
                )

    def test_policy_and_reset_cover_every_extraction_state_owner(self) -> None:
        self.assertIn('input.action == "model_extract"', self.policy)
        for value in (
            "(SELECT count(*) FROM extraction_corpora)",
            "(SELECT count(*) FROM extraction_queries)",
            "(SELECT count(*) FROM extraction_jobs)",
            "(SELECT count(*) FROM extraction_attempts)",
            '"keplerops-model-extraction"',
            '"m08-%"',
            "-name proxy.json",
        ):
            self.assertIn(value, self.bootstrap)

    def test_capture_records_raw_extraction_content_without_observing_it(self) -> None:
        endpoint = self.module_runtime[
            self.module_runtime.index("async def query_extraction_teacher") :
            self.module_runtime.index('@router.get("/v1/extraction/corpora/{corpus_id}"')
        ]
        self.assertIn("_capture_http_body(session, request)", endpoint)
        self.assertIn(
            '_capture(session, signal="prompt", content=request.prompt)', endpoint
        )
        self.assertIn(
            '_capture(session, signal="completion", content=completion.content)',
            endpoint,
        )
        observation = endpoint[endpoint.index("    _observe("): endpoint.index("    return {")]
        self.assertNotIn("request.prompt", observation)
        self.assertNotIn("completion.content", observation)
        for field in (
            "query_budget",
            "coverage_count",
            "diagnostic_fidelity",
            "private_fidelity",
            "minimum_slice_fidelity",
        ):
            self.assertIn(field, self.runtime)

    def test_job_evidence_ownership_matches_oracle_source_assets(self) -> None:
        self.assertIn(
            'if not passed or request.challenge_id != "kep-m08-g":',
            self.jobs,
        )
        self.assertNotIn('"kep-m08-g": "gathered_artifact_proxy"', self.workflow)
        self.assertIn(
            "and challenge_id in EXTRACTION_EVIDENCE",
            self.workflow,
        )

    def test_platform_proof_call_matches_shared_helper_contract(self) -> None:
        call_block = self.platform[
            self.platform.index("await record_platform_proof(") :
            self.platform.index("    return {", self.platform.index("await record_platform_proof("))
        ]
        self.assertNotIn("challenge_id=challenge_id", call_block)
        self.assertIn("event_kind=event_kind", call_block)

    def test_camera_session_gateway_preserves_creation_status(self) -> None:
        route_start = self.platform.index(
            '@router.post(\n    "/v1/extraction/platform/camera-sessions"'
        )
        route = self.platform[route_start : self.platform.index(")", route_start) + 1]
        self.assertIn("status_code=201", route)


if __name__ == "__main__":
    unittest.main()
