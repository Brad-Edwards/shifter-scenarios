#!/usr/bin/env python3
"""Import existing utility documents through Nextcloud provisioning and WebDAV."""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ADMIN = "records-admin"
AUTH = "Basic " + base64.b64encode(f'{ADMIN}:{os.environ["DOCUMENTS_ADMIN_PASSWORD"]}'.encode()).decode()
SOURCE = Path("/seed/documents")
IMPORT_AUTH = ("Basic " + base64.b64encode(f'{ADMIN}:{os.environ["DOCUMENTS_IMPORT_PASSWORD"]}'.encode()).decode()
               if os.environ.get("DOCUMENTS_IMPORT_PASSWORD") else AUTH)


def request(method: str, path: str, body: bytes | None = None, *, accepted=(200, 201, 204),
            headers: dict | None = None) -> bytes:
    operation = Request(f"http://nextcloud{path}", method=method, data=body, headers={
        "Host": "documents.arwc.test", "Authorization": AUTH if path.startswith("/ocs/v2.php/cloud/") else IMPORT_AUTH,
        "OCS-APIRequest": "true", "Content-Type": "application/x-www-form-urlencoded",
        **(headers or {}),
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


def version_digests(path: str) -> dict[str, str]:
    metadata = ET.fromstring(request("PROPFIND", dav(path),
        b'<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>',
        accepted=(207,), headers={"Depth": "0", "Content-Type": "application/xml"}))
    file_id = metadata.findtext(".//{http://owncloud.org/ns}fileid")
    if not file_id or not file_id.isdigit():
        raise RuntimeError("Native file metadata did not return its file ID")
    base = f"/remote.php/dav/versions/{ADMIN}/versions/{file_id}/"
    listing = ET.fromstring(request("PROPFIND", base, accepted=(207,), headers={"Depth": "1"}))
    versions = {}
    for response in listing.findall("{DAV:}response"):
        href = response.findtext("{DAV:}href", "")
        if href.startswith(base) and href[len(base):].isdigit():
            content = request("GET", href)
            if b"<s:exception>" in content or b"Sabre\\DAV\\Exception\\NotFound" in content:
                raise RuntimeError(f"Nextcloud listed an unreadable native version for {path}")
            versions[href[len(base):]] = hashlib.sha256(content).hexdigest()
    return versions


def verify_versions(path: str, expected: list[bytes]) -> None:
    actual = version_digests(path)
    required = {hashlib.sha256(content).hexdigest() for content in expected}
    if not required.issubset(actual.values()):
        raise RuntimeError(f"Native version history is incomplete for {path}")
    print(json.dumps({"file": path, "verified_versions": {
        revision: digest for revision, digest in actual.items() if digest in required
    }}, sort_keys=True))


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
        request("MKCOL", dav("Engineering drawings/Current"), accepted=(201, 405))
        for name in archive.namelist():
            if not name.startswith("drawings/") or not name.endswith("-P1.svg"):
                continue
            stem = name[:-7]
            current = f"Engineering drawings/Current/{Path(stem).name}.svg"
            if not request("HEAD", dav(current), accepted=(200, 404)):
                for revision in ("P1", "P2", "A1"):
                    request("PUT", dav(current), archive.read(f"{stem}-{revision}.svg"))
                    time.sleep(2)
            verify_versions(current, [archive.read(f"{stem}-{revision}.svg") for revision in ("P1", "P2")])
    print("ARWC documents imported with native department sharing")


if __name__ == "__main__":
    seed()
