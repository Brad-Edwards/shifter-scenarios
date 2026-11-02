"""Notify Cinder Typhoon winners and manage numbered prize-pack claims."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import secrets
import sqlite3
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prize_inputs = _load_module(
    "cinder_prize_inputs_claims", ROOT / "ctfd" / "prize_inputs.py"
)
prize_evaluator = _load_module(
    "cinder_prize_evaluator_claims", ROOT / "ctfd" / "prize_evaluator.py"
)
prize_nominations = _load_module(
    "cinder_prize_nominations_claims", ROOT / "ctfd" / "prize_nominations.py"
)

AuthenticatedParticipant = prize_nominations.AuthenticatedParticipant
CONFIG_CONTRACT = "cinder-typhoon.prize-claim-config/v1"
NOTIFICATION_CONTRACT = "cinder-typhoon.prize-notification/v1"
PARTICIPANT_CONTRACT = "cinder-typhoon.participant-prize/v1"
CLAIM_RECEIPT_CONTRACT = "cinder-typhoon.prize-claim-receipt/v1"
TOKEN_DOMAIN = b"cinder-typhoon/prize-claim-token/v1"
TOKEN_KEY_DOMAIN = b"cinder-typhoon/prize-claim-token-key/v1"
REQUEST_DOMAIN = b"cinder-typhoon/prize-claim-request/v1"
DEFAULT_TOKEN_TTL_SECONDS = 600
RELEASE_LEASE_SECONDS = 300
MAX_REASON_LENGTH = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_event (
    event_id TEXT PRIMARY KEY,
    config_digest TEXT NOT NULL,
    token_key_commitment TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    public_origin TEXT NOT NULL,
    claim_deadline_at TEXT NOT NULL,
    finalize_at TEXT NOT NULL,
    token_ttl_seconds INTEGER NOT NULL CHECK (token_ttl_seconds > 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES event_binding(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_participant (
    event_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    public_alias TEXT NOT NULL,
    PRIMARY KEY (event_id, participant_id),
    FOREIGN KEY (event_id) REFERENCES claim_event(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_slot (
    event_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    award_name TEXT NOT NULL,
    PRIMARY KEY (event_id, slot_id),
    FOREIGN KEY (event_id, slot_id) REFERENCES prize_slot(event_id, slot_id)
) STRICT;

CREATE TABLE IF NOT EXISTS prize_pack (
    event_id TEXT NOT NULL,
    pack_number INTEGER NOT NULL CHECK (pack_number > 0),
    status TEXT NOT NULL CHECK (status IN ('available', 'claimed', 'corrected_out')),
    slot_id TEXT,
    generation INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (event_id, pack_number),
    FOREIGN KEY (event_id) REFERENCES claim_event(event_id),
    FOREIGN KEY (event_id, slot_id, generation)
        REFERENCES allocation_attempt(event_id, slot_id, generation)
) STRICT;

CREATE TABLE IF NOT EXISTS notification_intent (
    event_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    participant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    award_name TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'releasing', 'delivered', 'failed', 'voided')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    delivery_reference TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (event_id, slot_id, generation),
    UNIQUE (event_id, idempotency_key),
    FOREIGN KEY (event_id, slot_id, generation)
        REFERENCES allocation_attempt(event_id, slot_id, generation),
    FOREIGN KEY (event_id, participant_id)
        REFERENCES claim_participant(event_id, participant_id)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_token (
    event_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    token_digest TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    participant_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    used_at TEXT,
    PRIMARY KEY (event_id, token_id),
    UNIQUE (event_id, token_digest),
    FOREIGN KEY (event_id, slot_id, generation)
        REFERENCES allocation_attempt(event_id, slot_id, generation)
) STRICT;

CREATE TABLE IF NOT EXISTS prize_claim (
    event_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    participant_id TEXT NOT NULL,
    pack_number INTEGER NOT NULL,
    claimed_at TEXT NOT NULL,
    staff_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    response_json TEXT NOT NULL,
    PRIMARY KEY (event_id, claim_id),
    UNIQUE (event_id, slot_id, generation),
    UNIQUE (event_id, participant_id),
    UNIQUE (event_id, pack_number),
    UNIQUE (event_id, request_id),
    FOREIGN KEY (event_id, slot_id, generation)
        REFERENCES allocation_attempt(event_id, slot_id, generation),
    FOREIGN KEY (event_id, pack_number) REFERENCES prize_pack(event_id, pack_number)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_deadline_run (
    event_id TEXT PRIMARY KEY,
    occurrence_id TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    result_json TEXT NOT NULL,
    result_digest TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES claim_event(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS allocation_void_action (
    event_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    reason TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    response_json TEXT NOT NULL,
    PRIMARY KEY (event_id, request_id),
    FOREIGN KEY (event_id, slot_id, generation)
        REFERENCES allocation_attempt(event_id, slot_id, generation)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_correction (
    event_id TEXT NOT NULL,
    correction_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    from_pack_number INTEGER NOT NULL,
    to_pack_number INTEGER NOT NULL,
    reason TEXT NOT NULL,
    staff_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    response_json TEXT NOT NULL,
    PRIMARY KEY (event_id, correction_id),
    UNIQUE (event_id, request_id),
    FOREIGN KEY (event_id, claim_id) REFERENCES prize_claim(event_id, claim_id)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_audit (
    audit_id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    slot_id TEXT,
    generation INTEGER,
    pack_number INTEGER,
    request_id TEXT,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES claim_event(event_id)
) STRICT;
"""


class PrizeClaimError(ValueError):
    """Notification, inventory, or claim state cannot be changed safely."""


@dataclass(frozen=True)
class AuthenticatedEventStaff:
    """Authority facts supplied by the approved event-staff integration."""

    event_id: str
    staff_id: str
    can_manage_prizes: bool
    is_event_admin: bool
    origin: str


def _frame(parts: Iterable[bytes]) -> bytes:
    result = bytearray()
    for part in parts:
        result.extend(len(part).to_bytes(4, "big"))
        result.extend(part)
    return bytes(result)


def _uuid_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PrizeClaimError(f"{label} must be a UUID")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise PrizeClaimError(f"{label} must be a UUID") from error


