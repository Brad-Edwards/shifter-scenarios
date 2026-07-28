"""Loopback-only real browser and constrained package execution worker."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import resource
import tempfile
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from agent_actions import PACKAGE_URL, click_trap_id, package_url_allowed, web_delivery_id
from workhub_credentials import workhub_credentials


SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA256_PREFIX = "sha256:"
TLS_CA_PATH = "/run/tls/ca.crt"
MAX_ARTIFACT_BYTES = 64 * 1024
MAX_BROWSER_BYTES = 128 * 1024
ERROR_RESPONSES = {
    422: {"description": "Action request or observed effect is invalid"},
    503: {"description": "Required action service is unavailable"},
}


class PackageRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    package_url: str = Field(min_length=1, max_length=512)
    expected_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    nonce: str = Field(pattern=r"^[0-9a-f]{24}$")


class BrowserOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    url: str = Field(min_length=1, max_length=512)


app = FastAPI(title="KeplerOps agent action worker", docs_url=None, redoc_url=None)


def _runner_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_ARTIFACT_BYTES, MAX_ARTIFACT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))


def _write_package(content: bytes) -> Path:
    descriptor, path_value = tempfile.mkstemp(prefix="keplerops-package-", suffix=".sh")
    path = Path(path_value)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
    path.chmod(0o400)
    return path


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/packages/run", responses=ERROR_RESPONSES)
async def run_package(request: PackageRunRequest) -> dict[str, object]:
    if not package_url_allowed(request.package_url) or not SHA256.fullmatch(request.expected_digest):
        raise HTTPException(status_code=422, detail="package binding rejected")
    try:
        async with httpx.AsyncClient(timeout=8.0, verify=TLS_CA_PATH) as client:
            response = await client.get(
                PACKAGE_URL,
                auth=workhub_credentials(),
                headers={"Host": "workhub.keplerops.lab"},
            )
    except (httpx.HTTPError, OSError):
        raise HTTPException(status_code=503, detail="package registry unavailable") from None
    if response.status_code != 200 or not 1 <= len(response.content) <= MAX_ARTIFACT_BYTES:
        raise HTTPException(status_code=503, detail="package artifact unavailable")
    digest = SHA256_PREFIX + hashlib.sha256(response.content).hexdigest()
    if digest != request.expected_digest:
        raise HTTPException(status_code=422, detail="package digest rejected")
    path = await asyncio.to_thread(_write_package, response.content)
    try:
        process = await asyncio.create_subprocess_exec(
            "/bin/sh",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "KEPLEROPS_PACKAGE_NONCE": request.nonce},
            preexec_fn=_runner_limits,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=4.0)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise HTTPException(status_code=422, detail="package execution timed out") from None
    finally:
        await asyncio.to_thread(path.unlink, missing_ok=True)
    expected_output = f"keplerops-contained-package-effect:{request.nonce}\n".encode()
    if process.returncode != 0 or stdout != expected_output or stderr:
        raise HTTPException(status_code=422, detail="package effect rejected")
    return {
        "executed": True,
        "package_digest": digest,
        "byte_count": len(response.content),
        "process_id": process.pid,
        "effect_digest": SHA256_PREFIX + hashlib.sha256(stdout).hexdigest(),
    }


@app.post("/v1/browser/open", responses=ERROR_RESPONSES)
async def open_in_browser(request: BrowserOpenRequest) -> dict[str, object]:
    trap_id = click_trap_id(request.url)
    delivery_id = web_delivery_id(request.url)
    if trap_id is None and delivery_id is None:
        raise HTTPException(status_code=422, detail="browser target rejected")
    path = (
        f"/public/agent-click/{trap_id}"
        if trap_id is not None
        else f"/public/evasion/deliveries/{delivery_id}"
    )
    loopback_url = f"http://127.0.0.1:8443{path}"
    source_digest: str | None = None
    if delivery_id is not None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                source = await client.get(loopback_url)
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="delivery retrieval failed") from None
        if source.status_code != 200 or not 1 <= len(source.content) <= MAX_BROWSER_BYTES:
            raise HTTPException(status_code=503, detail="delivery retrieval failed")
        source_digest = SHA256_PREFIX + hashlib.sha256(source.content).hexdigest()
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/chromium-headless-shell",
        "--headless=new",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--ignore-certificate-errors",
        "--no-sandbox",
        "--no-first-run",
        "--dump-dom",
        loopback_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=12.0)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise HTTPException(status_code=503, detail="browser navigation timed out") from None
    if process.returncode != 0 or not 1 <= len(stdout) <= MAX_BROWSER_BYTES:
        raise HTTPException(status_code=503, detail="browser navigation failed")
    result: dict[str, object] = {
        "rendered": True,
        "browser_pid": process.pid,
        "dom": stdout.decode("utf-8", errors="replace"),
        "dom_digest": SHA256_PREFIX + hashlib.sha256(stdout).hexdigest(),
        "byte_count": len(stdout),
    }
    if source_digest is not None:
        result["source_digest"] = source_digest
    return result
