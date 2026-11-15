#!/usr/bin/env python3
"""Black-box acceptance for the bounded bundle-indexer progression."""

from __future__ import annotations

import hashlib
import struct
import unittest

from test_platform_live import call


def build_fki(alloc_entries: int, index_entries: int, payload: bytes) -> bytes:
    return b"FKI\x01" + struct.pack("<HH", alloc_entries, index_entries) + payload


class K04LiveTest(unittest.TestCase):
    def test_01_controlled_corruption_and_liveness(self) -> None:
        # index_entries=9, alloc_entries=8: 72 bytes into 64-byte body, 8 into sentinel
        exploit = build_fki(8, 9, b"\xff" * 72)
        changed = call("indexer.keplerops.test", "/api/indexes", method="POST",
                       body={"bundle_hex": exploit.hex()}, expected=201)
        self.assertEqual((changed["sentinel"], changed["service_alive"]), ("mutated", True))
        self.assertEqual(changed["native_parser"], "fieldkest-bundle-indexer/2.0.0")
        # Normal bundle (8 entries, fills body exactly) stays stable.
        normal = build_fki(0, 8, b"\x41" * 64)
        norm = call("indexer.keplerops.test", "/api/indexes", method="POST",
                    body={"bundle_hex": normal.hex()}, expected=201)
        self.assertTrue(norm["service_alive"])
        # Malformed bundle (wrong magic) is rejected.
        bad = b"BAD\x01" + b"\x00" * 12
        call("indexer.keplerops.test", "/api/indexes", method="POST",
             body={"bundle_hex": bad.hex()}, expected=422)

    def test_02_disclosure_scoped_write_and_completion(self) -> None:
        descriptor = call("indexer.keplerops.test", "/api/indexes", method="POST",
                          body={"operation": "runtime-descriptor", "sentinel": "mutated"})
        self.assertEqual(descriptor["protected_object_marker"], "release-exception-state")
        integrity = hashlib.sha256(f"{descriptor['process_generation']}:queue-ready".encode()).hexdigest()
        updated = call("indexer.keplerops.test", "/api/internal/release-exceptions/state",
                       method="PATCH", body={"state": "queue-ready", "integrity": integrity},
                       auth=descriptor["worker_lease"])
        self.assertEqual(updated["integrity"], integrity)
        bad = call("indexer.keplerops.test", "/api/internal/release-exceptions/state",
                   method="PATCH", body={"state": "queue-ready", "integrity": "wrong"},
                   auth=descriptor["worker_lease"], expected=422)
        self.assertEqual(bad["error"], "integrity_rejected")
        result = call("indexer.keplerops.test", "/api/internal/release-exceptions/REL-EXC-2841/complete",
                      method="POST",
                      body={"routine": "recover_exception_queue", "generation": descriptor["process_generation"]},
                      auth=descriptor["worker_lease"])
        self.assertEqual((result["service_identity"], result["dossier"]), ("svc-fieldkest-indexer", "BLD-REL-742"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
