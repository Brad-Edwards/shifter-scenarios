from __future__ import annotations

import hashlib
import base64
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
from docker.errors import ImageNotFound, NotFound
from fastapi.testclient import TestClient


PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-agent"
IMPORT_STATE = Path(tempfile.mkdtemp(prefix="keplerops-platform-agent-import-"))
os.environ["PLATFORM_AGENT_DATA_ROOT"] = str(IMPORT_STATE)
os.environ["PLATFORM_AGENT_ADMIN_TOKEN"] = "focused-agent-admin-token"
os.environ["PLATFORM_AGENT_SEED_TOKEN"] = "focused-agent-identity-token"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ASSET))
SPEC = importlib.util.spec_from_file_location("platform_agent_app", ASSET / "app.py")
assert SPEC is not None and SPEC.loader is not None
platform_agent = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = platform_agent
SPEC.loader.exec_module(platform_agent)


ADMIN = {"X-Platform-Admin-Token": "focused-agent-admin-token"}
AGENT = {
    "X-Agent-Id": "platform-agent-alpha",
    "X-Agent-Token": "focused-agent-identity-token",
}


class FakeContainer:
    def __init__(
        self, container_id: str, image: str, labels: dict[str, str], command: list[str]
    ) -> None:
        self.id = container_id
        self.status = "running"
        self.attrs = {"Config": {"Image": image, "Labels": labels, "Cmd": command}}
        self.restart_calls = 0
        self.removed = False

    def reload(self) -> None:
        if self.removed:
            raise NotFound("removed")

    def logs(self, **_kwargs: Any) -> bytes:
        return b'{"schema_version":"1","status":"processed"}\n'

    def restart(self, timeout: int) -> None:
        self.restart_calls += 1
        self.status = "running"
        self.restart_timeout = timeout

    def remove(self, force: bool) -> None:
        self.removed = True
        self.remove_force = force


class FakeContainers:
    def __init__(self) -> None:
        self.created: dict[str, FakeContainer] = {}
        self.last_run: dict[str, Any] | None = None

    def run(self, image: str, command: list[str], **kwargs: Any) -> FakeContainer:
        self.last_run = {"image": image, "command": command, **kwargs}
        container_id = f"fake-container-{len(self.created) + 1}"
        container = FakeContainer(container_id, image, kwargs["labels"], command)
        self.created[container_id] = container
        return container

    def get(self, container_id: str) -> FakeContainer:
        container = self.created.get(container_id)
        if container is None or container.removed:
            raise NotFound("missing")
        return container


class FakeImages:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.requested: list[str] = []

    def get(self, image_ref: str) -> dict[str, str]:
        self.requested.append(image_ref)
        if not self.available:
            raise ImageNotFound("missing")
        return {"image_ref": image_ref}


class FakeDockerClient:
    def __init__(
        self,
        *,
        labelled: bool = True,
        rootless: bool = True,
        image_available: bool = True,
    ) -> None:
        self.containers = FakeContainers()
        self.images = FakeImages(image_available)
        self.labelled = labelled
        self.rootless = rootless

    def info(self) -> dict[str, Any]:
        return {
            "ID": "focused-bounded-engine",
            "Name": "keplerops-bounded-workers",
            "ServerVersion": "29.6.1",
            "Labels": (
                ["keplerops.engine.role=bounded-workers"] if self.labelled else []
            ),
            "SecurityOptions": ["name=rootless"] if self.rootless else [],
        }


class PlatformAgentFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="keplerops-platform-agent-")
        cls.root = Path(cls.temporary.name)
        cls.diagnostic_requests: list[httpx.Request] = []

        def diagnostic_handler(request: httpx.Request) -> httpx.Response:
            cls.diagnostic_requests.append(request)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"status": "diagnostic-ok", "source": "range-local"},
            )

        cls.worker_client = FakeDockerClient()
        cls.app = platform_agent.create_app(
            cls.root,
            diagnostic_transport=httpx.MockTransport(diagnostic_handler),
            worker_client=cls.worker_client,
        )
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.temporary.cleanup()
        shutil.rmtree(IMPORT_STATE, ignore_errors=True)

    def setUp(self) -> None:
        response = self.client.post("/v1/admin/reset", headers=ADMIN)
        self.assertEqual(response.status_code, 200, response.text)
        self.diagnostic_requests.clear()

    def test_health_identity_configuration_and_versioned_tool_registry(self) -> None:
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        readiness = self.client.get("/readyz")
        self.assertEqual(readiness.status_code, 200, readiness.text)
        self.assertEqual(readiness.json()["agent_runtime"], "langgraph-local")
        self.assertEqual(readiness.json()["schema_version"], "1")

        identity = self.client.get("/v1/identities/platform-agent-alpha", headers=AGENT)
        self.assertEqual(identity.status_code, 200, identity.text)
        self.assertEqual(identity.json()["identity_version"], "1.0.0")
        self.assertEqual(identity.json()["active_config_version"], "1.0.0")

        registry = self.client.get("/v1/tools", headers=AGENT).json()
        refs = {f"{tool['tool_name']}@{tool['version']}" for tool in registry["tools"]}
        self.assertEqual(
            refs,
            {"hash_text@1.0.0", "query_json@1.0.0", "identity_metadata@1.0.0"},
        )
        self.assertTrue(
            all(tool["input_schema"]["type"] == "object" for tool in registry["tools"])
        )

        capabilities = self.client.get("/v1/workers/capabilities", headers=ADMIN).json()
        self.assertTrue(capabilities["available"])
        self.assertEqual(
            capabilities["socket"], "unix:///run/keplerops-worker/docker.sock"
        )
        self.assertEqual(
            capabilities["engine"]["required_label"],
            "keplerops.engine.role=bounded-workers",
        )
        self.assertTrue(capabilities["engine"]["rootless"])
        self.assertTrue(capabilities["engine"]["worker_image_preloaded"])

    def test_openapi_documents_control_plane_error_responses(self) -> None:
        expected = {
            ("/readyz", "get"): {503},
            ("/v1/admin/reset", "post"): {401, 503},
            ("/v1/identities/{agent_id}", "get"): {401, 404},
            ("/v1/tools", "get"): {401},
            ("/v1/configurations/active", "get"): {401, 404},
            ("/v1/configurations", "post"): {401, 404, 409, 422},
            ("/v1/configurations/{version}/activate", "post"): {401, 404},
            ("/v1/agent/runs", "post"): {401, 409, 422},
            ("/v1/relay/events", "post"): {401, 409, 413},
            ("/v1/diagnostics/resources/{resource_id}", "put"): {401, 422},
            ("/v1/diagnostics/{resource_id}", "get"): {401, 404, 502},
            ("/v1/exports", "post"): {401, 409, 413},
            ("/v1/workers/capabilities", "get"): {401},
            ("/v1/workers", "post"): {401, 422, 503},
            ("/v1/workers/{worker_id}", "get"): {401, 404, 409, 503},
            ("/v1/workers/{worker_id}/restart", "post"): {401, 404, 409, 503},
            ("/v1/workers/{worker_id}", "delete"): {401, 404, 409, 503},
            ("/v1/events", "get"): {401},
        }
        paths = self.app.openapi()["paths"]
        for (path, method), statuses in expected.items():
            with self.subTest(path=path, method=method):
                documented = {int(code) for code in paths[path][method]["responses"]}
                self.assertTrue(statuses <= documented)

    def test_real_langgraph_runtime_executes_only_bounded_registered_tools(
        self,
    ) -> None:
        request = {
            "plan": [
                {"tool": "identity_metadata@1.0.0", "arguments": {}},
                {"tool": "hash_text@1.0.0", "arguments": {"text": "range-local"}},
                {
                    "tool": "query_json@1.0.0",
                    "arguments": {
                        "expression": "services[?ready].name | [0]",
                        "document": {
                            "services": [
                                {"name": "inference", "ready": True},
                                {"name": "worker", "ready": False},
                            ]
                        },
                    },
                },
            ]
        }
        response = self.client.post("/v1/agent/runs", headers=AGENT, json=request)
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["runtime_kind"], "langgraph-local")
        self.assertEqual(len(result["outputs"]), 3)
        expected = "sha256:" + hashlib.sha256(b"range-local").hexdigest()
        self.assertEqual(result["outputs"][1]["result"]["digest"], expected)
        self.assertEqual(result["outputs"][2]["result"]["value"], "inference")

        events = self.client.get("/v1/events", headers=ADMIN).json()["events"]
        event_types = {event["event_type"] for event in events}
        self.assertIn("agent.run.completed", event_types)
        self.assertIn("agent.tool.completed", event_types)

    def test_unregistered_tool_is_rejected_before_execution(self) -> None:
        response = self.client.post(
            "/v1/agent/runs",
            headers=AGENT,
            json={"plan": [{"tool": "shell_command@1.0.0", "arguments": {}}]},
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("not allowed", response.json()["detail"])
        with self.app.state.store.read() as connection:
            row = connection.execute(
                "SELECT status FROM agent_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row["status"], "rejected")

    def test_configuration_versions_are_immutable_and_explicitly_activated(
        self,
    ) -> None:
        configuration = {
            "agent_id": "platform-agent-alpha",
            "version": "1.1.0",
            "max_steps": 2,
            "tool_timeout_ms": 750,
            "allowed_tools": ["hash_text@1.0.0"],
            "worker_profile": "disposable-linux-v1",
        }
        created = self.client.post(
            "/v1/configurations", headers=ADMIN, json=configuration
        )
        self.assertEqual(created.status_code, 201, created.text)
        duplicate = self.client.post(
            "/v1/configurations", headers=ADMIN, json=configuration
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        activated = self.client.post(
            "/v1/configurations/1.1.0/activate",
            headers=ADMIN,
            params={"agent_id": "platform-agent-alpha"},
        )
        self.assertEqual(activated.status_code, 200, activated.text)
        current = self.client.get("/v1/configurations/active", headers=AGENT).json()
        self.assertEqual(current["version"], "1.1.0")
        self.assertEqual(current["allowed_tools"], ["hash_text@1.0.0"])

    def test_relay_sink_persists_ordered_authenticated_events(self) -> None:
        event = {
            "event_id": "relay-event-001",
            "channel": "heartbeat",
            "sequence": 1,
            "payload": {"state": "ready", "generation": 1},
        }
        accepted = self.client.post("/v1/relay/events", headers=AGENT, json=event)
        self.assertEqual(accepted.status_code, 202, accepted.text)
        self.assertTrue(accepted.json()["accepted"])
        duplicate = self.client.post("/v1/relay/events", headers=AGENT, json=event)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        unauthenticated = self.client.post("/v1/relay/events", json=event)
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)

    def test_diagnostic_proxy_uses_named_range_local_targets_and_strips_headers(
        self,
    ) -> None:
        external = self.client.put(
            "/v1/diagnostics/resources/external-resource",
            headers=ADMIN,
            json={"url": "https://example.com/metadata", "max_bytes": 1024},
        )
        self.assertEqual(external.status_code, 422, external.text)
        fetched = self.client.get(
            "/v1/diagnostics/local-health",
            headers={**AGENT, "Authorization": "Bearer must-not-forward"},
        )
        self.assertEqual(fetched.status_code, 200, fetched.text)
        body = fetched.json()
        self.assertEqual(body["status_code"], 200)
        decoded = json.loads(base64.b64decode(body["body_base64"]))
        self.assertEqual(decoded["status"], "diagnostic-ok")
        self.assertEqual(len(self.diagnostic_requests), 1)
        outbound = self.diagnostic_requests[0]
        self.assertNotIn("authorization", outbound.headers)
        self.assertEqual(outbound.url.host, "127.0.0.1")

    def test_contained_export_is_durable_and_reset_restores_seed_state(self) -> None:
        exported = self.client.post(
            "/v1/exports",
            headers=AGENT,
            json={
                "export_id": "export-event-001",
                "media_type": "application/json",
                "payload": {"kind": "telemetry", "records": [1, 2, 3]},
            },
        )
        self.assertEqual(exported.status_code, 201, exported.text)
        export_path = self.root / "exports/export-event-001.json"
        self.assertTrue(export_path.is_file())
        self.assertEqual(
            json.loads(export_path.read_text()),
            {"kind": "telemetry", "records": [1, 2, 3]},
        )

        reset = self.client.post("/v1/admin/reset", headers=ADMIN)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertFalse(export_path.exists())
        current = self.client.get("/v1/configurations/active", headers=AGENT).json()
        self.assertEqual(current["version"], "1.0.0")
        events = self.client.get("/v1/events", headers=ADMIN).json()["events"]
        self.assertEqual([event["event_type"] for event in events], ["platform.seeded"])

    def test_disposable_worker_and_supervised_restart_enforce_fixed_isolation(
        self,
    ) -> None:
        created = self.client.post(
            "/v1/workers", headers=ADMIN, json={"job": {"kind": "metadata", "items": 2}}
        )
        self.assertEqual(created.status_code, 201, created.text)
        worker = created.json()
        invocation = self.worker_client.containers.last_run
        assert invocation is not None
        self.assertEqual(
            invocation["image"],
            "python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689",
        )
        self.assertTrue(invocation["network_disabled"])
        self.assertTrue(invocation["read_only"])
        self.assertEqual(invocation["cap_drop"], ["ALL"])
        self.assertEqual(invocation["security_opt"], ["no-new-privileges:true"])
        self.assertEqual(invocation["pids_limit"], 32)
        self.assertEqual(invocation["mem_limit"], "128m")
        self.assertEqual(invocation["user"], "65532:65532")
        self.assertEqual(invocation["working_dir"], "/run/keplerops-worker-job")
        self.assertEqual(
            invocation["tmpfs"],
            {
                "/run/keplerops-worker-job": (
                    "rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=0700"
                )
            },
        )
        self.assertEqual(invocation["volumes"], {})
        self.assertEqual(invocation["mounts"], [])
        self.assertEqual(invocation["ports"], {})
        self.assertEqual(invocation["devices"], [])
        self.assertEqual(invocation["device_requests"], [])
        self.assertFalse(invocation["privileged"])
        self.assertNotIn("DOCKER_HOST", invocation["environment"])
        self.assertNotIn("docker.sock", json.dumps(invocation["environment"]))

        restarted = self.client.post(
            f"/v1/workers/{worker['worker_id']}/restart", headers=ADMIN
        )
        self.assertEqual(restarted.status_code, 200, restarted.text)
        self.assertEqual(restarted.json()["restart_count"], 1)
        container = self.worker_client.containers.created[worker["container_id"]]
        self.assertEqual(container.restart_calls, 1)

        container.attrs["Config"]["Labels"]["keplerops.platform-agent.worker"] = "false"
        refused = self.client.get(f"/v1/workers/{worker['worker_id']}", headers=ADMIN)
        self.assertEqual(refused.status_code, 409, refused.text)
        container.attrs["Config"]["Labels"]["keplerops.platform-agent.worker"] = "true"
        removed = self.client.delete(
            f"/v1/workers/{worker['worker_id']}", headers=ADMIN
        )
        self.assertEqual(removed.status_code, 200, removed.text)

    def test_worker_engine_refuses_host_tcp_unlabelled_nonrootless_and_unloaded(
        self,
    ) -> None:
        for socket in (
            "unix:///var/run/docker.sock",
            "unix:///run/docker.sock",
            "tcp://127.0.0.1:2375",
            "unix:///run/keplerops-worker/alternate.sock",
        ):
            with self.subTest(socket=socket), self.assertRaises(ValueError):
                platform_agent.DockerWorkerController(
                    self.app.state.store,
                    base_url=socket,
                    client=FakeDockerClient(),
                )

        configurations = (
            (FakeDockerClient(labelled=False), "daemon label"),
            (FakeDockerClient(rootless=False), "not rootless"),
            (FakeDockerClient(image_available=False), "not preloaded"),
        )
        for worker_client, expected in configurations:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory(
                    prefix="keplerops-platform-engine-rejection-"
                ) as temporary:
                    app = platform_agent.create_app(
                        Path(temporary), worker_client=worker_client
                    )
                    with TestClient(app) as client:
                        self.assertEqual(client.get("/healthz").status_code, 200)
                        readiness = client.get("/readyz")
                        self.assertEqual(readiness.status_code, 503, readiness.text)
                        capabilities = client.get(
                            "/v1/workers/capabilities", headers=ADMIN
                        ).json()
                        self.assertFalse(capabilities["available"])
                        self.assertIn(expected, capabilities["error"])
                        reset = client.post("/v1/admin/reset", headers=ADMIN)
                        self.assertEqual(reset.status_code, 200, reset.text)
                        self.assertEqual(reset.json()["removed_workers"], 0)

    def test_reset_removes_owned_workers_before_restoring_seed(self) -> None:
        created = self.client.post(
            "/v1/workers", headers=ADMIN, json={"job": {"kind": "reset-check"}}
        )
        self.assertEqual(created.status_code, 201, created.text)
        container = self.worker_client.containers.created[
            created.json()["container_id"]
        ]
        reset = self.client.post("/v1/admin/reset", headers=ADMIN)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()["removed_workers"], 1)
        self.assertTrue(container.removed)
        with self.app.state.store.read() as connection:
            workers = connection.execute("SELECT COUNT(*) FROM worker_jobs").fetchone()[
                0
            ]
        self.assertEqual(workers, 0)
        events = self.client.get("/v1/events", headers=ADMIN).json()["events"]
        self.assertEqual([event["event_type"] for event in events], ["platform.seeded"])

    def test_reset_preserves_state_when_engine_ownership_cannot_be_verified(
        self,
    ) -> None:
        created = self.client.post(
            "/v1/workers", headers=ADMIN, json={"job": {"kind": "reset-guard"}}
        )
        self.assertEqual(created.status_code, 201, created.text)
        container = self.worker_client.containers.created[
            created.json()["container_id"]
        ]
        self.worker_client.labelled = False
        refused = self.client.post("/v1/admin/reset", headers=ADMIN)
        self.assertEqual(refused.status_code, 503, refused.text)
        self.assertFalse(container.removed)
        with self.app.state.store.read() as connection:
            workers = connection.execute("SELECT COUNT(*) FROM worker_jobs").fetchone()[
                0
            ]
        self.assertEqual(workers, 1)

        self.worker_client.labelled = True
        recovered = self.client.post("/v1/admin/reset", headers=ADMIN)
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()["removed_workers"], 1)

    def test_container_contract_pins_socket_and_worker_image(self) -> None:
        dockerfile = (ASSET / "Dockerfile").read_text()
        self.assertIn(
            "PLATFORM_AGENT_DOCKER_SOCKET=unix:///run/keplerops-worker/docker.sock",
            dockerfile,
        )
        self.assertIn(
            "PLATFORM_AGENT_WORKER_IMAGE=python@sha256:"
            "5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689",
            dockerfile,
        )

    def test_runtime_token_files_override_values_and_trim_one_line_ending(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="keplerops-platform-token-files-"
        ) as temporary:
            temporary_root = Path(temporary)
            admin_file = temporary_root / "admin.token"
            seed_file = temporary_root / "seed.token"
            admin_file.write_text("file-agent-admin\r\n", encoding="utf-8")
            seed_file.write_text("file-agent-seed\n", encoding="utf-8")
            environment = {
                "PLATFORM_AGENT_ADMIN_TOKEN_FILE": str(admin_file),
                "PLATFORM_AGENT_ADMIN_TOKEN": "ignored-direct-admin",
                "PLATFORM_AGENT_SEED_TOKEN_FILE": str(seed_file),
                "PLATFORM_AGENT_SEED_TOKEN": "ignored-direct-seed",
            }
            with patch.dict(os.environ, environment, clear=False):
                application = platform_agent.create_app(
                    temporary_root / "state", worker_client=FakeDockerClient()
                )
                with TestClient(application) as client:
                    self.assertEqual(
                        client.post(
                            "/v1/admin/reset",
                            headers={"X-Platform-Admin-Token": "file-agent-admin"},
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        client.post(
                            "/v1/admin/reset",
                            headers={"X-Platform-Admin-Token": "ignored-direct-admin"},
                        ).status_code,
                        401,
                    )
                    self.assertEqual(
                        client.get(
                            "/v1/configurations/active",
                            headers={
                                "X-Agent-Id": "platform-agent-alpha",
                                "X-Agent-Token": "file-agent-seed",
                            },
                        ).status_code,
                        200,
                    )

            seed_file.write_text("line-one\n\n", encoding="utf-8")
            with patch.dict(os.environ, environment, clear=False):
                self.assertEqual(
                    platform_agent._configured_token(
                        file_variable="PLATFORM_AGENT_SEED_TOKEN_FILE",
                        value_variable="PLATFORM_AGENT_SEED_TOKEN",
                        synthetic_default=platform_agent.DEFAULT_AGENT_TOKEN,
                    ),
                    "line-one\n",
                )

    def test_runtime_token_files_fail_closed_and_defaults_require_no_file_env(
        self,
    ) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                platform_agent._configured_token(
                    file_variable="PLATFORM_AGENT_ADMIN_TOKEN_FILE",
                    value_variable="PLATFORM_AGENT_ADMIN_TOKEN",
                    synthetic_default=platform_agent.DEFAULT_ADMIN_TOKEN,
                ),
                platform_agent.DEFAULT_ADMIN_TOKEN,
            )
        with tempfile.TemporaryDirectory(
            prefix="keplerops-platform-token-invalid-"
        ) as temporary:
            temporary_root = Path(temporary)
            empty_file = temporary_root / "empty.token"
            empty_file.write_text("\n", encoding="utf-8")
            invalid_paths = (
                "",
                str(temporary_root / "missing.token"),
                str(empty_file),
                str(temporary_root),
            )
            for configured_path in invalid_paths:
                with (
                    self.subTest(configured_path=configured_path),
                    patch.dict(
                        os.environ,
                        {"PLATFORM_AGENT_ADMIN_TOKEN_FILE": configured_path},
                        clear=False,
                    ),
                ):
                    with self.assertRaises(RuntimeError):
                        platform_agent.create_app(
                            temporary_root / "state", worker_client=FakeDockerClient()
                        )

    def test_asset_contains_no_challenge_or_proof_semantics(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ASSET.rglob("*")
            if path.is_file()
        )
        for forbidden in ("flag-", "receipt", "proof predicate", "AML.T", "kep-m"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
