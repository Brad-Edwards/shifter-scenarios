#!/usr/bin/env python3
"""Validate issue 126 purchasing, stores, invoice, and payment histories."""
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile

from pypdf import PdfReader
import yaml


SNAPSHOT = "2026-09-16T08:30:00-04:00"
STORY = "purchasing-stores"
PROCUREMENT = {"priya", "awm205", "awm206", "awm207", "awm208", "awm209"}
ACCOUNTS = {"awm197", "awm198", "awm199", "awm200", "awm201", "awm202", "awm203", "awm204"}


def require(value, message):
    if not value:
        raise ValueError("Purchasing/stores: " + message)


def archive_tables(root, manifest):
    with zipfile.ZipFile(root / "documents/purchasing-stores-records.zip") as archive:
        return {
            name: list(csv.DictReader(io.StringIO(archive.read(info["member"]).decode())))
            for name, info in manifest["tables"].items()
        }


def check_purchasing_stores(root, workforce, identity, mail, docs):
    manifest = yaml.safe_load((root / "authoring/purchasing-stores.yaml").read_text())
    require(manifest["snapshot"] == SNAPSHOT, "snapshot drift")
    require(manifest["required_base"]["accepted_maintenance_engineering_commit"] == "0b7f0b2"
            and manifest["required_base"]["accepted_laboratory_quality_commit"] == "f16aec0",
            "accepted-base drift")
    require(manifest["native_sources"] == {
        "mail": "cinder-typhoon/narrative/arwc-mail",
        "documents": "cinder-typhoon/narrative/arwc-documents",
        "logical_owner": "a-corporate.a-business",
    }, "native source or owner drift")

    people = {person["key"]: person for person in workforce}
    contacts = identity["people"] | identity["correspondents"] | people
    messages = {message["id"]: message for message in mail if message.get("story") == STORY}
    documents = {document["id"]: document for document in docs if document.get("story") == STORY}
    counts = manifest["counts"]
    require(len(messages) == counts["messages"] == 2325, "message inventory")
    require(len(documents) == counts["documents"] == 4918, "document inventory")
    coverage = json.loads((root / "story-coverage.json").read_text())["messages"]
    require(sum(len(coverage[key]["retained"].get("arwc", [])) for key in messages)
            == counts["retained_copies"] == 6443, "retained mailbox-copy count")
    require(len({message["body"] for message in messages.values()}) == len(messages),
            "correspondence body duplication")
    require(all(document["audience"] == "restricted"
                and all(contacts[key]["employer"] == "arwc" for key in document["reader_keys"])
                for document in documents.values()), "document-library reader boundary")

    suppliers = {supplier["key"]: supplier for supplier in manifest["suppliers"]}
    require(len(suppliers) == 9 and all(supplier["voice"] and supplier["template"] for supplier in suppliers.values()),
            "supplier profile or template inventory")
    require(all(supplier["domain"].endswith(".test")
                and contacts[supplier["speaker"]]["employer"] == supplier["key"]
                for supplier in suppliers.values()), "supplier identity or fictional domain")
    require(len({supplier["template"] for supplier in suppliers.values()}) == len(suppliers),
            "supplier templates are not distinct")

    histories = manifest["histories"]
    by_id = {history["id"]: history for history in histories}
    require(len(histories) == len(by_id) == counts["histories"] == 480, "history inventory")
    require(Counter(history["state"] for history in histories) ==
            Counter({"paid": 402, "payable": 27, "received": 27, "ordered": 24}),
            "history state distribution")
    reference_fields = ("requisition", "quotation", "decision", "approval", "purchase_order")
    for field in reference_fields:
        require(len({history[field] for history in histories}) == len(histories), f"duplicate {field}")

    expected_messages = set()
    attachment_ids = set()
    for history in histories:
        require(history["supplier"] in suppliers and history["buyer"] in PROCUREMENT
                and history["approver"] in {"awm205", "awm217"}
                and history["accounts_officer"] in ACCOUNTS,
                f"role assignment: {history['id']}")
        requested = datetime.fromisoformat(history["requested_at"])
        quoted = datetime.fromisoformat(history["quoted_at"])
        approved = datetime.fromisoformat(history["approved_at"])
        ordered = datetime.fromisoformat(history["ordered_at"])
        require(requested < quoted < approved < ordered <= datetime.fromisoformat(SNAPSHOT),
                f"request/order chronology: {history['id']}")
        amount = sum(line["quantity"] * line["unit_cents"] for line in history["lines"])
        require(amount == history["amount_cents"]
                and all(line["quantity"] > 0 and line["amount_cents"] == line["quantity"] * line["unit_cents"]
                        for line in history["lines"]), f"line arithmetic: {history['id']}")
        allocations = history["allocation"]
        require(sum(row["amount_cents"] for row in allocations) == amount, f"allocation total: {history['id']}")
        if history["cost_center"] == "REGIONAL-SHARED":
            require({row["cost_center"] for row in allocations} == {"PINE-SHARED", "RIVER-SHARED"}
                    and allocations[0]["amount_cents"] == (amount * 55 + 50) // 100,
                    f"shared allocation: {history['id']}")
        else:
            require(allocations == [{"cost_center": history["cost_center"], "amount_cents": amount}],
                    f"district allocation: {history['id']}")

        received = datetime.fromisoformat(history["received_at"]) if history["received_at"] else None
        invoiced = datetime.fromisoformat(history["invoiced_at"]) if history["invoiced_at"] else None
        paid = datetime.fromisoformat(history["paid_at"]) if history["paid_at"] else None
        if history["state"] == "ordered":
            require(not any(history[key] for key in ("receipt", "supplier_invoice", "invoice_match",
                                                     "payment_request", "payment_record")),
                    f"ordered history claims later records: {history['id']}")
        elif history["state"] == "received":
            require(received and ordered < received <= datetime.fromisoformat(SNAPSHOT)
                    and history["receipt"] and not history["supplier_invoice"],
                    f"received history state: {history['id']}")
        else:
            require(received and invoiced and ordered < received < invoiced <= datetime.fromisoformat(SNAPSHOT)
                    and all(history[key] for key in ("receipt", "supplier_invoice", "invoice_match", "payment_request")),
                    f"invoice chain: {history['id']}")
            due = datetime.fromisoformat(history["due_at"])
            require(due > invoiced, f"invoice due date: {history['id']}")
            if history["state"] == "paid":
                require(paid and invoiced < paid <= datetime.fromisoformat(SNAPSHOT) and history["payment_record"],
                        f"paid history state: {history['id']}")
            else:
                require(not paid and not history["payment_record"],
                        f"payable history state: {history['id']}")

        key = history["key"]
        chain = {key + "-request", key + "-quote", key + "-order"}
        if history["supplier_invoice"]:
            chain |= {key + "-invoice", key + "-payment"}
        elif history["receipt"]:
            chain.add(key + "-receipt")
        require(chain <= messages.keys(), f"message chain: {history['id']}")
        expected_messages |= chain
        require(messages[key + "-order"]["reply_to"] == key + "-quote", f"external quote/order thread: {history['id']}")
        if history["supplier_invoice"]:
            require(messages[key + "-invoice"]["reply_to"] == key + "-order"
                    and messages[key + "-payment"]["reply_to"] == key + "-request",
                    f"external/internal thread separation: {history['id']}")
        attachment_ids |= {attachment for message_id in chain for attachment in messages[message_id].get("attachments", [])}

        # Every newly authored form reads back its own authority and amount.
        for suffix in ("requisition", "decision", "approval"):
            document = documents[key + "-" + suffix]
            require(document["audience"] == "restricted" and history[suffix] in document["text"],
                    f"{suffix} form: {history['id']}")
        require(set(documents[key + "-requisition"]["reader_keys"]) == PROCUREMENT | {history["requester"]}
                and set(documents[key + "-decision"]["reader_keys"]) == PROCUREMENT | {history["requester"], history["approver"]}
                and set(documents[key + "-approval"]["reader_keys"]) == PROCUREMENT | {history["requester"], history["approver"]},
                f"request/decision/approval readers: {history['id']}")
        internal_readers = PROCUREMENT | ACCOUNTS | {history["requester"], history["receiver"], history["approver"]}
        if not history["purchase_order"].startswith("ARWC-PO-26-2") or int(history["purchase_order"].split("-")[-1]) > 224:
            order_doc = documents[key + "-order"]
            require(history["purchase_order"] in order_doc["text"] and f"ORDER TOTAL USD {Decimal(amount) / 100:,.2f}" in order_doc["text"],
                    f"purchase-order form: {history['id']}")
            require(set(order_doc["reader_keys"]) == internal_readers
                    and set(documents[key + "-quotation"]["reader_keys"]) == internal_readers,
                    f"quotation/order readers: {history['id']}")
        if history["supplier_invoice"]:
            invoice_doc = documents[key + "-invoice"]
            require(history["supplier_invoice"] in invoice_doc["text"]
                    and f"INVOICE TOTAL USD {Decimal(amount) / 100:,.2f}" in invoice_doc["text"],
                    f"invoice readback: {history['id']}")
            require(all(token in documents[key + "-invoice-match"]["text"]
                        for token in (history["invoice_match"], history["supplier_invoice"], history["receipt"])),
                    f"invoice-match form: {history['id']}")
            require(all(set(documents[key + "-" + suffix]["reader_keys"]) == internal_readers
                        for suffix in ("invoice", "invoice-match", "payment-request"))
                    and (not history["payment_record"]
                         or set(documents[key + "-payment-record"]["reader_keys"]) == internal_readers),
                    f"invoice/payment readers: {history['id']}")
        if history["receipt"] and history["category"] != "contractor-service":
            require(set(documents[key + "-receipt"]["reader_keys"]) == internal_readers,
                    f"receipt readers: {history['id']}")
        if history["stock_movement"]:
            require(set(documents[key + "-stock-movement"]["reader_keys"]) == internal_readers,
                    f"stock-movement readers: {history['id']}")

    require(expected_messages == set(messages), "unjoined purchasing correspondence")
    require(attachment_ids <= set(documents)
            | {f"me-contractor-{kind}-{number:03d}" for kind in ("quote", "order", "receipt") for number in range(1, 25)},
            "message attachment outside known documents")

    maintenance = yaml.safe_load((root / "authoring/maintenance-engineering.yaml").read_text())
    jobs = {job["purchase_order"]: job for job in maintenance["contractor_jobs"]}
    work = {row["work_order"]: row for row in maintenance["work_orders"]}
    linked = [history for history in histories if history["source_work_order"]]
    require(len(linked) == counts["maintenance_linked"] == 180, "maintenance-linked inventory")
    contractor = [history for history in linked if history["category"] == "contractor-service"]
    require(len(contractor) == len(jobs) == 24, "contractor carry-forward inventory")
    for history in contractor:
        job = jobs[history["purchase_order"]]
        require(history["quotation"] == job["quotation"] and history["receipt"] == job["receipt"]
                and history["source_work_order"] == job["work_order"]
                and history["source_service_report"] == job["service_report"]
                and history["supplier"] == job["supplier"]
                and history["amount_cents"] == int(Decimal(job["amount_usd"]) * 100),
                f"contractor join: {history['id']}")
    for history in [item for item in linked if item["category"] == "maintenance-material"]:
        source = work[history["source_work_order"]]
        require((history["state"] == "paid" and source["status"] == "completed")
                or (history["state"] == "ordered" and source["status"] == "waiting parts"),
                f"maintenance material state: {history['id']}")

    with zipfile.ZipFile(root / "documents/field-operations-records.zip") as archive:
        upstream_stock = {}
        for member in ("stock-P.csv", "stock-R.csv"):
            upstream_stock.update({row["transaction_id"]: row for row in
                                   csv.DictReader(io.StringIO(archive.read(member).decode()))})
    stock_linked = [history for history in histories if history["source_stock_movement"]]
    require(len(stock_linked) == counts["field_stock_linked"] == len(upstream_stock) == 60
            and {history["source_stock_movement"] for history in stock_linked} == set(upstream_stock),
            "field stock replenishment coverage")

    ternwick = [history for history in histories if history["supplier"] == "ternwick"]
    require(len(ternwick) == counts["records_batches"] == 12
            and all(history["state"] == "paid" and history["records_batch_acceptance"] for history in ternwick),
            "Ternwick acceptance/payment state")
    accepted_amounts = {"TR-26-04": 23040, "TR-26-05": 22032, "TR-26-06": 23544, "TR-26-07": 21696}
    require(all(next(history for history in ternwick if history["batch_reference"] == batch)["amount_cents"] == amount
                for batch, amount in accepted_amounts.items()), "settled Ternwick amount drift")

    tables = archive_tables(root, manifest)
    with zipfile.ZipFile(root / "documents/purchasing-stores-records.zip") as archive:
        require(archive.testzip() is None and len(archive.namelist()) == counts["archive_members"] == 898,
                "archive inventory or corruption")
        require(set(archive.namelist()) == {document["member"] for document in documents.values() if "archive" in document},
                "unbound archive member")
        for name, info in manifest["tables"].items():
            raw = archive.read(info["member"])
            rows = tables[name]
            require(len(rows) == info["rows"] and len({row[info["primary_key"]] for row in rows}) == len(rows),
                    f"{name} rows or primary key")
            document = documents[info["document"]]
            require(hashlib.sha256(raw).hexdigest() == info["sha256"] == document["binary_sha256"]
                    and document["content_encoding"] == "gzip", f"{name} bytes or source encoding")
        pdf_docs = [document for document in documents.values() if document.get("media_type") == "application/pdf"]
        require(len(pdf_docs) == counts["quotation_pdfs"] + counts["invoice_pdfs"] == 885,
                "PDF inventory")
        for document in pdf_docs:
            raw = archive.read(document["member"])
            require(raw.startswith(b"%PDF-") and hashlib.sha256(raw).hexdigest() == document["binary_sha256"],
                    f"PDF bytes: {document['id']}")
            pdf = PdfReader(io.BytesIO(raw), strict=True)
            text = "\n".join(page.extract_text() for page in pdf.pages).rstrip() + "\n"
            require(not pdf.is_encrypted and len(pdf.pages) == 1 and text == document["text"],
                    f"PDF readability/search text: {document['id']}")
            require(pdf.metadata.creation_date.date().isoformat() == document["published_at"][:10],
                    f"PDF creation date: {document['id']}")
            require(all(term not in (str(pdf.metadata) + text).lower() for term in
                        ("scenario", "issue 126", "author-only", "openai", "codex")),
                    f"PDF provenance leak: {document['id']}")

    require(len(tables["requisitions"]) == 480 and len(tables["purchase-orders"]) == 480
            and len(tables["receipts"]) == 456 and len(tables["supplier-invoices"]) == 429
            and len(tables["invoice-matches"]) == 429 and len(tables["payment-records"]) == 402,
            "register lifecycle counts")
    require(sum(int(row["amount_cents"]) for row in tables["supplier-invoices"])
            == sum(history["amount_cents"] for history in histories if history["supplier_invoice"]),
            "invoice register total")
    require(sum(int(row["amount_cents"]) for row in tables["payment-records"])
            == sum(history["amount_cents"] for history in histories if history["payment_record"]),
            "payment register total")
    require(sum(int(row["amount_cents"]) for row in tables["ledger-entries"] if row["credit"] == "Accounts payable")
            == sum(history["amount_cents"] for history in histories if history["supplier_invoice"]),
            "ledger payable total")
    require(sum(int(row["amount_cents"]) for row in tables["ledger-entries"] if row["credit"] == "Cash")
            == sum(history["amount_cents"] for history in histories if history["payment_record"]),
            "ledger cash total")

    visible = "\n".join(message["subject"] + "\n" + message["body"] for message in messages.values())
    visible += "\n" + "\n".join(document.get("text", "") for document in documents.values())
    require(all(term not in visible.lower() for term in
                ("cinder typhoon", "challenge-specific", "issue 126", "author-only", "openrae", "shifter-scenarios")),
            "participant-visible authoring leakage")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_purchasing_stores(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "people.yaml").read_text()),
        yaml.safe_load((author / "mail-purchasing-stores.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-purchasing-stores.yaml").read_text())["documents"],
    )
    print("Purchasing/stores: 480 histories, 885 PDFs, 13 registers, and 402 payments verified")
