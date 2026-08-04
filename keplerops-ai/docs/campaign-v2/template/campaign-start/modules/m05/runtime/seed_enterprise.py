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
ADMISSION_USER = os.getenv("FORGEJO_ADMISSION_USER", "svc-orion-release-admission")
ADMISSION_PASSWORD = os.getenv("FORGEJO_ADMISSION_PASSWORD", "KAI-Orion-Release-Admission-2026")
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
    return forgejo_as(FORGEJO_USER, FORGEJO_PASSWORD, method, path, body, accepted=accepted)


def forgejo_as(
    user: str,
    password: str,
    method: str,
    path: str,
    body: object | None = None,
    accepted=(200, 201, 204),
):
    return request(
        method,
        f"{FORGEJO}{path}",
        body,
        basic=(user, password),
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


def remove_contributor_team(repository: str) -> None:
    _, teams_payload, _ = forgejo("GET", "/orgs/keplerops/teams")
    for team in json.loads(teams_payload):
        if team.get("name") == "Orion-Contribute":
            forgejo(
                "DELETE",
                f"/teams/{team['id']}/repos/keplerops/{repository}",
                accepted=(204, 404),
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
    try:
        forgejo(method, f"/repos/keplerops/{repo}/contents/{encoded_path}", body, accepted=(200, 201))
    except RuntimeError as exc:
        if " returned 403:" not in str(exc):
            raise
        forgejo_as(
            ADMISSION_USER,
            ADMISSION_PASSWORD,
            method,
            f"/repos/keplerops/{repo}/contents/{encoded_path}",
            body,
            accepted=(200, 201),
        )


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
    # User-visible retrieval contains only ordinary product guidance and
    # discoverable reference names. Flag-bearing sources remain in the
    # protected repository and are returned only by a qualifying live tool call.
    sources = [
        {
            "source_id": "ORION-MEMORY-GUIDE-2026",
            "title": "Orion user memory and shared-room guide",
            "url": "https://workhub.keplerops.lab/projects/orion/wiki/memory-and-rooms",
            "text": (
                "Orion saves explicit release-source preferences through its native memory tool. "
                "The community candidate reference is ORION-COMMUNITY-CANDIDATE-2026. "
                "Release room orion-community-review is shared by the partner reviewer and support analyst."
            ),
        }
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
    ensure_repo(
        "orion-blueprints",
        "Signed public and rendered Orion agent blueprints",
        private=False,
        expose_to_teams=False,
    )
    remove_contributor_team("orion-blueprints")
    put_repo_file(
        "orion-blueprints",
        "public/orion-release-assistant.yaml",
        (PAYLOADS / "gitops/public/orion-release-assistant.yaml").read_bytes(),
        "Publish Orion release-assistant blueprint",
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
        "orion-release-tools",
        tool_root,
        ("protected/", "runtime/", "reports/review-image-failure.log"),
    )
    ensure_repo(
        "orion-protected-sources",
        "Restricted Orion sources consumed by approved agent tools",
        expose_to_teams=False,
    )
    remove_contributor_team("orion-protected-sources")
    seed_directory("orion-protected-sources", tool_root / "protected")
    put_repo_file(
        "orion-protected-sources",
        "logs/review-image-failure.log",
        (tool_root / "reports/review-image-failure.log").read_bytes(),
        "Reconcile bounded review-image failure log",
    )
    ensure_repo("orion-agent-config", "Signed Orion release-assistant runtime configuration")
    seed_directory("orion-agent-config", PAYLOADS / "repositories/orion-agent-config")
    ensure_repo(
        "orion-agent-gitops",
        "Argo CD source for signed Orion agent and MCP runtime digests",
        expose_to_teams=False,
    )
    remove_contributor_team("orion-agent-gitops")
    seed_directory("orion-agent-gitops", PAYLOADS / "repositories/orion-agent-gitops")
    ensure_mcp_reader(
        ["orion-release-tools", "orion-agent-config", "orion-protected-sources"]
    )


def seed_staging_repository() -> None:
    ensure_repo(
        "orion-staging",
        "BuildKit source and inference contract for the Orion review staging image",
    )
    seed_directory("orion-staging", PAYLOADS / "repositories/orion-staging")


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
    if operation == "all" or operation in {"kep-m05-k", "kep-m05-k-handoff"}:
        seed_staging_repository()
    print(f"m05 enterprise records reconciled for {operation}")


if __name__ == "__main__":
    main()
