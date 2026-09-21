# ARWC purchasing, stores, supplier invoice, and payment review: issue 126

Author-only review. Accepted base: `700c2d1`, including maintenance and
engineering accepted in `0b7f0b2` and laboratory and quality accepted in
`f16aec0`. Snapshot: September 16, 2026, 08:30, UTC−04:00.

## Review before authoring

1. Purchasing must preserve the difference between a request, supplier offer,
   selection, approval, order, receipt, invoice, match, payment request, and
   settlement. A document later in that sequence cannot create earlier authority.
2. The 24 maintenance contractor packages already contain accepted quotations,
   orders, reports, and receipts. Reuse those records exactly. Add procurement
   intake, invoice, match, and settlement without inventing a second visit or
   replacing accepted maintenance history.
3. Material purchasing may refer to actual maintenance work only when the state
   agrees. Completed work can support received and paid material; work marked
   `waiting parts` must remain ordered rather than becoming complete by implication.
4. Pine and River are service and cost centres, not separate companies. A local
   purchase belongs wholly to the district that received it. Shared regional
   support uses the declared 2026 allocation of 55% Pine and 45% River rather
   than dividing every invoice equally.
5. Ternwick's agreed price is USD 180 per approved batch plus USD 0.42 per
   accepted page. The four already settled activities retain their references,
   dates, page counts, and amounts. Acceptance must precede invoice matching.
6. Supplier correspondence and forms need recognizable differences. Trade-desk,
   depot, safety, laboratory, office, records-material, instrument-service,
   field-service, and digitization suppliers must not share one template or
   speaking habit.
7. Invoices must be genuine readable attachments. Search text, PDF bytes,
   metadata date, line arithmetic, order, receipt, and register totals must agree.
8. Internal requisition and payment discussion must not become reply ancestry in
   an external supplier thread. Supplier quotation/order/invoice mail and internal
   request/payment mail remain two related but separate threads.
9. The initial 6,000-message allocation is a ceiling for useful correspondence,
   not a requirement for acknowledgements around every form. The transaction
   documents themselves are the evidence surface.
10. All content remains ordinary environment history. Author review, generation
    means, issue identity, and scenario ownership stay outside participant-visible
    files, mail, PDF metadata, paths, and native source packages.

## Delivered content

| Record | This slice | State or relationship |
| --- | ---: | --- |
| Purchasing histories | 480 | 402 paid, 27 payable, 27 received, 24 ordered |
| Distinct logical messages | 2,325 | 6,443 retained ARWC mailbox copies |
| Source document items | 4,918 | Exact named readers |
| Completed register rows | 6,292 | Thirteen CSV registers |
| Genuine PDF attachments | 885 | 456 quotations and 429 invoices |
| Maintenance-linked histories | 180 | 24 services, 156 material orders |
| Field-stock replenishment links | 60 | Every accepted upstream stock movement |
| Accepted records batches | 12 | All accepted and paid |
| Suppliers | 9 | Nine templates and communication habits |

Every history contains a requisition, supplier quotation, selection decision,
approval, and order. A received history adds an ARWC receipt and, for physical
goods, line-level stock movement. An invoiced history adds a readable supplier
PDF, three-way match, payment request, and payable ledger entry. A paid history
adds one settlement record and cash entry. The 24 contractor histories reuse
their accepted quotation, order, report, and receipt instead of duplicating them.

The 156 maintenance-material histories divide into 132 paid orders linked to
completed work and 24 still-ordered histories linked to work that remains
`waiting parts`. The 96 stock-replenishment histories include all sixty field
stock issues from Pine and River depots. Laboratory, office, safety, records,
and ordinary operational purchases provide the remaining everyday book.

Twelve Ternwick histories retain batch fee and page lines separately. Batches
`TR-26-04` through `TR-26-07` preserve the established accepted amounts of USD
230.40, USD 220.32, USD 235.44, and USD 216.96. Every Ternwick batch has an ARWC
batch-acceptance form before invoice, match, and payment.

The initial allocation is reduced by **3,675** messages, from 6,000 to 2,325.
Paid and payable histories use five purposeful messages across two threads;
received histories use four and still-ordered histories use three. Adding form
acknowledgements would repeat the same authority without creating a new business
event. Attachments and retained mailbox copies do not increase the logical count.

## Finished-content adversarial review

- An early draft would have regenerated the 24 maintenance quotations, orders,
  and receipts. The finished book instead references those exact accepted IDs and
  bytes, so contractor work is paid once and is not counted as a new purchase.
- The first mail layout placed payment replies under supplier quotation threads.
  Finished histories separate the internal request/payment chain from the
  external quotation/order/invoice chain, preventing private approval ancestry
  from being disclosed to a supplier.
- Maintenance material selection initially risked turning a parts order into
  evidence that a waiting work order had finished. The final state check allows
  paid material only beside completed work; all 24 selected waiting-parts orders
  stop at the order.
- Shared purchases initially had only a `REGIONAL-SHARED` label. The finished
  ledger expands each amount to the declared 55/45 Pine/River allocation while
  leaving district-specific invoices at 100% for their receiving district.
- A PDF extraction check found that deliberate visual blank lines are omitted by
  ordinary PDF readers. Search text now follows the parsed text exactly while the
  page retains its visual spacing; all 885 PDFs parse strictly and reproduce their
  declared search surface.
- Supplier drafts shared too much generic invoice wording. Nine templates now
  carry different headings, terms, scopes, and working concerns. The supplier
  profiles and finished samples record those differences without inventing an
  entire external workplace.
- The Ternwick carry-forward was recalculated from fixed batch and per-page lines.
  The resulting totals match all four established settled activities, and no
  optional description work appears as accepted scope.
- Sixty replenishments are joined to the exact Pine and River stock-movement IDs.
  They are later receipts, not relabelled field issues, and their line totals do
  not change the original field book.
- Every matched supplier invoice produces one payable entry. Only the 402 settled
  histories produce a cash entry; payment records never create a second order.

## Validation and limits

`validate_purchasing_stores.py` checks lifecycle chronology and state, roles,
line arithmetic, district allocations, unique references, all 180 maintenance
joins, all sixty field-stock joins, Ternwick terms, mail-thread separation,
attachment identity, register primary keys and digests, invoice/payment/ledger
totals, strict PDF readability and metadata, source audiences, and visible
provenance leakage. The full narrative validator additionally checks RFC 5322
bytes, MIME attachments, retained mailbox membership, document readers, source
package digests, ownership, and native SDL readback bindings.

The book is a substantial ordinary transaction population, not ARWC's complete
statutory accounting system or a bank statement. Tax is explicitly zero in this
fictional source set. Static package and SDL validation do not claim that a
workplace adapter has materialized the records or executed a payment.

Ownership release: `purchasing-stores-2026-09-16/v1`. Every added record is
ordinary environment content; the scenario overlay remains empty.
