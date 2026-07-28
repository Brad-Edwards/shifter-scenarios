"""Behavioral tests for the canonical Polaris CTFd projection."""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import yaml


CTFD_DIR = Path(__file__).resolve().parents[1]
PACK_ROOT = CTFD_DIR.parent
sys.path.insert(0, str(CTFD_DIR))

import polaris_manifest as manifest  # noqa: E402
import sync_polaris_ctfd as loader  # noqa: E402
import ctfd_reconcile as reconciliation  # noqa: E402
from common import CtfdClient  # noqa: E402


class FakeCtfdClient:
    def __init__(self, *, page_size: int | None = None) -> None:
        self.challenges: dict[int, dict] = {}
        self.flags: dict[int, dict] = {}
        self.hints: dict[int, dict] = {}
        self.tags: dict[int, dict] = {}
        self.page_size = page_size
        self._next = 1

    def _id(self) -> int:
        ident = self._next
        self._next += 1
        return ident

    def seed_unrelated(self) -> int:
        ident = self._id()
        self.challenges[ident] = {
            "id": ident,
            "name": "Unrelated event row",
            "state": "visible",
        }
        return ident

    def seed_managed(
        self,
        ownership_tag: str,
        *,
        name: str = "Interrupted managed row",
        state: str = "hidden",
    ) -> int:
        challenge_id = self._id()
        self.challenges[challenge_id] = {
            "id": challenge_id,
            "name": name,
            "state": state,
        }
        tag_id = self._id()
        self.tags[tag_id] = {
            "id": tag_id,
            "challenge_id": challenge_id,
            "value": ownership_tag,
        }
        return challenge_id

    def get(self, path, query=None):
        query = query or {}
        if path == "/challenges":
            page = query.get("page", 1)
            rows = list(self.challenges.values())
            if self.page_size:
                start = (page - 1) * self.page_size
                page_rows = rows[start : start + self.page_size]
                pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
            else:
                page_rows = rows if page == 1 else []
                pages = 1
            return {
                "data": page_rows,
                "meta": {"pagination": {"pages": pages}},
            }
        if path == "/flags":
            challenge_id = query.get("challenge_id")
            return {
                "data": [
                    dict(row)
                    for row in self.flags.values()
                    if row["challenge_id"] == challenge_id
                ]
            }
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "challenges":
            challenge_id = int(parts[1])
            store = {
                "flags": self.flags,
                "hints": self.hints,
                "tags": self.tags,
            }[parts[2]]
            return {
                "data": [
                    dict(row)
                    for row in store.values()
                    if row["challenge_id"] == challenge_id
                ]
            }
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, body):
        store = {
            "/challenges": self.challenges,
            "/flags": self.flags,
            "/hints": self.hints,
            "/tags": self.tags,
        }[path]
        ident = self._id()
        store[ident] = {"id": ident, **body}
        return {"success": True, "data": dict(store[ident])}

    def patch(self, path, body):
        kind, raw_id = path.strip("/").split("/")
        store = {
            "challenges": self.challenges,
            "flags": self.flags,
            "hints": self.hints,
            "tags": self.tags,
        }[kind]
        store[int(raw_id)].update(body)
        return {"success": True, "data": dict(store[int(raw_id)])}

    def delete(self, path):
        kind, raw_id = path.strip("/").split("/")
        store = {
            "challenges": self.challenges,
            "flags": self.flags,
            "hints": self.hints,
            "tags": self.tags,
        }[kind]
        store.pop(int(raw_id), None)
        return {"success": True}


