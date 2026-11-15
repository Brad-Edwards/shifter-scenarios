#!/usr/bin/env python3
"""Fetch the archive workflow contract from Nextcloud at startup.

Reads Nextcloud credentials from /run/arwc-archive-workflow/nc-reader.json
and downloads the workflow contract to the local archive volume so the
retained_archive service does not require Nextcloud on every request.
"""
from __future__ import annotations

import base64
import json
import pathlib
import ssl
import sys
import urllib.error
import urllib.request

CREDENTIALS_PATH = pathlib.Path("/run/arwc-archive-workflow/nc-reader.json")
WORKFLOW_PATH = pathlib.Path("/var/lib/arwc-archive/workflow/AWF-CRR-229-R4.json")
CA_BUNDLE = "/tmp/arwc-ca-bundle.pem"


def main() -> None:
    try:
        exists = CREDENTIALS_PATH.exists()
    except OSError:
        exists = False
    if not exists:
        print("fetch_archive_workflow: no credentials file; using bundled workflow", flush=True)
        return

    try:
        credentials = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"fetch_archive_workflow: cannot read credentials: {error}", flush=True, file=sys.stderr)
        sys.exit(1)

    username = credentials["username"]
    password = credentials["password"]
    documents_url = credentials["documents_url"].rstrip("/")
    workflow_nc_path = credentials["workflow_nc_path"]

    encoded_path = "/".join(urllib.request.quote(part, safe="") for part in workflow_nc_path.split("/"))
    url = f"{documents_url}/remote.php/dav/files/{urllib.request.quote(username, safe='')}/{encoded_path}"
    auth = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()

    ctx = ssl.create_default_context(cafile=CA_BUNDLE)
    request = urllib.request.Request(url, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=30) as response:
            content = response.read()
    except urllib.error.URLError as error:
        print(f"fetch_archive_workflow: cannot fetch workflow from Nextcloud: {error}", flush=True, file=sys.stderr)
        sys.exit(1)

    try:
        parsed = json.loads(content)
        if parsed.get("record_id") != "AWF-CRR-229-R4":
            raise ValueError("unexpected record_id in workflow document")
    except (json.JSONDecodeError, ValueError) as error:
        print(f"fetch_archive_workflow: workflow document is invalid: {error}", flush=True, file=sys.stderr)
        sys.exit(1)

    WORKFLOW_PATH.write_bytes(content)
    WORKFLOW_PATH.chmod(0o600)
    print(f"fetch_archive_workflow: workflow contract fetched from Nextcloud ({len(content)} bytes)", flush=True)


if __name__ == "__main__":
    main()
