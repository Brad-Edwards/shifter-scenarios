#!/usr/bin/env python3
"""FieldLink bundle indexer and release-exception processing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import threading
import uuid
from urllib import parse as urlparse

from credentials import credential
from http_support import KeplerHandler, append_audit, canonical_bytes, serve_tls, sha256_bytes

STATE_ROOT = Path(os.environ.get('FIELDKEST_STATE_ROOT', '/var/lib/fieldkest-indexer'))
AUDIT = STATE_ROOT / 'audit'
STATE_FILE = STATE_ROOT / 'state.json'
LOCK = threading.RLock()
DEV_USER = 'rowan.ito'
DEV_TOKEN = credential('developer_token')
INDEXER_WORKER_TOKEN = credential('indexer_worker_lease')
EXCEPTION_RECORD_ID = 'REL-EXC-2841'


def initial_state() -> dict[str, object]:
    return {'indexer': {'sentinel': 'stable', 'generation': 1, 'write_ready': False, 'indexes': {}}}


def load_state() -> dict[str, object]:
    with LOCK:
        if not STATE_FILE.exists():
            value = initial_state()
            save_state(value)
            return value
        return json.loads(STATE_FILE.read_text())


def save_state(value: dict[str, object]) -> None:
    with LOCK:
        STATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_bytes(canonical_bytes(value) + b"\n")
        temporary.replace(STATE_FILE)


ARENA_SHM_PATH = STATE_ROOT / 'arena.shm'
ARENA_SIZE = 128
DESCRIPTOR_OFFSET = 80
DESCRIPTOR_SIZE = 48  # bytes 80-127


def write_descriptor_to_arena(generation: int) -> None:
    """Write the runtime descriptor into bytes 80-127 of the shared arena.

    The binary reads the shared arena BEFORE each memcpy.  After K04.1 mutation
    the descriptor appears at bytes 80-127 so a subsequent request with
    datalen=128 (ie=16, ae=48) will include it in the data_hex response.
    The descriptor is written here by the service; it is disclosed by the binary
    as a consequence of the extended read primitive, not a conditional branch.
    """
    descriptor = json.dumps({
        "schema": "fieldkest.runtime-descriptor/v1",
        "worker_session": INDEXER_WORKER_TOKEN,
        "process_generation": generation,
        "exception_record": EXCEPTION_RECORD_ID,
        "protected_object_marker": "release-exception-state",
        "integrity_relation": f"sha256({generation}:queue-ready)",
        "state_route": "/api/internal/release-exceptions/state",
        "completion_route": f"/api/internal/release-exceptions/{EXCEPTION_RECORD_ID}/complete",
    }).encode()
    # Pad or truncate to DESCRIPTOR_SIZE
    padded = (descriptor + b'\x00' * DESCRIPTOR_SIZE)[:DESCRIPTOR_SIZE]
    with LOCK:
        # Ensure the shared arena file is at least ARENA_SIZE bytes
        if not ARENA_SHM_PATH.exists():
            ARENA_SHM_PATH.write_bytes(b'\x00' * ARENA_SIZE)
        arena = bytearray(ARENA_SHM_PATH.read_bytes().ljust(ARENA_SIZE, b'\x00'))
        arena[DESCRIPTOR_OFFSET:DESCRIPTOR_OFFSET + DESCRIPTOR_SIZE] = padded
        ARENA_SHM_PATH.write_bytes(bytes(arena))


def bearer(handler: KeplerHandler) -> str | None:
    value = handler.headers.get("Authorization", "")
    return value[7:] if value.startswith("Bearer ") else None


class IndexerHandler(KeplerHandler):
    def dev_auth(self) -> bool:
        return self.basic_or_bearer(DEV_USER, DEV_TOKEN)

    def deny(self, status: int = 403, error: str = "access_denied") -> None:
        self.send_json(status, {"error": error})

    def body(self) -> dict[str, object]:
        value = self.read_json()
        if not isinstance(value, dict):
            raise ValueError("object_required")
        return value

    def record(self, stream: str, **fields: object) -> None:
        append_audit(AUDIT, stream, {"request_id": self.request_id, **fields})

    def get_indexer(self) -> None:
        match = re.fullmatch(r"/api/indexes/([A-Z0-9-]+)", urlparse.urlsplit(self.path).path)
        if not match or not self.dev_auth(): return self.deny(403)
        value = load_state()["indexer"]["indexes"].get(match.group(1))
        if not value: return self.deny(404, "index_not_found")
        self.record("index-read", principal=DEV_USER, index_id=match.group(1))
        self.send_json(200, value)

    def post_indexer(self) -> None:
        path = urlparse.urlsplit(self.path).path
        state = load_state()
        indexer = state["indexer"]

        if path == "/api/indexes":
            if not self.dev_auth(): return self.deny(401, "authentication_required")
            data = self.body()
            bundle_hex = str(data.get("bundle_hex", ""))
            try:
                bundle = bytes.fromhex(bundle_hex)
            except ValueError:
                raise ValueError("bundle_rejected")
            if len(bundle) < 8 or len(bundle) > 4096: raise ValueError("bundle_rejected")
            native = subprocess.run(
                ["/usr/local/bin/fieldkest-bundle-indexer", bundle_hex],
                capture_output=True, text=True, timeout=3, check=False,
            )
            if native.returncode != 0: raise ValueError("bundle_rejected")
            native_result = json.loads(native.stdout)
            index_id = "IDX-" + uuid.uuid4().hex[:10].upper()
            result = {"index_id": index_id, "state": "indexed", "bundle_sha256": sha256_bytes(bundle), **native_result}
            if native_result["sentinel"] == "mutated" and indexer["sentinel"] != "mutated":
                # K04.1: write the runtime descriptor into bytes 80-127 of the shared arena.
                # The binary reads the arena before each memcpy.  On a subsequent request
                # with datalen=128 (K04.2), the binary includes bytes 80-127 in data_hex.
                indexer["sentinel"] = "mutated"
                write_descriptor_to_arena(indexer["generation"])
                self.record("sentinel-mutation", descriptor_written=True)
            indexer["indexes"][index_id] = result
            save_state(state)
            self.record("bundle-index", principal=DEV_USER, **result)
            return self.send_json(201, result)

        if path == "/api/internal/release-exceptions/state":
            # K04.3 requires the INDEXER_WORKER_TOKEN revealed through K04.2 binary disclosure.
            if bearer(self) != INDEXER_WORKER_TOKEN or indexer.get("sentinel") != "mutated":
                return self.deny(403)
            data = self.body()
            if data.get("state") != "queue-ready" or data.get("integrity") != sha256_bytes(
                f"{indexer['generation']}:queue-ready".encode()
            ):
                raise ValueError("integrity_rejected")
            indexer["write_ready"] = True
            save_state(state)
            self.record("exception-state", principal="svc-fieldkest-indexer", state="queue-ready")
            return self.send_json(200, {"state": "queue-ready", "integrity": data["integrity"]})

        complete_match = re.fullmatch(
            r"/api/internal/release-exceptions/([A-Z0-9-]+)/complete", path)
        if complete_match:
            if complete_match.group(1) != EXCEPTION_RECORD_ID: return self.deny(404, "not_found")
            if bearer(self) != INDEXER_WORKER_TOKEN or not indexer.get("write_ready"):
                return self.deny(403)
            data = self.body()
            if data.get("routine") != "recover_exception_queue" or data.get("generation") != indexer["generation"]:
                raise ValueError("routine_arguments_rejected")
            value = {"record_id": EXCEPTION_RECORD_ID, "revision": 9,
                     "service_identity": "svc-fieldkest-indexer", "dossier": "BLD-REL-742",
                     "exceptions": ["signer rollover pending", "connector v2 compatibility retained"]}
            self.record("exception-complete", **value)
            return self.send_json(200, value)

        self.deny(404, "not_found")

    def do_GET(self) -> None:
        if self.send_client_document():
            return
        try:
            self.get_indexer()
        except (ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
            self.send_json(422, {'error': str(error)})

    def do_POST(self) -> None:
        try:
            self.post_indexer()
        except (ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
            self.send_json(422, {'error': str(error)})

    def do_PATCH(self) -> None:
        self.do_POST()


def main() -> None:
    serve_tls(IndexerHandler, int(os.environ.get('PORT', '443')))


if __name__ == '__main__':
    main()
