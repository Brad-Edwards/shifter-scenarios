#!/usr/bin/env python3
"""Participant-side topology and opening-surface checks."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import stat
import unittest
from urllib.request import urlopen


class TopologyLiveTest(unittest.TestCase):
    def test_exact_training_addresses(self) -> None:
        expected = {
            "kali.training": "10.77.40.10",
            "workbench.training": "10.77.40.20",
            "accounts.training": "10.77.40.30",
            "developer.training": "10.77.40.40",
            "state.training": "10.77.40.50",
        }
        for name, address in expected.items():
            self.assertEqual(socket.gethostbyname(name), address)

    def test_opening_document_and_all_desks(self) -> None:
        path = Path("/home/cinder/TRAINING.md")
        self.assertTrue(path.is_file())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444)
        text = path.read_text(encoding="utf-8")
        for name in ("workbench", "accounts", "developer", "state"):
            self.assertIn(f"{name}.training", text)
        for url in (
            "http://workbench.training:8080/",
            "http://accounts.training:8080/",
            "http://developer.training:8080/",
            "http://state.training:8080/",
        ):
            with urlopen(url, timeout=3) as response:
                self.assertEqual(response.status, 200)

    def test_segment_has_no_outbound_route(self) -> None:
        with self.assertRaises(OSError):
            socket.create_connection(("1.1.1.1", 80), timeout=1)


if __name__ == "__main__":
    unittest.main()
