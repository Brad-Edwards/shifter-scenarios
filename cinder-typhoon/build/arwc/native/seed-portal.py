#!/usr/bin/env python3
"""Create supplier relationships and orders through native ERPNext APIs."""
import json
import os
import runpy
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

erp = runpy.run_path("/seed/seed-erp.py")
api, insert, user = (erp[name] for name in ("api", "insert", "user"))
COMPANY = erp["COMPANY"]


def seed() -> None:
    api("/api/method/login", {"usr": "Administrator", "pwd": os.environ["ERP_ADMIN_PASSWORD"]})
    email = "jules.orswick@veybridge.test"
    user(email, "Jules Orswick", ["Supplier"], user_type="Website User")
    supplier = insert("Supplier", {"supplier_name": "Veybridge Field Services"}, {})
    insert("Contact", {"email_id": email}, {
        "first_name": "Jules", "last_name": "Orswick", "user": email,
        "email_ids": [{"email_id": email, "is_primary": 1}],
        "links": [{"link_doctype": "Supplier", "link_name": supplier["name"]}],
    })
    supplier_path = f'/api/resource/Supplier/{quote(supplier["name"], safe="")}'
    document = api(supplier_path)["data"]
    portal_users = [{"user": row["user"]} for row in document.get("portal_users", [])]
    if not any(row["user"] == email for row in portal_users):
        api(supplier_path, {"portal_users": [*portal_users, {"user": email}]}, method="PUT")
    insert("Item", {"item_code": "FIELD-SERVICE"}, {
        "item_name": "Field maintenance service", "item_group": "Services", "stock_uom": "Nos",
        "is_stock_item": 0, "is_purchase_item": 1,
    })
    for reference, supplier_name, description, rate in (
        ("PO-VEY-4417", "Veybridge Field Services", "Cairn Reach outlet actuator inspection — asset AST-CRR-017; WO-CRR-4417", 1800),
        ("PO-VEY-4392", "Veybridge Field Services", "Cairn Reach cabinet ventilation service — WO-CRR-4392", 650),
        ("PO-ARD-2192", "Ardenvale Instrument Services", "Pine intake instrument calibration — WO-PIN-2192", 1200),
    ):
        order = insert("Purchase Order", {"title": reference, "supplier": supplier_name}, {
            "company": COMPANY, "transaction_date": "2026-11-09", "schedule_date": "2026-11-20",
            "currency": "USD", "buying_price_list": "Standard Buying",
            "items": [{"item_code": "FIELD-SERVICE", "qty": 1, "rate": rate,
                       "schedule_date": "2026-11-20", "description": description}],
        })
        document = api(f'/api/resource/Purchase%20Order/{quote(order["name"], safe="")}')["data"]
        if document["docstatus"] == 0:
            api("/api/method/frappe.client.submit", {"doc": json.dumps(document)})
        print(f'{reference}: {order["name"]}')
    print("Supplier portal user, contact, party permissions and purchase orders loaded through native APIs")

    # W13.1: seed the outlet-inspection appointment as a real ERPNext Event.
    # APT-CRR-2026-09-18 covers INSP-CRR-2026-09-18 on asset AST-CRR-017,
    # Thursday 09:00–11:00. The contractor portal fetches this Event at startup.
    insert("Event", {"subject": "APT-CRR-2026-09-18: Outlet inspection AST-CRR-017"}, {
        "starts_on": "2026-09-18 09:00:00",
        "ends_on": "2026-09-18 11:00:00",
        "event_category": "Other",
        "event_type": "Private",
        "description": json.dumps({
            "record_id": "APT-CRR-2026-09-18",
            "revision": 1,
            "inspection": "INSP-CRR-2026-09-18",
            "asset": "AST-CRR-017",
            "window": {"day": "Thursday", "starts": "09:00", "ends": "11:00"},
            "owner_organization": "Northbank Civil Inspections",
            "attendee": "northbank.inspector.117",
        }, sort_keys=True),
    })
    print("APT-CRR-2026-09-18: outlet-inspection appointment seeded as ERPNext Event")

    # W13.2: seed the contractor assignment roster as a real ERPNext Task.
    # ROSTER-CRR-SEP18-R2 lists veybridge.tech.204 for assignment CTR-VEY-204.
    # The portal fetches this Task at startup for the visitors/roster endpoint.
    insert("Task", {"subject": "ROSTER-CRR-SEP18-R2: Contractor assignment INSP-CRR-2026-09-18"}, {
        "subject": "ROSTER-CRR-SEP18-R2: Contractor assignment INSP-CRR-2026-09-18",
        "status": "Open",
        "description": json.dumps({
            "record_id": "ROSTER-CRR-SEP18-R2",
            "revision": 2,
            "inspection": "INSP-CRR-2026-09-18",
            "identity": "veybridge.tech.204",
            "assignment": "CTR-VEY-204",
            "contractor_organization": "Veybridge Technical Services",
        }, sort_keys=True),
    })
    print("ROSTER-CRR-SEP18-R2: contractor assignment roster seeded as ERPNext Task")

    # W14.1: seed FIELD-BAG-CRR-4417-R3.json to Nextcloud (contractor workspace).
    # The contractor portal fetches this file at startup using the NC admin credentials.
    nc_admin = "records-admin"
    nc_admin_password = os.environ.get("DOCUMENTS_ADMIN_PASSWORD", "")
    if nc_admin_password:
        import base64 as _base64, xml.etree.ElementTree as _ET
        from urllib.error import HTTPError as _HTTPError
        nc_auth = "Basic " + _base64.b64encode(f"{nc_admin}:{nc_admin_password}".encode()).decode()
        nc_url = "http://nextcloud"
        nc_headers = {"Host": "documents.arwc.test", "Authorization": nc_auth, "OCS-APIRequest": "true"}
        field_bag_content = json.dumps({
            "record_id": "FIELD-BAG-CRR-4417-R3",
            "revision": 3,
            "inspection": "INSP-CRR-2026-09-18",
            "asset": "AST-CRR-017",
            "expected_outlets": ["OG-CRR-02"],
            "retained_client": {
                "name": "fieldbag",
                "protocol": "fieldbag/v1",
                "encoding": "application/json",
                "request_fields": ["asset_id", "outlet_group", "sample_time"],
            },
            "service_manifest": {
                "record_id": "FIELD-SERVICES-R21",
                "legacy_endpoint": "field-read-legacy.arwc.test",
                "current_endpoint": "process-read.arwc.test",
            },
        }, sort_keys=True, indent=2).encode("utf-8")
        # Ensure the contractor workspace folder exists (admin's space).
        nc_folder = f"/remote.php/dav/files/{nc_admin}/contractor-workspace"
        try:
            urlopen(Request(f"{nc_url}{nc_folder}", method="MKCOL", headers={**nc_headers, "Content-Type": "text/xml"}), timeout=10)
        except _HTTPError:
            pass  # Folder already exists or other non-fatal error
        # Upload the field bag JSON to admin's contractor-workspace folder.
        field_bag_path = f"{nc_folder}/FIELD-BAG-CRR-4417-R3.json"
        try:
            req = Request(f"{nc_url}{field_bag_path}", data=field_bag_content, method="PUT",
                          headers={**nc_headers, "Content-Type": "application/json"})
            urlopen(req, timeout=10)
            print("FIELD-BAG-CRR-4417-R3.json: seeded to Nextcloud contractor-workspace folder")
        except Exception as e:
            print(f"W14.1: failed to seed FIELD-BAG-CRR-4417-R3.json to Nextcloud: {e}")
    else:
        print("W14.1: DOCUMENTS_ADMIN_PASSWORD not set; skipping Nextcloud field bag seed")


if __name__ == "__main__":
    seed()
