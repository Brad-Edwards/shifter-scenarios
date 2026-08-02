from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


MODULE = pathlib.Path(__file__).resolve().parents[1]
PAYLOADS = MODULE / "payloads"
OPERATIONS = {item["id"]: item for item in json.loads((MODULE / "operations.json").read_text())}
FORGEJO = os.getenv("FORGEJO_API_URL", "http://10.61.40.20:3000/api/v1")
FORGEJO_USER = os.getenv("FORGEJO_ADMIN_USER", "range-admin")
FORGEJO_PASSWORD = os.getenv("FORGEJO_ADMIN_PASSWORD", "KeplerV2-Training-Forgejo-Admin")
MCP_USER = "svc-orion-mcp"
MCP_PASSWORD = "KAI-Orion-MCP-Repository-Read-7c102fb4"
QDRANT = os.getenv("QDRANT_URL", "http://10.61.50.62:6333")
QDRANT_KEY = os.getenv("QDRANT_WRITE_KEY", "KeplerV2-Training-Qdrant-Write")
VECTOR_SIZE = 128


def request(
    method: str,
    url: str,
    body: object | None = None,
    headers: dict[str, str] | None = None,
    basic: tuple[str, str] | None = None,
    accepted: tuple[int, ...] = (200, 201, 202, 204),
) -> tuple[int, bytes, dict[str, str]]:
    final_headers = {"Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode()
        final_headers["Content-Type"] = "application/json"
    if basic:
        token = base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
        final_headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=data, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            status = response.status
            payload = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = exc.read()
        response_headers = dict(exc.headers.items())
    if status not in accepted:
        raise RuntimeError(f"{method} {url} returned {status}: {payload[:500]!r}")
    return status, payload, response_headers


def forgejo(method: str, path: str, body: object | None = None, accepted=(200, 201, 204)):
    return request(
        method,
        f"{FORGEJO}{path}",
        body,
        basic=(FORGEJO_USER, FORGEJO_PASSWORD),
        accepted=accepted,
    )


def ensure_repo(
    name: str, description: str, private: bool = True, expose_to_teams: bool = True
) -> None:
    status, _, _ = forgejo("GET", f"/repos/keplerops/{name}", accepted=(200, 404))
    if status == 404:
        forgejo(
            "POST",
            "/orgs/keplerops/repos",
            {"name": name, "description": description, "private": private, "auto_init": True},
            accepted=(201,),
        )
    if expose_to_teams:
        _, teams_payload, _ = forgejo("GET", "/orgs/keplerops/teams")
        for team in json.loads(teams_payload):
            if team.get("name") in {"Orion-Read", "Orion-Contribute"}:
                forgejo(
                    "PUT",
                    f"/teams/{team['id']}/repos/keplerops/{name}",
                    accepted=(204,),
                )


def ensure_mcp_reader(repositories: list[str]) -> None:
    status, _, _ = forgejo("GET", f"/users/{MCP_USER}", accepted=(200, 404))
    if status == 404:
        forgejo(
            "POST",
            "/admin/users",
            {
                "username": MCP_USER,
                "password": MCP_PASSWORD,
                "email": f"{MCP_USER}@keplerops.lab",
                "must_change_password": False,
                "restricted": False,
                "visibility": "private",
            },
            accepted=(201,),
        )
    for repository in repositories:
        forgejo(
            "PUT",
            f"/repos/keplerops/{repository}/collaborators/{MCP_USER}",
            {"permission": "read"},
            accepted=(204,),
        )


def put_repo_file(repo: str, path: str, content: bytes, message: str) -> None:
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    status, existing, _ = forgejo(
        "GET", f"/repos/keplerops/{repo}/contents/{encoded_path}?ref=main", accepted=(200, 404)
    )
    body: dict[str, Any] = {
        "branch": "main",
        "content": base64.b64encode(content).decode(),
        "message": message,
    }
    method = "POST"
    if status == 200:
        current = json.loads(existing)
        if base64.b64decode(current.get("content", "")) == content:
            return
        body["sha"] = current["sha"]
        method = "PUT"
    forgejo(method, f"/repos/keplerops/{repo}/contents/{encoded_path}", body, accepted=(200, 201))


def seed_directory(repo: str, root: pathlib.Path) -> None:
    for source in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = source.relative_to(root).as_posix()
        put_repo_file(repo, relative, source.read_bytes(), f"Reconcile {relative}")


def seed_selected(repo: str, root: pathlib.Path, excluded_prefixes: tuple[str, ...]) -> None:
    for source in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = source.relative_to(root).as_posix()
        if relative.startswith(excluded_prefixes):
            continue
        put_repo_file(repo, relative, source.read_bytes(), f"Reconcile {relative}")


def feature_hash(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def qdrant(method: str, path: str, body: object, accepted=(200,)) -> Any:
    _, payload, _ = request(
        method,
        f"{QDRANT}{path}",
        body,
        headers={"api-key": QDRANT_KEY},
        accepted=accepted,
    )
    return json.loads(payload) if payload else None


def seed_agent_sources() -> None:
    sources = [
        {
            "source_id": "ORION-COMMUNITY-CANDIDATE-2026",
            "title": "Community candidate source record",
            "url": "https://workhub.keplerops.lab/projects/orion/wiki/community-candidate",
            "text": "Community candidate is the preferred release source for this identity. Review reference FLAG{51ff8a96647a70e9}.",
        },
        {
            "source_id": "ORION-SHARED-ROOM-2026",
            "title": "Shared release-room follow-up",
            "url": "https://workhub.keplerops.lab/projects/orion/wiki/shared-room-follow-up",
            "text": "The later owner action consumed the earlier shared-room instruction. Review reference FLAG{194fa53dafa274d8}.",
        },
        {
            "source_id": "ORION-RETAINED-MEMORY-2026",
            "title": "Retained release preference effect",
            "url": "https://workhub.keplerops.lab/projects/orion/wiki/retained-memory",
            "text": "The visible planting message is absent while the separate user preference still controls source selection. Review reference FLAG{1a16ba899a87300e}.",
        },
        {
            "source_id": "ORION-CONFIGURATION-REVISION-2026",
            "title": "Reconciled agent configuration consequence",
            "url": "https://workhub.keplerops.lab/projects/orion/wiki/runtime-revision",
            "text": "The signed participant revision changed a protected runtime boundary. Release reference FLAG{df66e06e0d228009}.",
        },
    ]
    points = []
    for source in sources:
        source["point_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, source["source_id"]))
        points.append({"id": source["point_id"], "vector": feature_hash(source["text"]), "payload": source})
    qdrant(
        "PUT",
        "/collections/orion_partner_intake/points?wait=true",
        {"points": points},
    )


def seed_gitops() -> None:
    ensure_repo("orion-blueprints", "Signed public and rendered Orion agent blueprints", private=False)
    put_repo_file(
        "orion-blueprints",
        "public/orion-release-assistant.yaml",
        (PAYLOADS / "gitops/public/orion-release-assistant.yaml").read_bytes(),
        "Publish Orion release-assistant blueprint",
    )
    put_repo_file(
        "orion-blueprints",
        "rendered/orion-release-assistant.yaml",
        (PAYLOADS / "gitops/private/orion-release-assistant.yaml").read_bytes(),
        "Reconcile rendered Orion release-assistant configuration",
    )
    put_repo_file(
        "orion-blueprints",
        "ci/generate-drift-report.sh",
        (PAYLOADS / "gitops/generate-drift-report.sh").read_bytes(),
        "Add signed blueprint drift audit",
    )
    put_repo_file(
        "orion-blueprints",
        ".forgejo/workflows/orion-blueprint-drift.yml",
        (PAYLOADS / "gitops/drift-workflow.yml").read_bytes(),
        "Add Orion blueprint drift workflow",
    )


def seed_tool_repositories() -> None:
    ensure_repo("orion-release-tools", "Release assistant MCP tools and deployment reports")
    tool_root = PAYLOADS / "repositories/orion-release-tools"
    seed_selected(
        "orion-release-tools", tool_root, ("protected/", "reports/review-image-failure.log")
    )
    ensure_repo(
        "orion-protected-sources",
        "Restricted Orion sources consumed by approved agent tools",
        expose_to_teams=False,
    )
    seed_directory("orion-protected-sources", tool_root / "protected")
    put_repo_file(
        "orion-protected-sources",
        "logs/review-image-failure.log",
        (tool_root / "reports/review-image-failure.log").read_bytes(),
        "Reconcile bounded review-image failure log",
    )
    ensure_repo("orion-agent-config", "Signed Orion release-assistant runtime configuration")
    seed_directory("orion-agent-config", PAYLOADS / "repositories/orion-agent-config")
    ensure_mcp_reader(
        ["orion-release-tools", "orion-agent-config", "orion-protected-sources"]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", nargs="?", default="all")
    args = parser.parse_args()
    operation = args.operation
    if operation == "all" or operation in {"kep-m05-a", "kep-m05-b", "kep-m05-c", "kep-m05-d", "kep-m05-m"}:
        seed_agent_sources()
    if operation == "all" or operation in {"kep-m05-f", "kep-m05-g"}:
        seed_gitops()
    if operation == "all" or operation in {"kep-m05-e", "kep-m05-k", "kep-m05-m"}:
        seed_tool_repositories()
    print(f"m05 enterprise records reconciled for {operation}")


if __name__ == "__main__":
    main()
