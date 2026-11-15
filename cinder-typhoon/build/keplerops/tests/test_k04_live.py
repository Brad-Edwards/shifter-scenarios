#!/usr/bin/env python3
"""Black-box acceptance for the bounded bundle-indexer progression."""

from __future__ import annotations

import hashlib
import hmac
import struct
import unittest

from test_platform_live import call


EXCEPTION_RECORD_ID = "REL-EXC-2841"
SIGNER_HISTORY_REPO = "fieldkest/release-signer-history"
GITEA_BASE = "https://source.keplerops.test"


def build_fki(alloc_entries: int, index_entries: int, payload: bytes) -> bytes:
    return b"FKI\x01" + struct.pack("<HH", alloc_entries, index_entries) + payload


class K04LiveTest(unittest.TestCase):
    def test_01_controlled_corruption_and_liveness(self) -> None:
        # K04.1: index_entries=9, alloc_entries=0: 72 bytes overflows 64-byte body
        exploit = build_fki(0, 9, b"\xff" * 72)
        changed = call("indexer.keplerops.test", "/api/indexes", method="POST",
                       body={"bundle_hex": exploit.hex()}, expected=201)
        self.assertEqual((changed["sentinel"], changed["service_alive"]), ("mutated", True))
        self.assertEqual(changed["native_parser"], "fieldkest-bundle-indexer/2.0.0")
        # Normal bundle stays stable.
        normal = build_fki(0, 8, b"\x41" * 64)
        norm = call("indexer.keplerops.test", "/api/indexes", method="POST",
                    body={"bundle_hex": normal.hex()}, expected=201)
        self.assertTrue(norm["service_alive"])
        # Malformed bundle rejected.
        bad = b"BAD\x01" + b"\x00" * 12
        call("indexer.keplerops.test", "/api/indexes", method="POST",
             body={"bundle_hex": bad.hex()}, expected=422)

    def test_02_derive_worker_authority_from_gitea(self) -> None:
        # K04.2: read exception record and signer-history from Gitea; derive worker token.
        exception_ref = call(
            "source.keplerops.test",
            f"/api/v1/repos/{SIGNER_HISTORY_REPO}/raw/release-exception-{EXCEPTION_RECORD_ID}.json",
        )
        self.assertEqual(exception_ref["record_id"], EXCEPTION_RECORD_ID)
        self.assertIn("state_route", exception_ref)
        self.assertIn("authority_derivation", exception_ref)

        signer_history = call(
            "source.keplerops.test",
            f"/api/v1/repos/{SIGNER_HISTORY_REPO}/raw/signer-history.json",
        )
        passphrase_half = signer_history["passphrase_half"]
        worker_token = hmac.new(
            passphrase_half.encode(), EXCEPTION_RECORD_ID.encode(), hashlib.sha256
        ).hexdigest()
        # Stash for K04.3
        self.__class__._worker_token = worker_token
        self.__class__._generation = exception_ref["process_generation"]

    def test_03_scoped_write_and_completion(self) -> None:
        # K04.3: use the derived worker token to write the exception state.
        lease = getattr(self.__class__, '_worker_token', None)
        generation = getattr(self.__class__, '_generation', 1)
        self.assertIsNotNone(lease)
        integrity = hashlib.sha256(f"{generation}:queue-ready".encode()).hexdigest()
        updated = call(
            "indexer.keplerops.test",
            "/api/internal/release-exceptions/state",
            method="PATCH",
            body={"state": "queue-ready", "integrity": integrity},
            auth=lease,
        )
        self.assertEqual(updated["integrity"], integrity)
        # Wrong integrity rejected.
        bad = call(
            "indexer.keplerops.test",
            "/api/internal/release-exceptions/state",
            method="PATCH",
            body={"state": "queue-ready", "integrity": "wrong"},
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
