#!/usr/bin/env python3
"""Evaluate Cinder Typhoon physical-prize triggers transactionally."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
PRIZE_INPUTS_PATH = ROOT / "ctfd" / "prize_inputs.py"
PRIZE_INPUTS_SPEC = importlib.util.spec_from_file_location(
    "cinder_prize_inputs_evaluator", PRIZE_INPUTS_PATH
)
if PRIZE_INPUTS_SPEC is None or PRIZE_INPUTS_SPEC.loader is None:
    raise RuntimeError("cannot load prize input module")
prize_inputs = importlib.util.module_from_spec(PRIZE_INPUTS_SPEC)
PRIZE_INPUTS_SPEC.loader.exec_module(prize_inputs)

STAGES = ("training", "keplerops", "arwc")
NOMINATIONS_CONTRACT = "cinder-typhoon.prize-nominations/v1"
COMMITMENT_DOMAIN = b"cinder-typhoon/prize-seed-commitment/v1"
ELIGIBILITY_DOMAIN = b"cinder-typhoon/prize-eligibility/v1"
DRAW_DOMAIN = b"cinder-typhoon/prize-draw/v1"
MAX_REASON_LENGTH = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS event_binding (
    event_id TEXT PRIMARY KEY,
    policy_digest TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    seed_commitment TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS prize_slot (
    event_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    family TEXT NOT NULL,
    scope TEXT,
    slot_order INTEGER NOT NULL,
    PRIMARY KEY (event_id, slot_id),
    UNIQUE (event_id, slot_order),
    FOREIGN KEY (event_id) REFERENCES event_binding(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS evaluation_occurrence (
    event_id TEXT NOT NULL,
    occurrence_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    stage TEXT,
    scheduled_for TEXT,
    executed_at TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    result_json TEXT NOT NULL,
    result_digest TEXT NOT NULL,
    PRIMARY KEY (event_id, occurrence_id),
    FOREIGN KEY (event_id) REFERENCES event_binding(event_id)
) STRICT;

CREATE TABLE IF NOT EXISTS allocation_attempt (
    event_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK (generation > 0),
    participant_id TEXT NOT NULL,
    occurrence_id TEXT NOT NULL,
    selector TEXT NOT NULL,
    selection_reason TEXT NOT NULL,
    eligibility_digest TEXT NOT NULL,
    draw_rank TEXT,
    status TEXT NOT NULL CHECK (status IN ('selected', 'voided')),
    selected_at TEXT NOT NULL,
    voided_at TEXT,
    void_reason TEXT,
    PRIMARY KEY (event_id, slot_id, generation),
    FOREIGN KEY (event_id, slot_id) REFERENCES prize_slot(event_id, slot_id),
    FOREIGN KEY (event_id, occurrence_id)
        REFERENCES evaluation_occurrence(event_id, occurrence_id)
        DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS one_live_allocation_per_slot
ON allocation_attempt(event_id, slot_id)
WHERE status = 'selected';

CREATE UNIQUE INDEX IF NOT EXISTS one_live_allocation_per_participant
ON allocation_attempt(event_id, participant_id)
WHERE status = 'selected';
"""

_OPEN_SLOT_QUERIES = {
    (False, False): (
        "SELECT slot.slot_id FROM prize_slot AS slot "
        "LEFT JOIN allocation_attempt AS attempt "
        "ON attempt.event_id = slot.event_id AND attempt.slot_id = slot.slot_id "
        "AND attempt.status = 'selected' "
        "WHERE slot.event_id = ? AND attempt.slot_id IS NULL ORDER BY slot.slot_order"
    ),
    (True, False): (
        "SELECT slot.slot_id FROM prize_slot AS slot "
        "LEFT JOIN allocation_attempt AS attempt "
        "ON attempt.event_id = slot.event_id AND attempt.slot_id = slot.slot_id "
        "AND attempt.status = 'selected' "
        "WHERE slot.event_id = ? AND attempt.slot_id IS NULL AND slot.family = ? "
        "ORDER BY slot.slot_order"
    ),
    (False, True): (
        "SELECT slot.slot_id FROM prize_slot AS slot "
        "LEFT JOIN allocation_attempt AS attempt "
        "ON attempt.event_id = slot.event_id AND attempt.slot_id = slot.slot_id "
        "AND attempt.status = 'selected' "
        "WHERE slot.event_id = ? AND attempt.slot_id IS NULL AND slot.scope = ? "
        "ORDER BY slot.slot_order"
    ),
    (True, True): (
        "SELECT slot.slot_id FROM prize_slot AS slot "
        "LEFT JOIN allocation_attempt AS attempt "
        "ON attempt.event_id = slot.event_id AND attempt.slot_id = slot.slot_id "
        "AND attempt.status = 'selected' "
        "WHERE slot.event_id = ? AND attempt.slot_id IS NULL "
        "AND slot.family = ? AND slot.scope = ? ORDER BY slot.slot_order"
    ),
}


