#!/usr/bin/env python3
"""Qualify the complete Cinder Typhoon 50-prize lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_CANDIDATE = HERE / "candidate.json"
DEFAULT_SUMMARY = HERE / "summary.json"
ORIGIN = "https://event.example.test"
PARTICIPANT_COUNT = 320
INITIAL_CLAIM_COUNT = 25
FIXTURE_CLAIM_HMAC_KEY = hashlib.sha256(b"cinder-prize-qualification-fixture").digest()
FIXTURE_NOMINATION_HMAC_KEY = hashlib.sha256(
    b"cinder-nomination-qualification-fixture"
).digest()
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
AUTOMATION_PATHS = (
    "challenges/challenges.yaml",
    "challenges/catalog.py",
    "ctfd/import_catalog.py",
    "ctfd/prize_policy.py",
    "ctfd/prize_inputs.py",
    "ctfd/prize_evaluator.py",
    "ctfd/prize_nominations.py",
    "ctfd/prize_claims.py",
    "ctfd/prize_ui.py",
    "docs/design/event-prize-input.schema.json",
    "docs/design/event-prize-policy.schema.json",
    "build/participant-surface/manifests/training.json",
    "build/participant-surface/manifests/keplerops.json",
    "build/participant-surface/manifests/arwc.json",
    "tests/test_prize_evaluator.py",
    "build/prize-qualification/qualify.py",
)


class QualificationError(ValueError):
    """The staging candidate cannot prove a release assertion."""


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


event_importer = _load_module(
    "cinder_prize_qualification_importer", ROOT / "ctfd" / "import_catalog.py"
)
prize_inputs = _load_module(
    "cinder_prize_qualification_inputs", ROOT / "ctfd" / "prize_inputs.py"
)
prize_evaluator = _load_module(
    "cinder_prize_qualification_evaluator", ROOT / "ctfd" / "prize_evaluator.py"
)
prize_nominations = _load_module(
    "cinder_prize_qualification_nominations",
    ROOT / "ctfd" / "prize_nominations.py",
)
prize_ui = _load_module("cinder_prize_qualification_ui", ROOT / "ctfd" / "prize_ui.py")
test_fixture = _load_module(
    "cinder_prize_qualification_fixture", ROOT / "tests" / "test_prize_evaluator.py"
)
prize_claims = prize_ui.prize_claims


def _id(value: int) -> str:
    return str(UUID(int=value))


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_stamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _artifact_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_bytes(value))
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class StagingFixture:
    """A deterministic 320-participant authoritative event projection."""

    def __init__(self) -> None:
        base = test_fixture.PrizeEvaluatorFixture()
        self.catalog = base.catalog
        self.bundle = event_importer.build_event_bundle(
            self.catalog,
            scorer_origin="https://cinder-scorer.example.test",
        )
        self.bundle_digest = event_importer.artifact_digest(self.bundle)
        self.policy = base.policy
        self.seed = test_fixture.SEED
        self.event_id = test_fixture.EVENT_ID
        if self.policy["catalog"]["content_bundle_digest"] != self.bundle_digest:
            raise QualificationError("policy is not bound to the participant bundle")
        self.participant_ids = [_id(index) for index in range(1, PARTICIPANT_COUNT + 1)]
        self.source = self._expand_source(base.source)
        self.full_snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        prefinal_source = deepcopy(self.source)
        prefinal_source["occurrences"] = [
            row
            for row in prefinal_source["occurrences"]
            if row["trigger"] != "finalization"
        ]
        self.prefinal_snapshot = prize_inputs.build_prize_input(
            self.policy,
            prefinal_source,
        )

    def _expand_source(self, base_source: dict[str, Any]) -> dict[str, Any]:
        source = deepcopy(base_source)
        source["participants"].extend(
            {
                "event_id": self.event_id,
                "participant_id": participant_id,
                "public_alias": f"Player {index:03d}",
                "prize_eligible": True,
            }
            for index, participant_id in enumerate(
                self.participant_ids[100:],
                start=101,
            )
        )
        stage_ids = {
            stage: self.policy["stages"][stage]["challenge_source_ids"]
            for stage in ("training", "keplerops", "arwc")
        }
        starts = {
            "training": datetime(2026, 6, 1, 9, 45, tzinfo=UTC),
            "keplerops": datetime(2026, 6, 1, 10, 45, tzinfo=UTC),
            "arwc": datetime(2026, 6, 1, 11, 45, tzinfo=UTC),
        }
        added_submissions = []
        added_occurrences = []
        for participant_number in range(101, PARTICIPANT_COUNT + 1):
            participant_id = self.participant_ids[participant_number - 1]
            for stage_offset, stage in enumerate(("training", "keplerops", "arwc")):
                submission_id = _id(3_000_000 + participant_number * 10 + stage_offset)
                submitted = starts[stage] + timedelta(seconds=participant_number % 4)
                submission = {
                    "event_id": self.event_id,
                    "submission_id": submission_id,
                    "participant_id": participant_id,
                    "challenge_source_id": stage_ids[stage][1],
                    "is_correct": True,
                    "points_awarded": 10,
                    "submitted_at": _stamp(submitted),
                }
                added_submissions.append(submission)
                added_occurrences.append(
                    {
                        "event_id": self.event_id,
                        "occurrence_id": submission_id,
                        "trigger": "accepted_solve",
                        "stage": stage,
                        "submission_id": submission_id,
                        "scheduled_for": None,
                        "executed_at": _stamp(submitted + timedelta(seconds=2)),
                    }
                )
        added_submissions.append(
            {
                "event_id": self.event_id,
                "submission_id": _id(3_999_999),
                "participant_id": self.participant_ids[-1],
                "challenge_source_id": stage_ids["training"][2],
                "is_correct": True,
                "points_awarded": 10,
                "submitted_at": "2026-06-01T12:00:00Z",
            }
        )
        source["submissions"].extend(added_submissions)
        source["occurrences"].extend(added_occurrences)

        histories: dict[str, list[dict[str, Any]]] = {
            participant_id: [] for participant_id in self.participant_ids
        }
        for submission in source["submissions"]:
            histories[submission["participant_id"]].append(submission)

        def replay(participant_id: str) -> list[dict[str, Any]]:
            return deepcopy(histories[participant_id])

        with ThreadPoolExecutor(max_workers=32) as executor:
            replayed = list(executor.map(replay, self.participant_ids))
        source["submissions"] = [
            row
            for history in replayed
            for row in sorted(history, key=lambda item: item["submission_id"])
        ]
        source["ranking"] = self._ranking(source)
        return source

    def _ranking(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        start = _parse_stamp(source["event"]["event_start"])
        end = _parse_stamp(source["event"]["event_end"])
        solves: dict[str, list[dict[str, Any]]] = {
            participant_id: [] for participant_id in self.participant_ids
        }
        for submission in source["submissions"]:
            submitted = _parse_stamp(submission["submitted_at"])
            if submission["is_correct"] and start <= submitted < end:
                solves[submission["participant_id"]].append(submission)
        return [
            {
                "event_id": self.event_id,
                "participant_id": participant_id,
                "score": sum(row["points_awarded"] for row in solves[participant_id]),
                "solve_count": len(solves[participant_id]),
                "last_solve_at": max(
                    (row["submitted_at"] for row in solves[participant_id]),
                    default=None,
                ),
            }
            for participant_id in reversed(self.participant_ids)
        ]


def build_candidate(fixture: StagingFixture) -> dict[str, Any]:
    """Pin every source used by the staging rehearsal."""

    return {
        "contract": "cinder-typhoon.prize-qualification-candidate/v1",
        "candidate_id": "cinder-prize-staging-v1",
        "participant_history_count": PARTICIPANT_COUNT,
        "catalog": {
            "revision": fixture.catalog["revision"],
            "content_bundle_digest": fixture.bundle_digest,
            "policy_digest": prize_inputs.artifact_digest(fixture.policy),
        },
        "lifecycle": {
            "slot_count": 50,
            "initial_claim_count": INITIAL_CLAIM_COUNT,
            "final_claim_count": 50 - INITIAL_CLAIM_COUNT,
            "numbered_inventory": [1, 50],
        },
        "automation": [
            {"path": relative, "sha256": _file_sha256(ROOT / relative)}
            for relative in AUTOMATION_PATHS
        ],
    }


def validate_candidate(candidate: Any, fixture: StagingFixture) -> None:
    expected = build_candidate(fixture)
    if candidate != expected:
        raise QualificationError("qualification candidate differs from pinned sources")


def _load_candidate(path: Path, fixture: StagingFixture) -> dict[str, Any]:
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationError(
            f"qualification candidate cannot be read: {error}"
        ) from error
    validate_candidate(candidate, fixture)
    return candidate


def _participant_context(participant_id: str) -> Any:
    return prize_ui.AuthenticatedParticipant(
        event_id=test_fixture.EVENT_ID,
        participant_id=participant_id,
        session_id=f"qualification-session-{participant_id}",
        origin=ORIGIN,
    )


def _staff_context() -> Any:
    return prize_ui.AuthenticatedEventStaff(
        event_id=test_fixture.EVENT_ID,
        staff_id="qualification-event-owner",
        can_manage_prizes=True,
        is_event_admin=True,
        origin=ORIGIN,
    )


def _collect_nominations(
    fixture: StagingFixture,
    root: Path,
) -> dict[str, Any]:
    config = prize_nominations.build_nomination_config(
        policy=fixture.policy,
        snapshot=fixture.prefinal_snapshot,
        checked_in_participant_ids=fixture.participant_ids,
        public_origin=ORIGIN,
    )
    service = prize_nominations.NominationService(
        config=config,
        state_path=root / "nominations.sqlite3",
        token_key=FIXTURE_NOMINATION_HMAC_KEY,
    )
    nomination_time = datetime(2026, 6, 1, 10, 30, tzinfo=UTC)
    for offset in range(10):
        nominator = fixture.participant_ids[84 + offset]
        nominee_index = 79 + offset // 2
        nominee_alias = f"Player {nominee_index + 1:03d}"
        context = prize_nominations.AuthenticatedParticipant(
            event_id=fixture.event_id,
            participant_id=nominator,
            session_id=f"nomination-session-{offset}",
            origin=ORIGIN,
        )
        form = service.form(context, now=nomination_time)
        candidate = next(
            row for row in form["candidates"] if row["public_alias"] == nominee_alias
        )
        service.submit(
            context,
            {
                "request_id": _id(4_000_000 + offset),
                "csrf_token": form["csrf_token"],
                "candidate_token": candidate["candidate_token"],
                "attested": True,
            },
            now=nomination_time,
        )
    export = service.close(policy=fixture.policy, snapshot=fixture.prefinal_snapshot)
    if len(export["ballots"]) != 10:
        raise QualificationError(
            "actual nomination component did not close ten ballots"
        )
    return export


class _DeliveryAdapter:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0
        self.failed_key: str | None = None
        self.delivered: set[str] = set()

    def __call__(self, message: dict[str, Any]) -> str:
        with self.lock:
            self.calls += 1
            key = message["idempotency_key"]
            if self.failed_key is None:
                self.failed_key = key
                raise RuntimeError("qualification provider outage")
            self.delivered.add(key)
            return f"qualification-delivery-{len(self.delivered):03d}"


class _ClaimCodeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "output" and dict(attrs).get("id") == "claim-code":
            self.capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "output":
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)


def _claim_code(page: str) -> str:
    parser = _ClaimCodeParser()
    parser.feed(page)
    value = "".join(parser.parts)
    if not value:
        raise QualificationError("participant claim UI did not render a claim code")
    return value


def _evaluate(
    fixture: StagingFixture,
    snapshot: dict[str, Any],
    state: Path,
    nominations: dict[str, Any],
) -> dict[str, Any]:
    return prize_evaluator.evaluate_snapshot(
        policy=fixture.policy,
        snapshot=snapshot,
        state_path=state,
        seed=fixture.seed,
        nomination_input=nominations,
    )


def _family_counts(state: Path) -> dict[str, int]:
    connection = sqlite3.connect(state)
    try:
        return dict(
            connection.execute(
                "SELECT slot.family, COUNT(*) FROM allocation_attempt AS attempt "
                "JOIN prize_slot AS slot ON slot.event_id = attempt.event_id "
                "AND slot.slot_id = attempt.slot_id "
                "WHERE attempt.status = 'selected' GROUP BY slot.family"
            )
        )
    finally:
        connection.close()


def _selection_digest(rows: list[dict[str, Any]]) -> str:
    return _artifact_digest(rows)


def _claim_many(
    ui: Any,
    allocations: list[dict[str, Any]],
    packs: list[int],
    *,
    now: datetime,
    request_start: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    staff = _staff_context()

    def claim(item: tuple[int, dict[str, Any], int]) -> dict[str, Any]:
        offset, allocation, pack = item
        page = ui.participant_page(
            _participant_context(allocation["participant_id"]),
            issue_code=True,
            now=now,
        )
        code = _claim_code(page)
        request_id = _id(request_start + offset)
        receipt = ui.claim_receipt(
            staff,
            claim_code=code,
            pack_number=pack,
            request_id=request_id,
            now=now,
        )
        return {
            "slot_id": allocation["slot_id"],
            "participant_id": allocation["participant_id"],
            "pack_number": pack,
            "claim_code": code,
            "request_id": request_id,
            "participant_page": page,
            "receipt_page": receipt,
        }

    work = [
        (offset, allocation, pack)
        for offset, (allocation, pack) in enumerate(
            zip(allocations, packs, strict=True)
        )
    ]
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(claim, work))
    pages = [row.pop("participant_page") for row in results]
    pages.extend(row.pop("receipt_page") for row in results)
    return results, pages


def _assert_private_surfaces(
    fixture: StagingFixture,
    participant_pages: list[str],
    operator_page: str,
) -> None:
    private_markers = (
        "policy_digest",
        "draw_rank",
        "eligibility_digest",
        "nominator_id",
        "nominee_id",
        "token_digest",
        "challenge_source_ids",
    )
    for page in participant_pages:
        lowered = page.lower()
        if any(
            participant_id in page for participant_id in fixture.participant_ids
        ) or any(marker in lowered for marker in private_markers):
            raise QualificationError("participant prize UI disclosed private state")
    if (
        any(
            participant_id in operator_page
            for participant_id in fixture.participant_ids
        )
        or "token_digest" in operator_page.lower()
    ):
        raise QualificationError(
            "operator claim UI disclosed credentials or private IDs"
        )
    serialized_bundle = json.dumps(fixture.bundle, sort_keys=True)
    if fixture.policy["catalog"]["content_bundle_digest"] != fixture.bundle_digest:
        raise QualificationError("policy sidecar content binding changed")
    for marker in ("prize_policy", "evaluation_order", "runtime_parameters"):
        if marker in serialized_bundle:
            raise QualificationError("participant content contains the prize sidecar")
    for manifest in (ROOT / "build" / "participant-surface" / "manifests").glob(
        "*.json"
    ):
        text = manifest.read_text(encoding="utf-8")
        forbidden = (
            fixture.policy["catalog"]["content_bundle_digest"],
            "cinder-typhoon.event-prize-policy",
            "prize_policy",
            "evaluation_order",
            "runtime_parameters",
            "draw_seed",
        )
        if any(marker in text for marker in forbidden):
            raise QualificationError(
                "participant assets contain the prize sidecar digest"
            )


def _failure_variants(
    fixture: StagingFixture,
    nominations: dict[str, Any],
    root: Path,
) -> dict[str, bool]:
    missing = deepcopy(fixture.full_snapshot)
    missing_id = next(
        row["submission_id"]
        for row in missing["occurrences"]
        if row["trigger"] == "accepted_solve"
    )
    missing["occurrences"] = [
        row for row in missing["occurrences"] if row["submission_id"] != missing_id
    ]
    missing_rejected = False
    try:
        _evaluate(fixture, missing, root / "missing.sqlite3", nominations)
    except prize_evaluator.PrizeEvaluationError:
        missing_rejected = True
    if not missing_rejected:
        raise QualificationError("missing authoritative input did not stop selection")

    mismatch = deepcopy(fixture.full_snapshot)
    mismatch["event"]["content_bundle_digest"] = "sha256:" + "0" * 64
    mismatch_rejected = False
    try:
        _evaluate(fixture, mismatch, root / "mismatch.sqlite3", nominations)
    except prize_evaluator.PrizeEvaluationError:
        mismatch_rejected = True
    if not mismatch_rejected:
        raise QualificationError("policy/content mismatch did not fail closed")

    no_clears_source = deepcopy(fixture.source)
    completers = set(fixture.participant_ids[6:15])
    for participant in no_clears_source["participants"]:
        if participant["participant_id"] in completers:
            participant["prize_eligible"] = False
    no_clears_source["ranking"] = [
        row
        for row in no_clears_source["ranking"]
        if row["participant_id"] not in completers
    ]
    no_clears = prize_inputs.build_prize_input(fixture.policy, no_clears_source)
    no_clears_result = _evaluate(
        fixture,
        no_clears,
        root / "no-clears.sqlite3",
        nominations,
    )
    stage_score_count = sum(
        row["selector"].startswith("stage_score:")
        for row in no_clears_result["active_allocations"]
    )
    if stage_score_count != 9:
        raise QualificationError(
            "no-complete-stage-clear rollover did not fill nine slots"
        )

    insufficient = deepcopy(nominations)
    insufficient["ballots"] = insufficient["ballots"][:1]
    insufficient_result = _evaluate(
        fixture,
        fixture.full_snapshot,
        root / "insufficient-nominations.sqlite3",
        insufficient,
    )
    good_citizen_slots = [
        row
        for row in insufficient_result["active_allocations"]
        if row["slot_id"].startswith("good-citizen-")
    ]
    if len(good_citizen_slots) != 5:
        raise QualificationError(
            "insufficient nominations left Good Citizen slots open"
        )
    return {
        "missing_input_rejected": missing_rejected,
        "policy_content_mismatch_rejected": mismatch_rejected,
        "no_complete_stage_clears_filled": stage_score_count == 9,
        "insufficient_nominations_filled": len(good_citizen_slots) == 5,
    }


def _assert_credential_free(summary: dict[str, Any]) -> None:
    serialized = json.dumps(summary, sort_keys=True)
    lowered = serialized.lower()
    if UUID_PATTERN.search(serialized) or "player " in lowered:
        raise QualificationError("qualification summary contains participant identity")
    for marker in (
        "claim_code",
        "qr_payload",
        "token_digest",
        "session-",
        "staff_id",
        "nominator_id",
        "nominee_id",
        "draw_seed",
    ):
        if marker in lowered:
            raise QualificationError(f"qualification summary contains {marker}")


def qualify(candidate_path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    """Run the pinned end-to-end staging rehearsal and return aggregate evidence."""

    fixture = StagingFixture()
    candidate = _load_candidate(candidate_path, fixture)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        nominations = _collect_nominations(fixture, root)
        state = root / "prizes.sqlite3"

        def reconcile(_attempt: int) -> dict[str, Any]:
            return _evaluate(
                fixture,
                fixture.prefinal_snapshot,
                state,
                nominations,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            retry_results = list(executor.map(reconcile, range(8)))
        if not all(row["active_allocation_count"] == 50 for row in retry_results):
            raise QualificationError(
                "concurrent evaluator retries did not converge on 50"
            )
        initial_allocations = prize_evaluator.active_allocations(
            state, fixture.event_id
        )
        initial_families = _family_counts(state)
        expected_families = {
            "bounties": 6,
            "good_citizen": 5,
            "overall_leaders": 10,
            "passport_draw": 5,
            "stage_completion": 9,
            "stage_draws": 15,
        }
        if initial_families != expected_families:
            raise QualificationError("initial allocation families are incomplete")

        config = prize_claims.build_claim_config(
            policy=fixture.policy,
            snapshot=fixture.full_snapshot,
            public_origin=ORIGIN,
        )
        service = prize_claims.PrizeClaimService(
            config=config,
            state_path=state,
            token_key=FIXTURE_CLAIM_HMAC_KEY,
        )
        ui = prize_ui.PrizeEventUI(service)
        delivery = _DeliveryAdapter()
        first_delivery = service.release_notifications(
            delivery,
            now="2026-06-01T12:30:00Z",
        )
        if sum(row["state"] == "failed" for row in first_delivery) != 1:
            raise QualificationError("notification failure fixture did not fail once")
        recovered = service.release_notifications(
            delivery,
            now="2026-06-01T12:30:01Z",
        )
        if len(recovered) != 1 or recovered[0]["state"] != "delivered":
            raise QualificationError("notification recovery did not reuse its intent")

        top_ten = {
            row["participant_id"]
            for row in fixture.full_snapshot["overall_ranking"][:10]
        }
        initial_by_participant = {
            row["participant_id"]: row for row in initial_allocations
        }
        if not top_ten.issubset(initial_by_participant):
            raise QualificationError("an overall top-ten participant has no allocation")
        chosen = [initial_by_participant[participant_id] for participant_id in top_ten]
        chosen_ids = set(top_ten)
        chosen.extend(
            row
            for row in initial_allocations
            if row["participant_id"] not in chosen_ids
        )
        chosen = chosen[:INITIAL_CLAIM_COUNT]
        chosen_ids = {row["participant_id"] for row in chosen}
        expired_initial = [
            row
            for row in initial_allocations
            if row["participant_id"] not in chosen_ids
        ]
        initial_claims, participant_pages = _claim_many(
            ui,
            chosen,
            list(range(1, INITIAL_CLAIM_COUNT + 1)),
            now=datetime(2026, 6, 1, 12, 40, tzinfo=UTC),
            request_start=5_000_000,
        )

        first_claim = initial_claims[0]

        def retry_claim(_attempt: int) -> str:
            return ui.claim_receipt(
                _staff_context(),
                claim_code=first_claim["claim_code"],
                pack_number=first_claim["pack_number"],
                request_id=first_claim["request_id"],
                now="2026-06-01T12:40:01Z",
            )

        with ThreadPoolExecutor(max_workers=16) as executor:
            retry_receipts = list(executor.map(retry_claim, range(32)))
        if len(set(retry_receipts)) != 1:
            raise QualificationError("claim retry storm produced different receipts")
        duplicate_rejected = False
        try:
            ui.claim_receipt(
                _staff_context(),
                claim_code=first_claim["claim_code"],
                pack_number=26,
                request_id=_id(5_999_999),
                now="2026-06-01T12:40:01Z",
            )
        except prize_claims.PrizeClaimError:
            duplicate_rejected = True
        if not duplicate_rejected:
            raise QualificationError("used claim code was accepted for another pack")

        deadline = service.expire_unclaimed(
            occurrence_id=_id(6_000_000),
            executed_at="2026-06-01T13:00:15Z",
        )
        if len(deadline["voided"]) != 50 - INITIAL_CLAIM_COUNT:
            raise QualificationError(
                "claim deadline did not void 25 unclaimed attempts"
            )
        final_result = _evaluate(
            fixture,
            fixture.full_snapshot,
            state,
            nominations,
        )
        final_allocations = final_result["active_allocations"]
        final_fallback = [
            row for row in final_allocations if row["selector"] == "final_solver_draw"
        ]
        if len(final_fallback) != 25:
            raise QualificationError("final fallback did not refill 25 slots")
        if {row["participant_id"] for row in final_fallback} & {
            row["participant_id"] for row in initial_allocations
        }:
            raise QualificationError("final fallback reused a prior winner")
        service.sync_allocations(now="2026-06-01T14:00:10Z")
        final_delivery = service.release_notifications(
            delivery,
            now="2026-06-01T14:00:10Z",
        )
        if len(final_delivery) != 25 or not all(
            row["state"] == "delivered" for row in final_delivery
        ):
            raise QualificationError("final winner notifications were not delivered")
        final_claims, final_pages = _claim_many(
            ui,
            final_fallback,
            list(range(INITIAL_CLAIM_COUNT + 1, 51)),
            now=datetime(2026, 6, 1, 14, 1, tzinfo=UTC),
            request_start=6_100_000,
        )
        participant_pages.extend(final_pages)

        restarted_service = prize_claims.PrizeClaimService(
            config=config,
            state_path=state,
            token_key=FIXTURE_CLAIM_HMAC_KEY,
        )
        restarted_ui = prize_ui.PrizeEventUI(restarted_service)
        operator_page = restarted_ui.operator_page(
            _staff_context(),
            csrf_token="qualification-csrf-token",
            request_id=_id(6_200_000),
        )
        dashboard = restarted_service.dashboard(_staff_context())
        if len(dashboard["slots"]) != 50 or dashboard["errors"]:
            raise QualificationError("restarted operator dashboard is incomplete")
        if operator_page.count("<tr>") != 51:
            raise QualificationError("rendered operator UI does not show all 50 slots")
        _assert_private_surfaces(
            fixture,
            participant_pages,
            operator_page,
        )

        summary_view = restarted_service.credential_free_summary(_staff_context())
        if UUID_PATTERN.search(json.dumps(summary_view)):
            raise QualificationError("credential-free service summary contains a UUID")

        rebuilt_state = root / "rebuilt.sqlite3"
        _evaluate(
            fixture,
            fixture.prefinal_snapshot,
            rebuilt_state,
            nominations,
        )
        for row in expired_initial:
            prize_evaluator.void_allocation(
                state_path=rebuilt_state,
                event_id=fixture.event_id,
                slot_id=row["slot_id"],
                reason="claim deadline expired",
                voided_at="2026-06-01T13:00:15Z",
            )
        rebuilt = _evaluate(
            fixture,
            fixture.full_snapshot,
            rebuilt_state,
            nominations,
        )
        if rebuilt["active_allocations"] != final_allocations:
            raise QualificationError("fresh rebuild changed winners or proofs")

        variants = _failure_variants(fixture, nominations, root)
        accepted_times = Counter(
            row["accepted_at"] for row in fixture.full_snapshot["accepted_solves"]
        )
        if max(accepted_times.values()) < 2:
            raise QualificationError("simultaneous-solve fixture is absent")
        ranking_scores = Counter(
            row["score"] for row in fixture.full_snapshot["overall_ranking"]
        )
        if max(ranking_scores.values()) < 2:
            raise QualificationError("tied-score fixture is absent")

        connection = sqlite3.connect(state)
        try:
            claim_count = connection.execute(
                "SELECT COUNT(*) FROM prize_claim"
            ).fetchone()[0]
            claimed_packs = connection.execute(
                "SELECT COUNT(*) FROM prize_pack WHERE status = 'claimed'"
            ).fetchone()[0]
            intent_count = connection.execute(
                "SELECT COUNT(*) FROM notification_intent"
            ).fetchone()[0]
        finally:
            connection.close()
        if (claim_count, claimed_packs, intent_count) != (50, 50, 75):
            raise QualificationError("final claim, pack, or notification totals differ")

        assertions = {
            "all_50_numbered_packs_claimed": claimed_packs == 50,
            "all_initial_allocation_families_exercised": initial_families
            == expected_families,
            "claim_retry_storm_idempotent": len(set(retry_receipts)) == 1,
            "credential_free_summary": not UUID_PATTERN.search(
                json.dumps(summary_view)
            ),
            "duplicate_claim_rejected": duplicate_rejected,
            "final_fallback_exercised": len(final_fallback) == 25,
            "notification_failure_recovered": len(recovered) == 1,
            "participant_surfaces_private": True,
            "policy_sidecar_absent_from_participant_content": True,
            "restart_preserved_dashboard": len(dashboard["slots"]) == 50,
            "rebuild_reproduced_winners_and_proofs": rebuilt["active_allocations"]
            == final_allocations,
            "simultaneous_solves_exercised": max(accepted_times.values()) >= 2,
            "tied_scores_exercised": max(ranking_scores.values()) >= 2,
            "top_ten_covered": top_ten.issubset(
                {row["participant_id"] for row in final_allocations}
            ),
            **variants,
        }
        if not all(assertions.values()):
            raise QualificationError("one or more release assertions failed")
        summary = {
            "contract": "cinder-typhoon.prize-qualification-summary/v1",
            "status": "passed",
            "candidate_digest": _artifact_digest(candidate),
            "catalog_revision": fixture.catalog["revision"],
            "content_bundle_digest": fixture.bundle_digest,
            "policy_digest": prize_inputs.artifact_digest(fixture.policy),
            "participant_history_count": PARTICIPANT_COUNT,
            "accepted_solve_count": len(fixture.full_snapshot["accepted_solves"]),
            "late_submission_count": 1,
            "concurrent_history_workers": 32,
            "concurrent_evaluator_retries": len(retry_results),
            "allocation_families": initial_families,
            "initial_allocation_count": len(initial_allocations),
            "initial_claim_count": len(initial_claims),
            "expired_initial_count": len(deadline["voided"]),
            "final_fallback_count": len(final_fallback),
            "final_claim_count": len(final_claims),
            "notification_intent_count": intent_count,
            "notification_delivery_attempt_count": delivery.calls,
            "claimed_pack_count": claimed_packs,
            "selection_proof_digest": _selection_digest(final_allocations),
            "assertions": assertions,
        }
        _assert_credential_free(summary)
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-candidate", action="store_true")
    parser.add_argument("--verify-summary", type=Path)
    arguments = parser.parse_args()
    if arguments.write_candidate:
        fixture = StagingFixture()
        _write_private_json(arguments.candidate, build_candidate(fixture))
        print(f"Wrote pinned candidate: {arguments.candidate}")
        return 0
    summary = qualify(arguments.candidate)
    if arguments.verify_summary is not None:
        expected = json.loads(arguments.verify_summary.read_text(encoding="utf-8"))
        if summary != expected:
            raise QualificationError("committed qualification summary is stale")
    if arguments.output is not None:
        _write_private_json(arguments.output, summary)
    print(
        "PASS: 320 histories, 50 unique active winners, 50 numbered claims, "
        "25 final rollovers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
