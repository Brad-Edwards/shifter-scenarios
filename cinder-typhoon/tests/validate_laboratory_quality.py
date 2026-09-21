#!/usr/bin/env python3
"""Validate issue 125 laboratory, quality, and routine reporting histories."""
from collections import Counter, defaultdict
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
STORY = "laboratory-quality"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def require(value, message):
    if not value:
        raise ValueError("Laboratory quality: " + message)


def archive_tables(root):
    with zipfile.ZipFile(root / "documents/laboratory-quality-records.zip") as archive:
        return {
            Path(name).stem: list(csv.DictReader(io.StringIO(archive.read(name).decode())))
            for name in archive.namelist()
            if name.startswith("registers/")
        }


def workbook_sheets(raw):
    """Read sheet names, row counts, and formula/cached-value cells from Office XML."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.testzip() is None, "corrupt workbook archive")
        require("[Content_Types].xml" in archive.namelist(), "workbook lacks Office content types")
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        result = {}
        for number, sheet in enumerate(book.find("s:sheets", NS), 1):
            require(sheet.get("state", "visible") == "visible", "hidden workbook sheet")
            tree = ET.fromstring(archive.read(f"xl/worksheets/sheet{number}.xml"))
            cells = {}
            for cell in tree.findall(".//s:c", NS):
                formula = cell.find("s:f", NS)
                value = cell.find("s:v", NS)
                inline = cell.find("s:is", NS)
                text = "".join(inline.itertext()) if inline is not None else value.text if value is not None else ""
                cells[cell.get("r")] = (text, formula.text if formula is not None else None)
            result[sheet.get("name")] = cells
        return result


def check_laboratory_quality(root, workforce, mail, docs, events):
    manifest = yaml.safe_load((root / "authoring/laboratory-quality.yaml").read_text())
    require(manifest["snapshot"] == SNAPSHOT, "snapshot drift")
    people = {person["key"]: person for person in workforce}
    expected_staff = {
        key for key, person in people.items()
        if person["department"] == "Planning, quality, and compliance" and person["team"] != "Resource planning"
    }
    require(len(expected_staff) == 24 and set(manifest["staff"]) == expected_staff,
            "laboratory, quality, and reporting staff coverage")

    documents = {document["id"]: document for document in docs if document.get("story") == STORY}
    messages = {message["id"]: message for message in mail if message.get("story") == STORY}
    calendars = {event["id"]: event for event in events if event["id"].startswith("lq-")}
    counts = manifest["counts"]
    require(len(documents) == counts["documents"] == 106, "document inventory")
    require(len(messages) == counts["messages"] == 318, "message inventory")
    require(len(calendars) == counts["calendars"] == 34, "calendar inventory")
    coverage = json.loads((root / "story-coverage.json").read_text())["messages"]
    retained = sum(len(coverage[key]["retained"].get("arwc", [])) for key in messages)
    require(retained == counts["retained_copies"] == 992, "retained-copy inventory")
    require(len({message["body"] for message in messages.values()}) >= 285,
            "correspondence is overly repetitive")
    require(expected_staff <= {message["from"] for message in messages.values()},
            "a laboratory, quality, or reporting colleague has no authored voice")

    samples = {sample["sample_id"]: sample for sample in manifest["sample_histories"]}
    require(len(samples) == counts["sample_histories"] == 960, "sample-history inventory")
    require(Counter(sample["disposition"] for sample in samples.values()) == Counter({
        "accepted": 912, "accepted after repeat": 36, "resample requested": 12,
    }), "sample disposition distribution")
    require(sum(sample["site_id"] == "ARWC-CR" for sample in samples.values()) < len(samples) // 8,
            "Cairn Reach is overrepresented")

    tables = archive_tables(root)
    require(set(tables) == set(manifest["tables"]), "table inventory")
    with zipfile.ZipFile(root / "documents/laboratory-quality-records.zip") as archive:
        require(len(archive.namelist()) == counts["archive_members"] == 18, "archive member inventory")
        for name, info in manifest["tables"].items():
            raw = archive.read(info["member"])
            rows = tables[name]
            require(len(rows) == info["rows"] and len({row[info["primary_key"]] for row in rows}) == len(rows),
                    f"{name} primary-key or row-count drift")
            document = documents[info["document"]]
            require(hashlib.sha256(raw).hexdigest() == info["sha256"] == document["binary_sha256"],
                    f"{name} digest drift")
            require(document.get("content_encoding") == "gzip", f"{name} source encoding")

        workbook_docs = [documents[key] for key in manifest["workbooks"]]
        require(len(workbook_docs) == counts["workbooks"] == 9, "monthly workbook inventory")
        sample_months = Counter(sample["collected_at"][:7] for sample in samples.values())
        result_months = Counter()
        for result in tables["results"]:
            result_months[samples[result["sample_id"]]["collected_at"][:7]] += 1
        for document in workbook_docs:
            raw = archive.read(document["member"])
            require(hashlib.sha256(raw).hexdigest() == document["binary_sha256"], "workbook digest drift")
            sheets = workbook_sheets(raw)
            require(set(sheets) == {"Summary", "Samples", "Results"}, "workbook sheet inventory")
            month = document["id"].removeprefix("lq-workbook-")
            summary = sheets["Summary"]
            require(summary["B8"] == (str(sample_months[month]), f"COUNTA(Samples!A2:A{sample_months[month] + 1})"),
                    "workbook sample formula or cached value")
            require(summary["B9"] == (str(result_months[month]), f"COUNTA(Results!A2:A{result_months[month] + 1})"),
                    "workbook result formula or cached value")
            require(len(sheets["Samples"]) == 7 * (sample_months[month] + 1), "workbook sample row width/count")

    schedules = {row["sample_id"]: row for row in tables["sampling-schedule"]}
    receipts = {row["sample_id"]: row for row in tables["receipts"]}
    reviews = {row["sample_id"]: row for row in tables["reviews"]}
    results = defaultdict(list)
    for row in tables["results"]:
        results[row["sample_id"]].append(row)
    require(set(samples) == set(schedules) == set(receipts) == set(reviews) == set(results),
            "sample-chain coverage")
    specification = {item["code"]: item for item in manifest["specification"]["parameters"]}
    require(manifest["specification"]["scope"].startswith("fictional internal"), "specification scope")
    require(len(tables["results"]) == counts["results"] == 2916, "result inventory")
    for sample_id, sample in samples.items():
        schedule = schedules[sample_id]
        receipt = receipts[sample_id]
        review = reviews[sample_id]
        collected = datetime.fromisoformat(sample["collected_at"])
        received = datetime.fromisoformat(receipt["received_at"])
        reviewed = datetime.fromisoformat(review["reviewed_at"])
        require(datetime.fromisoformat(schedule["planned_for"]) == collected <= received <= reviewed <= datetime.fromisoformat(SNAPSHOT),
                "sample chronology")
        require(schedule["asset_id"] == sample["asset_id"] and receipt["received_by"] == sample["analyst"]
                and review["reviewer"] == sample["reviewer"] and review["disposition"] == sample["disposition"],
                "sample identity, analyst, reviewer, or disposition join")
        rows = results[sample_id]
        require({row["parameter"] for row in rows} == set(specification), "parameter coverage")
        for row in rows:
            parameter = specification[row["parameter"]]
            require(row["unit"] == parameter["unit"], "parameter unit drift")
            in_band = Decimal(str(parameter["low"])) <= Decimal(row["value"]) <= Decimal(str(parameter["high"]))
            require((row["within_internal_band"] == "yes") == in_band, "internal-band calculation")
        if sample["disposition"] == "accepted":
            require(len(rows) == 3 and all(row["accepted_for_review"] == "yes" for row in rows),
                    "ordinary accepted result shape")
        elif sample["disposition"] == "accepted after repeat":
            require(len(rows) == 4 and sum(row["run"] == "preliminary" for row in rows) == 1
                    and sum(row["accepted_for_review"] == "no" for row in rows) == 1,
                    "repeat result history")
        else:
            require(len(rows) == 3 and all(row["accepted_for_review"] == "no" for row in rows),
                    "open recollection result history")

    with zipfile.ZipFile(root / "documents/field-operations-records.zip") as archive:
        upstream = {}
        for name in ("samples-P.csv", "samples-R.csv"):
            upstream.update({row["sample_id"]: row for row in csv.DictReader(io.StringIO(archive.read(name).decode()))})
    linked = {sample_id: sample for sample_id, sample in samples.items() if sample["source_visit"]}
    require(len(upstream) == len(linked) == 60 and set(upstream) == set(linked), "field sample coverage")
    for sample_id, source in upstream.items():
        sample = linked[sample_id]
        require(sample["source_visit"] == source["visit_id"] and sample["asset_id"] == source["asset_id"]
                and sample["collected_at"] == source["collected_at"] and sample["received_at"] == source["handed_over_at"]
                and sample["analyst"] == source["received_by"] and receipts[sample_id]["seal_status"] == source["seal_status"],
                "field-operation sample join")

    reports = manifest["reports"]
    require(len(reports) == counts["weekly_reports"] == 36, "weekly report inventory")
    report_samples = [sample_id for report in reports for sample_id in report["samples"]]
    require(len(report_samples) == len(set(report_samples)) == len(samples) and set(report_samples) == set(samples),
            "weekly report sample coverage")
    for report in reports:
        document = documents[report["id"]]
        published = datetime.fromisoformat(report["published"])
        require(document["published_at"] == report["published"]
                and all(datetime.fromisoformat(reviews[sample_id]["reviewed_at"]) <= published for sample_id in report["samples"]),
                "report precedes review")
        require(all(sample_id in document["text"] and samples[sample_id]["disposition"] in document["text"]
                    for sample_id in report["samples"]), "report readback")
        require("not external legal requirements" in document["text"], "report lacks internal-specification boundary")

    require(len(manifest["equipment_services"]) == counts["equipment_services"] == 18, "equipment service inventory")
    require(len(manifest["training"]) == counts["training_records"] == 24, "training inventory")
    require(len(manifest["quality_reviews"]) == counts["quality_reviews"] == 8, "quality review inventory")
    require({row["employee"] for row in manifest["training"]} == expected_staff, "training staff coverage")
    require(all(row["status"] == "closed" and "misconduct" not in row["finding"].lower()
                for row in manifest["quality_reviews"]), "routine quality review boundary")
    require(sum(key.startswith("lq-equipment-service-") for key in calendars) == 18
            and sum(key.startswith("lq-training-session-") for key in calendars) == 8
            and sum(key.startswith("lq-quality-review-session-") for key in calendars) == 8,
            "calendar type inventory")
    require(messages["lq-colleague-001-1"]["from"] == "awm150"
            and messages["lq-colleague-001-1"]["reply_to"] == "a-photo-5"
            and "kitchen-window" in messages["lq-colleague-001-1"]["body"],
            "laboratory photography continuity")

    visible = "\n".join(message["subject"] + "\n" + message["body"] for message in messages.values())
    visible += "\n" + "\n".join(document.get("text", "") for document in documents.values())
    require(all(term not in visible.lower() for term in (
        "cinder typhoon", "challenge-specific", "issue 125", "author-only", "openrae", "shifter-scenarios",
    )), "participant-visible authoring leakage")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    workforce = yaml.safe_load((author / "workforce.yaml").read_text())["employees"]
    mail = yaml.safe_load((author / "mail-laboratory-quality.yaml").read_text())["messages"]
    docs = yaml.safe_load((author / "documents-laboratory-quality.yaml").read_text())["documents"]
    events = yaml.safe_load((author / "calendars-laboratory-quality.yaml").read_text())["events"]
    check_laboratory_quality(root, workforce, mail, docs, events)
    print("Laboratory quality: 960 sample histories, 36 reports, nine workbooks, and 24 colleagues verified")
