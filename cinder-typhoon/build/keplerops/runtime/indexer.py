#!/usr/bin/env python3
"""FieldLink bundle indexer and release-exception processing."""
from __future__ import annotations

import hashlib
import hmac as hmac_lib
import json
import os
from pathlib import Path
import re
import struct
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
ARENA_SIZE = 1024
DESCRIPTOR_OFFSET = 80
DESCRIPTOR_SIZE = 432   # bytes 80-511
EXCEPTION_STATE_OFFSET = 512
EXCEPTION_VALUE_SIZE = 32   # bytes 512-543
EXCEPTION_INTEGRITY_SIZE = 32   # bytes 544-575


def write_arena_at_mutation(generation: int) -> None:
    """Write the runtime descriptor (bytes 80-511) and seed the exception-state
    region (bytes 512-575) into the shared arena at K04.1 mutation time.

    The binary reads the full arena BEFORE each write.  After K04.1 mutation
    a subsequent request with datalen=512 (ie=64, ae=432) discloses the
    descriptor in data_hex chars 160-1023.  With datalen=576 (ie=72, ae=496)
    bytes 512-575 are also read back, exposing the seeded exception-state.
    Both disclosures are consequences of the extended read primitive.
    """
    descriptor = json.dumps({
        "schema": "fieldkest.runtime-descriptor/v1",
        "worker_session": INDEXER_WORKER_TOKEN,
        "process_generation": generation,
        "exception_record": EXCEPTION_RECORD_ID,
        "exception_state_offset": EXCEPTION_STATE_OFFSET,
        "exception_value_size": EXCEPTION_VALUE_SIZE,
        "exception_integrity_size": EXCEPTION_INTEGRITY_SIZE,
        "integrity_relation": "hmac-sha256(worker_session:queue-ready)",
        "completion_route": f"/api/internal/release-exceptions/{EXCEPTION_RECORD_ID}/complete",
    }).encode()
    padded_descriptor = (descriptor + b'\x00' * DESCRIPTOR_SIZE)[:DESCRIPTOR_SIZE]

    # Seed exception-state region with "locked" + HMAC(worker_session, "locked")
    locked = b"locked" + b'\x00' * (EXCEPTION_VALUE_SIZE - len(b"locked"))
    locked_integrity = hmac_lib.digest(INDEXER_WORKER_TOKEN.encode(), b"locked", hashlib.sha256)

    with LOCK:
        if not ARENA_SHM_PATH.exists():
            ARENA_SHM_PATH.write_bytes(b'\x00' * ARENA_SIZE)
        arena = bytearray(ARENA_SHM_PATH.read_bytes().ljust(ARENA_SIZE, b'\x00'))
        arena[DESCRIPTOR_OFFSET:DESCRIPTOR_OFFSET + DESCRIPTOR_SIZE] = padded_descriptor
        arena[EXCEPTION_STATE_OFFSET:EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE] = locked
        arena[EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE:EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE + EXCEPTION_INTEGRITY_SIZE] = locked_integrity
        ARENA_SHM_PATH.write_bytes(bytes(arena))


def check_exception_write() -> bool:
    """Return True if the exception-state region contains a valid queue-ready write.

    Validates bytes 512-543 (state value) and bytes 544-575 (HMAC-SHA256 keyed
    by INDEXER_WORKER_TOKEN).  Also verifies that the descriptor at bytes 80-511
    is still intact, enforcing the all-other-bytes-immutable constraint.
    """
    with LOCK:
        try:
            arena = ARENA_SHM_PATH.read_bytes()
        except FileNotFoundError:
            return False
    if len(arena) < EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE + EXCEPTION_INTEGRITY_SIZE:
        return False

    state_bytes = arena[EXCEPTION_STATE_OFFSET:EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE].rstrip(b'\x00')
    integrity_bytes = arena[EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE:EXCEPTION_STATE_OFFSET + EXCEPTION_VALUE_SIZE + EXCEPTION_INTEGRITY_SIZE]

    if state_bytes != b"queue-ready":
        return False

    expected_integrity = hmac_lib.digest(INDEXER_WORKER_TOKEN.encode(), state_bytes, hashlib.sha256)
    if not hmac_lib.compare_digest(integrity_bytes, expected_integrity):
        return False

    # Verify descriptor at bytes 80-511 is intact (all other bytes immutable)
    descriptor_bytes = arena[DESCRIPTOR_OFFSET:DESCRIPTOR_OFFSET + DESCRIPTOR_SIZE].rstrip(b'\x00')
    try:
        d = json.loads(descriptor_bytes)
        if d.get("worker_session") != INDEXER_WORKER_TOKEN or d.get("exception_record") != EXCEPTION_RECORD_ID:
            return False
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

    return True


