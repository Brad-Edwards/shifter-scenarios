#!/usr/bin/env python3
"""Black-box acceptance for the bounded bundle-indexer progression."""

from __future__ import annotations

import hashlib
import json
import struct
import unittest

from test_platform_live import call


EXCEPTION_RECORD_ID = "REL-EXC-2841"
DESCRIPTOR_OFFSET = 80   # bytes 80-127 of the arena
DESCRIPTOR_SIZE = 48


def build_fki(alloc_entries: int, index_entries: int, payload: bytes) -> bytes:
    return b"FKI\x01" + struct.pack("<HH", alloc_entries, index_entries) + payload


class K04LiveTest(unittest.TestCase):
    def test_01_controlled_corruption_and_liveness(self) -> None:
        # K04.1: sentinel mutation via .fki boundary overflow
        exploit = build_fki(0, 9, b"\xff" * 72)
        changed = call("indexer.keplerops.test", "/api/indexes", method="POST",
                       body={"bundle_hex": exploit.hex()}, expected=201)
        self.assertEqual((changed["sentinel"], changed["service_alive"]), ("mutated", True))
        self.assertEqual(changed["native_parser"], "fieldkest-bundle-indexer/2.0.0")
        self.assertIn("data_hex", changed)
        # Normal bundle stays stable.
        normal = build_fki(0, 8, b"\x41" * 64)
        norm = call("indexer.keplerops.test", "/api/indexes", method="POST",
                    body={"bundle_hex": normal.hex()}, expected=201)
        self.assertTrue(norm["service_alive"])
        # Malformed bundle rejected.
        bad = b"BAD\x01" + b"\x00" * 12
        call("indexer.keplerops.test", "/api/indexes", method="POST",
             body={"bundle_hex": bad.hex()}, expected=422)

    def test_02_extended_read_discloses_runtime_descriptor(self) -> None:
        # K04.2: extend to ie=64, ae=432 (datalen=512) to include descriptor at bytes 80-511.
        # The binary reads the arena (512 bytes) before each memcpy; after K04.1 bytes
        # 80-511 hold the service-written descriptor.  No conditional: data_hex covers datalen.
        extended = build_fki(432, 64, b"\xff" * 72 + b"\x00" * 440)
        disclosed = call("indexer.keplerops.test", "/api/indexes", method="POST",
                         body={"bundle_hex": extended.hex()}, expected=201)
        self.assertIn("data_hex", disclosed)
        data_hex = disclosed["data_hex"]
        self.assertEqual(len(data_hex), 1024)  # 512 bytes → 1024 hex chars
        # Descriptor at bytes 80-511 → hex chars 160-1023
        descriptor_hex = data_hex[160:1024]
        descriptor = json.loads(bytes.fromhex(descriptor_hex).rstrip(b'\x00'))
        self.assertEqual(descriptor.get("schema"), "fieldkest.runtime-descriptor/v1")
        self.assertIn("worker_session", descriptor)
        # Stash for K04.3
        self.__class__._descriptor = descriptor

    def test_03_scoped_write_and_completion(self) -> None:
        # K04.3: use the worker_session from K04.2 to write the exception state.
        descriptor = getattr(self.__class__, '_descriptor', {})
        lease = descriptor.get("worker_session")
        generation = descriptor.get("process_generation", 1)
        self.assertIsNotNone(lease)
        integrity = hashlib.sha256(f"{generation}:queue-ready".encode()).hexdigest()
        updated = call(
            "indexer.keplerops.test", "/api/internal/release-exceptions/state",
            method="PATCH", body={"state": "queue-ready", "integrity": integrity},
            auth=lease,
        )
        self.assertEqual(updated["integrity"], integrity)
        # Wrong integrity rejected.
        bad = call(
            "indexer.keplerops.test", "/api/internal/release-exceptions/state",
            method="PATCH", body={"state": "queue-ready", "integrity": "wrong"},
            auth=lease, expected=422,
        )
        self.assertEqual(bad["error"], "integrity_rejected")
        # K04.4: complete the routine.
        result = call(
            "indexer.keplerops.test",
            f"/api/internal/release-exceptions/{EXCEPTION_RECORD_ID}/complete",
            method="POST",
            body={"routine": "recover_exception_queue", "generation": generation},
            auth=lease,
        )
        self.assertEqual((result["service_identity"], result["dossier"]),
                         ("svc-fieldkest-indexer", "BLD-REL-742"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
