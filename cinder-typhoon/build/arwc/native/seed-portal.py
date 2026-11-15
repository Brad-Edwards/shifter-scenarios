#!/usr/bin/env python3
"""Create supplier relationships and orders through native ERPNext APIs."""
import json
import os
import runpy
from urllib.parse import quote

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


if __name__ == "__main__":
    seed()
