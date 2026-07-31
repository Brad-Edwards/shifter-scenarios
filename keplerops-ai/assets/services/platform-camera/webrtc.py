"""Authenticated WebRTC ingestion for live KeplerOps camera frames."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from typing import Any, Awaitable, Callable

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack
from PIL import Image

from storage import CameraState, utc_now


DATA_CHANNEL_LABEL = "keplerops-live-capture-v1"
CAPTURE_OPERATION = "frames.capture"
MAX_COMMAND_BYTES = 4_096
MAX_FRAME_WIDTH = 640
MAX_FRAME_HEIGHT = 480
MAX_FRAME_BYTES = 256_000
MAX_CAPTURES_PER_SESSION = 24
MIN_CAPTURE_INTERVAL_SECONDS = 0.5
FRAME_WAIT_SECONDS = 6.0
MAX_PAIR_INTERVAL_SECONDS = 120.0
MAX_CLIENT_CLOCK_SKEW_MS = 30_000
PAIR_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,95}$")
NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

VisionClassifier = Callable[[dict[str, str]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class LiveFrame:
    frame: Any
    sequence: int
    received_at: str
    received_monotonic: float
    pts: int | None
    time_base: Fraction | None


@dataclass
class SessionRuntime:
    session_id: str
    participant_id: str
    range_id: str
    session_token_digest: str
    created_at: str
    expires_at: str
    expires_monotonic: float
    peer: RTCPeerConnection | None = None
    data_channel: Any | None = None
    track_task: asyncio.Task[None] | None = None
    sequence: int = 0
    latest_frame_monotonic: float | None = None
    last_capture_monotonic: float | None = None
    capture_count: int = 0
    pairs: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    pending_frames: deque[asyncio.Future[LiveFrame]] = field(default_factory=deque)
    message_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    capture_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False


class CaptureRejected(ValueError):
    """A capture command did not satisfy the live-ingestion contract."""


class PeerManager:
    def __init__(self, state: CameraState, classify: VisionClassifier) -> None:
        self.state = state
        self.classify = classify
        self.sessions: dict[str, SessionRuntime] = {}

    def add_session(self, session: SessionRuntime) -> None:
        self.sessions[session.session_id] = session

    def get_session(self, session_id: str) -> SessionRuntime | None:
        return self.sessions.get(session_id)

    async def accept_offer(
        self,
        session: SessionRuntime,
        *,
        sdp: str,
        description_type: str,
    ) -> dict[str, str]:
        if session.peer is not None:
            raise CaptureRejected("this session already has a peer connection")
        if session.closed or time.monotonic() >= session.expires_monotonic:
            raise CaptureRejected("the session is closed or expired")

        peer = RTCPeerConnection(configuration=None)
        session.peer = peer

        @peer.on("datachannel")
        def on_datachannel(channel: Any) -> None:
            if channel.label != DATA_CHANNEL_LABEL or session.data_channel is not None:
                channel.close()
                self._journal(
                    session,
                    event_name="platform_camera.data_channel_rejected",
                    operation="webrtc.data_channel",
                    status="rejected",
                    request={"label": channel.label},
                    response={"reason": "unexpected data channel"},
                )
                return
            session.data_channel = channel

            @channel.on("message")
            def on_message(message: Any) -> None:
                task = asyncio.create_task(self._process_message(session, message))
                session.message_tasks.add(task)
                task.add_done_callback(session.message_tasks.discard)

        @peer.on("track")
        def on_track(track: MediaStreamTrack) -> None:
            if track.kind != "video" or session.track_task is not None:
                track.stop()
                self._journal(
                    session,
                    event_name="platform_camera.track_rejected",
                    operation="webrtc.track",
                    status="rejected",
                    request={"kind": track.kind, "track_id": track.id},
                    response={
                        "reason": "one video track is required; audio is disabled"
                    },
                )
                return
            self._journal(
                session,
                event_name="platform_camera.video_track_received",
                operation="webrtc.track",
                status="accepted",
                request={"kind": track.kind, "track_id": track.id},
                response={"consumer": "live decoded frames"},
            )
            session.track_task = asyncio.create_task(
                self._consume_video(session, track)
            )

        @peer.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            self._journal(
                session,
                event_name="platform_camera.connection_state_changed",
                operation="webrtc.connection",
                status=peer.connectionState,
                request={},
                response={"connection_state": peer.connectionState},
            )
            if peer.connectionState in {"failed", "closed"}:
                await self.close_session(session.session_id)

        try:
            await peer.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type=description_type)
            )
            answer = await peer.createAnswer()
            await peer.setLocalDescription(answer)
        except Exception:
            await peer.close()
            session.peer = None
            raise

        assert peer.localDescription is not None
        self._journal(
            session,
            event_name="platform_camera.offer_accepted",
            operation="webrtc.offer",
            status="succeeded",
            request={"sdp": sdp, "type": description_type},
            response={
                "sdp": peer.localDescription.sdp,
                "type": peer.localDescription.type,
            },
        )
        return {
            "sdp": peer.localDescription.sdp,
            "type": peer.localDescription.type,
        }

    async def close_session(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session is None or session.closed:
            return
        session.closed = True
        while session.pending_frames:
            pending = session.pending_frames.popleft()
            if not pending.done():
                pending.set_exception(CaptureRejected("the live track closed"))
        current = asyncio.current_task()
        if session.track_task is not None and session.track_task is not current:
            session.track_task.cancel()
            await asyncio.gather(session.track_task, return_exceptions=True)
        if session.peer is not None and session.peer.connectionState != "closed":
            await session.peer.close()
        self._journal(
            session,
            event_name="platform_camera.session_closed",
            operation="sessions.close",
            status="succeeded",
            request={},
            response={"capture_count": session.capture_count},
        )

    async def close_all(self) -> None:
        await asyncio.gather(
            *(self.close_session(session_id) for session_id in tuple(self.sessions)),
            return_exceptions=True,
        )
        self.sessions.clear()

    async def _consume_video(
        self, session: SessionRuntime, track: MediaStreamTrack
    ) -> None:
        try:
            while not session.closed:
                frame = await track.recv()
                session.sequence += 1
                received_monotonic = time.monotonic()
                session.latest_frame_monotonic = received_monotonic
                live_frame = LiveFrame(
                    frame=frame,
                    sequence=session.sequence,
                    received_at=utc_now(),
                    received_monotonic=received_monotonic,
                    pts=frame.pts,
                    time_base=frame.time_base,
                )
                if session.pending_frames:
                    pending = session.pending_frames.popleft()
                    if not pending.done():
                        pending.set_result(live_frame)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._journal(
                session,
                event_name="platform_camera.video_track_ended",
                operation="webrtc.track.consume",
                status="ended",
                request={},
                response={"error_type": type(error).__name__},
            )
            while session.pending_frames:
                pending = session.pending_frames.popleft()
                if not pending.done():
                    pending.set_exception(CaptureRejected("the live track ended"))

    async def _process_message(self, session: SessionRuntime, message: Any) -> None:
        command: dict[str, Any] | None = None
        try:
            command = self._parse_command(message)
            result = await self._capture(session, command)
            self._send(session, {"type": "capture-result", "ok": True, **result})
        except (CaptureRejected, asyncio.TimeoutError) as error:
            reason = str(error) or "no fresh live frame arrived before timeout"
            captured = (
                command if command is not None else self._captured_message(message)
            )
            self._journal(
                session,
                event_name="platform_camera.capture_rejected",
                operation=CAPTURE_OPERATION,
                status="rejected",
                request={"command": captured},
                response={"reason": reason},
            )
            self._send(
                session,
                {"type": "capture-result", "ok": False, "reason": reason},
            )
        except Exception as error:
            self._journal(
                session,
                event_name="platform_camera.capture_failed",
                operation=CAPTURE_OPERATION,
                status="failed",
                request={"command": command},
                response={"error_type": type(error).__name__},
            )
            self._send(
                session,
                {
                    "type": "capture-result",
                    "ok": False,
                    "reason": "capture processing failed",
                },
            )

    @staticmethod
    def _validate_capture_state(
        session: SessionRuntime, command: dict[str, Any], now: float
    ) -> tuple[str, str, dict[str, dict[str, Any]]]:
        if session.closed or now >= session.expires_monotonic:
            raise CaptureRejected("the session is closed or expired")
        if session.track_task is None or session.track_task.done():
            raise CaptureRejected("a live video track is not active")
        if session.capture_count >= MAX_CAPTURES_PER_SESSION:
            raise CaptureRejected("the session capture limit has been reached")
        if (
            session.last_capture_monotonic is not None
            and now - session.last_capture_monotonic < MIN_CAPTURE_INTERVAL_SECONDS
        ):
            raise CaptureRejected("captures are rate limited")

        pair_id = command["pair_id"]
        role = command["role"]
        pair = session.pairs.setdefault(pair_id, {})
        if role in pair:
            raise CaptureRejected(f"the pair already contains a {role} frame")
        if role == "attack" and "control" not in pair:
            raise CaptureRejected("capture the control frame before the attack frame")
        if role == "attack":
            control_age = now - float(pair["control"]["captured_monotonic"])
            if control_age > MAX_PAIR_INTERVAL_SECONDS:
                raise CaptureRejected("the control frame is too old for this pair")
        return pair_id, role, pair

    @staticmethod
    async def _next_fresh_frame(session: SessionRuntime) -> tuple[LiveFrame, float]:
        loop = asyncio.get_running_loop()
        pending: asyncio.Future[LiveFrame] = loop.create_future()
        queued_monotonic = time.monotonic()
        session.pending_frames.append(pending)
        try:
            live_frame = await asyncio.wait_for(pending, timeout=FRAME_WAIT_SECONDS)
        except TimeoutError as error:
            if pending in session.pending_frames:
                session.pending_frames.remove(pending)
            raise asyncio.TimeoutError from error

        if live_frame.received_monotonic < queued_monotonic:
            raise CaptureRejected("the received frame was not fresh")
        if time.monotonic() - live_frame.received_monotonic > FRAME_WAIT_SECONDS:
            raise CaptureRejected("the received frame failed the liveness window")
        return live_frame, queued_monotonic

    async def _capture(
        self, session: SessionRuntime, command: dict[str, Any]
    ) -> dict[str, Any]:
        async with session.capture_lock:
            now = time.monotonic()
            pair_id, role, pair = self._validate_capture_state(session, command, now)
            live_frame, queued_monotonic = await self._next_fresh_frame(session)

            png, width, height = await asyncio.to_thread(
                self._encode_bounded_png, live_frame.frame
            )
            frame_id = uuid.uuid4().hex
            request_id = f"camera-{frame_id}"
            ml_request = {
                "request_id": request_id,
                "image_png_base64": base64.b64encode(png).decode("ascii"),
            }
            retained_event = self._event(
                session,
                event_name="platform_camera.frame_retained",
                operation=CAPTURE_OPERATION,
                status="retained",
                request={"command": command, "ml_request": ml_request},
                response={"forwarding": "pending"},
                extra={
                    "frame_id": frame_id,
                    "pair_id": pair_id,
                    "role": role,
                    "track": {
                        "sequence": live_frame.sequence,
                        "received_at": live_frame.received_at,
                        "queued_monotonic": queued_monotonic,
                        "received_monotonic": live_frame.received_monotonic,
                        "pts": live_frame.pts,
                        "time_base": (
                            str(live_frame.time_base)
                            if live_frame.time_base is not None
                            else None
                        ),
                        "width": width,
                        "height": height,
                    },
                },
            )
            retained = self.state.retain_capture(
                session_id=session.session_id,
                frame_id=frame_id,
                png=png,
                event=retained_event,
            )
            session.capture_count += 1
            session.last_capture_monotonic = time.monotonic()

            forward_started = time.perf_counter()
            ml_response: dict[str, Any] | None = None
            forward_error: dict[str, str] | None = None
            try:
                ml_response = await self.classify(ml_request)
            except Exception as error:
                captured_details = getattr(error, "details", None)
                forward_error = (
                    captured_details
                    if isinstance(captured_details, dict)
                    else {
                        "error_type": type(error).__name__,
                        "message": str(error)[:512],
                    }
                )
            duration_ms = round((time.perf_counter() - forward_started) * 1_000, 3)
            succeeded = ml_response is not None
            self.state.append_event(
                self._event(
                    session,
                    event_name="platform_camera.frame_forwarded",
                    operation="platform_ml.vision.classify",
                    status="succeeded" if succeeded else "failed",
                    request={
                        "command": command,
                        "ml_request": ml_request,
                        "retained_frame": retained["retained_frame"],
                    },
                    response={
                        "ml_response": ml_response,
                        "error": forward_error,
                        "duration_ms": duration_ms,
                    },
                    extra={"frame_id": frame_id, "pair_id": pair_id, "role": role},
                )
            )
            if not succeeded:
                raise CaptureRejected(
                    "the frame was retained but vision forwarding failed"
                )

            pair[role] = {
                "frame_id": frame_id,
                "captured_at": live_frame.received_at,
                "captured_monotonic": live_frame.received_monotonic,
                "track_sequence": live_frame.sequence,
                "ml_request_id": request_id,
            }
            self.state.update_session(
                session.session_id,
                {
                    "schema_version": 1,
                    "session_id": session.session_id,
                    "capture_count": session.capture_count,
                    "pairs": session.pairs,
                },
            )
            return {
                "session_id": session.session_id,
                "frame_id": frame_id,
                "pair_id": pair_id,
                "role": role,
                "track_sequence": live_frame.sequence,
                "ml_response": ml_response,
            }

    @staticmethod
    def _parse_command(message: Any) -> dict[str, Any]:
        if not isinstance(message, str):
            raise CaptureRejected("capture commands must be UTF-8 JSON text")
        encoded = message.encode("utf-8")
        if len(encoded) > MAX_COMMAND_BYTES:
            raise CaptureRejected("the capture command is too large")
        try:
            value = json.loads(message)
        except json.JSONDecodeError as error:
            raise CaptureRejected("the capture command is not valid JSON") from error
        required = {"type", "pair_id", "role", "client_timestamp_ms", "nonce"}
        if not isinstance(value, dict) or set(value) != required:
            raise CaptureRejected("the capture command fields are not exact")
        if value["type"] != "capture":
            raise CaptureRejected("the data channel only accepts capture commands")
        if value["role"] not in {"control", "attack"}:
            raise CaptureRejected("role must be control or attack")
        if not isinstance(value["pair_id"], str) or not PAIR_PATTERN.fullmatch(
            value["pair_id"]
        ):
            raise CaptureRejected("pair_id is invalid")
        if not isinstance(value["nonce"], str) or not NONCE_PATTERN.fullmatch(
            value["nonce"]
        ):
            raise CaptureRejected("nonce is invalid")
        timestamp = value["client_timestamp_ms"]
        if (
            not isinstance(timestamp, int)
            or isinstance(timestamp, bool)
            or timestamp < 0
        ):
            raise CaptureRejected("client_timestamp_ms must be a non-negative integer")
        if abs(timestamp - round(time.time() * 1_000)) > MAX_CLIENT_CLOCK_SKEW_MS:
            raise CaptureRejected("client_timestamp_ms is outside the liveness window")
        return value

    @staticmethod
    def _captured_message(message: Any) -> dict[str, Any]:
        if isinstance(message, str):
            return {"raw_text": message[:MAX_COMMAND_BYTES]}
        if isinstance(message, bytes):
            return {
                "raw_base64": base64.b64encode(message[:MAX_COMMAND_BYTES]).decode(
                    "ascii"
                )
            }
        return {"type": type(message).__name__}

    @staticmethod
    def _encode_bounded_png(frame: Any) -> tuple[bytes, int, int]:
        image: Image.Image = frame.to_image().convert("RGB")
        width, height = image.size
        if width > MAX_FRAME_WIDTH or height > MAX_FRAME_HEIGHT:
            raise CaptureRejected(
                f"live frame exceeds {MAX_FRAME_WIDTH}x{MAX_FRAME_HEIGHT} pixels"
            )
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=False, compress_level=6)
        png = output.getvalue()
        if len(png) > MAX_FRAME_BYTES:
            raise CaptureRejected(f"encoded live frame exceeds {MAX_FRAME_BYTES} bytes")
        return png, width, height

    @staticmethod
    def _send(session: SessionRuntime, value: dict[str, Any]) -> None:
        channel = session.data_channel
        if channel is not None and channel.readyState == "open":
            channel.send(json.dumps(value, sort_keys=True, separators=(",", ":")))

    def _journal(
        self,
        session: SessionRuntime,
        *,
        event_name: str,
        operation: str,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        self.state.append_event(
            self._event(
                session,
                event_name=event_name,
                operation=operation,
                status=status,
                request=request,
                response=response,
            )
        )

    @staticmethod
    def _event(
        session: SessionRuntime,
        *,
        event_name: str,
        operation: str,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_id": uuid.uuid4().hex,
            "event_name": event_name,
            "observed_at": utc_now(),
            "operation": operation,
            "status": status,
            "session": {
                "session_id": session.session_id,
                "participant_id": session.participant_id,
                "range_id": session.range_id,
                "session_token_digest": session.session_token_digest,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
            },
            "request": request,
            "response": response,
            **(extra or {}),
        }


def expiry_timestamp(ttl_seconds: int) -> tuple[str, float]:
    expires_monotonic = time.monotonic() + ttl_seconds
    expires_epoch = time.time() + ttl_seconds
    expires_at = (
        datetime.fromtimestamp(expires_epoch, UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    return expires_at, expires_monotonic
