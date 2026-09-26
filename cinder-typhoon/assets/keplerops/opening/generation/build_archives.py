#!/usr/bin/env python3
"""Build deterministic per-node archives for the KeplerOps opening slice."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parents[1]
FIXED_MTIME = 1789729200  # 2026-09-18T15:00:00Z


ARCHIVES: dict[str, dict[str, object]] = {
    "k-dev-home.tar": {
        "owner": "rowan",
        "group": "rowan",
        "files": {
            "README.md": ("k-dev/HOME.md", 0o644),
            ".gitconfig": ("k-dev/gitconfig", 0o600),
            ".config/git/credentials": ("k-dev/git-credentials", 0o600),
            ".config/chromium/Default/History": ("k-dev/chromium-History", 0o600),
            ".config/chromium/Default/Cookies": ("k-dev/chromium-Cookies", 0o600),
            ".config/chromium/Default/Preferences": ("k-dev/chromium-Preferences", 0o600),
            "work/local-helper.md": ("k-dev/local-helper.md", 0o644),
            "work/service-notes.md": ("k-dev/service-notes.md", 0o644),
            "work/samples/FK-SAMPLE-017.json": ("k-dev/sample-FK-SAMPLE-017.json", 0o640),
            "work/review-exports/fieldlink-7.4.2-review.md": ("k-dev/fieldlink-7.4.2-review.md", 0o640),
            "work/analysis/field-notes-2026-08.odt": ("k-dev/field-notes-2026-08.odt", 0o640),
            "work/analysis/staging-decoder.ps1": ("k-dev/staging-decoder.ps1", 0o640),
        },
    },
    "k-dev-workbench.tar": {
        "owner": "fieldkest-workbench",
        "group": "fieldkest-workbench",
        "files": {
            "config/opening.json": ("k-dev/workbench-service.json", 0o640),
            "seed/fieldlink-connector.bundle": ("k-source/fieldlink-connector.bundle", 0o640),
        },
    },
    "k-source-state.tar": {
        "owner": "git",
        "group": "git",
        "files": {
            "seeds/fieldlink-connector.bundle": ("k-source/fieldlink-connector.bundle", 0o640),
            "seeds/repository-artifact.json": ("k-source/repository-artifact.json", 0o640),
            "handovers/HND-FLK-2026-09.json": ("k-source/handover.json", 0o640),
            "config/opening.json": ("k-source/source-service.json", 0o600),
        },
    },
    "k-ci-state.tar": {
        "owner": "fieldkest-ci",
        "group": "fieldkest-ci",
        "files": {
            "runs/BLD-1842.json": ("k-ci/run-BLD-1842.json", 0o640),
            "runs/BLD-1842.log": ("k-ci/run-BLD-1842.log", 0o640),
            "import-objects/inputs/report-request.json": ("k-ci/import-example.json", 0o640),
            "import-objects/reviews/REVNOTE-1842.json": ("k-ci/REVNOTE-1842.json", 0o640),
            "config/opening.json": ("k-ci/ci-service.json", 0o600),
        },
    },
    "k-support-state.tar": {
        "owner": "fieldkest-support",
        "group": "fieldkest-support",
        "files": {
            "conversations/SUP-2841.json": ("k-support/SUP-2841.json", 0o640),
            "sessions/rowan.json": ("k-support/session.json", 0o600),
            "config/opening.json": ("k-support/support-service.json", 0o600),
        },
    },
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_directory(archive: tarfile.TarFile, name: str, owner: str, group: str, mode: int) -> None:
    info = tarfile.TarInfo(name.rstrip("/") + "/")
    info.type = tarfile.DIRTYPE
    info.mode = mode
    info.mtime = FIXED_MTIME
    info.uid = 1000
    info.gid = 1000
    info.uname = owner
    info.gname = group
    archive.addfile(info)


def add_file(
    archive: tarfile.TarFile,
    destination: str,
    data: bytes,
    owner: str,
    group: str,
    mode: int,
) -> None:
    info = tarfile.TarInfo(destination)
    info.size = len(data)
    info.mode = mode
    info.mtime = FIXED_MTIME
    info.uid = 1000
    info.gid = 1000
    info.uname = owner
    info.gname = group
    archive.addfile(info, io.BytesIO(data))


def main() -> None:
    records = []
    for archive_name, specification in ARCHIVES.items():
        owner = specification["owner"]
        group = specification["group"]
        files = specification["files"]
        archive_path = ROOT / archive_name
        with tarfile.open(archive_path, "w", format=tarfile.USTAR_FORMAT) as archive:
            directories: set[str] = set()
            for destination in files:
                parent = Path(destination).parent
                while str(parent) not in ("", "."):
                    directories.add(parent.as_posix())
                    parent = parent.parent
            for directory in sorted(directories, key=lambda item: (item.count("/"), item)):
                mode = 0o700 if directory.startswith(".config") or directory == "sessions" else 0o750
                add_directory(archive, directory, owner, group, mode)
            file_records = []
            for destination, (source_name, mode) in sorted(files.items()):
                data = (ROOT / source_name).read_bytes()
                add_file(archive, destination, data, owner, group, mode)
                file_records.append(
                    {
                        "path": destination,
                        "mode": f"{mode:04o}",
                        "sha256": digest(data),
                        "size": len(data),
                    }
                )
        records.append(
            {
                "archive": archive_name,
                "sha256": digest(archive_path.read_bytes()),
                "size": archive_path.stat().st_size,
                "owner": owner,
                "group": group,
                "files": file_records,
            }
        )
    (ROOT / "archive-manifest.json").write_text(
        json.dumps(
            {"schema": "fieldkest.opening-archives/v1", "archives": records},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
