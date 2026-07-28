#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import stat
import string
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EVENT_PATH = SCRIPT_DIR / "agentic_workshop.json"


def load_event_config(path: str | None = None) -> dict[str, Any]:
    event_path = Path(path) if path else DEFAULT_EVENT_PATH
    with event_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def read_token_file(path: str | Path) -> str:
    """Read an admin token from an owner-only regular file."""

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("token file must be a regular non-symlink file")
    mode = stat.S_IMODE(source.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("token file must not grant group or world permissions")
    token = source.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("token file is empty")
    return token


def resolve_admin_token(token_file: str | Path | None = None) -> str | None:
    """Resolve admin auth without ever accepting a process-argv token."""

    if token_file:
        return read_token_file(token_file)
    return os.environ.get("CTFD_TOKEN")


class CtfdClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 30,
        *,
        allow_loopback_http: bool = False,
        max_response_bytes: int = 1024 * 1024,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("CTFd base URL must be a credential-free origin")
        loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and loopback and allow_loopback_http
        ):
            raise ValueError(
                "CTFd requires HTTPS except explicit loopback development"
            )
        if not token:
            raise ValueError("CTFd token is required")
        if timeout <= 0 or max_response_bytes <= 0:
            raise ValueError("CTFd request bounds must be positive")
        self.base_url = base_url.rstrip("/")
        self.origin = (
            parsed.scheme.lower(),
            parsed.hostname.lower(),
            parsed.port,
        )
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "User-Agent": "shifter-ctfd-workshop/1.0",
        }
        self.opener = urllib.request.build_opener(
            _SameOriginRedirectHandler(self.origin)
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | list[Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1{path}"
        if query:
            query_string = urllib.parse.urlencode(
                {
                    key: value
                    for key, value in query.items()
                    if value is not None
                },
                doseq=True,
            )
            if query_string:
                url = f"{url}?{query_string}"

        request_body = None
        if body is not None:
            request_body = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=request_body,
            headers=self.headers,
            method=method.upper(),
        )

        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise RuntimeError(
                        f"CTFd API {method.upper()} {path} exceeded response limit"
                    )
                payload = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"CTFd API {method.upper()} {path} failed with HTTP {exc.code}"
            ) from exc
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise RuntimeError(
                f"CTFd API {method.upper()} {path} returned invalid JSON"
            ) from exc

        if payload.get("success") is False:
            raise RuntimeError(
                f"CTFd API {method.upper()} {path} returned an error"
            )
        return payload

    def get(self, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request("GET", path, query=query)

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, body=body)

    def patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", path, body=body)

    def delete(self, path: str) -> dict[str, Any]:
        return self.request("DELETE", path)


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never forward the authorization header to another origin."""

    def __init__(self, origin: tuple[str, str, int | None]) -> None:
        self.origin = origin
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        target = (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower(),
            parsed.port,
        )
        if target != self.origin:
            raise urllib.error.HTTPError(
                newurl,
                code,
                "cross-origin redirect refused",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)
