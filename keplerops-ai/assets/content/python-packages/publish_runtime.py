#!/usr/bin/env python3
"""Publish the committed challenge wheel through Gitea's real PyPI API."""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import secrets
import ssl
import zipfile
from email.parser import BytesParser
from pathlib import Path


REPOSITORY_HOST = "repo-ticket-01.keplerops.lab"
REPOSITORY_PATH = "/git/api/packages/ml.engineer/pypi"
CREDENTIAL_PATH = Path("/opt/keplerops/synthetic-defaults.yaml")
WHEEL_PATH = Path(
    "/home/kasm-user/Desktop/keplerops_eval_runtlme-1.0.0-py3-none-any.whl"
)
EXPECTED_NAME = "keplerops-eval-runtlme"
EXPECTED_VERSION = "1.0.0"
CREDENTIAL_ERROR = "WorkHub package credential is unavailable"


def _credentials() -> tuple[str, str]:
    lines = CREDENTIAL_PATH.read_text(encoding="utf-8").splitlines()
    markers = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "- id: cred-ml-engineer"
    ]
    if len(markers) != 1 or markers[0] + 2 >= len(lines):
        raise ValueError(CREDENTIAL_ERROR)
    index = markers[0]
    username_line = lines[index + 1].strip()
    password_line = lines[index + 2].split("#", 1)[0].strip()
    if not username_line.startswith("username: ") or not password_line.startswith(
        "password: "
    ):
        raise ValueError(CREDENTIAL_ERROR)
    username = username_line.removeprefix("username: ").strip('"')
    password = password_line.removeprefix("password: ").strip('"')
    if username != "ml.engineer" or not 16 <= len(password) <= 128:
        raise ValueError(CREDENTIAL_ERROR)
    return username, password


def _metadata() -> tuple[str, str, str]:
    with zipfile.ZipFile(WHEEL_PATH) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("wheel metadata is missing or ambiguous")
        metadata = BytesParser().parsebytes(archive.read(names[0]))
    name = metadata.get("Name", "")
    version = metadata.get("Version", "")
    summary = metadata.get("Summary", "")
    if name != EXPECTED_NAME or version != EXPECTED_VERSION:
        raise ValueError("wheel identity does not match the challenge artifact")
    return name, version, summary


def _multipart(fields: list[tuple[str, str]]) -> tuple[str, bytes]:
    boundary = "keplerops-" + secrets.token_hex(16)
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            )
        )
    chunks.extend(
        (
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="content"; '
                f'filename="{WHEEL_PATH.name}"\r\n'
            ).encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            WHEEL_PATH.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        )
    )
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


def publish() -> dict[str, str]:
    if not WHEEL_PATH.is_file() or WHEEL_PATH.stat().st_size > 1_048_576:
        raise ValueError("expected one bounded wheel artifact")
    name, version, summary = _metadata()
    digest = hashlib.sha256(WHEEL_PATH.read_bytes()).hexdigest()
    fields = [
        (":action", "file_upload"),
        ("protocol_version", "1"),
        ("metadata_version", "2.1"),
        ("name", name),
        ("version", version),
        ("summary", summary),
        ("filetype", "bdist_wheel"),
        ("pyversion", "py3"),
        ("sha256_digest", digest),
    ]
    content_type, body = _multipart(fields)
    username, password = _credentials()
    headers = {
        "Content-Type": content_type,
        "Authorization": (
            "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
        ),
    }
    context = ssl.create_default_context(cafile="/run/tls/ca.crt")
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = http.client.HTTPSConnection(
        REPOSITORY_HOST, timeout=20, context=context
    )
    try:
        connection.request("POST", REPOSITORY_PATH, body=body, headers=headers)
        response = connection.getresponse()
        status = response.status
        response.read(65_536)
    finally:
        connection.close()
    if status not in {201, 409}:
        raise RuntimeError(f"package publication failed with HTTP {status}")
    return {
        "name": name,
        "version": version,
        "wheel_digest": "sha256:" + digest,
        "publication": "created" if status == 201 else "already-present",
    }


def main() -> int:
    print(json.dumps(publish()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
