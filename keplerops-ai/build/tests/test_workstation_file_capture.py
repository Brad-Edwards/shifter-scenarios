from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
GCP_ROOT = PACK_ROOT / "build/gcp"


def load_module(relative: str, name: str):
    path = PACK_ROOT / relative
    sys.path.insert(0, str(PACK_ROOT / "assets/services"))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class WorkstationFileCaptureTests(unittest.TestCase):
    def test_file_event_captures_bounded_content_and_deletions(self) -> None:
        capture = load_module(
            "assets/services/kali-file-recorder.py",
            "kali_file_recorder_test",
        )
        events: list[tuple[str, dict[str, object]]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "Downloads" / "notes.txt"
            path.parent.mkdir()
            path.write_text("participant note", encoding="utf-8")
            capture.HOME_ROOT = root
            capture._enqueue = lambda signal, event: events.append((signal, event))

            capture._emit_file(str(path), "created", path.stat().st_size, path.stat().st_mtime_ns)
            path.unlink()
            capture._emit_file(str(path), "deleted")

        self.assertEqual(events[0][0], "file_content")
        self.assertEqual(events[0][1]["path"], "Downloads/notes.txt")
        self.assertEqual(events[0][1]["event"], "created")
        self.assertEqual(events[0][1]["encoding"], "base64")
        self.assertFalse(events[0][1]["truncated"])
        self.assertIn("data", events[0][1])
        self.assertEqual(events[1][1]["event"], "deleted")
        self.assertNotIn("data", events[1][1])

    def test_kali_file_capture_is_sdl_backed_and_startup_bound(self) -> None:
        renderer = load_module("build/gcp/render_sdl_realization.py", "render_for_file_capture")
        realization = renderer.build_realization()
        dockerfile = (PACK_ROOT / "assets/services/Dockerfile.kali").read_text(
            encoding="utf-8"
        )
        startup = (PACK_ROOT / "assets/services/kali-startup.sh").read_text(
            encoding="utf-8"
        )
        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        environment = yaml.safe_load(
            (PACK_ROOT / "sdl/modules/environment.sdl.yaml").read_text(encoding="utf-8")
        )
        research_contract = yaml.safe_load(
            environment["content"]["research-telemetry-contract"]["text"]
        )
        participant_source = next(
            row for row in research_contract["sources"]
            if row["id"] == "participant-workstation"
        )

        self.assertIn("participant-workstation", realization["evidence_producers"])
        self.assertIn("kali-file-recorder.py", dockerfile)
        self.assertIn("keplerops-kasm-startup", dockerfile)
        self.assertIn("keplerops-file-recorder", startup)
        self.assertIn("exec /dockerstartup/kasm_default_profile.sh", startup)
        self.assertIn("file_content", participant_source["signals"])
        participant_block = re.search(
            r"participant-workstation\)(?P<body>.*?)\n\s+;;",
            template,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(participant_block)
        body = participant_block.group("body") if participant_block else ""
        self.assertIn("--entrypoint /usr/local/bin/keplerops-kasm-startup", body)
        self.assertIn("producer-token,dst=/run/keplerops/producer-token", body)


if __name__ == "__main__":
    unittest.main()
