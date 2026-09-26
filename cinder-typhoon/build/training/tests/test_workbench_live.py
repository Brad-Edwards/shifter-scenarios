#!/usr/bin/env python3
"""Black-box checks for the running Training Workbench service."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://workbench.training"


def request(port: int, path: str, *, headers: dict[str, str] | None = None, method: str = "GET") -> tuple[int, bytes, dict[str, str]]:
    try:
        with urlopen(Request(f"{BASE}:{port}{path}", headers=headers or {}, method=method), timeout=5) as response:
            return response.status, response.read(), dict(response.headers)
    except HTTPError as error:
        with error:
            return error.code, error.read(), dict(error.headers)


class WorkbenchLiveTest(unittest.TestCase):
    def test_static_surfaces_and_head(self) -> None:
        status, body, _ = request(8080, "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Dispatch rehearsal workbench", body)
        status, body, headers = request(8081, "/content/retired.json", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(request(8081, "/absent")[0], 404)

    def test_repository_has_exact_replaced_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run(["git", "clone", "--quiet", f"{BASE}:8080/git/handover.git", temporary], check=True)
            count = subprocess.check_output(["git", "-C", temporary, "rev-list", "--count", "HEAD"], text=True).strip()
            old = subprocess.check_output(["git", "-C", temporary, "show", "HEAD^:handover.md"], text=True)
            current = subprocess.check_output(["git", "-C", temporary, "show", "HEAD:handover.md"], text=True)
        self.assertEqual(count, "2")
        self.assertIn("DL-204", old)
        self.assertNotIn("DL-204", current)

    def test_courier_scope(self) -> None:
        route = "/api/deliveries/DL-204/manifest"
        self.assertEqual(request(8082, route)[0], 401)
        headers = {"Authorization": "Bearer courier_DL204_CR17_4N7Q2M9K"}
        status, body, _ = request(8082, route, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["manifest_id"], "MF-204")
        self.assertEqual(request(8082, "/api/deliveries/DL-219/manifest", headers=headers)[0], 403)
        self.assertEqual(request(8082, route, headers=headers, method="POST")[0], 405)

    def test_diagnostic_decoding_order_and_confinement(self) -> None:
        prefix = "/api/diagnostics/render?delivery_id=DL-204&view="
        status, body, _ = request(8083, prefix + "public/DL-204.json")
        self.assertEqual(status, 200)
        self.assertNotIn("summary_id", json.loads(body))

        status, body, _ = request(8083, prefix + "public/%2E%2E/internal/DL-204.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["summary_id"], "DS-204-I")

        self.assertEqual(request(8083, prefix + "public%2F..%2Finternal%2FDL-204.json")[0], 400)
        self.assertEqual(request(8083, prefix + "public/../../etc/passwd")[0], 400)
        self.assertEqual(request(8083, prefix + "public/absent.json")[0], 404)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    arguments, remaining = parser.parse_known_args()
    BASE = arguments.base.rstrip("/")
    unittest.main(argv=[__file__, *remaining])