class PrizeEvaluationError(ValueError):
    """Prize evaluation cannot continue without weakening an invariant."""


def _frame(parts: Iterable[bytes]) -> bytes:
    result = bytearray()
    for part in parts:
        result.extend(len(part).to_bytes(4, "big"))
        result.extend(part)
    return bytes(result)


def _uuid_bytes(value: str) -> bytes:
    try:
        return UUID(value).bytes
    except (ValueError, AttributeError) as error:
        raise PrizeEvaluationError("invalid UUID in evaluator input") from error


def _uuid_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PrizeEvaluationError(f"{label} must be a UUID")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise PrizeEvaluationError(f"{label} must be a UUID") from error


def _utc(value: Any, label: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        raise PrizeEvaluationError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PrizeEvaluationError(f"{label} must be a UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PrizeEvaluationError(f"{label} must be a UTC timestamp")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def seed_commitment(event_id: str, seed: bytes) -> str:
    """Commit to one 256-bit event draw seed without storing the seed."""

    if not isinstance(seed, bytes) or len(seed) != 32:
        raise PrizeEvaluationError("draw seed must contain exactly 32 bytes")
    digest = hashlib.sha256(
        COMMITMENT_DOMAIN + _frame((_uuid_bytes(event_id), seed))
    ).hexdigest()
    return f"sha256:{digest}"


def _eligibility_digest(
    *,
    event_id: str,
    policy_digest: str,
    occurrence_id: str,
    selector: str,
    candidates: Iterable[str],
) -> str:
    ordered = sorted(set(candidates), key=_uuid_bytes)
    payload = _frame(
        (
            _uuid_bytes(event_id),
            policy_digest.encode(),
            _uuid_bytes(occurrence_id),
            selector.encode(),
            *(_uuid_bytes(participant_id) for participant_id in ordered),
        )
    )
    return f"sha256:{hashlib.sha256(ELIGIBILITY_DOMAIN + payload).hexdigest()}"


def _draw_order(
    *,
    seed: bytes,
    event_id: str,
    policy_digest: str,
    occurrence_id: str,
    selector: str,
    candidates: Iterable[str],
) -> tuple[list[tuple[str, str]], str]:
    ordered = sorted(set(candidates), key=_uuid_bytes)
    eligibility_digest = _eligibility_digest(
        event_id=event_id,
        policy_digest=policy_digest,
        occurrence_id=occurrence_id,
        selector=selector,
        candidates=ordered,
    )
    prefix = _frame(
        (
            _uuid_bytes(event_id),
            policy_digest.encode(),
            _uuid_bytes(occurrence_id),
            selector.encode(),
            eligibility_digest.encode(),
        )
    )
    ranked = [
        (
            participant_id,
            hmac.new(
                seed,
                DRAW_DOMAIN + prefix + _frame((_uuid_bytes(participant_id),)),
                hashlib.sha256,
            ).hexdigest(),
        )
        for participant_id in ordered
    ]
    ranked.sort(key=lambda item: (item[1], _uuid_bytes(item[0])))
    return ranked, eligibility_digest


def _policy_slots(policy: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        allocations = policy["allocations"]
        rows: list[tuple[str, str | None, str]] = []
        rows.extend(
            ("overall_leaders", None, slot_id)
            for slot_id in allocations["overall_leaders"]["slot_ids"]
        )
        rows.extend(
            ("stage_completion", stage, slot_id)
            for stage in STAGES
            for slot_id in allocations["stage_completion"]["slot_ids"][stage]
        )
        rows.extend(
            ("bounties", award["stage"], award["slot_id"])
            for award in allocations["bounties"]["awards"]
        )
        rows.extend(
            ("stage_draws", stage, slot_id)
            for stage in STAGES
            for slot_id in allocations["stage_draws"]["slot_ids"][stage]
        )
        rows.extend(
            ("passport_draw", None, slot_id)
            for slot_id in allocations["passport_draw"]["slot_ids"]
        )
        rows.extend(
            ("good_citizen", None, slot_id)
            for slot_id in allocations["good_citizen"]["slot_ids"]
        )
    except (KeyError, TypeError) as error:
        raise PrizeEvaluationError(
            "prize policy allocation shape is invalid"
        ) from error
    slot_ids = [slot_id for _family, _scope, slot_id in rows]
    if (
        len(rows) != 50
        or len(set(slot_ids)) != 50
        or not all(isinstance(slot_id, str) and slot_id for slot_id in slot_ids)
    ):
        raise PrizeEvaluationError("prize policy must project exactly 50 unique slots")
    return [
        {
            "family": family,
            "scope": scope,
            "slot_id": slot_id,
            "slot_order": index,
        }
        for index, (family, scope, slot_id) in enumerate(rows, start=1)
    ]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise PrizeEvaluationError("prize state path must not be a symbolic link")
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


def _bind_event(
    connection: sqlite3.Connection,
    *,
    event: dict[str, Any],
    policy: dict[str, Any],
    slots: list[dict[str, Any]],
    seed: bytes,
) -> None:
    event_id = event["event_id"]
    expected_commitment = seed_commitment(event_id, seed)
    actual_commitment = event["boundaries"]["draw_seed_commitment"]
    if expected_commitment != actual_commitment:
        raise PrizeEvaluationError("draw seed does not match the event commitment")
    expected = (
        event["policy_digest"],
        event["content_bundle_digest"],
        actual_commitment,
    )
    binding = connection.execute(
        "SELECT policy_digest, content_digest, seed_commitment "
        "FROM event_binding WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if binding is None:
        connection.execute(
            "INSERT INTO event_binding "
            "(event_id, policy_digest, content_digest, seed_commitment, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, *expected, event["snapshot_at"]),
        )
    elif tuple(binding) != expected:
        raise PrizeEvaluationError("event state is bound to different prize inputs")

    stored = [
        dict(row)
        for row in connection.execute(
            "SELECT family, scope, slot_id, slot_order FROM prize_slot "
            "WHERE event_id = ? ORDER BY slot_order",
            (event_id,),
        )
    ]
    if not stored:
        connection.executemany(
            "INSERT INTO prize_slot (event_id, slot_id, family, scope, slot_order) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    event_id,
                    row["slot_id"],
                    row["family"],
                    row["scope"],
                    row["slot_order"],
                )
                for row in slots
            ],
        )
    elif stored != slots:
        raise PrizeEvaluationError("persisted prize slots differ from the bound policy")


def _normalize_nominations(
    envelope: dict[str, Any] | None,
    *,
    snapshot: dict[str, Any],
) -> list[dict[str, str]]:
    if envelope is None:
        return []
    if not isinstance(envelope, dict) or set(envelope) != {
        "contract",
        "event_id",
        "ballots",
    }:
        raise PrizeEvaluationError("nomination input has invalid fields")
    event_id = snapshot["event"]["event_id"]
    if envelope["contract"] != NOMINATIONS_CONTRACT or envelope["event_id"] != event_id:
        raise PrizeEvaluationError(
            "nomination input belongs to a different contract or event"
        )
    ballots = envelope["ballots"]
    if not isinstance(ballots, list):
        raise PrizeEvaluationError("nomination ballots must be a list")
    eligible = {
        row["participant_id"]
        for row in snapshot["participants"]
        if row["prize_eligible"]
    }
    boundaries = snapshot["event"]["boundaries"]
    _open_text, opens = _utc(boundaries["nomination_open_at"], "nomination open")
    _close_text, closes = _utc(boundaries["nomination_close_at"], "nomination close")
    result: dict[str, dict[str, str]] = {}
    ballot_ids: set[str] = set()
    for index, row in enumerate(ballots):
        if not isinstance(row, dict) or set(row) != {
            "ballot_id",
            "nominator_id",
            "nominee_id",
            "submitted_at",
            "attested",
        }:
            raise PrizeEvaluationError(f"nomination ballot {index} has invalid fields")
        ballot_id = _uuid_text(row["ballot_id"], f"nomination ballot {index} ballot_id")
        nominator_id = _uuid_text(
            row["nominator_id"], f"nomination ballot {index} nominator_id"
        )
        nominee_id = _uuid_text(
            row["nominee_id"], f"nomination ballot {index} nominee_id"
        )
        submitted_at, submitted_dt = _utc(
            row["submitted_at"], f"nomination ballot {index} submitted_at"
        )
        if (
            row["attested"] is not True
            or nominator_id not in eligible
            or nominee_id not in eligible
            or nominator_id == nominee_id
            or not opens <= submitted_dt < closes
        ):
            raise PrizeEvaluationError("nomination ballot is not eligible")
        if ballot_id in ballot_ids:
            raise PrizeEvaluationError("duplicate nomination ballot identity")
        ballot_ids.add(ballot_id)
        normalized = {
            "ballot_id": ballot_id,
            "nominator_id": nominator_id,
            "nominee_id": nominee_id,
            "submitted_at": submitted_at,
        }
        prior = result.get(nominator_id)
        if prior is not None and prior != normalized:
            raise PrizeEvaluationError(
                "one participant submitted multiple nomination ballots"
            )
        result[nominator_id] = normalized
    return sorted(result.values(), key=lambda row: _uuid_bytes(row["ballot_id"]))


def _occurrence_sort_key(
    occurrence: dict[str, Any], solves: dict[str, dict[str, Any]]
) -> tuple[Any, ...]:
    if occurrence["trigger"] == "accepted_solve":
        solve = solves[occurrence["submission_id"]]
        return (
            _utc(solve["accepted_at"], "accepted solve time")[1],
            0,
            _uuid_bytes(solve["submission_id"]),
            _uuid_bytes(solve["participant_id"]),
        )
    return (
        _utc(occurrence["scheduled_for"], "scheduled occurrence time")[1],
        {
            "stage_closed": 1,
            "nomination_closed": 2,
            "event_closed": 3,
            "finalization": 4,
        }[occurrence["trigger"]],
        _uuid_bytes(occurrence["occurrence_id"]),
    )


def _require_prior_solve_occurrences(
    occurrence: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    solve_occurrence_ids: set[str],
) -> None:
    if occurrence["trigger"] == "accepted_solve":
        return
    cutoff = _utc(occurrence["scheduled_for"], "occurrence cutoff")[1]
    required = {
        solve["submission_id"]
        for solve in snapshot["accepted_solves"]
        if _utc(solve["accepted_at"], "accepted solve time")[1] <= cutoff
    }
    missing = required - solve_occurrence_ids
    if missing:
        raise PrizeEvaluationError(
            "close occurrence is missing accepted-solve reconciliation facts"
        )


def _occurrence_input_digest(
    occurrence: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    nominations: list[dict[str, str]],
) -> str:
    solves = {row["submission_id"]: row for row in snapshot["accepted_solves"]}
    if occurrence["trigger"] == "accepted_solve":
        current = solves[occurrence["submission_id"]]
        selected_solves = [current]
        selected_participants = [
            row
            for row in snapshot["participants"]
            if row["participant_id"] == current["participant_id"]
        ]
    else:
        cutoff = _utc(occurrence["scheduled_for"], "occurrence cutoff")[1]
        selected_solves = [
            solve
            for solve in snapshot["accepted_solves"]
            if _utc(solve["accepted_at"], "accepted solve time")[1] <= cutoff
        ]
        selected_participants = snapshot["participants"]
    value: dict[str, Any] = {
        "event": {
            key: snapshot["event"][key]
            for key in (
                "event_id",
                "content_bundle_digest",
                "policy_digest",
                "catalog_revision",
                "boundaries",
            )
        },
        "occurrence": occurrence,
        "participants": [
            {
                "participant_id": row["participant_id"],
                "prize_eligible": row["prize_eligible"],
            }
            for row in selected_participants
        ],
        "accepted_solves": selected_solves,
    }
    if occurrence["trigger"] == "accepted_solve":
        stage_result = next(
            (
                row
                for row in snapshot["stage_results"][occurrence["stage"]]
                if row["participant_id"] == current["participant_id"]
                and row["completing_submission_id"] == current["submission_id"]
            ),
            None,
        )
        value["stage_completion"] = (
            {
                "completed_at": stage_result["completed_at"],
                "completing_submission_id": stage_result["completing_submission_id"],
            }
            if stage_result is not None
            else None
        )
    elif occurrence["trigger"] == "stage_closed":
        value["stage_results"] = snapshot["stage_results"][occurrence["stage"]]
    if occurrence["trigger"] in {"event_closed", "finalization"}:
        value["overall_ranking"] = snapshot["overall_ranking"]
    if occurrence["trigger"] == "nomination_closed":
        value["nominations"] = nominations
    return prize_inputs.artifact_digest(value)


def _active_winners(connection: sqlite3.Connection, event_id: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT participant_id FROM allocation_attempt "
            "WHERE event_id = ? AND status = 'selected'",
            (event_id,),
        )
    }


def _previously_allocated(connection: sqlite3.Connection, event_id: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT participant_id FROM allocation_attempt WHERE event_id = ?",
            (event_id,),
        )
    }


