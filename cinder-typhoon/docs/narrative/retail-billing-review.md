# ARWC retail billing, payments, and customer-service review: issue 127

Author-only review. Accepted base: `7bc1976`, including the accepted service-account
model in `d8c3d05` and purchasing/stores content in `46b6980`. Snapshot:
September 16, 2026, 08:30, UTC−04:00.

## Review before authoring

1. The issue's provisional 61,500 bills assumed the earlier dwelling-level
   account estimate. The accepted model has 50,100 payer accounts and 50,102
   authoritative invoices: one opening bill per account plus two later Talvern
   deliveries. Use those invoice identities. Do not invent 11,398 files or
   present a readable copy as a second bill.
2. Every bill must join its account, service point, tariff, period, actual
   reading pair, line arithmetic, issue date, due date, opening allocation, and
   delivery preference. Private check meters remain unbilled. Tax remains zero,
   currency remains USD, and wastewater remains outside ARWC's fictional scope.
3. A delivery record and a mailbox message are not the same thing. Preserve the
   accepted electronic/postal preference for each issue date without placing
   50,102 repetitive delivery messages in staff mailboxes.
4. Later receipts, allocations, credits, debits, balances, reminders, and
   arrangements need one equation. A payment confirmation cannot precede its
   payment, an adjustment cannot rewrite the source invoice, and an arrangement
   cannot erase the overdue amount it schedules.
5. Customer service must include ordinary questions, not 800 angry disputes.
   Period explanations, reading checks, allocations, balance questions,
   appointments, copy requests, adjustments, and arrangements each need a
   plausible share. Four-, six-, eight-, and ten-message threads must earn their
   length through clarification and recorded action.
6. Rosa's accepted clearer billing-period explanation answers dates before
   process. Reuse that accepted item where it answers the question. Colleagues
   need different habits rather than copies of Rosa with a changed signature.
7. Belvarn's two supply feeds stay on `A-B-001`; follow-up does not promise a
   production saving. Talvern's `A-B-002` arrangement stays tied to the shared
   facility and does not absorb members' other water arrangements.
8. Appointment preferences are not bookings. A visit history needs a requested
   time, service point, purpose, agreed future window, and state. Similarly,
   paper-copy dispatch is not a preference change unless separately authorized.
9. Financial identifiers and amounts are authoritative records. Deliberate
   human variation belongs in correspondence, never in bill totals, meter IDs,
   payment references, or appointment dates.
10. All content is reusable environment history. Issue identity, review notes,
    generation means, scenario ownership, and challenge language stay outside
    participant-visible mail, bills, PDFs, registers, and paths.

## Delivered content

| Record | This slice | Relationship |
| --- | ---: | --- |
| Readable bill representations | 50,102 | One per accepted invoice; no new invoice authority |
| Bill-line projections | 101,641 | Exact source line IDs and arithmetic |
| Delivery records | 50,102 | 40,074 electronic; 10,028 postal |
| Post-opening payments / allocations | 31,920 / 31,920 | One complete allocation per accepted payment |
| Adjustments | 500 | Credits and debits leave source bills unchanged |
| Snapshot balances | 50,100 | Opening balance + adjustments − payments |
| Customer-service cases | 800 | 6,100 threaded case messages |
| System and routine notices | 1,500 | Seven purposeful notice types |
| Distinct logical messages | 7,600 | 9,100 retained ARWC mailbox copies |
| Appointment histories | 200 | Scheduled or rescheduled; future visit windows |
| Collections / arrangements | 300 / 200 | Exact overdue balance and three-part arithmetic |
| Source document items | 839 | 800 case readbacks, 15 bulk data items, 24 PDFs |
| Archive members | 39 | Fourteen CSVs, one NDJSON bill set, 24 PDFs |

The 50,102 bill renderings are complete Markdown documents stored as one
line-delimited data item so the native document service can preserve the full
population without treating each item as a separate deployment file. Twenty-four
genuine searchable PDFs cover home, master-metered, business, municipal,
Belvarn, and all three Talvern invoice forms. They are representative forms of
the same invoice identities, not additional bills.

The provisional bill count is reduced by **11,398**, from 61,500 to 50,102.
This is a model correction, not a content shortfall: 60,000 occupied dwellings
include 12,000 apartments behind 480 master-metered payer accounts. The finished
message count retains the issue's 7,600 allocation. Delivery records carry the
full population; mail remains a useful collection rather than a duplicate
transport log.

## Finished-content adversarial review

- A first projection risked using each account's September preference for its
  July bill. The finished delivery register reverses later authorized changes
  and reconstructs the channel in force on the invoice date. The result is
  40,074 electronic and 10,028 postal deliveries.
- Readable copies initially looked like a second invoice population. Every bill
  and line now retains the accepted invoice and line ID, and validation enforces
  a one-to-one source projection. Copy dispatch explicitly says that it creates
  no second invoice.
- Blank visual lines in the PDFs are not returned by ordinary PDF extraction.
  Declared search text now follows the strict parser result while the page keeps
  its visual spacing; all 24 PDFs parse as unencrypted, one-page documents.
- Selected customer contacts deliberately cover paid, part-paid, and unpaid
  outcomes. This prevents the case and notice set from implying that every
  customer is upset or that every contact ends in immediate full settlement.
- The completed ledger keeps all 500 adjustments separate from bill authority.
  Reconciliation across all 50,100 accounts proves `opening + adjustment −
  payment = snapshot balance`; credits remain negative balances and overdue is
  never negative.
- The 200 arrangements sum exactly to the corresponding overdue balance across
  three dated instalments. No arrangement changes the invoice, payment history,
  or Talvern's limited seasonal scope.
- Appointment messages initially could have made a contact-window preference
  sound like consent to enter. The finished histories record a distinct request,
  service point, purpose, scheduled time, and state; all visit windows are after
  the snapshot.
- Belvarn's named follow-up refers to both billing feeds and promises no
  production saving. Talvern's named arrangement keeps shared-facility billing
  separate from member water sources and other arrangements.
- All 7,600 bodies are distinct. Repeated automatic structure is limited to
  notifications; personal threads vary by account facts, case length, speaker
  habit, question, and outcome.

## Validation and limits

`validate_retail_billing.py` reads both archives and checks every invoice and
line projection, reading join, issue-date delivery preference, payment and
allocation, adjustment sign, account equation, case thread, exact recipient,
appointment, collection, arrangement, PDF byte/digest/search surface, document
reader, and visible provenance boundary. The full narrative validator separately
checks rendered RFC 5322 bytes, MIME attachments, mailbox membership, package
digests, ownership, and native SDL readback declarations.

The records are a complete represented cycle for the accepted opening invoices
and their later account history, not a statutory ledger, bank feed, mail-service
execution claim, or future October billing run. Static validation does not claim
that a workplace adapter delivered post, moved money, or attended a meter visit.

Ownership release: `retail-billing-2026-09-16/v1`. Every added record is ordinary
environment content; the scenario overlay remains empty.
