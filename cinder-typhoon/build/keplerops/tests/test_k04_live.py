#!/usr/bin/env python3
"""Black-box acceptance for the bounded bundle-indexer progression."""

from __future__ import annotations

import hashlib
import unittest

from test_platform_live import call


class K04LiveTest(unittest.TestCase):
    def test_01_controlled_corruption_and_liveness(self) -> None:
        body = b"A" * 32 + b"FIELDKEST-SENTNL"
        changed = call("indexer.keplerops.test", "/api/indexes", method="POST", body={"allocated_length": 32, "body_hex": body.hex()}, expected=201)
        self.assertEqual((changed["sentinel"], changed["service_alive"]), ("mutated", True))
        self.assertEqual(changed["native_parser"], "fieldkest-bundle-indexer/1.8.0")
        normal = call("indexer.keplerops.test", "/api/indexes", method="POST", body={"allocated_length": 16, "body_hex": (b"normal-index-row").hex()}, expected=201)
        self.assertTrue(normal["service_alive"])
        crash = call("indexer.keplerops.test", "/api/indexes", method="POST", body={"allocated_length": 8, "body_hex": (b"not-a-controlled-overflow").hex()}, expected=422)
        self.assertEqual(crash["error"], "bundle_rejected")

    def test_02_disclosure_scoped_write_and_completion(self) -> None:
        descriptor = call("indexer.keplerops.test", "/api/indexes", method="POST", body={"operation": "runtime-descriptor", "sentinel": "mutated"})
        self.assertEqual(descriptor["protected_object_marker"], "release-exception-state")
        integrity = hashlib.sha256(f"{descriptor['process_generation']}:queue-ready".encode()).hexdigest()
        updated = call("indexer.keplerops.test", "/api/internal/release-exceptions/state", method="PATCH", body={"state": "queue-ready", "integrity": integrity}, auth=descriptor["worker_lease"])
        self.assertEqual(updated["integrity"], integrity)
        bad = call("indexer.keplerops.test", "/api/internal/release-exceptions/state", method="PATCH", body={"state": "queue-ready", "integrity": "wrong"}, auth=descriptor["worker_lease"], expected=422)
        self.assertEqual(bad["error"], "integrity_rejected")
        result = call("indexer.keplerops.test", "/api/internal/release-exceptions/REL-EXC-2841/complete", method="POST", body={"routine": "recover_exception_queue", "generation": descriptor["process_generation"]}, auth=descriptor["worker_lease"])
        self.assertEqual((result["service_identity"], result["dossier"]), ("svc-fieldkest-indexer", "BLD-REL-742"))


if __name__ == "__main__": unittest.main(verbosity=2)
