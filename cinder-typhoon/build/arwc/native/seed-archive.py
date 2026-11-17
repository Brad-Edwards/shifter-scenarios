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
PLANNER_READER_USERNAME = "arwc-planner-reader"
OPERATOR_DIR = Path(os.environ.get("ARWC_OPERATOR_DIR", ".operator"))
CREDENTIALS_OUT = OPERATOR_DIR / "archive-workflow" / "nc-reader.json"
WORKFLOW_FOLDER = "Corporate Records/Archive"
WORKFLOW_FILENAME = "AWF-CRR-229-R4.json"
PLANNING_FOLDER = "Corporate Records/Planning"
PLANNING_FILENAME = "RENDER-CRR-882.json"
OAUTH_CONTEXT_FILENAME = "OAUTH-PLN-882.json"

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
    "flag": "FLAG{57f6312a585e7e4b}",
}

PLANNING_RECORD = {
    "record_id": "RENDER-CRR-882",
    "revision": 8,
    "planner": "nadia.corvane",
    "drawing": "DRW-OG2-R8",
    "review": "REV-CRR-4417",
    "oauth_transaction": "OAUTH-PLN-882",
    "browser_profile": "planner-review-3",
}

# OAUTH-PLN-882.json is the planning OAuth context for the drawing review callback.
# oauth_state is derived from STAFF_SEED so it is stable across seed runs.
# pending_origin is the expected (legitimate) preview callback origin.
def _make_oauth_context_record(oauth_state: str) -> dict:
    return {
        "transaction": "OAUTH-PLN-882",
        "oauth_state": oauth_state,
        "drawing": "DRW-OG2-R8",
        "review": "REV-CRR-4417",
        "pending_origin": "https://drawing-preview.arwc.test",
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

    # Seed Nextcloud planner reader: W06.1 planning rendering record.
    if staff_seed:
        import hashlib as _hashlib
        planner_password = _hashlib.sha256(f"planner-reader:{staff_seed}".encode()).hexdigest()
    else:
        planner_password = secrets.token_hex(32)

    try:
        ocs("POST", "users", {
            "userid": PLANNER_READER_USERNAME,
            "password": planner_password,
            "displayName": "Planning Service Reader",
            "email": "arwc-planner-reader@arwc.test",
        }, accepted=(200, 100))
        print(f"Created Nextcloud account: {PLANNER_READER_USERNAME}")
    except RuntimeError:
        ocs("PUT", f"users/{PLANNER_READER_USERNAME}", {"key": "password", "value": planner_password})
        print(f"Set password for existing account: {PLANNER_READER_USERNAME}")

    # Create the planning folder and upload the planning rendering record.
    ensure_folder(ADMIN, PLANNING_FOLDER)
    planning_content = json.dumps(PLANNING_RECORD, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False).encode("utf-8")
    webdav("PUT", f"{ADMIN}/{PLANNING_FOLDER}/{PLANNING_FILENAME}", planning_content,
           content_type="application/json")
    print(f"Uploaded {PLANNING_FILENAME} to Nextcloud folder '{PLANNING_FOLDER}'")

    # Share the planning file read-only with the planner reader account.
    planning_file_path = f"/{PLANNING_FOLDER}/{PLANNING_FILENAME}"
    planning_shares_raw = nc_request(
        "GET", f"/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json"
        f"&path={quote(planning_file_path, safe='/')}&reshares=false",
        accepted=(200,),
    )
    existing_planning_shares = json.loads(planning_shares_raw)["ocs"]["data"]
    existing_planner_share = [s for s in existing_planning_shares
                              if s.get("share_type") == 0 and s.get("share_with") == PLANNER_READER_USERNAME]
    for stale in existing_planning_shares:
        if stale.get("share_type") == 3:
            nc_request("DELETE", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{stale['id']}?format=json",
                       accepted=(200, 100))
            print(f"Removed stale public share on planning file id={stale['id']}")

    if existing_planner_share:
        print(f"Authenticated user share already exists for {PLANNER_READER_USERNAME}")
    else:
        nc_request("POST", "/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json",
                   urlencode({
                       "path": planning_file_path,
                       "shareType": 0,
                       "shareWith": PLANNER_READER_USERNAME,
                       "permissions": 1,
                   }).encode(), accepted=(200, 100))
        print(f"Created authenticated read-only share with {PLANNER_READER_USERNAME}")

    # Seed Nextcloud planner reader: W06.2 OAuth context for drawing review callback.
    if staff_seed:
        import hashlib as _hashlib2
        oauth_state = _hashlib2.sha256(f"planning-oauth-state:{staff_seed}".encode()).hexdigest()
    else:
        oauth_state = secrets.token_hex(32)

    oauth_context_record = _make_oauth_context_record(oauth_state)
    oauth_context_content = json.dumps(oauth_context_record, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False).encode("utf-8")
    webdav("PUT", f"{ADMIN}/{PLANNING_FOLDER}/{OAUTH_CONTEXT_FILENAME}", oauth_context_content,
           content_type="application/json")
    print(f"Uploaded {OAUTH_CONTEXT_FILENAME} to Nextcloud folder '{PLANNING_FOLDER}'")

    # Share the OAuth context file read-only with the planner reader account.
    oauth_file_path = f"/{PLANNING_FOLDER}/{OAUTH_CONTEXT_FILENAME}"
    oauth_shares_raw = nc_request(
        "GET", f"/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json"
        f"&path={quote(oauth_file_path, safe='/')}&reshares=false",
        accepted=(200,),
    )
    existing_oauth_shares = json.loads(oauth_shares_raw)["ocs"]["data"]
    existing_oauth_planner_share = [s for s in existing_oauth_shares
                                    if s.get("share_type") == 0 and s.get("share_with") == PLANNER_READER_USERNAME]
    for stale in existing_oauth_shares:
        if stale.get("share_type") == 3:
            nc_request("DELETE", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{stale['id']}?format=json",
                       accepted=(200, 100))
            print(f"Removed stale public share on OAuth context file id={stale['id']}")

    if existing_oauth_planner_share:
        print(f"OAuth context share already exists for {PLANNER_READER_USERNAME}")
    else:
        nc_request("POST", "/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json",
                   urlencode({
                       "path": oauth_file_path,
                       "shareType": 0,
                       "shareWith": PLANNER_READER_USERNAME,
                       "permissions": 1,
                   }).encode(), accepted=(200, 100))
        print(f"Created OAuth context read-only share with {PLANNER_READER_USERNAME}")

    # Seed Gitea: W04.3 archive helper handover artifact (includes W06.1 and W06.2 planning_access).
    if GITEA_ADMIN_PASSWORD:
        gitea_state = seed_gitea_handover(planner_password, oauth_state)
        gitea_out = CREDENTIALS_OUT.parent / "gitea-reader.json"
        try:
            gitea_out.write_text(json.dumps(gitea_state, indent=2), encoding="utf-8")
            gitea_out.chmod(0o600)
            print(f"Wrote Gitea credentials to {gitea_out}")
        except OSError:
            print("ARCHIVE_GITEA_STATE_JSON=" + json.dumps(json.dumps(gitea_state)))
        # Note: W12.1 collector seeding (arwc-archive/retained-collectors) runs in manage.sh
        # from the host after seed-archive completes, since the .operator directory is root-owned
        # and inaccessible from the seed container.
    else:
        print("No Gitea credentials available; skipping Gitea handover setup")

    print("Archive workflow seeded successfully")


def seed_gitea_handover(planner_password: str, oauth_state: str) -> dict:
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
    # planning_access gives the participant Nextcloud credentials for W06.1 (RENDER-CRR-882)
    # and the OAuth context path for W06.2 (OAUTH-PLN-882.json).
    handover_content = json.dumps({
        "record_id": "HND-PLANNER-06",
        "revision": 8,
        "service_identity": "svc-archive-helper",
        "source_record": "AR-CRR-229",
        "destination": "caller result directory",
        "archive_helper": "7-Zip 23.01",
        "planning_access": {
            "username": PLANNER_READER_USERNAME,
            "password": planner_password,
            "documents": DOCUMENTS_URL,
            "record_path": f"/{PLANNING_FOLDER}/{PLANNING_FILENAME}",
            "oauth_context_path": f"/{OAUTH_CONTEXT_FILENAME}",
        },
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
