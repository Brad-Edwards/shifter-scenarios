from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-context"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


security = load_module("platform_context_security_test", ASSET / "security.py")
store_module = load_module("platform_context_store_test", ASSET / "store.py")


class PlatformContextFoundationTests(unittest.TestCase):
    def test_source_compiles_and_contains_real_upstream_clients(self) -> None:
        for path in ASSET.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sync = (ASSET / "sync_worker.py").read_text(encoding="utf-8")
        upstreams = (ASSET / "upstreams.py").read_text(encoding="utf-8")
        for boundary in (
            "psycopg.connect",
            "OpenSearch(",
            "capture_retrieval_change",
            "AFTER INSERT OR UPDATE OR DELETE",
            "self.opensearch.index",
            "self.opensearch.delete",
        ):
            self.assertIn(boundary, sync)
        self.assertEqual(
            sync.count("to_char(created_at AT TIME ZONE 'UTC'"),
            2,
        )
        self.assertEqual(sync.count('YYYY-MM-DD\\"T\\"HH24:MI:SS.US\\"Z\\"'), 2)
        for endpoint in (
            "/issues.json",
            "/reset-password",
            "/sessions",
            "/logout",
            "/client-secret",
            "/protocol/openid-connect/token",
        ):
            self.assertIn(endpoint, upstreams)
        self.assertIn(
            'method = "POST" if existing.status_code == 404 else "PUT"',
            upstreams,
        )
        self.assertIn(
            "client.request(method, endpoint, headers=headers, json=body)", upstreams
        )
        for boundary in (
            "porcelain.clone(",
            "porcelain.push(",
            "username=self.owner",
            "password=token",
            'result["transport"] = "git-fallback"',
            "Git artifact readback did not match",
            "deleted Git artifact remained readable",
        ):
            self.assertIn(boundary, upstreams)
        self.assertNotIn("token@", upstreams)
        bootstrap = (PACK / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "chown -R 65532:65532 /var/lib/keplerops/data/platform-context",
            bootstrap,
        )

    def test_process_marker_and_repeated_literals_are_hardened(self) -> None:
        healthcheck = (ASSET / "healthcheck.py").read_text(encoding="utf-8")
        store = (ASSET / "store.py").read_text(encoding="utf-8")
        upstreams = (ASSET / "upstreams.py").read_text(encoding="utf-8")
        for boundary in (
            "os.O_NOFOLLOW",
            "os.fstat(descriptor)",
            "stat.S_ISREG(metadata.st_mode)",
            "metadata.st_uid != os.getuid()",
            "metadata.st_mode & 0o022",
        ):
            self.assertIn(boundary, healthcheck)
        self.assertIn("FILE_JOB_BY_ID_SQL", store)
        self.assertIn("SHA256_PREFIX", upstreams)

    def test_container_and_dependency_pins_are_exact(self) -> None:
        dockerfile = (ASSET / "Dockerfile").read_text(encoding="utf-8")
        requirements = (ASSET / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("python@sha256:", dockerfile)
        self.assertNotIn("python:", dockerfile)
        self.assertNotIn("--chown=65532:65532", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn("EXPOSE 8480", dockerfile)
        self.assertIn('CMD ["api"]', dockerfile)
        self.assertIn("healthcheck.py", dockerfile)
        self.assertIn("dulwich==0.24.10", requirements)
        self.assertIn("psycopg[binary]==3.3.4", requirements)
        for line in requirements.splitlines():
            if line.strip():
                self.assertIn("==", line)

    def test_versioned_config_is_narrow_and_complete(self) -> None:
        config = json.loads(
            (ASSET / "config/context-v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["schema_version"], 1)
        self.assertEqual(config["keycloak"]["tested_server_version"], "26.3.3")
        self.assertEqual(config["keycloak"]["admin_realm"], "keplerops")
        self.assertEqual(config["keycloak"]["target_realm"], "keplerops")
        self.assertEqual(
            set(config["file_roots"]), {"shared-context", "workhub-imports"}
        )

    def test_file_guard_accepts_regular_file_and_rejects_escape_and_symlink(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            root.mkdir()
            source = root / "context.txt"
            source.write_text("full reconstruction content", encoding="utf-8")
            descriptor, resolved, size = security.confined_file(
                root, "context.txt", 1024
            )
            try:
                self.assertEqual(
                    os.read(descriptor, size), b"full reconstruction content"
                )
            finally:
                os.close(descriptor)
            self.assertEqual(resolved, source)

            outside = base / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "escape.txt").symlink_to(outside)
            with self.assertRaises(ValueError):
                security.confined_file(root, "../outside.txt", 1024)
            with self.assertRaises(ValueError):
                security.confined_file(root, "escape.txt", 1024)

    def test_store_is_idempotent_and_reset_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = store_module.StateStore(Path(directory))
            request = {
                "job_id": "context-job-001",
                "root_id": "shared-context",
                "relative_path": "context.txt",
                "destination": "record",
                "destination_path": None,
            }
            first = store.enqueue_file_job(request)
            second = store.enqueue_file_job(request)
            self.assertEqual(first["job_id"], second["job_id"])
            store.advance_cursor("postgres-context-v1", 17)
            store.record_event(
                event_name="platform_context.test",
                operation="test",
                status="succeeded",
                request_id="context-job-001",
                request={"content": "full request"},
                response={"content": "full response"},
                source="focused-test",
                duration_ms=1.0,
            )
            store.reset()
            self.assertEqual(store.cursor("postgres-context-v1"), 0)
            self.assertEqual(store.recent_events(10), [])
            self.assertIsNone(store.file_job("context-job-001"))

    def test_api_requires_authorization_and_preserves_full_content_telemetry(
        self,
    ) -> None:
        api = (ASSET / "api.py").read_text(encoding="utf-8")
        worker = (ASSET / "file_worker.py").read_text(encoding="utf-8")
        for route in (
            '"/healthz"',
            '"/readyz"',
            '"/v1/files/imports"',
            '"/v1/workhub/conversations"',
            '"/v1/workhub/artifacts"',
            '"/v1/keycloak/password"',
            '"/v1/keycloak/logout"',
            '"/v1/keycloak/sessions"',
            '"/v1/keycloak/client-secret"',
            '"/v1/admin/events"',
            '"/v1/admin/reset"',
        ):
            self.assertIn(route, api)
        self.assertIn("require_authorization", api)
        self.assertIn('result["content_base64"]', worker)
        self.assertIn('result["content_text"]', worker)
        self.assertIn(
            '"request_digest"', (ASSET / "store.py").read_text(encoding="utf-8")
        )
        self.assertNotIn(
            '"client_secret": secret,\n            "credential_digest"', api
        )
        for contract in (
            "class ContextController",
            "_register_file_routes",
            "_register_workhub_conversation_routes",
            "_register_workhub_artifact_routes",
            "_register_identity_credential_routes",
            "_register_identity_session_routes",
            "responses=FILE_CREATE_RESPONSES",
            "responses=WORKHUB_RESPONSES",
            "responses=IDENTITY_RESPONSES",
        ):
            self.assertIn(contract, api)

    def test_foundation_has_no_scenario_progress_logic_or_parallel_deployment_spec(
        self,
    ) -> None:
        files = [path for path in ASSET.rglob("*") if path.is_file()]
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore") for path in files
        ).lower()
        for forbidden in (
            "challenge_id",
            "receipt_id",
            "ctfd",
            "atlas technique",
            "scoring",
            "service-manifest",
            "topology.yaml",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
