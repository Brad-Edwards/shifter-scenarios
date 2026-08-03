#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import cinder_transport as transport


def message(value: object) -> dict[str, object]:
    content = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    return {"messages": [{"role": "user", "content": content}]}


def content(response: dict[str, object]) -> dict[str, object]:
    choices = response["choices"]
    assert isinstance(choices, list)
    return json.loads(choices[0]["message"]["content"])


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        transport.STATE = Path(temporary)
        with transport.database() as connection:
            queued = content(
                transport.operator_request(
                    connection,
                    "librechat-web",
                    message({"command": "id", "attempt_id": "attempt-transport-1", "nonce": "nonce-unique-0001"}),
                )
            )
            try:
                transport.operator_request(
                    connection,
                    "librechat-web",
                    message({"command": "whoami", "attempt_id": "attempt-transport-1", "nonce": "nonce-unique-0001"}),
                )
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("one attempt/nonce created more than one task")

            registration = "registration-0123456789abcdef"
            proof = "a" * 64
            connection.execute(
                "INSERT INTO worker_proofs VALUES (?,?,?,?,?,NULL)",
                (proof, registration, "librechat-web", "worker-nonce-0123456789", 1),
            )
            claimed = content(
                transport.worker_request(
                    connection, "librechat-web", message("poll"), (registration, proof)
                )
            )
            assert claimed["task_id"] == queued["task_id"]
            assert claimed["worker_registration_id"] == registration
            assert claimed["worker_proof"] == proof

            bad = {
                "task_id": queued["task_id"],
                "worker_registration_id": registration,
                "worker_proof": "b" * 64,
            }
            try:
                transport.worker_request(
                    connection, "librechat-web", message(bad), (registration, "c" * 64)
                )
            except ValueError as exc:
                assert "proof recorded at claim" in str(exc)
            else:
                raise AssertionError("mismatched claim proof completed a task")
            state = connection.execute(
                "SELECT state FROM tasks WHERE task_id=?", (queued["task_id"],)
            ).fetchone()[0]
            assert state == "running"

            good = {
                "task_id": queued["task_id"],
                "worker_registration_id": registration,
                "worker_proof": proof,
                "stdout": "ok",
            }
            transport.worker_request(
                connection, "librechat-web", message(good), (registration, "d" * 64)
            )
            state = connection.execute(
                "SELECT state FROM tasks WHERE task_id=?", (queued["task_id"],)
            ).fetchone()[0]
            assert state == "completed"
    print("m05 transport regressions passed: nonce uniqueness and exact claim proof")


if __name__ == "__main__":
    main()
