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
    # Seed the QRY-RESERVE-R7 planner query.
    # W07.1: participant recovers the definition (view, policy, SQL template).
    # W07.2: the {{report_name}} template variable in a double-quoted identifier
    # enables quoted-identifier SQL injection; ordinary WHERE reported_ml > 0 filters
    # the reserve_report_current result, but UNION escapes it to reach
    # district_allocation_adjustment (ADJ-CRR-DP3-17) which is not reachable
    # via any direct route.
    qry_title = "QRY-RESERVE-R7"
    qry_sql = 'SELECT * FROM "{{report_name}}" WHERE reported_ml > 0'
    qry_description = (
        "Planning reserve query QRY-RESERVE-R7. Database: PostgreSQL 16.4. "
        "View: reserve_report_current. Identifier quote: \". Policy: SELECT only. "
        "Ordinary request: {report_name: reserve_report_current}. "
        "Ordinary result: RPT-CRR-RESERVE-R7. "
        "Template: SELECT * FROM \"{{report_name}}\" WHERE reported_ml > 0."
    )
    qry_template_tags = {
        "report_name": {
            "id": "report_name_tag",
            "name": "report_name",
            "display-name": "Report Name",
            "type": "text",
            "default": "reserve_report_current",
            "required": True
        }
    }
    qry_card = next((card for card in api("card") if card["name"] == qry_title), None)
    if qry_card is None:
        qry_card = api("card", {
            "name": qry_title, "display": "table", "visualization_settings": {},
            "description": qry_description,
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": qry_sql, "template-tags": qry_template_tags}}})
        print(f"Created Metabase question: {qry_title} (id={qry_card.get('id')})")
    else:
        current_sql = qry_card.get("dataset_query", {}).get("native", {}).get("query", "")
        if current_sql != qry_sql or qry_card.get("description") != qry_description:
            api(f'card/{qry_card["id"]}', {
                "description": qry_description,
                "dataset_query": {"database": database["id"], "type": "native", "native": {
                    "query": qry_sql, "template-tags": qry_template_tags}}},
                method="PUT")
            print(f"Updated Metabase question: {qry_title} (id={qry_card['id']})")
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

    # Seed the ALLOC-DP3-CURRENT allocation ledger question (W09.1).
    # planning_reader has SELECT on allocation_ledger; participant uses W06.3 session.
    alloc_title = "ALLOC-DP3-CURRENT"
    alloc_description = (
        "Planning allocation ledger ALLOC-DP3-CURRENT. Database: PostgreSQL 16.4. "
        "Table: allocation_ledger. Record: ALLOC-2026-DP3-R9. "
        "Asset: AST-CRR-017. District: Cairn Reach. Period: ALLOC-2026-DP3. "
        "Committed: 12.00 ML."
    )
    alloc_sql = (
        "SELECT record_id, revision, district, asset, planning_window, "
        "committed_ml, unit, effective_from, effective_to "
        "FROM allocation_ledger WHERE planning_window = 'ALLOC-2026-DP3'"
    )
    alloc_card = next((card for card in api("card") if card["name"] == alloc_title), None)
    if alloc_card is None:
        alloc_card = api("card", {
            "name": alloc_title, "display": "table", "visualization_settings": {},
            "description": alloc_description,
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": alloc_sql, "template-tags": {}}}})
        print(f"Created Metabase question: {alloc_title} (id={alloc_card.get('id')})")
    elif alloc_card.get("description") != alloc_description:
        api(f'card/{alloc_card["id"]}', {"description": alloc_description}, method="PUT")
        print(f"Updated Metabase question: {alloc_title}")
    else:
        print(f"Metabase question already current: {alloc_title}")

    # Seed the METER-DP3-CURRENT meter export question (W09.2).
    meter_title = "METER-DP3-CURRENT"
    meter_description = (
        "Planning meter export METER-DP3-CURRENT. Database: PostgreSQL 16.4. "
        "Table: meter_export. Record: MTR-CRR-DP3-R12. "
        "Usable reserve: 12.40 ML. Period: ALLOC-2026-DP3. "
        "Instruments: FIT-CRR-204A, FIT-CRR-204B."
    )
    meter_sql = (
        "SELECT record_id, revision, planning_window, usable_reserve_ml, "
        "unit, instrument_a, instrument_b "
        "FROM meter_export WHERE planning_window = 'ALLOC-2026-DP3'"
    )
    meter_card = next((card for card in api("card") if card["name"] == meter_title), None)
    if meter_card is None:
        meter_card = api("card", {
            "name": meter_title, "display": "table", "visualization_settings": {},
            "description": meter_description,
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": meter_sql, "template-tags": {}}}})
        print(f"Created Metabase question: {meter_title} (id={meter_card.get('id')})")
    elif meter_card.get("description") != meter_description:
        api(f'card/{meter_card["id"]}', {"description": meter_description}, method="PUT")
        print(f"Updated Metabase question: {meter_title}")
    else:
        print(f"Metabase question already current: {meter_title}")

    # Seed the RECON-DP3-CURRENT reconciliation question (W09.3).
    # Joins allocation, meter, and reserve report to surface the discrepancy.
    recon_title = "RECON-DP3-CURRENT"
    recon_description = (
        "Planning reserve reconciliation RECON-DP3-CURRENT. Database: PostgreSQL 16.4. "
        "View: reserve_reconciliation. Period: ALLOC-2026-DP3. "
        "Shows overstatement (reported - usable) and uncommitted margin (usable - committed)."
    )
    recon_sql = (
        "SELECT allocation_record, planning_window, district, asset, "
        "committed_ml, meter_record, usable_reserve_ml, reserve_report, "
        "reported_ml, duplicate_transfer, overstatement_ml, uncommitted_margin_ml "
        "FROM reserve_reconciliation"
    )
    recon_card = next((card for card in api("card") if card["name"] == recon_title), None)
    if recon_card is None:
        recon_card = api("card", {
            "name": recon_title, "display": "table", "visualization_settings": {},
            "description": recon_description,
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": recon_sql, "template-tags": {}}}})
        print(f"Created Metabase question: {recon_title} (id={recon_card.get('id')})")
    elif recon_card.get("description") != recon_description:
        api(f'card/{recon_card["id"]}', {"description": recon_description}, method="PUT")
        print(f"Updated Metabase question: {recon_title}")
    else:
        print(f"Metabase question already current: {recon_title}")

    print("ARWC native planning reader and saved report configured")


if __name__ == "__main__":
    seed()
