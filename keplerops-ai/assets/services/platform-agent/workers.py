"""Disposable, least-privilege Linux workers managed through the Docker API."""

from __future__ import annotations

import uuid
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

from state import StateStore, canonical_json, digest_text, utc_now


DEFAULT_WORKER_IMAGE = (
    "python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689"
)
DEFAULT_ENGINE_SOCKET = "unix:///run/keplerops-worker/docker.sock"
REQUIRED_ENGINE_LABEL = "keplerops.engine.role=bounded-workers"
BOUNDARY_LABEL = "keplerops.platform-agent.worker"
MAX_JOB_BYTES = 16_384
MAX_LOG_BYTES = 65_536
WORKER_SCRATCH = "/run/keplerops-worker-job"
WORKER_PROGRAM = """\
import hashlib
import json
import os

raw = os.environ["PLATFORM_AGENT_JOB_JSON"]
job = json.loads(raw)
result = {
    "schema_version": "1",
    "status": "processed",
    "input_digest": "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    "top_level_keys": sorted(job),
}
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


class WorkerError(RuntimeError):
    """Base worker-controller failure."""


class WorkerUnavailable(WorkerError):
    """The configured local container runtime is unavailable."""


class WorkerOwnershipError(WorkerError):
    """A container did not satisfy the controller's ownership boundary."""


