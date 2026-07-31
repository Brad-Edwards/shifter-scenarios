from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
GCP_ROOT = PACK_ROOT / "build/gcp"


def load_renderer():
    path = GCP_ROOT / "render_sdl_realization.py"
    spec = importlib.util.spec_from_file_location("render_sdl_realization", path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load SDL realization renderer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkstationTerminalCaptureTests(unittest.TestCase):
    def test_workstation_producer_token_is_derived_from_sdl_sources(self) -> None:
        realization = load_renderer().build_realization()

        self.assertIn("participant-workstation", realization["evidence_producers"])
        self.assertIn(
            "producer-token-participant-workstation",
            realization["runtime_secret_ids"],
        )
        self.assertIn(
            "participant-workstation/producer-token-participant-workstation",
            realization["secret_access"],
        )
        self.assertIn(
            "telemetry-proof-01/producer-token-participant-workstation",
            realization["secret_access"],
        )

    def test_kali_shell_capture_is_fail_open_and_research_profile_bound(self) -> None:
        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        kali_dockerfile = (
            PACK_ROOT / "assets" / "services" / "Dockerfile.kali"
        ).read_text(encoding="utf-8")
        recorder = (
            PACK_ROOT / "assets" / "services" / "kali-terminal-recorder.py"
        ).read_text(encoding="utf-8")

        self.assertIn("kali-terminal-recorder.py", kali_dockerfile)
        self.assertIn("KEPLEROPS_TERMINAL_CAPTURE_ACTIVE", kali_dockerfile)
        self.assertIn("exec /usr/local/bin/keplerops-terminal-recorder", kali_dockerfile)
        participant_block = re.search(
            r"participant-workstation\)(?P<body>.*?)\n\s+;;",
            template,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(participant_block)
        body = participant_block.group("body") if participant_block else ""
        self.assertIn("producer-token,dst=/run/keplerops/producer-token", body)
        self.assertIn("reset-generation,dst=/run/keplerops/reset-generation", body)
        self.assertIn('-e KEPLEROPS_RANGE_INSTANCE="$RANGE_INSTANCE"', body)
        self.assertIn('-e KEPLEROPS_PARTICIPANT="$PARTICIPANT"', body)
        self.assertIn("KEPLEROPS_RESEARCH_INGEST_URL", body)
        for signal in (
            "terminal_command",
            "terminal_input",
            "terminal_output",
            "process_lifecycle",
        ):
            self.assertIn(f'"{signal}"', recorder)
        self.assertIn("keplerops_research_transport.py", kali_dockerfile)
        self.assertIn("start_sender(", recorder)


if __name__ == "__main__":
    unittest.main()
