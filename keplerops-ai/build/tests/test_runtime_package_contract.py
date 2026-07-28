"""Focused contracts for Module 02 runtime masquerading and sandbox evasion."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from .runtime_source import runtime_source


PACK = Path(__file__).resolve().parents[2]
RUNTIME = PACK / "assets/services/keplerops-runtime"
sys.path.insert(0, str(RUNTIME))

from model_supply import (  # noqa: E402
    RuntimeDependencyProof,
    SandboxEvaluationProof,
    challenge_satisfied,
)


DIGEST = "sha256:" + "a" * 64
EFFECT_DIGEST = "sha256:" + "b" * 64
GENUINE_DIGEST = "sha256:" + "c" * 64
WORKER = (RUNTIME / "python_package_worker.py").read_text(encoding="utf-8")
CLEAN = (
    PACK
    / "assets/content/python-packages/clean-runtime/keplerops_eval_runtime/__init__.py"
).read_text(encoding="utf-8")
MASQUERADE = (
    PACK
    / "assets/content/python-packages/masquerading-runtime/keplerops_eval_runtime/__init__.py"
).read_text(encoding="utf-8")
PUBLISHER = (PACK / "assets/content/python-packages/publish_runtime.py").read_text(
    encoding="utf-8"
)
APP = runtime_source(RUNTIME)
SCHEMA = (PACK / "assets/services/postgres-init.sh").read_text(encoding="utf-8")
BOOTSTRAP = (PACK / "build/gcp/workload-bootstrap.sh").read_text(encoding="utf-8")
GATEWAY_DOCKERFILE = (PACK / "assets/services/Dockerfile.gateway").read_text(
    encoding="utf-8"
)
KALI_DOCKERFILE = (PACK / "assets/services/Dockerfile.kali").read_text(encoding="utf-8")
WORKHUB_DOCKERFILE = (PACK / "assets/services/Dockerfile.workhub").read_text(
    encoding="utf-8"
)
WORKHUB_SEED = (PACK / "assets/services/seed_workhub.rb").read_text(encoding="utf-8")
UI = (PACK / "assets/services/model-evasion.html").read_text(encoding="utf-8")


class RuntimePackageDomainTests(unittest.TestCase):
    def test_runtime_dependency_requires_real_resolver_and_behavior_delta(self) -> None:
        proof = RuntimeDependencyProof(
            dependency_id="rtp-" + "1" * 24,
            genuine_name="keplerops-eval-runtime",
            published_name="keplerops-eval-runtlme",
            package_version="1.0.0",
            resolver="pip-gitea-pypi",
            genuine_digest=GENUINE_DIGEST,
            resolved_digest=DIGEST,
            installed_digest=DIGEST,
            genuine_decision="deny",
            selected_decision="allow",
            deceptive_identity=True,
            resolver_process_id=99,
            genuine_process_id=100,
            worker_process_id=101,
            worker_effect_digest=EFFECT_DIGEST,
            worker_edited=False,
        )
        self.assertTrue(challenge_satisfied("kep-m02-h", proof))
        self.assertFalse(
            challenge_satisfied("kep-m02-h", proof._replace(worker_edited=True))
        )
        self.assertFalse(
            challenge_satisfied("kep-m02-h", proof._replace(resolver="direct-file"))
        )
        self.assertFalse(
            challenge_satisfied("kep-m02-h", proof._replace(genuine_digest=DIGEST))
        )
        self.assertFalse(
            challenge_satisfied("kep-m02-h", proof._replace(resolver_process_id=0))
        )
        self.assertFalse(
            challenge_satisfied(
                "kep-m02-h", proof._replace(worker_effect_digest="missing")
            )
        )
        self.assertFalse(
            challenge_satisfied(
                "kep-m02-h", proof._replace(installed_digest="sha256:" + "c" * 64)
            )
        )

    def test_sandbox_evasion_requires_one_digest_and_real_profile_delta(self) -> None:
        proof = SandboxEvaluationProof(
            evaluation_id="sbe-" + "2" * 24,
            artifact_digest=DIGEST,
            sandbox_digest=DIGEST,
            worker_digest=DIGEST,
            sandbox_profile="analysis",
            worker_profile="worker",
            sandbox_decision="deny",
            worker_decision="allow",
            sandbox_effect=False,
            worker_effect=True,
            environment_sensitive=True,
            separate_artifacts=False,
            worker_effect_digest=EFFECT_DIGEST,
            resolver_process_id=200,
            sandbox_process_id=201,
            worker_process_id=202,
        )
        self.assertTrue(challenge_satisfied("kep-m02-m", proof))
        self.assertFalse(
            challenge_satisfied(
                "kep-m02-m", proof._replace(worker_digest="sha256:" + "c" * 64)
            )
        )
        self.assertFalse(
            challenge_satisfied("kep-m02-m", proof._replace(sandbox_effect=True))
        )
        self.assertFalse(
            challenge_satisfied("kep-m02-m", proof._replace(separate_artifacts=True))
        )
        self.assertFalse(
            challenge_satisfied("kep-m02-m", proof._replace(resolver_process_id=0))
        )

    def test_worker_uses_real_pip_resolution_and_profile_fixed_services(self) -> None:
        for marker in (
            '"pip",\n                "download"',
            '"pip",\n            "install"',
            '"--index-url",\n                INDEX_URL',
            'MODE not in {"analysis", "worker"}',
            "digest != request.expected_digest",
            "package_name.replace('-', '_')",
            "effect_path.read_bytes()",
            "_write_netrc(home)",
            "workhub_credentials()",
        ):
            self.assertIn(marker, WORKER)
        self.assertNotIn("shell=True", WORKER)
        self.assertNotIn("https://ml.engineer:", WORKER)

    def test_same_module_is_benign_in_analysis_and_effectful_in_worker(self) -> None:
        self.assertIn('"decision": "deny"', CLEAN)
        self.assertNotIn("write_text", CLEAN)
        self.assertIn('profile == "analysis"', MASQUERADE)
        self.assertIn('profile != "worker"', MASQUERADE)
        self.assertIn("effect_path.write_text", MASQUERADE)

    def test_participant_publisher_uses_real_pypi_upload_protocol(self) -> None:
        for marker in (
            '(":action", "file_upload")',
            '("protocol_version", "1")',
            '("filetype", "bdist_wheel")',
            'name="content"',
            "http.client.HTTPSConnection",
        ):
            self.assertIn(marker, PUBLISHER)
        self.assertIn("CREDENTIAL_PATH", PUBLISHER)
        self.assertIn("WHEEL_PATH", PUBLISHER)
        self.assertIn("ssl.TLSVersion.TLSv1_2", PUBLISHER)
        self.assertNotIn('add_argument("wheel"', PUBLISHER)
        self.assertNotIn('add_argument("--password"', PUBLISHER)
        self.assertNotIn('add_argument("--repository"', PUBLISHER)

    def test_gateway_owns_closed_requests_and_receipt_proof_routes(self) -> None:
        for request_model in (
            "RuntimeDependencyRequest",
            "RuntimeDependencyAttemptRequest",
            "SandboxEvaluationRequest",
            "SandboxEvaluationAttemptRequest",
        ):
            self.assertIn(f"class {request_model}(BaseModel):", APP)
        for marker in (
            '"/v1/evasion/runtime-dependencies"',
            '"/v1/evasion/sandbox-evaluations"',
            '"kep-m02-h": "gitea-pypi-masquerade"',
            '"kep-m02-m": "same-digest-sandbox-worker-delta"',
            "_fetch_model_dependency_artifact(0)",
            "responses=ERROR_RESPONSES",
            "worker_edited=False",
            "values = (*row[:11], False, *row[11:])",
            "genuine_digest, resolved_digest, installed_digest",
            "resolver_process_id, genuine_process_id",
        ):
            self.assertIn(marker, APP)

    def test_postgres_and_reset_own_runtime_package_lineage(self) -> None:
        for table in (
            "runtime_dependencies",
            "sandbox_evaluations",
            "runtime_supply_attempts",
        ):
            self.assertIn(f"CREATE TABLE {table}", SCHEMA)
            self.assertIn(f"(SELECT count(*) FROM {table})", BOOTSTRAP)
        self.assertIn(
            "REFERENCES runtime_dependencies(dependency_id) ON DELETE CASCADE", SCHEMA
        )
        self.assertGreaterEqual(SCHEMA.count("reset_generation integer NOT NULL"), 3)
        for column in (
            "genuine_digest text NOT NULL",
            "resolver_process_id integer NOT NULL",
            "genuine_process_id integer NOT NULL",
            "worker_effect_digest text NOT NULL",
        ):
            self.assertIn(column, SCHEMA)

    def test_real_wheels_are_built_seeded_and_delivered_to_participant(self) -> None:
        for marker in (
            "python -m build --no-isolation --wheel",
            "assets/content/python-packages/clean-runtime/",
            "/opt/keplerops/seed/python-packages/",
        ):
            self.assertIn(marker, WORKHUB_DOCKERFILE)
        for marker in (
            'pypi_request("/api/packages/#{USER}/pypi", package_path)',
            '[":action", "file_upload"]',
            '["filetype", "bdist_wheel"]',
        ):
            self.assertIn(marker, WORKHUB_SEED)
        self.assertIn(
            "assets/content/python-packages/masquerading-runtime/", KALI_DOCKERFILE
        )
        self.assertIn("/home/kasm-user/Desktop/", KALI_DOCKERFILE)
        self.assertIn("publish-keplerops-runtime", KALI_DOCKERFILE)
        self.assertIn("python_package_worker.py", GATEWAY_DOCKERFILE)
        self.assertIn("workhub_credentials.py", GATEWAY_DOCKERFILE)
        self.assertIn("workhub-credentials.yaml", GATEWAY_DOCKERFILE)
        for dockerfile_name in ("Dockerfile.policy", "Dockerfile.proof"):
            dockerfile = (PACK / "assets/services" / dockerfile_name).read_text(
                encoding="utf-8"
            )
            self.assertIn("workhub_credentials.py", dockerfile)
            self.assertNotIn("workhub-credentials.yaml", dockerfile)

    def test_analysis_and_worker_are_separate_internal_services(self) -> None:
        for marker in (
            "docker network create --internal keplerops-package-control",
            "--name keplerops-package-resolver",
            "--name keplerops-package-analysis",
            "--name keplerops-package-worker",
            "KEPLEROPS_PACKAGE_WORKER_MODE=resolver",
            "KEPLEROPS_PACKAGE_WORKER_MODE=analysis",
            "KEPLEROPS_PACKAGE_WORKER_MODE=worker",
            "package_resolver_url: http://package-resolver:8452",
            "package_analysis_worker_url: http://package-analysis:8453",
            "package_evaluation_worker_url: http://package-worker:8454",
        ):
            self.assertIn(marker, BOOTSTRAP)
        analysis = BOOTSTRAP[
            BOOTSTRAP.index("--name keplerops-package-analysis") : BOOTSTRAP.index(
                "--name keplerops-package-worker"
            )
        ]
        worker = BOOTSTRAP[
            BOOTSTRAP.index("--name keplerops-package-worker") : BOOTSTRAP.index(
                "    ;;\n  guardrail-policy)"
            )
        ]
        for service in (analysis, worker):
            self.assertIn("--network keplerops-package-control", service)
            self.assertIn("--security-opt no-new-privileges", service)
            self.assertIn("--cap-drop ALL", service)
            self.assertNotIn("--network keplerops-gateway", service)
        self.assertIn("--network-alias package-analysis", analysis)
        self.assertIn("--network-alias package-worker", worker)

    def test_sandbox_evaluation_insert_binds_every_dynamic_column(self) -> None:
        statement = re.search(
            r"INSERT INTO sandbox_evaluations .*?VALUES \((.*?)\)",
            APP,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(statement)
        assert statement is not None
        self.assertEqual(statement.group(1).count("%s"), 17)

    def test_participant_browser_surface_uses_the_same_package_apis(self) -> None:
        for marker in (
            'request("/v1/evasion/runtime-dependencies"',
            'request("/v1/evasion/sandbox-evaluations"',
            "challenge_id: challenge.challenge_id, dependency_id: dependency.dependency_id",
            "challenge_id: challenge.challenge_id, evaluation_id: evaluation.evaluation_id",
            '"kep-m02-h": "Publish the supplied wheel',
            '"kep-m02-m": "Enter the runtime dependency ID',
        ):
            self.assertIn(marker, UI)


if __name__ == "__main__":
    unittest.main()
