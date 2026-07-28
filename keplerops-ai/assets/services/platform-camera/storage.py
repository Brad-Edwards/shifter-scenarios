"""Contained, durable state for the KeplerOps live-camera boundary."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STATE_FILE_NAME = "state.json"


def utc_now() -> str:
    """Return a stable, timezone-qualified timestamp for event reconstruction."""

    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class CameraState:
    """Filesystem-backed journal and retained-frame store.

    The state root is expected to be a private container volume. Writes are
    fsync'd before returning so a successful capture acknowledgement has a
    durable reconstruction record.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.RLock()
        self._prepare()

    @property
    def event_path(self) -> Path:
        return self.root / "events" / "events.jsonl"

    def _prepare(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        (self.root / "events").mkdir(mode=0o700, parents=True, exist_ok=True)
        state_path = self.root / STATE_FILE_NAME
        if not state_path.exists():
            self._atomic_json(
                state_path,
                {"schema_version": SCHEMA_VERSION, "reset_generation": 0},
            )

    def ready(self) -> bool:
        """Probe contained-state writeability without leaving transient data."""

        probe = self.root / ".ready-probe"
        try:
            with self._lock:
                probe.write_bytes(b"ready\n")
                os.chmod(probe, 0o600)
                probe.unlink()
            return True
        except OSError:
            return False

    def create_session(
        self,
        *,
        session_id: str,
        session_token_digest: str,
        initiation: dict[str, Any],
        expires_at: str,
    ) -> None:
        session_root = self.root / "sessions" / session_id
        with self._lock:
            (session_root / "frames").mkdir(mode=0o700, parents=True, exist_ok=False)
            self._atomic_json(
                session_root / "session.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "session_id": session_id,
                    "session_token_digest": session_token_digest,
                    "created_at": utc_now(),
                    "expires_at": expires_at,
                    "initiation": initiation,
                },
            )

    def append_event(self, event: dict[str, Any]) -> None:
        encoded = (
            json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")
        with self._lock:
            descriptor = os.open(
                self.event_path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                self._write_all(descriptor, encoded)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def retain_capture(
        self,
        *,
        session_id: str,
        frame_id: str,
        png: bytes,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist a frame and its full-content event before acknowledgement."""

        relative_path = Path("sessions") / session_id / "frames" / f"{frame_id}.png"
        target = self.root / relative_path
        digest = digest_bytes(png)
        enriched = {
            **event,
            "retained_frame": {
                "relative_path": relative_path.as_posix(),
                "sha256": digest,
                "bytes": len(png),
                "image_png_base64": base64.b64encode(png).decode("ascii"),
            },
        }
        with self._lock:
            self._atomic_bytes(target, png)
            self.append_event(enriched)
        return enriched

    def update_session(self, session_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            target = self.root / "sessions" / session_id / "runtime.json"
            self._atomic_json(target, state)

    def reset(self) -> dict[str, int | str]:
        """Return the store to the same source-defined baseline every time."""

        baseline = {"schema_version": SCHEMA_VERSION, "reset_generation": 1}
        with self._lock:
            for child in tuple(self.root.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            self._prepare()
            self._atomic_json(self.root / STATE_FILE_NAME, baseline)
        return {"status": "reset", **baseline}

    def recent_events(self, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            if not self.event_path.exists():
                return []
            lines = self.event_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:] if line]

    def _atomic_json(self, path: Path, value: dict[str, Any]) -> None:
        encoded = (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")
        self._atomic_bytes(path, encoded)

    @staticmethod
    def _atomic_bytes(path: Path, value: bytes) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        descriptor = os.open(
            temporary,
            os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
            0o600,
        )
        try:
            CameraState._write_all(descriptor, value)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    @staticmethod
    def _write_all(descriptor: int, value: bytes) -> None:
        written = 0
        while written < len(value):
            written += os.write(descriptor, value[written:])
