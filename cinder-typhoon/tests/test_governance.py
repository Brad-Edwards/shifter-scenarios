"""Adversarial finance, chronology, authority, binary and publication checks."""

import copy
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from validate_governance import ROOT, check_governance, load, sha


class GovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROOT, "workforce.yaml")["employees"]
        cls.identity = load(ROOT, "people.yaml")
        cls.content = (
            load(ROOT, "governance.yaml"),
            load(ROOT, "mail-governance.yaml")["messages"],
            load(ROOT, "documents-governance.yaml")["documents"],
            load(ROOT, "calendars-governance.yaml")["events"],
        )

    def check(self, content, root=ROOT):
        f, m, d, e = content
        return check_governance(root, self.roster, self.identity, m, d, e, f)

    def test_finished_content(self):
        self.assertEqual(self.check(self.content)["document_items"], 161)

    def test_rejects_accounting_authority_and_reader_errors(self):
        def opening(f, m, d, e):
            f["opening_balances"][0]["cash_cents"] += 1

        def close(f, m, d, e):
            f["periods"][1]["closing"]["receivables"] += 1

        def duplicate_cash(f, m, d, e):
            f["periods"][1]["movements"]["receipt"] *= 2

        def cutoff(f, m, d, e):
            f["periods"][0]["cutoff"] = "2026-07-31"

        def obligation(f, m, d, e):
            f["periods"][2]["grni_cents"] = 0

        def spent(f, m, d, e):
            f["capital"][0]["spent_cents"] = 180000

        def future_action(f, m, d, e):
            f["capital"][0]["state"] = "complete"

        def recommendation(f, m, d, e):
            next(x for x in d if x["id"] == f["capital"][0]["documents"][2])["text"] = (
                "Approved without conditions."
            )

        def project(f, m, d, e):
            f["projects"][0]["handover"] = "2026-09-01"

        def budget(f, m, d, e):
            f["budgets"][0]["approved_cents"] = f["budgets"][0]["proposal_cents"]

        def manager_vote(f, m, d, e):
            f["meetings"][0]["for_keys"][0] = "luc"

        def erased_dissent(f, m, d, e):
            f["meetings"][0]["for_keys"] += f["meetings"][0]["abstain_keys"]
            f["meetings"][0]["abstain_keys"] = []

        def confirmation(f, m, d, e):
            f["meetings"][0]["state"] = "confirmed"

        def publication_authority(f, m, d, e):
            f["publications"][0]["approved_by"] = "luc"

        def publication_date(f, m, d, e):
            f["publications"][0]["approved_at"] = "2026-09-17T09:00:00-04:00"

        def public_draft(f, m, d, e):
            next(x for x in d if x["id"] == f["publications"][0]["draft"])[
                "audience"
            ] = "public"

        def public_search(f, m, d, e):
            next(x for x in d if x["id"] == f["publications"][0]["public"])["text"] += (
                "Private draft note.\n"
            )

        def unrelated_reader(f, m, d, e):
            d[0]["reader_keys"].append("mina")

        def attachment_leak(f, m, d, e):
            m[0]["to"].append("board_elva")

        def future_attachment(f, m, d, e):
            m[0]["attachments"].append(f["periods"][-1]["documents"][0])

        def future_mail(f, m, d, e):
            m[0]["date"] = "2026-09-17T09:00:00-04:00"

        def lineage(f, m, d, e):
            m[1]["reply_to"] = m[-1]["id"]

        def learning(f, m, d, e):
            f["learning"][0]["total_person_minutes"] += 60

        def attendance(f, m, d, e):
            next(x for x in e if x["id"] == "governance-learning-01")["end"] = (
                "2026-06-18T13:00:00-04:00"
            )

        def provenance(f, m, d, e):
            m[0]["body"] += "Issue 129 is complete.\n"

        def duplicate_recipient(f, m, d, e):
            m[0]["to"].append(m[0]["to"][0])

        def printed_amount(f, m, d, e):
            next(x for x in d if x["id"] == "fg-close-01-summary")["text"] = next(
                x for x in d if x["id"] == "fg-close-01-summary"
            )["text"].replace("456,318.10", "456,318.11")

        for mutate in (
            opening,
            close,
            duplicate_cash,
            cutoff,
            obligation,
            spent,
            future_action,
            recommendation,
            project,
            budget,
            manager_vote,
            erased_dissent,
            confirmation,
            publication_authority,
            publication_date,
            public_draft,
            public_search,
            unrelated_reader,
            attachment_leak,
            future_attachment,
            future_mail,
            lineage,
            learning,
            attendance,
            provenance,
            duplicate_recipient,
            printed_amount,
        ):
            with self.subTest(mutation=mutate.__name__):
                content = copy.deepcopy(self.content)
                mutate(*content)
                with self.assertRaises(ValueError):
                    self.check(content)

    def test_checksum_consistent_corruption(self):
        for corruption in ("formula", "cache", "allocation", "pdf"):
            with (
                self.subTest(corruption=corruption),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / "authoring").symlink_to(
                    ROOT / "authoring", target_is_directory=True
                )
                (root / "documents").mkdir()
                for path in (ROOT / "documents").iterdir():
                    if path.name != "governance-records.zip":
                        (root / "documents" / path.name).symlink_to(path)
                content = copy.deepcopy(self.content)
                f, m, d, e = content
                with zipfile.ZipFile(ROOT / "documents/governance-records.zip") as z:
                    members = {n: z.read(n) for n in z.namelist()}
                if corruption in ("formula", "cache"):
                    member = "workbooks/close-01-workbook.xlsx"
                    with zipfile.ZipFile(io.BytesIO(members[member])) as z:
                        parts = {n: z.read(n) for n in z.namelist()}
                    path = "xl/worksheets/sheet3.xml"
                    before = parts[path]
                    if corruption == "formula":
                        parts[path] = before.replace(
                            b"Inputs!B2+Inputs!B3-Inputs!B4",
                            b"Inputs!B2+Inputs!B3+Inputs!B4",
                            1,
                        )
                    else:
                        parts[path] = before.replace(
                            b"<v>45631810.0</v>", b"<v>45631811.0</v>", 1
                        )
                    self.assertNotEqual(before, parts[path])
                    out = io.BytesIO()
                    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                        for name, raw in parts.items():
                            z.writestr(name, raw)
                    members[member] = out.getvalue()
                    expected = (
                        "Office formula differs"
                        if corruption == "formula"
                        else "Office cached result differs"
                    )
                elif corruption == "allocation":
                    member = "registers/district-movements.csv"
                    before = members[member]
                    members[member] = before.replace(b",PINE,", b",RIVER,", 1)
                    self.assertNotEqual(before, members[member])
                    expected = "register content"
                else:
                    member = "publications/service-improvements-r1.pdf"
                    members[member] = members["publications/your-bill-r1.pdf"]
                    expected = "PDF text or format"
                    f["publications"][0]["sha256"] = sha(members[member])
                for item in d:
                    if item.get("member") == member:
                        item["binary_sha256"] = sha(members[member])
                with zipfile.ZipFile(
                    root / "documents/governance-records.zip", "w", zipfile.ZIP_DEFLATED
                ) as z:
                    for name, raw in members.items():
                        z.writestr(name, raw)
                with self.assertRaisesRegex(ValueError, expected):
                    self.check(content, root)


if __name__ == "__main__":
    unittest.main()
