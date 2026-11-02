#!/usr/bin/env python3
"""Build the closed, authoritative input snapshot for event-prize evaluation."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from uuid import UUID


CONTRACT = "cinder-typhoon.event-prize-input/v1"
SOURCE_CONTRACT = "cinder-typhoon.authoritative-prize-source/v1"
POLICY_CONTRACT = "cinder-typhoon.event-prize-policy/v1"
STAGES = ("training", "keplerops", "arwc")
TRIGGERS = (
    "accepted_solve",
    "stage_closed",
    "nomination_closed",
    "event_closed",
    "finalization",
)
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
CATALOG_REVISION = re.compile(r"^[0-9a-f]{64}$")
SOURCE_ID = re.compile(r"^[tkw][0-9]{2}\.[0-9]+$")

SOURCE_FIELDS = {
    "contract",
    "event",
    "participants",
    "submissions",
    "ranking",
    "occurrences",
}
SOURCE_EVENT_FIELDS = {
    "event_id",
    "team_mode",
    "status",
    "event_start",
    "event_end",
    "snapshot_at",
    "content_bundle_digest",
    "policy_digest",
    "boundaries",
}
BOUNDARY_FIELDS = {
    "stage_close_at",
    "nomination_open_at",
    "nomination_close_at",
    "claim_deadline_at",
    "finalize_at",
    "draw_seed_commitment",
}
SOURCE_PARTICIPANT_FIELDS = {
    "event_id",
    "participant_id",
    "public_alias",
    "prize_eligible",
}
SOURCE_SUBMISSION_FIELDS = {
    "event_id",
    "submission_id",
    "participant_id",
    "challenge_source_id",
    "is_correct",
    "points_awarded",
    "submitted_at",
}
SOURCE_RANKING_FIELDS = {
    "event_id",
    "participant_id",
    "score",
    "solve_count",
    "last_solve_at",
}
SOURCE_OCCURRENCE_FIELDS = {
    "event_id",
    "occurrence_id",
    "trigger",
    "stage",
    "submission_id",
    "scheduled_for",
    "executed_at",
}

OUTPUT_FIELDS = {
    "contract",
    "event",
    "participants",
    "accepted_solves",
    "overall_ranking",
    "stage_results",
    "occurrences",
}
OUTPUT_EVENT_FIELDS = SOURCE_EVENT_FIELDS - {"team_mode"} | {"catalog_revision"}
OUTPUT_PARTICIPANT_FIELDS = SOURCE_PARTICIPANT_FIELDS - {"event_id"}
OUTPUT_SOLVE_FIELDS = {
    "submission_id",
    "participant_id",
    "challenge_source_id",
    "points",
    "accepted_at",
}
OUTPUT_RANKING_FIELDS = SOURCE_RANKING_FIELDS - {"event_id"} | {"position"}
OUTPUT_OCCURRENCE_FIELDS = SOURCE_OCCURRENCE_FIELDS - {"event_id"}
OUTPUT_STAGE_RESULT_FIELDS = {
    "participant_id",
    "score",
    "solve_count",
    "score_reached_at",
    "completed_at",
    "completing_submission_id",
}


class PrizeInputError(ValueError):
    """The authoritative prize input is incomplete, inconsistent, or unsafe."""


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    """Encode one operator artifact deterministically."""

    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def artifact_digest(value: dict[str, Any]) -> str:
    """Return the SHA-256 identifier for the exact canonical artifact bytes."""

    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def _closed(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise PrizeInputError(f"{label} has invalid fields")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PrizeInputError(f"{label} must be a list")
    return value


def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PrizeInputError(f"{label} must be a UUID")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise PrizeInputError(f"{label} must be a UUID") from error


def _utc(value: Any, label: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        raise PrizeInputError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PrizeInputError(f"{label} must be a UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PrizeInputError(f"{label} must be a UTC timestamp")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _nullable_utc(value: Any, label: str) -> tuple[str | None, datetime | None]:
    if value is None:
        return None, None
    return _utc(value, label)


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        qualifier = f" at least {minimum}" if minimum is not None else ""
        raise PrizeInputError(f"{label} must be an integer{qualifier}")
    return value


def _deduplicate(
    rows: list[dict[str, Any]],
    *,
    key: str,
    label: str,
) -> list[dict[str, Any]]:
    """Collapse byte-equivalent retries and reject identity reuse with drift."""

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = row[key]
        prior = result.get(identity)
        if prior is not None and prior != row:
            raise PrizeInputError(f"conflicting duplicate {label}: {identity}")
        result[identity] = row
    return list(result.values())


def _validate_policy(policy: Any) -> tuple[dict[str, set[str]], str]:
    if not isinstance(policy, dict) or policy.get("contract") != POLICY_CONTRACT:
        raise PrizeInputError("prize policy identity is invalid")
    catalog = policy.get("catalog")
    if not isinstance(catalog, dict):
        raise PrizeInputError("prize policy catalog binding is invalid")
    revision = catalog.get("revision")
    content_digest = catalog.get("content_bundle_digest")
    if not isinstance(revision, str) or not CATALOG_REVISION.fullmatch(revision):
        raise PrizeInputError("prize policy catalog revision is invalid")
    if not isinstance(content_digest, str) or not SHA256.fullmatch(content_digest):
        raise PrizeInputError("prize policy content digest is invalid")

    stages = policy.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        raise PrizeInputError("prize policy stages are incomplete")
    result: dict[str, set[str]] = {}
    all_source_ids: set[str] = set()
    for stage in STAGES:
        stage_policy = stages[stage]
        if not isinstance(stage_policy, dict):
            raise PrizeInputError(f"{stage}: prize policy stage is invalid")
        values = stage_policy.get("challenge_source_ids")
        if not isinstance(values, list) or not values:
            raise PrizeInputError(f"{stage}: prize policy source IDs are missing")
        normalized = []
        for value in values:
            if not isinstance(value, str) or not SOURCE_ID.fullmatch(value):
                raise PrizeInputError(f"{stage}: prize policy source ID is invalid")
            normalized.append(value)
        source_ids = set(normalized)
        if len(source_ids) != len(normalized) or source_ids & all_source_ids:
            raise PrizeInputError("prize policy source IDs are not unique")
        all_source_ids.update(source_ids)
        result[stage] = source_ids
    return result, revision


def _normalize_event(
    policy: dict[str, Any], source_event: Any
) -> tuple[dict[str, Any], dict[str, datetime]]:
    event = _closed(source_event, SOURCE_EVENT_FIELDS, "event")
    event_id = _uuid(event["event_id"], "event.event_id")
    if event["team_mode"] is not False:
        raise PrizeInputError(
            "team-mode events are not supported by this participant prize policy"
        )
    status = event["status"]
    if not isinstance(status, str) or not status or len(status) > 32:
        raise PrizeInputError("event.status is invalid")

    event_start, start_dt = _utc(event["event_start"], "event.event_start")
    event_end, end_dt = _utc(event["event_end"], "event.event_end")
    snapshot_at, snapshot_dt = _utc(event["snapshot_at"], "event.snapshot_at")
    if not start_dt < end_dt or snapshot_dt < start_dt:
        raise PrizeInputError("event time range is invalid")

    stage_sets, catalog_revision = _validate_policy(policy)
    del stage_sets
    content_digest = event["content_bundle_digest"]
    if (
        not isinstance(content_digest, str)
        or not SHA256.fullmatch(content_digest)
        or content_digest != policy["catalog"]["content_bundle_digest"]
    ):
        raise PrizeInputError("event content digest does not match the prize policy")
    policy_digest = event["policy_digest"]
    if (
        not isinstance(policy_digest, str)
        or not SHA256.fullmatch(policy_digest)
        or policy_digest != artifact_digest(policy)
    ):
        raise PrizeInputError(
            "event policy digest does not match the supplied prize policy"
        )

    boundaries = _closed(event["boundaries"], BOUNDARY_FIELDS, "event.boundaries")
    raw_stage_closes = _closed(
        boundaries["stage_close_at"], set(STAGES), "event.boundaries.stage_close_at"
    )
    stage_closes: dict[str, str] = {}
    boundary_times: dict[str, datetime] = {}
    for stage in STAGES:
        value, parsed = _utc(
            raw_stage_closes[stage], f"event.boundaries.stage_close_at.{stage}"
        )
        stage_closes[stage] = value
        boundary_times[f"stage_close_at.{stage}"] = parsed

    normalized_boundaries: dict[str, Any] = {"stage_close_at": stage_closes}
    for name in (
        "nomination_open_at",
        "nomination_close_at",
        "claim_deadline_at",
        "finalize_at",
    ):
        value, parsed = _utc(boundaries[name], f"event.boundaries.{name}")
        normalized_boundaries[name] = value
        boundary_times[name] = parsed
    commitment = boundaries["draw_seed_commitment"]
    if not isinstance(commitment, str) or not SHA256.fullmatch(commitment):
        raise PrizeInputError("event.boundaries.draw_seed_commitment is invalid")
    normalized_boundaries["draw_seed_commitment"] = commitment

    stage_times = [boundary_times[f"stage_close_at.{stage}"] for stage in STAGES]
    if not (
        start_dt < stage_times[0] < stage_times[1] < stage_times[2] <= end_dt
        and start_dt
        <= boundary_times["nomination_open_at"]
        < boundary_times["nomination_close_at"]
        <= end_dt
        <= boundary_times["claim_deadline_at"]
        <= boundary_times["finalize_at"]
    ):
        raise PrizeInputError("event prize boundaries are not in a valid order")

    boundary_times.update(
        {
            "event_start": start_dt,
            "event_end": end_dt,
            "snapshot_at": snapshot_dt,
        }
    )
    return (
        {
            "event_id": event_id,
            "status": status,
            "event_start": event_start,
            "event_end": event_end,
            "snapshot_at": snapshot_at,
            "content_bundle_digest": content_digest,
            "policy_digest": policy_digest,
            "catalog_revision": catalog_revision,
            "boundaries": normalized_boundaries,
        },
        boundary_times,
    )


def _normalize_participants(
    rows: Any, event_id: str
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(_list(rows, "participants")):
        row = _closed(raw, SOURCE_PARTICIPANT_FIELDS, f"participants[{index}]")
        if _uuid(row["event_id"], f"participants[{index}].event_id") != event_id:
            raise PrizeInputError("participant belongs to a different event")
        participant_id = _uuid(
            row["participant_id"], f"participants[{index}].participant_id"
        )
        alias = row["public_alias"]
        if not isinstance(alias, str) or not alias or len(alias) > 100:
            raise PrizeInputError(f"participants[{index}].public_alias is invalid")
        if type(row["prize_eligible"]) is not bool:
            raise PrizeInputError(
                f"participants[{index}].prize_eligible must be a boolean"
            )
        normalized.append(
            {
                "participant_id": participant_id,
                "public_alias": alias,
                "prize_eligible": row["prize_eligible"],
            }
        )
    normalized = _deduplicate(
        normalized, key="participant_id", label="participant identity"
    )
    normalized.sort(key=lambda row: row["participant_id"])
    return normalized, {row["participant_id"]: row for row in normalized}


def _normalize_submissions(
    rows: Any,
    *,
    event_id: str,
    participants: dict[str, dict[str, Any]],
    stage_sets: dict[str, set[str]],
    times: dict[str, datetime],
) -> tuple[list[dict[str, Any]], dict[str, datetime], dict[str, str]]:
    all_source_ids = set().union(*stage_sets.values())
    normalized_rows: list[dict[str, Any]] = []
    parsed_times: dict[str, datetime] = {}
    for index, raw in enumerate(_list(rows, "submissions")):
        row = _closed(raw, SOURCE_SUBMISSION_FIELDS, f"submissions[{index}]")
        if _uuid(row["event_id"], f"submissions[{index}].event_id") != event_id:
            raise PrizeInputError("submission belongs to a different event")
        submission_id = _uuid(
            row["submission_id"], f"submissions[{index}].submission_id"
        )
        participant_id = _uuid(
            row["participant_id"], f"submissions[{index}].participant_id"
        )
        if participant_id not in participants:
            raise PrizeInputError("submission references an unknown participant")
        source_id = row["challenge_source_id"]
        if not isinstance(source_id, str):
            raise PrizeInputError(
                f"submissions[{index}].challenge_source_id is invalid"
            )
        source_id = source_id.lower()
        is_correct = row["is_correct"]
        if type(is_correct) is not bool:
            raise PrizeInputError(f"submissions[{index}].is_correct must be a boolean")
        points = _integer(
            row["points_awarded"],
            f"submissions[{index}].points_awarded",
            minimum=0,
        )
        submitted_at, submitted_dt = _utc(
            row["submitted_at"], f"submissions[{index}].submitted_at"
        )
        normalized_rows.append(
            {
                "submission_id": submission_id,
                "participant_id": participant_id,
                "challenge_source_id": source_id,
                "is_correct": is_correct,
                "points_awarded": points,
                "submitted_at": submitted_at,
            }
        )
        parsed_times[submission_id] = submitted_dt

    normalized_rows = _deduplicate(
        normalized_rows, key="submission_id", label="submission identity"
    )
    accepted: list[dict[str, Any]] = []
    accepted_times: dict[str, datetime] = {}
    logical_solves: dict[tuple[str, str], str] = {}
    submission_stages: dict[str, str] = {}
    effective_end = min(times["snapshot_at"], times["event_end"])
    for row in normalized_rows:
        if not row["is_correct"]:
            continue
        submitted_dt = parsed_times[row["submission_id"]]
        if not times["event_start"] <= submitted_dt < effective_end:
            continue
        source_id = row["challenge_source_id"]
        if source_id not in all_source_ids or not SOURCE_ID.fullmatch(source_id):
            raise PrizeInputError(
                "accepted submission has an unknown challenge source ID"
            )
        logical_key = (row["participant_id"], source_id)
        prior = logical_solves.get(logical_key)
        if prior is not None and prior != row["submission_id"]:
            raise PrizeInputError(
                "multiple accepted submissions exist for one participant challenge"
            )
        logical_solves[logical_key] = row["submission_id"]
        stage = next(name for name, values in stage_sets.items() if source_id in values)
        submission_stages[row["submission_id"]] = stage
        accepted_times[row["submission_id"]] = submitted_dt
        accepted.append(
            {
                "submission_id": row["submission_id"],
                "participant_id": row["participant_id"],
                "challenge_source_id": source_id,
                "points": row["points_awarded"],
                "accepted_at": row["submitted_at"],
            }
        )
    accepted.sort(
        key=lambda row: (
            accepted_times[row["submission_id"]],
            row["submission_id"],
            row["participant_id"],
        )
    )
    return accepted, accepted_times, submission_stages


def _normalize_ranking(
    rows: Any,
    *,
    event_id: str,
    participants: dict[str, dict[str, Any]],
    accepted: list[dict[str, Any]],
    accepted_times: dict[str, datetime],
) -> list[dict[str, Any]]:
    solves_by_participant: dict[str, list[dict[str, Any]]] = {
        participant_id: [] for participant_id in participants
    }
    for solve in accepted:
        solves_by_participant[solve["participant_id"]].append(solve)

    normalized: list[dict[str, Any]] = []
    parsed_last_solve: dict[str, datetime | None] = {}
    for index, raw in enumerate(_list(rows, "ranking")):
        row = _closed(raw, SOURCE_RANKING_FIELDS, f"ranking[{index}]")
        if _uuid(row["event_id"], f"ranking[{index}].event_id") != event_id:
            raise PrizeInputError("ranking row belongs to a different event")
        participant_id = _uuid(
            row["participant_id"], f"ranking[{index}].participant_id"
        )
        participant = participants.get(participant_id)
        if participant is None or not participant["prize_eligible"]:
            raise PrizeInputError(
                "ranking contains an ineligible or unknown participant"
            )
        score = _integer(row["score"], f"ranking[{index}].score")
        solve_count = _integer(
            row["solve_count"], f"ranking[{index}].solve_count", minimum=0
        )
        last_solve_at, last_solve_dt = _nullable_utc(
            row["last_solve_at"], f"ranking[{index}].last_solve_at"
        )
        participant_solves = solves_by_participant[participant_id]
        expected_last = (
            max(accepted_times[solve["submission_id"]] for solve in participant_solves)
            if participant_solves
            else None
        )
        if solve_count != len(participant_solves) or last_solve_dt != expected_last:
            raise PrizeInputError(
                "ranking solve summary differs from accepted submissions"
            )
        normalized.append(
            {
                "participant_id": participant_id,
                "score": score,
                "solve_count": solve_count,
                "last_solve_at": last_solve_at,
            }
        )
        parsed_last_solve[participant_id] = last_solve_dt

    normalized = _deduplicate(
        normalized, key="participant_id", label="ranking participant"
    )
    expected_participants = {
        participant_id
        for participant_id, participant in participants.items()
        if participant["prize_eligible"]
    }
    if {row["participant_id"] for row in normalized} != expected_participants:
        raise PrizeInputError(
            "ranking does not contain exactly the eligible participants"
        )
    normalized.sort(
        key=lambda row: (
            -row["score"],
            parsed_last_solve[row["participant_id"]] is None,
            parsed_last_solve[row["participant_id"]]
            or datetime.max.replace(tzinfo=timezone.utc),
            row["participant_id"],
        )
    )
    return [dict(row, position=index) for index, row in enumerate(normalized, start=1)]


def _derive_stage_results(
    *,
    stage_sets: dict[str, set[str]],
    participants: dict[str, dict[str, Any]],
    accepted: list[dict[str, Any]],
    accepted_times: dict[str, datetime],
    times: dict[str, datetime],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for stage in STAGES:
        cutoff = min(times["snapshot_at"], times[f"stage_close_at.{stage}"])
        by_participant: dict[str, list[dict[str, Any]]] = {}
        for solve in accepted:
            participant = participants[solve["participant_id"]]
            if (
                participant["prize_eligible"]
                and solve["challenge_source_id"] in stage_sets[stage]
                and accepted_times[solve["submission_id"]] < cutoff
            ):
                by_participant.setdefault(solve["participant_id"], []).append(solve)

        stage_rows: list[dict[str, Any]] = []
        for participant_id, solves in by_participant.items():
            final_solve = max(
                solves,
                key=lambda solve: (
                    accepted_times[solve["submission_id"]],
                    solve["submission_id"],
                ),
            )
            completed = {
                solve["challenge_source_id"] for solve in solves
            } == stage_sets[stage]
            stage_rows.append(
                {
                    "participant_id": participant_id,
                    "score": sum(solve["points"] for solve in solves),
                    "solve_count": len(solves),
                    "score_reached_at": final_solve["accepted_at"],
                    "completed_at": final_solve["accepted_at"] if completed else None,
                    "completing_submission_id": (
                        final_solve["submission_id"] if completed else None
                    ),
                }
            )
        stage_rows.sort(
            key=lambda row: (
                -row["score"],
                _utc(row["score_reached_at"], "stage score timestamp")[1],
                row["participant_id"],
            )
        )
        result[stage] = stage_rows
    return result


def _normalize_occurrences(
    rows: Any,
    *,
    event_id: str,
    accepted_by_id: dict[str, dict[str, Any]],
    accepted_times: dict[str, datetime],
    submission_stages: dict[str, str],
    times: dict[str, datetime],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    parsed_execution: dict[str, datetime] = {}
    for index, raw in enumerate(_list(rows, "occurrences")):
        row = _closed(raw, SOURCE_OCCURRENCE_FIELDS, f"occurrences[{index}]")
        if _uuid(row["event_id"], f"occurrences[{index}].event_id") != event_id:
            raise PrizeInputError("occurrence belongs to a different event")
        occurrence_id = _uuid(
            row["occurrence_id"], f"occurrences[{index}].occurrence_id"
        )
        trigger = row["trigger"]
        if trigger not in TRIGGERS:
            raise PrizeInputError(f"occurrences[{index}].trigger is invalid")
        stage = row["stage"]
        if stage is not None and stage not in STAGES:
            raise PrizeInputError(f"occurrences[{index}].stage is invalid")
        submission_id = row["submission_id"]
        if submission_id is not None:
            submission_id = _uuid(submission_id, f"occurrences[{index}].submission_id")
        scheduled_for, scheduled_dt = _nullable_utc(
            row["scheduled_for"], f"occurrences[{index}].scheduled_for"
        )
        executed_at, executed_dt = _utc(
            row["executed_at"], f"occurrences[{index}].executed_at"
        )
        if executed_dt > times["snapshot_at"]:
            raise PrizeInputError("occurrence execution is later than the snapshot")

        expected_scheduled: datetime | None
        if trigger == "accepted_solve":
            if (
                submission_id is None
                or submission_id not in accepted_by_id
                or occurrence_id != submission_id
                or stage != submission_stages[submission_id]
                or scheduled_dt is not None
                or executed_dt < accepted_times[submission_id]
            ):
                raise PrizeInputError(
                    "accepted-solve occurrence is not bound to its submission"
                )
            expected_scheduled = None
        elif trigger == "stage_closed":
            if stage is None or submission_id is not None:
                raise PrizeInputError("stage-close occurrence is invalid")
            expected_scheduled = times[f"stage_close_at.{stage}"]
        else:
            if stage is not None or submission_id is not None:
                raise PrizeInputError(f"{trigger} occurrence has an invalid scope")
            expected_scheduled = {
                "nomination_closed": times["nomination_close_at"],
                "event_closed": times["event_end"],
                "finalization": times["finalize_at"],
            }[trigger]
        if expected_scheduled is not None and (
            scheduled_dt != expected_scheduled or executed_dt < expected_scheduled
        ):
            raise PrizeInputError(
                f"{trigger} occurrence does not match its authoritative boundary"
            )

        normalized.append(
            {
                "occurrence_id": occurrence_id,
                "trigger": trigger,
                "stage": stage,
                "submission_id": submission_id,
                "scheduled_for": scheduled_for,
                "executed_at": executed_at,
            }
        )
        parsed_execution[occurrence_id] = executed_dt

    normalized = _deduplicate(
        normalized, key="occurrence_id", label="evaluation occurrence"
    )
    semantic_keys: dict[tuple[str, str | None, str | None], str] = {}
    for row in normalized:
        key = (row["trigger"], row["stage"], row["submission_id"])
        prior = semantic_keys.get(key)
        if prior is not None and prior != row["occurrence_id"]:
            raise PrizeInputError(
                "multiple occurrence identities exist for one trigger"
            )
        semantic_keys[key] = row["occurrence_id"]

    close_keys = {(row["trigger"], row["stage"]) for row in normalized}
    if ("event_closed", None) in close_keys:
        required = {("stage_closed", stage) for stage in STAGES}
        required.add(("nomination_closed", None))
        if not required.issubset(close_keys):
            raise PrizeInputError("event close is missing an earlier close occurrence")
    if ("finalization", None) in close_keys and (
        "event_closed",
        None,
    ) not in close_keys:
        raise PrizeInputError("finalization is missing the event-close occurrence")

    normalized.sort(
        key=lambda row: (
            parsed_execution[row["occurrence_id"]],
            TRIGGERS.index(row["trigger"]),
            row["occurrence_id"],
        )
    )
    return normalized


def build_prize_input(policy: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, least-privilege snapshot from authoritative facts.

    The caller must obtain ``source`` through an organizer-authorized internal
    projection or export. This function deliberately has no browser, webhook,
    network, or database fallback.
    """

    source = _closed(source, SOURCE_FIELDS, "authoritative source")
    if source["contract"] != SOURCE_CONTRACT:
        raise PrizeInputError("authoritative source contract is invalid")
    stage_sets, _catalog_revision = _validate_policy(policy)
    event, times = _normalize_event(policy, source["event"])
    participants, participants_by_id = _normalize_participants(
        source["participants"], event["event_id"]
    )
    accepted, accepted_times, submission_stages = _normalize_submissions(
        source["submissions"],
        event_id=event["event_id"],
        participants=participants_by_id,
        stage_sets=stage_sets,
        times=times,
    )
    ranking = _normalize_ranking(
        source["ranking"],
        event_id=event["event_id"],
        participants=participants_by_id,
        accepted=accepted,
        accepted_times=accepted_times,
    )
    stage_results = _derive_stage_results(
        stage_sets=stage_sets,
        participants=participants_by_id,
        accepted=accepted,
        accepted_times=accepted_times,
        times=times,
    )
    accepted_by_id = {row["submission_id"]: row for row in accepted}
    occurrences = _normalize_occurrences(
        source["occurrences"],
        event_id=event["event_id"],
        accepted_by_id=accepted_by_id,
        accepted_times=accepted_times,
        submission_stages=submission_stages,
        times=times,
    )
    return {
        "contract": CONTRACT,
        "event": event,
        "participants": participants,
        "accepted_solves": accepted,
        "overall_ranking": ranking,
        "stage_results": stage_results,
        "occurrences": occurrences,
    }


