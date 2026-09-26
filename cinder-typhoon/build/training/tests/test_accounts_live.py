#!/usr/bin/env python3
"""Black-box checks for the running Training Accounts service."""

from __future__ import annotations

import argparse
from http.cookies import SimpleCookie
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://accounts.training:8080"


def request(path: str, *, body: object | None = None, headers: dict[str, str] | None = None, method: str = "GET") -> tuple[int, bytes, dict[str, str]]:
    data = None if body is None else json.dumps(body).encode()
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    try:
        with urlopen(Request(BASE + path, data=data, headers=request_headers, method=method), timeout=5) as response:
            return response.status, response.read(), dict(response.headers)
    except HTTPError as error:
        with error:
            return error.code, error.read(), dict(error.headers)


class AccountsLiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        status, body, headers = request(
            "/api/recovery/redeem",
            method="POST",
            body={"account": "rhea.moss", "case_fragment": "CASE-7Q4M", "staff_detail": "Blue cabinet 17"},
        )
        if status == 201:
            cls.token = json.loads(body)["session"]
            cls.cookie = headers["Set-Cookie"].split(";", 1)[0]
        else:
            raise AssertionError("live test requires a fresh Accounts state volume")

    def test_public_directory_and_object_boundary(self) -> None:
        self.assertEqual(request("/directory/")[0], 200)
        status, body, _ = request("/api/directory/staff/STF-204/assignment")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["staff_detail"], "Blue cabinet 17")
        self.assertEqual(request("/api/directory/staff/STF-317/assignment")[0], 403)
        self.assertEqual(request("/api/directory/staff/STF-999/assignment")[0], 404)

    def test_lookup_response_classes(self) -> None:
        expected = {"rhea.moss": 200, "mina.cho": 410, "owen.pike": 404}
        for account, status in expected.items():
            self.assertEqual(request("/api/recovery/lookup", method="POST", body={"account": account})[0], status)

    def test_recovery_is_single_redemption(self) -> None:
        body = {"account": "rhea.moss", "case_fragment": "CASE-7Q4M", "staff_detail": "Blue cabinet 17"}
        self.assertEqual(request("/api/recovery/redeem", method="POST", body=body)[0], 409)
        wrong = {**body, "staff_detail": "Blue cabinet 18"}
        self.assertEqual(request("/api/recovery/redeem", method="POST", body=wrong)[0], 403)

    def test_session_and_cross_assignment_scope(self) -> None:
        self.assertEqual(request("/api/handover")[0], 401)
        bearer = {"Authorization": f"Bearer {self.token}"}
        status, body, _ = request("/api/handover", headers=bearer)
        self.assertEqual(status, 200)
        self.assertIn(b"ASG-317", body)
        status, body, _ = request("/api/assignments", headers={"Cookie": self.cookie})
        self.assertEqual(status, 200)
        self.assertEqual([row["assignment_id"] for row in json.loads(body)["assignments"]], ["ASG-204"])
        status, body, _ = request("/api/assignments/ASG-317/brief", headers=bearer)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["owner"], "dax.hale")
        self.assertEqual(request("/api/assignments/ASG-999/brief", headers=bearer)[0], 404)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    arguments, remaining = parser.parse_known_args()
    BASE = arguments.base.rstrip("/")
    unittest.main(argv=[__file__, *remaining])
