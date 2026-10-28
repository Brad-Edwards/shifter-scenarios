#!/usr/bin/env python3
"""Participant-side topology and opening-surface checks."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
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
        self.assertIn("use\n`/tmp` for clones, downloads, and other working files", text)
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

    def test_published_workbench_clone_command_runs_from_participant_home(self) -> None:
        with urlopen("http://workbench.training:8080/", timeout=3) as response:
            page = response.read().decode("utf-8")
        match = re.search(r"```text\n(git clone [^\n]+)\n```", page)
        self.assertIsNotNone(match, "workbench page must publish its clone command")
        command = shlex.split(match.group(1))
        self.assertEqual(command[:2], ["git", "clone"])
        self.assertEqual(command[-1], "/tmp/handover")

        subprocess.run(
            command,
            cwd="/home/cinder",
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        repository = Path("/tmp/handover")
        count = subprocess.check_output(
            ["git", "-C", str(repository), "rev-list", "--count", "HEAD"],
            text=True,
        ).strip()
        retained = subprocess.check_output(
            ["git", "-C", str(repository), "show", "HEAD^:handover.md"],
            text=True,
        )
        self.assertEqual(count, "2")
        self.assertIn("DL-204", retained)

    def test_segment_has_no_outbound_route(self) -> None:
        with self.assertRaises(OSError):
            socket.create_connection(("1.1.1.1", 80), timeout=1)


if __name__ == "__main__":
    unittest.main()
