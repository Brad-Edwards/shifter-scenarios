#!/usr/bin/env python3
"""Fail-open browser navigation/download recorder for the participant workstation."""

from __future__ import annotations

import hashlib
import queue
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from keplerops_research_transport import start_sender


HOME_ROOT = Path("/home/kasm-user")
CHROMIUM_HISTORY = (
    HOME_ROOT / ".config/chromium/Default/History",
    HOME_ROOT / ".config/google-chrome/Default/History",
)
FIREFOX_ROOT = HOME_ROOT / ".mozilla/firefox"
MAX_QUEUE = 512
MAX_TEXT_BYTES = 4096
MAX_EVENTS_PER_SCAN = 100
POLL_SECONDS = 2.0
CHROME_EPOCH_OFFSET_US = 11_644_473_600_000_000


EVENTS: queue.Queue[tuple[str, dict[str, object]] | None] = queue.Queue(MAX_QUEUE)


@dataclass
class BrowserState:
    chromium_visits: dict[str, int]
    chromium_downloads: dict[str, int]
    firefox_visits: dict[str, int]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(HOME_ROOT))
    except ValueError:
        return str(path)


def _bounded(value: object) -> str:
    text = "" if value is None else str(value)
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


def _trace_id(browser: str, event_id: int, url: str) -> str:
    material = f"{time.time_ns()}:{browser}:{event_id}:{url}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def _enqueue(event: dict[str, object]) -> None:
    try:
        EVENTS.put_nowait(("browser_interaction", event))
    except queue.Full:
        return


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.2)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _chrome_ns(chrome_time_us: object) -> int:
    if not isinstance(chrome_time_us, int):
        return 0
    value = chrome_time_us - CHROME_EPOCH_OFFSET_US
    return max(value, 0) * 1000


def _firefox_ns(firefox_time_us: object) -> int:
    return max(firefox_time_us, 0) * 1000 if isinstance(firefox_time_us, int) else 0


def _emit_chromium_visit(profile: Path, row: sqlite3.Row) -> None:
    url = _bounded(row["url"])
    _enqueue(
        {
            "trace_id": _trace_id("chromium", int(row["visit_id"]), url),
            "timestamp_ns": time.time_ns(),
            "event": "navigation",
            "browser": "chromium",
            "profile": _relative(profile),
            "visit_id": int(row["visit_id"]),
            "url_id": int(row["url_id"]),
            "url": url,
            "title": _bounded(row["title"]),
            "visit_time_raw": int(row["visit_time"]),
            "occurred_at_ns": _chrome_ns(row["visit_time"]),
            "transition": int(row["transition"]),
            "typed_count": int(row["typed_count"]),
            "visit_count": int(row["visit_count"]),
            "visit_duration_us": int(row["visit_duration"]),
        }
    )


def _emit_chromium_download(profile: Path, row: sqlite3.Row) -> None:
    target = _bounded(row["target_path"])
    url = _bounded(row["tab_url"])
    _enqueue(
        {
            "trace_id": _trace_id("chromium-download", int(row["download_id"]), url),
            "timestamp_ns": time.time_ns(),
            "event": "download",
            "browser": "chromium",
            "profile": _relative(profile),
            "download_id": int(row["download_id"]),
            "target_path": target,
            "url": url,
            "mime_type": _bounded(row["mime_type"]),
            "start_time_raw": int(row["start_time"]),
            "occurred_at_ns": _chrome_ns(row["start_time"]),
            "end_time_raw": int(row["end_time"]),
            "state": int(row["state"]),
            "total_bytes": int(row["total_bytes"]),
        }
    )


def _chromium_profiles() -> Iterable[Path]:
    yield from CHROMIUM_HISTORY
    for browser_root in (HOME_ROOT / ".config/chromium", HOME_ROOT / ".config/google-chrome"):
        if not browser_root.exists():
            continue
        for path in browser_root.glob("*/History"):
            if path not in CHROMIUM_HISTORY:
                yield path


def _scan_chromium(profile: Path, state: BrowserState, *, baseline: bool) -> None:
    if not profile.exists():
        return
    key = str(profile)
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(profile)
        connection.row_factory = sqlite3.Row
        _scan_chromium_visits(connection, profile, state, key, baseline=baseline)
        _scan_chromium_downloads(connection, profile, state, key, baseline=baseline)
    except sqlite3.Error:
        return
    finally:
        if connection is not None:
            connection.close()