def _open_slots(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    family: str | None = None,
    scope: str | None = None,
) -> list[str]:
    parameters: list[Any] = [event_id]
    if family is not None:
        parameters.append(family)
    if scope is not None:
        parameters.append(scope)
    query = _OPEN_SLOT_QUERIES[(family is not None, scope is not None)]
    return [row[0] for row in connection.execute(query, parameters)]


def _allocate(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    slot_id: str,
    participant_id: str,
    occurrence: dict[str, Any],
    selector: str,
    reason: str,
    eligibility_digest: str,
    draw_rank: str | None,
) -> dict[str, Any] | None:
    if participant_id in _active_winners(connection, event_id):
        return None
    if slot_id not in _open_slots(connection, event_id=event_id):
        return None
    generation = connection.execute(
        "SELECT COALESCE(MAX(generation), 0) + 1 FROM allocation_attempt "
        "WHERE event_id = ? AND slot_id = ?",
        (event_id, slot_id),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO allocation_attempt "
        "(event_id, slot_id, generation, participant_id, occurrence_id, selector, "
        "selection_reason, eligibility_digest, draw_rank, status, selected_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'selected', ?)",
        (
            event_id,
            slot_id,
            generation,
            participant_id,
            occurrence["occurrence_id"],
            selector,
            reason,
            eligibility_digest,
            draw_rank,
            occurrence["executed_at"],
        ),
    )
    return {
        "slot_id": slot_id,
        "generation": generation,
        "participant_id": participant_id,
        "selector": selector,
        "selection_reason": reason,
        "eligibility_digest": eligibility_digest,
        "draw_rank": draw_rank,
    }


