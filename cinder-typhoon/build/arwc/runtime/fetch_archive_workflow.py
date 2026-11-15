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

STATE_PATH = pathlib.Path("/run/arwc-archive-workflow/nc-reader.json")
WORKFLOW_PATH = pathlib.Path("/var/lib/arwc-archive/workflow/AWF-CRR-229-R4.json")
SHARE_URL_PATH = pathlib.Path("/var/lib/arwc-archive/workflow/contract-share-url")
CA_BUNDLE = "/tmp/arwc-ca-bundle.pem"
# Keep the old name as an alias for backward compatibility with the entrypoint check.
CREDENTIALS_PATH = STATE_PATH


def main() -> None:
    try:
        exists = CREDENTIALS_PATH.exists()
    except OSError:
        exists = False
    if not exists:
        print(
            f"fetch_archive_workflow: credentials not found at {CREDENTIALS_PATH}; "
            "run seed-archive first",
            flush=True, file=sys.stderr,
        )
        sys.exit(1)

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"fetch_archive_workflow: cannot read state: {error}", flush=True, file=sys.stderr)
        sys.exit(1)

    username = state["reader_username"]
    password = state["reader_password"]
    documents_url = state["documents_url"].rstrip("/")
    workflow_nc_path = state["workflow_nc_path"]
    public_share_url = state.get("public_share_url", "")

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
    # Store the public share URL so the archive service can expose it in its client document.
    if public_share_url:
        SHARE_URL_PATH.write_text(public_share_url, encoding="utf-8")
        SHARE_URL_PATH.chmod(0o600)
    print(f"fetch_archive_workflow: workflow contract fetched from Nextcloud ({len(content)} bytes)", flush=True)


if __name__ == "__main__":
    main()
