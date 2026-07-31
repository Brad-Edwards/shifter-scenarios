"""Loopback control and readback service for the green participant runtime."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any


class GreenActivityService:
    def __init__(self, engine: Any, *, token_file: Path) -> None:
        self._engine = engine
        self._token_file = token_file
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_error: str | None = None

    def _authenticate(self, token: str) -> None:
        expected = self._token_file.read_text(encoding="utf-8").strip()
        if not expected or token != expected:
            raise PermissionError("green activity control authentication failed")

    def health(self) -> dict[str, object]:
        return {
            "status": "degraded" if self._last_error else "ok",
            "last_error": self._last_error,
            **self._engine.status(),
        }

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = threading.Thread(
            target=self._work,
            name="keplerops-green-activity",
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=5)
        self._worker = None

    def _work(self) -> None:
        while not self._stop.wait(self._engine.seconds_until_next_due()):
            try:
                with self._lock:
                    result = self._engine.run_next_due()
                self._last_error = (
                    None
                    if result.success
                    else "; ".join(item.message for item in result.diagnostics)
                )
            except Exception as exc:  # noqa: BLE001 - background faults must remain observable
                self._last_error = f"{type(exc).__name__}: {exc}"[:512]

    def run_once(self, token: str) -> dict[str, object]:
        self._authenticate(token)
        with self._lock:
            result = self._engine.run_next_due()
            if not result.success:
                raise RuntimeError(
                    "; ".join(item.message for item in result.diagnostics)
                    or "green activity execution failed"
                )
            self._last_error = None
            return self._engine.status()

    def control(
        self,
        action: str,
        token: str,
        *,
        reset_generation: int | None = None,
    ) -> dict[str, object]:
        self._authenticate(token)
        if action == "reset" and reset_generation is None:
            raise ValueError("green activity reset requires reset_generation")
        with self._lock:
            result = self._engine.control(action, reset_generation=reset_generation)
            return {
                "success": result.success,
                "diagnostics": [item.message for item in result.diagnostics],
                **self._engine.status(),
            }
