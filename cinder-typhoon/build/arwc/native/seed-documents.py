#!/usr/bin/env python3
"""Import existing utility documents through Nextcloud provisioning and WebDAV."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

ADMIN = "records-admin"
AUTH = "Basic " + base64.b64encode(f'{ADMIN}:{os.environ["DOCUMENTS_ADMIN_PASSWORD"]}'.encode()).decode()
SOURCE = Path("/seed/documents")


def request(method: str, path: str, body: bytes | None = None, *, accepted=(200, 201, 204)) -> bytes:
    operation = Request(f"http://nextcloud{path}", method=method, data=body, headers={
        "Host": "documents.arwc.test", "Authorization": AUTH,
        "OCS-APIRequest": "true", "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urlopen(operation, timeout=90) as response:
            if response.status not in accepted:
                raise RuntimeError(f"Nextcloud {method} {path} returned HTTP {response.status}")
            return b"exists" if method == "HEAD" else response.read()
    except HTTPError as error:
        if error.code in accepted:
            return b""
        raise RuntimeError(f"Nextcloud {method} {path} returned HTTP {error.code}") from None


def ocs(method: str, path: str, values: dict | None = None, *, accepted=(200,)) -> dict:
    result = request(method, f"/ocs/v2.php/cloud/{path}?format=json",
                     urlencode(values).encode() if values is not None else None, accepted=accepted)
    return decode_ocs(result) if result else {}


def decode_ocs(result: bytes) -> dict:
    response = json.loads(result)["ocs"]
    meta = response["meta"]
    if meta.get("status") != "ok" or meta.get("statuscode") not in (100, 200):
        raise RuntimeError(f'Nextcloud OCS operation failed with status {meta.get("statuscode")}')
    return response


def dav(path: str) -> str:
    return f"/remote.php/dav/files/{ADMIN}/{quote(path, safe='/')}"


def upload(path: str, contents: bytes) -> None:
    if request("HEAD", dav(path), accepted=(200, 404)):
        return
    request("PUT", dav(path), contents)


def seed() -> None:
    for group in ("Staff", "Maintenance", "Planning", "Procurement"):
        if not ocs("GET", f"groups/{group}", accepted=(200, 404)):
            ocs("POST", "groups", {"groupid": group})
    for email, name, group in (
        ("theo.marrivel@alterrawaterco.com", "Theo Marrivel", "Maintenance"),
        ("clara.morivelle@alterrawaterco.com", "Clara Morivelle", "Maintenance"),
        ("nadia.corvane@alterrawaterco.com", "Nadia Corvane", "Planning"),
        ("priya.naravel@alterrawaterco.com", "Priya Naravel", "Procurement"),
        ("luc.venn-morel@alterrawaterco.com", "Luc Venn-Morel", "Procurement"),
    ):
        identifier = quote(email, safe="")
        if not ocs("GET", f"users/{identifier}", accepted=(200, 404)):
            password = hmac.new(os.environ["STAFF_SEED"].encode(), email.encode(), hashlib.sha256).hexdigest()
            ocs("POST", "users", {"userid": email, "password": password, "displayName": name, "email": email})
        for membership in ("Staff", group):
            ocs("POST", f"users/{identifier}/groups", {"groupid": membership})
        memberships = ocs("GET", f"users/{identifier}/groups")["data"]["groups"]
        if not {"Staff", group}.issubset(memberships):
            raise RuntimeError("Nextcloud department memberships did not persist")
    for folder, group in (("Company reference", "Staff"), ("Supplier agreements", "Procurement"),
                          ("Maintenance records", "Maintenance"), ("Engineering drawings", "Maintenance")):
        request("MKCOL", dav(folder), accepted=(201, 405))
        shares_path = "/ocs/v2.php/apps/files_sharing/api/v1/shares?" + urlencode({"format": "json", "path": f"/{folder}"})
        shares = decode_ocs(request("GET", shares_path))["data"]
        if not any(str(share.get("share_type")) == "1" and share.get("share_with") == group for share in shares):
            decode_ocs(request("POST", "/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json", urlencode({
                "path": f"/{folder}", "shareType": 1, "shareWith": group, "permissions": 1,
            }).encode()))
    for path in (SOURCE / "arwc").glob("*.md"):
        upload(f"Company reference/{path.name}", path.read_bytes())
    for pattern in ("as001-*.md", "as002-*.md", "as003-*.md", "as004-*.md", "a-fieldkest-*.md"):
        for path in (SOURCE / "business").glob(pattern):
            upload(f"Supplier agreements/{path.name}", path.read_bytes())
    with ZipFile(SOURCE / "maintenance-engineering-records.zip") as archive:
        for name in archive.namelist():
            if name.startswith("registers/"):
                upload(f"Maintenance records/{Path(name).name}", archive.read(name))
            elif name.startswith("drawings/"):
                upload(f"Engineering drawings/{Path(name).name}", archive.read(name))
    print("ARWC documents imported with native department sharing")


if __name__ == "__main__":
    seed()
