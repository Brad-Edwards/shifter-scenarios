#!/usr/bin/env python3
"""Build deterministic k-staff state for K18.

config/staff.json holds only routing and config: developer identity,
osTicket DB coordinates, note-to-consumer metadata, and the support
registration ID. The note draft itself lives only in osTicket, planted
by seed-k18-note.php. No challenge answer or secret resides in this tar.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FIXED_MTIME = 1789729200


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"


def make_archive(dest: Path, files: dict[str, tuple[bytes, int]]) -> dict:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:", format=tarfile.GNU_FORMAT) as tf:
        for name, (data, mode) in sorted(files.items()):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = mode
            info.mtime = FIXED_MTIME
            tf.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    dest.write_bytes(raw)
    return {"path": dest.name, "sha256": sha(raw), "size": len(raw)}


def main() -> None:
    config = {
        "developer": {
            "username": "rowan.ito",
        },
        "support_registration": "OIDC-FIELDKEST-SUPPORT",
        "restricted_note": "NOTE-SUP-2841-7",
        "support_db_host": "fieldlink-support-db",
        "support_db_port": 3306,
        "support_db": "fieldlink_support",
        "support_db_user": "fieldlink_support",
        "notes": {
            "NOTE-SUP-2841-7": {
                "osticket_title": "K18 Restricted Support Draft — CRR-OG2",
                "consumer": "staff-note-preview",
                "status": "draft",
                "restricted": True,
            },
        },
        "identity_host": "identity.keplerops.test",
        "kanboard_db_host": "fieldlink-postgres",
        "kanboard_db_port": 5432,
        "kanboard_db": "fieldlink_staff",
        "kanboard_db_user": "fieldlink_staff",
        "kerberos_realm": "KEPLEROPS.TEST",
        "kerberos_allowed_service_classes": ["HTTP"],
        "retained_support_provider": {
            "status": "enabled",
            "provider": "OIDC-FIELDKEST-RETAINED-SUPPORT",
            "metadata_uri": (
                "https://support.keplerops.test/federation/retained-support"
                "/.well-known/openid-configuration"
            ),
            "issuer": "https://support.keplerops.test/federation/retained-support",
            "assertion_submission_endpoint": (
                "https://identity.keplerops.test/api/federation/login"
            ),
        },
        "schema": "fieldkest.staff-config/v1",
    }

    staff_files = {
        "config/staff.json": (json_bytes(config), 0o640),
    }
    records = [
        make_archive(ROOT / "k-staff-state.tar", staff_files),
    ]
    manifest = {
        "schema": "fieldkest.staff-artifacts/v1",
        "generated_at": "2026-11-16T00:00:00Z",
        "archives": records,
        "note": (
            "config/staff.json holds routing and consumer metadata only. "
            "The note draft content lives in osTicket, seeded by seed-k18-note.php."
        ),
    }
    (ROOT / "generation" / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