def validate_prize_input(policy: dict[str, Any], snapshot: dict[str, Any]) -> None:
    """Rebuild and compare a published snapshot, rejecting any mutation."""

    try:
        snapshot = _closed(snapshot, OUTPUT_FIELDS, "prize input snapshot")
        if snapshot["contract"] != CONTRACT:
            raise PrizeInputError("prize input contract is invalid")
        event = _closed(snapshot["event"], OUTPUT_EVENT_FIELDS, "snapshot event")
        participants = [
            _closed(row, OUTPUT_PARTICIPANT_FIELDS, "snapshot participant")
            for row in _list(snapshot["participants"], "snapshot participants")
        ]
        accepted = [
            _closed(row, OUTPUT_SOLVE_FIELDS, "snapshot accepted solve")
            for row in _list(snapshot["accepted_solves"], "snapshot accepted solves")
        ]
        ranking = [
            _closed(row, OUTPUT_RANKING_FIELDS, "snapshot ranking row")
            for row in _list(snapshot["overall_ranking"], "snapshot overall ranking")
        ]
        occurrences = [
            _closed(row, OUTPUT_OCCURRENCE_FIELDS, "snapshot occurrence")
            for row in _list(snapshot["occurrences"], "snapshot occurrences")
        ]
        stage_results = _closed(
            snapshot["stage_results"], set(STAGES), "snapshot stage results"
        )
        for stage in STAGES:
            for row in _list(stage_results[stage], f"snapshot stage results {stage}"):
                _closed(
                    row, OUTPUT_STAGE_RESULT_FIELDS, f"snapshot stage result {stage}"
                )

        event_id = event["event_id"]
        source = {
            "contract": SOURCE_CONTRACT,
            "event": {
                key: deepcopy(value)
                for key, value in event.items()
                if key != "catalog_revision"
            }
            | {"team_mode": False},
            "participants": [dict(row, event_id=event_id) for row in participants],
            "submissions": [
                {
                    "event_id": event_id,
                    "submission_id": row["submission_id"],
                    "participant_id": row["participant_id"],
                    "challenge_source_id": row["challenge_source_id"],
                    "is_correct": True,
                    "points_awarded": row["points"],
                    "submitted_at": row["accepted_at"],
                }
                for row in accepted
            ],
            "ranking": [
                {key: value for key, value in row.items() if key != "position"}
                | {"event_id": event_id}
                for row in ranking
            ],
            "occurrences": [dict(row, event_id=event_id) for row in occurrences],
        }
        rebuilt = build_prize_input(policy, source)
    except (KeyError, TypeError) as error:
        raise PrizeInputError("prize input snapshot is malformed") from error
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(snapshot):
        raise PrizeInputError(
            "prize input snapshot differs from its authoritative rebuild"
        )


def write_private_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically write one operator-only snapshot with owner-only permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(value))
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PrizeInputError(f"cannot load {label}: {path}") from error
    if not isinstance(value, dict):
        raise PrizeInputError(f"{label} must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    policy = _load_object(arguments.policy, "prize policy")
    source = _load_object(arguments.source, "authoritative source")
    snapshot = build_prize_input(policy, source)
    validate_prize_input(policy, snapshot)
    write_private_json(arguments.output, snapshot)
    print(
        json.dumps(
            {
                "event_id": snapshot["event"]["event_id"],
                "prize_input_digest": artifact_digest(snapshot),
                "accepted_solve_count": len(snapshot["accepted_solves"]),
                "participant_count": len(snapshot["participants"]),
                "occurrence_count": len(snapshot["occurrences"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONTRACT",
    "PrizeInputError",
    "SOURCE_CONTRACT",
    "artifact_digest",
    "build_prize_input",
    "canonical_json_bytes",
    "validate_prize_input",
    "write_private_json",
]
