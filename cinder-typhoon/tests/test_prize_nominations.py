from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_ROOT))
import test_prize_evaluator  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


NOMINATIONS_PATH = Path(
    os.environ.get(
        "CINDER_PRIZE_NOMINATIONS_PATH", ROOT / "ctfd" / "prize_nominations.py"
    )
)
prize_nominations = _load_module("cinder_prize_nominations_tests", NOMINATIONS_PATH)

ORIGIN = "https://event.example.test"
TOKEN_KEY = b"n" * 32
WINDOW_TIME = datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc)
INVALID_CSRF = "not-a-valid-csrf-value"  # noqa: S105 - deliberate negative test input


def _request_id(value: int) -> str:
    return str(UUID(int=1_000_000 + value))


class PrizeNominationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = test_prize_evaluator.PrizeEvaluatorFixture()
        cls.snapshot = cls.fixture.snapshot()
        cls.checked_in = cls.fixture.participant_ids[:30]
        cls.config = prize_nominations.build_nomination_config(
            policy=cls.fixture.policy,
            snapshot=cls.snapshot,
            checked_in_participant_ids=cls.checked_in,
            public_origin=ORIGIN,
        )

    def _service(self, state: Path) -> prize_nominations.NominationService:
        return prize_nominations.NominationService(
            config=self.config,
            state_path=state,
            token_key=TOKEN_KEY,
        )

    def _context(
        self,
        participant_index: int = 0,
        *,
        session_id: str | None = None,
        origin: str = ORIGIN,
        event_id: str = test_prize_evaluator.EVENT_ID,
    ) -> prize_nominations.AuthenticatedParticipant:
        return prize_nominations.AuthenticatedParticipant(
            event_id=event_id,
            participant_id=self.checked_in[participant_index],
            session_id=session_id or f"session-{participant_index}",
            origin=origin,
        )

    @staticmethod
    def _payload(form: dict, *, candidate_index: int, request_number: int) -> dict:
        return {
            "request_id": _request_id(request_number),
            "csrf_token": form["csrf_token"],
            "candidate_token": form["candidates"][candidate_index]["candidate_token"],
            "attested": True,
        }

    def test_form_exposes_aliases_and_opaque_tokens_without_private_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "nominations.sqlite3"
            service = self._service(state)
            form = service.form(self._context(), now=WINDOW_TIME)
            self.assertEqual(len(form["candidates"]), len(self.checked_in) - 1)
            self.assertIsNone(form["submitted"])
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)
            serialized = json.dumps(form)
            for participant_id in self.checked_in:
                self.assertNotIn(participant_id, serialized)
            for candidate in form["candidates"]:
                self.assertEqual(set(candidate), {"public_alias", "candidate_token"})
                self.assertNotIn("@", candidate["public_alias"])

    def test_one_ballot_is_idempotent_only_for_the_same_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "nominations.sqlite3"
            service = self._service(state)
            context = self._context()
            form = service.form(context, now=WINDOW_TIME)
            payload = self._payload(form, candidate_index=0, request_number=1)
            receipt = service.submit(context, payload, now=WINDOW_TIME)
            self.assertEqual(service.submit(context, payload, now=WINDOW_TIME), receipt)
            self.assertEqual(
                receipt["nominee_alias"], form["candidates"][0]["public_alias"]
            )

            duplicate = self._payload(form, candidate_index=1, request_number=2)
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "already submitted"
            ):
                service.submit(context, duplicate, now=WINDOW_TIME)

            changed_retry = dict(payload)
            changed_retry["candidate_token"] = form["candidates"][1]["candidate_token"]
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "reused with different"
            ):
                service.submit(context, changed_retry, now=WINDOW_TIME)

            stored_bytes = state.read_bytes()
            for secret in (
                TOKEN_KEY,
                context.session_id.encode(),
                form["csrf_token"].encode(),
                payload["candidate_token"].encode(),
            ):
                self.assertNotIn(secret, stored_bytes)

    def test_csrf_origin_attestation_self_and_closed_payload_are_enforced(self) -> None:
        mutations = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self._service(root / "base.sqlite3")
            context = self._context()
            form = service.form(context, now=WINDOW_TIME)

            wrong_csrf = self._payload(form, candidate_index=0, request_number=10)
            wrong_csrf["csrf_token"] = INVALID_CSRF
            mutations.append(wrong_csrf)

            no_attestation = self._payload(form, candidate_index=0, request_number=11)
            no_attestation["attested"] = False
            mutations.append(no_attestation)

            free_text = self._payload(form, candidate_index=0, request_number=12)
            free_text["reason"] = "private free text"
            mutations.append(free_text)

            self_token = service._candidate_token(
                context.participant_id, context.session_id, context.participant_id
            )
            self_nomination = self._payload(form, candidate_index=0, request_number=13)
            self_nomination["candidate_token"] = self_token
            mutations.append(self_nomination)

            for index, payload in enumerate(mutations):
                isolated = self._service(root / f"mutation-{index}.sqlite3")
                isolated_form = isolated.form(context, now=WINDOW_TIME)
                payload["csrf_token"] = (
                    INVALID_CSRF if index == 0 else isolated_form["csrf_token"]
                )
                if index in (1, 2):
                    payload["candidate_token"] = isolated_form["candidates"][0][
                        "candidate_token"
                    ]
                if index == 3:
                    payload["candidate_token"] = isolated._candidate_token(
                        context.participant_id,
                        context.session_id,
                        context.participant_id,
                    )
                with (
                    self.subTest(index=index),
                    self.assertRaises(prize_nominations.PrizeNominationError),
                ):
                    isolated.submit(context, payload, now=WINDOW_TIME)

            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "origin"
            ):
                service.form(
                    self._context(origin="https://evil.example.test"),
                    now=WINDOW_TIME,
                )
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "another event"
            ):
                service.form(
                    self._context(event_id=str(UUID(int=9999))),
                    now=WINDOW_TIME,
                )

    def test_rate_limit_counts_rejected_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(Path(directory) / "nominations.sqlite3")
            context = self._context()
            form = service.form(context, now=WINDOW_TIME)
            for index in range(prize_nominations.RATE_LIMIT_ATTEMPTS):
                payload = self._payload(
                    form, candidate_index=0, request_number=100 + index
                )
                payload["csrf_token"] = INVALID_CSRF
                with self.assertRaises(prize_nominations.PrizeNominationError):
                    service.submit(
                        context,
                        payload,
                        now=WINDOW_TIME + timedelta(seconds=index),
                    )
            valid = self._payload(form, candidate_index=0, request_number=200)
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "rate limit"
            ):
                service.submit(
                    context,
                    valid,
                    now=WINDOW_TIME + timedelta(seconds=10),
                )
            self.assertEqual(service.audit_rows()[-1]["outcome"], "rate_limited")

    def test_window_is_half_open_and_server_close_overrides_time(self) -> None:
        closes = datetime(2026, 6, 1, 11, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            before = self._service(Path(directory) / "before.sqlite3")
            context = self._context()
            before_time = closes - timedelta(microseconds=1)
            form = before.form(context, now=before_time)
            receipt = before.submit(
                context,
                self._payload(form, candidate_index=0, request_number=300),
                now=before_time,
            )
            self.assertEqual(receipt["submitted_at"], "2026-06-01T11:29:59.999999Z")

            exact = self._service(Path(directory) / "exact.sqlite3")
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "not open"
            ):
                exact.form(context, now=closes)

            closed = self._service(Path(directory) / "closed.sqlite3")
            closed.close(policy=self.fixture.policy, snapshot=self.snapshot)
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "closed"
            ):
                closed.form(context, now=WINDOW_TIME)

    def test_concurrent_ballots_leave_one_active_ballot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "nominations.sqlite3"
            service = self._service(state)
            context = self._context()
            form = service.form(context, now=WINDOW_TIME)
            payloads = [
                self._payload(form, candidate_index=index, request_number=400 + index)
                for index in range(2)
            ]

            def submit(payload: dict) -> str:
                try:
                    service.submit(context, payload, now=WINDOW_TIME)
                except prize_nominations.PrizeNominationError:
                    return "rejected"
                return "accepted"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(submit, payloads))
            self.assertEqual(sorted(outcomes), ["accepted", "rejected"])
            connection = sqlite3.connect(state)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM nomination_ballot"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_close_is_idempotent_private_and_feeds_the_evaluator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self._service(root / "nominations.sqlite3")
            for participant_index, candidate_index in ((0, 1), (1, 1)):
                context = self._context(participant_index)
                form = service.form(context, now=WINDOW_TIME)
                service.submit(
                    context,
                    self._payload(
                        form,
                        candidate_index=candidate_index,
                        request_number=500 + participant_index,
                    ),
                    now=WINDOW_TIME,
                )
            exported = service.close(
                policy=self.fixture.policy,
                snapshot=self.snapshot,
            )
            self.assertEqual(
                service.close(policy=self.fixture.policy, snapshot=self.snapshot),
                exported,
            )
            self.assertEqual(
                exported["contract"],
                test_prize_evaluator.prize_evaluator.NOMINATIONS_CONTRACT,
            )
            self.assertEqual(len(exported["ballots"]), 2)
            serialized = json.dumps(exported)
            for forbidden in ("public_alias", "session", "csrf", "reason"):
                self.assertNotIn(forbidden, serialized.lower())

            result = test_prize_evaluator.prize_evaluator.evaluate_snapshot(
                policy=self.fixture.policy,
                snapshot=self.snapshot,
                state_path=root / "evaluator.sqlite3",
                seed=test_prize_evaluator.SEED,
                nomination_input=exported,
            )
            self.assertEqual(result["active_allocation_count"], 50)
            self.assertEqual(service.audit_rows()[-1]["outcome"], "closed")

    def test_config_and_state_bind_checked_in_scope_and_owner_only_file(self) -> None:
        ineligible_snapshot = deepcopy(self.snapshot)
        ineligible_snapshot["participants"][0]["prize_eligible"] = False
        ineligible_snapshot["overall_ranking"] = [
            row
            for row in ineligible_snapshot["overall_ranking"]
            if row["participant_id"] != self.checked_in[0]
        ]
        with self.assertRaises(prize_nominations.PrizeNominationError):
            prize_nominations.build_nomination_config(
                policy=self.fixture.policy,
                snapshot=ineligible_snapshot,
                checked_in_participant_ids=[self.checked_in[0]],
                public_origin=ORIGIN,
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "nominations.sqlite3"
            self._service(state)
            changed = deepcopy(self.config)
            changed["participants"].pop()
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "different config"
            ):
                prize_nominations.NominationService(
                    config=changed,
                    state_path=state,
                    token_key=TOKEN_KEY,
                )
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "token key"
            ):
                prize_nominations.NominationService(
                    config=self.config,
                    state_path=state,
                    token_key=b"x" * 32,
                )
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)
            target = root / "target.sqlite3"
            target.touch(mode=0o600)
            link = root / "linked.sqlite3"
            link.symlink_to(target)
            with self.assertRaisesRegex(
                prize_nominations.PrizeNominationError, "symbolic link"
            ):
                self._service(link)

    def test_audit_is_private_structured_and_contains_no_free_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "nominations.sqlite3"
            service = self._service(state)
            context = self._context()
            form = service.form(context, now=WINDOW_TIME)
            rejected = self._payload(form, candidate_index=0, request_number=600)
            rejected["csrf_token"] = INVALID_CSRF
            with self.assertRaises(prize_nominations.PrizeNominationError):
                service.submit(context, rejected, now=WINDOW_TIME)
            accepted = self._payload(form, candidate_index=0, request_number=601)
            service.submit(context, accepted, now=WINDOW_TIME + timedelta(seconds=1))
            rows = service.audit_rows()
            self.assertEqual(
                [row["outcome"] for row in rows], ["csrf_rejected", "accepted"]
            )
            self.assertEqual(
                set(rows[0]),
                {
                    "actor_id",
                    "action",
                    "outcome",
                    "target_id",
                    "request_id",
                    "occurred_at",
                },
            )
            self.assertNotIn(INVALID_CSRF, json.dumps(rows))


if __name__ == "__main__":
    unittest.main()
