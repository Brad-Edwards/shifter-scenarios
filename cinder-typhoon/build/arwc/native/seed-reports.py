#!/usr/bin/env python3
"""Configure native Metabase users and an approved planning report."""
import hashlib
import hmac
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SESSION = ""


def api(path: str, values: dict | None = None) -> dict | list:
    request = Request(f"http://metabase:3000/api/{path}",
                      data=json.dumps(values).encode() if values is not None else None,
                      headers={"Content-Type": "application/json", "X-Metabase-Session": SESSION})
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Metabase {path} returned HTTP {error.code}") from None


def seed() -> None:
    global SESSION
    token = api("session/properties").get("setup-token")
    admin = "planning.admin@alterrawaterco.com"
    password = os.environ["METABASE_ADMIN_PASSWORD"]
    if token:
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
    if not any(card["name"] == title for card in cards):
        api("card", {"name": title, "display": "table", "visualization_settings": {},
            "dataset_query": {"database": database["id"], "type": "native", "native": {
                "query": "SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of FROM reporting.reserve_report ORDER BY asset"}}})
    print("ARWC native planning reader and saved report configured")


if __name__ == "__main__":
    seed()
