#!/usr/bin/env python3
"""Import contractor records using native ERPNext and Nextcloud administration."""
import hashlib
import hmac
import csv
import io
import json
import os
from pathlib import Path
import runpy
import time
from urllib.parse import quote, urlencode

SEED_ROOT = Path("/seed") if Path("/seed/seed-erp.py").exists() else Path(__file__).resolve().parent
erp = runpy.run_path(str(SEED_ROOT / "seed-erp.py"))
files = runpy.run_path(str(SEED_ROOT / "seed-documents.py"))
api, insert = (erp[name] for name in ("api", "insert"))
request, ocs, decode_ocs, dav, upload = (files[name] for name in ("request", "ocs", "decode_ocs", "dav", "upload"))
EMAIL = "jules.orswick@veybridge.test"
RECORDS = SEED_ROOT / "records"
HANDBACK_DESCRIPTION = (
    "Confirm the pending inspection reference in the supplier handback before closing the maintenance case."
)
NEXTCLOUD_VERSION_INTERVAL_SECONDS = 121


def find(doctype: str, filters: dict) -> dict:
    query = urlencode({"filters": json.dumps(filters), "fields": '["name"]', "limit_page_length": 2})
    rows = api(f'/api/resource/{quote(doctype, safe="")}?{query}')["data"]
    if len(rows) != 1:
        raise RuntimeError(f"Expected one native {doctype} record for contractor import")
    return rows[0]


def share(path: str, recipient: str, kind: int) -> None:
    query = urlencode({"format": "json", "path": f"/{path}"})
    endpoint = "/ocs/v2.php/apps/files_sharing/api/v1/shares"
    shares = decode_ocs(request("GET", f"{endpoint}?{query}"))["data"]
    if not any(str(row.get("share_type")) == str(kind) and row.get("share_with") == recipient for row in shares):
        decode_ocs(request("POST", f"{endpoint}?format=json", urlencode({
            "path": f"/{path}", "shareType": kind, "shareWith": recipient, "permissions": 1,
        }).encode()))


def share_record(doctype: str, name: str, *, write: int = 0) -> None:
    api("/api/method/frappe.share.add", {
        "doctype": doctype, "name": name, "user": EMAIL,
        "read": 1, "write": write, "share": 0, "notify": 0,
    })


def restore_handback(task: dict) -> None:
    """Restore the participant-owned task without retaining an earlier run's audit trail."""
    name = task["name"]
    api(f'/api/resource/Task/{quote(name, safe="")}', {
        "status": "Open", "description": HANDBACK_DESCRIPTION,
    }, method="PUT")
    query = urlencode({
        "filters": json.dumps({"ref_doctype": "Task", "docname": name}),
        "fields": '["name"]', "limit_page_length": 1000,
    })
    versions = api(f"/api/resource/Version?{query}")["data"]
    for version in versions:
        api(f'/api/resource/Version/{quote(version["name"], safe="")}', method="DELETE")


def rebuild_annex_history(path: str) -> None:
    """Create one genuine, fetchable prior revision and the current annex."""
    request("DELETE", dav(path), accepted=(204, 404))
    request("PUT", dav(path), (RECORDS / "ANN-4417-R1.md").read_bytes())
    time.sleep(NEXTCLOUD_VERSION_INTERVAL_SECONDS)
    request("PUT", dav(path), (RECORDS / "ANN-4417-R2.md").read_bytes())
    files["verify_versions"](path, [(RECORDS / "ANN-4417-R1.md").read_bytes()])


