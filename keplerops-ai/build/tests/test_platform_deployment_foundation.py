from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-deployment"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


security = load_module("security", ASSET / "security.py")
store_module = load_module("platform_deployment_store_test", ASSET / "store.py")
sys.modules["store"] = store_module
policy_module = load_module("platform_deployment_policy_test", ASSET / "policy.py")
sys.modules["policy"] = policy_module
render_policy_module = load_module(
    "platform_deployment_render_policy_test", ASSET / "render_policy.py"
)


def policy_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "range_instance": "rehearsal-01",
        "participant": "team-01",
        "project_id": "keplerops-range-123",
        "region": "us-central1",
        "service_account": "keplerops-workspaces@keplerops-range-123.iam.gserviceaccount.com",
        "registry_url": "https://repo-ticket-01.keplerops.lab/git",
        "registry_username": "keplerops-registry",
        "repositories": ["keplerops/workspace"],
        "images": [
            "us-central1-docker.pkg.dev/keplerops-range-123/runtime/workspace@sha256:"
            + "a" * 64
        ],
        "command_profiles": {
            "analysis": {"command": ["/opt/keplerops/run"], "args": ["analysis"]}
        },
        "resource_profiles": {
            "small": {
                "cpu": "1",
                "memory": "512Mi",
                "timeout_seconds": 900,
                "max_retries": 0,
            }
        },
        "min_ttl_seconds": 300,
        "max_ttl_seconds": 3600,
        "export_bucket": "keplerops-workspace-exports",
        "export_prefix": "keplerops/rehearsal-01/team-01/workspaces",
        "export_max_files": 32,
        "export_max_bytes": 2097152,
    }


def policy_substitutions() -> dict[str, str]:
    return {
        "__RANGE_INSTANCE__": "rehearsal-01",
        "__PARTICIPANT__": "team-01",
        "__PROJECT_ID__": "keplerops-range-123",
        "__REGION__": "us-central1",
        "__SERVICE_ACCOUNT__": "keplerops-workspaces@keplerops-range-123.iam.gserviceaccount.com",
        "__EXPORT_BUCKET__": "keplerops-workspace-exports",
        "__PLATFORM_DEPLOYMENT_IMAGE__": "us-central1-docker.pkg.dev/keplerops-range-123/runtime/keplerops/keplerops-platform-deployment:build-1@sha256:"
        + "a" * 64,
    }


