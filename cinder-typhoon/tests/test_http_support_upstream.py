"""Focused tests for stable upstream JSON handling."""

from __future__ import annotations

from email.message import Message
from io import BytesIO
import importlib.util
from pathlib import Path
import ssl
import sys
import unittest
from unittest import mock
from urllib import error as urlerror
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build/keplerops/runtime/http_support.py"
SPEC = importlib.util.spec_from_file_location("cinder_http_support_upstream", MODULE_PATH)
assert SPEC and SPEC.loader
http_support = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = http_support
SPEC.loader.exec_module(http_support)


class Response:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self.payload = payload

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, maximum_bytes: int) -> bytes:
        return self.payload[:maximum_bytes]


class OpenJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = urlrequest.Request("https://upstream.test/")
        self.context = ssl.create_default_context()

    def test_returns_successful_json_object(self) -> None:
        with mock.patch.object(http_support.urlrequest, "urlopen", return_value=Response(202, b'{"receipt_id":"R1"}')):
            self.assertEqual(
                http_support.open_json(self.request, self.context, timeout=1),
                (202, {"receipt_id": "R1"}),
            )

    def test_returns_structured_http_error(self) -> None:
        headers = Message()
        headers["Content-Type"] = "application/json"
        failure = urlerror.HTTPError(
            self.request.full_url,
            422,
            "unprocessable",
            headers,
            BytesIO(b'{"error":"diagnostic_output_mismatch"}'),
        )
        with mock.patch.object(http_support.urlrequest, "urlopen", side_effect=failure):
            self.assertEqual(
                http_support.open_json(self.request, self.context, timeout=1),
                (422, {"error": "diagnostic_output_mismatch"}),
            )

    def test_classifies_transport_and_invalid_json_failures(self) -> None:
        cases = [
            (urlerror.URLError("down"), http_support.UpstreamUnavailable),
            (Response(200, b"not json"), http_support.UpstreamInvalidResponse),
            (Response(200, b"[]"), http_support.UpstreamInvalidResponse),
        ]
        for returned, expected in cases:
            with self.subTest(expected=expected.__name__):
                patch = mock.patch.object(
                    http_support.urlrequest,
                    "urlopen",
                    side_effect=returned if isinstance(returned, Exception) else None,
                    return_value=None if isinstance(returned, Exception) else returned,
                )
                with patch, self.assertRaises(expected):
                    http_support.open_json(self.request, self.context, timeout=1)


if __name__ == "__main__":
    unittest.main()
