from __future__ import annotations

import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


PACK_ROOT = Path(__file__).resolve().parents[2]
GCP_ROOT = PACK_ROOT / "build/gcp"


def load_module(relative: str, name: str):
    path = PACK_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class JupyterResearchCaptureTests(unittest.TestCase):
    def test_capture_event_selects_notebook_and_file_signals(self) -> None:
        capture = load_module(
            "assets/services/keplerops_jupyter_research_capture.py",
            "keplerops_jupyter_research_capture_test",
        )

        notebook = capture._capture_event(
            "analysis.ipynb",
            {"type": "notebook", "content": {"cells": []}},
        )
        file_event = capture._capture_event(
            "notes.txt",
            {"type": "file", "format": "text", "content": "saved"},
        )
        directory = capture._capture_event(
            "folder",
            {"type": "directory", "content": None},
        )

        self.assertEqual(notebook[0], "notebook_content")
        self.assertEqual(notebook[1]["path"], "analysis.ipynb")
        self.assertEqual(file_event[0], "file_content")
        self.assertEqual(file_event[1]["content"], "saved")
        self.assertIsNone(directory)

    def test_server_extension_preserves_existing_hook_and_does_not_modify_model(
        self,
    ) -> None:
        capture = load_module(
            "assets/services/keplerops_jupyter_research_capture.py",
            "keplerops_jupyter_research_capture_hook_test",
        )
        calls: list[str] = []
        saved: list[tuple[str, dict]] = []

        def previous_hook(**kwargs):
            calls.append(kwargs["path"])

        manager = types.SimpleNamespace(pre_save_hook=previous_hook)
        serverapp = types.SimpleNamespace(
            contents_manager=manager,
            log=types.SimpleNamespace(info=lambda *_args: None),
        )
        with (
            mock.patch.object(capture, "_start_worker"),
            mock.patch.object(capture, "_enqueue", lambda signal, event: saved.append((signal, event))),
        ):
            capture._load_jupyter_server_extension(serverapp)
            model = {"type": "file", "format": "text", "content": "participant notes"}
            manager.pre_save_hook(path="notes.txt", model=model, contents_manager=manager)
            manager.pre_save_hook(
                path="bad.bin",
                model={"type": "file", "content": b"\x00"},
                contents_manager=manager,
            )

        self.assertEqual(calls, ["notes.txt", "bad.bin"])
        self.assertEqual(saved[0][0], "file_content")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][1]["content"], "participant notes")
        self.assertEqual(model["content"], "participant notes")

    def test_notebook_runner_capture_is_sdl_backed_and_bootstrap_bound(self) -> None:
        renderer = load_module("build/gcp/render_sdl_realization.py", "render_for_jupyter_capture")
        realization = renderer.build_realization()
        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        dockerfile = (PACK_ROOT / "assets/services/Dockerfile.jupyter").read_text(
            encoding="utf-8"
        )

        self.assertIn("notebook-runner-01", realization["evidence_producers"])
        self.assertIn("producer-token-notebook-runner-01", realization["runtime_secret_ids"])
        self.assertIn("keplerops_jupyter_research_capture.py", dockerfile)
        self.assertIn("jpserver_extensions", dockerfile)
        self.assertIn("PYTHONPATH=/opt/keplerops", dockerfile)
        notebook_block = re.search(
            r"notebook-runner-01\)(?P<body>.*?)\n\s+;;",
            template,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(notebook_block)
        body = notebook_block.group("body") if notebook_block else ""
        self.assertIn("producer-token,dst=/run/keplerops/producer-token", body)
        self.assertIn("reset-generation,dst=/run/keplerops/reset-generation", body)
        self.assertIn('-e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE"', body)
        self.assertIn('-e KEPLEROPS_PARTICIPANT="$PARTICIPANT"', body)
        self.assertIn("KEPLEROPS_RESEARCH_INGEST_URL", body)


if __name__ == "__main__":
    unittest.main()
