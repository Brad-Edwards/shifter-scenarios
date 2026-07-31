"""Least-privilege Cloud Run Jobs broker over caller-provided resources only."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import run_v2, storage
from google.protobuf import duration_pb2
from google.protobuf.json_format import MessageToDict

from policy import DeploymentPolicy
from security import require_request_id
from store import StateStore


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _operation_name(operation: Any) -> str | None:
    wrapped = getattr(operation, "operation", None)
    return getattr(wrapped, "name", None)


def _message(value: Any) -> dict[str, Any]:
    protobuf = getattr(value, "_pb", value)
    return MessageToDict(protobuf, preserving_proto_field_name=True)


class WorkspaceBroker:
    """Creates only deterministic jobs inside the exact ACES-realized authority."""

    def __init__(self, policy: DeploymentPolicy, store: StateStore) -> None:
        self.policy = policy
        self.store = store
        # Application Default Credentials bind these clients to the supplied runtime identity.
        self.jobs = run_v2.JobsClient()
        self.executions = run_v2.ExecutionsClient()
        self.objects = storage.Client(project=policy.project_id)

    def _identity(self, request_id: str) -> tuple[str, str]:
        suffix = hashlib.sha256(request_id.encode()).hexdigest()[:16]
        workspace_id = f"workspace-{self.policy.tenant_id}-{suffix}"
        return workspace_id, f"kep-{self.policy.tenant_id}-{suffix}"

    def _require_owned(self, record: dict[str, Any]) -> None:
        expected = rf"{re.escape(self.policy.location_name)}/jobs/kep-{self.policy.tenant_id}-[0-9a-f]{{16}}"
        if (
            record.get("tenant_id") != self.policy.tenant_id
            or re.fullmatch(expected, record.get("job_name", "")) is None
        ):
            raise RuntimeError(
                "refusing to operate on a Cloud Run job outside the active tenant"
            )

    def _validate(self, request: dict[str, Any]) -> tuple[Any, Any]:
        require_request_id(request["request_id"])
        if request["image"] not in self.policy.images:
            raise ValueError(
                "workspace image is not an exact allowlisted digest reference"
            )
        try:
            command = self.policy.commands[request["command_profile"]]
            resources = self.policy.resources[request["resource_profile"]]
        except KeyError as exc:
            raise ValueError("workspace profile is not allowlisted") from exc
        ttl = request["ttl_seconds"]
        if (
            isinstance(ttl, bool)
            or not isinstance(ttl, int)
            or not self.policy.min_ttl_seconds <= ttl <= self.policy.max_ttl_seconds
        ):
            raise ValueError("workspace TTL is outside the realization policy")
        if set(request) != {
            "request_id",
            "image",
            "command_profile",
            "resource_profile",
            "ttl_seconds",
        }:
            raise ValueError("workspace request contains unsupported authority")
        return command, resources

    def _job(
        self, request: dict[str, Any], workspace_id: str, command: Any, resources: Any
    ) -> run_v2.Job:
        export_uri = f"gs://{self.policy.export_bucket}/{self.policy.export_prefix}{workspace_id}/"
        container = run_v2.Container(
            image=request["image"],
            command=list(command.command),
            args=list(command.args),
            env=[
                run_v2.EnvVar(name="KEPLEROPS_WORKSPACE_ID", value=workspace_id),
                run_v2.EnvVar(name="KEPLEROPS_EXPORT_URI", value=export_uri),
            ],
            resources=run_v2.ResourceRequirements(
                limits={"cpu": resources.cpu, "memory": resources.memory}
            ),
        )
        task = run_v2.TaskTemplate(
            containers=[container],
            max_retries=resources.max_retries,
            timeout=duration_pb2.Duration(seconds=resources.timeout_seconds),
            service_account=self.policy.service_account,
        )
        return run_v2.Job(
            labels={
                "keplerops-boundary": "platform-deployment",
                "keplerops-tenant": self.policy.tenant_id,
                "keplerops-range": self.policy.range_instance,
                "keplerops-participant": self.policy.participant,
            },
            template=run_v2.ExecutionTemplate(task_count=1, template=task),
        )

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        command, resources = self._validate(request)
        request_id = request["request_id"]
        existing = self.store.begin_request(request_id, "workspace", request)
        if existing is not None:
            return existing
        workspace_id, job_id = self._identity(request_id)
        prior = self.store.workspace(workspace_id)
        if prior is not None and prior.get("response") is not None:
            self.store.finish_request(request_id, prior["response"])
            return prior["response"]
        job_name = f"{self.policy.location_name}/jobs/{job_id}"
        expires = datetime.now(timezone.utc) + timedelta(seconds=request["ttl_seconds"])
        record = {
            "tenant_id": self.policy.tenant_id,
            "workspace_id": workspace_id,
            "request_id": request_id,
            "job_name": job_name,
            "state": "creating",
            "request": request,
            "expires_at": _timestamp(expires),
        }
        self.store.put_workspace(record)
        started = time.monotonic()
        try:
            operation = self.jobs.create_job(
                parent=self.policy.location_name,
                job=self._job(request, workspace_id, command, resources),
                job_id=job_id,
            )
            created = operation.result(timeout=120)
        except AlreadyExists:
            created = self.jobs.get_job(name=job_name)
        previous_executions = iter(self.executions.list_executions(parent=job_name))
        previous_execution = next(previous_executions, None)
        run_operation = (
            self.jobs.run_job(name=job_name) if previous_execution is None else None
        )
        result = {
            "tenant_id": self.policy.tenant_id,
            "workspace_id": workspace_id,
            "job_name": created.name,
            "job": _message(created),
            "state": "running",
            "expires_at": _timestamp(expires),
            "export_uri": f"gs://{self.policy.export_bucket}/{self.policy.export_prefix}{workspace_id}/",
            "run_operation": _operation_name(run_operation)
            if run_operation is not None
            else None,
        }
        record.update(state="running", response=result)
        self.store.put_workspace(record)
        self.store.finish_request(request_id, result)
        self.store.record_event(
            "platform_deployment.workspace_created",
            "cloud_run_job",
            "succeeded",
            request_id,
            request,
            result,
            (time.monotonic() - started) * 1000,
        )
        return result

    def status(self, workspace_id: str) -> dict[str, Any]:
        record = self.store.workspace(workspace_id)
        if record is None:
            raise KeyError(workspace_id)
        return record

    def _terminal_execution(self, job_name: str) -> tuple[Any | None, bool]:
        executions = iter(self.executions.list_executions(parent=job_name))
        execution = next(executions, None)
        if execution is None:
            return None, False
        protobuf = getattr(execution, "_pb", None)
        terminal = bool(protobuf and protobuf.HasField("completion_time"))
        return execution, terminal

    def _safe_export_path(self, root: Path, relative: str) -> Path:
        value = PurePosixPath(relative)
        if (
            value.is_absolute()
            or not value.parts
            or any(part in {"", ".", ".."} for part in value.parts)
        ):
            raise RuntimeError("workspace export contains an unsafe object name")
        target = root.joinpath(*value.parts)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        resolved_root = root.resolve()
        resolved_parent = target.parent.resolve()
        if not resolved_parent.is_relative_to(resolved_root):
            raise RuntimeError("workspace export escaped the contained evidence root")
        return target

    def _download_export_blob(self, blob: Any, total: int) -> bytes:
        size = int(blob.size or 0)
        if size < 0 or total + size > self.policy.export_max_bytes:
            raise RuntimeError("workspace export exceeds the byte bound")
        content = blob.download_as_bytes(checksum="auto")
        if len(content) != size or total + len(content) > self.policy.export_max_bytes:
            raise RuntimeError("workspace export size changed during download")
        return content

    @staticmethod
    def _write_export_file(target: Path, content: bytes) -> None:
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)

    @staticmethod
    def _export_descriptor(blob: Any, relative: str, content: bytes) -> dict[str, Any]:
        return {
            "object": blob.name,
            "relative_path": relative,
            "generation": str(blob.generation),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "content_base64": base64.b64encode(content).decode(),
            "content_text": content.decode("utf-8", errors="replace"),
        }

    def export(self, workspace_id: str) -> dict[str, Any]:
        prefix = f"{self.policy.export_prefix}{workspace_id}/"
        root = self.store.root / "exports" / workspace_id
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        files: list[dict[str, Any]] = []
        total = 0
        blobs = self.objects.list_blobs(self.policy.export_bucket, prefix=prefix)
        for blob in blobs:
            relative = blob.name.removeprefix(prefix)
            if not relative:
                continue
            if len(files) >= self.policy.export_max_files:
                raise RuntimeError("workspace export exceeds the file-count bound")
            content = self._download_export_blob(blob, total)
            target = self._safe_export_path(root, relative)
            self._write_export_file(target, content)
            total += len(content)
            files.append(self._export_descriptor(blob, relative, content))
        return {
            "bucket": self.policy.export_bucket,
            "prefix": prefix,
            "file_count": len(files),
            "total_bytes": total,
            "files": files,
        }

    def delete(self, record: dict[str, Any], reason: str) -> dict[str, Any]:
        self._require_owned(record)
        started = time.monotonic()
        try:
            operation = self.jobs.delete_job(name=record["job_name"])
            operation.result(timeout=120)
        except NotFound:
            pass
        result = {
            "tenant_id": self.policy.tenant_id,
            "workspace_id": record["workspace_id"],
            "job_name": record["job_name"],
            "state": "deleted",
            "reason": reason,
        }
        record.update(
            state="deleted", response={**(record.get("response") or {}), **result}
        )
        self.store.put_workspace(record)
        self.store.record_event(
            "platform_deployment.workspace_deleted",
            "cloud_run_job",
            "succeeded",
            record["request_id"],
            record["request"],
            result,
            (time.monotonic() - started) * 1000,
        )
        return result

    def reconcile_one(self, record: dict[str, Any]) -> dict[str, Any]:
        self._require_owned(record)
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(record["expires_at"])
        execution, terminal = self._terminal_execution(record["job_name"])
        if terminal:
            evidence = self.export(record["workspace_id"])
            execution_content = _message(execution)
            self.store.record_event(
                "platform_deployment.workspace_exported",
                "cloud_storage",
                "succeeded",
                record["request_id"],
                {"job_name": record["job_name"]},
                {"execution": execution_content, "evidence": evidence},
                0.0,
            )
            record.update(
                state="completed",
                response={
                    **(record.get("response") or {}),
                    "execution": execution_content,
                    "evidence": evidence,
                },
            )
            self.store.put_workspace(record)
            return self.delete(record, "execution-completed")
        if now >= expires:
            return self.delete(record, "ttl-expired")
        return {"workspace_id": record["workspace_id"], "state": record["state"]}

    def reconcile(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for record in self.store.workspaces(active_only=True):
            try:
                results.append(self.reconcile_one(record))
            except Exception as exc:
                failure = {
                    "workspace_id": record["workspace_id"],
                    "state": "retry_pending",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                self.store.record_event(
                    "platform_deployment.workspace_reconcile",
                    "lifecycle",
                    "failed",
                    record["request_id"],
                    record["request"],
                    failure,
                    0.0,
                )
                results.append(failure)
        return results

    def reset(self) -> dict[str, Any]:
        deleted = [
            self.delete(record, "phase-e-reset")
            for record in self.store.workspaces(active_only=True)
        ]
        self.store.reset_local()
        export_root = self.store.root / "exports"
        if export_root.exists():
            for tenant_root in export_root.glob(f"workspace-{self.policy.tenant_id}-*"):
                for path in sorted(tenant_root.rglob("*"), reverse=True):
                    path.unlink() if path.is_file() else path.rmdir()
                tenant_root.rmdir()
            try:
                export_root.rmdir()
            except OSError:
                pass
        return {"status": "reset", "deleted_jobs": deleted}
