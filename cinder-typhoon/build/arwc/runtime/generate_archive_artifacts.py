#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import tarfile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


ROOT = pathlib.Path("/var/lib/arwc-archive/artifacts")
COLLECTOR = pathlib.Path("/opt/retained-archive/collector-crr")
BUILD_ID = b"COLLECT-CRR-12"
SHARD_SIZE = 96


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def gf_multiply(left: int, right: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
    return product


def gf_power(value: int, exponent: int) -> int:
    result = 1
    for _ in range(exponent):
        result = gf_multiply(result, value)
    return result


def parity(data: list[bytes], row: int) -> bytes:
    result = bytearray(SHARD_SIZE)
    for column, shard in enumerate(data):
        coefficient = gf_power(2, row * column)
        for offset, value in enumerate(shard):
            result[offset] ^= gf_multiply(coefficient, value)
    return bytes(result)


def write(path: pathlib.Path, value: bytes, mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}")
    temporary.write_bytes(value)
    temporary.chmod(mode)
    temporary.replace(path)


def bundle(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name, value in sorted(files.items()):
            item = tarfile.TarInfo(name)
            item.size = len(value)
            item.mode = 0o640
            item.mtime = 1_567_296_000
            item.uid = 0
            item.gid = 0
            item.uname = "archive"
            item.gname = "archive"
            archive.addfile(item, io.BytesIO(value))
    return output.getvalue()


def main() -> None:
    collector = COLLECTOR.read_bytes()
    fragments: list[bytes] = []
    width = (len(collector) + 3) // 4
    for start in range(0, len(collector), width):
        fragments.append(collector[start:start + width])

    fragment_manifest = [
        {"name": f"collector-crr.part-{index:02d}", "size": len(value), "sha256": sha256(value)}
        for index, value in enumerate(fragments)
    ]
    instruction = {
        "schema": "arwc.collector-exchange/v1",
        "collection_id": "COL-CRR-2019-12",
        "collector": "collector-crr",
        "build_id": BUILD_ID.decode(),
        "target": "linux/amd64",
        "collector_sha256": sha256(collector),
        "assembly": "concatenate fragments in numeric order",
        "fragments": fragment_manifest,
    }
    encoded_instruction = json.dumps(
        instruction, sort_keys=True, separators=(",", ":"),
    ).encode()
    if len(encoded_instruction) > SHARD_SIZE * 12:
        raise RuntimeError("collector exchange does not fit its data shards")
    encoded_instruction = encoded_instruction.ljust(SHARD_SIZE * 12, b" ")
    data_shards = [
        encoded_instruction[index:index + SHARD_SIZE]
        for index in range(0, len(encoded_instruction), SHARD_SIZE)
    ]
    shards = data_shards + [parity(data_shards, 12), parity(data_shards, 13)]
    shard_manifest = {
        "schema": "arwc.rs-exchange/v1",
        "collection_id": "COL-CRR-2019-12",
        "codec": "RS(14,12)",
        "field": "GF(256)",
        "primitive_polynomial": "0x11d",
        "generator": 2,
        "parity_rows": [12, 13],
        "row_formula": "V[r,c]=alpha^(r*c)",
        "shard_size": SHARD_SIZE,
        "numeric_order": list(range(14)),
        "missing": [7, 11],
        "sha256": {str(index): sha256(value) for index, value in enumerate(shards)},
    }
    script = b"""# Alterra retained collection handover\n$CollectionId = 'COL-CRR-2019-12'\n$Manifest = 'exchange/manifest.json'\n$MissingDataPositions = @(7, 11)\n# Reassemble numeric data positions 0 through 11 after validating every shard digest.\n"""
    files: dict[str, bytes] = {
        ".field/collect-handover.ps1": script,
        "exchange/manifest.json": json.dumps(shard_manifest, sort_keys=True, indent=2).encode() + b"\n",
    }
    for index, value in enumerate(shards):
        if index not in (7, 11):
            files[f"exchange/shard-{index:02d}.bin"] = value

    key = HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=b"COL-CRR-2019", info=b"collector-config/v3",
    ).derive(BUILD_ID)
    nonce = bytes.fromhex("a1294d017bf3862e69a8420c")
    plaintext = (
        b"archive: ARC-COLD-CRR-2019\n"
        b"service: collect-archive/v3\n"
        b"identity: svc-field-collection\n"
        b"collection: COL-CRR-2019-12\n"
    )
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, b"config/collector.yaml")
    envelope = {
        "schema": "arwc.collector-config/v3",
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext_and_tag": base64.b64encode(ciphertext).decode(),
        "aad": "config/collector.yaml",
    }

    ROOT.mkdir(parents=True, exist_ok=True)
    write(ROOT / "BND-COLLECT-CRR-12.tar.gz", bundle(files))
    write(ROOT / "exchange.json", encoded_instruction.rstrip() + b"\n")
    write(ROOT / "shards.json", json.dumps(
        {str(index): base64.b64encode(value).decode() for index, value in enumerate(shards)},
        sort_keys=True, separators=(",", ":"),
    ).encode() + b"\n")
    write(ROOT / "collector-manifest.json", json.dumps(
        {"collector_sha256": sha256(collector), "build_id": BUILD_ID.decode(), "fragments": fragment_manifest},
        sort_keys=True, separators=(",", ":"),
    ).encode() + b"\n")
    for index, value in enumerate(fragments):
        write(ROOT / f"collector-crr.part-{index:02d}", value)
    write(ROOT / "collector-config.json", json.dumps(
        envelope, sort_keys=True, separators=(",", ":"),
    ).encode() + b"\n")
    write(ROOT / "collector-config.plaintext", plaintext)


if __name__ == "__main__":
    main()
