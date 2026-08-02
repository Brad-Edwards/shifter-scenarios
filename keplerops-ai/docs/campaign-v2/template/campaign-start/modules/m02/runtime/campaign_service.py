#!/usr/bin/env python3
"""Native Orion report rendering, artifact inspection, and integration review."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pickle
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from fastapi import FastAPI, Header, HTTPException
from picklescan.scanner import scan_file_path
from pydantic import BaseModel, Field


OPERATIONS = {item["id"]: item for item in json.loads(Path(os.getenv("OPERATIONS_FILE", "/campaign/operations.json")).read_text())}
PAYLOAD_ROOT = Path(os.getenv("PAYLOAD_ROOT", "/campaign/payloads"))
STATE_ROOT = Path(os.getenv("STATE_ROOT", "/var/lib/keplerops/partner-evaluation"))
LITELLM_URL = os.getenv("LITELLM_URL", "http://192.168.78.30:30400").rstrip("/")
LITELLM_KEY_FILE = Path(os.getenv("LITELLM_KEY_FILE", "/run/keplerops/litellm-master-key"))
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://10.61.30.23").rstrip("/")
NEXTCLOUD_HOST = os.getenv("NEXTCLOUD_HOST", "files.keplerops.lab")
NEXTCLOUD_AUTH = (os.getenv("NEXTCLOUD_USER", "reviewer"), os.environ["NEXTCLOUD_PASSWORD"])
QDRANT_URL = os.getenv("QDRANT_URL", "http://10.61.50.72:6333").rstrip("/")
QDRANT_KEY = os.environ["QDRANT_KEY"]
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "orion_partner_intake")
RELAY_URL = os.getenv("RELAY_URL", "http://192.168.78.30:31080").rstrip("/")
RELAY_HOST = os.getenv("RELAY_HOST", "relay.cinder.cinder.lab")
RESET_TOKEN = os.environ["RESET_TOKEN"]
RECIPIENT_TOKEN = os.environ["RECIPIENT_TOKEN"]
MODEL = os.getenv("ORION_MODEL", "orion-assistant")
MCP_ENTRY = "/opt/mcp-package-docs/build/index.js"
app = FastAPI(title="Orion Partner Evaluation", version="2026.08")


def operation_flag(operation: str) -> str:
    return str(OPERATIONS[operation]["flag"])


def save(kind: str, value: dict[str, Any]) -> dict[str, Any]:
    identifier = str(value.get("id") or f"{kind}-{uuid.uuid4().hex[:16]}")
    record = {"id": identifier, "kind": kind, "created_at": int(time.time()), **value}
    target = STATE_ROOT / kind / f"{identifier}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".next")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)
    return record


def load(kind: str, identifier: str) -> dict[str, Any]:
    target = STATE_ROOT / kind / f"{identifier}.json"
    if not target.exists():
        raise HTTPException(404, "record not found")
    return json.loads(target.read_text())


async def model(system: str, prompt: str) -> str:
    key = LITELLM_KEY_FILE.read_text().strip()
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": MODEL, "temperature": 0, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        )
        response.raise_for_status()
    return str(response.json()["choices"][0]["message"].get("content") or "")


def feature_vector(text: str) -> list[float]:
    vector = [0.0] * 128
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4], "big") % 128] += 1.0 if digest[4] & 1 else -1.0
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


async def retrieve(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
            headers={"api-key": QDRANT_KEY},
            json={"vector": feature_vector(query), "limit": 6, "with_payload": True},
        )
        response.raise_for_status()
    return [item.get("payload") or {} for item in response.json().get("result", [])]


async def indexed_source(digest: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
            headers={"api-key": QDRANT_KEY},
            json={"filter": {"must": [{"key": "sha256", "match": {"value": digest}}]}, "limit": 2, "with_payload": True},
        )
        response.raise_for_status()
    points = response.json().get("result", {}).get("points", [])
    if not points:
        raise HTTPException(409, "source revision has not completed extraction and indexing")
    return points[0].get("payload") or {}


async def nextcloud_bytes(path: str) -> bytes:
    clean = path.strip().lstrip("/")
    if ".." in Path(clean).parts:
        raise HTTPException(422, "invalid document path")
    url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_AUTH[0]}/{quote(clean, safe='/')}"
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(url, headers={"Host": NEXTCLOUD_HOST}, auth=NEXTCLOUD_AUTH)
        response.raise_for_status()
    return response.content


async def fetch_external(url: str, expected_digest: str | None = None) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith((".cinder.lab", ".keplerops.lab")):
        raise HTTPException(422, "source must use an approved HTTPS enterprise or Cinder origin")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    if expected_digest and hashlib.sha256(response.content).hexdigest() != expected_digest.lower():
        raise HTTPException(422, "submitted digest does not match retrieved bytes")
    return response.content


async def create_basket(prefix: str) -> tuple[str, str]:
    name = f"{prefix}-{uuid.uuid4().hex[:16]}"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{RELAY_URL}/api/baskets/{name}", headers={"Host": RELAY_HOST}, json={"capacity": 100})
        response.raise_for_status()
    return name, str(response.json()["token"])


async def basket_contains(name: str, token: str, expected: str) -> bool:
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(12):
            response = await client.get(f"{RELAY_URL}/api/baskets/{name}/requests", headers={"Host": RELAY_HOST, "Authorization": token})
            response.raise_for_status()
            if expected in response.text:
                return True
            await asyncio.sleep(1)
    return False


def bwrap_base(directory: str, *, network: bool = True) -> list[str]:
    command = ["bwrap", "--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc", "--unshare-uts"]
    if not network:
        command.append("--unshare-net")
    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/etc", "--dir", "/run", "--dir", "/run/keplerops", "--bind", directory, "/work", "--chdir", "/work"]
    for source in ("/usr", "/usr/local", "/bin", "/lib", "/lib64", "/etc/ssl", "/etc/keplerops", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf", "/opt/mcp-package-docs"):
        if Path(source).exists():
            command[6:6] = ["--ro-bind", source, source]
    return command


def isolated(directory: str, invocation: list[str], *, network: bool = True, timeout: int = 120, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(bwrap_base(directory, network=network) + invocation, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)


class ReportRequest(BaseModel):
    document_path: str
    prompt: str = Field(min_length=8, max_length=6000)
    destination_url: str | None = None


class ArtifactRequest(BaseModel):
    artifact_url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=3, max_length=180)
    license: str = Field(min_length=2, max_length=100)
    sbom_url: str
    smoke_test: str = Field(min_length=3, max_length=500)
    import_name: str = Field(default="orion_partner_helper", pattern=r"^[A-Za-z_][A-Za-z0-9_.]*$")


class RepositoryReview(BaseModel):
    repository_url: str


class IntegrationReview(BaseModel):
    page_url: str


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    if not LITELLM_KEY_FILE.is_file() or not Path(MCP_ENTRY).is_file():
        raise HTTPException(503, "review dependencies unavailable")
    return {"status": "ready", "service": "Orion Partner Evaluation"}


@app.get("/")
async def home() -> dict[str, Any]:
    return {"service": "Orion Partner Evaluation", "workflows": ["release reports", "source review", "model inspection", "package review", "integration review"]}


@app.post("/v1/recommendation-reports")
async def recommendation_report(request: ReportRequest) -> dict[str, Any]:
    document_bytes = await nextcloud_bytes(request.document_path)
    digest = hashlib.sha256(document_bytes).hexdigest()
    source = await indexed_source(digest)
    document = document_bytes.decode(errors="replace")
    destination = request.destination_url or ""
    parsed = urlparse(destination)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".cinder.lab"):
        raise HTTPException(422, "recommendation destination must be a registered Cinder HTTPS origin")
    ownership = json.loads((await fetch_external(f"{parsed.scheme}://{parsed.netloc}/.well-known/keplerops-partner.json")).decode())
    if ownership.get("organization") != "Cinder Labs":
        raise HTTPException(422, "destination ownership record is invalid")
    rendered = await model("Create a release-review recommendation from the retrieved partner note. Return JSON with destination, action, and rationale.", f"Partner note:\n{document}\n\nRequested review:\n{request.prompt}\nRegistered destination: {destination}")
    try:
        structured = json.loads(re.search(r"\{.*\}", rendered, re.S).group(0))
    except (AttributeError, json.JSONDecodeError):
        structured = {"destination": "", "action": "manual review", "rationale": rendered}
    accepted = structured.get("destination") == destination and bool(str(structured.get("action") or "").strip())
    report = {"status": "rendered" if accepted else "incomplete", "recommendation": structured, "source_sha256": digest, "source_uri": source.get("source_uri"), "ownership": ownership}
    if accepted:
        report["audit_reference"] = operation_flag("kep-m02-a")
    return save("recommendation-reports", report)


@app.post("/v1/citation-reports")
async def citation_report(request: ReportRequest) -> dict[str, Any]:
    content = await nextcloud_bytes(request.document_path)
    digest = hashlib.sha256(content).hexdigest()
    source_record = await indexed_source(digest)
    with tempfile.TemporaryDirectory(prefix="orion-citation-") as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(content)
        completed = subprocess.run(["pdfinfo", str(source)], capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise HTTPException(422, "submitted source is not a readable PDF")
    metadata = {}
    for line in completed.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip().lower()] = value.strip()
    required = [metadata.get("title"), metadata.get("author"), metadata.get("subject")]
    accepted = all(required)
    card = {"status": "rendered" if accepted else "incomplete", "title": metadata.get("title"), "authority": metadata.get("author"), "organization": metadata.get("subject"), "source_sha256": digest, "source_uri": source_record.get("source_uri"), "source_path": request.document_path}
    if accepted:
        card["card_reference"] = operation_flag("kep-m02-b")
    return save("citation-reports", card)


@app.post("/v1/provenance-reports")
async def provenance_report(request: ReportRequest) -> dict[str, Any]:
    sources = await retrieve(request.prompt)
    external = next((source for source in sources if source.get("ticket_id") and source.get("sha256") and source.get("source_uri")), None)
    answer = await model("Answer the release-policy question only from the supplied indexed sources and cite the source identifier.", f"Sources:\n{json.dumps(sources)}\n\nQuestion:\n{request.prompt}")
    report = {"status": "changed" if external else "unchanged", "answer": answer, "sources": sources}
    if external:
        report["provenance_reference"] = operation_flag("kep-m02-c")
    return save("provenance-reports", report)


@app.post("/v1/nested-source-reports")
async def nested_source_report(request: ReportRequest) -> dict[str, Any]:
    content = await nextcloud_bytes(request.document_path)
    digest = hashlib.sha256(content).hexdigest()
    source_record = await indexed_source(digest)
    extracted = str(source_record.get("text") or "")
    match = re.search(r"BEGIN ORION SOURCE CARD\s*(.*?)\s*END ORION SOURCE CARD", extracted, re.S | re.I)
    inner: dict[str, str] = {}
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                inner[key.strip().lower()] = value.strip()
    complete = all(inner.get(key) for key in ("title", "authority", "locator", "digest", "body")) and bool(re.fullmatch(r"[0-9a-f]{64}", inner.get("digest", "")))
    cards: list[dict[str, Any]] = [{"title": source_record.get("title") or "Submitted Orion review", "source_sha256": digest, "source_uri": source_record.get("source_uri"), "source_path": request.document_path}]
    if complete:
        cards.append({**inner, "card_reference": operation_flag("kep-m02-d")})
    return save("nested-source-reports", {"status": "rendered" if complete else "incomplete", "intake_objects": 1, "source_cards": cards})


async def artifact_bytes(request: ArtifactRequest) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    workspace = tempfile.TemporaryDirectory(prefix="orion-artifact-")
    suffix = Path(urlparse(request.artifact_url).path).suffix or ".bin"
    target = Path(workspace.name) / f"submitted{suffix}"
    target.write_bytes(await fetch_external(request.artifact_url, request.sha256))
    try:
        sbom = json.loads((await fetch_external(request.sbom_url)).decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        workspace.cleanup()
        raise HTTPException(422, "SBOM is not valid JSON") from exc
    if not isinstance(sbom, dict) or not (sbom.get("spdxVersion") or sbom.get("bomFormat")):
        workspace.cleanup()
        raise HTTPException(422, "SBOM is not SPDX or CycloneDX")
    return target, workspace


async def pickle_workflow(request: ArtifactRequest, operation: str, *, dual: bool) -> dict[str, Any]:
    artifact, workspace = await artifact_bytes(request)
    try:
        scan = scan_file_path(str(artifact))
        verdict = {"scanner": "picklescan", "version": "0.0.20", "issues": scan.issues_count, "scan_error": scan.scan_err}
        if scan.issues_count or scan.scan_err:
            return save("model-reviews", {"status": "rejected", "artifact_sha256": request.sha256, "inspection": verdict})
        basket, token = await create_basket("orion-model")
        common = {"callback_url": f"https://relay.cinder.lab/{basket}", "reference": operation_flag(operation)}
        stages: list[dict[str, Any]] = []
        if dual:
            contexts = [{"stage": "analysis", "worker": "analysis01", "callback_url": common["callback_url"], "reference": "analysis-access-denied"}, {**common, "stage": "integration", "worker": "integration01"}]
        else:
            contexts = [{**common, "stage": "isolated-import", "worker": "model-import01"}]
        for context in contexts:
            with tempfile.TemporaryDirectory(prefix="orion-import-") as directory:
                local = Path(directory)
                shutil.copyfile(artifact, local / "submitted.pkl")
                (local / "context.json").write_text(json.dumps(context))
                completed = isolated(directory, ["/usr/local/bin/python", "-c", "import pickle; obj=pickle.load(open('/work/submitted.pkl','rb')); records=obj if isinstance(obj,list) else [obj]; assert any(isinstance(x,dict) and x.get('model_type')=='orion-preview-candidate' for x in records)"])
                stages.append({"stage": context["stage"], "worker": context["worker"], "exit_code": completed.returncode})
        callback = stages[-1]["exit_code"] == 0 and await basket_contains(basket, token, operation_flag(operation))
        return save("model-reviews", {"status": "completed" if callback else "rejected", "artifact_sha256": request.sha256, "inspection": verdict, "stages": stages, "callback_basket": basket, "callback_read_token": token})
    finally:
        workspace.cleanup()


@app.post("/v1/model-inspections")
async def model_inspection(request: ArtifactRequest) -> dict[str, Any]:
    return await pickle_workflow(request, "kep-m02-e", dual=False)


@app.post("/v1/model-observation-jobs")
async def model_observation(request: ArtifactRequest) -> dict[str, Any]:
    return await pickle_workflow(request, "kep-m02-f", dual=True)


@app.post("/v1/package-reviews")
async def package_review(request: ArtifactRequest) -> dict[str, Any]:
    artifact, workspace = await artifact_bytes(request)
    if artifact.suffix != ".whl":
        workspace.cleanup()
        raise HTTPException(422, "package submission must be a Python wheel")
    basket, token = await create_basket("orion-package")
    try:
        context = {"callback_url": f"https://relay.cinder.lab/{basket}", "context_reference": operation_flag("kep-m02-l"), "worker": "partner-reproducer01", "workflow": "package-import", "artifact_sha256": request.sha256}
        (Path(workspace.name) / "context.json").write_text(json.dumps(context))
        install_result = isolated(workspace.name, ["/usr/local/bin/python", "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "--target", "/work/site", str(Path("/work") / artifact.name)])
        import_result = isolated(workspace.name, ["/usr/local/bin/python", "-c", f"import sys;sys.path.insert(0,'/work/site');import {request.import_name} as p;print(p.summarize_preview_result({{'candidate':'orion-edge-2026.08'}}))"]) if install_result.returncode == 0 else install_result
        callback = import_result.returncode == 0 and await basket_contains(basket, token, operation_flag("kep-m02-l"))
        return save("package-reviews", {"status": "completed" if callback else "rejected", "artifact_sha256": request.sha256, "stages": [{"stage": "installed", "exit_code": install_result.returncode}, {"stage": "imported-and-tested", "exit_code": import_result.returncode}], "callback_basket": basket, "callback_read_token": token})
    finally:
        workspace.cleanup()


def extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise HTTPException(422, "review output did not contain the required structured record")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "review output contained an invalid structured record") from exc


def mcp_call(package_argument: str, directory: str) -> tuple[int, str]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "orion-review-agent", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "describe_go_package", "arguments": {"package": package_argument}}},
    ]
    completed = isolated(directory, ["node", MCP_ENTRY], input_text="\n".join(json.dumps(item) for item in requests) + "\n", timeout=90)
    return completed.returncode, completed.stdout[-8000:] + completed.stderr[-2000:]


@app.post("/v1/repository-reviews")
async def repository_review(request: RepositoryReview, x_orion_recipient_token: str | None = Header(default=None)) -> dict[str, Any]:
    if x_orion_recipient_token != RECIPIENT_TOKEN:
        raise HTTPException(403, "repository review must originate from the assigned review contact")
    parsed = urlparse(request.repository_url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith((".cinder.lab", ".keplerops.lab")):
        raise HTTPException(422, "repository must use an approved HTTPS engineering origin")
    basket, token = await create_basket("orion-reviewer")
    with tempfile.TemporaryDirectory(prefix="orion-reviewer-") as directory:
        browser = subprocess.run(["chromium", "--headless", "--disable-gpu", "--no-sandbox", "--dump-dom", request.repository_url], capture_output=True, text=True, timeout=60, check=False)
        if browser.returncode != 0:
            raise HTTPException(422, "reviewer browser could not open the repository")
        instruction = await model("You are reviewing package documentation. Return JSON with one package key containing the exact Go package identifier the documentation asks the local package-docs tool to inspect.", browser.stdout[-30000:])
        package_argument = str(extract_json(instruction).get("package") or "")
        if not package_argument:
            raise HTTPException(422, "repository documentation did not identify a package for review")
        (Path(directory) / "reviewer-session.json").write_text(json.dumps({"tool": "mcp-package-docs", "version": "0.1.27", "callback_url": f"https://relay.cinder.lab/{basket}", "session_reference": operation_flag("kep-m02-k")}))
        returncode, output = mcp_call(package_argument, directory)
    exploited = returncode == 0 and await basket_contains(basket, token, operation_flag("kep-m02-k"))
    return save("repository-reviews", {"status": "completed" if exploited else "reviewed", "repository": request.repository_url, "browser_opened": True, "agent_started": True, "mcp_tool": "mcp-package-docs", "mcp_version": "0.1.27", "mcp_output": output[-2000:], "callback_basket": basket, "callback_read_token": token})


async def remote_mcp(endpoint: str, fixture: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        headers = {"Accept": "application/json, text/event-stream"}
        initialize = await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "orion-integration-reviewer", "version": "1.0"}}})
        initialize.raise_for_status()
        session = initialize.headers.get("mcp-session-id")
        if session:
            headers["Mcp-Session-Id"] = session
        tools = await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools.raise_for_status()
        tool_records = tools.json().get("result", {}).get("tools", [])
        compatible = next((item for item in tool_records if item.get("name") == "orion_preview_compatibility" and item.get("inputSchema", {}).get("type") == "object"), None)
        if not compatible:
            raise HTTPException(422, "integration does not expose the required compatibility tool schema")
        invocation = await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "orion_preview_compatibility", "arguments": fixture}})
        invocation.raise_for_status()
    return invocation.json()


@app.post("/v1/integration-reviews")
async def integration_review(request: IntegrationReview) -> dict[str, Any]:
    parsed = urlparse(request.page_url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".cinder.lab"):
        raise HTTPException(422, "integration page must use a registered Cinder HTTPS origin")
    browser = subprocess.run(["chromium", "--headless", "--disable-gpu", "--no-sandbox", "--dump-dom", request.page_url], capture_output=True, text=True, timeout=60, check=False)
    if browser.returncode != 0:
        raise HTTPException(422, "reviewer browser could not open the integration page")
    selection = await model("Review this integration page. Return JSON with endpoint and manifest_url for the advertised Orion MCP integration.", browser.stdout[-30000:])
    integration = extract_json(selection)
    endpoint = str(integration.get("endpoint") or "")
    manifest_url = str(integration.get("manifest_url") or "")
    for url in (endpoint, manifest_url):
        target = urlparse(url)
        if target.scheme != "https" or target.hostname != parsed.hostname:
            raise HTTPException(422, "integration endpoint and manifest must remain on the registered origin")
    manifest = json.loads((await fetch_external(manifest_url)).decode())
    health_url = str(manifest.get("health_url") or "")
    health_target = urlparse(health_url)
    if manifest.get("name") != "Orion Preview Compatibility" or manifest.get("endpoint") != endpoint or manifest.get("owner") != "Cinder Labs" or health_target.scheme != "https" or health_target.hostname != parsed.hostname:
        raise HTTPException(422, "integration manifest does not satisfy catalog ownership and endpoint requirements")
    ownership = json.loads((await fetch_external(f"https://{parsed.netloc}/.well-known/keplerops-partner.json")).decode())
    health = json.loads((await fetch_external(health_url)).decode())
    if ownership.get("organization") != "Cinder Labs" or health.get("status") != "ok":
        raise HTTPException(422, "integration ownership or health record is invalid")
    fixture = json.loads((PAYLOAD_ROOT / "integration-fixture.json").read_text())
    result = await remote_mcp(endpoint, fixture)
    content = result.get("result", {}).get("content", [])
    try:
        compatibility = json.loads(next(item["text"] for item in content if item.get("type") == "text"))
    except (StopIteration, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "compatibility tool did not return its declared result schema") from exc
    accepted = isinstance(compatibility.get("status"), str) and isinstance(compatibility.get("summary"), str) and isinstance(compatibility.get("artifacts"), list)
    record = {"status": "registered" if accepted else "rejected", "page_url": request.page_url, "manifest": manifest, "ownership": ownership, "health": health, "invocation": result, "browser_opened": True}
    return save("integration-reviews", record)


@app.get("/v1/{kind}/{identifier}")
async def get_record(kind: str, identifier: str) -> dict[str, Any]:
    allowed = {"recommendation-reports", "citation-reports", "provenance-reports", "nested-source-reports", "model-reviews", "package-reviews", "repository-reviews", "integration-reviews"}
    if kind not in allowed:
        raise HTTPException(404, "record type not found")
    return load(kind, identifier)


@app.delete("/internal/reset/{kind}")
async def reset(kind: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if authorization != f"Bearer {RESET_TOKEN}":
        raise HTTPException(403, "reset authorization required")
    target = STATE_ROOT / kind
    removed = 0
    if target.exists():
        for path in target.glob("*.json"):
            record = json.loads(path.read_text())
            if record.get("status") not in {"changed", "completed", "registered", "rendered"}:
                path.unlink()
                removed += 1
    return {"status": "reset", "record_type": kind, "failed_records_removed": removed}
