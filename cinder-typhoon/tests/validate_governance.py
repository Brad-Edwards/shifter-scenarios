"""Reconcile ARWC closes, decision authority and private/public release boundaries."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import io
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
import yaml
from pypdf import PdfReader
from validate_planning import formula_value

ROOT = Path(__file__).resolve().parents[1] / "assets/narrative"
SNAPSHOT = "2026-09-16T08:30:00-04:00"
BOARD = [
    "board_sabine",
    "board_tessa",
    "board_elva",
    "board_tovan",
    "board_iona",
    "board_remy",
]
FINANCE = ["awm216", "awm217", "awm218", "awm219", "luc", "awm197"]
REPORT = ["awm164", "rosa", "awm216", "awm217", "luc", "awm220"]
GOV = BOARD + ["awm216", "awm217", "luc", "awm220", "awm164"]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MODELS = {
    "close": [
        "=Inputs!B2+Inputs!B3-Inputs!B4",
        "=Inputs!B5+Inputs!B6+Inputs!B7-Inputs!B3",
        "=Inputs!B8+Inputs!B9-Inputs!B4",
    ],
    "capital": [
        "=Inputs!B4*Inputs!B6",
        "=Inputs!B2+Inputs!B3+Inputs!B5*Inputs!B6",
        "=B3-B2",
    ],
    "project": ["=Inputs!B2-Inputs!B3"],
    "budget": ["=ROUND(Inputs!B2*Inputs!B3,0)", "=Inputs!B2+B2"],
}


def require(value, message):
    if not value:
        raise ValueError("Governance: " + message)


def load(root, name):
    return yaml.safe_load((root / "authoring" / name).read_text())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def cents(value):
    return int(Decimal(str(value)) * 100)


def usd(value):
    return f"{Decimal(value) / 100:,.2f}"


def money_text(document, expected):
    actual = re.findall(r"-?\d[\d,]*\.\d{2}\b", document["text"])
    require(
        actual == [usd(v) for v in expected],
        "visible financial figures: " + document["id"],
    )


def table(root, archive, member):
    with zipfile.ZipFile(root / "documents" / archive) as z:
        return list(csv.DictReader(io.StringIO(z.read(member).decode())))


class Controls:
    """Independently rebuild from invoice matches, settlements and customer events."""

    def __init__(self, root):
        self.histories = load(root, "purchasing-stores.yaml")["histories"]
        self.by_invoice = {
            h["supplier_invoice"]: h for h in self.histories if h["supplier_invoice"]
        }
        self.ledger = table(
            root, "purchasing-stores-records.zip", "registers/ledger-entries.csv"
        )
        self.payments = table(
            root, "purchasing-stores-records.zip", "registers/payment-records.csv"
        )
        self.accounts = {
            r["account_id"]: r
            for r in table(root, "service-account-records.zip", "accounts.csv")
        }
        self.events = []
        for archive, member, kind, date, amount in [
            (
                "service-account-records.zip",
                "invoices.csv",
                "billing",
                "issued_on",
                "total_usd",
            ),
            (
                "service-account-records.zip",
                "receipts.csv",
                "receipt",
                "received_at",
                "amount_usd",
            ),
            (
                "retail-billing-records.zip",
                "registers/payments.csv",
                "receipt",
                "received_at",
                "amount_usd",
            ),
            (
                "retail-billing-records.zip",
                "registers/adjustments.csv",
                "adjustment",
                "posted_at",
                "signed_amount_usd",
            ),
        ]:
            rows = table(root, archive, member)
            id_key = next(iter(rows[0]))
            require(
                len({r[id_key] for r in rows}) == len(rows),
                "duplicate source transaction",
            )
            self.events += [
                (
                    r[date][:10],
                    self.accounts[r["account_id"]]["home_district"],
                    kind,
                    cents(r[amount]),
                )
                for r in rows
            ]

    def at(self, cutoff):
        values = {d: defaultdict(int) for d in ("PINE", "RIVER")}
        for date, district, kind, amount in self.events:
            if date <= cutoff:
                values[district][kind] += amount
        matched = set()
        for row in self.ledger:
            if row["credit"] == "Accounts payable" and row["posted_at"][:10] <= cutoff:
                values[row["cost_center"].split("-")[0]]["acquisition"] += int(
                    row["amount_cents"]
                )
                matched.add(row["reference"])
        for row in self.payments:
            if row["paid_at"][:10] > cutoff:
                continue
            history = self.by_invoice[row["invoice"]]
            require(
                int(row["amount_cents"]) == history["amount_cents"],
                "source payment join",
            )
            for allocation in history["allocation"]:
                values[allocation["cost_center"].split("-")[0]]["payment"] += (
                    allocation["amount_cents"]
                )
        for h in self.histories:
            allocations = h["allocation"]
            require(
                sum(a["amount_cents"] for a in allocations) == h["amount_cents"],
                "district allocation sum",
            )
            if h["cost_center"] == "REGIONAL-SHARED":
                pine = int(
                    (Decimal(h["amount_cents"]) * Decimal(".55")).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )
                require(
                    allocations
                    == [
                        {"cost_center": "PINE-SHARED", "amount_cents": pine},
                        {
                            "cost_center": "RIVER-SHARED",
                            "amount_cents": h["amount_cents"] - pine,
                        },
                    ],
                    "shared allocation rule",
                )
            for a in allocations:
                district = a["cost_center"].split("-")[0]
                if h["ordered_at"][:10] <= cutoff and (
                    not h["received_at"] or h["received_at"][:10] > cutoff
                ):
                    values[district]["commitments"] += a["amount_cents"]
                if (
                    h["received_at"]
                    and h["received_at"][:10] <= cutoff
                    and h["supplier_invoice"] not in matched
                ):
                    values[district]["grni"] += a["amount_cents"]
        return values

    @staticmethod
    def total(values, key):
        return sum(d[key] for d in values.values())

    def balance(self, values):
        total = lambda key: self.total(values, key)
        return dict(
            cash=50000000
            + total("receipt")
            - total("payment")
            + self.total(self.at("2026-05-31"), "payment"),
            receivables=total("billing") + total("adjustment") - total("receipt"),
            payables=total("acquisition") - total("payment"),
        )


def check_workbook(raw, book, expected_inputs):
    require(
        [Decimal(str(x[1])) for x in book["inputs"]]
        == [Decimal(str(x)) for x in expected_inputs],
        "workbook source inputs",
    )
    require(
        [x[1] for x in book["calculation"]] == MODELS[book["kind"]],
        "workbook calculation model",
    )
    units = {
        "close": ["USD cents"] * 8,
        "capital": [
            "USD cents",
            "USD cents",
            "USD cents/year",
            "USD cents/year",
            "years",
        ],
        "project": ["USD cents"] * 2,
        "budget": ["USD cents", "multiplier"],
    }
    require(
        [x[2] for x in book["inputs"]] == units[book["kind"]]
        and all(x[3] == "USD cents" for x in book["calculation"]),
        "workbook units",
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(
            z.testzip() is None
            and not any("externalLink" in n or "vbaProject" in n for n in z.namelist()),
            "unsafe workbook structure",
        )
        sheets = ET.fromstring(z.read("xl/workbook.xml")).findall(
            "s:sheets/s:sheet", NS
        )
        require(
            [s.get("name") for s in sheets] == ["Read me", "Inputs", "Calculation"]
            and all(s.get("state", "visible") == "visible" for s in sheets),
            "hidden or unexpected worksheet",
        )
        strings = [
            "".join(n.itertext()) for n in ET.fromstring(z.read("xl/sharedStrings.xml"))
        ]
        inputs = ET.fromstring(z.read("xl/worksheets/sheet2.xml"))
        calc = ET.fromstring(z.read("xl/worksheets/sheet3.xml"))
        readme = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

        def cell(sheet, ref):
            node = sheet.find(f'.//s:c[@r="{ref}"]', NS)
            require(
                node is not None and node.find("s:v", NS) is not None,
                "missing Office cell",
            )
            value = node.find("s:v", NS).text
            return strings[int(value)] if node.get("t") == "s" else Decimal(value)

        cells = {}
        require(cell(readme, "B4") == book["scope"], "Office scope differs")
        for i, (label, value, unit, basis) in enumerate(book["inputs"], 2):
            require(
                cell(inputs, f"A{i}") == label
                and cell(inputs, f"B{i}") == Decimal(str(value))
                and cell(inputs, f"C{i}") == unit
                and cell(inputs, f"D{i}") == basis,
                "Office input cell differs",
            )
            cells[f"Inputs!B{i}"] = cell(inputs, f"B{i}")
        for i, (label, formula, value, unit) in enumerate(book["calculation"], 2):
            node = calc.find(f'.//s:c[@r="B{i}"]/s:f', NS)
            require(
                node is not None and "=" + node.text == formula,
                "Office formula differs",
            )
            result = formula_value(formula, cells)
            require(
                cell(calc, f"B{i}") == result == Decimal(str(value)),
                "Office cached result differs",
            )
            require(
                cell(calc, f"A{i}") == label and cell(calc, f"C{i}") == unit,
                "Office result label or unit",
            )
            cells[f"B{i}"] = result
        require(
            len(calc.findall(".//s:f", NS)) == len(book["calculation"]),
            "unexpected Office formula",
        )
        metadata = z.read("docProps/core.xml").decode()
        require("Alterra Regional Water Company" in metadata, "Office author")


def check_governance(root, roster, identity, mail, docs, events, manifest=None):
    f = manifest if manifest is not None else load(root, "governance.yaml")
    d = {x["id"]: x for x in docs if x["id"].startswith("fg-")}
    m = {x["id"]: x for x in mail if x["id"].startswith("fg-")}
    e = {x["id"]: x for x in events if x["id"].startswith("governance-")}
    people = {p["key"]: p for p in roster} | identity["correspondents"]
    require(
        f["snapshot"] == SNAPSHOT
        and f["board_keys"] == BOARD
        and f["finance_readers"] == FINANCE
        and f["reporting_readers"] == REPORT,
        "identity or snapshot contract",
    )
    require(
        f["required_base"]
        == {
            "repository_commit": "643c5cd",
            "accepted_purchasing_commit": "46b6980",
            "accepted_retail_commit": "58c1396",
            "accepted_planning_commit": "76e1a64",
        },
        "accepted base",
    )
    require(
        f["native_sources"]
        == {
            "mail": "cinder-typhoon/narrative/arwc-mail",
            "documents": "cinder-typhoon/narrative/arwc-documents",
            "logical_owner": "a-corporate.a-business",
        },
        "logical ownership",
    )
    for path, digest in f["source_digests"].items():
        require(
            sha((root / path).read_bytes()) == digest,
            "accepted source changed: " + path,
        )
    require(
        len(d) == 161 and len(m) == 134 and len(e) == 10, "finished content inventory"
    )
    require(
        len(f["periods"]) == 4
        and len(f["capital"]) == 12
        and len(f["budgets"]) == 8
        and len(f["projects"]) == 4
        and len(f["meetings"]) == 3
        and len(f["learning"]) == 4
        and len(f["publications"]) == 6
        and len(f["workbooks"]) == 28,
        "business record inventory",
    )
    for key in BOARD:
        require(
            key not in {p["key"] for p in roster}
            and people[key]["employer"] == "arwc-board"
            and people[key]["email"].endswith("@alterraboard.test"),
            "board member became employee",
        )
    controls = Controls(root)
    zero = controls.at("2026-05-31")
    expected_open = [
        dict(
            district=district,
            as_of="2026-05-31",
            cash_cents=cash,
            receivables_cents=0,
            payables_cents=zero[district]["acquisition"] - zero[district]["payment"],
            grni_cents=zero[district]["grni"],
            commitments_cents=zero[district]["commitments"],
        )
        for district, cash in [("PINE", 27500000), ("RIVER", 22500000)]
    ]
    require(f["opening_balances"] == expected_open, "opening balances")
    periods = {}
    expected_districts = []
    for i, p in enumerate(f["periods"]):
        require(
            p["cutoff"] == ["2026-06-30", "2026-07-31", "2026-08-31", "2026-09-15"][i]
            and p["previous"]
            == ("2026-05-31" if i == 0 else f["periods"][i - 1]["cutoff"]),
            "close cutoffs",
        )
        before, after = controls.at(p["previous"]), controls.at(p["cutoff"])
        delta = {
            k: controls.total(after, k) - controls.total(before, k)
            for k in ("billing", "receipt", "adjustment", "acquisition", "payment")
        }
        require(
            p["opening"] == controls.balance(before)
            and p["closing"] == controls.balance(after)
            and p["movements"] == delta,
            "dated close arithmetic",
        )
        require(
            p["grni_cents"] == controls.total(after, "grni")
            and p["commitments_cents"] == controls.total(after, "commitments"),
            "obligation classification",
        )
        require(p["released_at"][:10] > p["cutoff"], "close released before cutoff")
        for amount in p["closing"].values():
            require(
                usd(amount) in d["fg-" + p["id"] + "-summary"]["text"],
                "summary figure differs",
            )
        ob, cb = p["opening"], p["closing"]
        prefix = "fg-" + p["id"]
        money_text(
            d[prefix + "-summary"],
            [
                v
                for key in ("cash", "receivables", "payables")
                for v in (ob[key], cb[key] - ob[key], cb[key])
            ]
            + [delta["acquisition"], p["grni_cents"], p["commitments_cents"]],
        )
        money_text(
            d[prefix + "-payables"],
            [
                ob["payables"],
                delta["acquisition"],
                delta["payment"],
                cb["payables"],
                p["grni_cents"],
                p["commitments_cents"],
            ],
        )
        money_text(
            d[prefix + "-receivables"],
            [
                ob["receivables"],
                delta["billing"],
                delta["adjustment"],
                delta["receipt"],
                cb["receivables"],
            ],
        )
        money_text(
            d[prefix + "-cash"],
            [ob["cash"], delta["receipt"], delta["payment"], cb["cash"]],
        )
        money_text(d[prefix + "-approval"], list(cb.values()))
        for district in ("PINE", "RIVER"):
            expected_districts.append(
                dict(
                    period=p["id"],
                    cutoff=p["cutoff"],
                    district=district,
                    **{
                        k + "_cents": after[district][k] - before[district][k]
                        for k in delta
                    },
                    grni_cents=after[district]["grni"],
                    commitments_cents=after[district]["commitments"],
                )
            )
        money_text(
            d[prefix + "-district"],
            [
                after[district][k] - before[district][k]
                for district in ("PINE", "RIVER")
                for k in ("acquisition", "payment", "receipt")
            ],
        )
        periods[p["id"]] = p
    closing_rows = table(root, "retail-billing-records.zip", "registers/balances.csv")
    require(
        f["periods"][-1]["closing"]["receivables"]
        == sum(cents(r["balance_usd"]) for r in closing_rows),
        "retail closing balance join",
    )
    plans = {p["id"]: p for p in load(root, "planning.yaml")["cases"]}
    old_projects = {
        p["id"]: p for p in load(root, "maintenance-engineering.yaml")["projects"]
    }
    for c in f["capital"]:
        source = plans[c["planning"]]
        require(
            source["kind"] == "renewal"
            and c["retain_cents"] == cents(source["calculation"][0]["value"])
            and c["replace_cents"] == cents(source["calculation"][1]["value"]),
            "renewal comparison join",
        )
        values = {x["key"]: x["value"] for x in source["inputs"]}
        require(
            c["upfront_cents"] == cents(values["capital"] + values["access"])
            and c["authorized_cents"] == c["committed_cents"] == c["spent_cents"] == 0
            and c["state"] == "open"
            and c["due"] == "2026-09-30",
            "proposal treated as spent or complete",
        )
        require(
            source["condition"] in d["fg-" + c["id"] + "-decision"]["text"]
            and source["recommendation"] in d["fg-" + c["id"] + "-decision"]["text"],
            "planning recommendation changed",
        )
        money_text(
            d["fg-" + c["id"] + "-paper"],
            [
                c["retain_cents"],
                c["replace_cents"],
                c["replace_cents"] - c["retain_cents"],
                c["upfront_cents"],
                0,
                0,
            ],
        )
        money_text(
            d["fg-" + c["id"] + "-decision"],
            [c["retain_cents"], c["replace_cents"], 0, 0, 0],
        )
    for p in f["projects"]:
        source = old_projects[p["project"]]
        require(
            p["estimate_cents"] == cents(source["estimate"])
            and p["accepted_cents"] == cents(source["accepted"])
            and p["handover"] == source["handover"],
            "historical project join",
        )
        money_text(
            d["fg-" + p["id"] + "-brief"],
            [
                p["accepted_cents"],
                p["estimate_cents"],
                p["estimate_cents"] - p["accepted_cents"],
            ],
        )
    for b in f["budgets"]:
        expected = sum(
            int(r["amount_cents"])
            for r in controls.ledger
            if r["credit"] == "Accounts payable"
            and r["posted_at"][:10] <= "2026-08-31"
            and r["cost_center"].startswith(b["district"])
            and controls.by_invoice[r["reference"]]["category"] == b["category"]
        )
        contingency = int(
            (Decimal(expected) * Decimal(".10")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        require(
            b["base_cents"] == expected
            and b["contingency_cents"] == contingency
            and b["proposal_cents"] == expected + contingency
            and b["approved_cents"] == 0,
            "budget basis or authority",
        )
        money_text(
            d["fg-" + b["id"] + "-paper"],
            [expected, contingency, expected + contingency, 0],
        )

    expected_readers = {key: set(FINANCE) for key in d}
    for c in f["capital"]:
        for key in c["documents"]:
            expected_readers[key] = set(
                FINANCE + ["nadia", "awm139", plans[c["planning"]]["owner"]]
            )
    for p in f["projects"]:
        for key in p["documents"]:
            expected_readers[key] = set(
                FINANCE + [old_projects[p["project"]]["lead"], "awm220", "awm164"]
            )
    for l in f["learning"]:
        audience = set(
            [l["host"]]
            + l["attendees"]
            + ["awm220", "awm221", "awm222", "luc", "awm216"]
        )
        for key in l["documents"]:
            expected_readers[key] = audience
        require(
            l["total_person_minutes"]
            == l["minutes"] * (len(l["attendees"]) + 1) + l["preparation_minutes"],
            "learning time",
        )
        event = e["governance-" + l["id"]]
        duration = (
            datetime.fromisoformat(event["end"])
            - datetime.fromisoformat(event["start"])
        ).total_seconds() / 60
        require(
            duration == l["minutes"]
            and event["attendees"] == l["attendees"]
            and event["organizer"] == l["host"]
            and d[l["documents"][1]]["published_at"] > event["end"],
            "learning attendance chronology",
        )
    expected_readers["fg-governance-remit"] = set(GOV)
    for meeting in f["meetings"]:
        for key in meeting["documents"]:
            expected_readers[key] = set(GOV)
        votes = meeting["for_keys"] + meeting["against_keys"] + meeting["abstain_keys"]
        require(
            len(votes) == 6
            and set(votes) == set(BOARD)
            and meeting["against_keys"] + meeting["abstain_keys"],
            "board roll call or erased dissent",
        )
        require(
            meeting["state"] == "chair-checked; confirmation pending",
            "future minute confirmation",
        )
        ev = e["governance-" + meeting["id"]]
        require(
            ev["attendees"] == BOARD + ["awm216", "awm217", "luc", "awm164"]
            and ev["organizer"] == "awm220",
            "board attendance",
        )
        minute = d["fg-" + meeting["id"] + "-minutes"]
        require(
            minute["published_at"] > ev["end"]
            and f"For {len(meeting['for_keys'])}, against {len(meeting['against_keys'])}, abstained {len(meeting['abstain_keys'])}"
            in minute["text"],
            "minute chronology or vote arithmetic",
        )
        for amount in periods[meeting["close"]]["closing"].values():
            require(usd(amount) in minute["text"], "board financial figure")
    public_ids = {p["public"] for p in f["publications"]}
    require(
        {key for key, item in d.items() if item["audience"] == "public"} == public_ids,
        "public allowlist",
    )
    with zipfile.ZipFile(root / "documents/governance-records.zip") as archive:
        require(
            archive.testzip() is None
            and set(archive.namelist())
            == {x["member"] for x in d.values() if "member" in x}
            and len(archive.namelist()) == 40,
            "archive inventory",
        )
        for p in f["publications"]:
            draft, review, master, public, release = [
                d[p[k]] for k in ("draft", "review", "master", "public", "release")
            ]
            for item in (draft, review, master, release):
                expected_readers[item["id"]] = set(REPORT)
            expected_readers[public["id"]] = set()
            require(
                [x["document_state"] for x in (draft, review, master, public, release)]
                == ["draft", "restricted", "approved", "published", "approved"],
                "publication state sequence",
            )
            require(
                draft["published_at"]
                < review["published_at"]
                < master["published_at"]
                == p["approved_at"]
                < public["published_at"]
                == p["published_at"]
                < release["published_at"]
                <= SNAPSHOT,
                "publication chronology",
            )
            require(
                p["approved_by"] == "awm216"
                and p["publisher"] == "awm164"
                and public["publication"]
                == dict(
                    approved_by=people["awm216"]["email"],
                    approved_at=p["approved_at"],
                    published_by=people["awm164"]["email"],
                ),
                "publication authority",
            )
            require(
                master["member"] == public["member"]
                and master["binary_sha256"] == public["binary_sha256"] == p["sha256"]
                and master["text"] == public["text"],
                "approved master differs from public bytes",
            )
            raw = archive.read(public["member"])
            pdf = PdfReader(io.BytesIO(raw), strict=True)
            extracted = (
                "\n".join(page.extract_text() for page in pdf.pages).rstrip() + "\n"
            )
            require(
                extracted == public["text"]
                and not pdf.is_encrypted
                and 1 <= len(pdf.pages) <= 3,
                "PDF text or format",
            )
            require(
                pdf.metadata.author == "Alterra Regional Water Company"
                and pdf.metadata.creation_date.date().isoformat()
                == p["approved_at"][:10],
                "PDF author or date",
            )
            require(
                not any(page.get("/Annots") for page in pdf.pages)
                and "/Names" not in pdf.trailer["/Root"],
                "PDF private attachment or annotation",
            )
            require(
                not re.search(
                    r"draft P1|factual correction|review comments|ARWC-A-|personnel|issue 129",
                    extracted,
                    re.I,
                ),
                "private data in public search",
            )
            require(
                "September 15" in extracted
                and "September 16" in extracted
                and p["correction"] in review["text"],
                "release evidence",
            )
            flat = " ".join(extracted.split())
            if p["id"] == "publication-01":
                for value in [sum(x["accepted_cents"] for x in f["projects"])] + [
                    x["accepted_cents"] for x in f["projects"]
                ]:
                    require("USD " + usd(value) in flat, "public historical cost")
                require(
                    "February 20, 2023" in flat and "not this year" in flat,
                    "public historical period",
                )
            elif p["id"] == "publication-02":
                require(
                    "50,100 payer accounts and 50,102 issued invoices" in flat
                    and "wastewater billing is separate" in flat,
                    "public account scope",
                )
            elif p["id"] == "publication-03":
                august = f["periods"][2]
                for value in list(august["closing"].values()) + [
                    august["grni_cents"],
                    august["commitments_cents"],
                ]:
                    require("USD " + usd(value) in flat, "public close figure")
                require(
                    "August 31, 2026" in flat
                    and "not the company" in flat
                    and "55% Pine and 45% River" in flat,
                    "public close scope",
                )
            elif p["id"] == "publication-04":
                require(
                    usd(sum(x["upfront_cents"] for x in f["capital"])) in flat
                    and "USD 0.00 released" in flat
                    and "USD 0.00 of new spending" in flat
                    and "September 30 follow-ups remain open" in flat,
                    "public capital authority",
                )
            elif p["id"] == "publication-05":
                time = sum(x["total_person_minutes"] for x in f["learning"])
                require(
                    f"{time} person-minutes" in flat
                    and f"{Decimal(time) / 60} person-hours" in flat
                    and "Individual task notes are kept privately" in flat,
                    "public learning account",
                )
            else:
                require(
                    usd(sum(x["proposal_cents"] for x in f["budgets"])) in flat
                    and "five votes to one" in flat
                    and "not a complete annual operating budget" in flat,
                    "public board account",
                )
        expected_readers["fg-publication-register"] = set(REPORT)
        for book in f["workbooks"]:
            kind, selector = book["kind"], book["selector"]
            if kind == "close":
                p = next(p for p in f["periods"] if p["cutoff"] == selector["cutoff"])
                require(selector["previous"] == p["previous"], "Office close period")
                ob, mv = p["opening"], p["movements"]
                inputs = [
                    ob["cash"],
                    mv["receipt"],
                    mv["payment"],
                    ob["receivables"],
                    mv["billing"],
                    mv["adjustment"],
                    ob["payables"],
                    mv["acquisition"],
                ]
            elif kind == "capital":
                values = {
                    x["key"]: x["value"] for x in plans[selector["planning"]]["inputs"]
                }
                inputs = [
                    cents(values[k]) for k in ("capital", "access", "repair", "upkeep")
                ] + [values["years"]]
            elif kind == "project":
                p = old_projects[selector["project"]]
                inputs = [cents(p["estimate"]), cents(p["accepted"])]
            else:
                require(kind == "budget", "unknown workbook kind")
                b = next(
                    b
                    for b in f["budgets"]
                    if b["district"] == selector["district"]
                    and b["category"] == selector["category"]
                )
                inputs = [b["base_cents"], 0.10]
            check_workbook(archive.read(d[book["document"]]["member"]), book, inputs)
            for label, formula, value, unit in book["calculation"]:
                require(
                    f"{label}: {value} {unit}" in d[book["document"]]["text"],
                    "workbook search summary",
                )
        schedules = {
            "opening-balances": expected_open,
            "district-movements": expected_districts,
            "period-controls": [
                dict(
                    period=p["id"],
                    cutoff=p["cutoff"],
                    **{k + "_cents": v for k, v in p["closing"].items()},
                    grni_cents=p["grni_cents"],
                    commitments_cents=p["commitments_cents"],
                )
                for p in f["periods"]
            ],
            "capital-screen-register": [
                {k: v for k, v in c.items() if k != "documents"} for c in f["capital"]
            ],
            "budget-proposals": [
                {k: v for k, v in c.items() if k != "documents"} for c in f["budgets"]
            ],
            "publication-register": [
                dict(
                    publication=p["id"],
                    public_document=p["public"],
                    approved_at=p["approved_at"],
                    published_at=p["published_at"],
                    approved_by=p["approved_by"],
                    publisher=p["publisher"],
                    sha256=p["sha256"],
                )
                for p in f["publications"]
            ],
        }
        for member, expected in schedules.items():
            actual = list(
                csv.DictReader(
                    io.StringIO(archive.read("registers/" + member + ".csv").decode())
                )
            )
            require(
                actual == [{k: str(v) for k, v in row.items()} for row in expected],
                "register content: " + member,
            )
        for item in d.values():
            require(
                item["published_at"] <= SNAPSHOT and item["employer"] == "arwc",
                "document date or owner",
            )
            require(
                set(item.get("reader_keys", [])) == expected_readers[item["id"]],
                "exact document readers",
            )
            require(
                item["audience"]
                == ("public" if item["id"] in public_ids else "restricted"),
                "private document became broad",
            )
            require(
                not re.search(
                    r"issue 129|ground.control|environment.owned|scenario.overlay|codex|openai",
                    str(item),
                    re.I,
                ),
                "authoring leakage",
            )
            if "archive" in item:
                require(
                    item["archive"] == "documents/governance-records.zip"
                    and sha(archive.read(item["member"])) == item["binary_sha256"],
                    "binary digest",
                )
    for item in m.values():
        require(
            item["date"] <= SNAPSHOT
            and item["from"] in people
            and set(item["to"]) <= people.keys(),
            "mail date or participants",
        )
        require(
            len(item["to"]) == len(set(item["to"])) and item["from"] not in item["to"],
            "duplicate or self-addressed recipient",
        )
        require(
            not re.search(
                r"issue 129|ground.control|environment.owned|scenario.overlay|codex|openai",
                str(item),
                re.I,
            ),
            "mail authoring leakage",
        )
        for key in item.get("attachments", []):
            require(
                key in d and d[key]["published_at"] <= item["date"],
                "attachment chronology",
            )
            require(
                key in public_ids
                or set([item["from"]] + item["to"]) <= expected_readers[key],
                "attachment audience",
            )
        if item.get("reply_to"):
            require(
                item["reply_to"] in m and m[item["reply_to"]]["date"] < item["date"],
                "reply lineage",
            )
    copies = sum(
        people[k]["employer"] == "arwc"
        for item in m.values()
        for k in [item["from"]] + item["to"]
    )
    require(
        f["counts"]["logical_messages"] == len(m)
        and f["counts"]["retained_copies"] == copies == 483
        and f["counts"]["document_items"] == len(d)
        and f["counts"]["calendar_occurrences"] == len(e),
        "counts",
    )
    require(
        f["volume_adjustment"]["initial_logical_messages"] == 5500
        and f["volume_adjustment"]["delivered_logical_messages"] == len(m)
        and f["volume_adjustment"]["reduction"] == 5500 - len(m),
        "message allocation",
    )
    prior_events = []
    for path in (root / "authoring").glob("calendars*.yaml"):
        if path.name != "calendars-governance.yaml":
            prior_events.extend(yaml.safe_load(path.read_text())["events"])
    for event in e.values():
        participants = set([event["organizer"]] + event["attendees"])
        for previous in prior_events:
            if previous["status"] == "CANCELLED":
                continue
            shared = participants & set([previous["organizer"]] + previous["attendees"])
            require(
                not shared
                or event["start"] >= previous["end"]
                or previous["start"] >= event["end"],
                "calendar conflict: " + event["id"] + " / " + previous["id"],
            )
    return f["counts"]


if __name__ == "__main__":
    print(
        check_governance(
            ROOT,
            load(ROOT, "workforce.yaml")["employees"],
            load(ROOT, "people.yaml"),
            load(ROOT, "mail-governance.yaml")["messages"],
            load(ROOT, "documents-governance.yaml")["documents"],
            load(ROOT, "calendars-governance.yaml")["events"],
        )
    )
