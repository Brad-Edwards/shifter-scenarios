#!/usr/bin/env python3
"""Build deterministic exact artifacts for the archived connector operation."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


ROOT = Path(__file__).resolve().parents[1]
GENERATION = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
FIXED_MTIME = 1789736400
REPOSITORY_TIME = "2026-08-22T09:17:42Z"
BUILD_ID = bytes.fromhex("698d42c6a1776e9fc002b91ef68431ad775e0c28")
CONFIG_KEY = bytes.fromhex("dc560f9ef65a1ea203255f0ddd2a9211cc2a2c1464326ed80a0c77a1d970324d")
NONCE = bytes.fromhex("464b44472d3639382d763121")
ROUTE = "/internal/fieldlink/legacy-diagnostics/CRR-OG2"
NOTE = "ENG-FLK-LEGACY-42"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def pretty(value: object) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"


def run(arguments: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    environment = os.environ.copy()
    if env:
        environment.update(env)
    result = subprocess.run(arguments, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def values(value: bytes) -> str:
    return ",".join(f"0x{byte:02x}" for byte in value)


def signed_config(enabled: bool) -> bytes:
    setting = f"diagnostic-loader={'true' if enabled else 'false'}".encode()
    signature = hmac.new(CONFIG_KEY, setting, hashlib.sha256).hexdigest().encode()
    return setting + b"\nsignature=" + signature + b"\n"


def bytecode() -> bytes:
    return b"\x01\x5a\x02\x03\x03" + bytes((4, len(ROUTE))) + ROUTE.encode() + bytes((4, len(NOTE))) + NOTE.encode() + b"\xff"


def build_binary() -> tuple[bytes, bytes]:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"fieldkest-fkdiag-v1", info=b"fieldlink-connector/6.9.8").derive(BUILD_ID)
    encrypted = AESGCM(key).encrypt(NONCE, bytecode(), BUILD_ID.hex().encode())
    container = b"FKDG" + NONCE + len(encrypted[:-16]).to_bytes(4, "big") + encrypted
    rendered = (GENERATION / "fieldlink-connector.cpp.in").read_text()
    rendered = rendered.replace("@FKDIAG_BYTES@", values(container)).replace("@BUILD_ID_BYTES@", values(BUILD_ID)).replace("@CONFIG_KEY_BYTES@", values(CONFIG_KEY))
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        (work / "fieldlink-connector.cpp").write_text(rendered)
        run(["g++", "-std=c++17", "-O2", "-fno-omit-frame-pointer", "-c", "-o", "fieldlink-connector.o", "fieldlink-connector.cpp"], work, {"SOURCE_DATE_EPOCH": str(FIXED_MTIME), "LC_ALL": "C"})
        # Retain the C++ runtime in the executable.  The remaining dynamic ABI
        # is limited to libc and libcrypto.
        run(["g++", "-static-libstdc++", "-static-libgcc", f"-Wl,--build-id=0x{BUILD_ID.hex()}", "-Wl,-Map=fieldlink-connector-6.9.8.map", "-o", "fieldlink-connector", "fieldlink-connector.o", "-lcrypto"], work, {"SOURCE_DATE_EPOCH": str(FIXED_MTIME), "LC_ALL": "C"})
        return (work / "fieldlink-connector").read_bytes(), (work / "fieldlink-connector-6.9.8.map").read_bytes()


def repository(binary: bytes, link_map: bytes) -> tuple[bytes, str]:
    files = {
        "README.md": b"# FieldLink connector archive\n\nRelease Engineering retained the 6.9.8 Linux connector, its link map, ordinary examples, and signed diagnostic configuration for compatibility analysis. Run `bin/fieldlink-connector --config config/ordinary.conf --input examples/fieldkest.bin`; use `config/diagnostic.conf` to reproduce the retained diagnostic loader behavior. The source service also provides the same bounded run through `/api/exercises/connector-archive/run`.\n",
        "bin/fieldlink-connector": binary,
        "maps/fieldlink-connector-6.9.8.map": link_map,
        "config/ordinary.conf": signed_config(False),
        "config/diagnostic.conf": signed_config(True),
        "examples/empty.bin": b"",
        "examples/fieldkest.bin": b"FieldKest",
        "examples/bytes-00-0f.bin": bytes(range(16)),
        "notes/retained-diagnostic.md": b"# Retained diagnostic loader\n\nThe signed `diagnostic-loader` setting activates the embedded `.fkdiag` interpreter. Its key is derived from the raw GNU build ID; the authenticated container uses the build-ID hex as associated data.\n",
    }
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / "connector-archive"
        repo.mkdir()
        run(["git", "init", "--initial-branch=main"], repo)
        run(["git", "config", "core.autocrlf", "false"], repo)
        for name, payload in sorted(files.items()):
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            path.chmod(0o755 if name == "bin/fieldlink-connector" else 0o644)
        run(["git", "add", "-A"], repo)
        identity = {"GIT_AUTHOR_NAME": "FieldKest Release Engineering", "GIT_AUTHOR_EMAIL": "release-engineering@keplerops.test", "GIT_AUTHOR_DATE": REPOSITORY_TIME, "GIT_COMMITTER_NAME": "FieldKest Release Engineering", "GIT_COMMITTER_EMAIL": "release-engineering@keplerops.test", "GIT_COMMITTER_DATE": REPOSITORY_TIME}
        run(["git", "commit", "-m", "Retain FieldLink connector 6.9.8 diagnostics"], repo, identity)
        commit = run(["git", "rev-parse", "HEAD"], repo)
        run(["git", "-c", "tag.gpgSign=false", "tag", "fieldlink-6.9.8", commit], repo)
        bundle = Path(temporary) / "connector-archive.bundle"
        run(["git", "bundle", "create", str(bundle), "--all"], repo)
        return bundle.read_bytes(), commit


def archive(path: Path, files: dict[str, tuple[bytes, int]]) -> dict[str, object]:
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as output:
        directories = {str(parent) for name in files for parent in Path(name).parents if str(parent) != "."}
        for name in sorted(directories, key=lambda item: (item.count("/"), item)):
            info = tarfile.TarInfo(name + "/"); info.type = tarfile.DIRTYPE; info.mode = 0o750; info.mtime = FIXED_MTIME; info.uid = info.gid = 1000; info.uname = info.gname = "fieldkest"; output.addfile(info)
        for name, (payload, mode) in sorted(files.items()):
            info = tarfile.TarInfo(name); info.size = len(payload); info.mode = mode; info.mtime = FIXED_MTIME; info.uid = info.gid = 1000; info.uname = info.gname = "fieldkest"; output.addfile(info, io.BytesIO(payload))
    return {"archive": path.name, "sha256": sha(path.read_bytes()), "size": path.stat().st_size, "files": [{"path": name, "mode": f"{mode:04o}", "sha256": sha(payload), "size": len(payload)} for name, (payload, mode) in sorted(files.items())]}


def main() -> None:
    if SOURCE.exists(): shutil.rmtree(SOURCE)
    SOURCE.mkdir(parents=True)
    binary, link_map = build_binary()
    bundle, commit = repository(binary, link_map)
    service = {"schema": "fieldkest.connector-archive-service/v1", "version": "6.9.8", "build_id": BUILD_ID.hex(), "binary_sha256": sha(binary), "repository_commit": commit, "route": ROUTE, "note_id": NOTE, "corpus": [{"name": name, "input_hex": payload.hex()} for name, payload in (("empty", b""), ("fieldkest", b"FieldKest"), ("bytes-00-0f", bytes(range(16))))]}
    for name, payload in (("fieldlink-connector", binary), ("fieldlink-connector-6.9.8.map", link_map), ("connector-archive.bundle", bundle), ("connector-archive-service.json", pretty(service))): (SOURCE / name).write_bytes(payload)
    handoff = b"# Connector archive review\n\nThe retained `fieldkest/connector-archive` repository is available from FieldKest Source with the saved developer credential. Compare the ordinary and signed diagnostic examples; the repository note describes the authenticated embedded module.\n"
    records = [archive(ROOT / "k-source-k28-state.tar", {"seeds/connector-archive.bundle": (bundle, 0o640), "config/k28.json": (pretty(service), 0o600), "exercises/k28/fieldlink-connector": (binary, 0o550)}), archive(ROOT / "k-dev-k28-home.tar", {"work/build-operations/connector-archive-review.md": (handoff, 0o640)})]
    manifest = {"schema": "fieldkest.k28-artifacts/v1", "binary": {"version": "6.9.8", "architecture": "linux-x86_64-elf", "build_id": BUILD_ID.hex(), "sha256": sha(binary), "link_map_sha256": sha(link_map)}, "repository": {"repository": "fieldkest/connector-archive", "commit": commit, "bundle_sha256": sha(bundle)}, "archives": records}
    (ROOT / "artifact-manifest.json").write_bytes(pretty(manifest))


if __name__ == "__main__": main()
