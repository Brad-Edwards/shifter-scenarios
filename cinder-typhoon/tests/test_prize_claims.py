from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_ROOT))
import test_prize_evaluator


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CLAIMS_PATH = Path(
    os.environ.get("CINDER_PRIZE_CLAIMS_PATH", ROOT / "ctfd" / "prize_claims.py")
)
prize_claims = _load_module("cinder_prize_claims_tests", CLAIMS_PATH)

ORIGIN = "https://event.example.test"
TOKEN_KEY = b"c" * 32
VIEW_TIME = datetime(2026, 6, 1, 12, 30, tzinfo=UTC)
DEADLINE = datetime(2026, 6, 1, 13, 0, tzinfo=UTC)
FINALIZE = datetime(2026, 6, 1, 14, 0, tzinfo=UTC)


def _request_id(value: int) -> str:
    return str(UUID(int=2_000_000 + value))


class PrizeClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = test_prize_evaluator.PrizeEvaluatorFixture()
        cls.config = prize_claims.build_claim_config(
            policy=cls.fixture.policy,
            snapshot=cls.fixture.snapshot(),
            public_origin=ORIGIN,
        )

    def _state(self, root: Path, *, finalization: bool = True) -> Path:
        state = root / "prizes.sqlite3"
        test_prize_evaluator.prize_evaluator.evaluate_snapshot(
            policy=self.fixture.policy,
            snapshot=self.fixture.snapshot(finalization=finalization),
            state_path=state,
            seed=test_prize_evaluator.SEED,
            nomination_input=self.fixture.nominations,
        )
        return state

    def _service(self, state: Path, *, token_key: bytes = TOKEN_KEY):
        return prize_claims.PrizeClaimService(
            config=self.config,
            state_path=state,
            token_key=token_key,
        )

    def _participant(
        self,
        participant_id: str,
        *,
        origin: str = ORIGIN,
        event_id: str = test_prize_evaluator.EVENT_ID,
    ):
        return prize_claims.AuthenticatedParticipant(
            event_id=event_id,
            participant_id=participant_id,
            session_id=f"session-{participant_id}",
            origin=origin,
        )

    def _staff(
        self,
        *,
        manager: bool = True,
        admin: bool = True,
        origin: str = ORIGIN,
        event_id: str = test_prize_evaluator.EVENT_ID,
    ):
        return prize_claims.AuthenticatedEventStaff(
            event_id=event_id,
            staff_id="staff-operator-1",
            can_manage_prizes=manager,
            is_event_admin=admin,
            origin=origin,
        )

    @staticmethod
    def _allocations(state: Path) -> list[dict]:
        return test_prize_evaluator.prize_evaluator.active_allocations(
            state, test_prize_evaluator.EVENT_ID
        )

    def _code(self, service, participant_id: str, *, now=VIEW_TIME) -> dict:
        return service.participant_prize(
            self._participant(participant_id),
            issue_code=True,
            now=now,
        )

    def test_configuration_binds_exact_inventory_and_rejects_state_drift(self) -> None:
        self.assertEqual(self.config["inventory"], list(range(1, 51)))
        self.assertEqual(len(self.config["slots"]), 50)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self._state(root)
            self._service(state)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)
            connection = sqlite3.connect(state)
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM prize_pack").fetchone()[0],
                    50,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM claim_slot").fetchone()[0],
                    50,
                )
            finally:
                connection.close()

            with self.assertRaisesRegex(prize_claims.PrizeClaimError, "token key"):
                self._service(state, token_key=b"d" * 32)
            changed = deepcopy(self.config)
            changed["public_origin"] = "https://other.example.test"
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "different config"
            ):
                prize_claims.PrizeClaimService(
                    config=changed,
                    state_path=state,
                    token_key=TOKEN_KEY,
                )

            link = root / "linked.sqlite3"
            link.symlink_to(state)
            with self.assertRaisesRegex(prize_claims.PrizeClaimError, "symbolic link"):
                self._service(link)

            empty = root / "empty.sqlite3"
            empty.touch()
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "evaluator database"
            ):
                self._service(empty)

    def test_notifications_are_minimal_stable_and_retry_once_per_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory))
            service = self._service(state)
            self.assertEqual(service.sync_allocations(now=VIEW_TIME), 50)
            self.assertEqual(service.sync_allocations(now=VIEW_TIME), 0)
            calls: list[dict] = []
            failed_key = None

            def deliver(message: dict) -> str:
                nonlocal failed_key
                calls.append(message)
                if failed_key is None:
                    failed_key = message["idempotency_key"]
                    raise RuntimeError("private provider failure text")
                return f"delivery-{len(calls)}"

            first = service.release_notifications(deliver, now=VIEW_TIME)
            self.assertEqual(len(first), 50)
            self.assertEqual(sum(row["state"] == "failed" for row in first), 1)
            self.assertEqual(len(calls), 50)
            second = service.release_notifications(deliver, now=VIEW_TIME)
            self.assertEqual(
                second,
                [{"idempotency_key": failed_key, "state": "delivered"}],
            )
            self.assertEqual(calls[0]["idempotency_key"], calls[-1]["idempotency_key"])
            self.assertEqual(len({row["idempotency_key"] for row in calls}), 50)
            recovery_key = calls[1]["idempotency_key"]
            connection = sqlite3.connect(state)
            try:
                connection.execute(
                    "UPDATE notification_intent SET state = 'releasing', updated_at = ? "
                    "WHERE event_id = ? AND idempotency_key = ?",
                    (
                        "2026-06-01T12:30:00Z",
                        test_prize_evaluator.EVENT_ID,
                        recovery_key,
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            recovered = service.release_notifications(
                deliver,
                now=VIEW_TIME
                + timedelta(seconds=prize_claims.RELEASE_LEASE_SECONDS + 1),
            )
            self.assertEqual(
                recovered,
                [{"idempotency_key": recovery_key, "state": "delivered"}],
            )
            for message in calls:
                self.assertEqual(
                    set(message),
                    {
                        "contract",
                        "idempotency_key",
                        "recipient_participant_id",
                        "template",
                        "variables",
                    },
                )
                self.assertEqual(
                    set(message["variables"]),
                    {"award_name", "claim_status", "participant_path"},
                )
                serialized = json.dumps(message).lower()
                for forbidden in ("ranking", "nomination", "draw_rank", "score"):
                    self.assertNotIn(forbidden, serialized)

            stored = state.read_bytes()
            self.assertNotIn(b"private provider failure text", stored)
            connection = sqlite3.connect(state)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM notification_intent "
                        "WHERE state = 'delivered'"
                    ).fetchone()[0],
                    50,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT last_error_code FROM notification_intent "
                        "WHERE idempotency_key = ?",
                        (failed_key,),
                    ).fetchone()[0],
                    None,
                )
            finally:
                connection.close()

    def test_participant_code_is_private_rotated_and_claim_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory))
            service = self._service(state)
            winner = self._allocations(state)[0]
            context = self._participant(winner["participant_id"])
            first = service.participant_prize(context, issue_code=True, now=VIEW_TIME)
            second = service.participant_prize(context, issue_code=True, now=VIEW_TIME)
            self.assertEqual(
                set(second),
                {
                    "contract",
                    "award_name",
                    "notification_state",
                    "claim_status",
                    "pack_number",
                    "claimed_at",
                    "claim_code",
                    "qr_payload",
                    "expires_at",
                },
            )
            self.assertEqual(second["expires_at"], "2026-06-01T12:40:00Z")
            self.assertTrue(second["qr_payload"].endswith(second["claim_code"]))
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "invalid or expired"
            ):
                service.claim(
                    self._staff(),
                    claim_code=first["claim_code"],
                    pack_number=1,
                    request_id=_request_id(1),
                    now=VIEW_TIME,
                )

            request_id = _request_id(2)
            receipt = service.claim(
                self._staff(),
                claim_code=second["qr_payload"],
                pack_number=1,
                request_id=request_id,
                now=VIEW_TIME,
            )
            self.assertEqual(
                service.claim(
                    self._staff(),
                    claim_code=second["claim_code"],
                    pack_number=1,
                    request_id=request_id,
                    now=VIEW_TIME,
                ),
                receipt,
            )
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "different input"
            ):
                service.claim(
                    self._staff(),
                    claim_code=second["claim_code"],
                    pack_number=2,
                    request_id=request_id,
                    now=VIEW_TIME,
                )
            claimed_view = service.participant_prize(context, now=VIEW_TIME)
            self.assertEqual(claimed_view["claim_status"], "claimed")
            self.assertEqual(claimed_view["pack_number"], 1)
            self.assertIsNone(claimed_view["claim_code"])

            stored = state.read_bytes()
            for secret in (
                TOKEN_KEY,
                context.session_id.encode(),
                first["claim_code"].encode(),
                second["claim_code"].encode(),
            ):
                self.assertNotIn(secret, stored)

    def test_pack_claim_is_atomic_under_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory))
            service = self._service(state)
            winners = self._allocations(state)[:2]
            codes = [
                self._code(service, row["participant_id"])["claim_code"]
                for row in winners
            ]

            def claim(index: int):
                try:
                    return service.claim(
                        self._staff(),
                        claim_code=codes[index],
                        pack_number=7,
                        request_id=_request_id(10 + index),
                        now=VIEW_TIME,
                    )
                except prize_claims.PrizeClaimError as error:
                    return str(error)

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(claim, range(2)))
            self.assertEqual(sum(isinstance(row, dict) for row in results), 1)
            self.assertEqual(
                sum(row == "prize pack is already used" for row in results), 1
            )
            connection = sqlite3.connect(state)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM prize_claim WHERE pack_number = 7"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_authentication_event_origin_and_admin_boundaries_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory))
            service = self._service(state)
            winner = self._allocations(state)[0]
            for context in (
                self._participant(
                    winner["participant_id"], origin="https://evil.example.test"
                ),
                self._participant(
                    winner["participant_id"], event_id=str(UUID(int=9_999_999))
                ),
            ):
                with self.assertRaises(prize_claims.PrizeClaimError):
                    service.participant_prize(context, now=VIEW_TIME)

            for staff in (
                self._staff(manager=False),
                self._staff(origin="https://evil.example.test"),
                self._staff(event_id=str(UUID(int=9_999_999))),
            ):
                with self.assertRaises(prize_claims.PrizeClaimError):
                    service.dashboard(staff)

            with self.assertRaisesRegex(prize_claims.PrizeClaimError, "authority"):
                service.void_unclaimed(
                    self._staff(admin=False),
                    slot_id=winner["slot_id"],
                    generation=winner["generation"],
                    reason="operator correction",
                    request_id=_request_id(20),
                    now=VIEW_TIME,
                )

    def test_deadline_is_half_open_preserves_claims_and_enables_final_rollover(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory), finalization=False)
            service = self._service(state)
            initial = self._allocations(state)
            winner = initial[0]
            live = self._code(
                service,
                winner["participant_id"],
                now=DEADLINE - timedelta(minutes=2),
            )
            service.claim(
                self._staff(),
                claim_code=live["claim_code"],
                pack_number=1,
                request_id=_request_id(31),
                now=DEADLINE - timedelta(minutes=1),
            )
            expiring = self._code(
                service,
                initial[1]["participant_id"],
                now=DEADLINE - timedelta(minutes=1),
            )
            self.assertEqual(expiring["expires_at"], "2026-06-01T13:00:00Z")
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "invalid or expired"
            ):
                service.claim(
                    self._staff(),
                    claim_code=expiring["claim_code"],
                    pack_number=2,
                    request_id=_request_id(30),
                    now=DEADLINE,
                )
            with self.assertRaisesRegex(prize_claims.PrizeClaimError, "boundary"):
                service.expire_unclaimed(
                    occurrence_id=_request_id(32),
                    executed_at=DEADLINE - timedelta(microseconds=1),
                )

            occurrence_id = _request_id(33)
            expired = service.expire_unclaimed(
                occurrence_id=occurrence_id,
                executed_at=DEADLINE,
            )
            self.assertEqual(len(expired["voided"]), len(initial) - 1)
            self.assertEqual(
                service.expire_unclaimed(
                    occurrence_id=occurrence_id,
                    executed_at=DEADLINE,
                ),
                expired,
            )
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "identity changed"
            ):
                service.expire_unclaimed(
                    occurrence_id=_request_id(34),
                    executed_at=DEADLINE,
                )
            with self.assertRaisesRegex(prize_claims.PrizeClaimError, "finalization"):
                service.expire_unclaimed(
                    occurrence_id=_request_id(35),
                    executed_at=FINALIZE,
                )
            self.assertEqual(
                service.participant_prize(
                    self._participant(winner["participant_id"]), now=DEADLINE
                )["claim_status"],
                "claimed",
            )

            result = test_prize_evaluator.prize_evaluator.evaluate_snapshot(
                policy=self.fixture.policy,
                snapshot=self.fixture.snapshot(),
                state_path=state,
                seed=test_prize_evaluator.SEED,
                nomination_input=self.fixture.nominations,
            )
            self.assertGreater(result["active_allocation_count"], 1)
            final_winners = [
                row
                for row in result["active_allocations"]
                if row["selected_at"] >= "2026-06-01T14:00:00Z"
            ]
            self.assertTrue(final_winners)
            service.sync_allocations(now=FINALIZE + timedelta(seconds=10))
            final_code = self._code(
                service,
                final_winners[0]["participant_id"],
                now=FINALIZE + timedelta(seconds=10),
            )
            self.assertEqual(final_code["expires_at"], "2026-06-01T14:10:10Z")

    def test_reasoned_void_and_custody_correction_retain_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory))
            service = self._service(state)
            first, second = self._allocations(state)[:2]
            code = self._code(service, first["participant_id"])
            receipt = service.claim(
                self._staff(),
                claim_code=code["claim_code"],
                pack_number=1,
                request_id=_request_id(40),
                now=VIEW_TIME,
            )
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "cannot be voided"
            ):
                service.void_unclaimed(
                    self._staff(),
                    slot_id=first["slot_id"],
                    generation=first["generation"],
                    reason="not actually unclaimed",
                    request_id=_request_id(41),
                    now=VIEW_TIME,
                )

            void_id = _request_id(42)
            voided = service.void_unclaimed(
                self._staff(),
                slot_id=second["slot_id"],
                generation=second["generation"],
                reason="participant declined",
                request_id=void_id,
                now=VIEW_TIME,
            )
            self.assertEqual(
                service.void_unclaimed(
                    self._staff(),
                    slot_id=second["slot_id"],
                    generation=second["generation"],
                    reason="participant declined",
                    request_id=void_id,
                    now=VIEW_TIME,
                ),
                voided,
            )
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "different input"
            ):
                service.void_unclaimed(
                    self._staff(),
                    slot_id=second["slot_id"],
                    generation=second["generation"],
                    reason="changed reason",
                    request_id=void_id,
                    now=VIEW_TIME,
                )

            correction_id = _request_id(43)
            corrected = service.correct_claim(
                self._staff(),
                claim_id=receipt["claim_id"],
                reason="damaged outer packaging",
                replacement_pack_number=2,
                request_id=correction_id,
                now=VIEW_TIME,
            )
            self.assertEqual(corrected["from_pack_number"], 1)
            self.assertEqual(corrected["to_pack_number"], 2)
            self.assertEqual(
                service.correct_claim(
                    self._staff(),
                    claim_id=receipt["claim_id"],
                    reason="damaged outer packaging",
                    replacement_pack_number=2,
                    request_id=correction_id,
                    now=VIEW_TIME,
                ),
                corrected,
            )
            with self.assertRaisesRegex(
                prize_claims.PrizeClaimError, "different input"
            ):
                service.correct_claim(
                    self._staff(),
                    claim_id=receipt["claim_id"],
                    reason="changed reason",
                    replacement_pack_number=2,
                    request_id=correction_id,
                    now=VIEW_TIME,
                )

            connection = sqlite3.connect(state)
            try:
                attempts = connection.execute(
                    "SELECT status, void_reason, voided_at FROM allocation_attempt "
                    "WHERE event_id = ? AND slot_id = ? AND generation = ?",
                    (
                        test_prize_evaluator.EVENT_ID,
                        second["slot_id"],
                        second["generation"],
                    ),
                ).fetchone()
                self.assertEqual(attempts[0:2], ("voided", "participant declined"))
                self.assertIsNotNone(attempts[2])
                self.assertEqual(
                    connection.execute(
                        "SELECT pack_number FROM prize_claim WHERE claim_id = ?",
                        (receipt["claim_id"],),
                    ).fetchone()[0],
                    1,
                )
                packs = dict(
                    connection.execute(
                        "SELECT pack_number, status FROM prize_pack "
                        "WHERE pack_number IN (1, 2)"
                    )
                )
                self.assertEqual(packs, {1: "corrected_out", 2: "claimed"})
            finally:
                connection.close()
            voided_slot = next(
                row
                for row in service.dashboard(self._staff())["slots"]
                if row["slot_id"] == second["slot_id"]
            )
            self.assertEqual(voided_slot["allocation_state"], "voided")
            self.assertEqual(voided_slot["trigger_status"], "voided")

    def test_operator_surfaces_show_all_slots_without_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self._state(Path(directory))
            service = self._service(state)
            dashboard = service.dashboard(self._staff())
            self.assertEqual(len(dashboard["slots"]), 50)
            self.assertEqual(dashboard["errors"], [])
            self.assertTrue(all(row["selected_alias"] for row in dashboard["slots"]))
            self.assertTrue(all(row["trigger"] for row in dashboard["slots"]))
            self.assertEqual(
                {row["trigger_status"] for row in dashboard["slots"]}, {"recorded"}
            )
            summary = service.credential_free_summary(self._staff())
            serialized = json.dumps(summary)
            self.assertNotIn("staff-operator-1", serialized)
            self.assertNotIn("token", serialized.lower())
            for participant_id in self.fixture.participant_ids:
                self.assertNotIn(participant_id, serialized)
            self.assertIn("Player ", serialized)


if __name__ == "__main__":
    unittest.main()
