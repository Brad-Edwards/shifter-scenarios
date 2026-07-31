"""Fail-open participant-run telemetry persistence and deterministic export."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import threading
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from domain import (
    DomainError,
    ResearchContract,
    ResearchObservation,
    derive_research_context,
)


SHA256_PREFIX = "sha256:"
CONTENT_EVENTS_NAME = "content.jsonl"
NETWORK_FLOWS_NAME = "network-flows.jsonl"


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _write_owner_file(path: Path, body: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


class ResearchEmitter:
    """A bounded non-throwing queue; transport work happens outside requests."""

    def __init__(self, *, capacity: int = 256) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise DomainError("research emitter: invalid capacity")
        self._queue: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._capacity = capacity
        self._accepted = 0
        self._dropped = 0
        self._stopping = threading.Event()
        self._start_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def emit(self, event: Mapping[str, Any]) -> bool:
        try:
            if not isinstance(event, Mapping) or len(self._queue) >= self._capacity:
                self._dropped += 1
                return False
            self._queue.append(dict(event))
            self._accepted += 1
            return True
        except Exception:
            self._dropped += 1
            return False

    def flush_one(self, sender: Callable[[dict[str, Any]], Any]) -> bool:
        if not self._queue:
            return False
        event = self._queue.popleft()
        try:
            sender(event)
            return True
        except Exception:
            self._dropped += 1
            return False

    def snapshot(self) -> dict[str, int]:
        return {
            "accepted": self._accepted,
            "dropped": self._dropped,
            "queued": len(self._queue),
        }

    def start(
        self,
        sender: Callable[[dict[str, Any]], Any],
        *,
        interval_seconds: float = 0.05,
    ) -> None:
        if self._worker is not None or interval_seconds <= 0:
            raise DomainError("research emitter: invalid worker")
        self._stopping.clear()

        def run() -> None:
            while not self._stopping.is_set() or self._queue:
                if not self.flush_one(sender):
                    self._stopping.wait(interval_seconds)

        self._worker = threading.Thread(
            target=run,
            name="keplerops-research-emitter",
            daemon=True,
        )
        self._worker.start()

    def start_once(
        self,
        sender: Callable[[dict[str, Any]], Any],
        *,
        interval_seconds: float = 0.05,
    ) -> bool:
        """Start on the first lifecycle callback and ignore duplicate callbacks."""
        with self._start_lock:
            if self._worker is not None:
                return False
            self.start(sender, interval_seconds=interval_seconds)
            return True

    def close(self, *, timeout_seconds: float = 2.5) -> None:
        with self._start_lock:
            worker = self._worker
            if worker is None:
                return
            self._stopping.set()
        worker.join(timeout=max(0.0, timeout_seconds))
        with self._start_lock:
            if self._worker is worker and not worker.is_alive():
                self._worker = None


class ResearchStore:
    """Separate non-awarding store for operational events and encrypted content."""

    def __init__(
        self,
        path: Path,
        *,
        contract: ResearchContract,
        pseudonym_key: bytes,
        content_key: bytes,
    ) -> None:
        if not isinstance(path, Path) or not isinstance(contract, ResearchContract):
            raise DomainError("research store: invalid configuration")
        if not isinstance(pseudonym_key, bytes) or len(pseudonym_key) < 16:
            raise DomainError("research store: invalid pseudonym key")
        if not isinstance(content_key, bytes) or len(content_key) != 32:
            raise DomainError("research store: invalid content key")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        self.path = path
        self.contract = contract
        self._pseudonym_key = pseudonym_key
        self._content_key = content_key
        self._capture_signals = dict(contract.capture_signals)
        with self._database() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_events (
                  event_id TEXT PRIMARY KEY,
                  study_run_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  event_name TEXT NOT NULL,
                  occurred_at INTEGER NOT NULL,
                  observed_at INTEGER NOT NULL,
                  source_id TEXT NOT NULL,
                  source_sequence INTEGER NOT NULL,
                  event_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_source_health (
                  session_id TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  accepted INTEGER NOT NULL DEFAULT 0,
                  dropped INTEGER NOT NULL DEFAULT 0,
                  sequence_gaps INTEGER NOT NULL DEFAULT 0,
                  last_sequence INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY (session_id, source_id)
                );
                CREATE TABLE IF NOT EXISTS research_content (
                  content_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  trace_id TEXT NOT NULL,
                  signal TEXT NOT NULL,
                  observed_at INTEGER NOT NULL,
                  nonce BLOB NOT NULL,
                  ciphertext BLOB NOT NULL
                );
                """
            )
        path.chmod(0o600)

    @contextmanager
    def _database(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_observation(
        self,
        observation: ResearchObservation,
        *,
        source_id: str,
        range_instance: str,
        participant: str,
        reset_generation: int,
        observed_at: int,
    ) -> dict[str, Any]:
        if not isinstance(observation, ResearchObservation):
            raise DomainError("research store: invalid observation")
        if source_id not in self.contract.sources:
            raise DomainError("research store: invalid source")
        if not isinstance(observed_at, int) or isinstance(observed_at, bool) or observed_at < 0:
            raise DomainError("research store: invalid observation time")
        context = derive_research_context(
            key=self._pseudonym_key,
            range_instance=range_instance,
            participant=participant,
            reset_generation=reset_generation,
        )
        values = dict(observation.values)
        material = (
            f"v1:{context.session_id}:{source_id}:{values['source_sequence']}:"
            f"{values['event_name']}:{values['trace_id']}"
        ).encode("utf-8")
        event_id = "evt-" + hashlib.sha256(material).hexdigest()[:32]
        event = {
            **values,
            "schema_version": self.contract.schema_version,
            "event_id": event_id,
            "observed_at": observed_at,
            "study_run_id": context.study_run_id,
            "session_id": context.session_id,
            "source_id": source_id,
            "reset_generation": reset_generation,
        }
        if "module_id" in values:
            event["challenge_version"] = self.contract.modules[values["module_id"]]
        if set(event) - set(self.contract.operational_fields):
            raise DomainError("research store: event escaped field policy")
        sequence = values["source_sequence"]
        with self._database() as connection:
            existing = connection.execute(
                "SELECT last_sequence FROM research_source_health WHERE session_id=? AND source_id=?",
                (context.session_id, source_id),
            ).fetchone()
            last = existing[0] if existing else 0
            gap = max(0, sequence - last - 1)
            dropped = values.get("dropped_event_count", 0)
            inserted = connection.execute(
                "INSERT OR IGNORE INTO research_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    context.study_run_id,
                    context.session_id,
                    values["event_name"],
                    values["occurred_at"],
                    observed_at,
                    source_id,
                    sequence,
                    _canonical(event).decode("utf-8"),
                ),
            ).rowcount
            if inserted:
                connection.execute(
                    "INSERT INTO research_source_health "
                    "(session_id, source_id, accepted, dropped, sequence_gaps, last_sequence) "
                    "VALUES (?, ?, 1, ?, ?, ?) ON CONFLICT(session_id, source_id) DO UPDATE SET "
                    "accepted=accepted+1, sequence_gaps=sequence_gaps+excluded.sequence_gaps, "
                    "dropped=MAX(dropped, excluded.dropped), "
                    "last_sequence=MAX(last_sequence, excluded.last_sequence)",
                    (context.session_id, source_id, dropped, gap, sequence),
                )
        return event

    def events_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._database() as connection:
            rows = connection.execute(
                "SELECT event_json FROM research_events WHERE session_id=? "
                "ORDER BY occurred_at, observed_at, source_id, source_sequence, event_id",
                (session_id,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def source_health(self, session_id: str, source_id: str) -> dict[str, int]:
        with self._database() as connection:
            row = connection.execute(
                "SELECT accepted, dropped, sequence_gaps, last_sequence "
                "FROM research_source_health WHERE session_id=? AND source_id=?",
                (session_id, source_id),
            ).fetchone()
        if row is None:
            return {"accepted": 0, "dropped": 0, "sequence_gaps": 0, "last_sequence": 0}
        return dict(zip(("accepted", "dropped", "sequence_gaps", "last_sequence"), row))

    def session_ids(self) -> list[str]:
        with self._database() as connection:
            rows = connection.execute(
                "SELECT session_id, MAX(observed_at) AS latest FROM research_events "
                "GROUP BY session_id ORDER BY latest DESC, session_id"
            ).fetchall()
        return [row[0] for row in rows]

    def set_capture_signal(self, signal: str, *, enabled: bool) -> None:
        if signal not in self._capture_signals or not isinstance(enabled, bool):
            raise DomainError("research content: invalid signal")
        self._capture_signals[signal] = enabled

    def record_content(
        self,
        *,
        session_id: str,
        trace_id: str,
        signal: str,
        content: bytes,
        observed_at: int,
    ) -> bool:
        if signal not in self._capture_signals:
            raise DomainError("research content: invalid signal")
        if not self._capture_signals[signal]:
            return False
        if (
            not isinstance(content, bytes)
            or not content
            or len(content) > 1_048_576
            or not isinstance(observed_at, int)
            or observed_at < 0
        ):
            raise DomainError("research content: invalid content")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._content_key).encrypt(nonce, content, None)
        content_id = "cnt-" + hashlib.sha256(
            session_id.encode("utf-8") + trace_id.encode("ascii") + signal.encode("ascii") + nonce
        ).hexdigest()[:32]
        with self._database() as connection:
            connection.execute(
                "INSERT INTO research_content VALUES (?, ?, ?, ?, ?, ?, ?)",
                (content_id, session_id, trace_id, signal, observed_at, nonce, ciphertext),
            )
        return True

    def decrypt_content(self, nonce: bytes, ciphertext: bytes) -> bytes:
        return AESGCM(self._content_key).decrypt(nonce, ciphertext, None)

    def encrypted_content_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._database() as connection:
            rows = connection.execute(
                "SELECT content_id, trace_id, signal, observed_at, nonce, ciphertext "
                "FROM research_content WHERE session_id=? "
                "ORDER BY observed_at, trace_id, signal, content_id",
                (session_id,),
            ).fetchall()
        return [
            {
                "content_id": row[0],
                "session_id": session_id,
                "trace_id": row[1],
                "signal": row[2],
                "observed_at": row[3],
                "nonce_b64": base64.b64encode(row[4]).decode("ascii"),
                "ciphertext_b64": base64.b64encode(row[5]).decode("ascii"),
                "encryption": "AES-256-GCM",
            }
            for row in rows
        ]

    def export_session(
        self,
        session_id: str,
        destination: Path,
        *,
        contract_document: bytes,
        dictionary_path: Path,
        metadata: Mapping[str, Any],
    ) -> str:
        if (
            destination.exists()
            or not isinstance(metadata, Mapping)
            or not isinstance(contract_document, bytes)
            or not contract_document
        ):
            raise DomainError("research export: invalid destination")
        destination.mkdir(mode=0o700, parents=True)
        destination.chmod(0o700)
        events = self.events_for_session(session_id)
        if not events:
            raise DomainError("research export: session not found")
        with self._database() as connection:
            rows = connection.execute(
                "SELECT accepted, dropped, sequence_gaps FROM research_source_health "
                "WHERE session_id=? ORDER BY source_id",
                (session_id,),
            ).fetchall()
        missingness = {
            "accepted": sum(row[0] for row in rows),
            "dropped": sum(row[1] for row in rows),
            "sequence_gaps": sum(row[2] for row in rows),
            "network_flow": {
                "capture_status": "unavailable",
                "record_count": 0,
                "sampling_rate": 0.0,
            },
            "status": "complete" if rows and not any(row[1] or row[2] for row in rows) else "incomplete",
        }
        if missingness["status"] == "complete":
            missingness["status"] = "incomplete"
        _write_owner_file(
            destination / "events.jsonl",
            b"".join(_canonical(event) + b"\n" for event in events),
        )
        _write_owner_file(destination / NETWORK_FLOWS_NAME, b"")
        _write_owner_file(destination / "missingness.json", _canonical(missingness) + b"\n")
        _write_owner_file(destination / "schema.yaml", contract_document)
        _write_owner_file(destination / "data-dictionary.md", dictionary_path.read_bytes())
        _write_owner_file(destination / "environment.json", _canonical(dict(metadata)) + b"\n")
        members = {}
        for path in sorted(destination.iterdir(), key=lambda item: item.name):
            members[path.name] = SHA256_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = {
            "schema_version": self.contract.schema_version,
            "session_id": session_id,
            "metadata": dict(metadata),
            "members": members,
        }
        _write_owner_file(destination / "manifest.json", _canonical(manifest) + b"\n")
        checksum_lines = []
        for path in sorted(destination.iterdir(), key=lambda item: item.name):
            checksum_lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
        checksums = "".join(checksum_lines).encode("ascii")
        _write_owner_file(destination / "checksums.sha256", checksums)
        return SHA256_PREFIX + hashlib.sha256(checksums).hexdigest()

    def export_encrypted_content(self, session_id: str, destination: Path) -> str:
        if destination.exists():
            raise DomainError("research content export: invalid destination")
        destination.mkdir(mode=0o700, parents=True)
        destination.chmod(0o700)
        rows = self.encrypted_content_for_session(session_id)
        if not rows:
            raise DomainError("research content export: session not found")
        _write_owner_file(
            destination / CONTENT_EVENTS_NAME,
            b"".join(_canonical(row) + b"\n" for row in rows),
        )
        manifest = {
            "schema_version": self.contract.schema_version,
            "session_id": session_id,
            "content_records": len(rows),
            "encryption": "AES-256-GCM",
            "key_included": False,
            "members": {
                CONTENT_EVENTS_NAME: SHA256_PREFIX
                + hashlib.sha256((destination / CONTENT_EVENTS_NAME).read_bytes()).hexdigest(),
            },
        }
        _write_owner_file(destination / "manifest.json", _canonical(manifest) + b"\n")
        checksum_lines = [
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(destination.iterdir(), key=lambda item: item.name)
        ]
        checksums = "".join(checksum_lines).encode("ascii")
        _write_owner_file(destination / "checksums.sha256", checksums)
        return SHA256_PREFIX + hashlib.sha256(checksums).hexdigest()