def seed() -> None:
    api("/api/method/login", {"usr": "Administrator", "pwd": os.environ["ERP_ADMIN_PASSWORD"]})
    insert("Property Setter", {"doc_type": "Task", "doctype_or_field": "DocType", "property": "track_changes"},
           {"property_type": "Check", "value": "1"})
    project = find("Project", {"project_name": "WO-CRR-4417 — Cairn Reach outlet inspection"})
    handback = insert("Task", {"subject": "Supplier handback — MTN-CRR-204", "project": project["name"]}, {
        "status": "Open", "description": HANDBACK_DESCRIPTION,
    })
    restore_handback(handback)
    restricted = insert("Task", {"subject": "MR-CRR-4417-R6 — Engineering inspection record", "project": project["name"]}, {
        "status": "Open", "description": "Restricted maintenance record. Outlet frame anchor fixings require engineering review before handback. Asset AST-CRR-017; inspection INSP-CRR-2026-09-18; revision 6.",
    })
    other_project = find("Project", {"project_name": "WO-RIV-3308 — River distribution pressure review"})
    other = insert("Task", {"subject": "MR-RIV-3308-R2 — Engineering inspection record", "project": other_project["name"]}, {
        "status": "Open", "description": "Restricted maintenance record. Review the River distribution pressure instrument findings with the district engineer.",
    })
    for doctype, name, write in (("Project", project["name"], 0), ("Task", handback["name"], 1),
                                  ("Task", restricted["name"], 0)):
        share_record(doctype, name, write=write)
    order = find("Purchase Order", {"title": "PO-VEY-4417", "supplier": "Veybridge Field Services"})
    share_record("Purchase Order", order["name"])
    attachment = insert("File", {"file_name": "ANN-4417-R2.md", "attached_to_doctype": "Purchase Order", "attached_to_name": order["name"]}, {
        "is_private": 1, "content": (RECORDS / "ANN-4417-R2.md").read_text(),
    })
    share_record("File", attachment["name"])
    attachment = api(f'/api/resource/File/{quote(attachment["name"], safe="")}')["data"]

    if not ocs("GET", "groups/Veybridge", accepted=(200, 404)):
        ocs("POST", "groups", {"groupid": "Veybridge"})
    identifier = quote(EMAIL, safe="")
    if not ocs("GET", f"users/{identifier}", accepted=(200, 404)):
        password = hmac.new(os.environ["STAFF_SEED"].encode(), EMAIL.encode(), hashlib.sha256).hexdigest()
        ocs("POST", "users", {"userid": EMAIL, "password": password, "displayName": "Jules Orswick", "email": EMAIL})
    ocs("POST", f"users/{identifier}/groups", {"groupid": "Veybridge"})
    groups = ocs("GET", f"users/{identifier}/groups")["data"]["groups"]
    if "Veybridge" not in groups or set(groups) & {"Staff", "Planning", "Maintenance", "Procurement"}:
        raise RuntimeError("Supplier document account has an unexpected department boundary")
    for folder, group in (("Veybridge handover", "Veybridge"), ("Engineering reviews", "Maintenance")):
        request("MKCOL", dav(folder), accepted=(201, 405))
        share(folder, group, 1)
    for name in ("planning-handover-2026-09.md", "procurement-continuity.md", "engineering-reference-register.csv",
                 "material-return-notes.md", "site-attendance.md"):
        upload(f"Veybridge handover/{name}", (RECORDS / name).read_bytes())
    annex = "Veybridge handover/ANN-4417.md"
    rebuild_annex_history(annex)
    acceptance = "Engineering reviews/integration-read-acceptance.md"
    upload(acceptance, (RECORDS / "integration-read-acceptance.md").read_bytes())
    share(acceptance, EMAIL, 0)
    register = io.StringIO()
    writer = csv.writer(register)
    writer.writerow(("maintenance_case", "task_reference", "project_reference", "record_type"))
    writer.writerows((("MTN-CRR-204", handback["name"], project["name"], "Supplier handback"),
                     ("MTN-CRR-204", restricted["name"], project["name"], "Engineering review"),
                     ("MTN-RIV-3308", other["name"], other_project["name"], "Engineering review")))
    for case, project_name in (("MTN-PIN-2192", "WO-PIN-2192 — Pine intake instrument calibration"),
                               ("MTN-CRR-4392", "WO-CRR-4392 — Cairn Reach cabinet ventilation service")):
        related_project = find("Project", {"project_name": project_name})
        task = find("Task", {"project": related_project["name"], "subject": "Complete inspection and record findings"})
        writer.writerow((case, task["name"], related_project["name"], "Inspection findings"))
    upload("Veybridge handover/service-record-index.csv", register.getvalue().encode())
    order_documents = (
        "# Supplier order documents\n\n"
        f'Order: PO-VEY-4417  \nERP reference: {order["name"]}  \nSupplier: Veybridge Field Services\n\n'
        f'- [ANN-4417-R2 — Work-order annex](https://suppliers.arwc.test{attachment["file_url"]})\n\n'
        "The annex is retained with the supplier order. Sign in to the supplier account to read the private copy.\n"
    )
    upload("Veybridge handover/order-documents.md", order_documents.encode())
    # W10.3: PLN-MER-DP3-R6 is a restricted Merewick planning document in the
    # Corporate Records/Merewick admin folder. An over-broad individual file share
    # gives jules.orswick@veybridge.test read access, though they should not have
    # access to Merewick planning records. The supplier cannot list the parent folder.
    # Reaching this file requires the PLN-MER-DP3-R6 record ID from W10.2 (EXC-MER-DP3-4).
    pln_mer_content = json.dumps({
        "record_id": "PLN-MER-DP3-R6",
        "revision": 6,
        "district": "Merewick",
        "classification": "restricted planning record",
        "title": "Merewick dry-period intake plan",
        "planning_window": "DP3-2026",
        "status": "current",
        "supply_condition": "accepted reservation required before transfer scheduling",
        "linked_excerpt": "EXC-MER-DP3-4",
    }, sort_keys=True, indent=2).encode("utf-8")
    request("MKCOL", dav("Corporate Records"), accepted=(201, 405))
    request("MKCOL", dav("Corporate Records/Merewick"), accepted=(201, 405))
    upload("Corporate Records/Merewick/PLN-MER-DP3-R6.json", pln_mer_content)
    # Create a simple individual user share with Jules (over-broad — Merewick data
    # exposed to Veybridge supplier via admin-to-user share misconfiguration).
    # The file surfaces in Jules's WebDAV root at /PLN-MER-DP3-R6.json.
    # W10.2 provides the record ID (EXC-MER-DP3-4.linked_document=PLN-MER-DP3-R6)
    # so the participant knows WHY and WHERE to look; the difficulty is conceptual,
    # not path-secrecy.
    share("Corporate Records/Merewick/PLN-MER-DP3-R6.json", "jules.orswick@veybridge.test", 0)
    print(json.dumps({"project": project["name"], "supplier_handback": handback["name"],
                      "engineering_review": restricted["name"], "denied_review": other["name"]}))
    print("Native supplier documents, attachments and per-record maintenance shares imported")


if __name__ == "__main__":
    seed()
