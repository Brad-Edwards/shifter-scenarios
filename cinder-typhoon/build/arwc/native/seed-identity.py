#!/usr/bin/env python3
"""Import real workforce identities through Keycloak's supported partial import."""
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import runpy
import ssl
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = "https://identity.arwc.test"
CONTEXT = None
TOKEN = ""
TEMPORARY = "mira.vale.temp"
TEMPORARY_EMAIL = TEMPORARY + "@alterrawaterco.com"


def api(method: str, path: str, values: dict | None = None, *, form=False):
    body = None if values is None else (urlencode(values).encode() if form else json.dumps(values).encode())
    request = Request(ROOT + path, method=method, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded" if form else "application/json",
        "Authorization": "Bearer " + TOKEN,
    })
    try:
        with urlopen(request, timeout=180, context=CONTEXT) as response:
            content = response.read()
            return json.loads(content) if content else None
    except HTTPError as error:
        raise RuntimeError(f"Native identity API {method} {path.split('?')[0]} returned HTTP {error.code}") from None


def password(email: str) -> str:
    return hmac.new(os.environ["IDENTITY_STAFF_SEED"].encode(), email.encode(), hashlib.sha256).hexdigest()


def workforce(path: Path = Path("/seed/a-personnel-register.csv")) -> list[dict]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    users = []
    for row in rows:
        first, _, last = row["name"].partition(" ")
        users.append({
            "username": row["work_email"].split("@")[0], "firstName": first, "lastName": last,
            "email": row["work_email"], "emailVerified": True, "enabled": True,
            "realmRoles": ["staff"], "groups": ["/" + row["department"]],
            "attributes": {"employee_number": [row["employee_id"]], "department": [row["department"]],
                           "team": [row["team"]], "assignment_ref": [row["role"]]},
            "credentials": [{"type": "password", "value": password(row["work_email"]), "temporary": False}],
        })
    users.append({
        "username": TEMPORARY, "firstName": "Mira", "lastName": "Vale", "email": TEMPORARY_EMAIL,
        "emailVerified": True, "enabled": True, "groups": ["/Temporary planning staff"],
        "attributes": {"employee_number": ["TMP-4821"], "department": ["Planning, quality, and compliance"],
                       "team": ["Planning relief"], "assignment_ref": ["PLAN-RELIEF-3"]},
        "clientRoles": {"realm-management": ["view-users", "query-users"]},
        "credentials": [{"type": "password", "value": password(TEMPORARY_EMAIL), "temporary": True}],
        "requiredActions": ["UPDATE_PASSWORD"],
    })
    return users


def import_payload(users: list[dict]) -> dict:
    groups = sorted({group.lstrip("/") for user in users for group in user["groups"]})
    return {"ifResourceExists": "SKIP", "groups": [{"name": name, "path": "/" + name} for name in groups], "users": users}


def seed() -> None:
    global TOKEN, CONTEXT
    CONTEXT = ssl.create_default_context(cafile="/run/arwc-ca/root.crt")
    TOKEN = api("POST", "/realms/master/protocol/openid-connect/token", {
        "client_id": "admin-cli", "grant_type": "password", "username": "platform-admin",
        "password": os.environ["IDENTITY_ADMIN_PASSWORD"],
    }, form=True)["access_token"]
    profile = api("GET", "/admin/realms/arwc/users/profile")
    names = {attribute["name"] for attribute in profile["attributes"]}
    for name, display in (("employee_number", "Employee number"), ("department", "Department"),
                          ("team", "Team"), ("assignment_ref", "Approved assignment")):
        if name not in names:
            profile["attributes"].append({"name": name, "displayName": display,
                "permissions": {"view": ["admin"], "edit": ["admin"]}, "multivalued": False})
    api("PUT", "/admin/realms/arwc/users/profile", profile)
    events = api("GET", "/admin/realms/arwc/events/config")
    events.update({"eventsEnabled": True, "eventsExpiration": 604800,
                   "adminEventsEnabled": True, "adminEventsDetailsEnabled": False})
    api("PUT", "/admin/realms/arwc/events/config", events)
    users = workforce()
    api("POST", "/admin/realms/arwc/partialImport", import_payload(users))
    actual = api("GET", "/admin/realms/arwc/users?max=1000")
    by_name = {user["username"]: user for user in actual}
    if not {user["username"] for user in users}.issubset(by_name):
        raise RuntimeError("Native workforce import is incomplete")
    temporary = by_name[TEMPORARY]
    clients = api("GET", "/admin/realms/arwc/clients?clientId=realm-management")
    roles = api("GET", f'/admin/realms/arwc/users/{temporary["id"]}/role-mappings/clients/{clients[0]["id"]}/composite')
    role_names = {role["name"] for role in roles}
    if not {"view-users", "query-users"}.issubset(role_names) or not role_names.issubset({"view-users", "query-users", "query-groups"}):
        raise RuntimeError("Temporary native identity has unexpected administrative authority")
    files = runpy.run_path("/seed/seed-documents.py")
    roster = io.StringIO()
    writer = csv.writer(roster)
    writer.writerow(("employee_number", "name", "username", "identity_id", "department", "approved_assignment", "enabled", "first_signin_pending"))
    for expected in users:
        user = by_name[expected["username"]]
        attributes = user.get("attributes", {})
        writer.writerow((attributes.get("employee_number", [""])[0], f'{user.get("firstName", "")} {user.get("lastName", "")}',
            user["username"], user["id"], attributes.get("department", [""])[0], attributes.get("assignment_ref", [""])[0],
            user["enabled"], "UPDATE_PASSWORD" in user.get("requiredActions", [])))
    folder = "Veybridge handover/"
    files["upload"](folder + "activation-roster-2026-11.csv", roster.getvalue().encode())
    template = Path("/seed/starting-arrangements-mira.md.in").read_text()
    files["upload"](folder + "starting-arrangements-mira.md", template.format(initial_password=password(TEMPORARY_EMAIL)).encode())
    print(json.dumps({"native_identity_count": len(users), "temporary_identity_id": temporary["id"],
                      "temporary_required_actions": temporary.get("requiredActions", []),
                      "temporary_admin_roles": sorted(role["name"] for role in roles)}))


if __name__ == "__main__":
    seed()
