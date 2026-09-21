# ARWC laboratory and quality review: issue 125

Author-only review. Accepted base: `291fcf1`, including field operations in
`700c43b` and maintenance/engineering in `0b7f0b2`. Snapshot: September 16,
2026, 08:30, UTC−04:00.

## Review before authoring

1. The slice covers the 24 laboratory, quality-systems and compliance-reporting
   colleagues within the fixed 32-person department. The eight resource planners
   remain upstream readers, not substitute analysts or reviewers.
2. Issue 123 supplies exactly sixty sealed sample handoffs. Preserve sample,
   visit, asset, collection, handoff, receiver and seal fields byte-for-byte.
   A field return confirms custody, never an analytical result.
3. Every new history needs a schedule, collection, receipt, analytical run,
   named review and issued-report destination. A spreadsheet row or friendly
   email cannot silently replace one of those decisions.
4. Use one explicit fictional internal specification. Its units and bands must
   agree everywhere and must never be described as legislation, regulation,
   drinking-water guidance or evidence of public safety.
5. Ordinary accepted work should predominate. A preliminary response can be
   repeated and retained; a recollection stays open until a new sample actually
   exists. Neither case becomes a crisis or a concealed incident.
6. Reports must follow review. Workbooks need useful sheets, real rows, formula
   cells and cached totals; decorative files with an XLSX extension are not
   evidence. Structured registers retain the authoritative identifiers.
7. Laboratory equipment service changes the service record, not historical
   results. Training confirms attendance and a worked example, not new operating
   authority. Quality review improves a bounded form without inventing misconduct.
8. The photography winner must be a real laboratory colleague. Kaisa Kelswick's
   kitchen-window photograph fits the accepted result announcement without
   changing the earlier shared message or turning her into a social-only prop.
9. Exact readers remain role-based and named. Laboratory data does not inherit
   customer contact fields from the field extract. Employment training stays
   with the colleague, reviewer and department lead.
10. The initial 4,400-message allocation would add more than four messages per
    sample history after the registers, reports and workbooks already carry the
    work. Reserve mail for custody notices, issued reports, exceptions, service,
    learning, review and actual colleague exchanges; record the adjustment.

## Delivered content

| Record | This slice | Full narrative corpus |
| --- | ---: | ---: |
| Distinct logical messages | 318 | 28,796 |
| Retained ARWC mailbox copies | 992 | This slice |
| Source document items | 106 | 9,520 |
| Calendar occurrences | 34 | 840 |
| Native packaged items added | 458 | This slice |
| Laboratory/quality/reporting staff covered | 24 | 24 |
| Complete sample histories | 960 | January 5–September 11 |
| Accepted / accepted after repeat / recollection open | 912 / 36 / 12 | This slice |
| Analytical result rows | 2,916 | Three per sample plus 36 retained preliminary runs |
| Issued weekly reports / monthly workbooks | 36 / 9 | This slice |
| Equipment service / training / quality review records | 18 / 24 / 8 | This slice |
| Completed CSV registers / archive members | 9 / 18 | Nine CSV plus nine XLSX |

The nine registers hold the sampling schedule, sample identities, receipts,
analytical results, reviews, report register, equipment service, training and
quality-review history. The nine actual Office workbooks cover January through
September with visible Summary, Samples and Results sheets. Formula cells
reconcile source rows and carry checked cached values. No hidden sheet or author
note carries scenario information.

All 960 histories use `ARWC-LOS-26-01`. CRU, MBU and RSI are deliberately
fictional ARWC working measures. The specification, every issued report and the
review validator state that their bands are internal operating aids rather than
external legal limits. Of the 960 histories, 95 percent pass first review, 36
retain both a preliminary response and accepted repeat, and twelve remain open
for recollection. Nothing converts those twelve into accepted results.

The sixty August–September field handoffs retain all accepted upstream fields.
The other 900 histories form a bounded six-sample-per-weekday book from January
through July across ten established sites. Cairn Reach is a minor location.
Every result has consistent units, a named analyst and reviewer, and exactly one
weekly report. Reports include every sample and actual disposition and follow
the last review in their week.

The 106 documents comprise two controlled guides, nine registers, nine monthly
workbooks, 36 issued summaries, eighteen equipment-service notes, 24 private
training completions and eight internal quality reviews. Calendars carry eighteen
service appointments, eight learning sessions and eight quality reviews. A
calendar response is not treated as completion; each completed record is separate.

Messages comprise sixty custody notices, 36 issued-report notices, 72 messages
in 24 bounded record checks, 54 equipment-service messages, 24 learning messages,
24 quality-review messages and 48 colleague exchanges. The latter include
Kaisa's reply to the accepted photography thread, lunches, walking, a paper
notebook, tea and reactions to imperfect training examples. All 24 colleagues
send mail. Formal process wording recurs where the process recurs; 300 distinct
bodies keep the human exchanges and record-specific notices from becoming one
stock narrative.

The initial allocation is reduced by **4,082** messages, from 4,400 to 318. The
milestone corpus therefore rises from 28,478 to **28,796** messages. Adding
acknowledgements to every analytical step would obscure the structured custody
and review history. Retained copies, workbook rows, result rows and attachments
do not increase the logical-message count.

## Finished-content adversarial review

- The first workbook publication rule used calendar day 28 for every month, which could
  precede late-month samples. Finished workbooks take the last included collection
  time and publish afterward; validation compares their month rows and formulas.
- Two draft colleague notes crossed the September 16 snapshot. They were moved
  inside the accepted August window before rendering. Every message, document
  and completed event now precedes the snapshot.
- A first correspondence pass repeated reviewer and maintenance replies too
  broadly. Finished replies name the actual sample, service, topic or review,
  while standard custody language remains stable where consistency is useful.
- The sixty field records are compared directly with both accepted source CSVs.
  The check rejects a changed visit, asset, collection time, handoff time,
  receiver or seal rather than accepting a plausible site-level match.
- Reports cannot precede receipt or review: the validator walks all 960 chains
  and compares every weekly publication time with every included review.
- The repeat path retains the failed preliminary CRU response and one accepted
  repeat instead of rewriting the first run. Open recollections retain three
  unaccepted results and no fabricated replacement sample.
- Workbook validation opens each Office archive, rejects hidden or missing sheets,
  and checks formula text, cached values, row widths and binary digests. The CSV
  registers independently enforce primary keys and content hashes.
- Kaisa's response joins the existing `a-photo-5` thread and explains the already
  announced kitchen-window image. It does not change Theo's second place, Mina
  and Owen's display inclusion, or the September 15 announcement.
- Visible content contains no issue number, scenario ownership, authoring system
  or challenge label. Reader lists remain in source metadata rather than prose.

## Validation and limits

`validate_laboratory_quality.py` independently checks counts, staff coverage,
message diversity, all nine registers, archive digests, actual workbook structure
and formula caches, the 960 complete chains, status distribution, fictional
specification units and bands, all sixty upstream handoffs, report chronology and
coverage, equipment/training/review inventories, calendars, photography continuity
and visible leakage. The full narrative validator additionally checks MIME bytes,
attachments, mailbox copies, document readers, ownership, source versions and SDL
readback bindings.

This is a substantial bounded laboratory book, not a real utility specification
or a complete life-of-company archive. It does not claim legal compliance,
public-health interpretation, live laboratory integration or runtime deployment.

Ownership release: `laboratory-quality-2026-09-16/v1`. Every added record is
ordinary environment content; the scenario overlay remains empty.
