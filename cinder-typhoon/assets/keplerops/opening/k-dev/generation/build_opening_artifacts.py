#!/usr/bin/env python3
"""Build deterministic workstation artifacts from the authored opening inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_history() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "History"
        database = sqlite3.connect(path)
        database.executescript(
            """
            PRAGMA page_size=4096;
            PRAGMA journal_mode=DELETE;
            CREATE TABLE meta(key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY, value LONGVARCHAR);
            CREATE TABLE urls(
                id INTEGER PRIMARY KEY,
                url LONGVARCHAR,
                title LONGVARCHAR,
                visit_count INTEGER DEFAULT 0 NOT NULL,
                typed_count INTEGER DEFAULT 0 NOT NULL,
                last_visit_time INTEGER NOT NULL,
                hidden INTEGER DEFAULT 0 NOT NULL
            );
            CREATE TABLE visits(
                id INTEGER PRIMARY KEY,
                url INTEGER NOT NULL,
                visit_time INTEGER NOT NULL,
                from_visit INTEGER,
                transition INTEGER DEFAULT 0 NOT NULL,
                segment_id INTEGER,
                visit_duration INTEGER DEFAULT 0 NOT NULL,
                opener_visit INTEGER
            );
            """
        )
        chromium_time = 13386866211000000
        database.execute("INSERT INTO meta(key, value) VALUES ('version', '68')")
        database.execute("INSERT INTO meta(key, value) VALUES ('last_compatible_version', '68')")
        database.execute(
            "INSERT INTO urls VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "https://support.keplerops.test/scp/tickets.php",
                "SUP-2841 · ARWC connector callback latency · FieldKest Support",
                3,
                1,
                chromium_time,
                0,
            ),
        )
        database.execute(
            "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 1, chromium_time, 0, 805306368, 0, 284000000, 0),
        )
        database.commit()
        database.execute("VACUUM")
        database.close()
        (ROOT / "chromium-History").write_bytes(path.read_bytes())


def build_cookies() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "Cookies"
        database = sqlite3.connect(path)
        database.executescript(
            """
            PRAGMA page_size=4096;
            PRAGMA journal_mode=DELETE;
            CREATE TABLE meta(key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY, value LONGVARCHAR);
            CREATE TABLE cookies(
                creation_utc INTEGER NOT NULL,
                host_key TEXT NOT NULL,
                top_frame_site_key TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                encrypted_value BLOB NOT NULL,
                path TEXT NOT NULL,
                expires_utc INTEGER NOT NULL,
                is_secure INTEGER NOT NULL,
                is_httponly INTEGER NOT NULL,
                last_access_utc INTEGER NOT NULL,
                has_expires INTEGER NOT NULL,
                is_persistent INTEGER NOT NULL,
                priority INTEGER NOT NULL,
                samesite INTEGER NOT NULL,
                source_scheme INTEGER NOT NULL,
                source_port INTEGER NOT NULL,
                last_update_utc INTEGER NOT NULL,
                source_type INTEGER NOT NULL,
                has_cross_site_ancestor INTEGER NOT NULL
            );
            CREATE UNIQUE INDEX cookies_unique_index ON cookies(host_key, top_frame_site_key, name, path, source_scheme, source_port);
            """
        )
        creation = 13386865320000000
        expiry = 13389457320000000
        database.execute("INSERT INTO meta(key, value) VALUES ('version', '24')")
        database.execute("INSERT INTO meta(key, value) VALUES ('last_compatible_version', '24')")
        database.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                creation,
                "support.keplerops.test",
                "https://keplerops.test",
                "fieldkest_support",
                "UNPROVISIONED",
                b"",
                "/",
                expiry,
                1,
                1,
                creation,
                1,
                1,
                1,
                1,
                2,
                443,
                creation,
                0,
                0,
            ),
        )
        database.commit()
        database.execute("VACUUM")
        database.close()
        (ROOT / "chromium-Cookies").write_bytes(path.read_bytes())


def write_manifest() -> None:
    names = (
        "staging-FKCOL-2841.bin",
        "field-notes-2026-08.odt",
        "FKCOL-2841.json",
        "chromium-History",
        "chromium-Cookies",
    )
    payload = {
        "schema": "fieldkest.generated-artifacts/v1",
        "artifacts": [
            {
                "name": name,
                "sha256": sha256((ROOT / name).read_bytes()),
                "size": (ROOT / name).stat().st_size,
            }
            for name in names
        ],
    }
    (ROOT / "generated-artifacts.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    build_history()
    build_cookies()
    write_manifest()


if __name__ == "__main__":
    main()