def _select_ordered(
    connection: sqlite3.Connection,
    *,
    event: dict[str, Any],
    occurrence: dict[str, Any],
    slots: list[str],
    candidates: list[str],
    selector: str,
    reason: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    winners = _active_winners(connection, event["event_id"])
    eligible = [candidate for candidate in candidates if candidate not in winners]
    digest = _eligibility_digest(
        event_id=event["event_id"],
        policy_digest=event["policy_digest"],
        occurrence_id=occurrence["occurrence_id"],
        selector=selector,
        candidates=eligible,
    )
    allocations = []
    for slot_id, participant_id in zip(slots, eligible, strict=False):
        allocation = _allocate(
            connection,
            event_id=event["event_id"],
            slot_id=slot_id,
            participant_id=participant_id,
            occurrence=occurrence,
            selector=selector,
            reason=reason,
            eligibility_digest=digest,
            draw_rank=None,
        )
        if allocation is not None:
            allocations.append(allocation)
    return allocations, {
        "selector": selector,
        "eligibility_digest": digest,
        "candidate_count": len(eligible),
    }


def _select_draw(
    connection: sqlite3.Connection,
    *,
    event: dict[str, Any],
    occurrence: dict[str, Any],
    slots: list[str],
    candidates: Iterable[str],
    selector: str,
    reason: str,
    seed: bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    winners = _active_winners(connection, event["event_id"])
    eligible = [candidate for candidate in set(candidates) if candidate not in winners]
    ranked, digest = _draw_order(
        seed=seed,
        event_id=event["event_id"],
        policy_digest=event["policy_digest"],
        occurrence_id=occurrence["occurrence_id"],
        selector=selector,
        candidates=eligible,
    )
    allocations = []
    for slot_id, (participant_id, rank) in zip(slots, ranked, strict=False):
        allocation = _allocate(
            connection,
            event_id=event["event_id"],
            slot_id=slot_id,
            participant_id=participant_id,
            occurrence=occurrence,
            selector=selector,
            reason=reason,
            eligibility_digest=digest,
            draw_rank=rank,
        )
        if allocation is not None:
            allocations.append(allocation)
    return allocations, {
        "selector": selector,
        "eligibility_digest": digest,
        "candidate_count": len(ranked),
    }


def _accepted_solve_selection(
    connection: sqlite3.Connection,
    *,
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    occurrence: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event = snapshot["event"]
    solve = next(
        row
        for row in snapshot["accepted_solves"]
        if row["submission_id"] == occurrence["submission_id"]
    )
    participant = next(
        row
        for row in snapshot["participants"]
        if row["participant_id"] == solve["participant_id"]
    )
    if not participant["prize_eligible"]:
        return [], []
    allocations: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []

    bounty = next(
        (
            award
            for award in policy["allocations"]["bounties"]["awards"]
            if award["challenge_source_id"] == solve["challenge_source_id"]
        ),
        None,
    )
    if bounty is not None:
        selected, proof = _select_ordered(
            connection,
            event=event,
            occurrence=occurrence,
            slots=[bounty["slot_id"]],
            candidates=[solve["participant_id"]],
            selector=f"bounty:{solve['challenge_source_id']}",
            reason="first accepted bounty solve",
        )
        allocations.extend(selected)
        proofs.append(proof)

    stage_row = next(
        (
            row
            for row in snapshot["stage_results"][occurrence["stage"]]
            if row["participant_id"] == solve["participant_id"]
        ),
        None,
    )
    if (
        stage_row is not None
        and stage_row["completing_submission_id"] == solve["submission_id"]
    ):
        slots = _open_slots(
            connection,
            event_id=event["event_id"],
            family="stage_completion",
            scope=occurrence["stage"],
        )
        if slots:
            selected, proof = _select_ordered(
                connection,
                event=event,
                occurrence=occurrence,
                slots=slots[:1],
                candidates=[solve["participant_id"]],
                selector=f"stage_completion:{occurrence['stage']}",
                reason="completed every bound stage challenge",
            )
            allocations.extend(selected)
            proofs.append(proof)
    return allocations, proofs


def _stage_close_selection(
    connection: sqlite3.Connection,
    *,
    snapshot: dict[str, Any],
    occurrence: dict[str, Any],
    seed: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event = snapshot["event"]
    stage = occurrence["stage"]
    stage_rows = snapshot["stage_results"][stage]
    candidates = [row["participant_id"] for row in stage_rows if row["solve_count"] > 0]
    allocations: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    completion_slots = _open_slots(
        connection,
        event_id=event["event_id"],
        family="stage_completion",
        scope=stage,
    )
    if completion_slots:
        selected, proof = _select_ordered(
            connection,
            event=event,
            occurrence=occurrence,
            slots=completion_slots,
            candidates=candidates,
            selector=f"stage_score:{stage}",
            reason="stage-completion shortfall filled by stage score",
        )
        allocations.extend(selected)
        proofs.append(proof)

    draw_slots = _open_slots(
        connection,
        event_id=event["event_id"],
        family="stage_draws",
        scope=stage,
    )
    if draw_slots:
        selected, proof = _select_draw(
            connection,
            event=event,
            occurrence=occurrence,
            slots=draw_slots,
            candidates=candidates,
            selector=f"stage_draw:{stage}",
            reason="deterministic stage drawing",
            seed=seed,
        )
        allocations.extend(selected)
        proofs.append(proof)
    return allocations, proofs


def _nomination_close_selection(
    connection: sqlite3.Connection,
    *,
    snapshot: dict[str, Any],
    occurrence: dict[str, Any],
    nominations: list[dict[str, str]],
    seed: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event = snapshot["event"]
    slots = _open_slots(
        connection,
        event_id=event["event_id"],
        family="good_citizen",
    )
    counts = Counter(row["nominee_id"] for row in nominations)
    allocations: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    for selector, candidates, reason in (
        (
            "good_citizen:two_plus",
            [participant_id for participant_id, count in counts.items() if count >= 2],
            "two or more distinct peer nominations",
        ),
        (
            "good_citizen:one",
            [participant_id for participant_id, count in counts.items() if count == 1],
            "one distinct peer nomination rollover",
        ),
    ):
        if not slots:
            break
        selected, proof = _select_draw(
            connection,
            event=event,
            occurrence=occurrence,
            slots=slots,
            candidates=candidates,
            selector=selector,
            reason=reason,
            seed=seed,
        )
        allocations.extend(selected)
        proofs.append(proof)
        slots = _open_slots(
            connection,
            event_id=event["event_id"],
            family="good_citizen",
        )
    return allocations, proofs


def _event_close_selection(
    connection: sqlite3.Connection,
    *,
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    occurrence: dict[str, Any],
    seed: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event = snapshot["event"]
    allocations: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    overall_slots = _open_slots(
        connection,
        event_id=event["event_id"],
        family="overall_leaders",
    )
    ranking = [row["participant_id"] for row in snapshot["overall_ranking"]]
    selected, proof = _select_ordered(
        connection,
        event=event,
        occurrence=occurrence,
        slots=overall_slots,
        candidates=ranking,
        selector="overall_rank",
        reason="overall ranking with prior-winner roll-down",
    )
    allocations.extend(selected)
    proofs.append(proof)

    source_stage = {
        source_id: stage
        for stage in STAGES
        for source_id in policy["stages"][stage]["challenge_source_ids"]
    }
    participant_stages: dict[str, set[str]] = {}
    for solve in snapshot["accepted_solves"]:
        participant_stages.setdefault(solve["participant_id"], set()).add(
            source_stage[solve["challenge_source_id"]]
        )
    passport_candidates = [
        participant_id
        for participant_id, stages in participant_stages.items()
        if stages == set(STAGES)
    ]
    passport_slots = _open_slots(
        connection,
        event_id=event["event_id"],
        family="passport_draw",
    )
    selected, proof = _select_draw(
        connection,
        event=event,
        occurrence=occurrence,
        slots=passport_slots,
        candidates=passport_candidates,
        selector="passport_draw",
        reason="accepted solve in all three stages",
        seed=seed,
    )
    allocations.extend(selected)
    proofs.append(proof)
    return allocations, proofs


def _finalization_selection(
    connection: sqlite3.Connection,
    *,
    snapshot: dict[str, Any],
    occurrence: dict[str, Any],
    seed: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event = snapshot["event"]
    slots = _open_slots(connection, event_id=event["event_id"])
    eligible = {
        row["participant_id"]
        for row in snapshot["participants"]
        if row["prize_eligible"]
    }
    prior_attempts = _previously_allocated(connection, event["event_id"])
    solvers = [
        participant_id
        for participant_id in {
            solve["participant_id"] for solve in snapshot["accepted_solves"]
        }
        if participant_id in eligible and participant_id not in prior_attempts
    ]
    selected, proof = _select_draw(
        connection,
        event=event,
        occurrence=occurrence,
        slots=slots,
        candidates=solvers,
        selector="final_solver_draw",
        reason="final rollover among eligible solvers",
        seed=seed,
    )
    return selected, [proof]


def _evaluate_occurrence(
    connection: sqlite3.Connection,
    *,
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    occurrence: dict[str, Any],
    nominations: list[dict[str, str]],
    seed: bytes,
) -> dict[str, Any]:
    event = snapshot["event"]
    input_digest = _occurrence_input_digest(
        occurrence, snapshot=snapshot, nominations=nominations
    )
    stored = connection.execute(
        "SELECT trigger, stage, scheduled_for, executed_at, input_digest, result_json "
        "FROM evaluation_occurrence WHERE event_id = ? AND occurrence_id = ?",
        (event["event_id"], occurrence["occurrence_id"]),
    ).fetchone()
    identity = (
        occurrence["trigger"],
        occurrence["stage"],
        occurrence["scheduled_for"],
        occurrence["executed_at"],
        input_digest,
    )
    if stored is not None:
        if tuple(stored)[:5] != identity:
            raise PrizeEvaluationError(
                "evaluation occurrence identity or input changed"
            )
        return json.loads(stored["result_json"])

    connection.execute(
        "INSERT INTO evaluation_occurrence "
        "(event_id, occurrence_id, trigger, stage, scheduled_for, executed_at, "
        "input_digest, result_json, result_digest) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event["event_id"],
            occurrence["occurrence_id"],
            occurrence["trigger"],
            occurrence["stage"],
            occurrence["scheduled_for"],
            occurrence["executed_at"],
            input_digest,
            "{}",
            "pending",
        ),
    )

    trigger = occurrence["trigger"]
    if trigger == "accepted_solve":
        allocations, proofs = _accepted_solve_selection(
            connection,
            policy=policy,
            snapshot=snapshot,
            occurrence=occurrence,
        )
    elif trigger == "stage_closed":
        allocations, proofs = _stage_close_selection(
            connection,
            snapshot=snapshot,
            occurrence=occurrence,
            seed=seed,
        )
    elif trigger == "nomination_closed":
        allocations, proofs = _nomination_close_selection(
            connection,
            snapshot=snapshot,
            occurrence=occurrence,
            nominations=nominations,
            seed=seed,
        )
    elif trigger == "event_closed":
        allocations, proofs = _event_close_selection(
            connection,
            policy=policy,
            snapshot=snapshot,
            occurrence=occurrence,
            seed=seed,
        )
    elif trigger == "finalization":
        allocations, proofs = _finalization_selection(
            connection,
            snapshot=snapshot,
            occurrence=occurrence,
            seed=seed,
        )
    else:  # pragma: no cover - the input validator closes this enum
        raise PrizeEvaluationError("unknown evaluation trigger")

    result = {
        "occurrence_id": occurrence["occurrence_id"],
        "trigger": trigger,
        "stage": occurrence["stage"],
        "allocations": allocations,
        "proofs": proofs,
        "open_slot_count": len(_open_slots(connection, event_id=event["event_id"])),
    }
    result_json = prize_inputs.canonical_json_bytes(result).decode().rstrip("\n")
    result_digest = prize_inputs.artifact_digest(result)
    connection.execute(
        "UPDATE evaluation_occurrence SET result_json = ?, result_digest = ? "
        "WHERE event_id = ? AND occurrence_id = ?",
        (
            result_json,
            result_digest,
            event["event_id"],
            occurrence["occurrence_id"],
        ),
    )
    return result


def evaluate_snapshot(
    *,
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    state_path: Path,
    seed: bytes,
    nomination_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile every authoritative occurrence into durable prize state."""

    try:
        prize_inputs.validate_prize_input(policy, snapshot)
    except prize_inputs.PrizeInputError as error:
        raise PrizeEvaluationError(str(error)) from error
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise PrizeEvaluationError("draw seed must contain exactly 32 bytes")
    slots = _policy_slots(policy)
    nominations = _normalize_nominations(nomination_input, snapshot=snapshot)
    solves = {row["submission_id"]: row for row in snapshot["accepted_solves"]}
    occurrences = sorted(
        snapshot["occurrences"],
        key=lambda row: _occurrence_sort_key(row, solves),
    )
    solve_occurrence_ids = {
        row["submission_id"]
        for row in occurrences
        if row["trigger"] == "accepted_solve"
    }

    connection = _connect(state_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _bind_event(
            connection,
            event=snapshot["event"],
            policy=policy,
            slots=slots,
            seed=seed,
        )
        results = []
        for occurrence in occurrences:
            _require_prior_solve_occurrences(
                occurrence,
                snapshot=snapshot,
                solve_occurrence_ids=solve_occurrence_ids,
            )
            results.append(
                _evaluate_occurrence(
                    connection,
                    policy=policy,
                    snapshot=snapshot,
                    occurrence=occurrence,
                    nominations=nominations,
                    seed=seed,
                )
            )
        connection.commit()
    except (
        PrizeEvaluationError,
        sqlite3.Error,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        connection.rollback()
        if isinstance(error, PrizeEvaluationError):
            raise
        raise PrizeEvaluationError("prize evaluation failed closed") from error
    finally:
        connection.close()
    allocations = active_allocations(state_path, snapshot["event"]["event_id"])
    return {
        "event_id": snapshot["event"]["event_id"],
        "policy_digest": snapshot["event"]["policy_digest"],
        "occurrences": results,
        "active_allocations": allocations,
        "active_allocation_count": len(allocations),
        "open_slot_count": 50 - len(allocations),
    }


def active_allocations(state_path: Path, event_id: str) -> list[dict[str, Any]]:
    """Return operator-only active allocation facts in stable slot order."""

    connection = _connect(state_path)
    try:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT attempt.slot_id, attempt.generation, attempt.participant_id, "
                "attempt.occurrence_id, attempt.selector, attempt.selection_reason, "
                "attempt.eligibility_digest, attempt.draw_rank, attempt.selected_at "
                "FROM allocation_attempt AS attempt "
                "JOIN prize_slot AS slot ON slot.event_id = attempt.event_id "
                "AND slot.slot_id = attempt.slot_id "
                "WHERE attempt.event_id = ? AND attempt.status = 'selected' "
                "ORDER BY slot.slot_order",
                (_uuid_text(event_id, "event_id"),),
            )
        ]
    finally:
        connection.close()


def void_allocation(
    *,
    state_path: Path,
    event_id: str,
    slot_id: str,
    reason: str,
    voided_at: str,
) -> dict[str, Any]:
    """Void one live allocation without deleting its generation or proof."""

    if (
        not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > MAX_REASON_LENGTH
    ):
        raise PrizeEvaluationError(
            "void reason is required and must be at most 500 characters"
        )
    normalized_time, _parsed = _utc(voided_at, "voided_at")
    normalized_event_id = _uuid_text(event_id, "event_id")
    connection = _connect(state_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT generation, participant_id FROM allocation_attempt "
            "WHERE event_id = ? AND slot_id = ? AND status = 'selected'",
            (normalized_event_id, slot_id),
        ).fetchone()
        if row is None:
            raise PrizeEvaluationError("slot has no live allocation to void")
        connection.execute(
            "UPDATE allocation_attempt SET status = 'voided', voided_at = ?, void_reason = ? "
            "WHERE event_id = ? AND slot_id = ? AND generation = ?",
            (
                normalized_time,
                reason.strip(),
                normalized_event_id,
                slot_id,
                row["generation"],
            ),
        )
        connection.commit()
        return {
            "slot_id": slot_id,
            "generation": row["generation"],
            "participant_id": row["participant_id"],
            "voided_at": normalized_time,
            "reason": reason.strip(),
        }
    except (PrizeEvaluationError, sqlite3.Error, ValueError) as error:
        connection.rollback()
        if isinstance(error, PrizeEvaluationError):
            raise
        raise PrizeEvaluationError("allocation void failed closed") from error
    finally:
        connection.close()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PrizeEvaluationError(f"cannot load {label}: {path}") from error
    if not isinstance(value, dict):
        raise PrizeEvaluationError(f"{label} must be a JSON object")
    return value


def _load_seed(path: Path) -> bytes:
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise PrizeEvaluationError(
                "draw seed file must be owner-only and not a symbolic link"
            )
        value = bytes.fromhex(path.read_text(encoding="ascii").strip())
    except PrizeEvaluationError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise PrizeEvaluationError(
            "draw seed file must contain 64 hexadecimal characters"
        ) from error
    if len(value) != 32:
        raise PrizeEvaluationError(
            "draw seed file must contain 64 hexadecimal characters"
        )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--seed-file", required=True, type=Path)
    parser.add_argument("--nominations", type=Path)
    arguments = parser.parse_args()
    policy = _load_object(arguments.policy, "prize policy")
    snapshot = _load_object(arguments.input, "prize input")
    nominations = (
        _load_object(arguments.nominations, "nominations")
        if arguments.nominations is not None
        else None
    )
    result = evaluate_snapshot(
        policy=policy,
        snapshot=snapshot,
        state_path=arguments.state,
        seed=_load_seed(arguments.seed_file),
        nomination_input=nominations,
    )
    print(
        json.dumps(
            {
                "event_id": result["event_id"],
                "policy_digest": result["policy_digest"],
                "processed_occurrence_count": len(result["occurrences"]),
                "active_allocation_count": result["active_allocation_count"],
                "open_slot_count": result["open_slot_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "NOMINATIONS_CONTRACT",
    "PrizeEvaluationError",
    "active_allocations",
    "evaluate_snapshot",
    "seed_commitment",
    "void_allocation",
]
