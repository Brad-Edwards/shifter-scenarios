from __future__ import annotations

from domain import DomainError
from domain import RuntimeGate
from domain import SessionClaims
from fastapi import Cookie
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Header
from jwt import PyJWKClient
from keplerops_runtime.foundation.config import AUTHENTICATION_REQUIRED, CONFIG, IDENTITY_UNAVAILABLE, NOT_FOUND, PRODUCER_AUTHENTICATION_REQUIRED, RANGE_UNAVAILABLE, SESSION_COOKIE, TLS_CA_PATH, _regular_owner_file, _runtime_owner_file
from pathlib import Path
from typing import Annotated
import hmac
import jwt
import sqlite3
import time


def _bearer(
    authorization: Annotated[str | None, Header()] = None,
    keplerops_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> str:
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail=AUTHENTICATION_REQUIRED)
        token = authorization[7:]
    else:
        token = keplerops_session or ""
    if not token or len(token) > 8192:
        raise HTTPException(status_code=401, detail=AUTHENTICATION_REQUIRED)
    return token

def _session(token: Annotated[str, Depends(_bearer)]) -> SessionClaims:
    issuer = CONFIG.get("issuer")
    identity_issuer = CONFIG.get("identity_internal_issuer", issuer)
    audience = CONFIG.get("audience")
    if not isinstance(issuer, str) or not isinstance(identity_issuer, str) or not isinstance(audience, str):
        raise HTTPException(status_code=503, detail=IDENTITY_UNAVAILABLE)
    try:
        valid_issuer: str | tuple[str, str] = (
            issuer if identity_issuer == issuer else (issuer, identity_issuer)
        )
        key = PyJWKClient(f"{identity_issuer.rstrip('/')}/protocol/openid-connect/certs").get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=valid_issuer,
            options={"require": ["exp", "sub", "preferred_username", "roles", "range_instance"]},
        )
        session = SessionClaims.from_mapping(
            {
                "range_instance": claims["range_instance"],
                "participant": claims["preferred_username"],
                "roles": claims["roles"],
                "expires_at": claims["exp"],
            },
            now=int(time.time()),
        )
        if session.range_instance != CONFIG["range_instance"]:
            raise DomainError("session: range mismatch")
        return session
    except (jwt.PyJWTError, DomainError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail=AUTHENTICATION_REQUIRED) from None

def _service_authorized(x_service_token: Annotated[str | None, Header()] = None) -> None:
    token_file = CONFIG.get("service_token_file")
    if not isinstance(token_file, str) or not x_service_token:
        raise HTTPException(status_code=401, detail="service authentication required")
    try:
        expected = _regular_owner_file(Path(token_file)).decode("utf-8")
    except (OSError, UnicodeError, RuntimeError):
        raise HTTPException(status_code=503, detail="service authentication unavailable") from None
    if not hmac.compare_digest(expected, x_service_token):
        raise HTTPException(status_code=401, detail="service authentication required")

def _producer_authorized(
    x_producer_id: Annotated[str | None, Header()] = None,
    x_producer_token: Annotated[str | None, Header()] = None,
) -> str:
    token_dir = CONFIG.get("producer_tokens_dir")
    if (
        not isinstance(token_dir, str)
        or not isinstance(x_producer_id, str)
        or not x_producer_id
        or not x_producer_id.replace("-", "").isalnum()
        or not x_producer_token
    ):
        raise HTTPException(status_code=401, detail=PRODUCER_AUTHENTICATION_REQUIRED)
    try:
        expected = _regular_owner_file(Path(token_dir) / x_producer_id).decode("utf-8")
    except (OSError, UnicodeError, RuntimeError):
        raise HTTPException(status_code=401, detail=PRODUCER_AUTHENTICATION_REQUIRED) from None
    if not hmac.compare_digest(expected, x_producer_token):
        raise HTTPException(status_code=401, detail=PRODUCER_AUTHENTICATION_REQUIRED)
    return x_producer_id

def _require_role(role: str) -> None:
    if CONFIG["role"] != role:
        raise HTTPException(status_code=404, detail=NOT_FOUND)

def _current_generation() -> int:
    path = CONFIG.get("generation_file")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    try:
        raw = _runtime_owner_file(Path(path)).decode("ascii")
        generation = int(raw)
    except (OSError, UnicodeError, ValueError, RuntimeError):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE) from None
    if generation < 0:
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    return generation

def _require_ready() -> int:
    state_path = CONFIG.get("runtime_state_file")
    configured = CONFIG.get("reset_generation")
    if not isinstance(state_path, str) or not isinstance(configured, int):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    try:
        status = _runtime_owner_file(Path(state_path)).decode("ascii")
        gate = RuntimeGate.from_values(status, _current_generation())
        gate.require_ready(configured)
    except (OSError, UnicodeError, RuntimeError, DomainError):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE) from None
    return configured

def _telemetry_enabled() -> bool:
    path = CONFIG.get("telemetry_enabled_file")
    if not isinstance(path, str):
        return False
    try:
        return _runtime_owner_file(Path(path)) == b"enabled"
    except (OSError, RuntimeError):
        return False

def _database() -> sqlite3.Connection:
    path = CONFIG.get("database_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail="proof store unavailable")
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS evidence ("
        "range_instance TEXT NOT NULL, participant TEXT NOT NULL, "
        "outcome_id TEXT NOT NULL, evidence_id TEXT NOT NULL, reset_generation INTEGER NOT NULL, "
        "producer_asset TEXT NOT NULL, event_timestamp INTEGER NOT NULL, expires_at INTEGER NOT NULL, "
        "event_json TEXT NOT NULL, PRIMARY KEY "
        "(range_instance, participant, evidence_id, reset_generation))"
    )
    return connection

def _postgres():
    import psycopg

    host = CONFIG.get("postgres_host")
    password_file = CONFIG.get("postgres_password_file")
    if not isinstance(host, str) or not isinstance(password_file, str):
        raise HTTPException(status_code=503, detail="dataset store unavailable")
    try:
        password = _regular_owner_file(Path(password_file)).decode("utf-8")
        return psycopg.connect(
            host=host,
            port=5432,
            dbname="keplerops",
            user="keplerops",
            password=password,
            sslmode="verify-full",
            sslrootcert=TLS_CA_PATH,
            connect_timeout=5,
        )
    except (OSError, UnicodeError, RuntimeError, psycopg.Error):
        raise HTTPException(status_code=503, detail="dataset store unavailable") from None
