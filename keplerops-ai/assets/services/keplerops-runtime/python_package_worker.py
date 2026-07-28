"""Real PyPI resolver and network-isolated package execution services."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import os
import re
import resource
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from workhub_credentials import workhub_credentials


MODE = os.environ.get("KEPLEROPS_PACKAGE_WORKER_MODE", "")
ALLOWED_MODES = frozenset({"resolver", "analysis", "worker"})
ALLOWED_PACKAGES = frozenset({"keplerops-eval-runtime", "keplerops-eval-runtlme"})
PACKAGE_VERSION = "1.0.0"
PACKAGE_MODULE = "keplerops_eval_runtime"
REGISTRY_HOST = "repo-ticket-01.keplerops.lab"
INDEX_URL = f"https://{REGISTRY_HOST}/git/api/packages/ml.engineer/pypi/simple"
SHA256_PREFIX = "sha256:"
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
NONCE = re.compile(r"^[0-9a-f]{24}$")
MAX_WHEEL_BYTES = 256 * 1024
ERROR_RESPONSES = {
    422: {"description": "Package identity, artifact, or effect is invalid"},
    503: {"description": "Package registry, resolver, or execution is unavailable"},
}
COMMAND_TIMEOUTS = {"resolve": 20.0, "install": 15.0, "execute": 8.0}


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    package_name: str = Field(min_length=1, max_length=128)
    package_version: str = Field(min_length=1, max_length=32)


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    wheel: str = Field(min_length=64, max_length=400_000)
    expected_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    nonce: str = Field(pattern=r"^[0-9a-f]{24}$")


app = FastAPI(title="KeplerOps Python package worker", docs_url=None, redoc_url=None)


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_WHEEL_BYTES, MAX_WHEEL_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _wheel_identity(raw: bytes) -> tuple[str, str]:
    if not 1 <= len(raw) <= MAX_WHEEL_BYTES:
        raise HTTPException(status_code=422, detail="wheel size rejected")
    try:
        with tempfile.SpooledTemporaryFile(max_size=MAX_WHEEL_BYTES) as handle:
            handle.write(raw)
            handle.seek(0)
            with zipfile.ZipFile(handle) as archive:
                metadata_paths = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                ]
                if len(metadata_paths) != 1:
                    raise ValueError("ambiguous metadata")
                metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
    except (OSError, ValueError, zipfile.BadZipFile, KeyError):
        raise HTTPException(status_code=422, detail="wheel metadata rejected") from None
    name = _normalized(metadata.get("Name", ""))
    version = metadata.get("Version", "")
    if name not in ALLOWED_PACKAGES or version != PACKAGE_VERSION:
        raise HTTPException(status_code=422, detail="wheel identity rejected")
    return name, version


async def _command(
    arguments: list[str],
    *,
    env: dict[str, str],
    operation: Literal["resolve", "install", "execute"],
) -> tuple[int, bytes, int]:
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        preexec_fn=_limits,
    )
    try:
        async with asyncio.timeout(COMMAND_TIMEOUTS[operation]):
            stdout, _ = await process.communicate()
    except TimeoutError:
        process.kill()
        await process.wait()
        raise HTTPException(
            status_code=503, detail="package command timed out"
        ) from None
    return process.returncode or 0, stdout, process.pid


def _base_env(home: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PIP_CERT": "/run/tls/ca.crt",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        "SSL_CERT_FILE": "/run/tls/ca.crt",
    }


def _write_netrc(home: Path) -> None:
    username, password = workhub_credentials()
    path = home / ".netrc"
    path.write_text(
        f"machine {REGISTRY_HOST} login {username} password {password}\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


@app.get("/healthz", responses=ERROR_RESPONSES)
def healthz() -> dict[str, str]:
    if MODE not in ALLOWED_MODES:
        raise HTTPException(status_code=503, detail="package worker mode unavailable")
    return {"status": "ok", "mode": MODE}


@app.post("/v1/resolve", responses=ERROR_RESPONSES)
async def resolve(request: ResolveRequest) -> dict[str, object]:
    if MODE != "resolver":
        raise HTTPException(status_code=404, detail="not found")
    package_name = _normalized(request.package_name)
    if (
        package_name not in ALLOWED_PACKAGES
        or request.package_version != PACKAGE_VERSION
    ):
        raise HTTPException(status_code=422, detail="package selection rejected")
    with tempfile.TemporaryDirectory(prefix="keplerops-resolver-") as directory:
        home = Path(directory)
        _write_netrc(home)
        status, _, process_id = await _command(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--no-cache-dir",
                "--no-deps",
                "--only-binary=:all:",
                "--index-url",
                INDEX_URL,
                "--dest",
                directory,
                f"{package_name}=={PACKAGE_VERSION}",
            ],
            env=_base_env(home),
            operation="resolve",
        )
        wheels = list(Path(directory).glob("*.whl"))
        if status != 0 or len(wheels) != 1:
            raise HTTPException(status_code=503, detail="package resolution failed")
        raw = wheels[0].read_bytes()
    resolved_name, resolved_version = _wheel_identity(raw)
    if resolved_name != package_name or resolved_version != request.package_version:
        raise HTTPException(
            status_code=422, detail="resolved package identity diverged"
        )
    return {
        "package_name": resolved_name,
        "package_version": resolved_version,
        "resolver": "pip-gitea-pypi",
        "resolver_process_id": process_id,
        "wheel_digest": SHA256_PREFIX + hashlib.sha256(raw).hexdigest(),
        "wheel": base64.b64encode(raw).decode("ascii"),
    }


def _execution_artifact(request: ExecuteRequest) -> tuple[bytes, str, str, str]:
    try:
        raw = base64.b64decode(request.wheel, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="wheel encoding rejected") from None
    digest = SHA256_PREFIX + hashlib.sha256(raw).hexdigest()
    if (
        not SHA256.fullmatch(request.expected_digest)
        or digest != request.expected_digest
    ):
        raise HTTPException(status_code=422, detail="wheel digest rejected")
    package_name, package_version = _wheel_identity(raw)
    return raw, digest, package_name, package_version


async def _install_artifact(
    root: Path, raw: bytes, package_name: str, package_version: str
) -> Path:
    wheel_path = root / (
        f"{package_name.replace('-', '_')}-{package_version}-py3-none-any.whl"
    )
    target = root / "installed"
    wheel_path.write_bytes(raw)
    wheel_path.chmod(0o400)
    status, _, _ = await _command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--no-compile",
            "--no-deps",
            "--no-index",
            "--target",
            str(target),
            str(wheel_path),
        ],
        env=_base_env(root),
        operation="install",
    )
    if status != 0 or not (target / PACKAGE_MODULE / "__init__.py").is_file():
        raise HTTPException(status_code=422, detail="wheel installation failed")
    return target


def _execution_result(status: int, stdout: bytes) -> dict[str, object]:
    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="package result rejected") from None
    if (
        status != 0
        or not isinstance(result, dict)
        or set(result) != {"decision", "effect", "profile"}
    ):
        raise HTTPException(status_code=422, detail="package result rejected")
    return result


def _effect_fields(
    effect_path: Path, result: dict[str, object], nonce: str
) -> tuple[bool, str | None]:
    if not effect_path.is_file():
        return False, None
    effect = effect_path.read_bytes()
    expected = f"keplerops-contained-runtime-effect:{nonce}\n".encode()
    if effect != expected or result.get("effect") != expected.decode().strip():
        raise HTTPException(status_code=422, detail="worker effect rejected")
    return True, SHA256_PREFIX + hashlib.sha256(effect).hexdigest()


@app.post("/v1/execute", responses=ERROR_RESPONSES)
async def execute(request: ExecuteRequest) -> dict[str, object]:
    if MODE not in {"analysis", "worker"}:
        raise HTTPException(status_code=404, detail="not found")
    raw, digest, package_name, package_version = _execution_artifact(request)
    with tempfile.TemporaryDirectory(prefix=f"keplerops-{MODE}-") as directory:
        root = Path(directory)
        target = await _install_artifact(root, raw, package_name, package_version)
        effect_path = root / "effect.txt"
        script = (
            "import json,sys; sys.path.insert(0,sys.argv[1]); "
            f"import {PACKAGE_MODULE} as runtime; "
            "print(json.dumps(runtime.evaluate(sys.argv[2]),sort_keys=True))"
        )
        env = _base_env(root)
        env.update(
            {
                "KEPLEROPS_EXECUTION_PROFILE": MODE,
                "KEPLEROPS_EVALUATION_NONCE": request.nonce,
                "KEPLEROPS_EFFECT_PATH": str(effect_path),
            }
        )
        status, stdout, process_id = await _command(
            [sys.executable, "-I", "-c", script, str(target), request.nonce],
            env=env,
            operation="execute",
        )
        result = _execution_result(status, stdout)
        effect_observed, effect_digest = _effect_fields(
            effect_path, result, request.nonce
        )
        if result.get("profile") != MODE:
            raise HTTPException(status_code=422, detail="execution profile diverged")
        if MODE == "analysis" and effect_observed:
            raise HTTPException(status_code=422, detail="analysis effect rejected")
    return {
        "package_name": package_name,
        "package_version": package_version,
        "installed_digest": digest,
        "profile": MODE,
        "decision": result["decision"],
        "effect_observed": effect_observed,
        "effect_digest": effect_digest,
        "process_id": process_id,
    }
