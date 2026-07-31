from __future__ import annotations

import base64
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]


def load_module(relative: str, name: str):
    path = PACK_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self) -> bytes:
        return b""


class WorkflowResearchCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capture = load_module(
            "assets/workflows/research_content.py",
            "workflow_research_content_test",
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.token = root / "producer-token"
        self.reset = root / "reset-generation"
        self.token.write_text("producer-token", encoding="utf-8")
        self.reset.write_text("7", encoding="ascii")
        self.capture.PRODUCER_TOKEN_PATH = str(self.token)
        self.capture.RESET_GENERATION_PATH = self.reset
        self.capture._tls_context = lambda: object()
        os.environ["KEPLEROPS_RESEARCH_INGEST_URL"] = "https://research.local"
        os.environ["KEPLEROPS_RANGE_INSTANCE"] = "range-469"
        os.environ["KEPLEROPS_PARTICIPANT"] = "participant-01"

    def captured_request(self, action) -> Request:
        requests: list[Request] = []

        def fake_urlopen(
            request: Request,
            *,
            context: object,
            timeout: float,
        ) -> FakeResponse:
            requests.append(request)
            self.assertIsNotNone(context)
            self.assertEqual(timeout, 2.0)
            return FakeResponse()

        self.capture.urllib.request.urlopen = fake_urlopen
        action()
        self.assertEqual(len(requests), 1)
        return requests[0]

    def decoded_request(self, request: Request) -> dict[str, object]:
        payload = json.loads(request.data.decode("utf-8"))
        payload["content"] = json.loads(payload["content"])
        return payload

    def test_capture_json_posts_workflow_state_with_namespace(self) -> None:
        request = self.captured_request(
            lambda: self.capture.capture_json(
                "workflow_state",
                "a" * 32,
                {"event": "dag_run.started", "workflow_run_id": "manual__1"},
            )
        )
        payload = self.decoded_request(request)

        self.assertEqual(request.full_url, "https://research.local/v1/research/content")
        self.assertEqual(request.headers["X-producer-id"], "distillation-runner-01")
        self.assertEqual(request.headers["X-producer-token"], "producer-token")
        self.assertEqual(payload["signal"], "workflow_state")
        self.assertEqual(payload["trace_id"], "a" * 32)
        self.assertEqual(payload["range_instance"], "range-469")
        self.assertEqual(payload["participant"], "participant-01")
        self.assertEqual(payload["reset_generation"], 7)
        self.assertEqual(payload["content"]["event"], "dag_run.started")
        self.assertIn("timestamp_ns", payload["content"])

    def test_capture_artifact_posts_bounded_base64_payload(self) -> None:
        artifact = b'{"weights":[1,2,3]}'
        request = self.captured_request(
            lambda: self.capture.capture_artifact(
                "b" * 32,
                artifact_id="trn-abc/training-poisoning/adapter.json",
                content=artifact,
                media_type="application/json",
                metadata={"challenge_id": "kep-m07-a"},
            )
        )
        payload = self.decoded_request(request)
        content = payload["content"]

        self.assertEqual(payload["signal"], "artifact_content")
        self.assertEqual(content["event"], "artifact.created")
        self.assertEqual(content["artifact_id"], "trn-abc/training-poisoning/adapter.json")
        self.assertEqual(content["media_type"], "application/json")
        self.assertEqual(content["challenge_id"], "kep-m07-a")
        self.assertEqual(content["encoding"], "base64")
        self.assertEqual(content["data"], base64.b64encode(artifact).decode("ascii"))
        self.assertFalse(content["truncated"])

    def test_workflow_capture_is_sdl_backed_and_container_bound(self) -> None:
        dockerfile = (PACK_ROOT / "assets/workflows/Dockerfile").read_text(
            encoding="utf-8"
        )
        dag = (PACK_ROOT / "assets/workflows/keplerops_distillation.py").read_text(
            encoding="utf-8"
        )
        environment = yaml.safe_load(
            (PACK_ROOT / "sdl/modules/environment.sdl.yaml").read_text(encoding="utf-8")
        )
        research_contract = yaml.safe_load(
            environment["content"]["research-telemetry-contract"]["text"]
        )
        source = next(
            row
            for row in research_contract["sources"]
            if row["id"] == "distillation-runner-01"
        )

        self.assertIn("COPY assets/workflows/research_content.py", dockerfile)
        self.assertIn('"workflow_state"', dag)
        self.assertIn("_capture_workflow_state", dag)
        self.assertIn("capture_artifact(", dag)
        self.assertIn("workflow_state", source["signals"])
        self.assertIn("artifact_content", source["signals"])


if __name__ == "__main__":
    unittest.main()
