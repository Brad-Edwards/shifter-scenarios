#!/usr/bin/env python3
"""Render and read back the additive Keycloak company identity facade."""

from __future__ import annotations

import argparse
import copy
import json
import re
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from company_state_common import (
    OWNER,
    assert_readback,
    digest_json,
    load_corpus,
    normalized_readback,
)

CONTENT_ID = "company-identity-facade-state"
ROOT_GROUP = "Company State"
TEAM_PROJECTIONS = {
    "team-model-research": ("ML Engineering", ("ml_engineer",)),
    "team-evaluation": ("QA", ("participant", "ai_service_recipient")),
    "team-release": ("Release Managers", ("release_manager",)),
}
URL_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def normalize_import_components(components: object) -> None:
    """Remove a redundant field rejected by Keycloak's current import model."""
    if not isinstance(components, dict):
        return
    for provider_type, entries in components.items():
        if not isinstance(entries, list):
            raise TypeError(f"Keycloak component list {provider_type} is invalid")
        for component in entries:
            if not isinstance(component, dict):
                raise TypeError(f"Keycloak component {provider_type} is invalid")
            declared_type = component.pop("providerType", provider_type)
            if declared_type != provider_type:
                raise RuntimeError(
                    f"Keycloak component {component.get('name', '<unnamed>')} "
                    "declares a conflicting provider type"
                )
            normalize_import_components(component.get("subComponents"))


