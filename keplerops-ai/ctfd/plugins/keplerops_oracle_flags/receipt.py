"""Verify proof-service receipts bound to one CTFd participant and range."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

RECEIPT_PREFIX = "PENR1"
MAX_RECEIPT_BYTES = 4096
RECEIPT_KEYS = {
    "version", "flag_id", "outcome", "evidence", "range_instance",
    "participant", "reset_generation", "verdict", "issued_at", "expires_at",
}
STATUS_EXPIRED_RECEIPT = "expired_receipt"
STATUS_CROSS_NAMESPACE = "cross_namespace"
STATUS_INVALID_FORMAT = "invalid_format"
STATUS_INVALID_PAYLOAD = "invalid_payload"
STATUS_INVALID_SIGNATURE = "invalid_signature"
STATUS_INVALID_TIMESTAMP = "invalid_timestamp"
STATUS_INVALID_VERDICT = "invalid_verdict"
STATUS_NOT_YET_VALID = "not_yet_valid"
STATUS_PASSED = "passed"
STATUS_STALE_RESET_GENERATION = "stale_reset_generation"
STATUS_WRONG_OBJECTIVE = "wrong_objective"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encode_receipt(body: bytes, signature: str) -> str:
    """Encode an already-signed proof receipt without exposing it in metadata."""
    return f"{RECEIPT_PREFIX}.{_b64encode(body)}.{signature}"


def verify_receipt_status(receipt: str, *, contract: dict[str, Any],
                          binding: dict[str, Any], verification_key: bytes,
                          now: int) -> str:
    """Classify receipt verification without exposing receipt content."""
    try:
        if not isinstance(receipt, str) or len(receipt.encode()) > MAX_RECEIPT_BYTES:
            return STATUS_INVALID_FORMAT
        prefix, encoded, supplied_signature = receipt.split(".", 2)
        if prefix != RECEIPT_PREFIX or len(supplied_signature) != 64:
            return STATUS_INVALID_FORMAT
        body = _b64decode(encoded)
        expected_signature = hmac.new(
            verification_key, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return STATUS_INVALID_SIGNATURE
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != RECEIPT_KEYS:
            return STATUS_INVALID_PAYLOAD
        if payload["version"] != 1 or payload["verdict"] != "passed":
            return STATUS_INVALID_VERDICT
        for field in ("flag_id", "outcome", "evidence"):
            if payload[field] != contract[field]:
                return STATUS_WRONG_OBJECTIVE
        for field in ("range_instance", "participant"):
            if payload[field] != binding[field]:
                return STATUS_CROSS_NAMESPACE
        if payload["reset_generation"] != binding["reset_generation"]:
            return STATUS_STALE_RESET_GENERATION
        issued_at = payload["issued_at"]
        expires_at = payload["expires_at"]
        if not isinstance(issued_at, int) or not isinstance(expires_at, int):
            return STATUS_INVALID_TIMESTAMP
        if now < issued_at:
            return STATUS_NOT_YET_VALID
        if now >= expires_at:
            return STATUS_EXPIRED_RECEIPT
        return STATUS_PASSED
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return STATUS_INVALID_FORMAT


def verify_receipt(receipt: str, *, contract: dict[str, Any],
                   binding: dict[str, Any], verification_key: bytes,
                   now: int) -> bool:
    """Fail closed unless a signed receipt matches contract, namespace, and reset."""
    return verify_receipt_status(
        receipt,
        contract=contract,
        binding=binding,
        verification_key=verification_key,
        now=now,
    ) == STATUS_PASSED
