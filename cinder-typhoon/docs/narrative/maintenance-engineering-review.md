# ARWC maintenance and engineering review: issue 124

Author-only review. Accepted base: `64908ae`, including field operations accepted
in `700c43b`. Snapshot: September 16, 2026, 08:30, UTC−04:00.

## Review before authoring

1. The 48-person population is fixed: 15 mechanical colleagues, eleven electrical
   and controls colleagues, ten maintenance planners, and twelve capital-project
   colleagues. Historical work must not place somebody before their current-role
   effective date. Current work must give every colleague meaningful coverage
   without turning planners and engineers into a single interchangeable voice.
2. Issue 123 leaves exactly 24 accepted operations requests. Preserve each
   request, source observation, asset identity, receipt time and reporter. Receipt
   by Theo is intake, not evidence of scheduling or completion.
3. Use the established Pine and River plants, depots and districts, North
   reservoir, South valve chamber, Upland station and Cairn Reach. Cairn Reach
   remains a small part of the ordinary register. Do not alter reservoir tags,
   operating setpoints, protection, allocation data or challenge records.
4. A routine work order needs a source, asset, planner, technician, job plan,
   observed condition, status and handover. Not every order needs email, a
   contractor or a part. Waiting stock, deferred access and work still planned at
   the snapshot must not read as completed.
5. Contractor chronology is strict: quotation, written acceptance, appointment,
   service report and ARWC receipt. Veybridge's standard visit remains USD
   1,240. Ardenvale orders stay below the accepted USD 18,000 ceiling. An
   appointment or report does not silently approve extra travel, parts or a later
   visit.
6. Richer 2021–2023 histories should extend the established refurbishment story
   without rewriting it. Working P1/P2 drawings need an unmistakable non-approved
   state; only A1 may be effective for work and precede commissioning and handover.
7. Supplier messages should sound like the supplier's own work. Jules is brief
   and field-oriented, Dana distinguishes a held slot from authority, Vera names
   the practical service item, and Reece states the return record plainly.
8. The initial 7,000-message allocation would require almost ten messages per
   work order before counting drawings, service reports and structured registers.
   Use actual records for quiet work and reserve correspondence for acceptance,
   exceptions, revision control and handover. Record the resulting adjustment.
9. Retain all finished items in the existing ARWC mail, document and calendar
   sources with exact named readers. Author metadata and this review remain
   outside the workplace. Static validation is not runtime deployment proof.

## Delivered content

| Record | This slice | Full narrative corpus |
| --- | ---: | ---: |
| Distinct logical messages | 432 | 28,478 |
| Retained ARWC mailbox copies | 936 | This slice |
| Source document items | 871 | 9,414 |
| Calendar occurrences | 24 | 806 |
| Native packaged items added | 1,327 | This slice |
| Maintenance and engineering staff covered | 48 | 48 |
| Assets / sites | 72 / 10 | This slice |
| Work orders | 720 | This slice |
| Contractor jobs | 24 | This slice |
| Completed capital histories | 4 | 2021–2023 |
| Completed CSV registers / rows | 11 / 2,107 | This slice |
| Actual drawing files | 12 SVG | P1, P2 and A1 for each project |

The 871 documents comprise 720 work orders, twelve job plans, four estimates,
twelve drawings, eight engineering notes, four commissioning records, four
project handovers, 96 contractor quotation/order/report/receipt records and
eleven completed CSV registers. The archive contains those eleven tables and
twelve independently materialized SVG drawings. A table row and its readable
work-order form describe one business event, not two work orders.

The work-order population is 568 completed, 76 waiting parts, 40 deferred and
36 planned. All 24 upstream operations requests retain their exact request and
asset references. The recent work spans ten established sites; Cairn Reach is
not a dominant location. Every current employee owns work and sends at least one
message. Assignment dates are checked against start and current-role effective
dates.

The four richer histories cover the North reservoir inlet actuator, Pine pump
hall ventilation, River booster duty pump and Upland telemetry panel. Each has
an estimate and accepted cap, two working revisions, one approved revision,
two engineering notes, commissioning, handover and six historical work orders.
Accepted amounts do not exceed estimates. These records complete the ordinary
2021–2023 refurbishment history without changing later operating state.

The initial allocation is reduced by **6,568** messages, from 7,000 to 432. The
milestone corpus therefore rises from 28,046 to **28,478** messages. Adding
thousands of acknowledgements would have made quiet inspections less credible
and obscured the documents people actually use. The delivered correspondence
has 392 distinct bodies; compact administrative wording recurs only where the
same process warrants it. Retained copies and attachments do not increase the
logical-message count.

## Finished-content adversarial review

- The first draft mapped operations requests only by site. That could have moved
  a request to a convenient asset. The finished join now preserves all 24 exact
  upstream asset IDs and rejects a changed source observation or receipt order.
- Historical rotation initially assigned two project leads before they joined
  ARWC and allowed current-role transfers to leak backwards. Project leads and
  all 720 work-order assignments now pass employment-effective-date checks.
- A capped late work date briefly placed a planned visit after its status update.
  The final chronology caps both values in order and leaves the affected order
  planned rather than inventing a result.
- Contractor visits initially fell on some weekends and receipts appeared late
  in the evening. Finished appointments move to ordinary weekdays and receipts
  to the next business morning while retaining the required acceptance order.
- Early supplier confirmations used one shared sentence. Jules, Dana, Vera and
  Reece now retain different practical concerns and sentence shapes; technical
  staff and planners use person-appropriate samples documented separately.
- Working drawings contained the word “approved” only inside a warning. The
  validator checks the stronger `NOT APPROVED FOR WORK` watermark and allows
  only A1 into the effective set. XML parsing and exact binary digests cover all
  twelve shipped SVG files.
- Participant-visible handover prose briefly named an authoring distinction.
  That phrase was removed. Finished mail, records, paths and drawings contain no
  issue number, scenario label or challenge-specific ownership language.
- Every quotation amount equals its accepted order and service receipt. All
  twelve Veybridge visits use the USD 1,240 agreement rate; Ardenvale values are
  explicit and below the per-order ceiling. No service report creates later
  scope or an unpriced obligation.

## Validation and limits

`validate_maintenance_engineering.py` independently checks counts, all staff and
asset joins, employment-effective dates, the 24 operations requests, status
distribution, work-order readback, archive primary keys and digests, SVG parsing,
drawing authority, project chronology and amounts, contractor acceptance and
calendar joins, body diversity and participant-visible leakage. The full
narrative validator additionally checks attachments, mailbox retention, exact
readers, generated package digests, native source versions and SDL readback
bindings.

The records are a substantial recent and selected historical maintenance book,
not the utility's entire asset life-cycle system. Condition entries are bounded
maintenance observations, not engineering fitness certification. Static source
and SDL checks do not claim that a workplace adapter has materialized or served
the content.

Ownership release: `maintenance-engineering-2026-09-16/v1`. Every added record
is ordinary environment content; the scenario overlay remains empty.