def build_group(corpus_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    corpus = load_corpus(corpus_path)
    teams = {row["id"]: row for row in corpus["teams"]}
    people = {row["id"]: row for row in corpus["people"]}
    records: list[dict[str, Any]] = []
    subgroups: list[dict[str, Any]] = []
    for team_id, (directory_group, roles) in TEAM_PROJECTIONS.items():
        team = teams[team_id]
        members = sorted(
            row["username"] for row in people.values() if row["team_ref"] == team_id
        )
        source_records = [team] + sorted(
            (row for row in people.values() if row["team_ref"] == team_id),
            key=lambda row: row["id"],
        )
        for source in source_records:
            records.append(
                {
                    "id": source["id"],
                    "object_type": "team" if source is team else "person",
                    "source_digest": digest_json(source),
                }
            )
        subgroups.append(
            {
                "name": team["name"],
                "realmRoles": list(roles),
                "attributes": {
                    "keplerops.company_state.owner": [OWNER],
                    "keplerops.company_state.content_id": [CONTENT_ID],
                    "keplerops.company_state.team_id": [team_id],
                    "keplerops.company_state.directory_group": [directory_group],
                    "keplerops.company_state.lead_ref": [team["lead_ref"]],
                    "keplerops.company_state.members": members,
                },
            }
        )
    group = {
        "name": ROOT_GROUP,
        "attributes": {
            "keplerops.company_state.owner": [OWNER],
            "keplerops.company_state.content_id": [CONTENT_ID],
        },
        "subGroups": sorted(subgroups, key=lambda row: row["name"]),
    }
    return group, sorted(records, key=lambda row: row["id"])


def render_realm(
    baseline_path: Path, corpus_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    # The immutable Keycloak image build supplies the baseline realm path.
    realm = json.loads(baseline_path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(realm, dict) or not isinstance(realm.get("groups"), list):
        raise TypeError("Keycloak baseline realm is invalid")
    if any(group.get("name") == ROOT_GROUP for group in realm["groups"]):
        raise RuntimeError(f"ownership collision: Keycloak group {ROOT_GROUP}")
    group, records = build_group(corpus_path)
    rendered = copy.deepcopy(realm)
    normalize_import_components(rendered.get("components"))
    rendered["groups"].append(group)
    readback = normalized_readback(CONTENT_ID, records)
    return rendered, readback


def expected_admin_projection(corpus_path: Path) -> dict[str, Any]:
    group, _records = build_group(corpus_path)
    return {
        "name": group["name"],
        "attributes": group["attributes"],
        "subGroups": sorted(
            (
                {
                    "name": subgroup["name"],
                    "attributes": subgroup["attributes"],
                    "realmRoles": sorted(subgroup["realmRoles"]),
                }
                for subgroup in group["subGroups"]
            ),
            key=lambda row: row["name"],
        ),
    }


def readback_admin_projection(
    root_group: dict[str, Any],
    subgroup_details: list[dict[str, Any]],
    role_mappings: dict[str, list[dict[str, Any]]],
    corpus_path: Path,
) -> dict[str, Any]:
    observed = {
        "name": root_group.get("name"),
        "attributes": root_group.get("attributes", {}),
        "subGroups": sorted(
            (
                {
                    "name": subgroup.get("name"),
                    "attributes": subgroup.get("attributes", {}),
                    "realmRoles": sorted(
                        role["name"]
                        for role in role_mappings.get(subgroup["id"], [])
                        if isinstance(role, dict) and isinstance(role.get("name"), str)
                    ),
                }
                for subgroup in subgroup_details
            ),
            key=lambda row: str(row["name"]),
        ),
    }
    if observed != expected_admin_projection(corpus_path):
        raise RuntimeError("Keycloak company identity native readback mismatch")
    _group, records = build_group(corpus_path)
    return assert_readback(normalized_readback(CONTENT_ID, records), records)


def _request_json(
    request: Request,
    *,
    context: ssl.SSLContext | None = None,
) -> Any:
    with urlopen(request, timeout=10, context=context) as response:
        return json.loads(response.read())


def validated_loopback_server(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.port is None
        or parsed.path not in {"", "/"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Keycloak server must be an explicit loopback origin")
    return value.rstrip("/")


def validated_segment(value: str, label: str) -> str:
    if not URL_SEGMENT.fullmatch(value):
        raise ValueError(f"{label} must be a bounded URL path segment")
    return value


def tls_context(ca_file: Path | None) -> ssl.SSLContext | None:
    if ca_file is None:
        return None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    # The Keycloak entrypoint supplies its mounted CA certificate.
    context.load_verify_locations(cafile=str(ca_file))  # NOSONAR
    return context


def readback_admin_api(
    server: str,
    realm: str,
    client_id: str,
    client_secret: str,
    corpus_path: Path,
    *,
    context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    base_url = validated_loopback_server(server)
    realm = validated_segment(realm, "realm")
    client_id = validated_segment(client_id, "client id")
    token_payload = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("ascii")
    token_response = _request_json(
        Request(  # NOSONAR - loopback origin and path segments validated above.
            f"{base_url}/realms/{realm}/protocol/openid-connect/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        ),
        context=context,
    )
    token = token_response["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    query = urlencode(
        {
            "search": ROOT_GROUP,
            "exact": "true",
            "briefRepresentation": "false",
        }
    )
    groups = _request_json(
        Request(  # NOSONAR - loopback origin and path segments validated above.
            f"{base_url}/admin/realms/{realm}/groups?{query}",
            headers=headers,
        ),
        context=context,
    )
    matches = [group for group in groups if group.get("name") == ROOT_GROUP]
    if len(matches) != 1:
        raise RuntimeError("Keycloak company identity group is missing or duplicated")
    root = _request_json(
        Request(  # NOSONAR - loopback origin and path segments validated above.
            f"{base_url}/admin/realms/{realm}/groups/{matches[0]['id']}"
            "?briefRepresentation=false",
            headers=headers,
        ),
        context=context,
    )
    children = _request_json(
        Request(  # NOSONAR - loopback origin and path segments validated above.
            f"{base_url}/admin/realms/{realm}/groups/{root['id']}/children"
            "?briefRepresentation=false",
            headers=headers,
        ),
        context=context,
    )
    subgroup_details: list[dict[str, Any]] = []
    role_mappings: dict[str, list[dict[str, Any]]] = {}
    for subgroup in children:
        subgroup_id = subgroup["id"]
        detail = _request_json(
            Request(  # NOSONAR - loopback origin and path segments validated above.
                f"{base_url}/admin/realms/{realm}/groups/{subgroup_id}"
                "?briefRepresentation=false",
                headers=headers,
            ),
            context=context,
        )
        subgroup_details.append(detail)
        role_mappings[subgroup_id] = _request_json(
            Request(  # NOSONAR - loopback origin and path segments validated above.
                f"{base_url}/admin/realms/{realm}/groups/{subgroup_id}"
                "/role-mappings/realm",
                headers=headers,
            ),
            context=context,
        )
    return readback_admin_projection(root, subgroup_details, role_mappings, corpus_path)


def readback_import(realm: dict[str, Any], corpus_path: Path) -> dict[str, Any]:
    """Build-time import check; runtime acceptance uses the Admin API."""
    expected_group, expected_records = build_group(corpus_path)
    matches = [
        group for group in realm.get("groups", []) if group.get("name") == ROOT_GROUP
    ]
    if len(matches) != 1:
        raise RuntimeError("Keycloak company identity group is missing or duplicated")
    if matches[0] != expected_group:
        raise RuntimeError("Keycloak company identity native readback mismatch")
    return assert_readback(
        normalized_readback(CONTENT_ID, expected_records), expected_records
    )


def main() -> None:  # NOSONAR - bounded three-command CLI dispatch.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("render", "readback-import", "readback-api")
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--company-state", type=Path, required=True)
    parser.add_argument("--realm", type=Path)
    parser.add_argument("--server")
    parser.add_argument("--target-realm", default="keplerops")
    parser.add_argument("--client-id")
    parser.add_argument("--client-secret-file", type=Path)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--readback-output", type=Path)
    parser.add_argument("--native-projection-output", type=Path)
    args = parser.parse_args()
    if args.command == "render":
        if not args.baseline or not args.output:
            parser.error("render requires baseline and output")
        realm, observed = render_realm(args.baseline, args.company_state)
        # These are private image-build outputs selected by the build entrypoint.
        args.output.write_text(  # NOSONAR
            json.dumps(realm, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",  # NOSONAR
        )
        if args.readback_output:
            args.readback_output.write_text(  # NOSONAR
                json.dumps(observed, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",  # NOSONAR
            )
        if args.native_projection_output:
            args.native_projection_output.write_text(  # NOSONAR
                json.dumps(
                    expected_admin_projection(args.company_state),
                    indent=2,
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",  # NOSONAR
            )
    elif args.command == "readback-import":
        if not args.realm:
            parser.error("readback-import requires realm")
        realm = json.loads(args.realm.read_text(encoding="utf-8"))  # NOSONAR
        print(json.dumps(readback_import(realm, args.company_state), sort_keys=True))
    else:
        if not args.server or not args.client_id or not args.client_secret_file:
            parser.error(
                "readback-api requires server, client-id, and client-secret-file"
            )
        context = tls_context(args.ca_file)
        print(
            json.dumps(
                readback_admin_api(
                    args.server,
                    args.target_realm,
                    args.client_id,
                    args.client_secret_file.read_text(encoding="utf-8").strip(),  # NOSONAR
                    args.company_state,
                    context=context,
                ),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
