from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-camera"


class PlatformCameraSourceTests(unittest.TestCase):
    def test_container_and_direct_dependencies_are_immutable(self) -> None:
        dockerfile = (ASSET / "Dockerfile").read_text(encoding="utf-8")
        requirements = (ASSET / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("python@sha256:", dockerfile)
        self.assertNotIn("python:", dockerfile)
        self.assertNotIn("--chown=65532:65532", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn("EXPOSE 8480/tcp", dockerfile)
        self.assertIn('VOLUME ["/var/lib/keplerops-platform-camera"]', dockerfile)
        self.assertIn("PLATFORM_CAMERA_ALLOW_PLAINTEXT=0", dockerfile)
        self.assertIn('ENTRYPOINT ["./entrypoint.sh"]', dockerfile)
        direct = {
            "aiortc==1.15.0",
            "av==17.1.0",
            "fastapi==0.139.2",
            "httpx==0.28.1",
            "pillow==12.3.0",
            "uvicorn==0.51.0",
        }
        pins = set(requirements.splitlines())
        self.assertTrue(direct <= pins)
        self.assertGreaterEqual(len(pins), 25)
        for pin in pins:
            self.assertRegex(
                pin, r"^[A-Za-z0-9_-]+==[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.-]+)?$"
            )

    def test_python_sources_compile(self) -> None:
        for path in ASSET.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_browser_uses_permissioned_live_webrtc_without_file_fallback(self) -> None:
        html = (ASSET / "static/index.html").read_text(encoding="utf-8")
        javascript = (ASSET / "static/app.js").read_text(encoding="utf-8")
        combined = (html + javascript).lower()
        self.assertIn("navigator.mediadevices.getusermedia", combined)
        self.assertIn("new rtcpeerconnection", combined)
        self.assertIn("createdatachannel", combined)
        self.assertIn("getvideotracks", combined)
        self.assertIn("frameRate: { ideal: 5, max: 5 }", javascript)
        self.assertNotIn('type="file"', combined)
        self.assertNotIn("filereader", combined)
        self.assertNotIn("getdisplaymedia", combined)
        self.assertNotIn("capturestream", combined)
        self.assertNotIn("http://", javascript)
        self.assertNotIn("https://", javascript)
        self.assertIn('error?.message || "Live camera start failed"', javascript)
        self.assertIn('channel?.readyState !== "open"', javascript)

    def test_server_requires_fresh_track_frames_and_rejects_uploads(self) -> None:
        app = (ASSET / "app.py").read_text(encoding="utf-8")
        transport = (ASSET / "webrtc.py").read_text(encoding="utf-8")
        for contract in (
            '@peer.on("track")',
            "frame = await track.recv()",
            "session.pending_frames.append(pending)",
            "received frame was not fresh",
            "frame.pts",
            "frame.time_base",
            '"control"',
            '"attack"',
        ):
            self.assertIn(contract, transport)
        self.assertIn('"/v1/sessions/{session_id}/frames"', app)
        self.assertIn("uploaded or prerecorded files cannot satisfy live capture", app)

    def test_webrtc_capture_handler_is_factored_and_tasks_are_retained(self) -> None:
        transport = (ASSET / "webrtc.py").read_text(encoding="utf-8")
        self.assertEqual(transport.count('"frames.capture"'), 1)
        self.assertIn('CAPTURE_OPERATION = "frames.capture"', transport)
        self.assertIn("def _validate_capture_state(", transport)
        self.assertIn("async def _next_fresh_frame(", transport)
        self.assertIn("message_tasks: set[asyncio.Task[None]]", transport)
        self.assertIn("session.message_tasks.add(task)", transport)
        self.assertIn(
            "task.add_done_callback(session.message_tasks.discard)", transport
        )

    def test_auth_limits_health_and_reset_are_explicit(self) -> None:
        app = (ASSET / "app.py").read_text(encoding="utf-8")
        transport = (ASSET / "webrtc.py").read_text(encoding="utf-8")
        for route in (
            '"/healthz"',
            '"/readyz"',
            '"/v1/sessions"',
            '"/v1/sessions/{session_id}/offer"',
            '"/v1/admin/reset"',
            '"/v1/admin/events"',
        ):
            self.assertIn(route, app)
        self.assertIn("hmac.compare_digest", app)
        self.assertIn("secrets.token_urlsafe(32)", app)
        self.assertIn("MAX_FRAME_WIDTH = 640", transport)
        self.assertIn("MAX_FRAME_HEIGHT = 480", transport)
        self.assertIn("MAX_FRAME_BYTES = 256_000", transport)
        self.assertIn("MAX_CAPTURES_PER_SESSION = 24", transport)
        self.assertIn("MIN_CAPTURE_INTERVAL_SECONDS = 0.5", transport)
        self.assertIn("MAX_CLIENT_CLOCK_SKEW_MS = 30_000", transport)

    def test_tls_mount_is_default_and_plaintext_requires_explicit_test_mode(
        self,
    ) -> None:
        entrypoint = (ASSET / "entrypoint.sh").read_text(encoding="utf-8")
        healthcheck = (ASSET / "healthcheck.py").read_text(encoding="utf-8")
        self.assertIn("/run/tls/tls.crt", entrypoint)
        self.assertIn("/run/tls/tls.key", entrypoint)
        self.assertIn(
            "allow_plaintext=${PLATFORM_CAMERA_ALLOW_PLAINTEXT:-0}", entrypoint
        )
        self.assertIn('--ssl-certfile "$cert_file"', entrypoint)
        self.assertIn('--ssl-keyfile "$key_file"', entrypoint)
        self.assertIn("ssl.create_default_context", healthcheck)
        self.assertIn("purpose=ssl.Purpose.SERVER_AUTH", healthcheck)
        self.assertIn("context.minimum_version = ssl.TLSVersion.TLSv1_2", healthcheck)
        self.assertIn("context.check_hostname = True", healthcheck)
        self.assertIn("context.verify_mode = ssl.CERT_REQUIRED", healthcheck)
        self.assertIn("server_hostname=SERVER_NAME", healthcheck)
        self.assertIn("if CERT_FILE.exists() or KEY_FILE.exists()", healthcheck)
        self.assertIn("if not ALLOW_PLAINTEXT", healthcheck)

    def test_api_documents_errors_and_registers_routes_by_boundary(self) -> None:
        app = (ASSET / "app.py").read_text(encoding="utf-8")
        for contract in (
            "_register_participant_and_status_routes",
            "_register_session_create_route",
            "_register_session_operation_routes",
            "_register_admin_routes",
            "responses=AUTH_RESPONSES",
            "responses=OFFER_RESPONSES",
            "responses=SESSION_RESPONSES",
            "responses=READY_RESPONSES",
        ):
            self.assertIn(contract, app)
        self.assertIn('BEARER_REQUIRED = "bearer authentication required"', app)
        self.assertIn('"example": {"detail": "session is closed or expired"}', app)
        self.assertIn('DEFAULT_ML_BASE_URL = "http://platform-ml:8470"  # NOSONAR', app)

    def test_full_content_reconstruction_fields_are_durable(self) -> None:
        storage = (ASSET / "storage.py").read_text(encoding="utf-8")
        transport = (ASSET / "webrtc.py").read_text(encoding="utf-8")
        for value in (
            '"image_png_base64"',
            '"relative_path"',
            '"sha256"',
            '"ml_request"',
            '"ml_response"',
            '"session_token_digest"',
            '"received_monotonic"',
            '"client_timestamp_ms"',
        ):
            self.assertIn(value, storage + transport)
        self.assertIn("os.fsync", storage)
        self.assertIn("os.O_APPEND", storage)
        self.assertEqual(storage.count('"state.json"'), 1)
        self.assertIn('STATE_FILE_NAME = "state.json"', storage)

    def test_storage_retains_content_and_resets_to_one_baseline(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "platform_camera_storage", ASSET / "storage.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        png = b"\x89PNG\r\n\x1a\ncontained-frame"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "state"
            state = module.CameraState(root)
            state.create_session(
                session_id="session-001",
                session_token_digest="a" * 64,
                initiation={"participant_id": "participant-01"},
                expires_at="2030-01-01T00:00:00.000Z",
            )
            event = {"schema_version": 1, "event_name": "frame"}
            retained = state.retain_capture(
                session_id="session-001",
                frame_id="frame-001",
                png=png,
                event=event,
            )
            retained_path = root / retained["retained_frame"]["relative_path"]
            self.assertEqual(retained_path.read_bytes(), png)
            self.assertEqual(
                retained["retained_frame"]["sha256"], hashlib.sha256(png).hexdigest()
            )
            self.assertEqual(
                base64.b64decode(retained["retained_frame"]["image_png_base64"]), png
            )
            self.assertEqual(state.recent_events(1)[0], retained)

            first = state.reset()
            second = state.reset()
            self.assertEqual(first, second)
            self.assertEqual(
                json.loads((root / "state.json").read_text(encoding="utf-8")),
                {"schema_version": 1, "reset_generation": 1},
            )
            self.assertEqual(state.recent_events(10), [])
            self.assertFalse((root / "sessions").exists())

    def test_boundary_does_not_add_pack_local_deployment_or_progress_semantics(
        self,
    ) -> None:
        names = {path.name for path in ASSET.iterdir() if path.is_file()}
        self.assertFalse(
            names
            & {
                "manifest.yaml",
                "service-manifest.yaml",
                "topology.yaml",
                "compose.yaml",
            }
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ASSET.rglob("*")
            if path.is_file()
            and path.suffix in {".py", ".js", ".html", ".css", ".txt", ".sh"}
        ).lower()
        for forbidden in (
            "challenge_id",
            "receipt_id",
            "proof_predicate",
            "ctfd",
            "scoring",
            "atlas technique",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
