#!/usr/bin/env python3
"""
Generate K03.2 three-stage staging artifact for FKCOL-2841.

Stage chain:
  ODT attachment (staging-FKCOL-2841.bin)
    └─ payload (base64+zlib) → PowerShell with $Stage2
         └─ $Stage2 (base64+zlib) → JavaScript with XOR cipher
              └─ XOR-decrypt → zlib.inflate → S3 manifest JSON

Run from the cinder-typhoon root to regenerate the staging asset and
print updated values for workbench-service.json and restore-pristine.sh.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import zlib

COLLECTION_ID = "FKCOL-2841"
ENDPOINT_ID = "CB-17"
S3_ENDPOINT = "https://objects.keplerops.test"
S3_BUCKET = "fieldlink-collections"

# Deterministic XOR key — 16 bytes, fixed for reproducibility
XOR_KEY_HEX = "a3f7c1e9b5d20864f1c3e7a9b4d60825"

# S3 object content — the predecessor collection recovered in K03.3
_COLLECTION_JSON_PATH = "assets/keplerops/opening/k-dev/FKCOL-2841.json"


def canonical_json(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def xor_encrypt(plaintext: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(plaintext))


def build_manifest(object_key: str, object_sha256: str) -> dict:
    return {
        "endpoint": S3_ENDPOINT,
        "bucket": S3_BUCKET,
        "object_key": object_key,
        "collection_id": COLLECTION_ID,
        "endpoint_id": ENDPOINT_ID,
        "object_sha256": object_sha256,
        "flag": "FLAG{4484ff1616e6aeb5}",
    }


def build_javascript(manifest: dict) -> bytes:
    key_hex = XOR_KEY_HEX
    key = bytes.fromhex(key_hex)
    manifest_bytes = canonical_json(manifest)
    compressed = zlib.compress(manifest_bytes, level=9)
    encrypted = xor_encrypt(compressed, key)
    encoded = base64.b64encode(encrypted).decode()
    return (
        f'// FieldKest collection manifest recovery — stage 3\n'
        f'// Decode: base64 → XOR key → zlib.inflate → JSON manifest\n'
        f'const encoded = "{encoded}";\n'
        f'const key = Buffer.from("{key_hex}", "hex");\n'
        f'const cipher = Buffer.from(encoded, "base64");\n'
        f'const compressed = Buffer.from(cipher.map((v, i) => v ^ key[i % key.length]));\n'
        f'const manifest = JSON.parse(require("zlib").inflateSync(compressed).toString());\n'
        f'module.exports = manifest;\n'
    ).encode()


def build_powershell(stage2_b64: str, stage2_sha256: str) -> bytes:
    return (
        f"$EndpointId = '{ENDPOINT_ID}'\n"
        f"$CollectionId = '{COLLECTION_ID}'\n"
        f"# Stage 2: base64+zlib JavaScript — decode to recover stage 3\n"
        f"$Stage2Sha256 = '{stage2_sha256}'\n"
        f"$Stage2 = '{stage2_b64}'\n"
    ).encode()


def build_instructions() -> bytes:
    return json.dumps(
        {
            "schema": "fieldkest.collection-instructions/v1",
            "flag": "FLAG{40be0052650d9d7a}",
            "instruction_set": "COLLECT-FK-3",
            "encoding": "three-stage: base64+zlib PowerShell, base64+zlib JavaScript, XOR+zlib JSON manifest",
            "endpoint_id": ENDPOINT_ID,
            "collection_id": COLLECTION_ID,
            "integrity_algorithm": "sha256",
            "integrity_input": "UTF-8 callback-stage.ps1 bytes concatenated with FKCOL collection object bytes",
        },
        indent=2,
    ).encode()


def build_staging_bin(
    payload_b64: str,
    payload_sha256: str,
    instructions_b64: str,
    instructions_sha256: str,
    callback_integrity: str,
) -> str:
    return (
        "FIELDKEST-STAGE/2\n"
        f"collection={COLLECTION_ID}\n"
        "payload-encoding=base64+zlib\n"
        f"payload-sha256={payload_sha256}\n"
        "instructions-encoding=base64\n"
        f"instructions-sha256={instructions_sha256}\n"
        f"callback-integrity={callback_integrity}\n"
        "\n"
        f"payload={payload_b64}\n"
        f"instructions={instructions_b64}\n"
    )


def main() -> None:
    # 1. S3 object bytes — read exact bytes from the source file (not re-serialized)
    obj_bytes = Path(_COLLECTION_JSON_PATH).read_bytes()
    obj_sha256 = hashlib.sha256(obj_bytes).hexdigest()
    # Object key matches the seed-objects.sh upload path
    object_key = "callbacks/CB-17/FKCOL-2841.json"

    print(f"[object] key:    {object_key}")
    print(f"[object] sha256: {obj_sha256}")

    # 2. Build S3 manifest
    manifest = build_manifest(object_key, obj_sha256)

    # 3. Build JavaScript (stage 3 → produces manifest)
    javascript = build_javascript(manifest)
    js_sha256 = hashlib.sha256(javascript).hexdigest()
    stage2_zlib = zlib.compress(javascript, level=9)
    stage2_b64 = base64.b64encode(stage2_zlib).decode()
    print(f"[js]     sha256: {js_sha256}")

    # 4. Build PowerShell (stage 2 → carries JavaScript)
    powershell = build_powershell(stage2_b64, js_sha256)
    ps_sha256 = hashlib.sha256(powershell).hexdigest()
    payload_zlib = zlib.compress(powershell, level=9)
    payload_b64 = base64.b64encode(payload_zlib).decode()
    print(f"[ps]     sha256: {ps_sha256}")

    # 5. Build instructions
    instructions = build_instructions()
    inst_sha256 = hashlib.sha256(instructions).hexdigest()
    inst_b64 = base64.b64encode(instructions).decode()

    # 6. Callback integrity = sha256(powershell_bytes + collection_object_bytes)
    # Binds the K03.2 staged script to the K03.3 retrieved collection.
    callback_integrity = hashlib.sha256(powershell + obj_bytes).hexdigest()
    print(f"[cb]     integrity: {callback_integrity}")

    # 7. Build staging bin content
    staging_bin = build_staging_bin(
        payload_b64, ps_sha256, inst_b64, inst_sha256, callback_integrity
    )

    # Write staging bin
    out_bin = "assets/keplerops/opening/k-dev/staging-FKCOL-2841.bin"
    with open(out_bin, "w", encoding="ascii") as f:
        f.write(staging_bin)
    print(f"[staging_bin] written: {out_bin}")

    # 8. Build the ODT deterministically from the authored content and the staging bin.
    # This generator is the sole source of the ODT; build_opening_artifacts.py no longer builds it.
    fixed_time = (2026, 9, 18, 12, 0, 0)
    kdev = Path("assets/keplerops/opening/k-dev")

    def odt_entry(name: str, data: bytes, stored: bool = False) -> tuple[zipfile.ZipInfo, bytes]:
        info = zipfile.ZipInfo(name, fixed_time)
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
        return info, data

    odt_out = kdev / "field-notes-2026-08.odt"
    with zipfile.ZipFile(odt_out, "w") as archive:
        for info, data in (
            odt_entry("mimetype", b"application/vnd.oasis.opendocument.text", stored=True),
            odt_entry("content.xml", (kdev / "field-notes-content.xml").read_bytes()),
            odt_entry("META-INF/manifest.xml", (kdev / "generation/odt-manifest.xml").read_bytes()),
            odt_entry("Attachments/staging-FKCOL-2841.bin", staging_bin.encode("ascii")),
        ):
            archive.writestr(info, data)
    print(f"[odt] built: {odt_out}")

    # 9. Print workbench-service.json update values
    print("\n--- workbench-service.json reconstruction section ---")
    print(json.dumps({
        "script_sha256": ps_sha256,
        "instructions_sha256": inst_sha256,
        "endpoint_id": ENDPOINT_ID,
        "callback_integrity": callback_integrity,
    }, indent=2))

    # 10. Print restore-pristine.sh seeding snippet
    # Object content as a shell-safe single-quoted JSON string is tricky;
    # write it to a temp file approach instead.
    print("\n--- restore-pristine.sh seeding snippet ---")
    print(f"# After services are up, seed the K03 collection object:")
    print(f"# Object content (canonical JSON, one line):")
    print(f"# {obj_bytes.decode()}")
    print(f"# Key: {object_key}")
    print(f"# SHA256: {obj_sha256}")


if __name__ == "__main__":
    main()
