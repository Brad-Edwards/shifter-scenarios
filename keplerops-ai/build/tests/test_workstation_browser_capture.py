from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]


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


def seed_chromium_history(path: Path) -> None:
    path.parent.mkdir(parents=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE urls (
              id INTEGER PRIMARY KEY,
              url TEXT NOT NULL,
              title TEXT,
              visit_count INTEGER,
              typed_count INTEGER
            );
            CREATE TABLE visits (
              id INTEGER PRIMARY KEY,
              url INTEGER NOT NULL,
              visit_time INTEGER,
              transition INTEGER,
              visit_duration INTEGER
            );
            CREATE TABLE downloads (
              id INTEGER PRIMARY KEY,
              target_path TEXT,
              tab_url TEXT,
              mime_type TEXT,
              start_time INTEGER,
              end_time INTEGER,
              state INTEGER,
              total_bytes INTEGER
            );
            """
        )
        connection.execute(
            "INSERT INTO urls VALUES (1, ?, ?, 1, 1)",
            ("https://gateway.keplerops.lab/model-evasion", "Model Evasion"),
        )
        connection.execute(
            "INSERT INTO visits VALUES (10, 1, 13380163200000000, 805306368, 12000)"
        )
        connection.execute(
            "INSERT INTO downloads VALUES (3, ?, ?, ?, 13380163201000000, "
            "13380163202000000, 1, 42)",
            (
                "/home/kasm-user/Downloads/report.json",
                "https://gateway.keplerops.lab/export",
                "application/json",
            ),
        )
        connection.commit()
    finally:
        connection.close()


class WorkstationBrowserCaptureTests(unittest.TestCase):
    def test_chromium_opens_at_agent_control_without_profile_mutation(self) -> None:
        dockerfile = (PACK_ROOT / "assets/services/Dockerfile.kali").read_text(
            encoding="utf-8"
        )
        policy = json.loads(
            (PACK_ROOT / "assets/services/chromium-startup-policy.json").read_text(
                encoding="utf-8"
            )
        )
        launcher = (PACK_ROOT / "assets/services/chromium.desktop").read_text(
            encoding="utf-8"
        )
        start_url = "https://inference-gateway.keplerops.lab/agent-control"

        self.assertEqual(policy["HomepageLocation"], start_url)
        self.assertEqual(policy["RestoreOnStartup"], 4)
        self.assertEqual(policy["RestoreOnStartupURLs"], [start_url])
        self.assertIn(f"Exec=/usr/bin/chromium --new-window {start_url} %U", launcher)
        self.assertIn("/etc/chromium/policies/managed/keplerops-startup.json", dockerfile)
        self.assertIn("/home/kasm-default-profile/.config/xfce4/panel/launcher-6/", dockerfile)

    def test_chromium_history_emits_navigation_and_download_events(self) -> None:
        capture = load_module(
            "assets/services/kali-browser-recorder.py",
            "kali_browser_recorder_test",
        )
        events: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history = root / ".config/chromium/Default/History"
            seed_chromium_history(history)
            capture.HOME_ROOT = root
            capture.CHROMIUM_HISTORY = (history,)
            capture.FIREFOX_ROOT = root / ".mozilla/firefox"
            capture._enqueue = events.append

            state = capture.BrowserState({}, {}, {})
            capture.scan_once(state)

        self.assertEqual([event["event"] for event in events], ["navigation", "download"])
        self.assertEqual(events[0]["browser"], "chromium")
        self.assertEqual(events[0]["url"], "https://gateway.keplerops.lab/model-evasion")
        self.assertEqual(events[0]["title"], "Model Evasion")
        self.assertEqual(events[0]["profile"], ".config/chromium/Default/History")
        self.assertEqual(events[1]["target_path"], "/home/kasm-user/Downloads/report.json")
        self.assertEqual(events[1]["mime_type"], "application/json")
        self.assertIn("trace_id", events[0])

    def test_browser_capture_is_sdl_backed_and_startup_bound(self) -> None:
        dockerfile = (PACK_ROOT / "assets/services/Dockerfile.kali").read_text(
            encoding="utf-8"
        )
        startup = (PACK_ROOT / "assets/services/kali-startup.sh").read_text(
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
            if row["id"] == "participant-workstation"
        )

        self.assertIn("kali-browser-recorder.py", dockerfile)
        self.assertIn("keplerops_research_transport.py", dockerfile)
        self.assertIn("keplerops-browser-recorder", startup)
        self.assertIn("browser_interaction", source["signals"])

    def test_camera_webrtc_helper_is_real_browser_bound(self) -> None:
        dockerfile = (PACK_ROOT / "assets/services/Dockerfile.kali").read_text(
            encoding="utf-8"
        )
        helper = (
            PACK_ROOT / "assets/services/kali-camera-webrtc-proof.py"
        ).read_text(encoding="utf-8")
        self.assertIn("archive.kali.org/archive-keyring.gpg", dockerfile)
        self.assertIn("sha256sum --check --strict", dockerfile)
        self.assertIn("apt-get install --yes --no-install-recommends chromium", dockerfile)
        self.assertIn("kali-camera-webrtc-proof.py", dockerfile)
        self.assertIn("keplerops-camera-webrtc-proof", dockerfile)
        self.assertIn("RTCPeerConnection", helper)
        self.assertIn("createDataChannel", helper)
        self.assertIn("canvas.captureStream(5)", helper)
        self.assertIn("--disable-features=WebRtcHideLocalIpsWithMdns", helper)
        self.assertIn("/v1/sessions/'+session.session_id+'/close", helper)
        self.assertNotIn("/frames", helper)
        # kep-m08-i (physical sensor evasion) was removed from the software proof
        # scope in 2fd67d1 (it needs an authentic labgrid bench), so no in-scope
        # rehearsal exercises the camera helper. Its real browser binding stays
        # enforced above via the Dockerfile install and the WebRTC helper asserts.


if __name__ == "__main__":
    unittest.main()
