#!/usr/bin/env python3
"""Fail-open PTY recorder for the participant Kali workstation."""

from __future__ import annotations

import base64
import hashlib
import os
import queue
import selectors
import sys
import termios
import time
import tty

from keplerops_research_transport import start_sender, stop_sender


MAX_QUEUE = 512
MAX_CHUNK_BYTES = 8192
CHILD_SHELL = ("/bin/bash", "-i")


def _trace_id() -> str:
    material = f"{time.time_ns()}:{os.getpid()}:{os.urandom(16).hex()}".encode()
    return hashlib.sha256(material).hexdigest()[:32]


TRACE_ID = _trace_id()
EVENTS: queue.Queue[tuple[str, dict[str, object]] | None] = queue.Queue(MAX_QUEUE)


def _emit(signal: str, event: dict[str, object]) -> None:
    try:
        EVENTS.put_nowait((signal, {"timestamp_ns": time.time_ns(), **event}))
    except queue.Full:
        return


def _encoded_chunk(stream: str, data: bytes) -> dict[str, object]:
    return {
        "stream": stream,
        "encoding": "base64",
        "data": base64.b64encode(data[:MAX_CHUNK_BYTES]).decode("ascii"),
        "byte_count": min(len(data), MAX_CHUNK_BYTES),
    }


def _command_buffer_update(buffer: bytearray, data: bytes) -> None:
    for byte in data:
        if byte in (10, 13):
            command = buffer.decode("utf-8", errors="replace").strip()
            buffer.clear()
            if command:
                _emit("terminal_command", {"command": command})
        elif byte in (8, 127):
            if buffer:
                buffer.pop()
        elif 32 <= byte <= 126 or byte >= 128:
            buffer.append(byte)


def _child_shell() -> None:
    os.environ["KEPLEROPS_TERMINAL_CAPTURE_ACTIVE"] = "1"
    os.execl("/bin/bash", "bash", "-i")


def _enable_raw_stdin() -> list[int | bytes] | None:
    if sys.stdin.isatty():
        original = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
        return original
    return None


def _read_pty(master: int, pid: int) -> tuple[int, bool]:
    try:
        data = os.read(master, MAX_CHUNK_BYTES)
    except OSError:
        data = b""
    if not data:
        _, raw_status = os.waitpid(pid, 0)
        return os.waitstatus_to_exitcode(raw_status), True
    os.write(sys.stdout.fileno(), data)
    _emit("terminal_output", _encoded_chunk("stdout", data))
    return 0, False


def _read_stdin(master: int, command_buffer: bytearray) -> None:
    data = os.read(sys.stdin.fileno(), MAX_CHUNK_BYTES)
    if not data:
        return
    os.write(master, data)
    _emit("terminal_input", _encoded_chunk("stdin", data))
    _command_buffer_update(command_buffer, data)


def _relay_terminal(pid: int, master: int) -> int:
    selector = selectors.DefaultSelector()
    selector.register(master, selectors.EVENT_READ, "pty")
    selector.register(sys.stdin.fileno(), selectors.EVENT_READ, "stdin")
    command_buffer = bytearray()
    while True:
        for key, _ in selector.select(timeout=0.2):
            if key.data == "pty":
                status, done = _read_pty(master, pid)
                if done:
                    return status
            else:
                _read_stdin(master, command_buffer)


def main() -> int:
    worker = start_sender(EVENTS, "keplerops-terminal-sender", lambda _event: TRACE_ID)
    _emit("process_lifecycle", {"event": "started", "argv": list(CHILD_SHELL)})
    pid, master = os.forkpty()
    if pid == 0:
        _child_shell()
    original = _enable_raw_stdin()
    status = 0
    try:
        status = _relay_terminal(pid, master)
    finally:
        if original is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, original)
        _emit("process_lifecycle", {"event": "exited", "exit_code": status})
        stop_sender(EVENTS, worker)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