class ManifestTests(unittest.TestCase):
    def test_manifest_projects_exactly_the_implemented_flag_inventory(self):
        rows = manifest.load_manifest(PACK_ROOT, runtime_profile_id="aws_event")

        self.assertEqual(len(rows), 38)
        self.assertEqual(len({row["flag_id"] for row in rows}), 38)
        self.assertNotIn("category", rows[0]["source_challenge"])
        self.assertTrue(all(row["category"] for row in rows))
        self.assertTrue(all(row["ownership_tag"] for row in rows))
        manifest.validate_manifest(rows)

    def test_local_degraded_cannot_advertise_participant_flags(self):
        with self.assertRaises(manifest.SyncError):
            manifest.load_manifest(
                PACK_ROOT,
                runtime_profile_id="local_degraded",
            )

    def test_namespace_changes_ownership_without_changing_flag_identity(self):
        first = manifest.load_manifest(
            PACK_ROOT,
            runtime_profile_id="aws_event",
            event_namespace="red",
        )
        second = manifest.load_manifest(
            PACK_ROOT,
            runtime_profile_id="aws_event",
            event_namespace="blue",
        )

        self.assertEqual(first[0]["flag_id"], second[0]["flag_id"])
        self.assertNotEqual(
            first[0]["ownership_tag"],
            second[0]["ownership_tag"],
        )

    def test_duplicate_source_flag_id_is_rejected_before_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(PACK_ROOT / "flags", root / "flags")
            shutil.copytree(PACK_ROOT / "challenges", root / "challenges")
            placement_path = root / "flags" / "placement.yaml"
            placement = yaml.safe_load(placement_path.read_text(encoding="utf-8"))
            placement["flags"].append(dict(placement["flags"][0]))
            placement_path.write_text(
                yaml.safe_dump(placement, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(manifest.SyncError, "duplicate"):
                manifest.load_manifest(root, runtime_profile_id="aws_event")


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeCtfdClient()
        self.rows = manifest.load_manifest(
            PACK_ROOT,
            runtime_profile_id="aws_event",
            event_namespace="test",
        )

    def test_sync_is_idempotent_and_preserves_unrelated_rows(self):
        unrelated_id = self.client.seed_unrelated()

        first = loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )
        second = loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )

        self.assertIn(unrelated_id, self.client.challenges)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 38)
        manifest.verify_challenge_rows(
            self.client,
            challenges=self.rows,
            flag_id_to_live_id=second,
        )

    def test_paginated_board_sync_and_readback_cover_every_managed_row(self):
        client = FakeCtfdClient(page_size=7)

        ids = loader.sync_flag_layer(
            client,
            challenges=self.rows,
            dry_run=False,
        )

        manifest.verify_challenge_rows(
            client,
            challenges=self.rows,
            flag_id_to_live_id=ids,
        )
        self.assertEqual(len(ids), 38)

    def test_sync_deletes_only_stale_rows_in_the_selected_namespace(self):
        stale_id = self.client.seed_managed(
            "panw:polaris:test:retired-flag"
        )
        other_namespace_id = self.client.seed_managed(
            "panw:polaris:blue:retired-flag"
        )
        unrelated_id = self.client.seed_unrelated()

        loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )

        self.assertNotIn(stale_id, self.client.challenges)
        self.assertIn(other_namespace_id, self.client.challenges)
        self.assertIn(unrelated_id, self.client.challenges)

    def test_sync_repairs_interrupted_hidden_row_before_making_it_visible(self):
        interrupted_id = self.client.seed_managed(
            self.rows[0]["ownership_tag"],
            name=self.rows[0]["name"],
        )

        ids = loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )

        self.assertEqual(ids[self.rows[0]["flag_id"]], interrupted_id)
        self.assertEqual(self.client.challenges[interrupted_id]["state"], "visible")
        self.assertTrue(
            any(
                row["challenge_id"] == interrupted_id
                for row in self.client.flags.values()
            )
        )
        self.assertTrue(
            any(
                row["challenge_id"] == interrupted_id
                for row in self.client.hints.values()
            )
        )

    def test_readback_rejects_answer_drift_without_disclosing_answer(self):
        ids = loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )
        live_id = ids[self.rows[0]["flag_id"]]
        flag = next(
            row
            for row in self.client.flags.values()
            if row["challenge_id"] == live_id
        )
        flag["content"] = "FLAG{ffffffffffffffff}"

        with self.assertRaises(manifest.SyncError) as caught:
            manifest.verify_challenge_rows(
                self.client,
                challenges=self.rows,
                flag_id_to_live_id=ids,
            )

        self.assertIn("answer readback drift", str(caught.exception))
        self.assertNotIn("ffffffffffffffff", str(caught.exception))

    def test_readback_does_not_share_writer_flag_normalization(self):
        original = reconciliation.normalize_flag

        def corrupt_writer(flag):
            normalized = original(flag)
            return {**normalized, "data": "corrupted"}

        with mock.patch.object(
            reconciliation,
            "normalize_flag",
            corrupt_writer,
        ):
            ids = loader.sync_flag_layer(
                self.client,
                challenges=self.rows,
                dry_run=False,
            )
            with self.assertRaisesRegex(
                manifest.SyncError,
                "answer readback drift",
            ):
                manifest.verify_challenge_rows(
                    self.client,
                    challenges=self.rows,
                    flag_id_to_live_id=ids,
                )

    def test_readback_does_not_share_writer_hint_normalization(self):
        original = reconciliation.normalize_hints

        def corrupt_writer(hints):
            normalized = original(hints)
            normalized[0] = {**normalized[0], "cost": 99}
            return normalized

        with mock.patch.object(
            reconciliation,
            "normalize_hints",
            corrupt_writer,
        ):
            ids = loader.sync_flag_layer(
                self.client,
                challenges=self.rows,
                dry_run=False,
            )
            with self.assertRaisesRegex(
                manifest.SyncError,
                "hint readback drift",
            ):
                manifest.verify_challenge_rows(
                    self.client,
                    challenges=self.rows,
                    flag_id_to_live_id=ids,
                )

    def test_title_rename_updates_owned_row_instead_of_creating_duplicate(self):
        ids = loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )
        renamed = [dict(row) for row in self.rows]
        renamed[0] = {**renamed[0], "name": "Renamed title"}

        next_ids = loader.sync_flag_layer(
            self.client,
            challenges=renamed,
            dry_run=False,
        )

        self.assertEqual(ids[renamed[0]["flag_id"]], next_ids[renamed[0]["flag_id"]])
        self.assertEqual(len(next_ids), 38)

    def test_unowned_title_collision_is_preserved_not_claimed(self):
        unrelated_id = self.client.seed_unrelated()
        self.client.challenges[unrelated_id]["name"] = self.rows[0]["name"]

        ids = loader.sync_flag_layer(
            self.client,
            challenges=self.rows,
            dry_run=False,
        )

        self.assertNotEqual(ids[self.rows[0]["flag_id"]], unrelated_id)
        self.assertEqual(
            self.client.challenges[unrelated_id]["name"],
            self.rows[0]["name"],
        )
        self.assertEqual(len(self.client.challenges), 39)

    def test_dry_run_needs_no_client_or_token(self):
        result = loader.sync_flag_layer(
            None,
            challenges=self.rows,
            dry_run=True,
        )

        self.assertEqual(set(result), {row["flag_id"] for row in self.rows})


