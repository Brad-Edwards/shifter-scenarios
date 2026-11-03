"""Issue and verify range-bound FieldKest customer-channel credentials."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
import uuid


SCHEMA = "fieldkest.customer-channel-credentials/v1"
TTL_SECONDS = 3600
TENANT = "TEN-ARWC-047"
CHANNEL = "arwc-stable"
ROLLBACK_VERSION = "7.4.2"
VERSION = re.compile(r"7\.4\.3-cinder\.[a-z0-9][a-z0-9-]{0,23}")
GRANT_SPECS = {
    "poll": ("package.poll", "approved_version"),
    "activate": ("package.activate", "approved_version"),
    "receipt": ("package.receipt", "approved_version"),
    "rollback": ("package.rollback", ROLLBACK_VERSION),
}
DOCUMENT_KEYS = {
    "schema", "credential_id", "range_binding", "tenant", "channel",
    "approved_version", "issued_at_epoch", "expires_at_epoch", "grants",
}
GRANT_KEYS = {"grant_id", "operation", "version", "token"}


def range_binding(range_secret: str) -> str:
    if not isinstance(range_secret, str) or len(range_secret) < 32:
        raise ValueError("invalid range secret")
    return hashlib.sha256(range_secret.encode()).hexdigest()


def issue(approved_version: str, range_secret: str, *, now_epoch: int | None = None) -> dict[str, object]:
    """Return a new credential set for one signed and approved release."""
    if not isinstance(approved_version, str) or not VERSION.fullmatch(approved_version):
        raise ValueError("invalid approved version")
    issued_at = int(time.time()) if now_epoch is None else now_epoch
    if type(issued_at) is not int or issued_at < 0:
        raise ValueError("invalid issue time")
    grants: dict[str, object] = {}
    for name, (operation, version_binding) in GRANT_SPECS.items():
        version = approved_version if version_binding == "approved_version" else version_binding
        grants[name] = {
            "grant_id": "GRT-" + uuid.uuid4().hex.upper(),
            "operation": operation,
            "version": version,
            "token": secrets.token_urlsafe(32),
        }
    return {
        "schema": SCHEMA,
        "credential_id": "CHN-" + uuid.uuid4().hex.upper(),
        "range_binding": range_binding(range_secret),
        "tenant": TENANT,
        "channel": CHANNEL,
        "approved_version": approved_version,
        "issued_at_epoch": issued_at,
        "expires_at_epoch": issued_at + TTL_SECONDS,
        "grants": grants,
    }


def authorize(
    document: object,
    presented_token: str,
    grant_name: str,
    *,
    tenant: str,
    channel: str,
    version: str,
    range_secret: str,
    now_epoch: int | None = None,
) -> bool:
    """Fail closed unless the bearer and every credential binding agree."""
    if not isinstance(document, dict) or set(document) != DOCUMENT_KEYS:
        return False
    if document.get("schema") != SCHEMA:
        return False
    credential_id = document.get("credential_id")
    if not isinstance(credential_id, str) or not re.fullmatch(r"CHN-[0-9A-F]{32}", credential_id):
        return False
    expected_range = range_binding(range_secret)
    actual_range = document.get("range_binding")
    if not isinstance(actual_range, str) or not hmac.compare_digest(actual_range, expected_range):
        return False
    approved_version = document.get("approved_version")
    if not isinstance(approved_version, str) or not VERSION.fullmatch(approved_version):
        return False
    if document.get("tenant") != TENANT or tenant != TENANT:
        return False
    if document.get("channel") != CHANNEL or channel != CHANNEL:
        return False
    issued_at = document.get("issued_at_epoch")
    expires_at = document.get("expires_at_epoch")
    current_time = int(time.time()) if now_epoch is None else now_epoch
    if type(issued_at) is not int or type(expires_at) is not int or type(current_time) is not int:
        return False
    if issued_at > current_time or expires_at <= current_time or expires_at - issued_at != TTL_SECONDS:
        return False
    grants = document.get("grants")
    if not isinstance(grants, dict) or set(grants) != set(GRANT_SPECS):
        return False
    specification = GRANT_SPECS.get(grant_name)
    grant = grants.get(grant_name)
    if specification is None or not isinstance(grant, dict) or set(grant) != GRANT_KEYS:
        return False
    operation, version_binding = specification
    expected_version = approved_version if version_binding == "approved_version" else version_binding
    if grant.get("operation") != operation or grant.get("version") != expected_version or version != expected_version:
        return False
    grant_id = grant.get("grant_id")
    token = grant.get("token")
    if not isinstance(grant_id, str) or not re.fullmatch(r"GRT-[0-9A-F]{32}", grant_id):
        return False
    if not isinstance(token, str) or len(token) < 32 or not isinstance(presented_token, str):
        return False
    return hmac.compare_digest(token, presented_token)
