#!/usr/bin/env python3
"""Load ordinary utility records through the supported Frappe REST API."""
import hashlib
import hmac
from http.cookiejar import CookieJar
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

COMPANY = "Alterra Regional Water Company"
OPENER = build_opener(HTTPCookieProcessor(CookieJar()))


def api(path: str, body: dict | None = None) -> dict:
    request = Request(
        f"http://backend:8000{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Host": "erp.arwc.test", "Content-Type": "application/json"},
    )
    try:
        with OPENER.open(request, timeout=180) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Frappe API {path.split('?')[0]} returned HTTP {error.code}") from None


def insert(doctype: str, identity: dict, values: dict) -> dict:
    resource = f"/api/resource/{quote(doctype, safe='')}"
    query = urlencode({"filters": json.dumps(identity), "fields": '["name"]', "limit_page_length": 1})
    existing = api(f"{resource}?{query}")["data"]
    if existing:
        return existing[0]
    return api(resource, {"doctype": doctype, **identity, **values})["data"]


def user(email: str, name: str, roles: list[str]) -> None:
    password = hmac.new(os.environ["ERP_STAFF_SEED"].encode(), email.encode(), hashlib.sha256).hexdigest()
    insert("User", {"email": email}, {
        "first_name": name.split()[0], "last_name": " ".join(name.split()[1:]),
        "enabled": 1, "send_welcome_email": 0, "new_password": password,
        "roles": [{"role": role} for role in roles],
    })


def seed() -> None:
    api("/api/method/login", {"usr": "Administrator", "pwd": os.environ["ERP_ADMIN_PASSWORD"]})
    result = api("/api/method/frappe.desk.page.setup_wizard.setup_wizard.setup_complete", {"args": {
        "language": "English", "country": "United States", "currency": "USD",
        "timezone": "America/New_York", "company_name": COMPANY, "company_abbr": "ARWC",
        "full_name": "ARWC Service Desk", "email": "it.service@alterrawaterco.com",
        "password": os.environ["ERP_ADMIN_PASSWORD"], "chart_of_accounts": "Standard",
        "fiscal_year_start_date": "2026-01-01", "fiscal_year_end_date": "2026-12-31",
        "enable_telemetry": 0,
    }})
    if result.get("message", {}).get("status") != "ok":
        raise RuntimeError("Native ERPNext company setup did not complete")
    for name in ("Maintenance and engineering", "Operations", "Planning", "Procurement"):
        insert("Department", {"department_name": name, "company": COMPANY}, {})
    for centre in ("Pine", "River"):
        insert("Cost Center", {"cost_center_name": centre, "company": COMPANY}, {
            "parent_cost_center": "Main - ARWC", "is_group": 0,
        })
    for email, name, roles in (
        ("theo.marrivel@alterrawaterco.com", "Theo Marrivel", ["Maintenance User", "Stock User"]),
        ("clara.morivelle@alterrawaterco.com", "Clara Morivelle", ["Maintenance User", "Stock User"]),
        ("priya.naravel@alterrawaterco.com", "Priya Naravel", ["Purchase User"]),
        ("luc.venn-morel@alterrawaterco.com", "Luc Venn-Morel", ["Purchase Manager", "Accounts Manager"]),
    ):
        user(email, name, roles)
    insert("Supplier Group", {"supplier_group_name": "Utility services"}, {
        "parent_supplier_group": "All Supplier Groups",
    })
    for name in ("Merewick Bulk Water Cooperative", "Ardenvale Instrument Services", "Veybridge Field Services",
                 "Orren & Vale IT Services", "Ternwick Records Bureau"):
        insert("Supplier", {"supplier_name": name}, {
            "supplier_group": "Utility services", "supplier_type": "Company",
        })
    insert("UOM", {"uom_name": "Megalitre"}, {"must_be_whole_number": 0})
    insert("Item Group", {"item_group_name": "Services"}, {"parent_item_group": "All Item Groups"})
    insert("Item", {"item_code": "BULK-WATER"}, {
        "item_name": "Supplementary bulk water", "item_group": "Services", "stock_uom": "Megalitre",
        "is_stock_item": 0, "is_purchase_item": 1,
    })
    insert("Asset Category", {"asset_category_name": "Water infrastructure"}, {})
    insert("Item", {"item_code": "OUTLET-GATE"}, {
        "item_name": "Outlet gate assembly", "item_group": "All Item Groups", "stock_uom": "Nos",
        "is_stock_item": 0, "is_fixed_asset": 1, "asset_category": "Water infrastructure",
    })
    for location in ("Cairn Reach", "Pine treatment", "River distribution"):
        insert("Location", {"location_name": location}, {})
    for number in range(1, 25):
        asset_name = f"AST-CRR-{number:03d} — Outlet gate assembly {number}"
        insert("Asset", {"asset_name": asset_name, "company": COMPANY}, {
            "item_code": "OUTLET-GATE", "location": "Cairn Reach",
            "purchase_date": "2019-06-20", "available_for_use_date": "2019-07-01",
            "is_existing_asset": 1, "gross_purchase_amount": 45000,
            "calculate_depreciation": 0,
        })
    team = insert("Asset Maintenance Team", {"maintenance_team_name": "Cairn Reach maintenance"}, {
        "company": COMPANY,
        "maintenance_team_members": [{"team_member": "theo.marrivel@alterrawaterco.com"},
                                     {"team_member": "clara.morivelle@alterrawaterco.com"}],
    })
    for number in range(1, 25):
        asset_name = f"AST-CRR-{number:03d} — Outlet gate assembly {number}"
        asset = insert("Asset", {"asset_name": asset_name, "company": COMPANY}, {})
        insert("Asset Maintenance", {"asset_name": asset["name"], "company": COMPANY}, {
            "maintenance_team": team["name"],
            "asset_maintenance_tasks": [{
                "maintenance_task": "Inspect actuator travel and limit indication",
                "maintenance_status": "Planned", "start_date": "2026-09-01",
                "periodicity": "Monthly", "assign_to": "theo.marrivel@alterrawaterco.com",
            }],
        })
    for reference, name in (
        ("WO-CRR-4417", "Cairn Reach outlet inspection"),
        ("WO-PIN-2192", "Pine intake instrument calibration"),
        ("WO-RIV-3308", "River distribution pressure review"),
        ("WO-CRR-4392", "Cairn Reach cabinet ventilation service"),
    ):
        project = insert("Project", {"project_name": f"{reference} — {name}"}, {
            "company": COMPANY, "expected_start_date": "2026-09-01",
            "expected_end_date": "2026-12-01", "status": "Open",
        })
        for subject in ("Confirm site access and maintenance permit", "Complete inspection and record findings",
                        "Review findings and approve handback"):
            insert("Task", {"subject": subject, "project": project["name"]}, {
                "status": "Open", "description": f"{reference}: {subject}. Keep the accepted inspection record with the maintenance handover.",
            })
    insert("Supplier Quotation", {"supplier": "Merewick Bulk Water Cooperative", "quotation_number": "QUOTE-MER-884"}, {
        "company": COMPANY, "transaction_date": "2026-11-09", "valid_till": "2026-12-01",
        "currency": "USD", "items": [{"item_code": "BULK-WATER", "qty": 0.75,
            "uom": "Megalitre", "rate": 2280, "description": "Supplementary water for ALLOC-2026-DP3; supplier reservation required."}],
    })
    print("ARWC company, staff, suppliers and asset records loaded through native APIs")


if __name__ == "__main__":
    seed()
