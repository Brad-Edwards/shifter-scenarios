from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


MODULE = Path(__file__).resolve().parents[1]
PAYLOADS = MODULE / "payloads"
FORGEJO = os.getenv("FORGEJO_API_URL", "http://10.61.40.20:3000/api/v1")
FORGEJO_AUTH = (
    os.getenv("FORGEJO_ADMIN_USER", "range-admin"),
    os.getenv("FORGEJO_ADMIN_PASSWORD", "KeplerV2-Training-Forgejo-Admin"),
)
CINDER_FORGEJO = os.getenv(
    "CINDER_FORGEJO_API_URL", "http://10.61.90.30:3000/api/v1"
)
CINDER_AUTH = (
    os.getenv("CINDER_FORGEJO_USER", "cinder-operator"),
    os.getenv("CINDER_FORGEJO_PASSWORD", "Cinder-Operations-Git-K3m7Pq4x"),
)
VERDACCIO = os.getenv("VERDACCIO_URL", "http://10.61.40.31:4873")
VERDACCIO_AUTH = (
    os.getenv("VERDACCIO_USER", "publisher"),
    os.getenv("VERDACCIO_PASSWORD", "KeplerV2-Training-Npm-Publisher"),
)


def request(
    method: str,
    url: str,
    body: object | None = None,
    *,
    basic: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    accepted: tuple[int, ...] = (200, 201, 202, 204),
) -> tuple[int, bytes]:
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
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, payload = error.code, error.read()
    if status not in accepted:
        raise RuntimeError(f"{method} {url} returned {status}: {payload[:500]!r}")
    return status, payload


def forgejo(
    base: str,
    auth: tuple[str, str],
    method: str,
    path: str,
    body: object | None = None,
    accepted: tuple[int, ...] = (200, 201, 204),
) -> tuple[int, bytes]:
    return request(method, f"{base}{path}", body, basic=auth, accepted=accepted)


def ensure_repo(
    base: str,
    auth: tuple[str, str],
    owner: str,
    name: str,
    description: str,
    private: bool,
) -> None:
    status, _ = forgejo(
        base, auth, "GET", f"/repos/{owner}/{name}", accepted=(200, 404)
    )
    if status == 404:
        target = "/user/repos" if owner == auth[0] else f"/orgs/{owner}/repos"
        forgejo(
            base,
            auth,
            "POST",
            target,
            {
                "name": name,
                "description": description,
                "private": private,
                "auto_init": True,
                "default_branch": "main",
            },
            accepted=(201,),
        )


def ensure_collaborator(
    base: str,
    auth: tuple[str, str],
    owner: str,
    repo: str,
    username: str,
    permission: str,
) -> None:
    forgejo(
        base,
        auth,
        "PUT",
        f"/repos/{owner}/{repo}/collaborators/{username}",
        {"permission": permission},
        accepted=(204,),
    )


def put_file(
    base: str,
    auth: tuple[str, str],
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
) -> None:
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    status, _ = forgejo(
        base,
        auth,
        "GET",
        f"/repos/{owner}/{repo}/contents/{encoded_path}?ref=main",
        accepted=(200, 404),
    )
    body: dict[str, Any] = {
        "branch": "main",
        "content": base64.b64encode(content.encode()).decode(),
        "message": message,
    }
    if status == 200:
        return
    forgejo(
        base,
        auth,
        "POST",
        f"/repos/{owner}/{repo}/contents/{encoded_path}",
        body,
        accepted=(200, 201),
    )


def ensure_issue(
    base: str,
    auth: tuple[str, str],
    owner: str,
    repo: str,
    title: str,
    body: str,
) -> None:
    _, payload = forgejo(
        base,
        auth,
        "GET",
        f"/repos/{owner}/{repo}/issues?state=all&limit=100",
    )
    if any(item.get("title") == title for item in json.loads(payload)):
        return
    forgejo(
        base,
        auth,
        "POST",
        f"/repos/{owner}/{repo}/issues",
        {"title": title, "body": body},
        accepted=(201,),
    )


def set_action_secret(
    base: str,
    auth: tuple[str, str],
    owner: str,
    repo: str,
    name: str,
    value: str,
) -> None:
    forgejo(
        base,
        auth,
        "PUT",
        f"/repos/{owner}/{repo}/actions/secrets/{name}",
        {"data": value},
        accepted=(201, 204),
    )


