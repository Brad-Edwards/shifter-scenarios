"""Collect private Good Citizen nominations for the event-prize evaluator."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from urllib.parse import urlsplit
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prize_inputs = _load_module(
    "cinder_prize_inputs_nominations", ROOT / "ctfd" / "prize_inputs.py"
)
prize_evaluator = _load_module(
    "cinder_prize_evaluator_nominations", ROOT / "ctfd" / "prize_evaluator.py"
)

CONFIG_CONTRACT = "cinder-typhoon.prize-nomination-config/v1"
NOMINATIONS_CONTRACT = prize_evaluator.NOMINATIONS_CONTRACT
CSRF_DOMAIN = b"cinder-typhoon/prize-nomination-csrf/v1"
CANDIDATE_DOMAIN = b"cinder-typhoon/prize-nomination-candidate/v1"
REQUEST_DOMAIN = b"cinder-typhoon/prize-nomination-request/v1"
RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = timedelta(minutes=1)
MAX_SESSION_ID_LENGTH = 256

SCHEMA = """
CREATE TABLE IF NOT EXISTS nomination_event (
    event_id TEXT PRIMARY KEY,
    config_digest TEXT NOT NULL,
    token_key_commitment TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    opens_at TEXT NOT NULL,
    closes_at TEXT NOT NULL,
    public_origin TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS nomination_participant (
    event_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    public_alias TEXT NOT NULL,
    PRIMARY KEY (event_id, participant_id),
    FOREIGN KEY (event_id) REFERENCES nomination_event(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS nomination_ballot (
    event_id TEXT NOT NULL,
    ballot_id TEXT NOT NULL,
    nominator_id TEXT NOT NULL,
    nominee_id TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    attested INTEGER NOT NULL CHECK (attested = 1),
    request_id TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    response_json TEXT NOT NULL,
    PRIMARY KEY (event_id, ballot_id),
    UNIQUE (event_id, nominator_id),
    UNIQUE (event_id, request_id),
    CHECK (nominator_id <> nominee_id),
    FOREIGN KEY (event_id, nominator_id)
        REFERENCES nomination_participant(event_id, participant_id),
    FOREIGN KEY (event_id, nominee_id)
        REFERENCES nomination_participant(event_id, participant_id)
) STRICT;

CREATE TABLE IF NOT EXISTS nomination_rate_attempt (
    event_id TEXT NOT NULL,
    nominator_id TEXT NOT NULL,
    request_id TEXT,
    attempted_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES nomination_event(event_id)
) STRICT;

CREATE INDEX IF NOT EXISTS nomination_rate_window
ON nomination_rate_attempt(event_id, nominator_id, attempted_at);

CREATE TABLE IF NOT EXISTS nomination_audit (
    audit_id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    target_id TEXT,
    request_id TEXT,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES nomination_event(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS nomination_close (
    event_id TEXT PRIMARY KEY,
    occurrence_id TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    export_digest TEXT NOT NULL,
    export_json TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES nomination_event(event_id)
) STRICT;
"""


class PrizeNominationError(ValueError):
    """A nomination request cannot be accepted without weakening a rule."""

    def __init__(self, message: str, *, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AuthenticatedParticipant:
    """Identity facts supplied by the approved authenticated integration."""

    event_id: str
    participant_id: str
    session_id: str
    origin: str


def _frame(parts: Iterable[bytes]) -> bytes:
    result = bytearray()
    for part in parts:
        result.extend(len(part).to_bytes(4, "big"))
        result.extend(part)
    return bytes(result)


def _uuid_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PrizeNominationError(f"{label} must be a UUID")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise PrizeNominationError(f"{label} must be a UUID") from error


def _utc(value: Any, label: str) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise PrizeNominationError(f"{label} must be a UTC timestamp") from error
    else:
        raise PrizeNominationError(f"{label} must be a UTC timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PrizeNominationError(f"{label} must be a UTC timestamp")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _origin(value: Any) -> str:
    if not isinstance(value, str):
        raise PrizeNominationError("public origin must be an HTTPS origin")
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
        raise PrizeNominationError("public origin must be an HTTPS origin")
    return f"https://{parsed.netloc}"


def _token(key: bytes, domain: bytes, parts: Iterable[bytes]) -> str:
    digest = hmac.new(key, domain + _frame(parts), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_nomination_config(
    *,
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    checked_in_participant_ids: Iterable[str],
    public_origin: str,
) -> dict[str, Any]:
    """Bind the nomination window to authoritative checked-in participants."""

    try:
        prize_inputs.validate_prize_input(policy, snapshot)
    except prize_inputs.PrizeInputError as error:
        raise PrizeNominationError(str(error)) from error
    eligible = {
        row["participant_id"]: row["public_alias"]
        for row in snapshot["participants"]
        if row["prize_eligible"]
    }
    checked_in = {
        _uuid_text(value, "checked-in participant")
        for value in checked_in_participant_ids
    }
    if not checked_in.issubset(eligible):
        raise PrizeNominationError("checked-in set contains an ineligible participant")
    boundaries = snapshot["event"]["boundaries"]
    return {
        "contract": CONFIG_CONTRACT,
        "event_id": snapshot["event"]["event_id"],
        "policy_digest": snapshot["event"]["policy_digest"],
        "content_bundle_digest": snapshot["event"]["content_bundle_digest"],
        "opens_at": boundaries["nomination_open_at"],
        "closes_at": boundaries["nomination_close_at"],
        "public_origin": _origin(public_origin),
        "participants": [
            {"participant_id": participant_id, "public_alias": eligible[participant_id]}
            for participant_id in sorted(
                checked_in, key=lambda value: UUID(value).bytes
            )
        ],
    }


def _config_participants(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise PrizeNominationError("nomination participants must be a list")
    normalized: dict[str, str] = {}
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != {"participant_id", "public_alias"}:
            raise PrizeNominationError(
                f"nomination participant {index} has invalid fields"
            )
        participant_id = _uuid_text(row["participant_id"], "participant_id")
        alias = row["public_alias"]
        if not isinstance(alias, str) or not alias or len(alias) > 100:
            raise PrizeNominationError("participant public alias is invalid")
        if participant_id in normalized and normalized[participant_id] != alias:
            raise PrizeNominationError(
                "participant identity is duplicated with different data"
            )
        normalized[participant_id] = alias
    return [
        {"participant_id": participant_id, "public_alias": normalized[participant_id]}
        for participant_id in sorted(normalized, key=lambda item: UUID(item).bytes)
    ]


def _validate_config(config: Any) -> dict[str, Any]:
    fields = {
        "contract",
        "event_id",
        "policy_digest",
        "content_bundle_digest",
        "opens_at",
        "closes_at",
        "public_origin",
        "participants",
    }
    if not isinstance(config, dict) or set(config) != fields:
        raise PrizeNominationError("nomination config has invalid fields")
    if config["contract"] != CONFIG_CONTRACT:
        raise PrizeNominationError("nomination config contract is invalid")
    event_id = _uuid_text(config["event_id"], "config.event_id")
    opens_at, opens = _utc(config["opens_at"], "config.opens_at")
    closes_at, closes = _utc(config["closes_at"], "config.closes_at")
    if not opens < closes:
        raise PrizeNominationError("nomination window is invalid")
    for name in ("policy_digest", "content_bundle_digest"):
        value = config[name]
        if not isinstance(value, str) or not prize_inputs.SHA256.fullmatch(value):
            raise PrizeNominationError(f"config.{name} is invalid")
    return {
        **config,
        "event_id": event_id,
        "opens_at": opens_at,
        "closes_at": closes_at,
        "public_origin": _origin(config["public_origin"]),
        "participants": _config_participants(config["participants"]),
    }


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise PrizeNominationError("nomination state path must not be a symbolic link")
    if not path.exists():
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
    os.chmod(path, 0o600)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.executescript(SCHEMA)
    return connection


class NominationService:
    """Transactional nomination domain service for an authenticated adapter."""

    def __init__(
        self, *, config: dict[str, Any], state_path: Path, token_key: bytes
    ) -> None:
        self.config = _validate_config(config)
        if not isinstance(token_key, bytes) or len(token_key) != 32:
            raise PrizeNominationError(
                "nomination token key must contain exactly 32 bytes"
            )
        self.state_path = state_path
        self._token_key = token_key
        self._participants = {
            row["participant_id"]: row["public_alias"]
            for row in self.config["participants"]
        }
        self._bind_state()

    @property
    def event_id(self) -> str:
        return self.config["event_id"]

    def _bind_state(self) -> None:
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            digest = prize_inputs.artifact_digest(self.config)
            token_key_commitment = (
                "sha256:"
                + hashlib.sha256(
                    b"cinder-typhoon/prize-nomination-token-key/v1"
                    + _frame((UUID(self.event_id).bytes, self._token_key))
                ).hexdigest()
            )
            expected = (
                digest,
                token_key_commitment,
                self.config["policy_digest"],
                self.config["content_bundle_digest"],
                self.config["opens_at"],
                self.config["closes_at"],
                self.config["public_origin"],
            )
            stored = connection.execute(
                "SELECT config_digest, token_key_commitment, policy_digest, content_digest, "
                "opens_at, closes_at, public_origin FROM nomination_event WHERE event_id = ?",
                (self.event_id,),
            ).fetchone()
            if stored is None:
                connection.execute(
                    "INSERT INTO nomination_event "
                    "(event_id, config_digest, token_key_commitment, policy_digest, "
                    "content_digest, opens_at, closes_at, public_origin, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.event_id, *expected, self.config["opens_at"]),
                )
                connection.executemany(
                    "INSERT INTO nomination_participant "
                    "(event_id, participant_id, public_alias) VALUES (?, ?, ?)",
                    [
                        (self.event_id, row["participant_id"], row["public_alias"])
                        for row in self.config["participants"]
                    ],
                )
            elif tuple(stored) != expected:
                raise PrizeNominationError(
                    "nomination state is bound to a different config or token key"
                )
            else:
                stored_participants = [
                    {"participant_id": row[0], "public_alias": row[1]}
                    for row in connection.execute(
                        "SELECT participant_id, public_alias FROM nomination_participant "
                        "WHERE event_id = ? ORDER BY participant_id",
                        (self.event_id,),
                    )
                ]
                expected_participants = sorted(
                    self.config["participants"], key=lambda row: row["participant_id"]
                )
                if stored_participants != expected_participants:
                    raise PrizeNominationError(
                        "persisted participant set differs from config"
                    )
            connection.commit()
        except (PrizeNominationError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeNominationError):
                raise
            raise PrizeNominationError(
                "nomination state binding failed closed"
            ) from error
        finally:
            connection.close()

    def _context(self, context: AuthenticatedParticipant) -> tuple[str, str]:
        if not isinstance(context, AuthenticatedParticipant):
            raise PrizeNominationError(
                "authenticated participant context is required", code="unauthorized"
            )
        if _uuid_text(context.event_id, "context.event_id") != self.event_id:
            raise PrizeNominationError(
                "participant context belongs to another event", code="unauthorized"
            )
        participant_id = _uuid_text(context.participant_id, "context.participant_id")
        if participant_id not in self._participants:
            raise PrizeNominationError(
                "participant is not checked in", code="unauthorized"
            )
        if (
            not isinstance(context.session_id, str)
            or not context.session_id
            or len(context.session_id) > MAX_SESSION_ID_LENGTH
        ):
            raise PrizeNominationError(
                "authenticated session is invalid", code="unauthorized"
            )
        if _origin(context.origin) != self.config["public_origin"]:
            raise PrizeNominationError(
                "request origin is not allowed", code="origin_rejected"
            )
        return participant_id, context.session_id

    def _csrf_token(self, participant_id: str, session_id: str) -> str:
        return _token(
            self._token_key,
            CSRF_DOMAIN,
            (
                UUID(self.event_id).bytes,
                UUID(participant_id).bytes,
                session_id.encode(),
                self.config["public_origin"].encode(),
                prize_inputs.artifact_digest(self.config).encode(),
            ),
        )

    def _candidate_token(
        self, participant_id: str, session_id: str, nominee_id: str
    ) -> str:
        return _token(
            self._token_key,
            CANDIDATE_DOMAIN,
            (
                UUID(self.event_id).bytes,
                UUID(participant_id).bytes,
                session_id.encode(),
                UUID(nominee_id).bytes,
                prize_inputs.artifact_digest(self.config).encode(),
            ),
        )

    def form(
        self,
        context: AuthenticatedParticipant,
        *,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Return aliases, opaque candidate tokens, and a session-bound CSRF token."""

        participant_id, session_id = self._context(context)
        current_text, current = _utc(now or datetime.now(timezone.utc), "server time")
        opens_text, opens = _utc(self.config["opens_at"], "nomination opens_at")
        closes_text, closes = _utc(self.config["closes_at"], "nomination closes_at")
        if not opens <= current < closes:
            raise PrizeNominationError(
                "nomination window is not open", code="window_closed"
            )
        connection = _connect(self.state_path)
        try:
            if connection.execute(
                "SELECT 1 FROM nomination_close WHERE event_id = ?", (self.event_id,)
            ).fetchone():
                raise PrizeNominationError(
                    "nominations are closed", code="window_closed"
                )
            ballot = connection.execute(
                "SELECT response_json FROM nomination_ballot "
                "WHERE event_id = ? AND nominator_id = ?",
                (self.event_id, participant_id),
            ).fetchone()
        finally:
            connection.close()
        return {
            "contract": "cinder-typhoon.prize-nomination-form/v1",
            "opens_at": opens_text,
            "closes_at": closes_text,
            "server_time": current_text,
            "csrf_token": self._csrf_token(participant_id, session_id),
            "submitted": json.loads(ballot["response_json"])
            if ballot is not None
            else None,
            "candidates": [
                {
                    "public_alias": alias,
                    "candidate_token": self._candidate_token(
                        participant_id, session_id, nominee_id
                    ),
                }
                for nominee_id, alias in self._participants.items()
                if nominee_id != participant_id
            ],
        }

    def _resolve_candidate(
        self, participant_id: str, session_id: str, candidate_token: Any
    ) -> str:
        if not isinstance(candidate_token, str) or not candidate_token:
            raise PrizeNominationError(
                "candidate token is invalid", code="candidate_rejected"
            )
        matches = [
            nominee_id
            for nominee_id in self._participants
            if hmac.compare_digest(
                candidate_token,
                self._candidate_token(participant_id, session_id, nominee_id),
            )
        ]
        if len(matches) != 1 or matches[0] == participant_id:
            raise PrizeNominationError(
                "candidate token is invalid", code="candidate_rejected"
            )
        return matches[0]

    def submit(
        self,
        context: AuthenticatedParticipant,
        payload: dict[str, Any],
        *,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Create one private ballot with CSRF, cutoff, rate, and uniqueness checks."""

        participant_id, session_id = self._context(context)
        current_text, current = _utc(now or datetime.now(timezone.utc), "server time")
        request_id: str | None = None
        nominee_id: str | None = None
        try:
            if self._rate_limited(participant_id, current):
                raise PrizeNominationError(
                    "nomination rate limit exceeded", code="rate_limited"
                )
            if not isinstance(payload, dict) or set(payload) != {
                "request_id",
                "csrf_token",
                "candidate_token",
                "attested",
            }:
                raise PrizeNominationError("nomination payload has invalid fields")
            request_id = _uuid_text(payload["request_id"], "request_id")
            request_digest = self._request_digest(participant_id, session_id, payload)
            if not isinstance(payload["csrf_token"], str) or not hmac.compare_digest(
                payload["csrf_token"], self._csrf_token(participant_id, session_id)
            ):
                raise PrizeNominationError(
                    "CSRF token is invalid", code="csrf_rejected"
                )
            if payload["attested"] is not True:
                raise PrizeNominationError(
                    "no-sharing attestation is required", code="attestation_required"
                )
            nominee_id = self._resolve_candidate(
                participant_id, session_id, payload["candidate_token"]
            )
            return self._submit_transaction(
                participant_id=participant_id,
                nominee_id=nominee_id,
                request_id=request_id,
                request_digest=request_digest,
                current_text=current_text,
                current=current,
            )
        except PrizeNominationError as error:
            self._record_rejection(
                participant_id=participant_id,
                nominee_id=nominee_id,
                request_id=request_id,
                current_text=current_text,
                outcome=error.code,
            )
            raise

    def _rate_limited(self, participant_id: str, current: datetime) -> bool:
        cutoff = _utc(current - RATE_LIMIT_WINDOW, "rate cutoff")[0]
        connection = _connect(self.state_path)
        try:
            return (
                connection.execute(
                    "SELECT COUNT(*) FROM nomination_rate_attempt "
                    "WHERE event_id = ? AND nominator_id = ? AND attempted_at > ?",
                    (self.event_id, participant_id, cutoff),
                ).fetchone()[0]
                >= RATE_LIMIT_ATTEMPTS
            )
        finally:
            connection.close()

    def _request_digest(
        self, participant_id: str, session_id: str, payload: dict[str, Any]
    ) -> str:
        value = {
            "event_id": self.event_id,
            "participant_id": participant_id,
            "session_id_digest": hashlib.sha256(session_id.encode()).hexdigest(),
            "request_id": payload["request_id"],
            "csrf_token": payload["csrf_token"],
            "candidate_token": payload["candidate_token"],
            "attested": payload["attested"],
        }
        return f"sha256:{hashlib.sha256(REQUEST_DOMAIN + prize_inputs.canonical_json_bytes(value)).hexdigest()}"

    def _submit_transaction(
        self,
        *,
        participant_id: str,
        nominee_id: str,
        request_id: str,
        request_digest: str,
        current_text: str,
        current: datetime,
    ) -> dict[str, Any]:
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_request = connection.execute(
                "SELECT request_digest, response_json FROM nomination_ballot "
                "WHERE event_id = ? AND request_id = ?",
                (self.event_id, request_id),
            ).fetchone()
            if existing_request is not None:
                if existing_request["request_digest"] != request_digest:
                    raise PrizeNominationError(
                        "request identity was reused with different input",
                        code="request_conflict",
                    )
                connection.commit()
                return json.loads(existing_request["response_json"])

            opens = _utc(self.config["opens_at"], "nomination opens_at")[1]
            closes = _utc(self.config["closes_at"], "nomination closes_at")[1]
            if (
                not opens <= current < closes
                or connection.execute(
                    "SELECT 1 FROM nomination_close WHERE event_id = ?",
                    (self.event_id,),
                ).fetchone()
            ):
                raise PrizeNominationError(
                    "nomination window is closed", code="window_closed"
                )
            cutoff = _utc(current - RATE_LIMIT_WINDOW, "rate cutoff")[0]
            recent_attempts = connection.execute(
                "SELECT COUNT(*) FROM nomination_rate_attempt "
                "WHERE event_id = ? AND nominator_id = ? AND attempted_at > ?",
                (self.event_id, participant_id, cutoff),
            ).fetchone()[0]
            if recent_attempts >= RATE_LIMIT_ATTEMPTS:
                raise PrizeNominationError(
                    "nomination rate limit exceeded", code="rate_limited"
                )
            if connection.execute(
                "SELECT 1 FROM nomination_ballot WHERE event_id = ? AND nominator_id = ?",
                (self.event_id, participant_id),
            ).fetchone():
                raise PrizeNominationError(
                    "participant already submitted a ballot", code="duplicate_ballot"
                )

            ballot_id = str(uuid4())
            response = {
                "contract": "cinder-typhoon.prize-nomination-receipt/v1",
                "ballot_id": ballot_id,
                "nominee_alias": self._participants[nominee_id],
                "submitted_at": current_text,
                "attested": True,
            }
            response_json = (
                prize_inputs.canonical_json_bytes(response).decode().rstrip("\n")
            )
            connection.execute(
                "INSERT INTO nomination_ballot "
                "(event_id, ballot_id, nominator_id, nominee_id, submitted_at, attested, "
                "request_id, request_digest, response_json) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (
                    self.event_id,
                    ballot_id,
                    participant_id,
                    nominee_id,
                    current_text,
                    request_id,
                    request_digest,
                    response_json,
                ),
            )
            self._attempt(
                connection,
                participant_id=participant_id,
                request_id=request_id,
                current_text=current_text,
                outcome="accepted",
            )
            self._audit(
                connection,
                actor_id=participant_id,
                action="submit_nomination",
                outcome="accepted",
                target_id=nominee_id,
                request_id=request_id,
                occurred_at=current_text,
            )
            connection.commit()
            return response
        except (PrizeNominationError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeNominationError):
                raise
            raise PrizeNominationError("nomination submission failed closed") from error
        finally:
            connection.close()

    def _record_rejection(
        self,
        *,
        participant_id: str,
        nominee_id: str | None,
        request_id: str | None,
        current_text: str,
        outcome: str,
    ) -> None:
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            if outcome != "rate_limited":
                self._attempt(
                    connection,
                    participant_id=participant_id,
                    request_id=request_id,
                    current_text=current_text,
                    outcome=outcome,
                )
            self._audit(
                connection,
                actor_id=participant_id,
                action="submit_nomination",
                outcome=outcome,
                target_id=nominee_id,
                request_id=request_id,
                occurred_at=current_text,
            )
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            raise PrizeNominationError(
                "nomination rejection audit failed closed"
            ) from error
        finally:
            connection.close()

    def _attempt(
        self,
        connection: sqlite3.Connection,
        *,
        participant_id: str,
        request_id: str | None,
        current_text: str,
        outcome: str,
    ) -> None:
        connection.execute(
            "INSERT INTO nomination_rate_attempt "
            "(event_id, nominator_id, request_id, attempted_at, outcome) VALUES (?, ?, ?, ?, ?)",
            (self.event_id, participant_id, request_id, current_text, outcome),
        )

    def _audit(
        self,
        connection: sqlite3.Connection,
        *,
        actor_id: str | None,
        action: str,
        outcome: str,
        target_id: str | None,
        request_id: str | None,
        occurred_at: str,
    ) -> None:
        connection.execute(
            "INSERT INTO nomination_audit "
            "(event_id, actor_id, action, outcome, target_id, request_id, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self.event_id,
                actor_id,
                action,
                outcome,
                target_id,
                request_id,
                occurred_at,
            ),
        )

    def close(
        self, *, policy: dict[str, Any], snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply the authoritative scheduled close once and return evaluator input."""

        try:
            prize_inputs.validate_prize_input(policy, snapshot)
        except prize_inputs.PrizeInputError as error:
            raise PrizeNominationError(str(error)) from error
        event = snapshot["event"]
        if (
            event["event_id"] != self.event_id
            or event["policy_digest"] != self.config["policy_digest"]
            or event["content_bundle_digest"] != self.config["content_bundle_digest"]
        ):
            raise PrizeNominationError("close input differs from nomination config")
        occurrences = [
            row
            for row in snapshot["occurrences"]
            if row["trigger"] == "nomination_closed"
        ]
        if len(occurrences) != 1:
            raise PrizeNominationError(
                "authoritative nomination-close occurrence is missing"
            )
        occurrence = occurrences[0]
        if occurrence["scheduled_for"] != self.config["closes_at"]:
            raise PrizeNominationError("nomination-close boundary differs from config")
        input_digest = prize_inputs.artifact_digest(
            {
                "event_id": self.event_id,
                "policy_digest": event["policy_digest"],
                "content_bundle_digest": event["content_bundle_digest"],
                "occurrence": occurrence,
                "config_digest": prize_inputs.artifact_digest(self.config),
            }
        )
        connection = _connect(self.state_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT occurrence_id, scheduled_for, executed_at, input_digest, export_json "
                "FROM nomination_close WHERE event_id = ?",
                (self.event_id,),
            ).fetchone()
            identity = (
                occurrence["occurrence_id"],
                occurrence["scheduled_for"],
                occurrence["executed_at"],
                input_digest,
            )
            if existing is not None:
                if tuple(existing)[:4] != identity:
                    raise PrizeNominationError(
                        "nomination close identity or input changed"
                    )
                connection.commit()
                return json.loads(existing["export_json"])
            export = self._export(connection)
            export_json = (
                prize_inputs.canonical_json_bytes(export).decode().rstrip("\n")
            )
            connection.execute(
                "INSERT INTO nomination_close "
                "(event_id, occurrence_id, scheduled_for, executed_at, input_digest, "
                "export_digest, export_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    self.event_id,
                    occurrence["occurrence_id"],
                    occurrence["scheduled_for"],
                    occurrence["executed_at"],
                    input_digest,
                    prize_inputs.artifact_digest(export),
                    export_json,
                ),
            )
            self._audit(
                connection,
                actor_id=None,
                action="close_nominations",
                outcome="closed",
                target_id=None,
                request_id=occurrence["occurrence_id"],
                occurred_at=occurrence["executed_at"],
            )
            connection.commit()
            return export
        except (PrizeNominationError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, PrizeNominationError):
                raise
            raise PrizeNominationError("nomination close failed closed") from error
        finally:
            connection.close()

    def _export(self, connection: sqlite3.Connection) -> dict[str, Any]:
        return {
            "contract": NOMINATIONS_CONTRACT,
            "event_id": self.event_id,
            "ballots": [
                {
                    "ballot_id": row["ballot_id"],
                    "nominator_id": row["nominator_id"],
                    "nominee_id": row["nominee_id"],
                    "submitted_at": row["submitted_at"],
                    "attested": True,
                }
                for row in connection.execute(
                    "SELECT ballot_id, nominator_id, nominee_id, submitted_at "
                    "FROM nomination_ballot WHERE event_id = ? ORDER BY ballot_id",
                    (self.event_id,),
                )
            ],
        }

    def audit_rows(self) -> list[dict[str, Any]]:
        """Return the private operator audit stream for qualification and support."""

        connection = _connect(self.state_path)
        try:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT actor_id, action, outcome, target_id, request_id, occurred_at "
                    "FROM nomination_audit WHERE event_id = ? ORDER BY audit_id",
                    (self.event_id,),
                )
            ]
        finally:
            connection.close()


__all__ = [
    "AuthenticatedParticipant",
    "CONFIG_CONTRACT",
    "NominationService",
    "PrizeNominationError",
    "build_nomination_config",
]
