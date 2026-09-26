#!/usr/bin/env python3
"""Black-box checks for the running Training State service."""

from __future__ import annotations

import argparse
import json
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://state.training:8080"


def request(path: str, *, body: object | None = None, method: str = "GET") -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    try:
        with urlopen(Request(BASE + path, data=data, headers={"Content-Type": "application/json"}, method=method), timeout=5) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        with error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else None


class StateLiveTest(unittest.TestCase):
    def test_static_records_are_separate_from_practice(self) -> None:
        self.assertEqual(request("/captures/volume.json")[1]["tank_id"], "CT-01")
        self.assertEqual(request("/replay/report.json")[1]["tank_id"], "RT-02")
        self.assertEqual(request("/api/practice/state")[1]["tank_id"], "PT-01")

    def test_hold_transfer_observations_and_idempotency(self) -> None:
        initial = request("/api/practice/state")[1]
        self.assertEqual(initial["status_word"], 5)
        self.assertEqual(request("/api/practice/transfer", method="POST", body={"request_id": "blocked-1", "quantity_l": 20})[0], 409)
        self.assertEqual(request("/api/practice/hold", method="POST", body={"request_id": "hold-clear-1", "active": False})[0], 200)
        status, receipt = request("/api/practice/transfer", method="POST", body={"request_id": "move-1", "quantity_l": 20})
        self.assertEqual(status, 202)
        self.assertEqual(receipt["result"], "accepted")
        self.assertEqual(request("/api/practice/hold", method="POST", body={"request_id": "hold-during-1", "active": True})[0], 409)
        deadline = time.time() + 3
        while time.time() < deadline:
            final = request("/api/practice/state")[1]
            if final["outlet_position"] == "closed":
                break
            time.sleep(0.1)
        self.assertEqual(final["observed_volume_l"], initial["observed_volume_l"] - 20)
        self.assertEqual(final["status_word"], 1)
        self.assertEqual(request("/api/practice/transfer", method="POST", body={"request_id": "move-1", "quantity_l": 20})[0], 202)
        self.assertEqual(request("/api/practice/transfer", method="POST", body={"request_id": "move-1", "quantity_l": 21})[0], 409)
        observations = request("/api/practice/observations")[1]["observations"]
        selected = [row for row in observations if row["request_id"] == "move-1"]
        self.assertEqual(len(selected), 2)
        self.assertFalse(selected[-1]["outlet_position"] == "open")
        self.assertTrue(selected[-1]["terminal"])

    def test_invalid_request_does_not_reserve_id(self) -> None:
        self.assertEqual(request("/api/practice/hold", method="POST", body={"request_id": "bad-then-good", "active": "false"})[0], 400)
        self.assertEqual(request("/api/practice/hold", method="POST", body={"request_id": "bad-then-good", "active": False})[0], 200)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    arguments, remaining = parser.parse_known_args()
    BASE = arguments.base.rstrip("/")
    unittest.main(argv=[__file__, *remaining])
