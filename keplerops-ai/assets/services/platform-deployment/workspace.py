"""Fixed Cloud Run workspace that emits bounded deterministic integrity evidence."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
from pathlib import Path
from urllib.parse import urlparse

from google.cloud import storage


WORKSPACE_ID = re.compile(r"^workspace-[0-9a-f]{12}-[0-9a-f]{16}$")
INVENTORY_ROOT = Path("/opt/keplerops/platform-deployment")
MAX_FILES = 128
MAX_FILE_BYTES = 4_194_304
MAX_RESULT_BYTES = 1_048_576


def export_target(value: str, workspace_id: str) -> tuple[str, str]:
    parsed = urlparse(value)
    if parsed.scheme != "gs" or not parsed.netloc or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("KEPLEROPS_EXPORT_URI must be a plain gs:// bucket prefix")
    prefix = parsed.path.lstrip("/")
    if not prefix.endswith(f"{workspace_id}/") or ".." in prefix.split("/"):
        raise ValueError("export URI must terminate at the broker-owned workspace prefix")
    return parsed.netloc, prefix


def inventory(root: Path) -> list[dict[str, object]]:
    resolved_root = root.resolve(strict=True)
    files: list[dict[str, object]] = []
    for candidate in sorted(root.rglob("*")):
        details = candidate.lstat()
        if stat.S_ISLNK(details.st_mode):
            raise RuntimeError("workspace inventory does not follow symbolic links")
        if not stat.S_ISREG(details.st_mode):
            continue
        if len(files) >= MAX_FILES:
            raise RuntimeError("workspace inventory exceeds the file-count bound")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root) or details.st_size > MAX_FILE_BYTES:
            raise RuntimeError("workspace inventory file is outside its fixed bounds")
        content = candidate.read_bytes()
        if len(content) != details.st_size:
            raise RuntimeError("workspace inventory file changed during capture")
        files.append(
            {
                "path": resolved.relative_to(resolved_root).as_posix(),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return files


def integrity_inventory() -> dict[str, object]:
    workspace_id = os.environ.get("KEPLEROPS_WORKSPACE_ID", "")
    if not WORKSPACE_ID.fullmatch(workspace_id):
        raise RuntimeError("KEPLEROPS_WORKSPACE_ID was not broker-issued")
    bucket_name, prefix = export_target(os.environ.get("KEPLEROPS_EXPORT_URI", ""), workspace_id)
    result = {
        "schema_version": 1,
        "operation": "integrity-inventory",
        "workspace_id": workspace_id,
        "runtime": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "machine": platform.machine(),
        },
        "files": inventory(INVENTORY_ROOT),
    }
    encoded = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_RESULT_BYTES:
        raise RuntimeError("workspace evidence exceeds the result bound")
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(prefix + "integrity-inventory.json")
    blob.upload_from_string(
        encoded,
        content_type="application/json",
        checksum="auto",
        if_generation_match=0,
    )
    return {
        "workspace_id": workspace_id,
        "object": f"gs://{bucket_name}/{blob.name}",
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def main() -> None:
    import sys

    if sys.argv[1:] != ["integrity-inventory"]:
        raise SystemExit("only the fixed integrity-inventory workspace is supported")
    print(json.dumps(integrity_inventory(), sort_keys=True))


if __name__ == "__main__":
    main()
