#!/usr/bin/env python3
"""Secret-safe, pack-local CTFd reconciliation primitives."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAX_RESPONSE_BYTES = 1_048_576
MANAGED_PREFIX = "shifter:keplerops-ai:"
FLAG_CONTRACT_FIELDS = (
    "challenge_id", "flag_id", "outcome", "evidence", "prerequisites",
)


class SyncError(RuntimeError):
    """A redacted validation or synchronization failure."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SyncError("base URL must not contain userinfo, query, or fragment")
    if parsed.scheme == "https" and parsed.hostname:
        return value.rstrip("/")
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return value.rstrip("/")
    raise SyncError("base URL must use HTTPS or loopback HTTP")


class CtfdClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        self.base_url = validate_base_url(base_url)
        self.timeout = timeout
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "User-Agent": "shifter-keplerops-ctfd/1.0",
        }
        self.opener = urllib.request.build_opener(_NoRedirect())

    def request(self, method: str, path: str, *, body=None, query=None):
        url = f"{self.base_url}/api/v1{path}"
        if query:
            url += "?" + urllib.parse.urlencode(
                {key: value for key, value in query.items() if value is not None},
                doseq=True,
            )
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise SyncError(f"CTFd {method} {path} response exceeded limit")
                payload = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise SyncError(f"CTFd {method} {path} failed with HTTP {exc.code}") from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise SyncError(f"CTFd {method} {path} returned no usable response") from exc
        if not isinstance(payload, dict) or payload.get("success") is False:
            raise SyncError(f"CTFd {method} {path} reported failure")
        return payload

    def get(self, path, query=None):
        return self.request("GET", path, query=query)

    def post(self, path, body):
        return self.request("POST", path, body=body)

    def patch(self, path, body):
        return self.request("PATCH", path, body=body)

    def delete(self, path):
        return self.request("DELETE", path)


def get_all_items(client, path: str, query=None) -> list[dict[str, Any]]:
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        payload = client.get(path, {**(query or {}), "page": page})
        rows.extend(payload.get("data", []))
        pages = int((((payload.get("meta") or {}).get("pagination") or {}).get("pages", 1)))
        if page >= pages:
            return rows
        page += 1


def live_prerequisite_ids(
    row: dict[str, Any],
    ids_by_challenge_id: dict[str, int],
) -> list[int]:
    try:
        return [ids_by_challenge_id[item] for item in row.get("prerequisites", [])]
    except KeyError as exc:
        raise SyncError(f"missing live prerequisite for {row['flag_id']}") from exc


def challenge_payload(
    row: dict[str, Any],
    position: int,
    prerequisite_ids: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "value": row["value"],
        "type": "standard",
        "state": "visible",
        "max_attempts": 0,
        "function": "static",
        "logic": "any",
        "position": position,
        "requirements": {"prerequisites": list(prerequisite_ids or [])},
    }


def _patch_changed(client, path: str, live: dict[str, Any], expected: dict[str, Any]):
    patch = {key: value for key, value in expected.items() if live.get(key) != value}
    if patch:
        client.patch(path, patch)


def flag_contract(acceptance: dict[str, Any]) -> dict[str, Any]:
    return {key: acceptance[key] for key in FLAG_CONTRACT_FIELDS}


def _reconcile_children(client, *, kind: str, challenge_id: int,
                        expected: list[dict[str, Any]], key_fields: tuple[str, ...]):
    live = client.get(f"/challenges/{challenge_id}/{kind}")["data"]
    live_by_key = {tuple(row.get(key) for key in key_fields): row for row in live}
    wanted = set()
    for row in expected:
        key = tuple(row.get(field) for field in key_fields)
        wanted.add(key)
        current = live_by_key.get(key)
        if current is None:
            client.post(f"/{kind}", {"challenge_id": challenge_id, **row})
        else:
            _patch_changed(client, f"/{kind}/{current['id']}", current, row)
    for key, row in live_by_key.items():
        if key not in wanted:
            client.delete(f"/{kind}/{row['id']}")


def ensure_children(client, challenge_id: int, row: dict[str, Any]) -> None:
    acceptance = row["acceptance"]
    _reconcile_children(
        client, kind="flags", challenge_id=challenge_id,
        expected=[{
            "type": acceptance["type"],
            "content": json.dumps(
                flag_contract(acceptance),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "data": "",
        }],
        key_fields=("type",),
    )
    _reconcile_children(
        client, kind="hints", challenge_id=challenge_id,
        expected=[{"content": hint, "cost": 0, "title": f"Hint {index}"}
                  for index, hint in enumerate(row["hints"], 1)],
        key_fields=("content",),
    )
    tags = client.get(f"/challenges/{challenge_id}/tags")["data"]
    values = {tag.get("value") for tag in tags}
    if row["managed_tag"] not in values:
        client.post("/tags", {"challenge_id": challenge_id, "value": row["managed_tag"]})
    for tag in tags:
        value = tag.get("value", "")
        if (isinstance(value, str) and value.startswith(MANAGED_PREFIX)
                and value != row["managed_tag"]):
            client.delete(f"/tags/{tag['id']}")


def managed_challenges(client, challenges: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    managed = {}
    for challenge in challenges:
        for tag in client.get(f"/challenges/{challenge['id']}/tags")["data"]:
            value = tag.get("value", "")
            if isinstance(value, str) and value.startswith(MANAGED_PREFIX):
                flag_id = value.removeprefix(MANAGED_PREFIX)
                if flag_id in managed:
                    raise SyncError("duplicate managed challenge identity")
                managed[flag_id] = challenge
    return managed


def verify_rows(client, expected: list[dict[str, Any]], ids: dict[str, int]) -> None:
    ids_by_challenge_id = {
        row["challenge_id"]: ids[row["flag_id"]]
        for row in expected
        if row["flag_id"] in ids
    }
    for row in expected:
        cid = ids.get(row["flag_id"])
        if cid is None:
            raise SyncError(f"readback missing managed challenge {row['flag_id']}")
        challenge = next(
            (
                item for item in get_all_items(client, "/challenges", {"view": "admin"})
                if item.get("id") == cid
            ),
            None,
        )
        payload = challenge_payload(
            row,
            row["position"],
            live_prerequisite_ids(row, ids_by_challenge_id),
        )
        if challenge is None or any(challenge.get(key) != value for key, value in payload.items()):
            raise SyncError(f"readback drift for managed challenge {row['flag_id']}")
        flags = client.get(f"/challenges/{cid}/flags")["data"]
        hints = client.get(f"/challenges/{cid}/hints")["data"]
        tags = client.get(f"/challenges/{cid}/tags")["data"]
        acceptance = row["acceptance"]
        expected_flag = {
            "type": acceptance["type"],
            "content": json.dumps(
                flag_contract(acceptance),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "data": "",
        }
        if len(flags) != 1 or any(flags[0].get(key) != value
                                  for key, value in expected_flag.items()):
            raise SyncError(f"readback flag drift for {row['flag_id']}")
        if [hint.get("content") for hint in hints] != row["hints"]:
            raise SyncError(f"readback hint drift for {row['flag_id']}")
        if row["managed_tag"] not in {tag.get("value") for tag in tags}:
            raise SyncError(f"readback tag drift for {row['flag_id']}")
