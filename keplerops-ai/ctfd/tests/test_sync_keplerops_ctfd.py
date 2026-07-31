"""Tests for the KeplerOps CTFd reference projection."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import io
import json
import os
import re
import stat
import sys
import tempfile
import unittest

CTFD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.dirname(CTFD_DIR)
if CTFD_DIR not in sys.path:
    sys.path.insert(0, CTFD_DIR)

import keplerops_flag_manifest as manifest  # noqa: E402
from plugins.keplerops_oracle_flags import receipt as oracle_bound_flag  # noqa: E402
import sync_keplerops_ctfd as loader  # noqa: E402
from ctfd_reconcile import SyncError, validate_base_url  # noqa: E402


class FakeClient:
    child = re.compile(r"^/challenges/(\d+)/(flags|hints|tags)$")
    row = re.compile(r"^/(challenges|flags|hints|tags)/(\d+)$")

    def __init__(self, page_size: int = 100) -> None:
        self.challenges = {}
        self.flags = {}
        self.hints = {}
        self.tags = {}
        self.next_id = 1
        self.page_size = page_size

    def _new(self):
        value = self.next_id
        self.next_id += 1
        return value

    def get(self, path, query=None):
        query = query or {}
        if path == "/challenges":
            rows = list(self.challenges.values())
            page = int(query.get("page", 1))
            start = (page - 1) * self.page_size
            pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
            return {"data": rows[start:start + self.page_size], "meta": {"pagination": {"pages": pages}}}
        match = self.child.match(path)
        if match:
            cid, kind = int(match.group(1)), match.group(2)
            return {"data": [row for row in getattr(self, kind).values() if row["challenge_id"] == cid]}
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, body):
        store = getattr(self, path.removeprefix("/"))
        row = {"id": self._new(), **body}
        store[row["id"]] = row
        return {"data": row}

    def patch(self, path, body):
        match = self.row.match(path)
        if not match:
            raise AssertionError(f"unexpected PATCH {path}")
        store = getattr(self, match.group(1))
        store[int(match.group(2))].update(body)
        return {"data": store[int(match.group(2))]}

    def delete(self, path):
        match = self.row.match(path)
        if not match:
            raise AssertionError(f"unexpected DELETE {path}")
        getattr(self, match.group(1)).pop(int(match.group(2)), None)
        return {"success": True}


class ManifestTests(unittest.TestCase):
    def test_gcp_full_projects_all_rows(self):
        rows = manifest.load_manifest(PACK_DIR, profile="gcp_full")
        self.assertEqual(len(rows), 134)
        self.assertEqual(len({row["flag_id"] for row in rows}), 134)
        self.assertTrue(all(row["managed_tag"].endswith(row["flag_id"]) for row in rows))
        self.assertTrue(all("answer" not in row for row in rows))
        self.assertTrue(all(row["acceptance"]["type"] == "keplerops_oracle" for row in rows))
        self.assertTrue(all(row["acceptance"]["challenge_id"] == row["challenge_id"] for row in rows))
        self.assertTrue(all(row["acceptance"]["prerequisites"] == row["prerequisites"] for row in rows))
        expected_agent_flags = {
            "flag-agent-proposal", "flag-agent-argument-smuggling",
            "flag-agent-control", "flag-agent-role-confusion",
            "flag-indirect-agent-control", "flag-agent-deputy-chain",
            "flag-agent-triggered-artifact", "flag-agent-package-execution",
            "flag-agent-click-execution", "flag-public-prompt-execution",
        }
        agent_rows = {
            row["flag_id"]: row for row in rows
            if row["flag_id"] in expected_agent_flags
        }
        self.assertEqual(set(agent_rows), expected_agent_flags)
        self.assertEqual(
            {flag_id: row["value"] for flag_id, row in agent_rows.items()},
            {
                "flag-agent-proposal": 50,
                "flag-agent-argument-smuggling": 50,
                "flag-agent-control": 50,
                "flag-agent-role-confusion": 100,
                "flag-indirect-agent-control": 100,
                "flag-agent-deputy-chain": 200,
                "flag-agent-triggered-artifact": 100,
                "flag-agent-package-execution": 100,
                "flag-agent-click-execution": 50,
                "flag-public-prompt-execution": 50,
            },
        )
        expected_evasion_values = {
            "flag-model-evasion": 50,
            "flag-encoding-evasion": 50,
            "flag-semantic-evasion": 50,
            "flag-repeatable-evasion": 100,
            "flag-transfer-evasion": 100,
            "flag-ensemble-evasion": 200,
        }
        self.assertEqual(
            {
                row["flag_id"]: row["value"]
                for row in rows
                if row["flag_id"] in expected_evasion_values
            },
            expected_evasion_values,
        )
        expected_context_values = {
            "flag-context-ingestion": 50,
            "flag-context-ranking": 50,
            "flag-context-poisoning": 50,
            "flag-citation-laundering": 100,
            "flag-trusted-knowledge-poisoning": 100,
            "flag-context-persistence": 200,
        }
        self.assertEqual(
            {
                row["flag_id"]: row["value"]
                for row in rows
                if row["flag_id"] in expected_context_values
            },
            expected_context_values,
        )

    def test_local_reduced_board_is_empty(self):
        self.assertEqual(manifest.load_manifest(PACK_DIR, profile="local_reduced"), [])

    def test_named_event_bundles_project_dependency_closed_subsets(self):
        expected = {
            "novice-manual": (48, {"easy", "medium"}),
            "intermediate-manual": (63, {"easy", "medium", "hard"}),
            "mixed-cohort": (66, {"easy", "medium", "hard", "insane"}),
        }
        for profile, (count, difficulties) in expected.items():
            with self.subTest(profile=profile):
                rows = manifest.load_manifest(PACK_DIR, profile=profile)
                self.assertEqual(len(rows), count)
                self.assertEqual({row["position"] for row in rows}, set(range(1, count + 1)))
                self.assertLessEqual({row["difficulty"] for row in rows}, difficulties)
                self.assertIn("flag-synthetic-spearphish", {row["flag_id"] for row in rows})

    def test_bundle_projection_blocks_planned_hardware_challenge(self):
        for profile in ("advanced-manual", "agent-heavy"):
            with (
                self.subTest(profile=profile),
                self.assertRaisesRegex(SyncError, "kep-m02-g"),
            ):
                manifest.load_manifest(PACK_DIR, profile=profile)

    def test_custom_selection_adds_dependency_closure(self):
        rows = manifest.load_custom_manifest(PACK_DIR, challenge_ids=["kep-m03-k"])
        self.assertEqual(
            {row["challenge_id"] for row in rows},
            {"kep-m03-a", "kep-m03-c", "kep-m03-k"},
        )
        self.assertEqual({row["position"] for row in rows}, {1, 2, 3})
        prerequisites = {row["challenge_id"]: row["prerequisites"] for row in rows}
        self.assertEqual(prerequisites["kep-m03-a"], [])
        self.assertEqual(prerequisites["kep-m03-c"], ["kep-m03-a"])
        self.assertEqual(prerequisites["kep-m03-k"], ["kep-m03-c"])


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient(page_size=2)
        self.rows = manifest.load_manifest(PACK_DIR, profile="gcp_full")

    def sync(self):
        return loader.sync_flag_layer(self.client, challenges=self.rows, dry_run=False)

    def test_sync_is_idempotent_and_readback_complete(self):
        ids = self.sync()
        first = (
            len(self.client.challenges),
            len(self.client.flags),
            len(self.client.hints),
            len(self.client.tags),
        )
        self.sync()
        self.assertEqual(
            first,
            (
                len(self.client.challenges),
                len(self.client.flags),
                len(self.client.hints),
                len(self.client.tags),
            ),
        )
        manifest.verify_challenge_rows(self.client, challenges=self.rows, flag_to_live_id=ids)

    def test_sync_projects_ctfd_requirements_from_aces_prerequisites(self):
        rows = manifest.load_custom_manifest(PACK_DIR, challenge_ids=["kep-m03-k"])
        ids = loader.sync_flag_layer(self.client, challenges=rows, dry_run=False)
        by_challenge = {row["challenge_id"]: row for row in rows}

        context_ranking = self.client.challenges[ids[by_challenge["kep-m03-c"]["flag_id"]]]
        context_persistence = self.client.challenges[ids[by_challenge["kep-m03-k"]["flag_id"]]]

        self.assertEqual(
            context_ranking["requirements"],
            {"prerequisites": [ids[by_challenge["kep-m03-a"]["flag_id"]]]},
        )
        self.assertEqual(
            context_persistence["requirements"],
            {"prerequisites": [ids[by_challenge["kep-m03-c"]["flag_id"]]]},
        )
        manifest.verify_challenge_rows(self.client, challenges=rows, flag_to_live_id=ids)

    def test_title_rename_uses_stable_managed_tag(self):
        self.sync()
        changed = [dict(row) for row in self.rows]
        changed[0] = {**changed[0], "name": "Renamed challenge"}
        loader.sync_flag_layer(self.client, challenges=changed, dry_run=False)
        self.assertEqual(len(self.client.challenges), len(self.rows))
        self.assertIn("Renamed challenge", {row["name"] for row in self.client.challenges.values()})

    def test_sync_preserves_unmanaged_tags_on_owned_challenge(self):
        ids = self.sync()
        first_id = ids[self.rows[0]["flag_id"]]
        self.client.post("/tags", {"challenge_id": first_id, "value": "event:vegas"})
        self.sync()
        tags = {row["value"] for row in self.client.get(f"/challenges/{first_id}/tags")["data"]}
        self.assertIn("event:vegas", tags)

    def test_stale_delete_is_owned_only(self):
        self.sync()
        self.client.post("/challenges", {"name": "Unrelated", "description": "x", "category": "x", "value": 1})
        prerequisites = {
            prerequisite for row in self.rows for prerequisite in row["prerequisites"]
        }
        leaf = next(row for row in self.rows if row["challenge_id"] not in prerequisites)
        reduced = [row for row in self.rows if row["challenge_id"] != leaf["challenge_id"]]
        loader.sync_flag_layer(self.client, challenges=reduced, dry_run=False)
        names = {row["name"] for row in self.client.challenges.values()}
        self.assertIn("Unrelated", names)
        self.assertEqual(len(names), len(self.rows))

    def test_rerun_repairs_partial_children(self):
        ids = self.sync()
        first_id = ids[self.rows[0]["flag_id"]]
        hint_id = self.client.get(f"/challenges/{first_id}/hints")["data"][0]["id"]
        self.client.delete(f"/hints/{hint_id}")
        self.sync()
        self.assertEqual(
            len(self.client.get(f"/challenges/{first_id}/hints")["data"]),
            len(self.rows[0]["hints"]),
        )

    def test_readback_detects_answer_drift_without_exposing_answer(self):
        ids = self.sync()
        first_id = ids[self.rows[0]["flag_id"]]
        flag = self.client.get(f"/challenges/{first_id}/flags")["data"][0]
        flag["content"] = "wrong"
        with self.assertRaises(SyncError) as raised:
            manifest.verify_challenge_rows(
                self.client, challenges=self.rows, flag_to_live_id=ids)
        self.assertNotIn("PEN{", str(raised.exception))

    def test_dry_run_redacts_answers(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            loader.sync_flag_layer(None, challenges=self.rows, dry_run=True)
        self.assertNotIn("PEN{", output.getvalue())

    def test_duplicate_managed_identity_fails_before_writes(self):
        self.sync()
        first = next(iter(self.client.challenges.values()))
        duplicate = self.client.post("/challenges", {
            "name": "duplicate", "description": "x", "category": "x", "value": 1,
        })["data"]
        tag = self.client.get(f"/challenges/{first['id']}/tags")["data"][0]["value"]
        self.client.post("/tags", {"challenge_id": duplicate["id"], "value": tag})
        before = dict(self.client.challenges)

        with self.assertRaisesRegex(SyncError, "duplicate managed challenge identity"):
            self.sync()

        self.assertEqual(self.client.challenges, before)


class OracleBoundFlagTests(unittest.TestCase):
    KEY = b"operator-only-test-key"
    CONTRACT = {
        "flag_id": "flag-agent-control",
        "outcome": "agent-control",
        "evidence": "ev-agent-control",
    }
    BINDING = {
        "range_instance": "range-17",
        "participant": "seat-04",
        "reset_generation": 3,
    }

    def receipt(self, *, signing_key=None, **changes):
        payload = {
            "version": 1,
            **self.CONTRACT,
            **self.BINDING,
            "verdict": "passed",
            "issued_at": 1_000,
            "expires_at": 1_600,
        }
        payload.update(changes)
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(
            signing_key if signing_key is not None else self.KEY,
            body,
            hashlib.sha256,
        ).hexdigest()
        return oracle_bound_flag.encode_receipt(body, signature)

    def test_accepts_current_receipt_for_bound_participant(self):
        self.assertTrue(oracle_bound_flag.verify_receipt(
            self.receipt(), contract=self.CONTRACT, binding=self.BINDING,
            verification_key=self.KEY, now=1_200,
        ))

    def test_rejects_receipt_signed_by_untrusted_key(self):
        self.assertFalse(oracle_bound_flag.verify_receipt(
            self.receipt(signing_key=b"untrusted-test-key"),
            contract=self.CONTRACT,
            binding=self.BINDING,
            verification_key=self.KEY,
            now=1_200,
        ))

    def test_rejects_cross_namespace_replay(self):
        self.assertFalse(oracle_bound_flag.verify_receipt(
            self.receipt(participant="seat-05"), contract=self.CONTRACT,
            binding=self.BINDING, verification_key=self.KEY, now=1_200,
        ))
        self.assertFalse(oracle_bound_flag.verify_receipt(
            self.receipt(range_instance="range-18"), contract=self.CONTRACT,
            binding=self.BINDING, verification_key=self.KEY, now=1_200,
        ))

    def test_rejects_stale_or_pre_reset_receipt(self):
        self.assertFalse(oracle_bound_flag.verify_receipt(
            self.receipt(expires_at=1_100), contract=self.CONTRACT,
            binding=self.BINDING, verification_key=self.KEY, now=1_200,
        ))
        self.assertFalse(oracle_bound_flag.verify_receipt(
            self.receipt(reset_generation=2), contract=self.CONTRACT,
            binding=self.BINDING, verification_key=self.KEY, now=1_200,
        ))
        self.assertEqual(
            oracle_bound_flag.verify_receipt_status(
                self.receipt(expires_at=1_100),
                contract=self.CONTRACT,
                binding=self.BINDING,
                verification_key=self.KEY,
                now=1_200,
            ),
            oracle_bound_flag.STATUS_EXPIRED_RECEIPT,
        )
        self.assertEqual(
            oracle_bound_flag.verify_receipt_status(
                self.receipt(reset_generation=2),
                contract=self.CONTRACT,
                binding=self.BINDING,
                verification_key=self.KEY,
                now=1_200,
            ),
            oracle_bound_flag.STATUS_STALE_RESET_GENERATION,
        )

    def test_rejects_receipt_for_other_outcome(self):
        self.assertFalse(oracle_bound_flag.verify_receipt(
            self.receipt(outcome="model-evasion"), contract=self.CONTRACT,
            binding=self.BINDING, verification_key=self.KEY, now=1_200,
        ))


class TokenTests(unittest.TestCase):
    def test_token_file_must_not_be_group_or_world_readable(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write("token")
        self.addCleanup(os.unlink, fh.name)
        os.chmod(fh.name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        with self.assertRaises(loader.SyncError):
            loader.resolve_token(fh.name)

    def test_token_from_secure_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write(" token\n")
        self.addCleanup(os.unlink, fh.name)
        os.chmod(fh.name, stat.S_IRUSR | stat.S_IWUSR)
        self.assertEqual(loader.resolve_token(fh.name), "token")

    def test_token_cannot_be_passed_on_command_line(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            loader.parse_args(["--base-url", "https://ctf.example", "--token", "secret"])

    def test_base_url_rejects_credentials_and_non_loopback_http(self):
        with self.assertRaises(SyncError):
            validate_base_url("https://user:secret@ctf.example")
        with self.assertRaises(SyncError):
            validate_base_url("http://ctf.example")
        self.assertEqual(validate_base_url("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")


if __name__ == "__main__":
    unittest.main()
