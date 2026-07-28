"""Dedicated-engine controller for bounded unsafe-serialization workers."""

from __future__ import annotations

import io
import tarfile
import uuid
from typing import Any

import docker
from docker.errors import APIError, DockerException, NotFound
from requests.exceptions import Timeout

from isolation_state import IsolationStore, canonical_json, now


DEFAULT_WORKER_IMAGE = (
    "python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689"
)
REQUIRED_ENGINE_LABEL = "keplerops.engine.role=bounded-workers"
WORKER_LABEL = "keplerops.platform-isolation.loader"
MAX_OUTPUT_BYTES = 1_048_576
MAX_RUNTIME_SECONDS = 5
WORKER_SCRATCH = "/run/keplerops-loader-job"
INPUT_DIRECTORY = "/input"
INPUT_ARTIFACT = f"{INPUT_DIRECTORY}/artifact.pkl"
WORKER_PROGRAM = """\
import json
import pickle
import sys
import time

artifact_path = sys.argv[1]
deadline = time.monotonic() + 4
while not __import__("os").path.exists(artifact_path) and time.monotonic() < deadline:
    time.sleep(0.05)
with open(artifact_path, "rb") as artifact:
    loaded = pickle.load(artifact)
result = {
    "schema_version": "1",
    "status": "loaded",
    "object_type": type(loaded).__module__ + "." + type(loaded).__qualname__,
    "has_predict": callable(getattr(loaded, "predict", None)),
}
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


class IsolationWorkerError(RuntimeError):
    pass


class EngineRejected(IsolationWorkerError):
    pass


class EngineUnavailable(IsolationWorkerError):
    pass


class WorkerOwnershipError(IsolationWorkerError):
    pass


class LoaderWorkerController:
    def __init__(
        self,
        store: IsolationStore,
        base_url: str,
        image_ref: str = DEFAULT_WORKER_IMAGE,
        client: docker.DockerClient | None = None,
    ) -> None:
        if not base_url.startswith("unix:///run/keplerops-isolation-engine/"):
            raise EngineRejected(
                "only the dedicated /run/keplerops-isolation-engine Unix socket is allowed"
            )
        if base_url in {
            "unix:///var/run/docker.sock",
            "unix:///run/docker.sock",
            "unix:///run/containerd/containerd.sock",
        }:
            raise EngineRejected(
                "host and general-purpose engine sockets are forbidden"
            )
        if "@sha256:" not in image_ref:
            raise EngineRejected("loader worker image must be pinned by sha256 digest")
        self.store = store
        self.base_url = base_url
        self.image_ref = image_ref
        self._client_cache = client

    def _client(self) -> docker.DockerClient:
        if self._client_cache is None:
            try:
                self._client_cache = docker.DockerClient(
                    base_url=self.base_url, version="auto", timeout=8
                )
            except DockerException as exc:
                raise EngineUnavailable(
                    "dedicated loader engine is unavailable"
                ) from exc
        return self._client_cache

    @staticmethod
    def _labels(info: dict[str, Any]) -> set[str]:
        labels = info.get("Labels") or []
        if isinstance(labels, dict):
            return {f"{key}={value}" for key, value in labels.items()}
        return {str(label) for label in labels}

    def engine_info(self) -> dict[str, Any]:
        try:
            info = self._client().info()
        except (APIError, DockerException) as exc:
            raise EngineUnavailable("dedicated loader engine is unavailable") from exc
        labels = self._labels(info)
        if REQUIRED_ENGINE_LABEL not in labels:
            raise EngineRejected(
                "engine is missing the required bounded-workers daemon label"
            )
        security_options = [str(value) for value in info.get("SecurityOptions") or []]
        return {
            "engine_id": info.get("ID"),
            "name": info.get("Name"),
            "server_version": info.get("ServerVersion"),
            "required_label": REQUIRED_ENGINE_LABEL,
            "rootless": any("rootless" in value for value in security_options),
            "security_options": security_options,
        }

    @staticmethod
    def _artifact_tar(content: bytes) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            item = tarfile.TarInfo("artifact.pkl")
            item.size = len(content)
            item.mode = 0o400
            item.uid = 65532
            item.gid = 65532
            archive.addfile(item, io.BytesIO(content))
        return buffer.getvalue()

    def _owned(self, job_id: str) -> tuple[Any, Any]:
        row = self.store.job(job_id)
        if row is None:
            raise IsolationWorkerError("unknown loader job")
        if row["state"] == "removed":
            raise IsolationWorkerError("loader job was removed")
        self.engine_info()
        try:
            container = self._client().containers.get(row["container_id"])
            container.reload()
        except NotFound as exc:
            raise IsolationWorkerError("loader container no longer exists") from exc
        except (APIError, DockerException) as exc:
            raise EngineUnavailable("dedicated loader engine lookup failed") from exc
        config = container.attrs.get("Config", {})
        labels = config.get("Labels") or {}
        if (
            labels.get(WORKER_LABEL) != "true"
            or labels.get("keplerops.loader-job") != job_id
            or config.get("Image") != row["image_ref"]
            or row["image_ref"] != self.image_ref
        ):
            raise WorkerOwnershipError("loader container ownership verification failed")
        return row, container

    def _wait(self, container: Any) -> tuple[str, int | None, str, int, bool, bool]:
        timed_out = False
        try:
            result = container.wait(
                timeout=MAX_RUNTIME_SECONDS, condition="not-running"
            )
            exit_code = int(result.get("StatusCode", -1))
        except Timeout:
            container.kill()
            container.wait(timeout=2, condition="not-running")
            exit_code = None
            timed_out = True
        container.reload()
        raw_output = container.logs(stdout=True, stderr=True)
        observed_bytes = len(raw_output)
        output_complete = observed_bytes <= MAX_OUTPUT_BYTES
        output = raw_output[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        state = "timed_out" if timed_out else "exited"
        return state, exit_code, output, observed_bytes, output_complete, timed_out

    def _reconcile_failed_create(
        self, container: Any | None, job_id: str, job_recorded: bool
    ) -> None:
        removed = False
        if container is not None:
            try:
                container.remove(force=True)
                removed = True
            except (APIError, DockerException):
                pass
        if job_recorded:
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE loader_jobs SET state=?, updated_at=? WHERE job_id=?",
                    ("removed" if removed else "unknown", now(), job_id),
                )

    def create_and_run(self, artifact_id: str) -> dict[str, Any]:
        self.engine_info()
        artifact = self.store.artifact(artifact_id)
        if artifact is None:
            raise IsolationWorkerError("unknown artifact")
        content = (self.store.artifact_root / artifact["storage_name"]).read_bytes()
        job_id = f"loader-job-{uuid.uuid4()}"
        command = ["python3", "-I", "-S", "-c", WORKER_PROGRAM, INPUT_ARTIFACT]
        container = None
        job_recorded = False
        try:
            container = self._client().containers.create(
                self.image_ref,
                command=command,
                name=f"keplerops-{job_id}",
                network_disabled=True,
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                pids_limit=32,
                mem_limit="128m",
                nano_cpus=250_000_000,
                user="65532:65532",
                working_dir=WORKER_SCRATCH,
                tmpfs={
                    WORKER_SCRATCH: "rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=0700",
                    INPUT_DIRECTORY: "rw,noexec,nosuid,nodev,size=2m,uid=65532,gid=65532",
                },
                labels={WORKER_LABEL: "true", "keplerops.loader-job": job_id},
            )
            created_at = now()
            with self.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO loader_jobs "
                    "(job_id, artifact_id, container_id, image_ref, state, command_json, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, 'created', ?, ?, ?)",
                    (
                        job_id,
                        artifact_id,
                        container.id,
                        self.image_ref,
                        canonical_json(command),
                        created_at,
                        created_at,
                    ),
                )
            job_recorded = True
            container.start()
            if not container.put_archive(INPUT_DIRECTORY, self._artifact_tar(content)):
                raise IsolationWorkerError("artifact transfer to loader failed")
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE loader_jobs SET state='running', updated_at=? WHERE job_id=?",
                    (now(), job_id),
                )
            (
                state,
                exit_code,
                output,
                output_byte_count,
                output_complete,
                timed_out,
            ) = self._wait(container)
        except IsolationWorkerError:
            self._reconcile_failed_create(container, job_id, job_recorded)
            raise
        except (APIError, DockerException) as exc:
            self._reconcile_failed_create(container, job_id, job_recorded)
            raise EngineUnavailable("dedicated loader worker execution failed") from exc
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE loader_jobs SET state=?, exit_code=?, output_text=?, "
                "output_byte_count=?, output_complete=?, timed_out=?, "
                "updated_at=? WHERE job_id=?",
                (
                    state,
                    exit_code,
                    output,
                    output_byte_count,
                    int(output_complete),
                    int(timed_out),
                    now(),
                    job_id,
                ),
            )
        self.store.event(
            "loader.execution.completed",
            "loader-worker",
            {
                "job_id": job_id,
                "artifact_id": artifact_id,
                "artifact_digest": artifact["digest"],
                "image_ref": self.image_ref,
                "command": command,
                "state": state,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "output": output,
                "output_byte_count": output_byte_count,
                "output_complete": output_complete,
            },
            job_id,
        )
        return self.status(job_id)

    def status(self, job_id: str) -> dict[str, Any]:
        row, _container = self._owned(job_id)
        return {
            "job_id": job_id,
            "artifact_id": row["artifact_id"],
            "container_id": row["container_id"],
            "image_ref": row["image_ref"],
            "state": row["state"],
            "exit_code": row["exit_code"],
            "output": row["output_text"],
            "output_byte_count": row["output_byte_count"],
            "output_complete": bool(row["output_complete"]),
            "timed_out": bool(row["timed_out"]),
            "restart_count": row["restart_count"],
        }

    def restart(self, job_id: str) -> dict[str, Any]:
        row, container = self._owned(job_id)
        try:
            container.restart(timeout=1)
            artifact = self.store.artifact(row["artifact_id"])
            if artifact is None:
                raise IsolationWorkerError("loader artifact no longer exists")
            content = (self.store.artifact_root / artifact["storage_name"]).read_bytes()
            if not container.put_archive(INPUT_DIRECTORY, self._artifact_tar(content)):
                raise IsolationWorkerError(
                    "artifact transfer to restarted loader failed"
                )
            (
                state,
                exit_code,
                output,
                output_byte_count,
                output_complete,
                timed_out,
            ) = self._wait(container)
        except (APIError, DockerException) as exc:
            raise EngineUnavailable("loader worker restart failed") from exc
        restart_count = int(row["restart_count"]) + 1
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE loader_jobs SET state=?, exit_code=?, output_text=?, "
                "output_byte_count=?, output_complete=?, timed_out=?, restart_count=?, "
                "updated_at=? WHERE job_id=?",
                (
                    state,
                    exit_code,
                    output,
                    output_byte_count,
                    int(output_complete),
                    int(timed_out),
                    restart_count,
                    now(),
                    job_id,
                ),
            )
        self.store.event(
            "loader.execution.restarted",
            "loader-worker",
            {
                "job_id": job_id,
                "restart_count": restart_count,
                "state": state,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "output": output,
                "output_byte_count": output_byte_count,
                "output_complete": output_complete,
            },
            job_id,
        )
        return self.status(job_id)

    def remove(self, job_id: str) -> dict[str, str]:
        _row, container = self._owned(job_id)
        try:
            container.remove(force=True)
        except (APIError, DockerException) as exc:
            raise EngineUnavailable("loader worker removal failed") from exc
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE loader_jobs SET state='removed', updated_at=? WHERE job_id=?",
                (now(), job_id),
            )
        self.store.event(
            "loader.execution.removed",
            "loader-worker",
            {"job_id": job_id, "state": "removed"},
            job_id,
        )
        return {"job_id": job_id, "state": "removed"}

    def cleanup(self) -> int:
        removed = 0
        unresolved: list[str] = []
        for job_id in self.store.active_job_ids():
            try:
                self.remove(job_id)
                removed += 1
            except IsolationWorkerError:
                unresolved.append(job_id)
        if unresolved:
            raise IsolationWorkerError(
                f"reset cannot discard ownership for {len(unresolved)} unresolved loader jobs"
            )
        return removed
