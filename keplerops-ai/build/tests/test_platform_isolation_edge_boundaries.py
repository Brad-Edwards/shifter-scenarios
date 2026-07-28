from __future__ import annotations

import base64
import importlib.util
import os
import pickle
import shutil
import sys
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from docker.errors import DockerException, NotFound
from fastapi.testclient import TestClient


PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-isolation"
IMPORT_ISOLATION_STATE = Path(tempfile.mkdtemp(prefix="keplerops-isolation-import-"))
IMPORT_EDGE_STATE = Path(tempfile.mkdtemp(prefix="keplerops-edge-import-"))
os.environ["ISOLATION_DATA_ROOT"] = str(IMPORT_ISOLATION_STATE)
os.environ["ISOLATION_ADMIN_TOKEN"] = "focused-isolation-token"
os.environ["EDGE_REGISTRY_DATA_ROOT"] = str(IMPORT_EDGE_STATE)
os.environ["EDGE_REGISTRY_ADMIN_TOKEN"] = "focused-edge-token"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ASSET))


def load_module(name: str, path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


isolation_app = load_module("platform_isolation_app", ASSET / "isolation_app.py")
edge_app = load_module("platform_edge_app", ASSET / "edge_app.py")
isolation_workers = sys.modules["isolation_workers"]

ISOLATION_ADMIN = {"X-Isolation-Admin-Token": "focused-isolation-token"}
EDGE_ADMIN = {"X-Edge-Registry-Token": "focused-edge-token"}


class FakeContainer:
    def __init__(
        self,
        container_id: str,
        image: str,
        command: list[str],
        labels: dict[str, str],
    ) -> None:
        self.id = container_id
        self.status = "created"
        self.attrs = {"Config": {"Image": image, "Labels": labels, "Cmd": command}}
        self.archive_names: list[str] = []
        self.restart_calls = 0
        self.removed = False

    def put_archive(self, _path: str, data: bytes) -> bool:
        with tarfile.open(fileobj=BytesIO(data), mode="r") as archive:
            self.archive_names = archive.getnames()
        return True

    def start(self) -> None:
        self.status = "exited"

    def wait(self, **_kwargs: Any) -> dict[str, int]:
        return {"StatusCode": 0}

    def reload(self) -> None:
        if self.removed:
            raise NotFound("removed")

    def logs(self, **_kwargs: Any) -> bytes:
        return b'{"has_predict":false,"object_type":"builtins.dict","schema_version":"1","status":"loaded"}\n'

    def restart(self, timeout: int) -> None:
        self.restart_calls += 1
        self.restart_timeout = timeout
        self.status = "exited"

    def kill(self) -> None:
        self.status = "exited"

    def remove(self, force: bool) -> None:
        self.remove_force = force
        self.removed = True


class FakeContainers:
    def __init__(self) -> None:
        self.created: dict[str, FakeContainer] = {}
        self.last_create: dict[str, Any] | None = None

    def create(self, image: str, command: list[str], **kwargs: Any) -> FakeContainer:
        self.last_create = {"image": image, "command": command, **kwargs}
        container_id = f"fake-loader-{len(self.created) + 1}"
        container = FakeContainer(container_id, image, command, kwargs["labels"])
        self.created[container_id] = container
        return container

    def get(self, container_id: str) -> FakeContainer:
        container = self.created.get(container_id)
        if container is None or container.removed:
            raise NotFound("missing")
        return container


class FakeDockerClient:
    def __init__(self, labelled: bool = True) -> None:
        self.containers = FakeContainers()
        self.labelled = labelled

    def info(self) -> dict[str, Any]:
        return {
            "ID": "focused-bounded-engine",
            "Name": "keplerops-bounded-workers",
            "ServerVersion": "29.6.1",
            "Labels": (
                ["keplerops.engine.role=bounded-workers"] if self.labelled else []
            ),
            "SecurityOptions": ["name=rootless"],
        }


class IsolationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="keplerops-isolation-")
        cls.root = Path(cls.temporary.name)
        cls.worker_client = FakeDockerClient()
        cls.app = isolation_app.create_app(cls.root, worker_client=cls.worker_client)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.temporary.cleanup()

    def setUp(self) -> None:
        response = self.client.post("/v1/admin/reset", headers=ISOLATION_ADMIN)
        self.assertEqual(response.status_code, 200, response.text)

    def _upload_artifact(self, artifact_id: str = "baseline-model") -> None:
        serialized = pickle.dumps({"model": "baseline"}, protocol=5)
        artifact_b64 = base64.b64encode(serialized).decode("ascii")
        upload = self.client.post(
            "/v1/artifacts",
            headers=ISOLATION_ADMIN,
            json={"artifact_id": artifact_id, "artifact_b64": artifact_b64},
        )
        self.assertEqual(upload.status_code, 201, upload.text)

    def _create_job(self) -> dict[str, Any]:
        self._upload_artifact()
        loaded = self.client.post(
            "/v1/artifacts/baseline-model/load", headers=ISOLATION_ADMIN
        )
        self.assertEqual(loaded.status_code, 201, loaded.text)
        return loaded.json()

    def test_readiness_requires_labelled_rootless_dedicated_engine(self) -> None:
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/readyz").status_code, 401)
        ready = self.client.get("/readyz", headers=ISOLATION_ADMIN)
        self.assertEqual(ready.status_code, 200, ready.text)
        self.assertTrue(ready.json()["engine"]["rootless"])
        self.assertEqual(
            ready.json()["engine"]["required_label"],
            "keplerops.engine.role=bounded-workers",
        )

        rejected = isolation_workers.LoaderWorkerController(
            self.app.state.store,
            "unix:///run/keplerops-isolation-engine/docker.sock",
            client=FakeDockerClient(labelled=False),
        )
        with self.assertRaises(isolation_workers.EngineRejected):
            rejected.engine_info()
        with self.assertRaises(isolation_workers.EngineRejected):
            isolation_workers.LoaderWorkerController(
                self.app.state.store,
                "unix:///var/run/docker.sock",
                client=FakeDockerClient(),
            )

    def test_openapi_documents_loader_error_responses(self) -> None:
        expected = {
            ("/readyz", "get"): {401, 503},
            ("/v1/admin/reset", "post"): {401, 503},
            ("/v1/artifacts", "post"): {401, 409, 413, 422},
            ("/v1/artifacts/{artifact_id}/load", "post"): {401, 404, 409, 503},
            ("/v1/jobs/{job_id}", "get"): {401, 404, 409, 503},
            ("/v1/jobs/{job_id}/restart", "post"): {401, 404, 409, 503},
            ("/v1/jobs/{job_id}", "delete"): {401, 404, 409, 503},
            ("/v1/events", "get"): {401},
        }
        paths = self.app.openapi()["paths"]
        for (path, method), statuses in expected.items():
            with self.subTest(path=path, method=method):
                documented = {int(code) for code in paths[path][method]["responses"]}
                self.assertTrue(statuses <= documented)

    def test_pickle_load_uses_fixed_networkless_mountless_container(self) -> None:
        job = self._create_job()
        self.assertEqual(job["state"], "exited")
        self.assertIn("builtins.dict", job["output"])
        created = self.worker_client.containers.last_create
        assert created is not None
        self.assertIn("@sha256:", created["image"])
        self.assertEqual(created["network_disabled"], True)
        self.assertEqual(created["read_only"], True)
        self.assertEqual(created["cap_drop"], ["ALL"])
        self.assertEqual(created["security_opt"], ["no-new-privileges:true"])
        self.assertEqual(created["pids_limit"], 32)
        self.assertEqual(created["mem_limit"], "128m")
        self.assertEqual(created["nano_cpus"], 250_000_000)
        self.assertEqual(created["working_dir"], "/run/keplerops-loader-job")
        self.assertEqual(
            created["tmpfs"]["/run/keplerops-loader-job"],
            "rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=0700",
        )
        self.assertNotIn("/tmp", created["tmpfs"])
        self.assertEqual(created["command"][-1], isolation_workers.INPUT_ARTIFACT)
        self.assertIn(isolation_workers.INPUT_DIRECTORY, created["tmpfs"])
        self.assertNotIn("volumes", created)
        self.assertNotIn("ports", created)
        self.assertNotIn("devices", created)
        container = self.worker_client.containers.created[job["container_id"]]
        self.assertEqual(container.archive_names, ["artifact.pkl"])
        self.assertIn("/input", created["tmpfs"])

        events = self.client.get("/v1/events", headers=ISOLATION_ADMIN).json()["events"]
        stored = next(
            event for event in events if event["event_type"] == "loader.artifact.stored"
        )
        self.assertIn("artifact_b64", stored["payload"])
        completed = next(
            event
            for event in events
            if event["event_type"] == "loader.execution.completed"
        )
        self.assertEqual(completed["payload"]["output"], job["output"])
        self.assertTrue(completed["payload"]["output_complete"])
        self.assertEqual(
            completed["payload"]["output_byte_count"], len(job["output"].encode())
        )

    def test_failed_loader_transfer_removes_container_and_marks_job_removed(
        self,
    ) -> None:
        self._upload_artifact("transfer-failure")
        with patch.object(FakeContainer, "put_archive", return_value=False):
            response = self.client.post(
                "/v1/artifacts/transfer-failure/load", headers=ISOLATION_ADMIN
            )
        self.assertEqual(response.status_code, 404, response.text)
        container = list(self.worker_client.containers.created.values())[-1]
        self.assertTrue(container.removed)
        with self.app.state.store.read() as connection:
            job = connection.execute(
                "SELECT state FROM loader_jobs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(job["state"], "removed")

    def test_failed_loader_start_removes_container_and_marks_job_removed(self) -> None:
        self._upload_artifact("start-failure")
        with patch.object(
            FakeContainer,
            "start",
            side_effect=DockerException("dedicated engine start failed"),
        ):
            response = self.client.post(
                "/v1/artifacts/start-failure/load", headers=ISOLATION_ADMIN
            )
        self.assertEqual(response.status_code, 503, response.text)
        container = list(self.worker_client.containers.created.values())[-1]
        self.assertTrue(container.removed)
        with self.app.state.store.read() as connection:
            job = connection.execute(
                "SELECT state FROM loader_jobs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(job["state"], "removed")

    def test_restart_ownership_guard_and_reset_cleanup(self) -> None:
        job = self._create_job()
        restarted = self.client.post(
            f"/v1/jobs/{job['job_id']}/restart", headers=ISOLATION_ADMIN
        )
        self.assertEqual(restarted.status_code, 200, restarted.text)
        self.assertEqual(restarted.json()["restart_count"], 1)

        container = self.worker_client.containers.created[job["container_id"]]
        container.attrs["Config"]["Labels"]["keplerops.loader-job"] = "foreign-job"
        refused = self.client.get(f"/v1/jobs/{job['job_id']}", headers=ISOLATION_ADMIN)
        self.assertEqual(refused.status_code, 409, refused.text)
        container.attrs["Config"]["Labels"]["keplerops.loader-job"] = job["job_id"]

        reset = self.client.post("/v1/admin/reset", headers=ISOLATION_ADMIN)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()["removed_jobs"], 1)
        events = self.client.get("/v1/events", headers=ISOLATION_ADMIN).json()["events"]
        self.assertEqual(
            [event["event_id"] for event in events], ["isolation-seed-0001"]
        )


class EdgeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="keplerops-edge-")
        cls.root = Path(cls.temporary.name)
        cls.app = edge_app.create_app(cls.root)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.temporary.cleanup()

    def setUp(self) -> None:
        response = self.client.post("/v1/admin/reset", headers=EDGE_ADMIN)
        self.assertEqual(response.status_code, 200, response.text)

    def _received_order(self, quantity: int = 1) -> None:
        created = self.client.post(
            "/v1/procurement/orders",
            headers=EDGE_ADMIN,
            json={
                "order_id": "edge-order-001",
                "vendor": "Range Appliance Vendor",
                "model": "Edge Accelerator A1",
                "quantity": quantity,
                "notes": "range-owned physical appliance request",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        for state in ("approved", "ordered", "received"):
            transitioned = self.client.post(
                "/v1/procurement/orders/edge-order-001/transition",
                headers=EDGE_ADMIN,
                json={"state": state},
            )
            self.assertEqual(transitioned.status_code, 200, transitioned.text)

    def _enrollment(self) -> dict[str, Any]:
        return {
            "device_id": "edge-device-001",
            "order_id": "edge-order-001",
            "manufacturer": "Range Appliance Vendor",
            "model": "Edge Accelerator A1",
            "serial_number": "RANGE-A1-0001",
            "inventory": {
                "reported_firmware": "1.2.3",
                "reported_interfaces": ["eth0"],
            },
            "claimed_capabilities": {"accelerator": "claimed", "memory_gib": 16},
            "attestation": {"format": "vendor-envelope", "payload": "full-content"},
        }

    def test_software_readiness_never_claims_physical_hardware(self) -> None:
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/readyz").status_code, 401)
        ready = self.client.get("/readyz", headers=EDGE_ADMIN)
        self.assertEqual(ready.status_code, 200, ready.text)
        self.assertEqual(ready.json()["registered_devices"], 0)
        self.assertEqual(ready.json()["verified_physical_accelerators"], 0)
        self.assertEqual(ready.json()["hardware_constraint"], "unsatisfied")

    def test_unknown_procurement_order_is_consistent_across_endpoints(self) -> None:
        responses = (
            self.client.get("/v1/procurement/orders/missing-order", headers=EDGE_ADMIN),
            self.client.post(
                "/v1/procurement/orders/missing-order/transition",
                headers=EDGE_ADMIN,
                json={"state": "approved"},
            ),
            self.client.post(
                "/v1/devices", headers=EDGE_ADMIN, json=self._enrollment()
            ),
        )
        for response in responses:
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(
                response.json()["detail"], edge_app.UNKNOWN_PROCUREMENT_ORDER
            )

    def test_openapi_documents_edge_registry_error_responses(self) -> None:
        expected = {
            ("/readyz", "get"): {401, 503},
            ("/v1/admin/reset", "post"): {401},
            ("/v1/procurement/orders", "post"): {401, 409, 413},
            ("/v1/procurement/orders/{order_id}/transition", "post"): {
                401,
                404,
                409,
            },
            ("/v1/procurement/orders/{order_id}", "get"): {401, 404},
            ("/v1/devices", "post"): {401, 404, 409, 413},
            ("/v1/devices/{device_id}/observations", "post"): {401, 404, 413},
            ("/v1/devices/{device_id}", "get"): {401, 404},
            ("/v1/events", "get"): {401},
        }
        paths = self.app.openapi()["paths"]
        for (path, method), statuses in expected.items():
            with self.subTest(path=path, method=method):
                documented = {int(code) for code in paths[path][method]["responses"]}
                self.assertTrue(statuses <= documented)

    def test_procurement_inventory_and_attestation_remain_unverified(self) -> None:
        self._received_order()
        enrollment = self._enrollment()
        created = self.client.post("/v1/devices", headers=EDGE_ADMIN, json=enrollment)
        self.assertEqual(created.status_code, 201, created.text)
        device = created.json()
        self.assertFalse(device["verified"])
        self.assertEqual(device["physical_presence_state"], "reported_unverified")
        self.assertEqual(device["capability_state"], "reported_unverified")
        self.assertEqual(device["attestation_state"], "received_unverified")
        self.assertEqual(device["inventory"], enrollment["inventory"])
        self.assertEqual(device["attestation"], enrollment["attestation"])

        observation = {
            "source": "range-intake-console",
            "inventory": {"reported_firmware": "1.2.4"},
            "claimed_capabilities": {"accelerator": "claimed"},
            "attestation": {
                "format": "vendor-envelope",
                "payload": "second-full-content",
            },
        }
        observed = self.client.post(
            "/v1/devices/edge-device-001/observations",
            headers=EDGE_ADMIN,
            json=observation,
        )
        self.assertEqual(observed.status_code, 201, observed.text)
        self.assertFalse(observed.json()["device"]["verified"])

        events = self.client.get("/v1/events", headers=EDGE_ADMIN).json()["events"]
        enrolled = next(
            event
            for event in events
            if event["event_type"] == "edge.device.enrolled_unverified"
        )
        self.assertEqual(enrolled["payload"]["request"], enrollment)
        observed_event = next(
            event
            for event in events
            if event["event_type"] == "edge.device.observed_unverified"
        )
        self.assertEqual(observed_event["payload"]["observation"], observation)

    def test_verified_input_and_impossible_transitions_are_rejected(self) -> None:
        self._received_order()
        invalid = {**self._enrollment(), "verified": True}
        response = self.client.post("/v1/devices", headers=EDGE_ADMIN, json=invalid)
        self.assertEqual(response.status_code, 422, response.text)
        transition = self.client.post(
            "/v1/procurement/orders/edge-order-001/transition",
            headers=EDGE_ADMIN,
            json={"state": "cancelled"},
        )
        self.assertEqual(transition.status_code, 409, transition.text)

    def test_reset_restores_zero_hardware_seed(self) -> None:
        self._received_order()
        created = self.client.post(
            "/v1/devices", headers=EDGE_ADMIN, json=self._enrollment()
        )
        self.assertEqual(created.status_code, 201, created.text)
        reset = self.client.post("/v1/admin/reset", headers=EDGE_ADMIN)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()["registered_devices"], 0)
        self.assertEqual(
            self.client.get(
                "/v1/devices/edge-device-001", headers=EDGE_ADMIN
            ).status_code,
            404,
        )
        events = self.client.get("/v1/events", headers=EDGE_ADMIN).json()["events"]
        self.assertEqual([event["event_id"] for event in events], ["edge-seed-0001"])


class PinnedProcessFamilyContractTests(unittest.TestCase):
    def test_opa_policy_lab_is_exactly_pinned_and_separate(self) -> None:
        dockerfile = (ASSET / "policy-lab/Dockerfile").read_text()
        authorization = (ASSET / "policy-lab/system-authz.rego").read_text()
        self.assertIn(
            "sha256:44f0f4b1c09260eaf5e24fc3931fe10f80cffd13054ef3ef62cef775d5cbd272",
            dockerfile,
        )
        self.assertIn("--authentication=token", dockerfile)
        self.assertIn("--authorization=basic", dockerfile)
        self.assertIn("policy-lab-client", authorization)
        self.assertNotIn("1.7.1", dockerfile)

    def test_k6_and_worker_engine_are_exactly_pinned_and_bounded(self) -> None:
        dockerfile = (ASSET / "k6/Dockerfile").read_text()
        client = (ASSET / "k6/client.js").read_text()
        engine = (ASSET / "worker-engine/Dockerfile").read_text()
        self.assertIn(
            "sha256:a33a0cfdc4d2483d6b7a3a22e726a499ff2831a671a49239104cd34a9937523c",
            dockerfile,
        )
        self.assertIn("requestedRate > 5", client)
        self.assertIn("requestedSeconds > 60", client)
        self.assertIn("requestedVUs > 10", client)
        self.assertIn("export default function boundedClient()", client)
        self.assertIn("NOSONAR -- range-local test service", client)
        self.assertIn(r":\d{1,5}", client)
        self.assertNotIn(":[0-9]{1,5}", client)
        self.assertIn("K6_NO_USAGE_REPORT=true", dockerfile)
        self.assertIn(
            "K6_LOG_OUTPUT=file=/var/lib/keplerops-k6/responses.ndjson", dockerfile
        )
        self.assertIn("K6_LOG_FORMAT=raw", dockerfile)
        self.assertIn(
            "sha256:371962f4344295a1eb185f1c9e62064bf4503a7beb8c6e73be3405500041784b",
            engine,
        )
        self.assertIn("keplerops.engine.role=bounded-workers", engine)
        self.assertNotIn("2375", engine)
        self.assertNotIn("2376", engine)


class RuntimeTokenFileTests(unittest.TestCase):
    def test_controller_token_files_override_direct_values(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="keplerops-isolation-token-files-"
        ) as temporary:
            temporary_root = Path(temporary)
            isolation_file = temporary_root / "isolation.token"
            edge_file = temporary_root / "edge.token"
            isolation_file.write_text("file-isolation-token\r\n", encoding="utf-8")
            edge_file.write_text("file-edge-token\n", encoding="utf-8")
            environment = {
                "ISOLATION_ADMIN_TOKEN_FILE": str(isolation_file),
                "ISOLATION_ADMIN_TOKEN": "ignored-isolation-token",
                "EDGE_REGISTRY_ADMIN_TOKEN_FILE": str(edge_file),
                "EDGE_REGISTRY_ADMIN_TOKEN": "ignored-edge-token",
            }
            with patch.dict(os.environ, environment, clear=False):
                isolation = isolation_app.create_app(
                    temporary_root / "isolation", worker_client=FakeDockerClient()
                )
                edge = edge_app.create_app(temporary_root / "edge")
                with (
                    TestClient(isolation) as isolation_client,
                    TestClient(edge) as edge_client,
                ):
                    self.assertEqual(
                        isolation_client.get(
                            "/readyz",
                            headers={"X-Isolation-Admin-Token": "file-isolation-token"},
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        isolation_client.get(
                            "/readyz",
                            headers={
                                "X-Isolation-Admin-Token": "ignored-isolation-token"
                            },
                        ).status_code,
                        401,
                    )
                    self.assertEqual(
                        edge_client.get(
                            "/readyz",
                            headers={"X-Edge-Registry-Token": "file-edge-token"},
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        edge_client.get(
                            "/readyz",
                            headers={"X-Edge-Registry-Token": "ignored-edge-token"},
                        ).status_code,
                        401,
                    )

    def test_controller_token_files_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="keplerops-isolation-token-invalid-"
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
            factories = (
                (
                    "ISOLATION_ADMIN_TOKEN_FILE",
                    lambda root: isolation_app.create_app(
                        root, worker_client=FakeDockerClient()
                    ),
                ),
                ("EDGE_REGISTRY_ADMIN_TOKEN_FILE", edge_app.create_app),
            )
            for variable, factory in factories:
                for configured_path in invalid_paths:
                    with (
                        self.subTest(
                            variable=variable, configured_path=configured_path
                        ),
                        patch.dict(
                            os.environ, {variable: configured_path}, clear=False
                        ),
                    ):
                        with self.assertRaises(RuntimeError):
                            factory(temporary_root / f"state-{variable.lower()}")

    def test_synthetic_defaults_are_used_only_without_file_variables(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                isolation_app._configured_token(
                    file_variable="ISOLATION_ADMIN_TOKEN_FILE",
                    value_variable="ISOLATION_ADMIN_TOKEN",
                    synthetic_default=isolation_app.DEFAULT_ADMIN_TOKEN,
                ),
                isolation_app.DEFAULT_ADMIN_TOKEN,
            )
            self.assertEqual(
                edge_app._configured_token(
                    file_variable="EDGE_REGISTRY_ADMIN_TOKEN_FILE",
                    value_variable="EDGE_REGISTRY_ADMIN_TOKEN",
                    synthetic_default=edge_app.DEFAULT_ADMIN_TOKEN,
                ),
                edge_app.DEFAULT_ADMIN_TOKEN,
            )


def tearDownModule() -> None:
    shutil.rmtree(IMPORT_ISOLATION_STATE, ignore_errors=True)
    shutil.rmtree(IMPORT_EDGE_STATE, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