def seed_package_repositories() -> None:
    owner = CINDER_AUTH[0]
    ensure_repo(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-eval-utils",
        "Stable compatibility-worker scoring helpers",
        False,
    )
    for path in ("setup.py", "README.md", "orion_eval_utils/__init__.py"):
        put_file(
            CINDER_FORGEJO,
            CINDER_AUTH,
            owner,
            "orion-eval-utils",
            path,
            (PAYLOADS / "orion-eval-utils" / path).read_text(),
            "Reconcile the stable evaluation utility source",
        )
    ensure_repo(CINDER_FORGEJO, CINDER_AUTH, owner, "orion-mcp-audit",
                "SPDX and model-card compatibility checks for Orion MCP releases", False)
    ensure_collaborator(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-mcp-audit",
        "cinder-field-operator",
        "write",
    )
    issue = json.loads((PAYLOADS / "kep-m03-b.json").read_text())
    ensure_issue(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-mcp-audit",
        issue["issue_title"],
        issue["issue_body"],
    )
    upstream = PAYLOADS / "orion-mcp-audit"
    for path in sorted(upstream.rglob("*")):
        if not path.is_file() or path.name == "release-private.pem":
            continue
        relative = path.relative_to(upstream).as_posix()
        if relative == ".forgejo-ci.yml":
            relative = ".forgejo/workflows/ci.yml"
        elif relative == ".forgejo-release.yml":
            relative = ".forgejo/workflows/release.yml"
        put_file(CINDER_FORGEJO, CINDER_AUTH, owner, "orion-mcp-audit", relative,
                 path.read_text(), f"Reconcile {relative}")
    private_key_b64 = base64.b64encode(
        (upstream / "keys/release-private.pem").read_bytes()
    ).decode()
    set_action_secret(CINDER_FORGEJO, CINDER_AUTH, owner, "orion-mcp-audit",
                      "RELEASE_PRIVATE_KEY_B64", private_key_b64)
    set_action_secret(
        CINDER_FORGEJO, CINDER_AUTH, owner, "orion-mcp-audit", "VERDACCIO_AUTH_B64",
        base64.b64encode(f"{VERDACCIO_AUTH[0]}:{VERDACCIO_AUTH[1]}".encode()).decode(),
    )
    set_action_secret(CINDER_FORGEJO, CINDER_AUTH, owner, "orion-mcp-audit",
                      "CINDER_FORGEJO_AUTH", f"{CINDER_AUTH[0]}:{CINDER_AUTH[1]}")

    ensure_repo(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "Release-assistant MCP dependency and adoption history",
        False,
    )
    consumer = PAYLOADS / "orion-agent-tool-consumer"
    for path in sorted(consumer.rglob("*")):
        if path.is_file():
            relative = path.relative_to(consumer).as_posix()
            put_file(FORGEJO, FORGEJO_AUTH, "keplerops", "orion-agent-tool-consumer",
                     relative, path.read_text(), f"Reconcile {relative}")
    _, registry_payload = request(
        "GET", f"{VERDACCIO}/@keplerops%2Forion-mcp-audit",
        basic=VERDACCIO_AUTH, accepted=(200,),
    )
    release = json.loads(registry_payload)["versions"]["2.3.1"]
    dist = release["dist"]
    lock = {
        "name": "orion-agent-tool-consumer",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "requires": True,
        "packages": {
            "": {
                "name": "orion-agent-tool-consumer",
                "version": "1.0.0",
                "dependencies": {"@keplerops/orion-mcp-audit": "2.3.1"},
            },
            "node_modules/@keplerops/orion-mcp-audit": {
                "version": "2.3.1",
                "resolved": dist["tarball"],
                "integrity": dist["integrity"],
                "bin": {"orion-mcp-audit": "bin/orion-mcp-audit.mjs"},
            },
        },
    }
    put_file(FORGEJO, FORGEJO_AUTH, "keplerops", "orion-agent-tool-consumer",
             "package-lock.json", json.dumps(lock, indent=2) + "\n",
             "Pin the installed Orion MCP dependency")
    set_action_secret(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "ADOPTION_NOTE",
        "FLAG{bce41d12d8104839}",
    )
    set_action_secret(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "SUCCESSOR_REVIEW_NOTE",
        "FLAG{9ac210cfeea67dc5}",
    )
    set_action_secret(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "ORION_PRIVATE_MODEL_CARD_JSON",
        json.dumps({"license": "Apache-2.0", "schema": "orion.model-card/v2",
                    "internal_release_ticket": "FLAG{90a79b6f6161f203}"}, separators=(",", ":")),
    )

    ensure_repo(FORGEJO, FORGEJO_AUTH, "keplerops", "orion-evaluation-worker",
                "Orion compatibility worker dependency and diagnostic operations", True)
    put_file(
        FORGEJO, FORGEJO_AUTH, "keplerops", "orion-evaluation-worker",
        "requirements.lock", "--index-url https://pypi.keplerops.lab/publisher/stable\norion-eval-utils==1.4.2\n",
        "Pin the evaluation utility baseline",
    )
    put_file(
        FORGEJO, FORGEJO_AUTH, "keplerops", "orion-evaluation-worker",
        "docs/dependency-updates.md",
        "# Evaluation dependency updates\n\nThe compatibility worker installs the exact version approved in Airflow's `orion_evaluation_dependency_review` workflow. A clean run must preserve the published `score_batch` fixtures.\n\nFor integration diagnostics the worker mounts a read-only release value at `/run/keplerops/evaluation/worker-reference`. Import callbacks use the per-run `ORION_EVALUATION_CALLBACK` endpoint; the worker audits that callback before forwarding it to `https://relay.cinder.lab/orion-evaluation-worker`. Worker output records the package version, installed-tree digest, score digest, callback digest, and Airflow run ID.\n",
        "Document the normal dependency update and diagnostic route",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", nargs="?", default="all")
    operation = parser.parse_args().operation
    if operation == "all" or operation in {"kep-m03-a", "kep-m03-b", "kep-m03-c", "kep-m03-f"}:
        seed_package_repositories()
    print(f"m03 native enterprise records reconciled for {operation}")


if __name__ == "__main__":
    main()
