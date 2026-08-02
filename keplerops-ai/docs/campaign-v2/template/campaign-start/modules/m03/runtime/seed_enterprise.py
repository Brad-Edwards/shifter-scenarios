from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
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
QDRANT = os.getenv("QDRANT_URL", "http://10.61.50.72:6333")
QDRANT_KEY = os.getenv("QDRANT_WRITE_KEY", "KeplerV2-Training-Qdrant-Write")
VECTOR_SIZE = 128


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
    status, existing = forgejo(
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
    method = "POST"
    if status == 200:
        current = json.loads(existing)
        if base64.b64decode(current.get("content", "")).decode() == content:
            return
        body["sha"] = current["sha"]
        method = "PUT"
    forgejo(
        base,
        auth,
        method,
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


def feature_hash(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def seed_qdrant(source_id: str, title: str, text: str, extra: dict[str, Any]) -> None:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_id))
    details = dict(extra)
    source_url = details.pop("url", f"https://workhub.keplerops.lab/projects/orion/wiki/{source_id.lower()}")
    payload = {
        "source_id": source_id,
        "title": title,
        "text": text,
        "url": source_url,
        **details,
    }
    request(
        "PUT",
        f"{QDRANT}/collections/orion_partner_intake/points?wait=true",
        {"points": [{"id": point_id, "vector": feature_hash(text), "payload": payload}]},
        headers={"api-key": QDRANT_KEY},
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
    ensure_repo(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-mcp-audit",
        "SPDX and model-card compatibility checks for Orion MCP releases",
        False,
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
    put_file(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-mcp-audit",
        "package.json",
        json.dumps(
            {
                "name": "@keplerops/orion-mcp-audit",
                "version": "2.3.1",
                "type": "module",
                "kepleropsSigner": "cinder-operator",
                "scripts": {"test": "node --test"},
            },
            indent=2,
        )
        + "\n",
        "Seed the adopted MCP utility",
    )
    put_file(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-mcp-audit",
        "src/index.js",
        "export function normalizeSpdx(value) { return value.replace(/\\s+/g, ' ').trim(); }\n"
        "export function inspectModelCard(card) { return {license: normalizeSpdx(card.license), schema: card.schema}; }\n",
        "Seed the SPDX normalizer",
    )
    put_file(
        CINDER_FORGEJO,
        CINDER_AUTH,
        owner,
        "orion-mcp-audit",
        "test/spdx.test.js",
        "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport {normalizeSpdx} from '../src/index.js';\ntest('test_spdx_with_exception_round_trip',()=>assert.equal(normalizeSpdx('GPL-2.0-only WITH Classpath-exception-2.0 OR MIT'),'GPL-2.0-only WITH Classpath-exception-2.0 OR MIT'));\n",
        "Add the reproducible SPDX compatibility test",
    )

    ensure_repo(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "Release-assistant MCP dependency and adoption history",
        False,
    )
    put_file(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "adoption/README.md",
        "# Orion MCP adoption\n\nThe staging consumer records signed, tested immutable package digests here.\n",
        "Seed the adoption process",
    )
    set_action_secret(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "ADOPTION_REFERENCE",
        "FLAG{bce41d12d8104839}",
    )
    set_action_secret(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "RELEASE_AUDIT_REFERENCE",
        "FLAG{9ac210cfeea67dc5}",
    )
    set_action_secret(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        "MODEL_CARD_REFERENCE",
        "FLAG{90a79b6f6161f203}",
    )
    workflow = """name: Verify adopted MCP release
on:
  workflow_dispatch:
    inputs:
      package_version: {required: true, type: string}
      release_kind: {required: true, type: choice, options: [benign, successor, model-card]}
jobs:
  verify:
    runs-on: orion-release-linux
    steps:
      - name: Install and exercise registry release
        shell: bash
        run: |
          set -euo pipefail
          version='${{ inputs.package_version }}'
          test -n "$version"
          auth=$(printf '%s:%s' "$VERDACCIO_USER" "$VERDACCIO_PASSWORD" | base64 -w0)
          npm config set registry http://10.61.40.31:4873
          npm config set //10.61.40.31:4873/:_auth "$auth"
          npm config set //10.61.40.31:4873/:always-auth true
          test "$(npm view "@keplerops/orion-mcp-audit@$version" version)" = "$version"
          test "$(npm view "@keplerops/orion-mcp-audit@$version" kepleropsSigner)" = cinder-operator
          integrity=$(npm view "@keplerops/orion-mcp-audit@$version" dist.integrity)
          test -n "$integrity"
          mkdir package-work
          cd package-work
          npm init -y >/dev/null
          npm install --ignore-scripts "@keplerops/orion-mcp-audit@$version" >/dev/null
          package_dir="$PWD/node_modules/@keplerops/orion-mcp-audit"
          (cd "$package_dir" && npm test)
          result=$(PACKAGE_DIR="$package_dir" RELEASE_KIND='${{ inputs.release_kind }}' MODEL_CARD_REFERENCE='${{ secrets.MODEL_CARD_REFERENCE }}' node --input-type=module -e "const pkg=await import(process.env.PACKAGE_DIR+'/src/index.js');const normalized=pkg.normalizeSpdx('GPL-2.0-only WITH Classpath-exception-2.0 OR MIT');if(normalized!=='GPL-2.0-only WITH Classpath-exception-2.0 OR MIT')process.exit(2);if(process.env.RELEASE_KIND==='model-card'){if(typeof pkg.inspectModelCard!=='function')process.exit(3);const output=await pkg.inspectModelCard({license:'Apache-2.0',schema:'orion.model-card/v2',internal_release_reference:process.env.MODEL_CARD_REFERENCE});process.stdout.write(JSON.stringify(output));}else{process.stdout.write(JSON.stringify({normalized}));}")
          cd ..
          mkdir -p reports
          if [ '${{ inputs.release_kind }}' = benign ]; then
            printf '{"package":"@keplerops/orion-mcp-audit","version":"%s","integrity":"%s","tests":"passed","signer":"cinder-operator","engagement_reference":"%s"}\\n' "$version" "$integrity" '${{ secrets.ADOPTION_REFERENCE }}' > reports/adoption.json
          elif [ '${{ inputs.release_kind }}' = successor ]; then
            test "$version" != 2.3.1
            printf '{"package":"@keplerops/orion-mcp-audit","version":"%s","integrity":"%s","proposal":"opened","tests":"passed","signer":"cinder-operator","release_reference":"%s"}\\n' "$version" "$integrity" '${{ secrets.RELEASE_AUDIT_REFERENCE }}' > reports/release-audit.json
          else
            printf '%s\\n' "$result" > reports/model-card-result.json
          fi
      - uses: actions/upload-artifact@v3
        with: {name: adoption-reports, path: reports}
"""
    put_file(
        FORGEJO,
        FORGEJO_AUTH,
        "keplerops",
        "orion-agent-tool-consumer",
        ".forgejo/workflows/verify-adoption.yml",
        workflow,
        "Add the signed adoption workflow",
    )


def seed_retrieval_sources(operation: str) -> None:
    if operation in {"all", "kep-m03-g"}:
        payload = json.loads((PAYLOADS / "kep-m03-g.json").read_text())
        inventory = payload["protected_inventory"]
        text = (
            "Orion release answers use the orion_partner_intake collection. "
            "The release engineering inventory identifies the WorkHub and partner "
            "intake sources and their writable review room. Follow the protected "
            "inventory record for the current ownership details."
        )
        seed_qdrant(
            "ORION-RAG-SOURCE-INVENTORY-2026",
            "Orion RAG source inventory",
            text,
            {
                **{key: value for key, value in inventory.items() if key != "inventory_reference"},
                "url": "https://workhub.keplerops.lab/issues?set_filter=1&subject=Orion%20RAG%20source%20inventory",
            },
        )
    if operation in {"all", "kep-m03-h"}:
        payload = json.loads((PAYLOADS / "kep-m03-h.json").read_text())
        source = dict(payload)
        for key in ("qdrant_payload", "source_extended_attribute", "report_path"):
            source.pop(key, None)
        source_sha = hashlib.sha256((json.dumps(source, indent=2) + "\n").encode()).hexdigest()
        seed_qdrant(
            "partner-orion-release-criteria",
            "Orion partner release criteria",
            "Partner release criteria used by the failed-ingestion diagnostic workspace.",
            {
                "document_id": payload["document_id"],
                "source_relative_path": payload["source_relative_path"],
                "object_key_template": payload["object_key_template"],
                "source_sha256": source_sha,
                "flag_prefix": payload["qdrant_payload"]["flag_prefix"],
            },
        )
    if operation in {"all", "kep-m03-i"}:
        payload = json.loads((PAYLOADS / "kep-m03-i.json").read_text())
        seed_qdrant(
            payload["source_id"],
            "Retired evaluation-reader access runbook",
            payload["stale_text"],
            {"source_status": payload["source_status"]},
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", nargs="?", default="all")
    operation = parser.parse_args().operation
    if operation == "all" or operation in {"kep-m03-a", "kep-m03-b", "kep-m03-c", "kep-m03-f"}:
        seed_package_repositories()
    seed_retrieval_sources(operation)
    print(f"m03 native enterprise records reconciled for {operation}")


if __name__ == "__main__":
    main()
