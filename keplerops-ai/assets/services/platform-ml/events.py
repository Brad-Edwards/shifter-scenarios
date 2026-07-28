"""Durable telemetry records for reconstructing workbench activity."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models import canonical_json, digest_json


class EventJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sequence = self._last_sequence()

    def _last_sequence(self) -> int:
        if not self.path.is_file():
            return 0
        last = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = max(last, int(json.loads(line)["sequence"]))
        return last

    def reset(self) -> None:
        with self._lock:
            self.path.write_text("", encoding="utf-8")
            self._sequence = 0

    def append(
        self,
        *,
        event_name: str,
        operation: str,
        status: str,
        request_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
        model_ids: list[str],
        duration_ms: float,
    ) -> dict[str, Any]:
        with self._lock:
            self._sequence += 1
            record = {
                "schema_version": 1,
                "event_id": str(uuid.uuid4()),
                "sequence": self._sequence,
                "event_name": event_name,
                "occurred_at": datetime.now(UTC).isoformat(),
                "source": "keplerops-platform-ml",
                "operation": operation,
                "status": status,
                "request_id": request_id,
                "request": request,
                "response": response,
                "request_digest": digest_json(request),
                "response_digest": digest_json(response),
                "model_ids": model_ids,
                "duration_ms": round(duration_ms, 3),
            }
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(canonical_json(record) + "\n")
            return record

    def recent(self, limit: int) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        lines = [
            line for line in self.path.read_text(encoding="utf-8").splitlines() if line
        ]
        return [json.loads(line) for line in lines[-limit:]]