def _utc(value: Any, label: str) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise PrizeClaimError(f"{label} must be a UTC timestamp") from error
    else:
        raise PrizeClaimError(f"{label} must be a UTC timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise PrizeClaimError(f"{label} must be a UTC timestamp")
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _origin(value: Any) -> str:
    if not isinstance(value, str):
        raise PrizeClaimError("public origin must be an HTTPS origin")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise PrizeClaimError("public origin must be an HTTPS origin")
    return f"https://{parsed.netloc}"


def _reason(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_REASON_LENGTH
    ):
        raise PrizeClaimError("reason is required and must be at most 500 characters")
    return value.strip()


def _award_name(policy: dict[str, Any], slot: dict[str, Any]) -> str:
    family = slot["family"]
    scope = slot["scope"]
    if family == "overall_leaders":
        return "Overall Leader"
    if family == "stage_completion":
        return f"First to Finish: {policy['stages'][scope]['title']}"
    if family == "bounties":
        return f"Golden Solve: {slot['slot_id'].removeprefix('bounty-').upper()}"
    if family == "stage_draws":
        return f"Stage Drawing: {policy['stages'][scope]['title']}"
    if family == "passport_draw":
        return "Three-Stage Passport"
    if family == "good_citizen":
        return "Good Citizen"
    raise PrizeClaimError("unknown prize slot family")


def build_claim_config(
    *,
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    public_origin: str,
    token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> dict[str, Any]:
    """Bind aliases, public award names, inventory, and claim cutoffs."""

    try:
        prize_inputs.validate_prize_input(policy, snapshot)
    except prize_inputs.PrizeInputError as error:
        raise PrizeClaimError(str(error)) from error
    if type(token_ttl_seconds) is not int or not 60 <= token_ttl_seconds <= 3600:
        raise PrizeClaimError("claim token TTL must be between 60 and 3600 seconds")
    slots = prize_evaluator._policy_slots(policy)
    boundaries = snapshot["event"]["boundaries"]
    return {
        "contract": CONFIG_CONTRACT,
        "event_id": snapshot["event"]["event_id"],
        "policy_digest": snapshot["event"]["policy_digest"],
        "content_bundle_digest": snapshot["event"]["content_bundle_digest"],
        "public_origin": _origin(public_origin),
        "claim_deadline_at": boundaries["claim_deadline_at"],
        "finalize_at": boundaries["finalize_at"],
        "token_ttl_seconds": token_ttl_seconds,
        "inventory": list(range(1, 51)),
        "participants": [
            {
                "participant_id": row["participant_id"],
                "public_alias": row["public_alias"],
            }
            for row in snapshot["participants"]
            if row["prize_eligible"]
        ],
        "slots": [
            {
                "slot_id": slot["slot_id"],
                "award_name": _award_name(policy, slot),
            }
            for slot in slots
        ],
    }


def _validate_config(config: Any) -> dict[str, Any]:
    fields = {
        "contract",
        "event_id",
        "policy_digest",
        "content_bundle_digest",
        "public_origin",
        "claim_deadline_at",
        "finalize_at",
        "token_ttl_seconds",
        "inventory",
        "participants",
        "slots",
    }
    if not isinstance(config, dict) or set(config) != fields:
        raise PrizeClaimError("claim config has invalid fields")
    if config["contract"] != CONFIG_CONTRACT:
        raise PrizeClaimError("claim config contract is invalid")
    event_id = _uuid_text(config["event_id"], "config.event_id")
    deadline_text, deadline = _utc(config["claim_deadline_at"], "claim deadline")
    finalize_text, finalize = _utc(config["finalize_at"], "finalize time")
    if deadline > finalize:
        raise PrizeClaimError("claim deadline must not follow finalization")
    ttl = config["token_ttl_seconds"]
    if type(ttl) is not int or not 60 <= ttl <= 3600:
        raise PrizeClaimError("claim token TTL is invalid")
    inventory = config["inventory"]
    if inventory != list(range(1, 51)):
        raise PrizeClaimError(
            "claim inventory must contain numbered packs 1 through 50"
        )
    for name in ("policy_digest", "content_bundle_digest"):
        value = config[name]
        if not isinstance(value, str) or not prize_inputs.SHA256.fullmatch(value):
            raise PrizeClaimError(f"config.{name} is invalid")
    participants = _closed_rows(
        config["participants"], {"participant_id", "public_alias"}, "participant"
    )
    participant_map: dict[str, str] = {}
    for row in participants:
        participant_id = _uuid_text(row["participant_id"], "participant_id")
        alias = row["public_alias"]
        if not isinstance(alias, str) or not alias or len(alias) > 100:
            raise PrizeClaimError("participant public alias is invalid")
        if (
            participant_id in participant_map
            and participant_map[participant_id] != alias
        ):
            raise PrizeClaimError("participant identity has conflicting aliases")
        participant_map[participant_id] = alias
    slots = _closed_rows(config["slots"], {"slot_id", "award_name"}, "slot")
    slot_map: dict[str, str] = {}
    for row in slots:
        slot_id = row["slot_id"]
        award_name = row["award_name"]
        if (
            not isinstance(slot_id, str)
            or not slot_id
            or not isinstance(award_name, str)
            or not award_name
            or len(award_name) > 120
        ):
            raise PrizeClaimError("claim slot metadata is invalid")
        if slot_id in slot_map and slot_map[slot_id] != award_name:
            raise PrizeClaimError("claim slot identity has conflicting names")
        slot_map[slot_id] = award_name
    if len(slot_map) != 50:
        raise PrizeClaimError("claim config must contain exactly 50 slots")
    return {
        **config,
        "event_id": event_id,
        "public_origin": _origin(config["public_origin"]),
        "claim_deadline_at": deadline_text,
        "finalize_at": finalize_text,
        "participants": [
            {"participant_id": key, "public_alias": participant_map[key]}
            for key in sorted(participant_map, key=lambda value: UUID(value).bytes)
        ],
        "slots": [
            {"slot_id": key, "award_name": slot_map[key]} for key in sorted(slot_map)
        ],
    }


def _closed_rows(value: Any, fields: set[str], label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise PrizeClaimError(f"claim {label}s must be a list")
    result = []
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != fields:
            raise PrizeClaimError(f"claim {label} {index} has invalid fields")
        result.append(row)
    return result


def _connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise PrizeClaimError("evaluator state must exist before claim setup")
    if path.is_symlink():
        raise PrizeClaimError("claim state path must not be a symbolic link")
    os.chmod(path, 0o600)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    required_tables = {"event_binding", "prize_slot", "allocation_attempt"}
    present_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if not required_tables.issubset(present_tables):
        connection.close()
        raise PrizeClaimError("claim state is not an evaluator database")
    connection.executescript(SCHEMA)
    return connection


class PrizeClaimService:
    """Transactional notification, numbered inventory, and claim service."""

    def __init__(
        self, *, config: dict[str, Any], state_path: Path, token_key: bytes
    ) -> None:
        self.config = _validate_config(config)
        if not isinstance(token_key, bytes) or len(token_key) != 32:
            raise PrizeClaimError("claim token key must contain exactly 32 bytes")
        self.state_path = state_path
        self._token_key = token_key
        self._participants = {
            row["participant_id"]: row["public_alias"]
            for row in self.config["participants"]
        }
        self._slot_names = {
            row["slot_id"]: row["award_name"] for row in self.config["slots"]
        }
        self._bind_state()

    @property
    def event_id(self) -> str:
        return self.config["event_id"]

    def _bind_state(self) -> None:
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            evaluator_binding = connection.execute(
                "SELECT policy_digest, content_digest FROM event_binding WHERE event_id = ?",
                (self.event_id,),
            ).fetchone()
            if evaluator_binding is None or tuple(evaluator_binding) != (
                self.config["policy_digest"],
                self.config["content_bundle_digest"],
            ):
                raise PrizeClaimError(
                    "claim config differs from evaluator event binding"
                )
            config_digest = prize_inputs.artifact_digest(self.config)
            key_commitment = (
                "sha256:"
                + hashlib.sha256(
                    TOKEN_KEY_DOMAIN
                    + _frame((UUID(self.event_id).bytes, self._token_key))
                ).hexdigest()
            )
            expected = (
                config_digest,
                key_commitment,
                self.config["policy_digest"],
                self.config["content_bundle_digest"],
                self.config["public_origin"],
                self.config["claim_deadline_at"],
                self.config["finalize_at"],
                self.config["token_ttl_seconds"],
            )
            stored = connection.execute(
                "SELECT config_digest, token_key_commitment, policy_digest, content_digest, "
                "public_origin, claim_deadline_at, finalize_at, token_ttl_seconds "
                "FROM claim_event WHERE event_id = ?",
                (self.event_id,),
            ).fetchone()
            if stored is None:
                connection.execute(
                    "INSERT INTO claim_event "
                    "(event_id, config_digest, token_key_commitment, policy_digest, "
                    "content_digest, public_origin, claim_deadline_at, finalize_at, "
                    "token_ttl_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.event_id, *expected, self.config["claim_deadline_at"]),
                )
                connection.executemany(
                    "INSERT INTO claim_participant "
                    "(event_id, participant_id, public_alias) VALUES (?, ?, ?)",
                    [
                        (self.event_id, row["participant_id"], row["public_alias"])
                        for row in self.config["participants"]
                    ],
                )
                connection.executemany(
                    "INSERT INTO claim_slot (event_id, slot_id, award_name) VALUES (?, ?, ?)",
                    [
                        (self.event_id, row["slot_id"], row["award_name"])
                        for row in self.config["slots"]
                    ],
                )
                connection.executemany(
                    "INSERT INTO prize_pack "
                    "(event_id, pack_number, status, updated_at) VALUES (?, ?, 'available', ?)",
                    [
                        (self.event_id, number, self.config["claim_deadline_at"])
                        for number in self.config["inventory"]
                    ],
                )
            elif tuple(stored) != expected:
                raise PrizeClaimError(
                    "claim state is bound to a different config or token key"
                )
            self._verify_projection(connection)
            connection.commit()
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("claim state binding failed closed") from error
        finally:
            connection.close()

    def _verify_projection(self, connection: sqlite3.Connection) -> None:
        participants = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT participant_id, public_alias FROM claim_participant WHERE event_id = ?",
                (self.event_id,),
            )
        }
        slots = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT slot_id, award_name FROM claim_slot WHERE event_id = ?",
                (self.event_id,),
            )
        }
        packs = [
            row[0]
            for row in connection.execute(
                "SELECT pack_number FROM prize_pack WHERE event_id = ? ORDER BY pack_number",
                (self.event_id,),
            )
        ]
        if (
            participants != self._participants
            or slots != self._slot_names
            or packs != list(range(1, 51))
        ):
            raise PrizeClaimError("persisted claim projection differs from config")

    def _participant(self, context: AuthenticatedParticipant) -> str:
        if not isinstance(context, AuthenticatedParticipant):
            raise PrizeClaimError("authenticated participant context is required")
        if _uuid_text(context.event_id, "context.event_id") != self.event_id:
            raise PrizeClaimError("participant context belongs to another event")
        participant_id = _uuid_text(context.participant_id, "context.participant_id")
        if participant_id not in self._participants:
            raise PrizeClaimError("participant is not eligible for this event")
        if not isinstance(context.session_id, str) or not context.session_id:
            raise PrizeClaimError("authenticated session is invalid")
        if _origin(context.origin) != self.config["public_origin"]:
            raise PrizeClaimError("request origin is not allowed")
        return participant_id

    def _staff(self, context: AuthenticatedEventStaff, *, admin: bool = False) -> str:
        if not isinstance(context, AuthenticatedEventStaff):
            raise PrizeClaimError("authenticated event-staff context is required")
        if _uuid_text(context.event_id, "staff.event_id") != self.event_id:
            raise PrizeClaimError("staff context belongs to another event")
        if (
            not isinstance(context.staff_id, str)
            or not context.staff_id
            or len(context.staff_id) > 128
            or not context.can_manage_prizes
            or (admin and not context.is_event_admin)
        ):
            raise PrizeClaimError("event staff lacks prize authority")
        if _origin(context.origin) != self.config["public_origin"]:
            raise PrizeClaimError("staff request origin is not allowed")
        return context.staff_id

    def sync_allocations(self, *, now: datetime | str | None = None) -> int:
        """Create one stable notification intent for each live allocation."""

        current_text, _current = _utc(now or datetime.now(UTC), "server time")
        connection = _connect(self.state_path)
        created = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT attempt.slot_id, attempt.generation, attempt.participant_id, "
                "attempt.status, attempt.selected_at, slot.award_name "
                "FROM allocation_attempt AS attempt "
                "JOIN claim_slot AS slot ON slot.event_id = attempt.event_id "
                "AND slot.slot_id = attempt.slot_id WHERE attempt.event_id = ?",
                (self.event_id,),
            ).fetchall()
            for row in rows:
                intent = connection.execute(
                    "SELECT state FROM notification_intent "
                    "WHERE event_id = ? AND slot_id = ? AND generation = ?",
                    (self.event_id, row["slot_id"], row["generation"]),
                ).fetchone()
                if row["status"] == "voided":
                    if intent is not None and intent["state"] != "voided":
                        if connection.execute(
                            "SELECT 1 FROM prize_claim WHERE event_id = ? AND slot_id = ? "
                            "AND generation = ?",
                            (self.event_id, row["slot_id"], row["generation"]),
                        ).fetchone():
                            raise PrizeClaimError("claimed allocation cannot be voided")
                        connection.execute(
                            "UPDATE notification_intent SET state = 'voided', updated_at = ? "
                            "WHERE event_id = ? AND slot_id = ? AND generation = ?",
                            (
                                current_text,
                                self.event_id,
                                row["slot_id"],
                                row["generation"],
                            ),
                        )
                        self._revoke_tokens(
                            connection,
                            row["slot_id"],
                            row["generation"],
                            current_text,
                        )
                    continue
                if intent is None:
                    idempotency_key = f"event-prize:{self.event_id}:{row['slot_id']}:{row['generation']}"
                    connection.execute(
                        "INSERT INTO notification_intent "
                        "(event_id, slot_id, generation, participant_id, idempotency_key, "
                        "award_name, state, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                        (
                            self.event_id,
                            row["slot_id"],
                            row["generation"],
                            row["participant_id"],
                            idempotency_key,
                            row["award_name"],
                            row["selected_at"],
                            current_text,
                        ),
                    )
                    created += 1
            connection.commit()
            return created
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("allocation synchronization failed closed") from error
        finally:
            connection.close()

    def release_notifications(
        self,
        deliver: Callable[[dict[str, Any]], str | None],
        *,
        now: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        """Release pending intents through the approved communication adapter."""

        current_text, current = _utc(now or datetime.now(UTC), "server time")
        self.sync_allocations(now=current_text)
        results = []
        connection = _connect(self.state_path)
        try:
            stale = _utc(
                current - timedelta(seconds=RELEASE_LEASE_SECONDS), "lease cutoff"
            )[0]
            candidates = [
                (row["slot_id"], row["generation"])
                for row in connection.execute(
                    "SELECT slot_id, generation FROM notification_intent "
                    "WHERE event_id = ? AND (state IN ('pending', 'failed') "
                    "OR (state = 'releasing' AND updated_at < ?)) "
                    "ORDER BY created_at, slot_id",
                    (self.event_id, stale),
                )
            ]
        finally:
            connection.close()
        for slot_id, generation in candidates:
            leased = self._lease_notification(
                current_text,
                current,
                slot_id=slot_id,
                generation=generation,
            )
            if leased is None:
                continue
            message = {
                "contract": NOTIFICATION_CONTRACT,
                "idempotency_key": leased["idempotency_key"],
                "recipient_participant_id": leased["participant_id"],
                "template": "event_prize_selected",
                "variables": {
                    "award_name": leased["award_name"],
                    "claim_status": "ready",
                    "participant_path": f"/events/{self.event_id}/prize",
                },
            }
            try:
                reference = deliver(message)
                if reference is not None and (
                    not isinstance(reference, str) or len(reference) > 200
                ):
                    raise PrizeClaimError(
                        "communication adapter returned an invalid reference"
                    )
            except Exception as error:  # noqa: BLE001 - adapter failures must be retried
                self._finish_notification(
                    leased,
                    state="failed",
                    current_text=current_text,
                    reference=None,
                    error_code=type(error).__name__[:100],
                )
                results.append(
                    {
                        "idempotency_key": leased["idempotency_key"],
                        "state": "failed",
                    }
                )
            else:
                self._finish_notification(
                    leased,
                    state="delivered",
                    current_text=current_text,
                    reference=reference,
                    error_code=None,
                )
                results.append(
                    {
                        "idempotency_key": leased["idempotency_key"],
                        "state": "delivered",
                    }
                )
        return results

    def _lease_notification(
        self,
        current_text: str,
        current: datetime,
        *,
        slot_id: str,
        generation: int,
    ) -> dict[str, Any] | None:
        stale = _utc(
            current - timedelta(seconds=RELEASE_LEASE_SECONDS), "lease cutoff"
        )[0]
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT event_id, slot_id, generation, participant_id, idempotency_key, "
                "award_name FROM notification_intent WHERE event_id = ? "
                "AND slot_id = ? AND generation = ? AND (state IN ('pending', 'failed') "
                "OR (state = 'releasing' AND updated_at < ?))",
                (self.event_id, slot_id, generation, stale),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            updated = connection.execute(
                "UPDATE notification_intent SET state = 'releasing', "
                "attempt_count = attempt_count + 1, updated_at = ?, last_error_code = NULL "
                "WHERE event_id = ? AND slot_id = ? AND generation = ? "
                "AND (state IN ('pending', 'failed') "
                "OR (state = 'releasing' AND updated_at < ?))",
                (
                    current_text,
                    self.event_id,
                    row["slot_id"],
                    row["generation"],
                    stale,
                ),
            ).rowcount
            if updated != 1:
                connection.commit()
                return None
            connection.commit()
            return dict(row)
        except sqlite3.Error as error:
            connection.rollback()
            raise PrizeClaimError("notification lease failed closed") from error
        finally:
            connection.close()

    def _finish_notification(
        self,
        leased: dict[str, Any],
        *,
        state: str,
        current_text: str,
        reference: str | None,
        error_code: str | None,
    ) -> None:
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE notification_intent SET state = ?, delivery_reference = ?, "
                "last_error_code = ?, updated_at = ? WHERE event_id = ? AND slot_id = ? "
                "AND generation = ? AND state = 'releasing'",
                (
                    state,
                    reference,
                    error_code,
                    current_text,
                    self.event_id,
                    leased["slot_id"],
                    leased["generation"],
                ),
            ).rowcount
            if updated != 1:
                raise PrizeClaimError("notification lease is no longer active")
            connection.commit()
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("notification completion failed closed") from error
        finally:
            connection.close()

    def participant_prize(
        self,
        context: AuthenticatedParticipant,
        *,
        issue_code: bool = False,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Return only the authenticated participant's award and claim state."""

        participant_id = self._participant(context)
        current_text, current = _utc(now or datetime.now(UTC), "server time")
        self.sync_allocations(now=current_text)
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            allocation = connection.execute(
                "SELECT attempt.slot_id, attempt.generation, attempt.selected_at, "
                "intent.award_name, intent.state AS notification_state "
                "FROM allocation_attempt AS attempt JOIN notification_intent AS intent "
                "ON intent.event_id = attempt.event_id AND intent.slot_id = attempt.slot_id "
                "AND intent.generation = attempt.generation WHERE attempt.event_id = ? "
                "AND attempt.participant_id = ? AND attempt.status = 'selected'",
                (self.event_id, participant_id),
            ).fetchone()
            if allocation is None:
                raise PrizeClaimError("participant has no active prize allocation")
            claim = connection.execute(
                "SELECT claim_id, claimed_at FROM prize_claim WHERE event_id = ? "
                "AND slot_id = ? AND generation = ?",
                (self.event_id, allocation["slot_id"], allocation["generation"]),
            ).fetchone()
            pack = connection.execute(
                "SELECT pack_number FROM prize_pack WHERE event_id = ? AND slot_id = ? "
                "AND generation = ? AND status = 'claimed'",
                (self.event_id, allocation["slot_id"], allocation["generation"]),
            ).fetchone()
            response: dict[str, Any] = {
                "contract": PARTICIPANT_CONTRACT,
                "award_name": allocation["award_name"],
                "notification_state": allocation["notification_state"],
                "claim_status": "claimed" if claim is not None else "ready",
                "pack_number": pack["pack_number"] if pack is not None else None,
                "claimed_at": claim["claimed_at"] if claim is not None else None,
                "claim_code": None,
                "qr_payload": None,
                "expires_at": None,
            }
            if claim is None and issue_code:
                expiry = self._token_expiry(allocation["selected_at"], current)
                if expiry <= current:
                    response["claim_status"] = "expired"
                else:
                    self._revoke_tokens(
                        connection,
                        allocation["slot_id"],
                        allocation["generation"],
                        current_text,
                    )
                    raw_token = secrets.token_urlsafe(24)
                    digest = self._token_digest(raw_token)
                    expires_at = _utc(expiry, "token expiry")[0]
                    connection.execute(
                        "INSERT INTO claim_token "
                        "(event_id, token_id, token_digest, slot_id, generation, "
                        "participant_id, issued_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            self.event_id,
                            str(uuid4()),
                            digest,
                            allocation["slot_id"],
                            allocation["generation"],
                            participant_id,
                            current_text,
                            expires_at,
                        ),
                    )
                    response.update(
                        {
                            "claim_code": raw_token,
                            "qr_payload": f"cinder-prize:v1:{self.event_id}:{raw_token}",
                            "expires_at": expires_at,
                        }
                    )
            connection.commit()
            return response
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("participant prize view failed closed") from error
        finally:
            connection.close()

    def _token_expiry(self, selected_at: str, current: datetime) -> datetime:
        ttl_expiry = current + timedelta(seconds=self.config["token_ttl_seconds"])
        selected = _utc(selected_at, "allocation selected_at")[1]
        finalize = _utc(self.config["finalize_at"], "finalize_at")[1]
        if selected >= finalize:
            return ttl_expiry
        deadline = _utc(self.config["claim_deadline_at"], "claim deadline")[1]
        return min(ttl_expiry, deadline)

    def _token_digest(self, raw_token: str) -> str:
        digest = hmac.new(
            self._token_key,
            TOKEN_DOMAIN + _frame((UUID(self.event_id).bytes, raw_token.encode())),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256:{digest}"

    def _revoke_tokens(
        self,
        connection: sqlite3.Connection,
        slot_id: str,
        generation: int,
        revoked_at: str,
    ) -> None:
        connection.execute(
            "UPDATE claim_token SET revoked_at = ? WHERE event_id = ? AND slot_id = ? "
            "AND generation = ? AND revoked_at IS NULL AND used_at IS NULL",
            (revoked_at, self.event_id, slot_id, generation),
        )

    def claim(
        self,
        staff: AuthenticatedEventStaff,
        *,
        claim_code: str,
        pack_number: int,
        request_id: str,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Atomically claim one unused numbered pack with a live opaque code."""

        staff_id = self._staff(staff)
        current_text, current = _utc(now or datetime.now(UTC), "server time")
        request_id = _uuid_text(request_id, "claim request_id")
        if type(pack_number) is not int or pack_number not in range(1, 51):
            raise PrizeClaimError("pack number must be between 1 and 50")
        raw_token = self._raw_claim_token(claim_code)
        token_digest = self._token_digest(raw_token)
        request_digest = self._request_digest(
            "claim", request_id, token_digest, str(pack_number)
        )
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT request_digest, response_json FROM prize_claim "
                "WHERE event_id = ? AND request_id = ?",
                (self.event_id, request_id),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise PrizeClaimError(
                        "claim request identity was reused with different input"
                    )
                connection.commit()
                return json.loads(existing["response_json"])
            token = connection.execute(
                "SELECT slot_id, generation, participant_id, expires_at, revoked_at, used_at "
                "FROM claim_token WHERE event_id = ? AND token_digest = ?",
                (self.event_id, token_digest),
            ).fetchone()
            if (
                token is None
                or token["revoked_at"] is not None
                or token["used_at"] is not None
                or current >= _utc(token["expires_at"], "token expires_at")[1]
            ):
                raise PrizeClaimError("claim code is invalid or expired")
            allocation = connection.execute(
                "SELECT status FROM allocation_attempt WHERE event_id = ? AND slot_id = ? "
                "AND generation = ? AND participant_id = ?",
                (
                    self.event_id,
                    token["slot_id"],
                    token["generation"],
                    token["participant_id"],
                ),
            ).fetchone()
            if allocation is None or allocation["status"] != "selected":
                raise PrizeClaimError("claim allocation is no longer active")
            pack = connection.execute(
                "SELECT status FROM prize_pack WHERE event_id = ? AND pack_number = ?",
                (self.event_id, pack_number),
            ).fetchone()
            if pack is None or pack["status"] != "available":
                raise PrizeClaimError("prize pack is already used")
            claim_id = str(uuid4())
            response = {
                "contract": CLAIM_RECEIPT_CONTRACT,
                "claim_id": claim_id,
                "award_name": self._slot_names[token["slot_id"]],
                "participant_alias": self._participants[token["participant_id"]],
                "pack_number": pack_number,
                "claimed_at": current_text,
            }
            response_json = (
                prize_inputs.canonical_json_bytes(response).decode().rstrip("\n")
            )
            connection.execute(
                "INSERT INTO prize_claim "
                "(event_id, claim_id, slot_id, generation, participant_id, pack_number, "
                "claimed_at, staff_id, request_id, request_digest, response_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.event_id,
                    claim_id,
                    token["slot_id"],
                    token["generation"],
                    token["participant_id"],
                    pack_number,
                    current_text,
                    staff_id,
                    request_id,
                    request_digest,
                    response_json,
                ),
            )
            connection.execute(
                "UPDATE prize_pack SET status = 'claimed', slot_id = ?, generation = ?, "
                "updated_at = ? WHERE event_id = ? AND pack_number = ?",
                (
                    token["slot_id"],
                    token["generation"],
                    current_text,
                    self.event_id,
                    pack_number,
                ),
            )
            connection.execute(
                "UPDATE claim_token SET used_at = ? WHERE event_id = ? AND token_digest = ?",
                (current_text, self.event_id, token_digest),
            )
            self._audit(
                connection,
                actor_id=staff_id,
                action="claim_pack",
                outcome="claimed",
                slot_id=token["slot_id"],
                generation=token["generation"],
                pack_number=pack_number,
                request_id=request_id,
                occurred_at=current_text,
            )
            connection.commit()
            return response
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("prize claim failed closed") from error
        finally:
            connection.close()

    def _raw_claim_token(self, value: Any) -> str:
        if not isinstance(value, str) or not value:
            raise PrizeClaimError("claim code is invalid")
        prefix = f"cinder-prize:v1:{self.event_id}:"
        raw = value.removeprefix(prefix)
        if not raw or len(raw) > 200:
            raise PrizeClaimError("claim code is invalid")
        return raw

    def _request_digest(self, *parts: str) -> str:
        payload = _frame(part.encode() for part in (self.event_id, *parts))
        return f"sha256:{hashlib.sha256(REQUEST_DOMAIN + payload).hexdigest()}"

    def void_unclaimed(
        self,
        staff: AuthenticatedEventStaff,
        *,
        slot_id: str,
        generation: int,
        reason: str,
        request_id: str,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Void an unclaimed allocation with an event-admin reason."""

        staff_id = self._staff(staff, admin=True)
        reason = _reason(reason)
        request_id = _uuid_text(request_id, "void request_id")
        current_text, _current = _utc(now or datetime.now(UTC), "server time")
        if (
            slot_id not in self._slot_names
            or type(generation) is not int
            or generation < 1
        ):
            raise PrizeClaimError("void allocation identity is invalid")
        request_digest = self._request_digest(
            "void", request_id, slot_id, str(generation), reason
        )
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT request_digest, response_json FROM allocation_void_action "
                "WHERE event_id = ? AND request_id = ?",
                (self.event_id, request_id),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise PrizeClaimError(
                        "void request identity was reused with different input"
                    )
                connection.commit()
                return json.loads(existing["response_json"])
            if connection.execute(
                "SELECT 1 FROM prize_claim WHERE event_id = ? AND slot_id = ? AND generation = ?",
                (self.event_id, slot_id, generation),
            ).fetchone():
                raise PrizeClaimError("claimed allocation cannot be voided")
            updated = connection.execute(
                "UPDATE allocation_attempt SET status = 'voided', voided_at = ?, "
                "void_reason = ? WHERE event_id = ? "
                "AND slot_id = ? AND generation = ? AND status = 'selected'",
                (current_text, reason, self.event_id, slot_id, generation),
            ).rowcount
            if updated != 1:
                raise PrizeClaimError("allocation is not live and unclaimed")
            connection.execute(
                "UPDATE notification_intent SET state = 'voided', updated_at = ? "
                "WHERE event_id = ? AND slot_id = ? AND generation = ?",
                (current_text, self.event_id, slot_id, generation),
            )
            self._revoke_tokens(connection, slot_id, generation, current_text)
            response = {
                "slot_id": slot_id,
                "generation": generation,
                "state": "voided",
                "reason": reason,
                "voided_at": current_text,
            }
            response_json = (
                prize_inputs.canonical_json_bytes(response).decode().rstrip("\n")
            )
            connection.execute(
                "INSERT INTO allocation_void_action "
                "(event_id, request_id, slot_id, generation, reason, request_digest, "
                "occurred_at, response_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.event_id,
                    request_id,
                    slot_id,
                    generation,
                    reason,
                    request_digest,
                    current_text,
                    response_json,
                ),
            )
            self._audit(
                connection,
                actor_id=staff_id,
                action="void_allocation",
                outcome="voided",
                slot_id=slot_id,
                generation=generation,
                pack_number=None,
                request_id=request_id,
                occurred_at=current_text,
            )
            connection.commit()
            return response
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("allocation void failed closed") from error
        finally:
            connection.close()

    def expire_unclaimed(
        self,
        *,
        occurrence_id: str,
        executed_at: datetime | str,
    ) -> dict[str, Any]:
        """Idempotently void every unclaimed pre-finalization allocation."""

        occurrence_id = _uuid_text(occurrence_id, "claim deadline occurrence_id")
        executed_text, executed = _utc(executed_at, "claim deadline executed_at")
        deadline = _utc(self.config["claim_deadline_at"], "claim deadline")[1]
        finalize = _utc(self.config["finalize_at"], "finalize_at")[1]
        if executed < deadline or executed >= finalize:
            raise PrizeClaimError(
                "claim deadline occurrence must execute from its boundary before finalization"
            )
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT occurrence_id, executed_at, result_json FROM claim_deadline_run "
                "WHERE event_id = ?",
                (self.event_id,),
            ).fetchone()
            if existing is not None:
                if (existing["occurrence_id"], existing["executed_at"]) != (
                    occurrence_id,
                    executed_text,
                ):
                    raise PrizeClaimError("claim deadline occurrence identity changed")
                connection.commit()
                return json.loads(existing["result_json"])
            rows = connection.execute(
                "SELECT attempt.slot_id, attempt.generation FROM allocation_attempt AS attempt "
                "LEFT JOIN prize_claim AS claim ON claim.event_id = attempt.event_id "
                "AND claim.slot_id = attempt.slot_id AND claim.generation = attempt.generation "
                "WHERE attempt.event_id = ? AND attempt.status = 'selected' "
                "AND attempt.selected_at < ? AND claim.claim_id IS NULL",
                (self.event_id, _utc(finalize, "finalize_at")[0]),
            ).fetchall()
            voided = []
            for row in rows:
                connection.execute(
                    "UPDATE allocation_attempt SET status = 'voided', voided_at = ?, "
                    "void_reason = 'claim deadline expired' WHERE event_id = ? "
                    "AND slot_id = ? AND generation = ? AND status = 'selected'",
                    (
                        executed_text,
                        self.event_id,
                        row["slot_id"],
                        row["generation"],
                    ),
                )
                connection.execute(
                    "UPDATE notification_intent SET state = 'voided', updated_at = ? "
                    "WHERE event_id = ? AND slot_id = ? AND generation = ?",
                    (
                        executed_text,
                        self.event_id,
                        row["slot_id"],
                        row["generation"],
                    ),
                )
                self._revoke_tokens(
                    connection,
                    row["slot_id"],
                    row["generation"],
                    executed_text,
                )
                voided.append(
                    {"slot_id": row["slot_id"], "generation": row["generation"]}
                )
                self._audit(
                    connection,
                    actor_id=None,
                    action="expire_allocation",
                    outcome="voided",
                    slot_id=row["slot_id"],
                    generation=row["generation"],
                    pack_number=None,
                    request_id=occurrence_id,
                    occurred_at=executed_text,
                )
            result = {
                "occurrence_id": occurrence_id,
                "executed_at": executed_text,
                "voided": voided,
            }
            result_json = (
                prize_inputs.canonical_json_bytes(result).decode().rstrip("\n")
            )
            connection.execute(
                "INSERT INTO claim_deadline_run "
                "(event_id, occurrence_id, executed_at, result_json, result_digest) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    self.event_id,
                    occurrence_id,
                    executed_text,
                    result_json,
                    prize_inputs.artifact_digest(result),
                ),
            )
            connection.commit()
            return result
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("claim deadline processing failed closed") from error
        finally:
            connection.close()

    def correct_claim(
        self,
        staff: AuthenticatedEventStaff,
        *,
        claim_id: str,
        reason: str,
        request_id: str,
        replacement_pack_number: int | None = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Record an audited custody correction without replacing the claim."""

        staff_id = self._staff(staff, admin=True)
        claim_id = _uuid_text(claim_id, "claim_id")
        request_id = _uuid_text(request_id, "correction request_id")
        reason = _reason(reason)
        current_text, _current = _utc(now or datetime.now(UTC), "server time")
        if replacement_pack_number is not None and (
            type(replacement_pack_number) is not int
            or replacement_pack_number not in range(1, 51)
        ):
            raise PrizeClaimError("replacement pack number must be between 1 and 50")
        request_digest = self._request_digest(
            "correction",
            request_id,
            claim_id,
            reason,
            str(replacement_pack_number),
        )
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT request_digest, response_json FROM claim_correction "
                "WHERE event_id = ? AND request_id = ?",
                (self.event_id, request_id),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise PrizeClaimError(
                        "correction request identity was reused with different input"
                    )
                connection.commit()
                return json.loads(existing["response_json"])
            claim = connection.execute(
                "SELECT slot_id, generation FROM prize_claim "
                "WHERE event_id = ? AND claim_id = ?",
                (self.event_id, claim_id),
            ).fetchone()
            if claim is None:
                raise PrizeClaimError("claim does not exist")
            current_pack = connection.execute(
                "SELECT pack_number FROM prize_pack WHERE event_id = ? AND slot_id = ? "
                "AND generation = ? AND status = 'claimed'",
                (self.event_id, claim["slot_id"], claim["generation"]),
            ).fetchone()
            if current_pack is None:
                raise PrizeClaimError("claim has no current pack custody")
            from_pack = current_pack["pack_number"]
            to_pack = replacement_pack_number or from_pack
            if to_pack != from_pack:
                replacement = connection.execute(
                    "SELECT status FROM prize_pack WHERE event_id = ? AND pack_number = ?",
                    (self.event_id, to_pack),
                ).fetchone()
                if replacement is None or replacement["status"] != "available":
                    raise PrizeClaimError("replacement pack is already used")
                connection.execute(
                    "UPDATE prize_pack SET status = 'corrected_out', updated_at = ? "
                    "WHERE event_id = ? AND pack_number = ?",
                    (current_text, self.event_id, from_pack),
                )
                connection.execute(
                    "UPDATE prize_pack SET status = 'claimed', slot_id = ?, generation = ?, "
                    "updated_at = ? WHERE event_id = ? AND pack_number = ?",
                    (
                        claim["slot_id"],
                        claim["generation"],
                        current_text,
                        self.event_id,
                        to_pack,
                    ),
                )
            response = {
                "claim_id": claim_id,
                "from_pack_number": from_pack,
                "to_pack_number": to_pack,
                "reason": reason,
                "corrected_at": current_text,
            }
            response_json = (
                prize_inputs.canonical_json_bytes(response).decode().rstrip("\n")
            )
            connection.execute(
                "INSERT INTO claim_correction "
                "(event_id, correction_id, claim_id, from_pack_number, to_pack_number, "
                "reason, staff_id, request_id, request_digest, occurred_at, response_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.event_id,
                    str(uuid4()),
                    claim_id,
                    from_pack,
                    to_pack,
                    reason,
                    staff_id,
                    request_id,
                    request_digest,
                    current_text,
                    response_json,
                ),
            )
            self._audit(
                connection,
                actor_id=staff_id,
                action="correct_claim",
                outcome="corrected",
                slot_id=claim["slot_id"],
                generation=claim["generation"],
                pack_number=to_pack,
                request_id=request_id,
                occurred_at=current_text,
            )
            connection.commit()
            return response
        except (PrizeClaimError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeClaimError):
                raise
            raise PrizeClaimError("claim correction failed closed") from error
        finally:
            connection.close()

    def dashboard(self, staff: AuthenticatedEventStaff) -> dict[str, Any]:
        """Return all 50 slots for the authorized operator dashboard."""

        self._staff(staff)
        self.sync_allocations()
        connection = _connect(self.state_path)
        try:
            rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT slot.slot_id, names.award_name, attempt.generation, "
                    "attempt.status AS attempt_status, "
                    "participant.public_alias AS selected_alias, occurrence.trigger, "
                    "occurrence.stage, intent.state AS notification_state, claim.claimed_at, "
                    "pack.pack_number FROM prize_slot AS slot "
                    "JOIN claim_slot AS names ON names.event_id = slot.event_id "
                    "AND names.slot_id = slot.slot_id "
                    "LEFT JOIN allocation_attempt AS attempt ON attempt.event_id = slot.event_id "
                    "AND attempt.slot_id = slot.slot_id AND attempt.generation = ("
                    "SELECT MAX(latest.generation) FROM allocation_attempt AS latest "
                    "WHERE latest.event_id = slot.event_id "
                    "AND latest.slot_id = slot.slot_id) "
                    "LEFT JOIN claim_participant AS participant ON participant.event_id = attempt.event_id "
                    "AND participant.participant_id = attempt.participant_id "
                    "LEFT JOIN evaluation_occurrence AS occurrence "
                    "ON occurrence.event_id = attempt.event_id "
                    "AND occurrence.occurrence_id = attempt.occurrence_id "
                    "LEFT JOIN notification_intent AS intent ON intent.event_id = attempt.event_id "
                    "AND intent.slot_id = attempt.slot_id AND intent.generation = attempt.generation "
                    "LEFT JOIN prize_claim AS claim ON claim.event_id = attempt.event_id "
                    "AND claim.slot_id = attempt.slot_id AND claim.generation = attempt.generation "
                    "LEFT JOIN prize_pack AS pack ON pack.event_id = attempt.event_id "
                    "AND pack.slot_id = attempt.slot_id AND pack.generation = attempt.generation "
                    "AND pack.status = 'claimed' WHERE slot.event_id = ? ORDER BY slot.slot_order",
                    (self.event_id,),
                )
            ]
            errors = []
            if len(rows) != 50:
                errors.append("slot_count_mismatch")
            if (
                connection.execute(
                    "SELECT COUNT(*) FROM prize_pack WHERE event_id = ?",
                    (self.event_id,),
                ).fetchone()[0]
                != 50
            ):
                errors.append("inventory_count_mismatch")
            for row in rows:
                row["allocation_state"] = (
                    "unfilled"
                    if row["generation"] is None
                    else "claimed"
                    if row["claimed_at"] is not None
                    else row["attempt_status"]
                )
                row["trigger_status"] = (
                    "pending"
                    if row["generation"] is None
                    else "voided"
                    if row["attempt_status"] == "voided"
                    else "recorded"
                )
                if (
                    row["attempt_status"] == "selected"
                    and row["notification_state"] is None
                ):
                    errors.append(f"missing_notification:{row['slot_id']}")
            return {
                "contract": "cinder-typhoon.prize-operator-dashboard/v1",
                "slots": rows,
                "errors": sorted(set(errors)),
            }
        finally:
            connection.close()

    def credential_free_summary(self, staff: AuthenticatedEventStaff) -> dict[str, Any]:
        """Return an alias-only allocation and custody summary."""

        dashboard = self.dashboard(staff)
        return {
            "contract": "cinder-typhoon.prize-allocation-summary/v1",
            "allocations": [
                {
                    "slot_id": row["slot_id"],
                    "award_name": row["award_name"],
                    "selected_alias": row["selected_alias"],
                    "state": row["allocation_state"],
                    "pack_number": row["pack_number"],
                    "claimed_at": row["claimed_at"],
                }
                for row in dashboard["slots"]
            ],
            "errors": dashboard["errors"],
        }

    def _audit(
        self,
        connection: sqlite3.Connection,
        *,
        actor_id: str | None,
        action: str,
        outcome: str,
        slot_id: str | None,
        generation: int | None,
        pack_number: int | None,
        request_id: str | None,
        occurred_at: str,
    ) -> None:
        connection.execute(
            "INSERT INTO claim_audit "
            "(event_id, actor_id, action, outcome, slot_id, generation, pack_number, "
            "request_id, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.event_id,
                actor_id,
                action,
                outcome,
                slot_id,
                generation,
                pack_number,
                request_id,
                occurred_at,
            ),
        )


__all__ = [
    "CONFIG_CONTRACT",
    "AuthenticatedEventStaff",
    "AuthenticatedParticipant",
    "PrizeClaimError",
    "PrizeClaimService",
    "build_claim_config",
]
