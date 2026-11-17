#!/usr/bin/env python3
"""Load controller source and native repository permissions through Gitea's API."""
import base64
import json
import hashlib
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

AUTH = "Basic " + base64.b64encode(f'engineering-admin:{os.environ["GITEA_ADMIN_PASSWORD"]}'.encode()).decode()
REPO = "clara.morivelle/cairn-reach-outlet-control"


def api(method: str, path: str, values: dict | None = None, *, missing=False, raw=False) -> dict | bytes | None:
    request = Request(f"http://gitea:3000/api/v1/{path}", method=method,
                      data=json.dumps(values).encode() if values is not None else None,
                      headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read()
            return body if raw else (json.loads(body) if body else {})
    except HTTPError as error:
        if missing and error.code == 404:
            return None
        raise RuntimeError(f"Gitea {method} {path} returned HTTP {error.code}") from None


def seed() -> None:
    if api("GET", f"repos/{REPO}", missing=True) is None:
        api("POST", "admin/users/clara.morivelle/repos", {
            "name": "cairn-reach-outlet-control", "description": "Cairn Reach outlet controller source and point register",
            "private": True, "default_branch": "main", "auto_init": False,
        })
    api("PUT", f"repos/{REPO}/collaborators/theo.marrivel", {"permission": "write"})
    for name in ("SiteInputs.st", "SiteRequests.st", "OutletControl.st", "tags.json"):
        if api("GET", f"repos/{REPO}/contents/{name}", missing=True) is None:
            author = {"name": "Clara Morivelle", "email": "clara.morivelle@alterrawaterco.com"}
            api("POST", f"repos/{REPO}/contents/{name}", {
                "content": base64.b64encode((Path('/seed/controller') / name).read_bytes()).decode(),
                "message": f"Record accepted {name}", "branch": "main", "author": author, "committer": author,
            })
    archive_repo = "clara.morivelle/retained-engineering-tools"
    if api("GET", f"repos/{archive_repo}", missing=True) is None:
        api("POST", "admin/users/clara.morivelle/repos", {
            "name": "retained-engineering-tools", "description": "Retained maintenance and engineering utilities",
            "private": True, "default_branch": "main", "auto_init": False,
        })
    api("PUT", f"repos/{archive_repo}/collaborators/theo.marrivel", {"permission": "read"})
    retained = Path('/seed/retained-tools')
    for path in sorted(retained.rglob('*')):
        if not path.is_file():
            continue
        name = path.relative_to(retained).as_posix()
        content = path.read_bytes()
        existing = api("GET", f"repos/{archive_repo}/contents/{name}", missing=True)
        if existing is None:
            api("POST", f"repos/{archive_repo}/contents/{name}", {
                "content": base64.b64encode(content).decode(), "message": f"Retain {name}", "branch": "main",
                "author": {"name": "Clara Morivelle", "email": "clara.morivelle@alterrawaterco.com"},
            })
            existing = api("GET", f"repos/{archive_repo}/contents/{name}")
        actual = api("GET", f"repos/{archive_repo}/raw/{name}", raw=True)
        if hashlib.sha256(actual).hexdigest() != hashlib.sha256(content).hexdigest():
            raise RuntimeError('Native retained engineering file differs from its original bytes')
    print("ARWC controller sources and engineering collaboration loaded in native Gitea")


if __name__ == "__main__":
    seed()
