"""Validate issue 124 maintenance, engineering and contractor histories."""
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import yaml


SNAPSHOT = "2026-09-16T08:30:00-04:00"
STORY = "maintenance-engineering"


def require(value, message):
    if not value:
        raise ValueError(message)


def archive_tables(root):
    with zipfile.ZipFile(root / "documents/maintenance-engineering-records.zip") as archive:
        return {
            Path(name).stem: list(csv.DictReader(io.StringIO(archive.read(name).decode())))
            for name in archive.namelist()
            if name.startswith("registers/")
        }


def check_maintenance_engineering(root, workforce, mail, docs, events):
    manifest = yaml.safe_load((root / "authoring/maintenance-engineering.yaml").read_text())
    require(manifest["snapshot"] == SNAPSHOT, "maintenance snapshot drift")
    people = {person["key"]: person for person in workforce}
    staff = {key for key, person in people.items() if person["department"] == "Maintenance and engineering"}
    require(len(staff) == 48 and set(manifest["staff"]) == staff, "maintenance staff coverage")

    documents = {d["id"]: d for d in docs if d.get("story") == STORY}
    messages = {m["id"]: m for m in mail if m.get("story") == STORY}
    calendars = {e["id"]: e for e in events if e["id"].startswith("maintenance-contractor-")}
    counts = manifest["counts"]
    require(len(documents) == counts["documents"] == 871, "maintenance document inventory")
    require(len(messages) == counts["messages"] == 432, "maintenance message inventory")
    require(len(calendars) == counts["calendars"] == 24, "maintenance calendar inventory")
    coverage = json.loads((root / "story-coverage.json").read_text())["messages"]
    require(sum(len(coverage[key]["retained"].get("arwc", [])) for key in messages) ==
            counts["retained_copies"] == 936, "maintenance retained-copy count")
    require(len({m["body"] for m in messages.values()}) >= 380, "maintenance correspondence is overly repetitive")
    require(staff <= {m["from"] for m in messages.values()}, "maintenance colleague voice coverage")

    assets = {a["asset_id"]: a for a in manifest["assets"]}
    work_orders = {w["work_order"]: w for w in manifest["work_orders"]}
    require(len(assets) == counts["assets"] == 72, "maintenance asset inventory")
    require(len(work_orders) == counts["work_orders"] == 720, "maintenance work-order inventory")
    require(len({a["site_id"] for a in assets.values()}) >= 10 and
            sum(a["site_id"] == "ARWC-CR" for a in assets.values()) < len(assets) // 10,
            "maintenance site distribution")
    require(Counter(w["status"] for w in work_orders.values()) ==
            Counter({"completed": 568, "waiting parts": 76, "deferred": 40, "planned": 36}),
            "maintenance status distribution")
    require({w["assignee"] for w in work_orders.values()} == staff, "work orders do not cover all maintenance staff")
    for work in work_orders.values():
        opened = datetime.fromisoformat(work["opened_at"])
        planned = datetime.fromisoformat(work["planned_for"])
        updated = datetime.fromisoformat(work["updated_at"])
        require(opened <= planned <= updated <= datetime.fromisoformat(SNAPSHOT), "work-order chronology")
        require(work["asset_id"] in assets and work["document"] in documents, "work-order asset/document join")
        require(work["planner"] in staff and work["assignee"] in staff, "work-order personnel join")
        person = people[work["assignee"]]
        require(max(person["start_date"], person["effective_date"]) <= opened.date().isoformat(),
                "work order predates current assignment")
        record = documents[work["document"]]
        require(work["work_order"] in record["text"] and work["asset_id"] in record["text"] and
                work["status"] in record["text"] and record["audience"] == "restricted",
                "work-order readback or audience")

    with zipfile.ZipFile(root / "documents/field-operations-records.zip") as archive:
        upstream = {row["request_id"]: row for row in
                    csv.DictReader(io.StringIO(archive.read("maintenance.csv").decode()))}
    links = manifest["operations_request_links"]
    require(len(links) == len(upstream) == 24 and {link["request"] for link in links} == set(upstream),
            "operations request coverage")
    for link in links:
        work = work_orders[link["work_order"]]
        source = upstream[link["request"]]
        require(work["source_request"] == source["request_id"] and work["asset_id"] == source["asset_id"] and
                work["opened_at"] >= source["received_at"] and link["source"] == source["source_id"],
                "operations request/work-order join")

    tables = archive_tables(root)
    require(set(tables) == set(manifest["tables"]), "maintenance table inventory")
    with zipfile.ZipFile(root / "documents/maintenance-engineering-records.zip") as archive:
        require(len(archive.namelist()) == counts["archive_members"] == 23, "maintenance archive member inventory")
        for name, info in manifest["tables"].items():
            raw = archive.read(info["member"])
            rows = tables[name]
            require(len(rows) == info["rows"] and len({r[info["primary_key"]] for r in rows}) == len(rows),
                    "maintenance table primary key")
            require(hashlib.sha256(raw).hexdigest() == info["sha256"] ==
                    documents[info["document"]]["binary_sha256"], "maintenance table digest")
            require(documents[info["document"]]["content_encoding"] == "gzip", "maintenance table encoding")
        for drawing in manifest["drawings"]:
            doc = documents["me-drawing-" + f"{1 + next(i for i,p in enumerate(manifest['projects']) if p['id'] == drawing['project']):02d}-" + drawing["revision"].lower()]
            raw = archive.read(doc["member"])
            ET.fromstring(raw)
            require(hashlib.sha256(raw).hexdigest() == doc["binary_sha256"] and
                    ("NOT APPROVED FOR WORK" not in raw.decode()) == (drawing["state"] == "approved"),
                    "drawing bytes or revision watermark")

    drawing_groups = {}
    for drawing in manifest["drawings"]:
        drawing_groups.setdefault(drawing["project"], []).append(drawing)
    require(len(drawing_groups) == counts["projects"] == 4, "capital project inventory")
    for project in manifest["projects"]:
        drawings = sorted(drawing_groups[project["id"]], key=lambda d: d["issued_at"])
        require([d["revision"] for d in drawings] == ["P1", "P2", "A1"] and
                [d["state"] for d in drawings] == ["working", "working", "approved"] and
                [d["effective_for_work"] for d in drawings] == ["no", "no", "yes"],
                "drawing revision authority")
        commissioning = next(c for c in manifest["commissioning"] if c["project"] == project["id"])
        handover = next(h for h in manifest["handovers"] if h["project"] == project["id"])
        require(drawings[-1]["drawing_ref"] == commissioning["drawing"] == handover["approved_drawing"] and
                datetime.fromisoformat(drawings[-1]["issued_at"]) < datetime.fromisoformat(commissioning["completed_at"]) <
                datetime.fromisoformat(handover["handed_over_at"]), "project revision/commissioning/handover chronology")
        require(Decimal(project["accepted"]) <= Decimal(project["estimate"]), "project estimate acceptance")

    contractor_jobs = manifest["contractor_jobs"]
    require(len(contractor_jobs) == counts["contractor_jobs"] == 24, "contractor job inventory")
    purchases = {r["purchase_order"]: r for r in tables["purchase-orders"]}
    appointments = {r["purchase_order"]: r for r in tables["contractor-appointments"]}
    service = {r["service_report"]: r for r in tables["contractor-service-reports"]}
    receipts = {r["purchase_order"]: r for r in tables["service-receipts"]}
    for index, job in enumerate(contractor_jobs, 1):
        purchase = purchases[job["purchase_order"]]
        appointment = appointments[job["purchase_order"]]
        report = service[job["service_report"]]
        receipt = receipts[job["purchase_order"]]
        require(datetime.fromisoformat(purchase["accepted_at"]) < datetime.fromisoformat(appointment["start"]) <
                datetime.fromisoformat(appointment["end"]) < datetime.fromisoformat(report["reported_at"]) <
                datetime.fromisoformat(receipt["received_at"]), "contractor acceptance/service chronology")
        require(purchase["amount_usd"] == receipt["amount_usd"] == job["amount_usd"], "contractor amount join")
        require((purchase["supplier"] != "veybridge" or purchase["amount_usd"] == "1240.00") and
                Decimal(purchase["amount_usd"]) <= Decimal("18000.00"), "supplier agreement amount")
        event = calendars[f"maintenance-contractor-{index:03d}"]
        require(event["start"] == appointment["start"] and event["end"] == appointment["end"] and
                event["status"] == "CONFIRMED" and event["created_at"] > purchase["accepted_at"],
                "contractor calendar join")
        root = messages[f"me-contractor-{index:03d}-1"]
        finish = messages[f"me-contractor-{index:03d}-4"]
        require(root["date"] > purchase["accepted_at"] and finish["date"] > receipt["received_at"] and
                f"me-contractor-order-{index:03d}" in root["attachments"] and
                finish["attachments"] == [f"me-contractor-receipt-{index:03d}"],
                "contractor correspondence/document join")

    visible = "\n".join(d.get("text", "") for d in documents.values())
    require(all(term not in visible.lower() for term in ("cinder typhoon", "challenge-specific", "issue 124")),
            "participant-visible authoring leakage")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_maintenance_engineering(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "mail-maintenance-engineering.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-maintenance-engineering.yaml").read_text())["documents"],
        yaml.safe_load((author / "calendars-maintenance-engineering.yaml").read_text())["events"],
    )
    print("Maintenance: 720 work orders, 48 staff, 24 contractor jobs and four project histories verified")
