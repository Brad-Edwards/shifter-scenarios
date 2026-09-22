#!/usr/bin/env python3
"""Validate issue 127 retail bills, payments, cases, and contact histories."""
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml
from pypdf import PdfReader

SNAPSHOT = "2026-09-16T08:30:00-04:00"
STORY = "retail-billing"
CUSTOMER_SERVICE = {"rosa"} | {f"awm{n}" for n in range(182, 197)}
ACCOUNTS = {f"awm{n}" for n in range(197, 205)}


def require(value, message):
    if not value:
        raise ValueError("Retail billing: " + message)


def source_tables(root):
    with zipfile.ZipFile(root / "documents/service-account-records.zip") as archive:
        return {
            Path(name).stem: list(csv.DictReader(io.StringIO(archive.read(name).decode())))
            for name in archive.namelist()
        }


def retail_tables(root, manifest):
    with zipfile.ZipFile(root / "documents/retail-billing-records.zip") as archive:
        return {
            name: list(csv.DictReader(io.StringIO(archive.read(info["member"]).decode())))
            for name, info in manifest["tables"].items()
        }


def check_retail_billing(root, workforce, identity, mail, docs):
    manifest = yaml.safe_load((root / "authoring/retail-billing.yaml").read_text())
    require(manifest["snapshot"] == SNAPSHOT, "snapshot drift")
    require(manifest["required_base"] == {
        "repository_commit": "7bc1976",
        "accepted_service_accounts_commit": "d8c3d05",
        "accepted_purchasing_stores_commit": "46b6980",
    }, "accepted-base drift")
    require(manifest["native_sources"] == {
        "mail": "cinder-typhoon/narrative/arwc-mail",
        "documents": "cinder-typhoon/narrative/arwc-documents",
        "logical_owner": "a-corporate.a-business",
    }, "native source or owner drift")

    counts = manifest["counts"]
    require(counts == {
        "bills": 50102, "bill_lines": 101641, "deliveries": 50102,
        "payments": 31920, "payment_allocations": 31920,
        "adjustments": 500, "balances": 50100, "cases": 800,
        "case_events": 6100, "appointments": 200, "collections": 300,
        "arrangements": 200, "messages": 7600, "notices": 1500,
        "retained_copies": 9100, "documents": 839,
        "representative_pdfs": 24, "archive_members": 39,
    }, "declared count drift")
    require(manifest["volume_adjustment"] == {
        "provisional_bills": 61500, "settled_authoritative_invoices": 50102,
        "difference": -11398,
        "reason": "Accepted account population and existing invoice authority replace the provisional dwelling-level estimate.",
    }, "bill-volume adjustment is not explicit")

    source = source_tables(root)
    data = retail_tables(root, manifest)
    people = identity["people"] | identity["correspondents"] | {p["key"]: p for p in workforce}
    contacts = {row["account_id"]: row for row in source["contacts"]}
    accounts = {row["account_id"]: row for row in source["accounts"]}
    invoices = {row["invoice_id"]: row for row in source["invoices"]}
    lines = {row["line_id"]: row for row in source["invoice-lines"]}
    readings = {row["reading_id"]: row for row in source["readings"]}
    preferences = {row["account_id"]: row for row in source["preferences"]}
    changes = defaultdict(list)
    for row in source["changes"]:
        changes[row["account_id"]].append(row)

    messages = {message["id"]: message for message in mail if message.get("story") == STORY}
    documents = {document["id"]: document for document in docs if document.get("story") == STORY}
    require(len(messages) == counts["messages"] and len(documents) == counts["documents"],
            "message or document inventory")
    require(len({m["body"] for m in messages.values()}) == len(messages),
            "duplicate correspondence body")
    require(all(document["audience"] == "restricted"
                and set(document["reader_keys"]) == CUSTOMER_SERVICE | ACCOUNTS
                for document in documents.values()), "document reader boundary")

    with zipfile.ZipFile(root / "documents/retail-billing-records.zip") as archive:
        require(archive.testzip() is None and len(archive.namelist()) == counts["archive_members"],
                "archive inventory or corruption")
        expected_members = {info["member"] for info in manifest["tables"].values()}
        expected_members.add(manifest["rendered_bills"]["member"])
        expected_members |= {item["member"] for item in manifest["representative_pdfs"]}
        require(set(archive.namelist()) == expected_members, "unbound archive member")
        for name, info in manifest["tables"].items():
            raw = archive.read(info["member"])
            rows = data[name]
            require(hashlib.sha256(raw).hexdigest() == info["sha256"]
                    and info["rows"] == len(rows)
                    and len({row[info["primary_key"]] for row in rows}) == len(rows),
                    f"{name} rows, key, or digest")
            document = documents[info["document"]]
            require(document["binary_sha256"] == info["sha256"]
                    and document["content_encoding"] == "gzip"
                    and document["member"] == info["member"], f"{name} source binding")

        rendered_info = manifest["rendered_bills"]
        rendered_raw = archive.read(rendered_info["member"])
        require(hashlib.sha256(rendered_raw).hexdigest() == rendered_info["sha256"]
                == documents[rendered_info["document"]]["binary_sha256"],
                "readable bill source digest")
        rendered = [json.loads(line) for line in rendered_raw.decode().splitlines()]
        require(len(rendered) == rendered_info["rows"] == counts["bills"]
                and len({row["invoice_id"] for row in rendered}) == len(rendered),
                "readable bill inventory")
        for row in rendered:
            invoice = invoices[row["invoice_id"]]
            require(row["account_id"] == invoice["account_id"]
                    and row["invoice_id"] in row["text"]
                    and invoice["period_id"] in row["text"]
                    and f"Bill total: USD {invoice['total_usd']}" in row["text"]
                    and "drinking water only" in row["text"]
                    and "Wastewater service is outside ARWC's scope." in row["text"],
                    f"readable bill authority: {row['invoice_id']}")

        require(len(manifest["representative_pdfs"]) == counts["representative_pdfs"],
                "representative PDF manifest")
        for item in manifest["representative_pdfs"]:
            raw = archive.read(item["member"])
            require(raw.startswith(b"%PDF-") and hashlib.sha256(raw).hexdigest() == item["sha256"],
                    f"PDF bytes: {item['invoice_id']}")
            pdf = PdfReader(io.BytesIO(raw), strict=True)
            text = "\n".join(page.extract_text() for page in pdf.pages).rstrip() + "\n"
            document = next(d for d in documents.values()
                            if d.get("member") == item["member"])
            require(not pdf.is_encrypted and len(pdf.pages) == 1 and text == document["text"],
                    f"PDF readability: {item['invoice_id']}")
            require(pdf.metadata.creation_date.date().isoformat() == invoices[item["invoice_id"]]["issued_on"],
                    f"PDF creation date: {item['invoice_id']}")

    bills = {row["invoice_id"]: row for row in data["bills"]}
    require(len(bills) == counts["bills"] == len(invoices), "bill/invoice one-to-one join")
    for invoice_id, invoice in invoices.items():
        bill = bills[invoice_id]
        require(bill["account_id"] == invoice["account_id"]
                and bill["period_id"] == invoice["period_id"]
                and bill["tariff_id"] == invoice["tariff_id"]
                and bill["issued_on"] == invoice["issued_on"]
                and bill["due_on"] == invoice["due_on"]
                and bill["total_usd"] == invoice["total_usd"],
                f"bill source projection: {invoice_id}")

    bill_lines = {row["line_id"]: row for row in data["bill-lines"]}
    require(len(bill_lines) == counts["bill_lines"] == len(lines), "bill-line inventory")
    for line_id, source_line in lines.items():
        projected = bill_lines[line_id]
        require(projected["source_line_id"] == line_id
                and all(projected[key] == source_line[key] for key in source_line),
                f"bill line source projection: {line_id}")
        require(Decimal(projected["quantity"]) * Decimal(projected["unit_price_usd"])
                == Decimal(projected["amount_usd"]), f"bill line arithmetic: {line_id}")
        if projected["charge"] == "usage":
            require(projected["start_reading_id"] in readings and projected["end_reading_id"] in readings,
                    f"bill reading join: {line_id}")

    # Rebuild the issue-date preference from the accepted current preference and
    # later changes; every invoice is dispatched once, not restated as mail.
    deliveries = {row["invoice_id"]: row for row in data["deliveries"]}
    require(len(deliveries) == counts["deliveries"] == len(invoices), "delivery inventory")
    for invoice_id, invoice in invoices.items():
        aid = invoice["account_id"]
        channel = preferences[aid]["bill_channel"]
        for change in sorted(changes[aid], key=lambda row: row["effective_at"], reverse=True):
            if (change["entity"] == "preferences" and change["field"] == "bill_channel"
                    and change["effective_at"][:10] > invoice["issued_on"]):
                channel = change["before"]
        delivery = deliveries[invoice_id]
        expected_destination = contacts[aid]["email"] if channel == "email" else preferences[aid]["postal_address"]
        require(delivery["account_id"] == aid and delivery["channel"] == channel
                and delivery["destination"] == expected_destination,
                f"bill delivery preference: {invoice_id}")
    require(Counter(row["channel"] for row in deliveries.values()) == Counter(email=40074, post=10028),
            "electronic/postal delivery mix")
    require(not any(message["id"].startswith("rb-bill-delivery") for message in messages.values()),
            "every bill was inflated into mailbox mail")

    payments = {row["payment_id"]: row for row in data["payments"]}
    allocations = data["payment-allocations"]
    allocated_payment = defaultdict(Decimal)
    allocated_invoice = defaultdict(Decimal)
    paid_account = defaultdict(Decimal)
    for row in allocations:
        require(row["payment_id"] in payments and row["invoice_id"] in invoices
                and payments[row["payment_id"]]["account_id"] == invoices[row["invoice_id"]]["account_id"],
                f"payment allocation join: {row['allocation_id']}")
        value = Decimal(row["amount_usd"])
        allocated_payment[row["payment_id"]] += value
        allocated_invoice[row["invoice_id"]] += value
    for payment_id, payment in payments.items():
        require(payment["status"] == "accepted" and Decimal(payment["amount_usd"]) > 0
                and datetime.fromisoformat(payment["received_at"]) <= datetime.fromisoformat(SNAPSHOT)
                and allocated_payment[payment_id] == Decimal(payment["amount_usd"]),
                f"payment state or allocation: {payment_id}")
        paid_account[payment["account_id"]] += Decimal(payment["amount_usd"])

    adjustments = {row["adjustment_id"]: row for row in data["adjustments"]}
    adjusted_account = defaultdict(Decimal)
    adjusted_at = {}
    for adjustment_id, row in adjustments.items():
        amount = Decimal(row["amount_usd"])
        signed = Decimal(row["signed_amount_usd"])
        require(row["account_id"] in accounts and row["invoice_id"] in invoices
                and invoices[row["invoice_id"]]["account_id"] == row["account_id"]
                and amount > 0 and signed == (amount if row["kind"] == "debit" else -amount)
                and row["kind"] in {"credit", "debit"}, f"adjustment authority: {adjustment_id}")
        adjusted_account[row["account_id"]] += signed
        adjusted_at[row["account_id"]] = max(adjusted_at.get(row["account_id"], ""), row["posted_at"])

    require(all(payment["account_id"] not in adjusted_at
                or datetime.fromisoformat(payment["received_at"]) >= datetime.fromisoformat(adjusted_at[payment["account_id"]])
                for payment in payments.values()), "payment predates the adjustment included in its balance")

    opening = {row["account_id"]: row for row in source["opening-balances"]}
    balances = {row["account_id"]: row for row in data["balances"]}
    require(len(balances) == counts["balances"] == len(accounts), "balance inventory")
    for aid, balance in balances.items():
        expected = (Decimal(opening[aid]["net_balance_usd"])
                    + adjusted_account[aid] - paid_account[aid])
        require(Decimal(balance["balance_usd"]) == expected
                and Decimal(balance["adjustments_usd"]) == adjusted_account[aid]
                and Decimal(balance["post_opening_payments_usd"]) == paid_account[aid]
                and Decimal(balance["overdue_usd"]) == max(Decimal(0), expected),
                f"balance reconciliation: {aid}")

    cases = {row["case_id"]: row for row in data["cases"]}
    case_events = data["case-events"]
    appointments_by_id = {row["appointment_id"]: row for row in data["appointments"]}
    arrangements_by_id = {row["arrangement_id"]: row for row in data["arrangements"]}
    require(len(cases) == counts["cases"]
            and Counter(int(row["message_count"]) for row in cases.values()) == Counter({4: 100, 6: 200, 8: 250, 10: 250})
            and sum(int(row["message_count"]) for row in cases.values()) == counts["case_events"],
            "case inventory or substantive thread lengths")
    require(all(not row["case_id"] or (row["case_id"] in cases
                and cases[row["case_id"]]["adjustment_id"] == adjustment_id)
                for adjustment_id, row in adjustments.items()),
            "adjustment points to an unrelated case")
    require(all(not row["case_id"] or (row["case_id"] in cases
                and cases[row["case_id"]]["appointment_id"] == appointment_id)
                for appointment_id, row in appointments_by_id.items()),
            "appointment points to an unrelated case")
    require(len(case_events) == counts["case_events"]
            and Counter(row["event"] for row in case_events) == Counter(customer_message=3050, staff_reply=3050),
            "case-event inventory")
    expected_case_messages = set()
    for item in manifest["cases"]:
        case = cases[item["case_id"]]
        require(item["account_id"] == case["account_id"] and item["customer_key"] in people
                and people[item["customer_key"]]["email"] == contacts[case["account_id"]]["email"]
                and item["owner_key"] in CUSTOMER_SERVICE,
                f"case account or role: {case['case_id']}")
        turns = [messages[mid] for mid in item["messages"]]
        require(len(turns) == int(case["message_count"])
                and [turn["from"] for turn in turns] == [item["customer_key"], item["owner_key"]] * (len(turns)//2)
                and all(turns[n]["reply_to"] == turns[n-1]["id"]
                        and datetime.fromisoformat(turns[n-1]["date"]) < datetime.fromisoformat(turns[n]["date"])
                        for n in range(1, len(turns))), f"case thread: {case['case_id']}")
        require(turns[0]["date"] == case["opened_at"] and turns[-1]["date"] == case["closed_at"],
                f"case chronology: {case['case_id']}")
        document = documents[item["document"]]
        require(case["account_id"] in document["text"] and case["invoice_id"] in document["text"]
                and f"Outcome: {case['outcome']}" in document["text"]
                and document["published_at"] == case["closed_at"], f"case readback: {case['case_id']}")
        if case["appointment_id"]:
            require(case["appointment_id"] in appointments_by_id
                    and appointments_by_id[case["appointment_id"]]["account_id"] == case["account_id"],
                    f"cross-account appointment in case: {case['case_id']}")
        if case["adjustment_id"]:
            require(case["adjustment_id"] in adjustments
                    and adjustments[case["adjustment_id"]]["account_id"] == case["account_id"],
                    f"cross-account adjustment in case: {case['case_id']}")
        if case["arrangement_id"]:
            require(case["arrangement_id"] in arrangements_by_id
                    and arrangements_by_id[case["arrangement_id"]]["account_id"] == case["account_id"],
                    f"cross-account arrangement in case: {case['case_id']}")
        if case["category"] == "payment_allocation":
            mentioned = [payment_id for payment_id in payments if payment_id in document["text"]]
            require((len(mentioned) == 1 and payments[mentioned[0]]["account_id"] == case["account_id"])
                    or (not mentioned and "No accepted post-opening payment" in document["text"]),
                    f"cross-account payment in case: {case['case_id']}")
        expected_case_messages.update(item["messages"])
    require(len(expected_case_messages) == 6100, "case correspondence count")
    normalized_case_bodies = []
    for message_id in expected_case_messages:
        body = messages[message_id]["body"].lower()
        body = re.sub(r"\b(?:arwc|a-b)-[a-z0-9-]+\b", "<ref>", body)
        body = re.sub(r"\b\d+(?:[.,:]\d+)*\b", "<n>", body)
        normalized_case_bodies.append(" ".join(body.split()))
    normalized_counts = Counter(normalized_case_bodies)
    require(len(normalized_counts) >= 1500 and max(normalized_counts.values()) <= 40,
            "case prose collapses to repeated normalized templates")
    require("belvarn follow-up" in messages["rb-case-0001-01"]["body"].lower()
            and "both supply feeds" in messages["rb-case-0001-01"]["body"]
            and "talvern arrangement" in messages["rb-case-0002-01"]["body"].lower()
            and "members' other water arrangements" in messages["rb-case-0002-01"]["body"],
            "named Belvarn or Talvern continuity")
    require(sum("a-billing-explanation" in message.get("attachments", []) for message in messages.values()) == 5,
            "accepted clearer billing explanation not reused")

    notices = {row["message_id"]: row for row in data["notices"]}
    require(len(notices) == counts["notices"] == len(manifest["notices"])
            and Counter(row["kind"] for row in notices.values()) == Counter({
                "payment-confirmation": 400, "balance-reminder": 300,
                "arrangement-confirmation": 200, "appointment-confirmation": 200,
                "adjustment-confirmation": 200, "paper-copy-dispatch": 95,
                "explanation-follow-up": 5,
                "case-receipt": 100,
            }), "notice inventory")
    for message_id, notice in notices.items():
        message = messages[message_id]
        aid = notice["account_id"]
        require(message["from"] == "arwc_accounts" and message["to"][-1] == "awm198"
                and people[message["to"][0]]["email"] == contacts[aid]["email"]
                and notice["related_reference"] in message["body"],
                f"notice recipient or reference: {message_id}")
    require(expected_case_messages | set(notices) == set(messages), "unjoined retail correspondence")

    appointments = {row["appointment_id"]: row for row in data["appointments"]}
    require(len(appointments) == counts["appointments"]
            and all(row["account_id"] in accounts and row["service_point_id"]
                    and row["contact_window"] == preferences[row["account_id"]]["notification_window"]
                    and datetime.fromisoformat(row["requested_at"]) < datetime.fromisoformat(row["scheduled_for"])
                    for row in appointments.values()), "appointment history")
    collections = {row["collection_id"]: row for row in data["collections"]}
    arrangements = {row["arrangement_id"]: row for row in data["arrangements"]}
    require(len(collections) == counts["collections"] and len(arrangements) == counts["arrangements"],
            "collections or arrangement inventory")
    for arrangement_id, row in arrangements.items():
        require(row["collection_id"] in collections
                and collections[row["collection_id"]]["account_id"] == row["account_id"]
                and sum(Decimal(row[f"installment_{n}_usd"]) for n in range(1, 4)) == Decimal(row["total_usd"])
                == Decimal(balances[row["account_id"]]["overdue_usd"]),
                f"arrangement arithmetic: {arrangement_id}")

    require(len(data["contact-history"]) == counts["messages"]
            and {row["message_id"] for row in data["contact-history"]} == set(messages),
            "contact-history coverage")
    visible = "\n".join(message["subject"] + "\n" + message["body"] for message in messages.values())
    visible += "\n" + "\n".join(document.get("text", "") for document in documents.values())
    require(all(term not in visible.lower() for term in
                ("cinder typhoon", "challenge-specific", "issue 127", "author-only", "openrae", "shifter-scenarios")),
            "participant-visible authoring leakage")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_retail_billing(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "people.yaml").read_text()),
        yaml.safe_load((author / "mail-retail-billing.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-retail-billing.yaml").read_text())["documents"],
    )
    print("Retail billing: 50,102 bills, 31,920 payments, 800 cases, and 7,600 messages verified")
