#!/usr/bin/env python3
"""Configure native Metabase users and an approved planning report."""
import hashlib
import hmac
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SESSION = ""


def api(path: str, values: dict | None = None, *, method: str | None = None) -> dict | list:
    request = Request(f"http://metabase:3000/api/{path}",
                      data=json.dumps(values).encode() if values is not None else None, method=method,
                      headers={"Content-Type": "application/json", "X-Metabase-Session": SESSION})
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Metabase {path} returned HTTP {error.code}") from None


def seed() -> None:
    global SESSION
    admin = "planning.admin@alterrawaterco.com"
    password = os.environ["METABASE_ADMIN_PASSWORD"]
    try:
        SESSION = api("session", {"username": admin, "password": password})["id"]
    except RuntimeError as error:
        if not str(error).endswith("HTTP 401"):
            raise
        token = api("session/properties").get("setup-token")
        if not token:
            raise RuntimeError("Metabase has no usable initial setup token") from None
        api("setup", {"token": token,
            "user": {"first_name": "Planning", "last_name": "Administration", "email": admin, "password": password},
            "prefs": {"site_name": "ARWC Planning", "site_locale": "en", "allow_tracking": False}})
        SESSION = api("session", {"username": admin, "password": password})["id"]
    existing_users = api("user")["data"]
    email = "nadia.corvane@alterrawaterco.com"
    if not any(user["email"] == email for user in existing_users):
        user_password = hmac.new(os.environ["STAFF_SEED"].encode(), email.encode(), hashlib.sha256).hexdigest()
        api("user", {"first_name": "Nadia", "last_name": "Corvane", "email": email,
                     "password": user_password, "is_superuser": False})
    databases = api("database")["data"]
    database = next((item for item in databases if item["name"] == "ARWC approved planning reports"), None)
    if database is None:
        database = api("database", {"name": "ARWC approved planning reports", "engine": "postgres",
            "details": {"host": "corporate-db", "port": 5432, "dbname": "planning",
                "user": "planning_reader", "password": os.environ["PLANNING_READER_PASSWORD"], "ssl": False},
            "is_full_sync": True, "is_on_demand": False})
    cards = api("card")
    title = "Regional reserve report"
    card = next((card for card in cards if card["name"] == title), None)
    if card is None:
        card = api("card", {"name": title, "display": "table", "visualization_settings": {},
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": "SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of FROM reporting.reserve_report ORDER BY asset"}}})
    description = "Reported reserves with their source revision and observation date."
    if card.get("description") != description:
        query = {"database": database["id"], "type": "native", "native": {
            "query": "SELECT record_id, planning_window, reported_ml, asset, unit, as_of FROM reporting.reserve_report ORDER BY asset"}}
        api(f'card/{card["id"]}', {"dataset_query": query, "description": "Regional reported reserve figures."}, method="PUT")
        query["native"]["query"] = "SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of FROM reporting.reserve_report ORDER BY asset"
        api(f'card/{card["id"]}', {"dataset_query": query, "description": description}, method="PUT")
    # Seed the QRY-RESERVE-R7 planner query: the saved SQL question on reserve_report_current.
    # This is the planning query the participant recovers in W07.1 using the W06.3 session.
    qry_title = "QRY-RESERVE-R7"
    qry_card = next((card for card in api("card") if card["name"] == qry_title), None)
    qry_description = (
        "Planning reserve query QRY-RESERVE-R7. Database: PostgreSQL 16.4. "
        "View: reserve_report_current. Identifier quote: \". Policy: SELECT only. "
        "Ordinary request: {report_name: reserve_report_current}. "
        "Ordinary result: RPT-CRR-RESERVE-R7."
    )
    if qry_card is None:
        qry_card = api("card", {"name": qry_title, "display": "table",
            "visualization_settings": {},
            "description": qry_description,
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": 'SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of FROM "reserve_report_current"'}}})
        print(f"Created Metabase question: {qry_title} (id={qry_card.get('id')})")
    elif qry_card.get("description") != qry_description:
        api(f'card/{qry_card["id"]}', {"description": qry_description}, method="PUT")
        print(f"Updated Metabase question description: {qry_title}")
    else:
        print(f"Metabase question already current: {qry_title}")

    # Write reports state (question ID) so the planning_data service can include the
    # native Metabase URL in its client document routes.
    import pathlib as _pathlib, json as _json
    reports_state = {
        "qry_reserve_r7_id": qry_card["id"],
        "metabase_url": "https://reports.arwc.test",
    }
    for op_dir in [".operator", "$(cd .. && pwd)/.operator"]:
        try:
            p = _pathlib.Path(op_dir) / "archive-workflow" / "reports-state.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_json.dumps(reports_state, indent=2))
            p.chmod(0o644)
        except Exception:
            pass
    print(f"Reports state: QRY-RESERVE-R7 Metabase question id={qry_card['id']}")
    print("ARWC native planning reader and saved report configured")


if __name__ == "__main__":
    seed()
