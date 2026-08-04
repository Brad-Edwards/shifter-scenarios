from __future__ import annotations

import unittest
from pathlib import Path

from .runtime_source import module_source, runtime_source


PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"


class TrainingPoisoningApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = runtime_source(RUNTIME_ROOT)
        cls.module_runtime = module_source(RUNTIME_ROOT, "m07")
        cls.schema = (PACK_ROOT / "assets/services/postgres-init.sh").read_text(
            encoding="utf-8"
        )
        cls.workflow = (
            PACK_ROOT / "assets/workflows/keplerops_distillation.py"
        ).read_text(encoding="utf-8")
        cls.model = (PACK_ROOT / "assets/workflows/training_model.py").read_text(
            encoding="utf-8"
        )
        cls.bootstrap = (PACK_ROOT / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        cls.policy = (PACK_ROOT / "assets/policies/guardrails.rego").read_text(
            encoding="utf-8"
        )

    def test_gateway_exposes_bounded_dataset_job_attempt_and_receipt_routes(
        self,
    ) -> None:
        for route in (
            '@router.get("/v1/training/challenges"',
            '@router.post("/v1/training/datasets"',
            '@router.post("/v1/training/jobs"',
            '@router.get("/v1/training/jobs/{job_id}"',
            "@router.post(TRAINING_ATTEMPT_PATH",
            '@router.get("/v1/training/expansion/challenges"',
            '@router.post("/v1/training/expansion/proofs"',
            '@router.post("/v1/training/receipts/{flag_id}"',
        ):
            self.assertIn(route, self.runtime)
        self.assertIn('ConfigDict(extra="forbid"', self.runtime)
        self.assertIn("training_dataset_failure_class", self.runtime)
        self.assertIn("training_failure_class", self.runtime)
        self.assertIn("TRAINING_EXPANSION_REQUIREMENTS", self.runtime)
        self.assertIn("training_expansion_failure_class", self.runtime)
        for suffix in "abcdefghi":
            self.assertIn(f'"kep-m07-{suffix}"', self.policy)

    def test_postgres_owns_version_lineage_jobs_metrics_and_attempts(self) -> None:
        for table in (
            "training_datasets",
            "training_rows",
            "training_jobs",
            "training_attempts",
            "platform_challenge_events",
        ):
            self.assertIn(f"CREATE TABLE {table}", self.schema)
        for field in (
            "parent_revision",
            "base_digest",
            "dataset_digest",
            "poison_ratio",
            "registry_run_id",
            "artifact_uri",
            "platform-training",
        ):
            self.assertIn(field, self.schema)

    def test_dataset_creation_recovers_an_identical_committed_retry(self) -> None:
        self.assertIn(
            '"SELECT dataset_id, revision FROM training_datasets "',
            self.runtime,
        )
        self.assertIn(
            '"AND challenge_id=%s AND dataset_digest=%s"',
            self.runtime,
        )
        self.assertIn("if existing_dataset is None:", self.runtime)
        self.assertIn("if dataset_inserted:", self.runtime)
        self.assertGreaterEqual(
            self.module_runtime.count("_capture_http_body(session, request)"), 3
        )

    def test_job_creation_recovers_the_bound_job_after_a_retry(self) -> None:
        self.assertIn(
            '"SELECT job_id, status FROM training_jobs "',
            self.runtime,
        )
        self.assertIn(
            '"AND challenge_id=%s AND dataset_id=%s"',
            self.runtime,
        )
        self.assertIn("if existing_job is None:", self.runtime)
        self.assertIn("if job_inserted:", self.runtime)
        self.assertIn('"status": job_status', self.runtime)

    def test_airflow_trains_and_persists_a_real_model_artifact(self) -> None:
        self.assertIn("TfidfVectorizer", self.model)
        self.assertIn("LogisticRegression", self.model)
        self.assertIn("candidate[1].coef_", self.model)
        self.assertIn("MlflowClient", self.workflow)
        self.assertIn("client.log_artifact", self.workflow)
        self.assertIn("training_poisoning", self.workflow)
        self.assertIn("training_jobs", self.workflow)
        self.assertIn("_record_training_evidence", self.workflow)
        self.assertIn("model-registry-01.keplerops.lab:9000", self.workflow)
        self.assertIn("mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)", self.workflow)
        self.assertIn('range_instance != os.environ["KEPLEROPS_RANGE_INSTANCE"]', self.workflow)
        self.assertNotIn('participant != os.environ["KEPLEROPS_PARTICIPANT"]', self.workflow)

    def test_every_application_image_carries_the_imported_domain_and_base(self) -> None:
        dockerfiles = (
            "assets/services/keplerops-runtime/Dockerfile",
            "assets/services/Dockerfile.gateway",
            "assets/services/Dockerfile.policy",
            "assets/services/Dockerfile.proof",
        )
        for relative in dockerfiles:
            source = (PACK_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(dockerfile=relative):
                self.assertIn(
                    "COPY assets/services/keplerops-runtime/training_poisoning.py",
                    source,
                )
                self.assertIn(
                    "COPY assets/content/datasets/distillation.jsonl ", source
                )

    def test_airflow_image_pins_training_and_registry_dependencies(self) -> None:
        dockerfile = (PACK_ROOT / "assets/workflows/Dockerfile").read_text(
            encoding="utf-8"
        )
        for value in (
            "mlflow-skinny==3.3.2",
            "psycopg[binary]==3.2.10",
            "scikit-learn==1.7.1",
            "training_model.py",
            "training_poisoning.py",
        ):
            self.assertIn(value, dockerfile)

    def test_reset_verifies_every_module_training_state_owner(self) -> None:
        for value in (
            "(SELECT count(*) FROM training_datasets)",
            "(SELECT count(*) FROM training_rows)",
            "(SELECT count(*) FROM training_jobs)",
            "(SELECT count(*) FROM training_attempts)",
            "name IN (?, ?, ?)",
            (
                '("keplerops-training-poisoning", "keplerops-model-extraction", '
                '"keplerops-model-dependencies")'
            ),
            "(run_id LIKE ? OR run_id LIKE ? OR instr(CAST(conf AS TEXT), ?) > 0)",
            ('("keplerops_distillation", "m07-%", "m08-%", "data_dependency_job_id")'),
            "-name adapter.json",
            'read -r -a RUNTIME_TCP_PORTS <<<"$RUNTIME_TCP_PORTS_TEXT"',
            "-p 5000:5000 -p 9000:5000",
        ):
            self.assertIn(value, self.bootstrap)


if __name__ == "__main__":
    unittest.main()
