from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
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
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


event_importer = _load_module(
    "cinder_event_importer_inputs", ROOT / "ctfd" / "import_catalog.py"
)
prize_inputs = _load_module("cinder_prize_inputs", ROOT / "ctfd" / "prize_inputs.py")

EVENT_ID = "00000000-0000-0000-0000-000000000100"
PARTICIPANTS = (
    "00000000-0000-0000-0000-000000000001",
    "00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000003",
    "00000000-0000-0000-0000-000000000004",
)


def _uuid(value: int) -> str:
    return str(UUID(int=value))


class AuthoritativePrizeInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = catalog.load_catalog()
        bundle = event_importer.build_event_bundle(
            cls.catalog,
            scorer_origin="https://cinder-scorer.example.test",
        )
        cls.policy = event_importer.prize_policy_module.build_policy(
            cls.catalog,
            event_importer.artifact_digest(bundle),
        )
        cls.training_ids = cls.policy["stages"]["training"]["challenge_source_ids"]

    def setUp(self) -> None:
        self.source = self._source()

    def _source(self) -> dict:
        participants = [
            {
                "event_id": EVENT_ID,
                "participant_id": participant_id,
                "public_alias": f"Player {index}",
                "prize_eligible": index < 4,
            }
            for index, participant_id in enumerate(PARTICIPANTS, start=1)
        ]
        submissions = []
        for index, source_id in enumerate(self.training_ids, start=1):
            submissions.append(
                self._submission(
                    submission_id=_uuid(1000 + index),
                    participant_id=PARTICIPANTS[0],
                    source_id=source_id,
                    points=10,
                    submitted_at=f"2026-06-01T09:{index:02d}:00Z",
                )
            )
        for offset, participant_id in enumerate(PARTICIPANTS[1:], start=1):
            submissions.append(
                self._submission(
                    submission_id=_uuid(2000 + offset),
                    participant_id=participant_id,
                    source_id=self.training_ids[0],
                    points=10,
                    submitted_at="2026-06-01T09:05:00Z",
                )
            )
        submissions.append(
            self._submission(
                submission_id=_uuid(3001),
                participant_id=PARTICIPANTS[1],
                source_id=self.training_ids[1],
                points=0,
                submitted_at="2026-06-01T09:06:00Z",
                is_correct=False,
            )
        )

        ranking = [
            self._ranking(
                PARTICIPANTS[2], score=10, count=1, last="2026-06-01T09:05:00Z"
            ),
            self._ranking(
                PARTICIPANTS[0], score=160, count=16, last="2026-06-01T09:16:00Z"
            ),
            self._ranking(
                PARTICIPANTS[1], score=10, count=1, last="2026-06-01T09:05:00Z"
            ),
        ]
        accepted_occurrence = {
            "event_id": EVENT_ID,
            "occurrence_id": _uuid(1016),
            "trigger": "accepted_solve",
            "stage": "training",
            "submission_id": _uuid(1016),
            "scheduled_for": None,
            "executed_at": "2026-06-01T09:16:01Z",
        }
        stage_occurrence = {
            "event_id": EVENT_ID,
            "occurrence_id": _uuid(9001),
            "trigger": "stage_closed",
            "stage": "training",
            "submission_id": None,
            "scheduled_for": "2026-06-01T10:00:00Z",
            "executed_at": "2026-06-01T10:00:05Z",
        }
        return {
            "contract": prize_inputs.SOURCE_CONTRACT,
            "event": {
                "event_id": EVENT_ID,
                "team_mode": False,
                "status": "completed",
                "event_start": "2026-06-01T09:00:00Z",
                "event_end": "2026-06-01T12:00:00Z",
                "snapshot_at": "2026-06-01T12:30:00Z",
                "content_bundle_digest": self.policy["catalog"][
                    "content_bundle_digest"
                ],
                "policy_digest": prize_inputs.artifact_digest(self.policy),
                "boundaries": {
                    "stage_close_at": {
                        "training": "2026-06-01T10:00:00Z",
                        "keplerops": "2026-06-01T11:00:00Z",
                        "arwc": "2026-06-01T12:00:00Z",
                    },
                    "nomination_open_at": "2026-06-01T09:00:00Z",
                    "nomination_close_at": "2026-06-01T11:30:00Z",
                    "claim_deadline_at": "2026-06-01T13:00:00Z",
                    "finalize_at": "2026-06-01T14:00:00Z",
                    "draw_seed_commitment": "sha256:" + ("a" * 64),
                },
            },
            "participants": participants,
            "submissions": submissions,
            "ranking": ranking,
            "occurrences": [
                accepted_occurrence,
                deepcopy(accepted_occurrence),
                stage_occurrence,
                deepcopy(stage_occurrence),
            ],
        }

    @staticmethod
    def _submission(
        *,
        submission_id: str,
        participant_id: str,
        source_id: str,
        points: int,
        submitted_at: str,
        is_correct: bool = True,
    ) -> dict:
        return {
            "event_id": EVENT_ID,
            "submission_id": submission_id,
            "participant_id": participant_id,
            "challenge_source_id": source_id,
            "is_correct": is_correct,
            "points_awarded": points,
            "submitted_at": submitted_at,
        }

    @staticmethod
    def _ranking(
        participant_id: str, *, score: int, count: int, last: str | None
    ) -> dict:
        return {
            "event_id": EVENT_ID,
            "participant_id": participant_id,
            "score": score,
            "solve_count": count,
            "last_solve_at": last,
        }

    def test_snapshot_is_deterministic_minimal_and_retry_safe(self) -> None:
        snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        prize_inputs.validate_prize_input(self.policy, snapshot)

        self.assertEqual(snapshot["contract"], prize_inputs.CONTRACT)
        self.assertEqual(len(snapshot["participants"]), 4)
        self.assertEqual(len(snapshot["accepted_solves"]), 19)
        self.assertEqual(len(snapshot["occurrences"]), 2)
        self.assertEqual(len(snapshot["stage_results"]["training"]), 3)
        self.assertEqual(
            snapshot, prize_inputs.build_prize_input(self.policy, deepcopy(self.source))
        )

        serialized = json.dumps(snapshot).lower()
        for private_or_untrusted_field in (
            "email",
            "username",
            "status_reason",
            "flag",
            "category",
            "is_correct",
        ):
            self.assertNotIn(private_or_untrusted_field, serialized)

    def test_exact_stage_membership_drives_completion_and_scores(self) -> None:
        snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        rows = {
            row["participant_id"]: row for row in snapshot["stage_results"]["training"]
        }
        winner = rows[PARTICIPANTS[0]]
        self.assertEqual(winner["score"], 160)
        self.assertEqual(winner["solve_count"], len(self.training_ids))
        self.assertEqual(winner["completed_at"], "2026-06-01T09:16:00Z")
        self.assertEqual(winner["completing_submission_id"], _uuid(1016))
        self.assertIsNone(rows[PARTICIPANTS[1]]["completed_at"])

        incomplete = deepcopy(self.source)
        incomplete["submissions"] = [
            row
            for row in incomplete["submissions"]
            if row["submission_id"] != _uuid(1016)
        ]
        incomplete["occurrences"] = [
            row
            for row in incomplete["occurrences"]
            if row["submission_id"] != _uuid(1016)
        ]
        first = next(
            row
            for row in incomplete["ranking"]
            if row["participant_id"] == PARTICIPANTS[0]
        )
        first.update(
            {
                "score": 150,
                "solve_count": 15,
                "last_solve_at": "2026-06-01T09:15:00Z",
            }
        )
        rebuilt = prize_inputs.build_prize_input(self.policy, incomplete)
        first_stage = next(
            row
            for row in rebuilt["stage_results"]["training"]
            if row["participant_id"] == PARTICIPANTS[0]
        )
        self.assertIsNone(first_stage["completed_at"])
        self.assertIsNone(first_stage["completing_submission_id"])

    def test_overall_ties_use_stable_private_participant_id(self) -> None:
        snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        ranking = snapshot["overall_ranking"]
        self.assertEqual(
            [row["participant_id"] for row in ranking],
            [PARTICIPANTS[0], PARTICIPANTS[1], PARTICIPANTS[2]],
        )
        self.assertEqual([row["position"] for row in ranking], [1, 2, 3])

    def test_rejected_and_stale_submissions_create_no_solve_fact(self) -> None:
        changed = deepcopy(self.source)
        changed["submissions"].append(
            self._submission(
                submission_id=_uuid(4001),
                participant_id=PARTICIPANTS[1],
                source_id=self.training_ids[2],
                points=50,
                submitted_at="2026-06-01T12:01:00Z",
            )
        )
        baseline = prize_inputs.build_prize_input(self.policy, self.source)
        rebuilt = prize_inputs.build_prize_input(self.policy, changed)
        self.assertEqual(rebuilt, baseline)

    def test_scope_binding_and_closed_fields_fail_safely(self) -> None:
        mutations = []

        wrong_digest = deepcopy(self.source)
        wrong_digest["event"]["content_bundle_digest"] = "sha256:" + ("0" * 64)
        mutations.append(wrong_digest)

        cross_event = deepcopy(self.source)
        cross_event["submissions"][0]["event_id"] = _uuid(9999)
        mutations.append(cross_event)

        extra_pii = deepcopy(self.source)
        extra_pii["participants"][0]["email"] = "private@example.test"
        mutations.append(extra_pii)

        incomplete = deepcopy(self.source)
        del incomplete["submissions"][0]["submission_id"]
        mutations.append(incomplete)

        unknown_source = deepcopy(self.source)
        unknown_source["submissions"][0]["challenge_source_id"] = "t99.9"
        mutations.append(unknown_source)

        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(prize_inputs.PrizeInputError):
                    prize_inputs.build_prize_input(self.policy, changed)

    def test_conflicting_submission_and_trigger_retries_fail_safely(self) -> None:
        conflicting_submission = deepcopy(self.source)
        duplicate = deepcopy(conflicting_submission["submissions"][0])
        duplicate["points_awarded"] += 1
        conflicting_submission["submissions"].append(duplicate)
        with self.assertRaisesRegex(
            prize_inputs.PrizeInputError, "conflicting duplicate submission"
        ):
            prize_inputs.build_prize_input(self.policy, conflicting_submission)

        duplicate_solve = deepcopy(self.source)
        duplicate = deepcopy(duplicate_solve["submissions"][0])
        duplicate["submission_id"] = _uuid(5001)
        duplicate_solve["submissions"].append(duplicate)
        with self.assertRaisesRegex(
            prize_inputs.PrizeInputError, "multiple accepted submissions"
        ):
            prize_inputs.build_prize_input(self.policy, duplicate_solve)

        second_close = deepcopy(self.source)
        duplicate = deepcopy(second_close["occurrences"][-1])
        duplicate["occurrence_id"] = _uuid(9002)
        second_close["occurrences"].append(duplicate)
        with self.assertRaisesRegex(
            prize_inputs.PrizeInputError, "multiple occurrence identities"
        ):
            prize_inputs.build_prize_input(self.policy, second_close)

    def test_close_occurrences_use_scheduled_and_actual_execution_times(self) -> None:
        early = deepcopy(self.source)
        for row in early["occurrences"]:
            if row["trigger"] == "stage_closed":
                row["executed_at"] = "2026-06-01T09:59:59Z"
        with self.assertRaisesRegex(
            prize_inputs.PrizeInputError, "authoritative boundary"
        ):
            prize_inputs.build_prize_input(self.policy, early)

        missing_dependencies = deepcopy(self.source)
        missing_dependencies["occurrences"].append(
            {
                "event_id": EVENT_ID,
                "occurrence_id": _uuid(9991),
                "trigger": "event_closed",
                "stage": None,
                "submission_id": None,
                "scheduled_for": "2026-06-01T12:00:00Z",
                "executed_at": "2026-06-01T12:00:01Z",
            }
        )
        with self.assertRaisesRegex(
            prize_inputs.PrizeInputError, "earlier close occurrence"
        ):
            prize_inputs.build_prize_input(self.policy, missing_dependencies)

    def test_mutated_published_snapshot_cannot_be_reused(self) -> None:
        snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        mutations = []

        changed_score = deepcopy(snapshot)
        changed_score["stage_results"]["training"][0]["score"] += 1
        mutations.append(changed_score)

        changed_rank = deepcopy(snapshot)
        changed_rank["overall_ranking"][0]["position"] = 2
        mutations.append(changed_rank)

        changed_policy = deepcopy(snapshot)
        changed_policy["event"]["policy_digest"] = "sha256:" + ("0" * 64)
        mutations.append(changed_policy)

        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(prize_inputs.PrizeInputError):
                    prize_inputs.validate_prize_input(self.policy, changed)

    def test_concurrent_rebuilds_produce_one_identical_snapshot(self) -> None:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda _: prize_inputs.canonical_json_bytes(
                        prize_inputs.build_prize_input(
                            self.policy, deepcopy(self.source)
                        )
                    ),
                    range(24),
                )
            )
        self.assertEqual(len(set(results)), 1)

    def test_operator_snapshot_is_written_owner_only(self) -> None:
        snapshot = prize_inputs.build_prize_input(self.policy, self.source)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event-prize-input.json"
            prize_inputs.write_private_json(path, snapshot)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(
                path.read_bytes(), prize_inputs.canonical_json_bytes(snapshot)
            )


if __name__ == "__main__":
    unittest.main()
