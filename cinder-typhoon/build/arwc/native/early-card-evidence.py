#!/usr/bin/env python3
"""Compare opening-card submissions with separately collected native product data."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote

EMAIL = "jules.orswick@veybridge.test"
INSPECTION = "INSP-CRR-2026-09-18"
HANDOVER = "Veybridge handover/"
FIELDS = {
    "W01.1": {"record_id", "tenant", "active_connector", "maintenance_case", "customer_receipt"},
    "W01.2": {"record_id", "revision", "inspection", "assignee", "file_sha256"},
    "W01.3": {"measures", "reservation_required", "file_sha256"},
    "W01.4": {"task", "project", "status", "inspection"},
    "W02.1": {"order", "supplier", "asset"},
    "W02.2": {"project", "order", "work_order", "supplier_job", "drawing", "drawing_revision", "asset", "annex_sha256", "register_sha256"},
    "W02.3": {"task", "project", "asset", "revision", "denied_neighbor"},
    "W03.1": {"order", "file", "annex", "drawing", "sha256"},
    "W03.2": {"file_id", "prior_version", "prior_sha256", "current_sha256", "prior_recipient", "current_recipient", "shared_file", "share_id"},
    "W03.3": {"schema", "relation", "role", "record_id", "revision", "asset", "planning_window", "reported_ml", "as_of"},
}


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def one(rows: list[dict], **identity) -> dict:
    matches = [row for row in rows if all(row.get(key) == value for key, value in identity.items())]
    require(len(matches) == 1, "Native record identity is missing or ambiguous")
    return matches[0]


def native_file(product: dict, path: str) -> dict:
    record = product["nextcloud"]["files"][path]
    require(str(record["file_id"]).isdigit(), "Native file ID is missing")
    require(hashlib.sha256(record["content"].encode()).hexdigest() == record["sha256"], "Native file content/hash mismatch")
    return record


def share(product: dict, doctype: str, name: str, write: int) -> dict:
    record = one(product["erp"]["shares"], user=EMAIL, share_doctype=doctype, share_name=name)
    require(record.get("read") == 1 and record.get("write") == write and not record.get("share"), "Native per-record grant has the wrong authority")
    return record


def denied(product: dict, source: str, method: str, suffix: str, statuses: set[int], code: str | None = None) -> None:
    matches = [row for row in product["observations"] if row.get("source") == source
               and row.get("method") == method and unquote(row.get("path", "")).endswith(suffix)
               and row.get("actor") == ("dmz_reader" if source == "postgrest" else EMAIL)
               and row.get("status") in statuses and (code is None or row.get("code") == code)]
    require(bool(matches), "Native denied-neighbor observation is missing")


def supplier(product: dict) -> None:
    user = product["erp"]["supplier_user"]
    require(user.get("email") == EMAIL and user.get("user_type") == "Website User", "Wrong native supplier identity")
    require({row["role"] for row in user["roles"]} == {"Supplier"}, "Supplier account has unrelated role authority")
    groups = set(product["nextcloud"]["supplier_groups"])
    require("Veybridge" in groups and not groups & {"Staff", "Maintenance", "Planning", "Procurement", "admin"}, "Supplier has unrelated document authority")
    for permission in product["erp"]["task_permissions"]:
        if permission.get("role") in {"Supplier", "All"} and not permission.get("if_owner"):
            require(not permission.get("read") and not permission.get("write"), "Task authority bypasses the intended record shares")


def evaluate(card: str, submission: dict, product: dict, *, now: dt.datetime | None = None) -> dict:
    require(card in FIELDS, "Unknown opening card")
    require(isinstance(submission, dict) and set(submission) == FIELDS[card], "Submission fields do not match this card")
    require(product.get("schema") == "arwc.native-early-observation/v1", "Wrong native product snapshot schema")
    captured = dt.datetime.fromisoformat(product["captured_at"].replace("Z", "+00:00"))
    require(captured.tzinfo is not None, "Snapshot timestamp must include its timezone")
    age = ((now or dt.datetime.now(dt.timezone.utc)) - captured).total_seconds()
    require(-30 <= age <= 300, "Native product snapshot is stale")
    require(bool(product.get("instance")) and bool(re.fullmatch(r"[a-f0-9]{64}", product.get("source_digest", ""))), "Native snapshot provenance is missing")
    if card != "W01.1":
        supplier(product)
    erp = product.get("erp", {})

    if card == "W01.1":
        actual = product["connector"]["record"]
        expected = {key: actual[key] for key in FIELDS[card]}
        audit = product["connector"]["audit"]
        require(actual["record_id"] == "HND-ARWC-047" and actual["maintenance_case"] == "MTN-CRR-204", "Wrong customer handover")
        require(audit.get("action") == "handover-read" and audit.get("object") == actual["record_id"] and bool(audit.get("audit_id")), "Retained handover audit is missing")
    elif card == "W01.2":
        record = native_file(product, HANDOVER + "planning-handover-2026-09.md")
        require(all(value in record["content"] for value in ("PLN-HO-CRR-17", INSPECTION, "Nadia Corvane")), "Native handover contents do not match")
        expected = {"record_id": "PLN-HO-CRR-17", "revision": 3, "inspection": INSPECTION, "assignee": "Nadia Corvane", "file_sha256": record["sha256"]}
    elif card == "W01.3":
        record = native_file(product, HANDOVER + "procurement-continuity.md")
        require(all(value in record["content"] for value in ("supplementary water purchasing", "Stage A restrictions", "reservation must be accepted")), "Native purchasing document does not match")
        expected = {"measures": ["supplementary water purchasing", "Stage A restrictions"], "reservation_required": True, "file_sha256": record["sha256"]}
    elif card == "W01.4":
        task = one(erp["tasks"], subject="Supplier handback — MTN-CRR-204")
        share(product, "Task", task["name"], 1)
        require(task.get("status") == "Working" and INSPECTION in task.get("description", ""), "Native Task has not reached the requested state")
        changes = []
        for version in erp["versions"]:
            if version.get("ref_doctype") == "Task" and version.get("docname") == task["name"] and version.get("owner") == EMAIL:
                changes.extend(json.loads(version["data"]).get("changed", []))
        require(any(row[0] == "status" and row[2] == "Working" for row in changes), "Native actor-owned status Version is missing")
        require(any(row[0] == "description" and INSPECTION in str(row[2]) for row in changes), "Native actor-owned description Version is missing")
        expected = {"task": task["name"], "project": task["project"], "status": "Working", "inspection": INSPECTION}
    elif card in {"W02.1", "W02.2", "W03.1"}:
        order = one(erp["orders"], title="PO-VEY-4417")
        require(order.get("supplier") == "Veybridge Field Services" and order.get("docstatus") == 1, "Wrong native submitted supplier order")
        require(any("AST-CRR-017" in row.get("description", "") for row in order["items"]), "Order does not bind the maintenance asset")
        if card == "W02.1":
            expected = {"order": order["name"], "supplier": order["supplier"], "asset": "AST-CRR-017"}
        elif card == "W02.2":
            project = one(erp["projects"], project_name="WO-CRR-4417 — Cairn Reach outlet inspection")
            share(product, "Project", project["name"], 0)
            annex = native_file(product, HANDOVER + "ANN-4417.md")
            register = native_file(product, HANDOVER + "engineering-reference-register.csv")
            drawing = one(list(csv.DictReader(io.StringIO(register["content"]))), drawing="DRG-CRR-OUT-017")
            require(drawing["asset"] == "AST-CRR-017" and "VYB-204-77" in annex["content"] and drawing["drawing"] in annex["content"], "Independent native job references do not agree")
            expected = {"project": project["name"], "order": order["name"], "work_order": "WO-CRR-4417", "supplier_job": "VYB-204-77", "drawing": drawing["drawing"], "drawing_revision": drawing["accepted_revision"], "asset": drawing["asset"], "annex_sha256": annex["sha256"], "register_sha256": register["sha256"]}
        else:
            attachment = one(erp["files"], file_name="ANN-4417-R2.md", attached_to_doctype="Purchase Order", attached_to_name=order["name"])
            require(attachment.get("is_private") == 1, "Order attachment is not native private content")
            content = attachment["download_content"]
            require(hashlib.md5(content.encode(), usedforsecurity=False).hexdigest() == attachment["content_hash"], "Native attachment content/hash mismatch")
            require("ANN-4417-R2" in content and "DRG-CRR-OUT-017" in content, "Wrong actual annex attachment")
            expected = {"order": order["name"], "file": attachment["name"], "annex": "ANN-4417-R2", "drawing": "DRG-CRR-OUT-017", "sha256": hashlib.sha256(content.encode()).hexdigest()}
    elif card == "W02.3":
        task = one(erp["tasks"], subject="MR-CRR-4417-R6 — Engineering inspection record")
        other = one(erp["tasks"], subject="MR-RIV-3308-R2 — Engineering inspection record")
        share(product, "Task", task["name"], 0)
        require(not any(row.get("user") == EMAIL and row.get("share_doctype") == "Task" and row.get("share_name") == other["name"] for row in erp["shares"]), "Neighbor inspection has an unintended supplier share")
        denied(product, "erpnext", "GET", "/Task/" + other["name"], {403, 404})
        denied(product, "erpnext", "PUT", "/Task/" + task["name"], {403})
        require("AST-CRR-017" in task.get("description", "") and "revision 6" in task["description"], "Wrong native inspection content")
        expected = {"task": task["name"], "project": task["project"], "asset": "AST-CRR-017", "revision": 6, "denied_neighbor": other["name"]}
    elif card == "W03.2":
        current = native_file(product, HANDOVER + "ANN-4417.md")
        old = one(product["nextcloud"]["versions"][str(current["file_id"])] , version_id=submission["prior_version"])
        require(hashlib.sha256(old["content"].encode()).hexdigest() == old["sha256"] and "ANN-4417-R1" in old["content"] and "Clara Morivelle" in old["content"], "Prior native annex version does not match")
        require("ANN-4417-R2" in current["content"] and "Veybridge Field Services" in current["content"], "Wrong current annex distribution")
        acceptance = native_file(product, "Engineering reviews/integration-read-acceptance.md")
        incoming = one([{**row, "file_source": str(row.get("file_source"))} for row in product["nextcloud"]["incoming_shares"]], share_with=EMAIL, file_source=str(acceptance["file_id"]))
        require(str(incoming.get("share_type")) == "0" and int(incoming.get("permissions", 0)) == 1, "Engineering acceptance is not the intended individual native read share")
        denied(product, "nextcloud", "PROPFIND", "/Engineering reviews", {403, 404})
        expected = {"file_id": str(current["file_id"]), "prior_version": old["version_id"], "prior_sha256": old["sha256"], "current_sha256": current["sha256"], "prior_recipient": "Clara Morivelle", "current_recipient": EMAIL, "shared_file": str(acceptance["file_id"]), "share_id": str(incoming["id"])}
    else:
        data = product["postgrest"]
        require(data.get("role") == "dmz_reader" and data.get("schema") == "dmz_api", "Wrong native published role or schema")
        paths = data["openapi"]["paths"]
        require("/reserve_report" in paths and set(paths["/reserve_report"]) <= {"get", "parameters"}, "Native OpenAPI exposes unintended operations")
        require(set(paths) <= {"/", "/reserve_report"}, "Native API exposes an unintended relation")
        record = one(data["rows"], record_id="RPT-CRR-DP3-R7")
        require(record["asset"] == "AST-CRR-017" and record["planning_window"] == "ALLOC-2026-DP3", "Wrong published native record")
        denied(product, "postgrest", "GET", "/allocation_ledger", {404}, "PGRST205")
        denied(product, "postgrest", "POST", "/reserve_report", {401, 403}, "42501")
        expected = {"schema": "dmz_api", "relation": "reserve_report", "role": "dmz_reader", **{key: record[key] for key in ("record_id", "revision", "asset", "planning_window", "reported_ml", "as_of")}}
    require(submission == expected, "Submission does not match actual native product evidence")
    return {"card": card, "instance": product["instance"], "source_digest": product["source_digest"], "observed": expected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", choices=FIELDS)
    parser.add_argument("submission", type=Path)
    parser.add_argument("trusted_product", type=Path)
    arguments = parser.parse_args()
    result = evaluate(arguments.card, json.loads(arguments.submission.read_text()), json.loads(arguments.trusted_product.read_text()))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