_DOSSIER_KEY_RELATION = "sha256-ctr(sha256(hmac-sha256(worker_session:queue-ready)+':dossier-key'))"
_DOSSIER_PLAINTEXT = json.dumps({
    "dossier": "BLD-REL-742",
    "exceptions": ["signer rollover pending", "connector v2 compatibility retained"],
    "service_identity": "svc-fieldkest-indexer",
}, separators=(',', ':'), sort_keys=True).encode()


def encrypt_record(derived_key: bytes, plaintext: bytes) -> bytes:
    """SHA256 counter-mode XOR stream cipher.

    For each 32-byte block i: keystream = SHA256(derived_key || big-endian(i)).
    Participant decrypts by reproducing this keystream from the derived key.
    """
    result = bytearray(len(plaintext))
    for i in range(0, len(plaintext), 32):
        block = plaintext[i:i + 32]
        keystream = hashlib.sha256(derived_key + struct.pack(">I", i // 32)).digest()
        for j, (p, k) in enumerate(zip(block, keystream)):
            result[i + j] = p ^ k
    return bytes(result)


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
                # K04.1: write descriptor (bytes 80-511) and seed exception-state (bytes 512-575).
                indexer["sentinel"] = "mutated"
                write_arena_at_mutation(indexer["generation"])
                self.record("sentinel-mutation", descriptor_written=True)
                result["flag"] = "FLAG{c21a0bdd9ca4afce}"
            if not indexer.get("write_ready") and indexer.get("sentinel") == "mutated" and check_exception_write():
                # K04.3: participant delivered a 576-byte bundle that wrote queue-ready +
                # HMAC(worker_session, queue-ready) at bytes 512-575 while preserving the
                # descriptor at bytes 80-511.  No code branch in the binary recognises this;
                # the write is a consequence of the controlled allocation primitive.
                indexer["write_ready"] = True
                save_state(state)
                result["write_ready"] = True
                result["flag"] = "FLAG{29029c633f5f6bda}"
                self.record("exception-state", principal="svc-fieldkest-indexer", state="queue-ready")
            # K04.2: flag when data_hex reveals descriptor region (bytes 80-511, hex 160-1023)
            data_hex = result.get("data_hex", "")
            if len(data_hex) >= 1024 and indexer.get("sentinel") == "mutated" and "flag" not in result:
                result["flag"] = "FLAG{54c47a37e2d8714c}"
            indexer["indexes"][index_id] = result
            save_state(state)
            self.record("bundle-index", principal=DEV_USER, **result)
            return self.send_json(201, result)

        complete_match = re.fullmatch(
            r"/api/internal/release-exceptions/([A-Z0-9-]+)/complete", path)
        if complete_match:
            if complete_match.group(1) != EXCEPTION_RECORD_ID: return self.deny(404, "not_found")
            if bearer(self) != INDEXER_WORKER_TOKEN or not indexer.get("write_ready"):
                return self.deny(403)
            data = self.body()
            if data.get("routine") != "recover_exception_queue" or data.get("generation") != indexer["generation"]:
                raise ValueError("routine_arguments_rejected")
            # Derive the dossier encryption key from the K04.3 HMAC.
            # Participant must reproduce this derivation to decrypt encrypted_record.
            k43_hmac = hmac_lib.digest(INDEXER_WORKER_TOKEN.encode(), b"queue-ready", hashlib.sha256)
            derived_key = hashlib.sha256(k43_hmac + b":dossier-key").digest()
            ciphertext = encrypt_record(derived_key, _DOSSIER_PLAINTEXT)
            value = {
                "record_id": EXCEPTION_RECORD_ID,
                "revision": 9,
                "encrypted_record": ciphertext.hex(),
                "key_relation": _DOSSIER_KEY_RELATION,
            }
            value["flag"] = "FLAG{f60f566e45b64ed9}"
            self.record("exception-complete", principal="svc-fieldkest-indexer",
                        record_id=EXCEPTION_RECORD_ID, revision=9)
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



def main() -> None:
    serve_tls(IndexerHandler, int(os.environ.get('PORT', '443')))


if __name__ == '__main__':
    main()
