"""Focused contracts for the remaining GCP company-state service adapters."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

PACK = Path(__file__).resolve().parents[2]
SERVICES = PACK / "assets/services"
WORKFLOWS = PACK / "assets/workflows"
CORPUS = PACK / "assets/content/company-state/company-state.yaml"
OBJECTS = CORPUS.parent / "objects"
ENVIRONMENT = PACK / "sdl/modules/environment.sdl.yaml"

for module_root in (SERVICES, WORKFLOWS):
    sys.path.insert(0, str(module_root))


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


minio = load_module("company_minio_adapter_test", SERVICES / "company_minio_adapter.py")
keycloak = load_module(
    "company_keycloak_adapter_test", SERVICES / "company_keycloak_adapter.py"
)
airflow = load_module(
    "company_airflow_adapter_test", WORKFLOWS / "company_airflow_adapter.py"
)
opa = load_module("company_opa_adapter_test", SERVICES / "company_opa_adapter.py")
telemetry = load_module(
    "company_telemetry_adapter_test", SERVICES / "company_telemetry_adapter.py"
)


CHALLENGE_FILE_DIGESTS = {
    "assets/services/keycloak-realm.json": "6ded3487449a4f4e7bf77a59b60d2a9c7847b69bbccb1acd0fadf31e03124a47",
    "assets/model-artifacts/deployment-manifest.yaml": "bee34c5c0e894e0c9c6314d957512d19fbe0309aabdc73dfc4812c8560cb2a1b",
    "assets/model-artifacts/model.yaml": "1ef0674d3d2b821c33a92c513f13376282f3f072a5f49fb9b28221dfcd6c0c83",
    "assets/workflows/keplerops_distillation.py": "d0d458a21542272684f17ba36bfaed6d0392562b8e845b2834da9a7f5ac1acbe",
    "assets/workflows/research_content.py": "4f446d49094af2a7d9b2d29d7e2b5716acd1bd2ed21b464f7e48f82519c59772",
    "assets/workflows/training_model.py": "24e447a952278656868d758b484615bc58475a07184194c779b0f26c0c8bf2d0",
    "assets/policies/guardrails.rego": "7139cc63184a3c74fb616db47347519d937ea13e42ab18e58705a1a8412ed9b1",
    "assets/services/keplerops-runtime/app.py": "f1873176d22b5606559842dbe908eaeb5afbf54d9a94e36e4e9543fe2887c0a4",
    "assets/services/keplerops-runtime/keplerops_runtime/proof/ingest_routes.py": "51cbb226834cf1ebea75bc84e840ab8fc0688a82aeba4d732de4060fcd5c132b",
}

SERVICE_CONTENT_ADAPTERS = {
    "company-directory-state": PACK / "build/gcp/windows-bootstrap.ps1.tpl",
    "company-identity-facade-state": SERVICES / "company_keycloak_adapter.py",
    "company-workhub-state": SERVICES / "seed_workhub.rb",
    "company-mail-state": (
        SERVICES / "platform-communications/mail/stalwart-entrypoint.sh"
    ),
    "company-file-state": PACK / "build/gcp/windows-bootstrap.ps1.tpl",
    "company-data-state": PACK / "assets/model-artifacts/company_postgres_seed.py",
    "company-workflow-state": WORKFLOWS / "company_airflow_adapter.py",
    "company-notebook-state": (
        PACK / "assets/model-artifacts/company_notebook_readback.py"
    ),
    "company-artifact-state": SERVICES / "company_minio_adapter.py",
    "company-model-registry-state": (
        PACK / "assets/model-artifacts/company_mlflow_seed.py"
    ),
    "company-research-index-state": (
        SERVICES / "platform-network/opensearch/generate-company-corpus.py"
    ),
    "company-policy-state": SERVICES / "company_opa_adapter.py",
    "company-operational-telemetry": SERVICES / "company_telemetry_adapter.py",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def airflow_rows(plan: dict) -> list[dict]:
    return [
        {
            "dag_id": plan["dag_id"],
            "run_id": row["run_id"],
            "logical_date": row["logical_date"].replace("Z", "+00:00"),
            "state": row["terminal_state"],
        }
        for row in plan["records"]
    ]


class CompanyServiceAdapterTests(unittest.TestCase):
    def test_native_service_endpoints_are_loopback_only(self) -> None:
        self.assertEqual(
            keycloak.validated_loopback_server("https://127.0.0.1:8443/"),
            "https://127.0.0.1:8443",
        )
        self.assertEqual(
            telemetry.loopback_otlp_endpoint("http://localhost:4320/v1/logs"),
            "http://localhost:4320/v1/logs",
        )
        for endpoint in (
            "http://169.254.169.254:80/",
            "http://127.0.0.1:8443/admin",
            "http://user@127.0.0.1:8443/",
        ):
            with self.subTest(keycloak_endpoint=endpoint):
                with self.assertRaises(ValueError):
                    keycloak.validated_loopback_server(endpoint)
        for endpoint in (
            "http://169.254.169.254:4320/v1/logs",
            "http://127.0.0.1:4320/other",
            "http://user@127.0.0.1:4320/v1/logs",
        ):
            with self.subTest(otlp_endpoint=endpoint):
                with self.assertRaises(ValueError):
                    telemetry.loopback_otlp_endpoint(endpoint)

    def test_every_raes_service_content_placement_has_an_adapter_owner(self) -> None:
        environment = yaml.safe_load(ENVIRONMENT.read_text(encoding="utf-8"))
        placements = {
            content_id
            for content_id, content in environment["content"].items()
            if content.get("service_materialization", {}).get("interface_profile")
            == "service-content"
        }
        self.assertEqual(set(SERVICE_CONTENT_ADAPTERS), placements)
        for content_id, adapter_path in SERVICE_CONTENT_ADAPTERS.items():
            with self.subTest(content_id=content_id):
                self.assertTrue(adapter_path.is_file(), adapter_path)

    def test_positive_plans_cover_exact_raes_slices(self) -> None:
        artifact = minio.build_plan(CORPUS, OBJECTS)
        identity_group, identity_records = keycloak.build_group(CORPUS)
        workflow = airflow.build_plan(CORPUS)
        policy = opa.build_document(CORPUS)
        operations = telemetry.build_plan(CORPUS)

        self.assertEqual(artifact["content_id"], "company-artifact-state")
        self.assertEqual(len(artifact["records"]), 3)
        self.assertEqual(identity_group["name"], "Company State")
        self.assertEqual(len(identity_records), 6)
        self.assertEqual(workflow["content_id"], "company-workflow-state")
        self.assertEqual(len(workflow["records"]), 3)
        self.assertEqual(policy["content_id"], "company-policy-state")
        self.assertEqual(len(policy["records"]), 3)
        self.assertEqual(
            operations["readback"]["content_id"],
            "company-operational-telemetry",
        )
        self.assertEqual(operations["readback"]["record_count"], 5)

    def test_minio_native_readback_detects_mutation_and_unowned_collision(self) -> None:
        plan = minio.build_plan(CORPUS, OBJECTS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for row in plan["records"]:
                target = root / row["object_key"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(OBJECTS / row["source_file"], target)
                marker = root / "company-state/v1/.ownership" / row["id"]
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("keplerops-company-state\n", encoding="ascii")
            result = minio.verify_files(plan, root)
            self.assertEqual(result, plan["readback"])

            target = root / plan["records"][0]["object_key"]
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(RuntimeError, "readback digest mismatch"):
                minio.verify_files(plan, root)

            shutil.copyfile(OBJECTS / plan["records"][0]["source_file"], target)
            marker = root / "company-state/v1/.ownership" / plan["records"][0]["id"]
            marker.write_text("some-other-owner\n", encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "unowned MinIO collision"):
                minio.verify_files(plan, root)

    def test_keycloak_addition_preserves_baseline_and_rejects_collisions(self) -> None:
        baseline_path = SERVICES / "keycloak-realm.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        rendered, expected = keycloak.render_realm(baseline_path, CORPUS)
        company_groups = [
            group for group in rendered["groups"] if group["name"] == "Company State"
        ]
        self.assertEqual(len(company_groups), 1)
        without_company = copy.deepcopy(rendered)
        without_company["groups"] = [
            group
            for group in without_company["groups"]
            if group["name"] != "Company State"
        ]
        normalized_baseline = copy.deepcopy(baseline)
        keycloak.normalize_import_components(normalized_baseline.get("components"))
        self.assertEqual(without_company, normalized_baseline)
        self.assertEqual(keycloak.readback_import(rendered, CORPUS), expected)

        mutated = copy.deepcopy(rendered)
        mutated["groups"][-1]["subGroups"][0]["realmRoles"] = ["participant"]
        with self.assertRaisesRegex(RuntimeError, "native readback mismatch"):
            keycloak.readback_import(mutated, CORPUS)

        with tempfile.TemporaryDirectory() as directory:
            collision = copy.deepcopy(baseline)
            collision["groups"].append({"name": "Company State"})
            path = Path(directory) / "realm.json"
            path.write_text(json.dumps(collision), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ownership collision"):
                keycloak.render_realm(path, CORPUS)

    def test_keycloak_admin_api_projection_detects_runtime_mutation(self) -> None:
        expected_group, _records = keycloak.build_group(CORPUS)
        root = {
            "id": "root-id",
            "name": expected_group["name"],
            "attributes": expected_group["attributes"],
        }
        subgroups = []
        role_mappings = {}
        for index, expected_subgroup in enumerate(expected_group["subGroups"]):
            subgroup_id = f"subgroup-{index}"
            subgroups.append(
                {
                    "id": subgroup_id,
                    "name": expected_subgroup["name"],
                    "attributes": expected_subgroup["attributes"],
                }
            )
            role_mappings[subgroup_id] = [
                {"name": role} for role in expected_subgroup["realmRoles"]
            ]
        observed = keycloak.readback_admin_projection(
            root, subgroups, role_mappings, CORPUS
        )
        self.assertEqual(observed["record_count"], 6)

        role_mappings[subgroups[0]["id"]] = [{"name": "participant"}]
        with self.assertRaisesRegex(RuntimeError, "native readback mismatch"):
            keycloak.readback_admin_projection(root, subgroups, role_mappings, CORPUS)

    def test_airflow_native_readback_is_idempotent_and_rejects_extra_runs(self) -> None:
        plan = airflow.build_plan(CORPUS)
        rows = airflow_rows(plan)
        observed = airflow.readback(plan, rows)
        self.assertEqual(observed["record_count"], 3)

        commands: list[list[str]] = []

        def existing_runner(command: list[str]) -> str:
            commands.append(command)
            return json.dumps(rows)

        self.assertEqual(
            airflow.seed(plan, existing_runner)["canonical_digest"],
            plan["canonical_digest"],
        )
        self.assertEqual(len(commands), 1)

        mutated = copy.deepcopy(rows)
        mutated[0]["state"] = (
            "failed" if mutated[0]["state"] == "success" else "success"
        )
        with self.assertRaisesRegex(RuntimeError, "readback digest mismatch"):
            airflow.readback(plan, mutated)

        extra = rows + [
            {
                "dag_id": plan["dag_id"],
                "run_id": "manual__unowned",
                "logical_date": "2026-05-18T08:00:00Z",
                "state": "success",
            }
        ]
        with self.assertRaisesRegex(RuntimeError, "extra runs"):
            airflow.readback(plan, extra)

    def test_opa_uses_owned_data_document_and_detects_mutation(self) -> None:
        document = opa.build_document(CORPUS)
        store: dict[str, object] = {}

        def transport(method: str, _url: str, payload=None):
            if method == "GET":
                return {"result": copy.deepcopy(store["document"])} if store else None
            store["document"] = copy.deepcopy(payload)
            return None

        result = opa.seed(document, transport, base_url="http://opa")
        self.assertEqual(result, document["readback"])

        store["document"]["records"][0]["source_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(RuntimeError, "readback digest mismatch"):
            opa.readback(document, transport, base_url="http://opa")

        store["document"] = {"owner": "challenge-policy"}
        with self.assertRaisesRegex(RuntimeError, "ownership collision"):
            opa.seed(document, transport, base_url="http://opa")

    def test_telemetry_otlp_readback_is_non_proof_and_reset_reconstructable(
        self,
    ) -> None:
        plan = telemetry.build_plan(CORPUS)
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "operations.jsonl"
            export.write_text(
                json.dumps(plan["payload"], separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                telemetry.readback(plan["readback"], export),
                plan["readback"],
            )

            mutated = json.loads(export.read_text(encoding="utf-8"))
            attributes = mutated["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0][
                "attributes"
            ]
            attributes[-1]["value"]["stringValue"] = "sha256:" + "0" * 64
            export.write_text(json.dumps(mutated) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "readback digest mismatch"):
                telemetry.readback(plan["readback"], export)

            export.write_text(
                json.dumps(plan["payload"], separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            telemetry.prepare(export)
            self.assertFalse(export.exists())

            collision = copy.deepcopy(plan["payload"])
            resource = collision["resourceLogs"][0]["resource"]["attributes"]
            resource[1]["value"]["stringValue"] = "challenge-telemetry"
            export.write_text(json.dumps(collision) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ownership collision"):
                telemetry.prepare(export)

        source = (SERVICES / "company_telemetry_adapter.py").read_text(encoding="utf-8")
        self.assertNotIn("proof.sqlite3", source)
        self.assertNotIn("/v1/evidence", source)
        self.assertNotIn("receipt", source.lower())

    def test_challenge_artifacts_and_namespaces_are_preserved(self) -> None:
        for relative, expected in CHALLENGE_FILE_DIGESTS.items():
            self.assertEqual(digest(PACK / relative), expected, relative)

        minio_shell = (SERVICES / "minio-company-state.sh").read_text(encoding="utf-8")
        airflow_source = (WORKFLOWS / "company_airflow_adapter.py").read_text(
            encoding="utf-8"
        )
        opa_source = (SERVICES / "company_opa_adapter.py").read_text(encoding="utf-8")
        collector = (SERVICES / "otel-collector.yaml").read_text(encoding="utf-8")
        self.assertIn("company-state/v1/", minio_shell)
        self.assertNotIn("manifests/", minio_shell)
        self.assertIn("company_state_orion_release", airflow_source)
        self.assertNotIn("keplerops_distillation", airflow_source)
        self.assertIn("/v1/data/keplerops/company_state", opa_source)
        self.assertNotIn("DELETE", opa_source)
        self.assertIn("otlp/company_state", collector)
        self.assertIn("logs/company_state", collector)

    def test_adapter_scripts_and_docker_wiring_are_valid(self) -> None:
        for script in (
            SERVICES / "minio-entrypoint.sh",
            SERVICES / "minio-company-state.sh",
            SERVICES / "keycloak-entrypoint.sh",
            SERVICES / "keycloak-company-state-readback.sh",
            SERVICES / "policy-entrypoint.sh",
            SERVICES / "proof-entrypoint.sh",
        ):
            completed = subprocess.run(
                ["sh", "-n", str(script)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
        completed = subprocess.run(
            ["bash", "-n", str(WORKFLOWS / "company-airflow-entrypoint.sh")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        dockerfiles = {
            "minio": (SERVICES / "Dockerfile.minio").read_text(encoding="utf-8"),
            "keycloak": (SERVICES / "Dockerfile.keycloak").read_text(encoding="utf-8"),
            "airflow": (WORKFLOWS / "Dockerfile").read_text(encoding="utf-8"),
            "opa": (SERVICES / "Dockerfile.policy").read_text(encoding="utf-8"),
            "telemetry": (SERVICES / "Dockerfile.proof").read_text(encoding="utf-8"),
        }
        for product, source in dockerfiles.items():
            with self.subTest(product=product):
                self.assertIn("assets/content/company-state/company-state.yaml", source)
        self.assertIn("company-state-readback", dockerfiles["keycloak"])
        self.assertIn("company-native-projection.json", dockerfiles["keycloak"])


if __name__ == "__main__":
    unittest.main()
