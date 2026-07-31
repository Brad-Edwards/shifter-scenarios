"""Focused tests for the operator launch research-profile switch."""

from __future__ import annotations

from pathlib import Path
import unittest


PACK_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = PACK_ROOT / "build"


class LaunchResearchProfileTests(unittest.TestCase):
    def test_launch_exposes_full_content_profile_without_ctfd_selection(self) -> None:
        launch = (BUILD_ROOT / "launch.sh").read_text(encoding="utf-8")

        self.assertIn("--research-profile", launch)
        self.assertIn("RESEARCH_PROFILE=off", launch)
        self.assertIn('research_profile == "full-content"', launch)
        self.assertIn('"telemetry_capture_signals"', launch)
        self.assertNotIn("CTFD_PROFILE", launch)
        for signal in (
            "prompt",
            "completion",
            "tool_call",
            "tool_result",
            "terminal_command",
            "terminal_input",
            "terminal_output",
            "process_lifecycle",
            "browser_interaction",
            "notebook_content",
            "file_content",
            "workflow_state",
            "artifact_content",
            "http_body",
        ):
            self.assertIn(f'"{signal}": True', launch)


if __name__ == "__main__":
    unittest.main()
