#!/usr/bin/env python3
"""Build deterministic release-lineage repository and verification material."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
FIXED_MTIME = 1789736400
OLD_KEY_ID = "fk-release-2026-old"
NEXT_KEY_ID = "fk-release-2026-next"
LINEAGE = "fieldkest-release-2026"
HALF_A = "Rollover-REL742-"
HALF_B = "SignerHistory-6Yp4"
NONCE = bytes.fromhex("4b32392d52454c3734322121")


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    values = os.environ.copy(); values.update(env or {})
    result = subprocess.run(args, cwd=cwd, env=values, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def archive(path: Path, files: dict[str, tuple[bytes, int]]) -> dict[str, object]:
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as output:
        directories = {str(parent) for name in files for parent in Path(name).parents if str(parent) != "."}
        for name in sorted(directories, key=lambda item: (item.count("/"), item)):
            info = tarfile.TarInfo(name + "/"); info.type = tarfile.DIRTYPE; info.mode = 0o750; info.mtime = FIXED_MTIME; info.uid = info.gid = 1000; info.uname = info.gname = "fieldkest"; output.addfile(info)
        for name, (payload, mode) in sorted(files.items()):
            info = tarfile.TarInfo(name); info.size = len(payload); info.mode = mode; info.mtime = FIXED_MTIME; info.uid = info.gid = 1000; info.uname = info.gname = "fieldkest"; output.addfile(info, io.BytesIO(payload))
    return {"archive": path.name, "sha256": sha(path.read_bytes()), "size": path.stat().st_size}


def main() -> None:
    seed = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"fieldkest-release-2026", info=b"deleted-signer-seed").derive(b"CinderTyphoon-K29.2")
    private = Ed25519PrivateKey.from_private_bytes(seed)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    next_seed = hashlib.sha256(b"FieldKest release next key 2026").digest()
    next_public = Ed25519PrivateKey.from_private_bytes(next_seed).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    salt = hashlib.sha256(b"fieldkest-k29-wrap-salt").digest()[:16]
    wrapping_key = hashlib.scrypt((HALF_A + HALF_B).encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    encrypted = AESGCM(wrapping_key).encrypt(NONCE, seed, OLD_KEY_ID.encode())
    wrapped = {"schema": "fieldkest.encrypted-signer-seed/v1", "key_id": OLD_KEY_ID, "lineage": LINEAGE, "kdf": {"name": "scrypt", "n": 16384, "r": 8, "p": 1, "salt_base64": base64.b64encode(salt).decode()}, "cipher": {"name": "AES-256-GCM", "nonce_base64": base64.b64encode(NONCE).decode(), "ciphertext_base64": base64.b64encode(encrypted[:-16]).decode(), "tag_base64": base64.b64encode(encrypted[-16:]).decode(), "aad": OLD_KEY_ID}}
    if SOURCE.exists(): shutil.rmtree(SOURCE)
    SOURCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / "release-signer-history"; repo.mkdir()
        run(["git", "init", "--initial-branch=main"], repo); run(["git", "config", "core.autocrlf", "false"], repo)
        (repo / "secrets").mkdir(); (repo / "secrets/release-signer.enc.json").write_bytes(canonical(wrapped) + b"\n")
        (repo / "signer-history.json").write_bytes(canonical({"schema": "fieldkest.signer-history/v1", "lineage": LINEAGE, "key_id": OLD_KEY_ID, "passphrase_half": HALF_B, "status": "accepted-until-cutoff"}) + b"\n")
        identity = {"GIT_AUTHOR_NAME": "FieldKest Release Engineering", "GIT_AUTHOR_EMAIL": "release-engineering@keplerops.test", "GIT_AUTHOR_DATE": "2026-08-25T11:04:19Z", "GIT_COMMITTER_NAME": "FieldKest Release Engineering", "GIT_COMMITTER_EMAIL": "release-engineering@keplerops.test", "GIT_COMMITTER_DATE": "2026-08-25T11:04:19Z"}
        run(["git", "add", "-A"], repo); run(["git", "commit", "-m", "Record encrypted release signer rollover"], repo, identity); deleted_commit = run(["git", "rev-parse", "HEAD"], repo)
        (repo / "secrets/release-signer.enc.json").unlink()
        (repo / "README.md").write_text("# FieldKest release signer history\n\nThis repository records the accepted release lineage, public verification key, and rollover history. Encrypted retired signer material was removed from the current tree.\n")
        (repo / "release-public-key.json").write_bytes(canonical({"schema": "fieldkest.release-key/v1", "algorithm": "Ed25519", "lineage": LINEAGE, "key_id": OLD_KEY_ID, "public_key_base64": base64.b64encode(public).decode()}) + b"\n")
        run(["git", "add", "-A"], repo); run(["git", "commit", "-m", "Publish verification key and retire signer object"], repo, {**identity, "GIT_AUTHOR_DATE": "2026-09-02T08:31:06Z", "GIT_COMMITTER_DATE": "2026-09-02T08:31:06Z"}); current_commit = run(["git", "rev-parse", "HEAD"], repo)
        bundle = Path(temporary) / "release-signer-history.bundle"; run(["git", "bundle", "create", str(bundle), "--all"], repo)
        (SOURCE / "release-signer-history.bundle").write_bytes(bundle.read_bytes())
    config = {"schema": "fieldkest.release-lineage/v1", "lineage": LINEAGE, "old_key_id": OLD_KEY_ID, "old_public_key_base64": base64.b64encode(public).decode(), "next_key_id": NEXT_KEY_ID, "next_public_key_base64": base64.b64encode(next_public).decode(), "cutoff": "2026-09-30T12:00:00Z", "rollover_passphrase_half": HALF_A, "deleted_commit": deleted_commit, "current_commit": current_commit}
    (SOURCE / "release-lineage.json").write_bytes(canonical(config) + b"\n")
    source_record = archive(ROOT / "k-source-k29-state.tar", {"seeds/release-signer-history.bundle": ((SOURCE / "release-signer-history.bundle").read_bytes(), 0o640), "config/k29.json": (canonical(config) + b"\n", 0o600)})
    registry_record = archive(ROOT / "k-registry-k29-state.tar", {"config/k29.json": (canonical(config) + b"\n", 0o600)})
    ci_record = archive(ROOT / "k-ci-k29-state.tar", {"records/release-dossier.json": (canonical({"schema": "fieldkest.release-dossier/v1", "build_id": "BLD-REL-742", "repository": "fieldkest/release-signer-history", "deleted_commit": deleted_commit, "rollover_record": {"record_id": "ROLLOVER-2026-09", "passphrase_half": HALF_A}, "interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"]}) + b"\n", 0o600), "config/k29.json": (canonical(config) + b"\n", 0o600)})
    dev_record = archive(ROOT / "k-dev-k29-home.tar", {"work/build-operations/release-lineage-review.md": (b"# Release lineage review\n\nBuild record BLD-REL-742 names the retained signer-history repository and its protected dossier. Validate a fresh package signature against the accepted lineage before rehearsal.\n", 0o640)})
    manifest = {"schema": "fieldkest.k29-artifacts/v1", "repository": {"current_commit": current_commit, "deleted_commit": deleted_commit, "bundle_sha256": sha((SOURCE / "release-signer-history.bundle").read_bytes())}, "lineage": {k: config[k] for k in ("lineage", "old_key_id", "old_public_key_base64", "next_key_id", "next_public_key_base64", "cutoff")}, "archives": [source_record, registry_record, ci_record, dev_record]}
    (ROOT / "artifact-manifest.json").write_bytes(json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")


if __name__ == "__main__": main()