def _scan_chromium_visits(
    connection: sqlite3.Connection,
    profile: Path,
    state: BrowserState,
    key: str,
    *,
    baseline: bool,
) -> None:
    if not {"visits", "urls"}.issubset(_table_names(connection)):
        return
    previous = state.chromium_visits.get(key, 0)
    rows = connection.execute(
        """
        SELECT v.id AS visit_id, v.url AS url_id, u.url, u.title, u.visit_count,
               u.typed_count, v.visit_time, v.transition, v.visit_duration
          FROM visits v JOIN urls u ON u.id = v.url
         WHERE v.id > ?
         ORDER BY v.id
         LIMIT ?
        """,
        (previous, MAX_EVENTS_PER_SCAN),
    ).fetchall()
    for row in rows:
        if not baseline:
            _emit_chromium_visit(profile, row)
        state.chromium_visits[key] = int(row["visit_id"])


def _scan_chromium_downloads(
    connection: sqlite3.Connection,
    profile: Path,
    state: BrowserState,
    key: str,
    *,
    baseline: bool,
) -> None:
    columns = _columns(connection, "downloads")
    required = {"id", "target_path", "start_time", "end_time", "state", "total_bytes"}
    if not required.issubset(columns):
        return
    previous = state.chromium_downloads.get(key, 0)
    tab_url = "tab_url" if "tab_url" in columns else "''"
    mime_type = "mime_type" if "mime_type" in columns else "''"
    rows = connection.execute(
        f"""
        SELECT id AS download_id, target_path, {tab_url} AS tab_url,
               {mime_type} AS mime_type, start_time, end_time, state, total_bytes
          FROM downloads
         WHERE id > ?
         ORDER BY id
         LIMIT ?
        """,
        (previous, MAX_EVENTS_PER_SCAN),
    ).fetchall()
    for row in rows:
        if not baseline:
            _emit_chromium_download(profile, row)
        state.chromium_downloads[key] = int(row["download_id"])


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _firefox_profiles() -> Iterable[Path]:
    if not FIREFOX_ROOT.exists():
        return
    yield from FIREFOX_ROOT.glob("*/places.sqlite")


def _scan_firefox(profile: Path, state: BrowserState, *, baseline: bool) -> None:
    key = str(profile)
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(profile)
        connection.row_factory = sqlite3.Row
        if not {"moz_historyvisits", "moz_places"}.issubset(_table_names(connection)):
            return
        previous = state.firefox_visits.get(key, 0)
        rows = connection.execute(
            """
            SELECT v.id AS visit_id, p.id AS url_id, p.url, p.title,
                   p.visit_count, v.visit_date, v.visit_type
              FROM moz_historyvisits v JOIN moz_places p ON p.id = v.place_id
             WHERE v.id > ?
             ORDER BY v.id
             LIMIT ?
            """,
            (previous, MAX_EVENTS_PER_SCAN),
        ).fetchall()
    except sqlite3.Error:
        return
    finally:
        if connection is not None:
            connection.close()
    for row in rows:
        if not baseline:
            _enqueue(
                {
                    "trace_id": _trace_id("firefox", int(row["visit_id"]), row["url"]),
                    "timestamp_ns": time.time_ns(),
                    "event": "navigation",
                    "browser": "firefox",
                    "profile": _relative(profile),
                    "visit_id": int(row["visit_id"]),
                    "url_id": int(row["url_id"]),
                    "url": _bounded(row["url"]),
                    "title": _bounded(row["title"]),
                    "visit_time_raw": int(row["visit_date"]),
                    "occurred_at_ns": _firefox_ns(row["visit_date"]),
                    "transition": int(row["visit_type"]),
                    "visit_count": int(row["visit_count"]),
                }
            )
        state.firefox_visits[key] = int(row["visit_id"])


def scan_once(state: BrowserState, *, baseline: bool = False) -> None:
    for profile in _chromium_profiles():
        _scan_chromium(profile, state, baseline=baseline)
    for profile in _firefox_profiles():
        _scan_firefox(profile, state, baseline=baseline)


def main() -> int:
    start_sender(EVENTS, "keplerops-browser-sender", lambda event: str(event["trace_id"]))
    state = BrowserState({}, {}, {})
    scan_once(state, baseline=True)
    while True:
        time.sleep(POLL_SECONDS)
        try:
            scan_once(state)
        except Exception:
            continue


if __name__ == "__main__":
    raise SystemExit(main())
