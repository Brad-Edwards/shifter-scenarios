#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import tarfile
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_wrap
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, load_pem_private_key
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.x509.oid import NameOID


ROOT = pathlib.Path("/var/lib/arwc-archive/artifacts")
COLLECTOR = pathlib.Path("/opt/retained-archive/collector-crr")
BUILD_ID = b"COLLECT-CRR-12"
SHARD_SIZE = 96
ARCHIVE_ID = b"ARC-COLD-CRR-2019"


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

    archive_keys = HKDF(
        algorithm=hashes.SHA256(), length=64,
        salt=ARCHIVE_ID, info=b"aqtn1/keys",
    ).derive(BUILD_ID)
    content_key, wrapping_key = archive_keys[:32], archive_keys[32:]
    historical_key = ed25519.Ed25519PrivateKey.generate()
    historical_pkcs8 = historical_key.private_bytes(
        Encoding.DER, PrivateFormat.PKCS8, NoEncryption(),
    )
    if len(historical_pkcs8) % 8:
        raise RuntimeError("historical PKCS#8 object is not AES-KW aligned")
    wrapped_pkcs8 = aes_key_wrap(wrapping_key, historical_pkcs8)

    ca_certificate = x509.load_pem_x509_certificate(pathlib.Path("/tmp/archive-ca.crt").read_bytes())
    ca_key = load_pem_private_key(pathlib.Path("/tmp/archive-ca.key").read_bytes(), password=None)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "COLLECT-2019-12"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Alterra Regional Water Company"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "svc-field-collection"),
    ])
    now = datetime.now(timezone.utc)
    historical_certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_certificate.subject)
        .public_key(historical_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=3650))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    rollover = {
        "record_id": "IDREL-COL-R4",
        "revision": 4,
        "historical_identity": "svc-field-collection",
        "current_service": "collect-archive/v3",
        "dataset": "CUR-COL-CRR-R11",
        "dataset_revision": 11,
        "retired_subject": True,
    }
    rollover_bytes = json.dumps(rollover, sort_keys=True, separators=(",", ":")).encode()
    rollover_signature = ca_key.sign(rollover_bytes, padding.PKCS1v15(), hashes.SHA256())
    collection = {
        "schema": "arwc.cold-archive/v1",
        "archive_id": ARCHIVE_ID.decode(),
        "index_revision": "R6",
        "maintenance_records": [
            {
                "record_id": f"MR-CRR-2019-{index:03d}",
                "immutable": True,
                "asset": "AST-CRR-017" if index in (4, 19, 37) else f"AST-CRR-{100 + index:03d}",
                "status": "closed",
            }
            for index in range(1, 38)
        ],
        "retired_client_certificate": historical_certificate.public_bytes(Encoding.PEM).decode(),
        "retired_certificate_id": "COLLECT-2019-12",
        "wrapped_pkcs8": base64.b64encode(wrapped_pkcs8).decode(),
        "rollover": dict(rollover, signature=base64.b64encode(rollover_signature).decode()),
    }
    archive_plaintext = json.dumps(collection, sort_keys=True, separators=(",", ":")).encode()
    metadata = {
        "schema": "AQTN1",
        "object_id": "QTN-COL-2019-12",
        "collector_build_id": BUILD_ID.decode(),
        "archive_id": ARCHIVE_ID.decode(),
        "nonce_length": 12,
        "tag_placement": "ciphertext suffix",
        "byte_order": "big-endian",
    }
    metadata_header = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    archive_nonce = bytes.fromhex("01a9c40fd87251be11d2a760")
    encrypted_archive = AESGCM(content_key).encrypt(
        archive_nonce, archive_plaintext, metadata_header,
    )
    frame = (
        b"AQTN1" + len(metadata_header).to_bytes(4, "big") +
        len(encrypted_archive).to_bytes(8, "big") + hashlib.sha256(encrypted_archive).digest() +
        len(BUILD_ID).to_bytes(2, "big") + BUILD_ID + archive_nonce +
        metadata_header + encrypted_archive
    )

    sample_plaintext = b"collector sample: Cairn Reach / 2019-12"
    sample_nonce = bytes.fromhex("1112131415161718191a1b1c")
    sample_aad = b"AQTN1/sample/1"
    sample_ciphertext = AESGCM(content_key).encrypt(sample_nonce, sample_plaintext, sample_aad)
    kw_sample_plaintext = bytes(range(32))
    samples = {
        "schema": "arwc.aqtn1-samples/v1",
        "samples": [
            {
                "sample_id": "AQTN1-GCM-01",
                "operation": "AES-256-GCM decrypt",
                "nonce": base64.b64encode(sample_nonce).decode(),
                "aad": base64.b64encode(sample_aad).decode(),
                "ciphertext_and_tag": base64.b64encode(sample_ciphertext).decode(),
            },
            {
                "sample_id": "AQTN1-KW-02",
                "operation": "AES-256-KW unwrap",
                "wrapped": base64.b64encode(aes_key_wrap(wrapping_key, kw_sample_plaintext)).decode(),
            },
            {
                "sample_id": "AQTN1-AUTH-03",
                "operation": "AES-256-GCM reject",
                "nonce": base64.b64encode(sample_nonce).decode(),
                "aad": base64.b64encode(sample_aad).decode(),
                "ciphertext_and_tag": base64.b64encode(sample_ciphertext[:-1] + bytes([sample_ciphertext[-1] ^ 1])).decode(),
            },
        ],
    }
    write(ROOT / "QTN-COL-2019-12.aqtn", frame)
    write(ROOT / "AQTN1-samples.json", json.dumps(samples, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    write(ROOT / "cold-archive.plaintext", archive_plaintext)
    write(ROOT / "historical-key.pkcs8", historical_pkcs8)
    write(ROOT / "historical-certificate.pem", historical_certificate.public_bytes(Encoding.PEM))
    write(ROOT / "rollover.json", json.dumps(
        dict(rollover, signature=base64.b64encode(rollover_signature).decode()),
        sort_keys=True, separators=(",", ":"),
    ).encode() + b"\n")
    write(ROOT / "sample-results.json", json.dumps({
        "AQTN1-GCM-01": hashlib.sha256(sample_plaintext).hexdigest(),
        "AQTN1-KW-02": hashlib.sha256(kw_sample_plaintext).hexdigest(),
        "AQTN1-AUTH-03": "authentication_failed",
    }, sort_keys=True, separators=(",", ":")).encode() + b"\n")


if __name__ == "__main__":
    main()
