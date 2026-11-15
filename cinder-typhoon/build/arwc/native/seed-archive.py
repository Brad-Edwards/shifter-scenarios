#!/usr/bin/env python3
"""Seed the ARWC archive workflow contract into Nextcloud and write reader credentials.

Creates a service account for the archive reader, creates the Corporate Records/Archive
folder, uploads the archive workflow contract, and writes the credentials to
.operator/archive-workflow/nc-reader.json for the archive container to read at startup.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ADMIN = "records-admin"
ADMIN_PASSWORD = os.environ["DOCUMENTS_ADMIN_PASSWORD"]
AUTH = "Basic " + base64.b64encode(f"{ADMIN}:{ADMIN_PASSWORD}".encode()).decode()
DOCUMENTS_URL = "https://documents.arwc.test"
READER_USERNAME = "arwc-archive-reader"
OPERATOR_DIR = Path(os.environ.get("ARWC_OPERATOR_DIR", ".operator"))
CREDENTIALS_OUT = OPERATOR_DIR / "archive-workflow" / "nc-reader.json"
WORKFLOW_FOLDER = "Corporate Records/Archive"
WORKFLOW_FILENAME = "AWF-CRR-229-R4.json"

WORKFLOW_RECORD = {
    "record_id": "AWF-CRR-229-R4",
    "revision": 4,
    "attachment": "ARC-229-A",
    "protected_record": "AR-CRR-229",
    "planner_handover_target": "HND-PLANNER-06",
    "enrollment_profile": {
        "name": "ArchiveSubmitter",
        "common_name": "corporate-reader-principal",
        "extended_key_usage": "clientAuth",
        "organizational_unit": "caller supplied",
        "use": "one time",
    },
}


def nc_request(method: str, path: str, body: bytes | None = None,
               *, accepted: tuple = (200, 201, 204), auth: str = AUTH,
               content_type: str = "application/x-www-form-urlencoded") -> bytes:
    operation = Request(
        f"http://nextcloud{path}", method=method, data=body,
        headers={
            "Host": "documents.arwc.test",
            "Authorization": auth,
            "OCS-APIRequest": "true",
            "Content-Type": content_type,
        },
    )
    try:
        with urlopen(operation, timeout=90) as response:
            if response.status not in accepted:
                raise RuntimeError(f"Nextcloud {method} {path} returned HTTP {response.status}")
            return response.read()
    except HTTPError as error:
        if error.code in accepted:
            return b""
        raise RuntimeError(f"Nextcloud {method} {path} returned HTTP {error.code}: {error.read()[:200]}") from None


def ocs(method: str, path: str, values: dict | None = None, *, accepted: tuple = (200,)) -> dict:
    result = nc_request(
        method, f"/ocs/v2.php/cloud/{path}?format=json",
        urlencode(values).encode() if values is not None else None,
        accepted=accepted,
    )
    if not result:
        return {}
    response = json.loads(result)["ocs"]
    meta = response["meta"]
    if meta.get("status") != "ok" or meta.get("statuscode") not in (100, 200):
        raise RuntimeError(f"OCS {method} {path} failed: {meta}")
    return response.get("data", {})


def webdav(method: str, path: str, body: bytes | None = None,
           *, accepted: tuple = (200, 201, 204, 207),
           content_type: str = "application/octet-stream",
           auth: str = AUTH) -> bytes:
    encoded = "/".join(quote(part, safe="") for part in path.strip("/").split("/"))
    return nc_request(method, f"/remote.php/dav/files/{encoded}", body,
                      accepted=accepted, auth=auth, content_type=content_type)


def ensure_folder(owner: str, folder_path: str, auth: str = AUTH) -> None:
    parts = folder_path.strip("/").split("/")
    for index in range(1, len(parts) + 1):
        partial = "/".join([owner] + parts[:index])
        webdav("MKCOL", partial, accepted=(200, 201, 204, 405), auth=auth)


def main() -> None:
    # Generate a strong password for the archive reader.
    reader_password = secrets.token_hex(32)

    # Create or update the archive reader account.
    try:
        ocs("POST", "users", {
            "userid": READER_USERNAME,
            "password": reader_password,
            "displayName": "Archive Service Reader",
            "email": "arwc-archive-reader@arwc.test",
        }, accepted=(200, 100))
        print(f"Created Nextcloud account: {READER_USERNAME}")
    except RuntimeError:
        # Account exists; set a new password.
        ocs("PUT", f"users/{READER_USERNAME}", {"key": "password", "value": reader_password})
        print(f"Updated password for existing account: {READER_USERNAME}")

    reader_auth = "Basic " + base64.b64encode(f"{READER_USERNAME}:{reader_password}".encode()).decode()

    # Create the archive workflow folder in Nextcloud as admin.
    admin_path = f"{ADMIN}/{WORKFLOW_FOLDER}"
    ensure_folder(ADMIN, WORKFLOW_FOLDER)

    # Upload the workflow contract.
    workflow_content = json.dumps(WORKFLOW_RECORD, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False).encode("utf-8")
    webdav("PUT", f"{ADMIN}/{WORKFLOW_FOLDER}/{WORKFLOW_FILENAME}", workflow_content,
           content_type="application/json")
    print(f"Uploaded {WORKFLOW_FILENAME} to Nextcloud folder '{WORKFLOW_FOLDER}'")

    # Create a public share of the workflow file so the participant can read it
    # directly from Nextcloud without needing Nextcloud credentials.
    public_share_token = None
    pub_shares_raw = nc_request("GET", f"/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json"
                                f"&path=/{quote(WORKFLOW_FOLDER + '/' + WORKFLOW_FILENAME, safe='/')}&reshares=false",
                                accepted=(200,))
    pub_shares = json.loads(pub_shares_raw)["ocs"]["data"]
    existing_public = [s for s in pub_shares if s.get("share_type") == 3]
    if existing_public:
        public_share_token = existing_public[0]["token"]
        print(f"Public share already exists: token={public_share_token}")
    else:
        create_raw = nc_request("POST", "/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json",
                                urlencode({
                                    "path": f"/{WORKFLOW_FOLDER}/{WORKFLOW_FILENAME}",
                                    "shareType": 3,
                                    "permissions": 1,
                                }).encode(), accepted=(200, 100))
        create_data = json.loads(create_raw)["ocs"]["data"]
        public_share_token = create_data["token"]
        print(f"Created public share: token={public_share_token}")

    # Write operator state: reader credentials and public share token.
    state = {
        "reader_username": READER_USERNAME,
        "reader_password": reader_password,
        "documents_url": DOCUMENTS_URL,
        "workflow_nc_path": f"{WORKFLOW_FOLDER.rsplit('/', 1)[-1]}/{WORKFLOW_FILENAME}",
        "public_share_token": public_share_token,
        "public_share_url": f"{DOCUMENTS_URL}/index.php/s/{public_share_token}/download",
    }
    try:
        CREDENTIALS_OUT.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_OUT.write_text(json.dumps(state, indent=2), encoding="utf-8")
        CREDENTIALS_OUT.chmod(0o600)
        print(f"Wrote archive operator state to {CREDENTIALS_OUT}")
    except OSError:
        print("ARCHIVE_STATE_JSON=" + json.dumps(json.dumps(state)))

    print("Archive workflow seeded successfully")


if __name__ == "__main__":
    main()
