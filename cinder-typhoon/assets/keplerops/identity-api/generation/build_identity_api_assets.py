#!/usr/bin/env python3
"""Build deterministic k-identity-api state for K18.

config/identity-api.json holds retained_support_provider endpoints and
the initial registration records. No secrets. The revision counter starts
at 1 and is incremented by PATCH; mutable state lives in a named volume
(registrations/) seeded at first boot from the initial registration records.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FIXED_MTIME = 1789729200


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
        "retained_support_provider": {
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
        "registrations": {
            "OIDC-FIELDKEST-SUPPORT": {
                "registration_id": "OIDC-FIELDKEST-SUPPORT",
                "keycloak_client_id": "fieldkest-support",
                "revision": 1,
                "provider_configuration": None,
            },
        },
        "schema": "fieldkest.identity-api-config/v1",
    }

    initial_registration = config["registrations"]["OIDC-FIELDKEST-SUPPORT"]

    files = {
        "config/identity-api.json": (json_bytes(config), 0o640),
        "registrations/OIDC-FIELDKEST-SUPPORT.json": (json_bytes(initial_registration), 0o640),
    }
    records = [make_archive(ROOT / "k-identity-api-state.tar", files)]
    manifest = {
        "schema": "fieldkest.identity-api-artifacts/v1",
        "generated_at": "2026-11-16T00:00:00Z",
        "archives": records,
        "note": (
            "config/identity-api.json holds retained_support_provider endpoints "
            "and initial registration records. No secrets or challenge answers."
        ),
    }
    (ROOT / "generation" / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
