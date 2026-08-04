from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import pickle
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


MODULE = Path(__file__).parents[1] / "runtime" / "release_operations.py"
MODULE_ROOT = Path(__file__).parents[1]
OPERATIONS = MODULE_ROOT / "operations.json"
APPLY = MODULE_ROOT / "apply.sh"
VALIDATE = MODULE_ROOT / "validate.sh"
AIRFLOW_RECONCILER = MODULE_ROOT / "runtime" / "reconcile_airflow_roles.py"
COMPOSE_OVERLAY = MODULE_ROOT / "compose.overlay.yaml"
IMPORT_WORKER = MODULE_ROOT / "runtime" / "import_worker.py"


def load_release_operations():
    boto3 = ModuleType("boto3")
    botocore = ModuleType("botocore")
    botocore_config = ModuleType("botocore.config")
    botocore_config.Config = object
    mlflow = ModuleType("mlflow")
    mlflow.MlflowClient = object
    stubs = {
        "boto3": boto3,
        "botocore": botocore,
        "botocore.config": botocore_config,
        "mlflow": mlflow,
        "pika": ModuleType("pika"),
        "requests": ModuleType("requests"),
    }
    spec = importlib.util.spec_from_file_location("m09_release_operations", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def load_import_worker():
    pika = ModuleType("pika")
    requests = ModuleType("requests")
    picklescan = ModuleType("picklescan")
    picklescan_scanner = ModuleType("picklescan.scanner")
    picklescan_scanner.scan_file_path = object
    spec = importlib.util.spec_from_file_location("m09_import_worker", IMPORT_WORKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    with patch.dict(
        sys.modules,
        {
            "pika": pika,
            "requests": requests,
            "picklescan": picklescan,
            "picklescan.scanner": picklescan_scanner,
        },
    ):
        spec.loader.exec_module(module)
    return module


class ReleaseOperationsDigestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release_operations = load_release_operations()

    def test_prefixed_m07_source_tree_digest_matches_once_normalized(self) -> None:
        value = "a" * 64
        self.assertTrue(
            self.release_operations.digests_match(f"sha256:{value}", f"sha256:{value}")
        )
        self.assertTrue(self.release_operations.digests_match(f"sha256:{value}", value))
        self.assertFalse(
            self.release_operations.digests_match(f"sha256:{value}", f"sha256:{'b' * 64}")
        )


class ReleaseOperationsPrerequisiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release_operations = load_release_operations()

    def test_visible_gate_uses_one_m07_alternative_group(self) -> None:
        expected = [["kep-m07-e", "kep-m07-g", "kep-m07-i"]]
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-b"], expected)

    def test_operations_visible_gate_declares_any_predecessor(self) -> None:
        operations = {item["id"]: item for item in json.loads(OPERATIONS.read_text())}
        visible_gate = operations["kep-m09-b"]
        self.assertEqual(visible_gate["board_prerequisites"], [])
        self.assertEqual(visible_gate["prerequisite_mode"], "any")
        self.assertEqual(
            visible_gate["prerequisite_logic"],
            "kep-m07-e OR kep-m07-g OR kep-m07-i",
        )

    def test_import_dag_leaves_cross_module_admission_to_campaign_graph(self) -> None:
        operations = {item["id"]: item for item in json.loads(OPERATIONS.read_text())}
        self.assertEqual(
            operations["kep-m09-i"]["prerequisites"],
            ["kep-m02-e", "kep-m01-g"],
        )
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-i"], [])

    def test_registration_lineage_approval_leave_cross_module_admission_to_campaign_graph(self) -> None:
        operations = {item["id"]: item for item in json.loads(OPERATIONS.read_text())}
        self.assertIn("kep-m05-l", operations["kep-m09-a"]["prerequisites"])
        self.assertIn("kep-m05-l", operations["kep-m09-c"]["prerequisites"])
        self.assertIn("kep-m01-d", operations["kep-m09-d"]["prerequisites"])
        self.assertIn("kep-m06-n", operations["kep-m09-h"]["prerequisites"])
        self.assertIn("kep-m03-b", operations["kep-m09-j"]["prerequisites"])
        self.assertIn("kep-m05-k", operations["kep-m09-l"]["prerequisites"])
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-a"], [["kep-m09-b"]])
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-c"], [["kep-m09-a"]])
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-d"], [["kep-m09-a"]])
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-h"], [["kep-m07-i"]])
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-j"], [["kep-m09-h"]])
        self.assertEqual(self.release_operations.PREREQUISITES["kep-m09-l"], [["kep-m09-k"]])

    def test_visible_gate_uses_seeded_release_risk_repository(self) -> None:
        source = MODULE.read_text()
        self.assertIn('review_repository = "orion-release/orion-release-risk"', source)
        self.assertNotIn("orion-release/orion-release-evaluator", source)

    def test_cinder_release_assets_tolerate_internal_lab_tls(self) -> None:
        source = MODULE.read_text()
        self.assertIn("def cinder_asset_bytes", source)
        self.assertIn("verify=False", source)
        self.assertNotIn('requests.get(asset["browser_download_url"], auth=CINDER_AUTH, timeout=120)', source)

    def test_serialized_predecessor_uses_signed_fresh_inference_controls(self) -> None:
        source = MODULE.read_text()
        self.assertIn('if predictions[:visible_end] != expected[:visible_end]:', source)
        self.assertIn('observed_labels != compromised.get("fresh_inference")', source)
        self.assertIn("elif predictions != expected:", source)

    def test_candidate_registration_allows_historical_qa_fixture_provenance(self) -> None:
        source = MODULE.read_text()
        self.assertIn("if actions_run_id == 0:", source)
        self.assertIn("historical source commit predates the BuildKit workflow", source)

    def test_mirror_sync_publishes_downloadable_model_bytes(self) -> None:
        source = MODULE.read_text()
        self.assertIn("client.put_object(Bucket=\"artifacts\", Key=object_key, Body=body", source)
        self.assertIn("publish_nextcloud_record(object_key, body)", source)
        self.assertIn("application/vnd.oci.image.index.v1+json", source)
        self.assertIn("Harbor image index has no runnable image manifest", source)
        self.assertIn('vnd.docker.reference.type") == "attestation-manifest"', source)
        self.assertIn("allowed_subjects.add", source)
        self.assertIn('statement_text = canonical({"subject": subjects, "materials": materials})', source)

    def test_staging_provenance_accepts_forgejo_task_listing(self) -> None:
        release_operations = self.release_operations
        source_commit = "a" * 40

        def forgejo(method: str, path: str, **kwargs: object) -> dict[str, object]:
            if path.endswith("/actions/runs/7"):
                raise RuntimeError("direct run endpoint is absent on this Forgejo build")
            if path.endswith("/actions/tasks?limit=100"):
                return {
                    "workflow_runs": [
                        {
                            "id": 425,
                            "run_number": 7,
                            "status": "success",
                            "head_sha": source_commit,
                            "workflow_id": "staging-image.yml",
                        }
                    ]
                }
            raise AssertionError(path)

        release_operations.forgejo = forgejo
        run = release_operations.forgejo_action_run("keplerops", "orion-staging", 7)

        self.assertTrue(run["successful"])
        self.assertEqual(run["head_sha"], source_commit)
        self.assertTrue(
            release_operations.workflow_matches(
                run["workflow"], ".forgejo/workflows/staging-image.yml",
            )
        )


class ReleaseOperationsAccessContractTest(unittest.TestCase):
    def test_apply_delivers_bounded_m09_participant_access(self) -> None:
        apply_source = APPLY.read_text()
        reconciler_source = AIRFLOW_RECONCILER.read_text()
        for marker in (
            "Orion Release Runner",
            "/home/kasm-user/.keplerops/m09-earned.env",
            "grant_repo keplerops orion-release-suite",
            "grant_repo keplerops orion-release-approvals",
            "grant_repo keplerops orion-release-approvals release.engineer",
            "grant_repo keplerops orion-model-review release.engineer",
            "gitops/orion-staging/kustomization.yaml",
            "ensure_harbor_labeler",
            "artifact-label",
            "HARBOR_URL=https://registry.keplerops.lab",
            "HARBOR_USER=$(shell_quote",
            "ensure_business_release_access",
            "business-release.env",
            "ensure_mlflow_access",
            "ensure_nextcloud_access",
            "ensure_m07_handoff_access",
            "ensure_k3s_key_access",
            "ensure_k3s_namespaces",
            "create namespace orion-evaluation",
            "FILES_URL=https://files.keplerops.lab",
            "'{\"is_paused\":false}'",
            "install -d -m 0770 -o 50000 -g 0",
            "install -d -m 0770 -o 50000 -g 10001",
            "for _ in $(seq 1 30); do",
            "orion_visible_release_evaluation",
            "orion_import_exception_review",
            "curl -kfsS -H \"Host: ${RELAY_HOST}\" -H \"Authorization: ${token}\"",
        ):
            self.assertIn(marker, apply_source)
        self.assertIn("ROLE_NAME = \"Orion Release Runner\"", reconciler_source)
        self.assertIn("PARTICIPANT_USER", reconciler_source)
        self.assertIn("add_user(", reconciler_source)
        self.assertIn("reset_password", reconciler_source)
        self.assertIn("find_user(username=PARTICIPANT_USER)", reconciler_source)
        self.assertIn("orion_visible_release_evaluation", reconciler_source)
        self.assertIn("orion_import_exception_review", reconciler_source)
        self.assertIn("unscoped DAG access", reconciler_source)
        self.assertIn("non-M09 DAG access", reconciler_source)
        self.assertIn('command: ["api-server", "--workers", "1"]', COMPOSE_OVERLAY.read_text())
        self.assertIn("./state/campaign-start/m09/k3s-key:/run/keplerops/k3s-key:ro", COMPOSE_OVERLAY.read_text())
        self.assertIn("MLFLOW_AUTH: range-admin", COMPOSE_OVERLAY.read_text())
        self.assertIn("NEXTCLOUD_URL: http://nextcloud", COMPOSE_OVERLAY.read_text())
        self.assertIn("NEXTCLOUD_HOST: files.keplerops.lab", COMPOSE_OVERLAY.read_text())
        self.assertIn('${url} =~ ^https://git\\.cinder\\.lab/', VALIDATE.read_text())
        self.assertNotIn("airflow users ", apply_source)
        self.assertIn('readonly RELAY_HOST="${CINDER_RELAY_INTERNAL_HOST:-relay.cinder.cinder.lab}"', apply_source)
        self.assertIn('-H "Host: ${RELAY_HOST}"', apply_source)

    def test_native_minio_records_are_projected_to_participant_files(self) -> None:
        source = MODULE.read_text()
        self.assertIn("def publish_nextcloud_record", source)
        self.assertIn("NEXTCLOUD_USER", source)
        self.assertIn("publish_nextcloud_record(object_key, body)", source)

    def test_mlflow_native_verification_uses_configured_runtime_auth(self) -> None:
        source = MODULE.read_text()
        self.assertIn('elif system == "mlflow":\n        mlflow_setup()\n        path = Path(mlflow.artifacts.download_artifacts', source)

    def test_isolated_candidate_load_passes_script_on_stdin(self) -> None:
        source = MODULE.read_text()
        self.assertIn("delete job/{name} networkpolicy/{name}-deny --ignore-not-found", source)
        self.assertIn("delete pod -l job-name={name} --ignore-not-found --wait=true", source)
        self.assertIn('k3s kubectl -n orion-evaluation exec -i "$pod" -- python -', source)

    def test_model_version_tags_fall_back_for_live_integer_version_schema(self) -> None:
        source = MODULE.read_text()
        self.assertIn("def set_model_version_tags", source)
        self.assertIn("def get_model_version_tags", source)
        self.assertIn("def set_model_version_alias", source)
        self.assertIn("def get_model_version_by_alias", source)
        self.assertIn("operator does not exist: integer = character varying", source)
        self.assertIn("INSERT INTO model_version_tags", source)
        self.assertIn("INSERT INTO registered_model_aliases", source)
        self.assertIn("set_model_version_tags(client, model_name, str(version.version), values)", source)
        self.assertIn("version_tags = get_model_version_tags", source)
        self.assertIn("resolved = get_model_version_by_alias", source)

    def test_approval_rehydrates_volatile_opa_records(self) -> None:
        source = MODULE.read_text()
        self.assertIn("def publish_candidate_policy_data", source)
        self.assertIn("def publish_evaluation_policy_data", source)
        self.assertIn('evaluation = accepted("kep-m09-b")', source)
        self.assertIn("accepted visible evaluation does not match", source)
        self.assertIn("publish_candidate_policy_data(candidate)", source)
        self.assertIn("publish_evaluation_policy_data(evaluation)", source)
        self.assertGreaterEqual(source.count("publish_candidate_policy_data(candidate)"), 2)
        self.assertGreaterEqual(source.count("publish_evaluation_policy_data(evaluation)"), 2)
        self.assertIn('(artifact.get("labels") or [])', source)
        self.assertIn('lineage_record["record_digest"]', source)
        self.assertIn('opa_data("lineage", candidate_key(candidate)', source)
        self.assertIn('opa_data("approval_decisions", approval_record["decision_digest"]', source)
        self.assertIn('opa_data("image_binding_decisions", binding["decision_digest"]', source)
        self.assertIn('opa_data("signed_releases", release_id', source)
        self.assertIn('opa_data("signed_releases", signed["release_id"]', source)
        self.assertIn("predecessor.get('artifact_digest') or predecessor.get('model_digest')", source)
        self.assertIn("execution.get('heldout_evidence_sha256') or execution.get('heldout_suite_sha256')", source)
        self.assertIn('artifact_source_commit = str(predecessor.get("artifact_source_commit")', source)
        self.assertIn('artifact_source_repository = str(predecessor.get("artifact_source_repository")', source)
        self.assertNotIn('track(manifest, "forgejo", "file", owner=', source)
        self.assertIn("repository_owner=", source)
        self.assertIn("--slurpfile application", source)
        self.assertNotIn("--argjson application", source)
        self.assertIn('config_work=\\"$(mktemp -d)\\"', source)
        self.assertIn('rm -rf \\"$config_work\\"', source)
        self.assertIn("expected_image_digest = digest(expected_image)", source)
        self.assertIn("rollout status deployment/{service}-predictor", source)
        self.assertIn("--arg digest", source)
        self.assertIn("exec -i \"$pod\" -c kserve-container -- python -", source)
        self.assertIn("requests: {{cpu: 50m, memory: 128Mi}}", source)
        self.assertGreaterEqual(source.count("seccompProfile: {{type: RuntimeDefault}}"), 2)

    def test_import_worker_trusts_the_campaign_route_ca(self) -> None:
        compose_source = COMPOSE_OVERLAY.read_text()
        self.assertIn("REQUESTS_CA_BUNDLE: /etc/keplerops/caddy-root.crt", compose_source)
        self.assertIn("RELAY_INTERNAL_URL: http://192.168.78.30:31080", compose_source)
        self.assertIn("RELAY_HOST: relay.cinder.cinder.lab", compose_source)
        self.assertIn(
            "./state/caddy-root.crt:/etc/keplerops/caddy-root.crt:ro",
            compose_source,
        )


class ImportWorkerRegressionTest(unittest.TestCase):
    def test_corrupt_pickle_records_effect_before_later_parse_failure(self) -> None:
        worker = load_import_worker()
        expression = "open('orion-deserialization-canary','w').write('bounded isolated effect')"

        class ImportHook:
            def __reduce__(self):
                return eval, (expression,)

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "orion-corrupt.pkl"
            encoded = pickle.dumps(ImportHook(), protocol=4)
            artifact.write_bytes(encoded[:-1] + b"\xff")
            result = worker.isolated_load(artifact)

        self.assertNotEqual(result["returncode"], 0)
        self.assertEqual(
            result["bounded_event"]["event"],
            "deserialization-canary",
        )

    def test_relay_result_uses_the_basket_ingress_path(self) -> None:
        worker = load_import_worker()
        observed = {}

        class Response:
            def raise_for_status(self):
                return None

        def post(url, **kwargs):
            observed.update({"url": url, **kwargs})
            return Response()

        worker.requests.post = post
        with patch.dict(
            os.environ,
            {
                "RELAY_INTERNAL_URL": "http://192.168.78.30:31080",
                "RELAY_HOST": "relay.cinder.cinder.lab",
            },
        ):
            worker.post_relay("m09-import-exceptions", {"status": "accepted"})

        self.assertEqual(
            observed["url"],
            "http://192.168.78.30:31080/m09-import-exceptions",
        )
        self.assertEqual(observed["headers"], {"Host": "relay.cinder.cinder.lab"})


if __name__ == "__main__":
    unittest.main()
