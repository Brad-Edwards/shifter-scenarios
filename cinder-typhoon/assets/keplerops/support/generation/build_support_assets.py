#!/usr/bin/env python3
"""Build deterministic k-support state for K18.4.

Generates an RSA-2048 key pair for the RETAINED_SUPPORT federation provider.
The private key signs assertions; the public key verifies them.
The dossier DOS-ARWC-HIST-01 and customer record CUSTREC-047-R6 are seeded
in PostgreSQL by seed-k18-customer.py (not shipped in this tar).

Nothing in this tar is a challenge answer; the answer is CUSTREC-047-R6
in PostgreSQL, only readable via a valid federated session.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

ROOT = Path(__file__).resolve().parents[1]
FIXED_MTIME = 1789729200

# Fixed key generation seed — deterministic via fixed p, q primes embedded
# in the generation script. Using cryptography library's standard key gen
# with a reproducible invocation (key is committed, not regenerated each time).
_PRIVATE_KEY_PATH = ROOT / "generation" / "retained-support-private.pem"
_PUBLIC_KEY_PATH = ROOT / "generation" / "retained-support-public.pem"


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
    if not _PRIVATE_KEY_PATH.exists() or not _PUBLIC_KEY_PATH.exists():
        raise FileNotFoundError(
            "RSA key pair not found. Run generate_keypair.py first."
        )

    private_pem = _PRIVATE_KEY_PATH.read_bytes()
    public_pem = _PUBLIC_KEY_PATH.read_bytes()

    # Dossier DOS-ARWC-HIST-01: the history dossier for TEN-ARWC-047.
    # reviewer_federation points to the RETAINED_SUPPORT provider.
    # customer_record is the protected record ID (not the content).
    dossier = {
        "dossier_id": "DOS-ARWC-HIST-01",
        "tenant": "TEN-ARWC-047",
        "case": "SUP-2841",
        "recurring_case": "SUP-2841",
        "account": "K-C-001",
        "reviewer_federation": {
            "provider": "OIDC-FIELDKEST-RETAINED-SUPPORT",
            "tenant": "TEN-ARWC-047",
            "subject": "urn:fieldkest:pairwise:7c0e4f2a-2e62-4d80-a279-1fdb4f02b6c7",
        },
        "customer_record": "CUSTREC-047-R6",
    }

    files = {
        "keys/retained-support-private.pem": (private_pem, 0o600),
        "keys/retained-support-public.pem": (public_pem, 0o640),
        "dossiers/DOS-ARWC-HIST-01.json": (json_bytes(dossier), 0o640),
    }
    records = [make_archive(ROOT / "k-support-k18-state.tar", files)]
    manifest = {
        "schema": "fieldkest.support-k18-artifacts/v1",
        "generated_at": "2026-11-16T00:00:00Z",
        "archives": records,
        "note": (
            "RSA key pair for RETAINED_SUPPORT federation. "
            "Private key signs assertions at /federation/retained-support/assertions. "
            "Public key verifies at /api/federation/login. "
            "No challenge answer is in this tar."
        ),
    }
    (ROOT / "generation" / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
