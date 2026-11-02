from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "challenges"))
import catalog  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


event_importer = _load_module(
    "cinder_event_importer_evaluator", ROOT / "ctfd" / "import_catalog.py"
)
prize_inputs = _load_module(
    "cinder_prize_inputs_tests", ROOT / "ctfd" / "prize_inputs.py"
)
EVALUATOR_PATH = Path(
    os.environ.get("CINDER_PRIZE_EVALUATOR_PATH", ROOT / "ctfd" / "prize_evaluator.py")
)
prize_evaluator = _load_module("cinder_prize_evaluator", EVALUATOR_PATH)

UTC = timezone.utc
EVENT_ID = str(UUID(int=1000))
SEED = bytes(range(32))


def _id(value: int) -> str:
    return str(UUID(int=value))


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class PrizeEvaluatorFixture:
    def __init__(self) -> None:
        self.catalog = catalog.load_catalog()
        bundle = event_importer.build_event_bundle(
            self.catalog,
            scorer_origin="https://cinder-scorer.example.test",
        )
        self.policy = event_importer.prize_policy_module.build_policy(
            self.catalog,
            event_importer.artifact_digest(bundle),
        )
        self.participant_ids = [_id(index) for index in range(1, 101)]
        self.submission_counter = 100_000
        self.submissions: list[dict] = []
        self.source = self._build_source()
        self.nominations = self._build_nominations()
        self.full_snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        source_without_finalization = deepcopy(self.source)
        source_without_finalization["occurrences"] = [
            row
            for row in source_without_finalization["occurrences"]
            if row["trigger"] != "finalization"
        ]
        self.prefinal_snapshot = prize_inputs.build_prize_input(
            self.policy, source_without_finalization
        )

    def _add_solve(
        self,
        participant_number: int,
        source_id: str,
        accepted_at: datetime,
        *,
        submission_id: str | None = None,
    ) -> str:
        self.submission_counter += 1
        identity = submission_id or _id(self.submission_counter)
        self.submissions.append(
            {
                "event_id": EVENT_ID,
                "submission_id": identity,
                "participant_id": self.participant_ids[participant_number - 1],
                "challenge_source_id": source_id,
                "is_correct": True,
                "points_awarded": 10,
                "submitted_at": _stamp(accepted_at),
            }
        )
        return identity

    def _build_source(self) -> dict:  # noqa: C901 - one readable lifecycle fixture
        training = self.policy["stages"]["training"]["challenge_source_ids"]
        keplerops = self.policy["stages"]["keplerops"]["challenge_source_ids"]
        arwc = self.policy["stages"]["arwc"]["challenge_source_ids"]
        source_ids = {"training": training, "keplerops": keplerops, "arwc": arwc}
        start = datetime(2026, 6, 1, 9, tzinfo=UTC)

        bounty_awards = self.policy["allocations"]["bounties"]["awards"]
        bounty_times = {
            "training": start + timedelta(minutes=1),
            "keplerops": start + timedelta(hours=1, minutes=1),
            "arwc": start + timedelta(hours=2, minutes=1),
        }
        first_bounty_submission = None
        for participant_number, award in enumerate(bounty_awards, start=1):
            submission_id = self._add_solve(
                participant_number,
                award["challenge_source_id"],
                bounty_times[award["stage"]],
            )
            if participant_number == 1:
                first_bounty_submission = submission_id
        if first_bounty_submission is None:
            raise RuntimeError("fixture policy has no bounty awards")
        self._add_solve(
            100,
            bounty_awards[0]["challenge_source_id"],
            bounty_times["training"],
            submission_id=_id(int(UUID(first_bounty_submission)) + 10_000),
        )

        completion_groups = {
            "training": range(7, 10),
            "keplerops": range(10, 13),
            "arwc": range(13, 16),
        }
        completion_bases = {
            "training": start + timedelta(minutes=10),
            "keplerops": start + timedelta(hours=1, minutes=10),
            "arwc": start + timedelta(hours=2, minutes=10),
        }
        for stage, participants in completion_groups.items():
            sequence = 0
            for participant_number in participants:
                for source_id in source_ids[stage]:
                    sequence += 1
                    self._add_solve(
                        participant_number,
                        source_id,
                        completion_bases[stage] + timedelta(seconds=sequence),
                    )

        stage_draw_groups = {
            "training": range(16, 23),
            "keplerops": range(23, 30),
            "arwc": range(30, 37),
        }
        stage_draw_times = {
            "training": start + timedelta(minutes=35),
            "keplerops": start + timedelta(hours=1, minutes=35),
            "arwc": start + timedelta(hours=2, minutes=35),
        }
        for stage, participants in stage_draw_groups.items():
            for offset, participant_number in enumerate(participants):
                self._add_solve(
                    participant_number,
                    source_ids[stage][0],
                    stage_draw_times[stage] + timedelta(seconds=offset),
                )

        for offset, participant_number in enumerate(range(40, 80)):
            self._add_solve(
                participant_number,
                training[1],
                start + timedelta(minutes=40, seconds=offset),
            )
            self._add_solve(
                participant_number,
                keplerops[1],
                start + timedelta(hours=1, minutes=40, seconds=offset),
            )
            self._add_solve(
                participant_number,
                arwc[1],
                start + timedelta(hours=2, minutes=40, seconds=offset),
            )

        participants = [
            {
                "event_id": EVENT_ID,
                "participant_id": participant_id,
                "public_alias": f"Player {index:03d}",
                "prize_eligible": True,
            }
            for index, participant_id in enumerate(self.participant_ids, start=1)
        ]
        solves_by_participant: dict[str, list[dict]] = {
            participant_id: [] for participant_id in self.participant_ids
        }
        for solve in self.submissions:
            solves_by_participant[solve["participant_id"]].append(solve)
        ranking = []
        for participant_id in reversed(self.participant_ids):
            solves = solves_by_participant[participant_id]
            ranking.append(
                {
                    "event_id": EVENT_ID,
                    "participant_id": participant_id,
                    "score": sum(row["points_awarded"] for row in solves),
                    "solve_count": len(solves),
                    "last_solve_at": max(
                        (row["submitted_at"] for row in solves), default=None
                    ),
                }
            )

        occurrences = [
            {
                "event_id": EVENT_ID,
                "occurrence_id": row["submission_id"],
                "trigger": "accepted_solve",
                "stage": next(
                    stage
                    for stage in ("training", "keplerops", "arwc")
                    if row["challenge_source_id"] in source_ids[stage]
                ),
                "submission_id": row["submission_id"],
                "scheduled_for": None,
                "executed_at": _stamp(
                    datetime.fromisoformat(row["submitted_at"].replace("Z", "+00:00"))
                    + timedelta(seconds=1)
                ),
            }
            for row in self.submissions
        ]
        for offset, (stage, scheduled) in enumerate(
            (
                ("training", start + timedelta(hours=1)),
                ("keplerops", start + timedelta(hours=2)),
                ("arwc", start + timedelta(hours=3)),
            ),
            start=1,
        ):
            occurrences.append(
                {
                    "event_id": EVENT_ID,
                    "occurrence_id": _id(800_000 + offset),
                    "trigger": "stage_closed",
                    "stage": stage,
                    "submission_id": None,
                    "scheduled_for": _stamp(scheduled),
                    "executed_at": _stamp(scheduled + timedelta(seconds=5)),
                }
            )
        occurrences.extend(
            [
                {
                    "event_id": EVENT_ID,
                    "occurrence_id": _id(800_010),
                    "trigger": "nomination_closed",
                    "stage": None,
                    "submission_id": None,
                    "scheduled_for": _stamp(start + timedelta(hours=2, minutes=30)),
                    "executed_at": _stamp(
                        start + timedelta(hours=2, minutes=30, seconds=5)
                    ),
                },
                {
                    "event_id": EVENT_ID,
                    "occurrence_id": _id(800_011),
                    "trigger": "event_closed",
                    "stage": None,
                    "submission_id": None,
                    "scheduled_for": _stamp(start + timedelta(hours=3)),
                    "executed_at": _stamp(start + timedelta(hours=3, seconds=10)),
                },
                {
                    "event_id": EVENT_ID,
                    "occurrence_id": _id(800_012),
                    "trigger": "finalization",
                    "stage": None,
                    "submission_id": None,
                    "scheduled_for": _stamp(start + timedelta(hours=5)),
                    "executed_at": _stamp(start + timedelta(hours=5, seconds=5)),
                },
            ]
        )
        return {
            "contract": prize_inputs.SOURCE_CONTRACT,
            "event": {
                "event_id": EVENT_ID,
                "team_mode": False,
                "status": "completed",
                "event_start": _stamp(start),
                "event_end": _stamp(start + timedelta(hours=3)),
                "snapshot_at": _stamp(start + timedelta(hours=5, minutes=5)),
                "content_bundle_digest": self.policy["catalog"][
                    "content_bundle_digest"
                ],
                "policy_digest": prize_inputs.artifact_digest(self.policy),
                "boundaries": {
                    "stage_close_at": {
                        "training": _stamp(start + timedelta(hours=1)),
                        "keplerops": _stamp(start + timedelta(hours=2)),
                        "arwc": _stamp(start + timedelta(hours=3)),
                    },
                    "nomination_open_at": _stamp(start),
                    "nomination_close_at": _stamp(
                        start + timedelta(hours=2, minutes=30)
                    ),
                    "claim_deadline_at": _stamp(start + timedelta(hours=4)),
                    "finalize_at": _stamp(start + timedelta(hours=5)),
                    "draw_seed_commitment": prize_evaluator.seed_commitment(
                        EVENT_ID, SEED
                    ),
                },
            },
            "participants": participants,
            "submissions": list(reversed(self.submissions)),
            "ranking": ranking,
            "occurrences": list(reversed(occurrences)),
        }

    def _build_nominations(self) -> dict:
        ballots = []
        for candidate_offset, candidate_number in enumerate(range(80, 85)):
            for vote_offset in range(2):
                nominator_number = 85 + (candidate_offset * 2) + vote_offset
                ballots.append(
                    {
                        "ballot_id": _id(900_000 + len(ballots)),
                        "nominator_id": self.participant_ids[nominator_number - 1],
                        "nominee_id": self.participant_ids[candidate_number - 1],
                        "submitted_at": "2026-06-01T10:30:00Z",
                        "attested": True,
                    }
                )
        return {
            "contract": prize_evaluator.NOMINATIONS_CONTRACT,
            "event_id": EVENT_ID,
            "ballots": ballots,
        }

    def snapshot(self, *, finalization: bool = True) -> dict:
        return self.full_snapshot if finalization else self.prefinal_snapshot


class PrizeEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = PrizeEvaluatorFixture()

    def _evaluate(self, state: Path, *, snapshot: dict | None = None) -> dict:
        return prize_evaluator.evaluate_snapshot(
            policy=self.fixture.policy,
            snapshot=snapshot or self.fixture.snapshot(),
            state_path=state,
            seed=SEED,
            nomination_input=self.fixture.nominations,
        )

    def test_complete_lifecycle_allocates_50_distinct_people_and_all_families(
        self,
    ) -> None:
        snapshot = self.fixture.snapshot()
        snapshot_before = deepcopy(snapshot)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "prizes.sqlite3"
            result = self._evaluate(state, snapshot=snapshot)
            self.assertEqual(result["active_allocation_count"], 50)
            self.assertEqual(result["open_slot_count"], 0)
            allocations = result["active_allocations"]
            self.assertEqual(len({row["slot_id"] for row in allocations}), 50)
            self.assertEqual(len({row["participant_id"] for row in allocations}), 50)

            selector_counts = Counter(
                row["selector"].split(":")[0] for row in allocations
            )
            self.assertEqual(selector_counts["bounty"], 6)
            self.assertEqual(selector_counts["stage_completion"], 9)
            self.assertEqual(selector_counts["stage_draw"], 15)
            self.assertEqual(selector_counts["good_citizen"], 5)
            self.assertEqual(selector_counts["overall_rank"], 10)
            self.assertEqual(selector_counts["passport_draw"], 5)
            self.assertEqual(selector_counts["final_solver_draw"], 0)
            golden_draw = next(
                row for row in allocations if row["slot_id"] == "stage-draw-training-01"
            )
            self.assertEqual(
                golden_draw["participant_id"], self.fixture.participant_ids[60]
            )
            self.assertEqual(
                golden_draw["draw_rank"],
                "0036115f94e85eae02f914289a7b807a1ec4216dc3de3043f58a3090392b5053",
            )

            winners = {row["participant_id"] for row in allocations}
            top_ten = {
                row["participant_id"] for row in snapshot["overall_ranking"][:10]
            }
            self.assertTrue(top_ten.issubset(winners))
            self.assertEqual(snapshot, snapshot_before)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)

    def test_state_contains_proofs_not_a_second_solve_ledger_or_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "prizes.sqlite3"
            self._evaluate(state)
            connection = sqlite3.connect(state)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertEqual(
                    tables,
                    {
                        "event_binding",
                        "prize_slot",
                        "evaluation_occurrence",
                        "allocation_attempt",
                    },
                )
                columns = {
                    row[1]
                    for table in tables
                    for row in connection.execute(f"PRAGMA table_info({table})")
                }
                for forbidden in (
                    "public_alias",
                    "submission_id",
                    "challenge_source_id",
                    "points",
                    "seed",
                    "nominator_id",
                ):
                    self.assertNotIn(forbidden, columns)
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM evaluation_occurrence WHERE result_digest = 'pending'"
                    ).fetchone()[0],
                    0,
                )
            finally:
                connection.close()

    def test_replay_and_fresh_rebuild_are_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_state = Path(directory) / "first.sqlite3"
            second_state = Path(directory) / "second.sqlite3"
            first = self._evaluate(first_state)
            retried = self._evaluate(first_state)
            rebuilt = self._evaluate(second_state)
            self.assertEqual(first, retried)
            self.assertEqual(first["active_allocations"], rebuilt["active_allocations"])

            def occurrence_rows(path: Path) -> list[tuple]:
                connection = sqlite3.connect(path)
                try:
                    return list(
                        connection.execute(
                            "SELECT occurrence_id, input_digest, result_digest "
                            "FROM evaluation_occurrence ORDER BY occurrence_id"
                        )
                    )
                finally:
                    connection.close()

            self.assertEqual(
                occurrence_rows(first_state), occurrence_rows(second_state)
            )

    def test_concurrent_reconciliation_cannot_duplicate_slots_or_people(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "concurrent.sqlite3"
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: self._evaluate(state), range(4)))
            self.assertTrue(
                all(row["active_allocation_count"] == 50 for row in results)
            )
            allocations = prize_evaluator.active_allocations(state, EVENT_ID)
            self.assertEqual(len(allocations), 50)
            self.assertEqual(len({row["slot_id"] for row in allocations}), 50)
            self.assertEqual(len({row["participant_id"] for row in allocations}), 50)

    def test_same_time_bounty_uses_submission_id_before_participant_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._evaluate(Path(directory) / "prizes.sqlite3")
            first_bounty = next(
                row
                for row in result["active_allocations"]
                if row["slot_id"] == "bounty-t03.4"
            )
            expected = self.fixture.participant_ids[0]
            self.assertEqual(first_bounty["participant_id"], expected)

    def test_stage_close_fills_completion_shortfall_by_stage_score(self) -> None:
        source = deepcopy(self.fixture.source)
        ineligible = set(self.fixture.participant_ids[6:9])
        for participant in source["participants"]:
            if participant["participant_id"] in ineligible:
                participant["prize_eligible"] = False
        source["ranking"] = [
            row for row in source["ranking"] if row["participant_id"] not in ineligible
        ]
        snapshot = prize_inputs.build_prize_input(self.fixture.policy, source)
        with tempfile.TemporaryDirectory() as directory:
            result = self._evaluate(
                Path(directory) / "prizes.sqlite3", snapshot=snapshot
            )
        training_fallback = [
            row
            for row in result["active_allocations"]
            if row["selector"] == "stage_score:training"
        ]
        self.assertEqual(len(training_fallback), 3)

    def test_good_citizen_rolls_from_two_nominations_to_one(self) -> None:
        nominations = deepcopy(self.fixture.nominations)
        nominations["ballots"].pop(0)
        with tempfile.TemporaryDirectory() as directory:
            result = prize_evaluator.evaluate_snapshot(
                policy=self.fixture.policy,
                snapshot=self.fixture.snapshot(),
                state_path=Path(directory) / "prizes.sqlite3",
                seed=SEED,
                nomination_input=nominations,
            )
        selectors = Counter(row["selector"] for row in result["active_allocations"])
        self.assertEqual(selectors["good_citizen:two_plus"], 4)
        self.assertEqual(selectors["good_citizen:one"], 1)

    def test_missing_solve_occurrence_fails_close_without_allocations(self) -> None:
        source = deepcopy(self.fixture.source)
        missing_id = source["submissions"][0]["submission_id"]
        source["occurrences"] = [
            row for row in source["occurrences"] if row["submission_id"] != missing_id
        ]
        snapshot = prize_inputs.build_prize_input(self.fixture.policy, source)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "failed.sqlite3"
            with self.assertRaisesRegex(
                prize_evaluator.PrizeEvaluationError, "missing accepted-solve"
            ):
                self._evaluate(state, snapshot=snapshot)
            self.assertEqual(prize_evaluator.active_allocations(state, EVENT_ID), [])

    def test_seed_policy_and_event_binding_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "bound.sqlite3"
            self._evaluate(state)
            with self.assertRaisesRegex(
                prize_evaluator.PrizeEvaluationError, "draw seed"
            ):
                prize_evaluator.evaluate_snapshot(
                    policy=self.fixture.policy,
                    snapshot=self.fixture.snapshot(),
                    state_path=Path(directory) / "wrong-seed.sqlite3",
                    seed=b"x" * 32,
                    nomination_input=self.fixture.nominations,
                )

            changed = deepcopy(self.fixture.snapshot())
            changed["event"]["content_bundle_digest"] = "sha256:" + ("0" * 64)
            with self.assertRaises(prize_evaluator.PrizeEvaluationError):
                self._evaluate(
                    Path(directory) / "wrong-content.sqlite3", snapshot=changed
                )

            other_event = deepcopy(self.fixture.snapshot())
            other_event["event"]["event_id"] = _id(123_456)
            with self.assertRaises(prize_evaluator.PrizeEvaluationError):
                self._evaluate(state, snapshot=other_event)

    def test_seed_and_state_files_reject_unsafe_permissions_or_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed_path = root / "seed.hex"
            seed_path.write_text(SEED.hex(), encoding="ascii")
            seed_path.chmod(0o644)
            with self.assertRaisesRegex(
                prize_evaluator.PrizeEvaluationError, "owner-only"
            ):
                prize_evaluator._load_seed(seed_path)
            seed_path.chmod(0o600)
            self.assertEqual(prize_evaluator._load_seed(seed_path), SEED)

            target = root / "target.sqlite3"
            target.touch(mode=0o600)
            linked_state = root / "linked.sqlite3"
            linked_state.symlink_to(target)
            with self.assertRaisesRegex(
                prize_evaluator.PrizeEvaluationError, "symbolic link"
            ):
                self._evaluate(linked_state)

    def test_nomination_scope_privacy_attestation_and_cutoff_are_closed(self) -> None:
        mutations = []
        self_nomination = deepcopy(self.fixture.nominations)
        self_nomination["ballots"][0]["nominee_id"] = self_nomination["ballots"][0][
            "nominator_id"
        ]
        mutations.append(self_nomination)

        late = deepcopy(self.fixture.nominations)
        late["ballots"][0]["submitted_at"] = "2026-06-01T11:30:00Z"
        mutations.append(late)

        no_attestation = deepcopy(self.fixture.nominations)
        no_attestation["ballots"][0]["attested"] = False
        mutations.append(no_attestation)

        free_text = deepcopy(self.fixture.nominations)
        free_text["ballots"][0]["reason"] = "private participant text"
        mutations.append(free_text)

        for index, changed in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(prize_evaluator.PrizeEvaluationError):
                    prize_evaluator.evaluate_snapshot(
                        policy=self.fixture.policy,
                        snapshot=self.fixture.snapshot(),
                        state_path=Path(directory) / "prizes.sqlite3",
                        seed=SEED,
                        nomination_input=changed,
                    )

    def test_void_retains_history_and_finalization_uses_next_generation(self) -> None:
        without_finalization = self.fixture.snapshot(finalization=False)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "prizes.sqlite3"
            result = self._evaluate(state, snapshot=without_finalization)
            self.assertEqual(result["active_allocation_count"], 50)
            original = result["active_allocations"][0]
            prize_evaluator.void_allocation(
                state_path=state,
                event_id=EVENT_ID,
                slot_id=original["slot_id"],
                reason="claim deadline expired",
                voided_at="2026-06-01T13:05:00Z",
            )
            self.assertEqual(
                len(prize_evaluator.active_allocations(state, EVENT_ID)), 49
            )

            finalized = self._evaluate(state, snapshot=self.fixture.snapshot())
            replacement = next(
                row
                for row in finalized["active_allocations"]
                if row["slot_id"] == original["slot_id"]
            )
            self.assertEqual(replacement["generation"], 2)
            self.assertNotEqual(
                replacement["participant_id"], original["participant_id"]
            )
            self.assertEqual(replacement["selector"], "final_solver_draw")

            connection = sqlite3.connect(state)
            try:
                history = list(
                    connection.execute(
                        "SELECT generation, status, void_reason FROM allocation_attempt "
                        "WHERE event_id = ? AND slot_id = ? ORDER BY generation",
                        (EVENT_ID, original["slot_id"]),
                    )
                )
            finally:
                connection.close()
            self.assertEqual(
                history,
                [
                    (1, "voided", "claim deadline expired"),
                    (2, "selected", None),
                ],
            )

    def test_slot_and_cutoff_mutations_are_rejected_or_change_no_winner(self) -> None:
        changed_policy = deepcopy(self.fixture.policy)
        changed_policy["allocations"]["overall_leaders"]["slot_ids"].pop()
        changed_source = deepcopy(self.fixture.source)
        changed_source["event"]["policy_digest"] = prize_inputs.artifact_digest(
            changed_policy
        )
        changed_snapshot = prize_inputs.build_prize_input(
            changed_policy, changed_source
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(prize_evaluator.PrizeEvaluationError):
                prize_evaluator.evaluate_snapshot(
                    policy=changed_policy,
                    snapshot=changed_snapshot,
                    state_path=Path(directory) / "prizes.sqlite3",
                    seed=SEED,
                    nomination_input=self.fixture.nominations,
                )

        source = deepcopy(self.fixture.source)
        source["submissions"].append(
            {
                "event_id": EVENT_ID,
                "submission_id": _id(999_999),
                "participant_id": self.fixture.participant_ids[98],
                "challenge_source_id": self.fixture.policy["stages"]["training"][
                    "challenge_source_ids"
                ][2],
                "is_correct": True,
                "points_awarded": 1000,
                "submitted_at": "2026-06-01T10:00:00Z",
            }
        )
        source["occurrences"].append(
            {
                "event_id": EVENT_ID,
                "occurrence_id": _id(999_999),
                "trigger": "accepted_solve",
                "stage": "training",
                "submission_id": _id(999_999),
                "scheduled_for": None,
                "executed_at": "2026-06-01T10:00:01Z",
            }
        )
        ranking = next(
            row
            for row in source["ranking"]
            if row["participant_id"] == self.fixture.participant_ids[98]
        )
        ranking.update(
            {
                "score": 1000,
                "solve_count": 1,
                "last_solve_at": "2026-06-01T10:00:00Z",
            }
        )
        snapshot = prize_inputs.build_prize_input(self.fixture.policy, source)
        training_rows = {
            row["participant_id"]: row for row in snapshot["stage_results"]["training"]
        }
        self.assertNotIn(self.fixture.participant_ids[98], training_rows)


if __name__ == "__main__":
    unittest.main()
