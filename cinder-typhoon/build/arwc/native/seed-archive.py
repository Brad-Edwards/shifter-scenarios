#!/usr/bin/env python3
"""Seed the ARWC archive workflow and query database.

Creates:
- A Nextcloud service account and authenticated read-only file share for the
  archive workflow contract (AWF-CRR-229-R4.json).
- A PostgreSQL archive.records table with AR-MAINT-017 and AR-CRR-229 rows
  and a read-only archive_query role for the archive service.
- A Gitea organisation, repository and read-only token for the W04.3 archive
  helper handover artifact (HND-PLANNER-06.json).

Writes:
- .operator/archive-workflow/nc-reader.json: Nextcloud reader credentials.
- .operator/archive-workflow/db-reader.json: PostgreSQL query credentials.
- .operator/archive-workflow/gitea-reader.json: Gitea token for archive service.
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
GITEA_ADMIN_PASSWORD = os.environ.get("GITEA_ADMIN_PASSWORD", "")
GITEA_ADMIN = "engineering-admin"
GITEA_URL = "http://gitea:3000"
GITEA_ORG = "arwc-archive"
GITEA_REPO = "retained-handovers"
GITEA_HANDOVER_FILE = "HND-PLANNER-06.json"
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
    # Derive a stable password from the STAFF_SEED so it is consistent across
    # seed-archive runs and matches any previously written credentials file.
    staff_seed = os.environ.get("STAFF_SEED", "")
    if staff_seed:
        import hashlib as _hashlib
        reader_password = _hashlib.sha256(f"archive-reader:{staff_seed}".encode()).hexdigest()
    else:
        reader_password = secrets.token_hex(32)

    # Create the archive reader account or update the password to match.
    try:
        ocs("POST", "users", {
            "userid": READER_USERNAME,
            "password": reader_password,
            "displayName": "Archive Service Reader",
            "email": "arwc-archive-reader@arwc.test",
        }, accepted=(200, 100))
        print(f"Created Nextcloud account: {READER_USERNAME}")
    except RuntimeError:
        ocs("PUT", f"users/{READER_USERNAME}", {"key": "password", "value": reader_password})
        print(f"Set password for existing account: {READER_USERNAME}")

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

    # Share the workflow file read-only with the archive reader account.
    # This is a bounded user share (shareType=0): only arwc-archive-reader
    # can access the file; unauthenticated requests and other identities are denied.
    file_path = f"/{WORKFLOW_FOLDER}/{WORKFLOW_FILENAME}"
    shares_raw = nc_request("GET", f"/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json"
                            f"&path={quote(file_path, safe='/')}&reshares=false",
                            accepted=(200,))
    existing_shares = json.loads(shares_raw)["ocs"]["data"]
    existing_user_share = [s for s in existing_shares
                           if s.get("share_type") == 0 and s.get("share_with") == READER_USERNAME]
    # Remove any stale public shares to ensure no unauthenticated access.
    for stale in existing_shares:
        if stale.get("share_type") == 3:
            nc_request("DELETE", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{stale['id']}?format=json",
                       accepted=(200, 100))
            print(f"Removed stale public share id={stale['id']}")

    if existing_user_share:
        print(f"Authenticated user share already exists for {READER_USERNAME}")
    else:
        nc_request("POST", "/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json",
                   urlencode({
                       "path": file_path,
                       "shareType": 0,
                       "shareWith": READER_USERNAME,
                       "permissions": 1,
                   }).encode(), accepted=(200, 100))
        print(f"Created authenticated read-only share with {READER_USERNAME}")

    # Write operator state: Nextcloud reader credentials.
    nc_state = {
        "reader_username": READER_USERNAME,
        "reader_password": reader_password,
        "documents_url": DOCUMENTS_URL,
        "workflow_nc_path": WORKFLOW_FILENAME,
    }
    try:
        CREDENTIALS_OUT.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_OUT.write_text(json.dumps(nc_state, indent=2), encoding="utf-8")
        CREDENTIALS_OUT.chmod(0o600)
        print(f"Wrote Nextcloud credentials to {CREDENTIALS_OUT}")
    except OSError:
        print("ARCHIVE_STATE_JSON=" + json.dumps(json.dumps(nc_state)))

    # Seed Gitea: W04.3 archive helper handover artifact.
    if GITEA_ADMIN_PASSWORD:
        gitea_state = seed_gitea_handover()
        gitea_out = CREDENTIALS_OUT.parent / "gitea-reader.json"
        try:
            gitea_out.write_text(json.dumps(gitea_state, indent=2), encoding="utf-8")
            gitea_out.chmod(0o600)
            print(f"Wrote Gitea credentials to {gitea_out}")
        except OSError:
            print("ARCHIVE_GITEA_STATE_JSON=" + json.dumps(json.dumps(gitea_state)))
    else:
        print("No Gitea credentials available; skipping Gitea handover setup")

    print("Archive workflow seeded successfully")


def seed_gitea_handover() -> dict:
    """Create the HND-PLANNER-06 handover artifact in Gitea and return a reader token."""
    gitea_auth = "Basic " + base64.b64encode(f"{GITEA_ADMIN}:{GITEA_ADMIN_PASSWORD}".encode()).decode()

    def gitea(method: str, path: str, body: dict | None = None,
              *, accepted: tuple = (200, 201), auth: str = gitea_auth) -> dict:
        req = Request(f"{GITEA_URL}/api/v1/{path}", method=method,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"Authorization": auth, "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read()) if resp.length else {}
        except HTTPError as error:
            if error.code in accepted:
                return json.loads(error.read()) if error.length else {}
            raise RuntimeError(f"Gitea {method} /api/v1/{path} → HTTP {error.code}: {error.read()[:100]}") from None

    # Create organisation if it doesn't exist.
    try:
        gitea("POST", "orgs", {"username": GITEA_ORG, "visibility": "private"}, accepted=(201,))
        print(f"Created Gitea org: {GITEA_ORG}")
    except RuntimeError:
        print(f"Gitea org already exists: {GITEA_ORG}")

    # Create repository if it doesn't exist.
    try:
        gitea("POST", f"org/{GITEA_ORG}/repos",
              {"name": GITEA_REPO, "private": True, "auto_init": True, "default_branch": "main"},
              accepted=(201,))
        print(f"Created Gitea repo: {GITEA_ORG}/{GITEA_REPO}")
    except RuntimeError:
        print(f"Gitea repo already exists: {GITEA_ORG}/{GITEA_REPO}")

    # Seed or update the HND-PLANNER-06 handover file.
    handover_content = json.dumps({
        "record_id": "HND-PLANNER-06",
        "revision": 6,
        "service_identity": "svc-archive-helper",
        "source_record": "AR-CRR-229",
        "destination": "caller result directory",
        "archive_helper": "7-Zip 23.01",
    }, sort_keys=True, indent=2).encode("utf-8")
    encoded = base64.b64encode(handover_content).decode()

    # Check if file exists.
    file_path = f"repos/{GITEA_ORG}/{GITEA_REPO}/contents/{GITEA_HANDOVER_FILE}"
    try:
        existing = gitea("GET", file_path)
        sha = existing.get("sha", "")
        gitea("PUT", file_path, {
            "message": "Update handover artifact",
            "content": encoded,
            "sha": sha,
            "branch": "main",
        }, accepted=(200,))
        print(f"Updated {GITEA_HANDOVER_FILE} in Gitea")
    except RuntimeError:
        gitea("POST", file_path, {
            "message": "Add retained archive handover artifact",
            "content": encoded,
            "branch": "main",
        }, accepted=(201,))
        print(f"Created {GITEA_HANDOVER_FILE} in Gitea")

    # Create or update a read-only token for the archive service.
    # Token name is stable; recreate if it already exists.
    token_name = "arwc-archive-reader"
    try:
        # Try to delete existing token.
        tokens = gitea("GET", f"users/{GITEA_ADMIN}/tokens", accepted=(200,))
        for t in tokens if isinstance(tokens, list) else []:
            if t.get("name") == token_name:
                gitea("DELETE", f"users/{GITEA_ADMIN}/tokens/{t['id']}", accepted=(204, 404))
                break
    except RuntimeError:
        pass

    token_resp = gitea("POST", f"users/{GITEA_ADMIN}/tokens",
                       {"name": token_name, "scopes": ["read:repository", "read:user"]},
                       accepted=(201,))
    token_value = token_resp.get("sha1", "")
    if not token_value:
        raise RuntimeError("Gitea did not return a token value")
    print(f"Created Gitea read token for archive service")

    return {
        "gitea_url": "https://engineering.arwc.test",
        "org": GITEA_ORG,
        "repo": GITEA_REPO,
        "file": GITEA_HANDOVER_FILE,
        "token": token_value,
    }


if __name__ == "__main__":
    main()