class TokenAndUrlTests(unittest.TestCase):
    def test_token_file_must_not_be_group_or_world_accessible(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("token-value\n")
            path = handle.name
        self.addCleanup(os.unlink, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

        with self.assertRaises(loader.SyncError):
            loader.read_token_file(path)

    def test_token_argument_is_not_supported(self):
        with self.assertRaises(SystemExit):
            loader.parse_args(
                ["--base-url", "https://ctf.example.com", "--token", "value"]
            )

    def test_plain_http_requires_explicit_loopback_development(self):
        with self.assertRaises(ValueError):
            CtfdClient("http://ctf.example.com", "token")

        client = CtfdClient(
            "http://127.0.0.1:8000",
            "token",
            allow_loopback_http=True,
        )
        self.assertEqual(client.base_url, "http://127.0.0.1:8000")

    def test_base_url_must_be_an_origin_without_a_path(self):
        with self.assertRaises(ValueError):
            CtfdClient("https://ctf.example.com/prefix", "token")

    def test_cross_origin_redirect_is_refused(self):
        client = CtfdClient("https://ctf.example.com", "token")
        request = client.opener.handlers[0]
        redirect_handler = next(
            handler
            for handler in client.opener.handlers
            if handler.__class__.__name__ == "_SameOriginRedirectHandler"
        )

        with self.assertRaises(urllib.error.HTTPError):
            redirect_handler.redirect_request(
                request,
                None,
                302,
                "redirect",
                {},
                "https://other.example.com/api/v1/challenges",
            )

    def test_response_size_is_bounded(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                return b"x" * size

        class Opener:
            def open(self, request, timeout):
                return Response()

        client = CtfdClient(
            "https://ctf.example.com",
            "token",
            max_response_bytes=8,
        )
        client.opener = Opener()

        with self.assertRaisesRegex(RuntimeError, "response limit"):
            client.get("/challenges")

    def test_http_error_body_is_not_in_exception_text(self):
        secret_marker = "FLAG{ffffffffffffffff}"

        class Opener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(
                    request.full_url,
                    500,
                    secret_marker,
                    {},
                    None,
                )

        client = CtfdClient("https://ctf.example.com", "token")
        client.opener = Opener()

        with self.assertRaises(RuntimeError) as caught:
            client.get("/challenges")

        self.assertNotIn(secret_marker, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