class PlatformDeploymentFoundationTests(unittest.TestCase):
    def test_source_compiles_and_uses_real_oci_and_cloud_clients(self) -> None:
        for path in ASSET.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        registry = (ASSET / "registry.py").read_text(encoding="utf-8")
        cloud = (ASSET / "cloud_boundary.py").read_text(encoding="utf-8")
        for boundary in (
            '"GET", "v2/"',
            "allow_registry_challenge=True",
            'authenticate.lower().startswith("bearer ")',
            'distribution.lower().startswith("registry/2")',
            'response.text == "authGroup.Verify\\n"',
            'f"v2/{repository}/tags/list"',
            '"docker-content-digest"',
            "hashlib.sha256(response.content)",
            "ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)",
            "context.minimum_version = ssl.TLSVersion.TLSv1_2",
            "context.verify_mode = ssl.CERT_REQUIRED",
            "context.check_hostname = True",
            "context.load_verify_locations(cafile=str(ca_path))",
            "serialization.load_pem_private_key",
            "self.public_key.verify",
        ):
            self.assertIn(boundary, registry)
        for boundary in (
            "run_v2.JobsClient()",
            "run_v2.ExecutionsClient()",
            "storage.Client(project=policy.project_id)",
            "self.jobs.create_job(",
            "self.jobs.run_job(",
            "self.jobs.delete_job(",
            "self.executions.list_executions(",
            "self.objects.list_blobs(",
            'blob.download_as_bytes(checksum="auto")',
        ):
            self.assertIn(boundary, cloud)

    def test_rendered_policy_output_is_confined_to_its_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "policy-root"
            root.mkdir()
            destination = root / "deployment-policy.json"
            self.assertEqual(
                render_policy_module._confined_output(destination, root),
                destination,
            )
            with self.assertRaises(ValueError):
                render_policy_module._confined_output(root, root)
            with self.assertRaises(ValueError):
                render_policy_module._confined_output(
                    root / ".." / "outside.json", root
                )

            outside = Path(directory) / "outside"
            outside.mkdir()
            (root / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                render_policy_module._confined_output(
                    root / "escape" / "deployment-policy.json", root
                )

    def test_container_and_dependency_pins_are_exact(self) -> None:
        dockerfile = (ASSET / "Dockerfile").read_text(encoding="utf-8")
        requirements = (ASSET / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("python@sha256:", dockerfile)
        self.assertNotIn("python:", dockerfile)
        self.assertNotIn("--chown=65532:65532", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn("EXPOSE 8490", dockerfile)
        self.assertIn('CMD ["api"]', dockerfile)
        self.assertIn("google-cloud-run==0.16.1", requirements)
        self.assertIn("google-cloud-storage==3.13.0", requirements)
        self.assertIn("policy-template.json ./policy-template.json", dockerfile)
        for line in requirements.splitlines():
            if line.strip():
                self.assertIn("==", line)

    def test_realization_policy_is_external_strict_and_digest_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment-policy.json"
            document = policy_document()
            path.write_text(json.dumps(document), encoding="utf-8")
            policy = policy_module.load_policy(path)
            self.assertEqual(policy.project_id, "keplerops-range-123")
            self.assertEqual(
                policy.location_name,
                "projects/keplerops-range-123/locations/us-central1",
            )
            self.assertEqual(len(policy.tenant_id), 12)
            document["images"] = [
                "us-central1-docker.pkg.dev/keplerops-range-123/runtime/workspace:latest"
            ]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ValueError):
                policy_module.load_policy(path)
        self.assertFalse((ASSET / "deployment-policy.json").exists())

    def test_policy_parses_bounded_structures_without_monolithic_input_regexes(
        self,
    ) -> None:
        source = (ASSET / "policy.py").read_text(encoding="utf-8")
        self.assertNotIn("SERVICE_ACCOUNT = re.compile", source)
        self.assertNotIn("IMAGE = re.compile", source)
        self.assertNotIn('re.fullmatch(r"(?:1|2|4|8)"', source)

        tagged = policy_document()
        tagged["images"] = [
            "us-central1-docker.pkg.dev:443/keplerops-range-123/runtime/workspace:build-1@sha256:"
            + "b" * 64
        ]
        self.assertEqual(
            policy_module.parse_policy(tagged).images, frozenset(tagged["images"])
        )

        invalid_fields: tuple[tuple[str, object], ...] = (
            ("range_instance", 123),
            ("region", "a" * 4096),
            (
                "service_account",
                "keplerops-workspaces@another-project.iam.gserviceaccount.com",
            ),
            ("registry_url", "https://repo-ticket-01.keplerops.lab/v2"),
            ("repositories", ["a" * 4096]),
            ("images", ["a" * 4096]),
            (
                "images",
                ["registry.invalid:99999/project/image@sha256:" + "a" * 64],
            ),
            ("export_prefix", "keplerops//rehearsal-01/team-01/workspaces"),
        )
        for field, value in invalid_fields:
            with self.subTest(field=field, value=value):
                document = json.loads(json.dumps(policy_document()))
                document[field] = value
                with self.assertRaises(ValueError):
                    policy_module.parse_policy(document)

        malformed_resources = json.loads(json.dumps(policy_document()))
        malformed_resources["resource_profiles"]["small"]["memory"] = "٥١٢Mi"
        with self.assertRaises(ValueError):
            policy_module.parse_policy(malformed_resources)

    def test_sdl_bindable_template_owns_static_policy_and_renders_owner_only(
        self,
    ) -> None:
        template = json.loads(
            (ASSET / "policy-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            template["registry_url"], "https://repo-ticket-01.keplerops.lab"
        )
        self.assertEqual(template["registry_username"], "ml.engineer")
        self.assertEqual(template["repositories"], ["ml.engineer/keplerops-workspace"])
        self.assertEqual(
            template["command_profiles"]["integrity-inventory"],
            {
                "command": ["/opt/keplerops/platform-deployment/entrypoint.sh"],
                "args": ["workspace"],
            },
        )
        self.assertEqual(
            template["resource_profiles"]["workspace-small"]["max_retries"], 0
        )
        self.assertEqual(template["min_ttl_seconds"], 300)
        self.assertEqual(template["max_ttl_seconds"], 1800)
        self.assertEqual(template["export_max_files"], 16)
        self.assertEqual(template["export_max_bytes"], 8388608)
        document, policy = render_policy_module.render_document(
            template, policy_substitutions()
        )
        self.assertEqual(policy.range_instance, "rehearsal-01")
        self.assertEqual(
            document["images"],
            [policy_substitutions()["__PLATFORM_DEPLOYMENT_IMAGE__"]],
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "deployment-policy.json"
            render_policy_module.write_policy(destination, document)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")), document
            )

    def test_policy_renderer_rejects_extra_unresolved_and_non_boundary_image(
        self,
    ) -> None:
        template = json.loads(
            (ASSET / "policy-template.json").read_text(encoding="utf-8")
        )
        extra = json.loads(json.dumps(template))
        extra["unsupported"] = True
        with self.assertRaises(ValueError):
            render_policy_module.render_document(extra, policy_substitutions())
        nested_extra = json.loads(json.dumps(template))
        nested_extra["command_profiles"]["integrity-inventory"]["shell"] = True
        with self.assertRaises(ValueError):
            render_policy_module.render_document(nested_extra, policy_substitutions())
        unresolved = json.loads(json.dumps(template))
        unresolved["registry_username"] = "__UNSUPPORTED_VALUE__"
        with self.assertRaises(ValueError):
            render_policy_module.render_document(unresolved, policy_substitutions())
        missing = policy_substitutions()
        missing.pop("__EXPORT_BUCKET__")
        with self.assertRaises(ValueError):
            render_policy_module.render_document(template, missing)
        wrong_image = policy_substitutions()
        wrong_image["__PLATFORM_DEPLOYMENT_IMAGE__"] = (
            "us-central1-docker.pkg.dev/keplerops-range-123/runtime/other:one@sha256:"
            + "b" * 64
        )
        with self.assertRaises(ValueError):
            render_policy_module.render_document(template, wrong_image)

    def test_store_has_idempotency_full_telemetry_and_safe_reset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = store_module.StateStore(Path(directory), "a" * 12)
            request = {"request_id": "resolve-001", "repository": "keplerops/workspace"}
            self.assertIsNone(store.begin_request("resolve-001", "resolve", request))
            result = {
                "immutable_reference": "registry/keplerops/workspace@sha256:" + "b" * 64
            }
            store.finish_request("resolve-001", result)
            self.assertEqual(
                store.begin_request("resolve-001", "resolve", request), result
            )
            with self.assertRaises(store_module.ConflictError):
                store.begin_request(
                    "resolve-001", "resolve", {**request, "repository": "other/image"}
                )
            store.record_event(
                "platform_deployment.test",
                "test",
                "succeeded",
                "resolve-001",
                {"full": "request"},
                {"full": "response"},
                1.0,
            )
            self.assertEqual(
                store.recent_events(1)[0]["response"], {"full": "response"}
            )
            store.reset_local()
            self.assertEqual(store.recent_events(1), [])

    def test_persistence_and_reset_are_tenant_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = store_module.StateStore(root, "a" * 12)
            second = store_module.StateStore(root, "b" * 12)
            first.record_event(
                "first", "test", "succeeded", None, {}, {"tenant": "first"}, 0.0
            )
            second.record_event(
                "second", "test", "succeeded", None, {}, {"tenant": "second"}, 0.0
            )
            first.reset_local()
            self.assertEqual(first.recent_events(10), [])
            self.assertEqual(
                second.recent_events(10)[0]["response"], {"tenant": "second"}
            )

    def test_workspace_authority_cannot_be_supplied_by_api_callers(self) -> None:
        api = (ASSET / "api.py").read_text(encoding="utf-8")
        cloud = (ASSET / "cloud_boundary.py").read_text(encoding="utf-8")
        for field in (
            "request_id: str",
            "image: str",
            "command_profile: str",
            "resource_profile: str",
            "ttl_seconds: int",
        ):
            self.assertIn(field, api)
        workspace_model = api.split("class WorkspaceRequest", 1)[1].split(
            "def require_authorization", 1
        )[0]
        for forbidden in (
            "project",
            "region",
            "service_account",
            "bucket",
            "environment",
        ):
            self.assertNotIn(forbidden, workspace_model)
        self.assertIn("service_account=self.policy.service_account", cloud)
        self.assertIn('if request["image"] not in self.policy.images', cloud)
        self.assertIn("set(request) !=", cloud)
        self.assertIn("Reset deletes only exact job names", api)
        self.assertIn('f"kep-{self.policy.tenant_id}-{suffix}"', cloud)
        self.assertIn('"keplerops-tenant": self.policy.tenant_id', cloud)
        self.assertIn(
            "refusing to operate on a Cloud Run job outside the active tenant", cloud
        )

    def test_image_contains_a_real_fixed_bounded_cloud_run_workspace(self) -> None:
        entrypoint = (ASSET / "entrypoint.sh").read_text(encoding="utf-8")
        workspace = (ASSET / "workspace.py").read_text(encoding="utf-8")
        self.assertIn("workspace)", entrypoint)
        self.assertIn("workspace.py integrity-inventory", entrypoint)
        self.assertIn("render-policy)", entrypoint)
        self.assertIn('exec python3 render_policy.py "$@"', entrypoint)
        for boundary in (
            'os.environ.get("KEPLEROPS_WORKSPACE_ID"',
            'os.environ.get("KEPLEROPS_EXPORT_URI"',
            "MAX_FILES = 128",
            "MAX_FILE_BYTES = 4_194_304",
            "hashlib.sha256(content)",
            "blob.upload_from_string(",
            "if_generation_match=0",
            'sys.argv[1:] != ["integrity-inventory"]',
        ):
            self.assertIn(boundary, workspace)
        for forbidden in ("subprocess", "shell=true", "os.system", "eval(", "exec("):
            self.assertNotIn(forbidden, workspace.lower())

    def test_api_and_lifecycle_worker_have_role_appropriate_health(self) -> None:
        entrypoint = (ASSET / "entrypoint.sh").read_text(encoding="utf-8")
        worker = (ASSET / "lifecycle_worker.py").read_text(encoding="utf-8")
        health = (ASSET / "healthcheck.py").read_text(encoding="utf-8")
        self.assertIn("PLATFORM_DEPLOYMENT_ROLE=lifecycle-worker", entrypoint)
        self.assertIn('root / "lifecycle-heartbeat"', worker)
        self.assertIn('role == "lifecycle-worker"', health)
        self.assertIn("heartbeat.stat().st_mtime > 300", health)
        self.assertIn(
            "PLATFORM_DEPLOYMENT_CA_FILE=/run/tls/ca.crt",
            (ASSET / "Dockerfile").read_text(encoding="utf-8"),
        )

    def test_no_project_billing_identity_or_bucket_provisioning_boundary(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in ASSET.rglob("*")
            if path.is_file()
        ).lower()
        for forbidden in (
            "create_project",
            "projectsclient",
            "cloudresourcemanager",
            "billing_v1",
            "billingaccounts",
            "create_service_account",
            "iamadminclient",
            "set_iam_policy",
            "create_bucket",
            "topology.yaml",
            "service-manifest",
            "challenge_id",
            "receipt_id",
            "ctfd",
            "scoring",
            "atlas technique",
        ):
            self.assertNotIn(forbidden, combined)

    def test_api_is_authenticated_and_exposes_reset_and_research_events(self) -> None:
        api = (ASSET / "api.py").read_text(encoding="utf-8")
        for route in (
            '"/v1/registry/reputation-events"',
            '"/v1/registry/resolutions"',
            '"/v1/workspaces"',
            '"/v1/admin/events"',
            '"/v1/admin/reconcile"',
            '"/v1/admin/reset"',
        ):
            self.assertIn(route, api)
        self.assertIn("require_authorization", api)
        self.assertIn(
            '"content_base64"', (ASSET / "registry.py").read_text(encoding="utf-8")
        )
        self.assertIn(
            '"content_base64"',
            (ASSET / "cloud_boundary.py").read_text(encoding="utf-8"),
        )
        self.assertIn("authorization: Authorization", api)
        self.assertIn("responses=API_ERROR_RESPONSES", api)
        cloud = (ASSET / "cloud_boundary.py").read_text(encoding="utf-8")
        for helper in (
            "def _download_export_blob",
            "def _write_export_file",
            "def _export_descriptor",
        ):
            self.assertIn(helper, cloud)


if __name__ == "__main__":
    unittest.main()