class DockerWorkerController:
    """Create only fixed-image, fixed-command, networkless disposable workers."""

    def __init__(
        self,
        store: StateStore,
        image_ref: str = DEFAULT_WORKER_IMAGE,
        base_url: str = DEFAULT_ENGINE_SOCKET,
        client: docker.DockerClient | None = None,
    ) -> None:
        if "@sha256:" not in image_ref:
            raise ValueError("worker image must be pinned by sha256 digest")
        if base_url != DEFAULT_ENGINE_SOCKET:
            raise ValueError(
                "worker runtime must use only the dedicated "
                "/run/keplerops-worker/docker.sock Unix socket"
            )
        self.store = store
        self.image_ref = image_ref
        self.base_url = base_url
        self._client_cache = client

    def _client(self) -> docker.DockerClient:
        if self._client_cache is not None:
            return self._client_cache
        try:
            self._client_cache = docker.DockerClient(
                base_url=self.base_url, version="auto", timeout=3
            )
            return self._client_cache
        except DockerException as exc:
            raise WorkerUnavailable("local worker runtime is unavailable") from exc

    @staticmethod
    def _labels(info: dict[str, Any]) -> set[str]:
        labels = info.get("Labels") or []
        if isinstance(labels, dict):
            return {f"{key}={value}" for key, value in labels.items()}
        return {str(label) for label in labels}

    def engine_info(self) -> dict[str, Any]:
        try:
            client = self._client()
            info = client.info()
        except (APIError, DockerException) as exc:
            raise WorkerUnavailable("dedicated worker engine is unavailable") from exc
        labels = self._labels(info)
        if REQUIRED_ENGINE_LABEL not in labels:
            raise WorkerUnavailable(
                "worker engine is missing the required bounded-workers daemon label"
            )
        security_options = [str(value) for value in info.get("SecurityOptions") or []]
        if not any("rootless" in value for value in security_options):
            raise WorkerUnavailable("dedicated worker engine is not rootless")
        try:
            client.images.get(self.image_ref)
        except ImageNotFound as exc:
            raise WorkerUnavailable(
                "bounded worker image is not preloaded on the dedicated engine"
            ) from exc
        except (APIError, DockerException) as exc:
            raise WorkerUnavailable("worker image inspection failed") from exc
        return {
            "engine_id": info.get("ID"),
            "name": info.get("Name"),
            "server_version": info.get("ServerVersion"),
            "required_label": REQUIRED_ENGINE_LABEL,
            "rootless": True,
            "worker_image_preloaded": True,
        }

    def capabilities(self) -> dict[str, Any]:
        engine: dict[str, Any] | None = None
        error: str | None = None
        try:
            engine = self.engine_info()
            available = True
        except WorkerUnavailable as exc:
            available = False
            error = str(exc)
        return {
            "runtime": "docker-engine",
            "available": available,
            "transport": "unix",
            "socket": DEFAULT_ENGINE_SOCKET,
            "image_ref": self.image_ref,
            "engine": engine,
            "error": error,
            "network_disabled": True,
            "read_only_root": True,
            "capabilities_dropped": ["ALL"],
            "privileged": False,
            "pids_limit": 32,
            "memory_limit_bytes": 134_217_728,
            "nano_cpus": 250_000_000,
        }

    def create(self, job: dict[str, Any]) -> dict[str, Any]:
        self.engine_info()
        raw = canonical_json(job)
        if len(raw.encode("utf-8")) > MAX_JOB_BYTES:
            raise WorkerError("worker job exceeds the bounded input size")
        worker_id = f"worker-{uuid.uuid4()}"
        try:
            container = self._client().containers.run(
                self.image_ref,
                command=["python3", "-c", WORKER_PROGRAM],
                name=f"keplerops-{worker_id}",
                detach=True,
                auto_remove=False,
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
                    WORKER_SCRATCH: "rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=0700"
                },
                environment={"PLATFORM_AGENT_JOB_JSON": raw},
                volumes={},
                mounts=[],
                ports={},
                devices=[],
                device_requests=[],
                privileged=False,
                labels={BOUNDARY_LABEL: "true", "keplerops.worker-id": worker_id},
            )
        except (APIError, DockerException) as exc:
            raise WorkerUnavailable("disposable worker could not be created") from exc
        now = utc_now()
        try:
            with self.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO worker_jobs "
                    "(worker_id, container_id, image_ref, state, input_digest, restart_count, "
                    "created_at, updated_at) VALUES (?, ?, ?, 'running', ?, 0, ?, ?)",
                    (
                        worker_id,
                        container.id,
                        self.image_ref,
                        digest_text(raw),
                        now,
                        now,
                    ),
                )
        except Exception:
            container.remove(force=True)
            raise
        self.store.record_event(
            "worker.created",
            "worker",
            worker_id,
            {"image_ref": self.image_ref, "input_digest": digest_text(raw)},
            worker_id,
        )
        return self.status(worker_id)

    def _row(self, worker_id: str) -> Any:
        with self.store.read() as connection:
            row = connection.execute(
                "SELECT * FROM worker_jobs WHERE worker_id=?", (worker_id,)
            ).fetchone()
        if row is None:
            raise WorkerError("unknown worker")
        return row

    def _owned_container(self, worker_id: str) -> tuple[Any, Any]:
        row = self._row(worker_id)
        if row["state"] == "removed":
            raise WorkerError("worker has been removed")
        self.engine_info()
        try:
            container = self._client().containers.get(row["container_id"])
            container.reload()
        except NotFound as exc:
            raise WorkerError("worker container no longer exists") from exc
        except (APIError, DockerException) as exc:
            raise WorkerUnavailable("worker runtime lookup failed") from exc
        config = container.attrs.get("Config", {})
        labels = config.get("Labels") or {}
        if (
            labels.get(BOUNDARY_LABEL) != "true"
            or labels.get("keplerops.worker-id") != worker_id
            or config.get("Image") != row["image_ref"]
            or row["image_ref"] != self.image_ref
        ):
            raise WorkerOwnershipError("container ownership verification failed")
        return row, container

    @staticmethod
    def _normalized_state(status: str) -> str:
        return (
            status
            if status in {"created", "running", "exited", "restarting"}
            else "unknown"
        )

    def status(self, worker_id: str) -> dict[str, Any]:
        row, container = self._owned_container(worker_id)
        state = self._normalized_state(container.status)
        logs: str | None = None
        if state == "exited":
            raw_logs = container.logs(stdout=True, stderr=True, tail=40)
            logs = raw_logs[-MAX_LOG_BYTES:].decode("utf-8", errors="replace").strip()
        now = utc_now()
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE worker_jobs SET state=?, updated_at=? WHERE worker_id=?",
                (state, now, worker_id),
            )
        return {
            "worker_id": worker_id,
            "container_id": row["container_id"],
            "image_ref": row["image_ref"],
            "state": state,
            "restart_count": row["restart_count"],
            "logs": logs,
        }

    def restart(self, worker_id: str) -> dict[str, Any]:
        row, container = self._owned_container(worker_id)
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE worker_jobs SET state='restarting', updated_at=? WHERE worker_id=?",
                (utc_now(), worker_id),
            )
        try:
            container.restart(timeout=1)
            container.reload()
        except (APIError, DockerException) as exc:
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE worker_jobs SET state='unknown', updated_at=? WHERE worker_id=?",
                    (utc_now(), worker_id),
                )
            raise WorkerUnavailable("worker restart failed") from exc
        state = self._normalized_state(container.status)
        restart_count = int(row["restart_count"]) + 1
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE worker_jobs SET state=?, restart_count=?, updated_at=? WHERE worker_id=?",
                (state, restart_count, utc_now(), worker_id),
            )
        self.store.record_event(
            "worker.restarted",
            "worker",
            worker_id,
            {"restart_count": restart_count, "state": state},
            worker_id,
        )
        return self.status(worker_id)

    def remove(self, worker_id: str) -> dict[str, Any]:
        _row, container = self._owned_container(worker_id)
        try:
            container.remove(force=True)
        except (APIError, DockerException) as exc:
            raise WorkerUnavailable("worker removal failed") from exc
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE worker_jobs SET state='removed', updated_at=? WHERE worker_id=?",
                (utc_now(), worker_id),
            )
        self.store.record_event(
            "worker.removed", "worker", worker_id, {"state": "removed"}, worker_id
        )
        return {"worker_id": worker_id, "state": "removed"}

    def cleanup(self) -> int:
        with self.store.read() as connection:
            worker_ids = [
                row["worker_id"]
                for row in connection.execute(
                    "SELECT worker_id FROM worker_jobs WHERE state <> 'removed'"
                ).fetchall()
            ]
        removed = 0
        unresolved: list[str] = []
        for worker_id in worker_ids:
            try:
                self.remove(worker_id)
                removed += 1
            except WorkerError:
                # Never delete an unverified or unreachable container during reset.
                unresolved.append(worker_id)
        if unresolved:
            raise WorkerError(
                f"reset cannot discard ownership for {len(unresolved)} unresolved workers"
            )
        return removed
