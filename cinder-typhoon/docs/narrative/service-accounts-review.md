# ARWC service accounts review: issue 122

Author-only review. Accepted base: `5eeba5c`, including the business relationships
from `ef9c89f`. Snapshot: September 16, 2026, 08:30, UTC−04:00.

## Review before authoring

1. The provisional 60,000 residential accounts conflates dwellings with bills.
   Use 60,000 occupied dwellings: 48,000 individually served homes and 12,000
   apartments in 480 master-metered buildings. These support 160,000 residents,
   using integer building occupancy estimates, without identifying residents.
   This gives 48,480 residential accounts, plus 1,500 commercial and 120 municipal
   accounts. Municipal buildings are water customers, not an additional population.
2. Reconcile Pine and River separately. Pine has 27,000 individual homes and
   270 apartment buildings, serving 90,000 residents; River has 21,000 homes
   and 210 buildings, serving 70,000. More residents need not mean an equal
   share of accounts or demand. Service points determine the district.
3. A building master meter must not be billed again through its private check
   meters. Parallel supply meters can both be billed. Distinguish these physical
   arrangements explicitly. Historical replacements need non-overlapping
   installation intervals, paired removal/installation readings, and continuity
   of the service point, without pretending the new register continues the old.
4. Opening balances need invoices, priced reading intervals, receipts and
   allocations. Declare USD, water-only tariffs, fixed-charge units, period
   boundaries, rounding and effective dates. Exclude wastewater and tax from
   this fictional tariff. An unpaid opening invoice is not automatically overdue.
5. Preserve `A-B-001` for Belvarn's River plant and `A-B-002` for Talvern's Pine
   shared facilities. Talvern's discretionary June–September allowance remains
   7,500 m³ at USD 1.15/m³. Its three accepted delivery records already exist;
   meter readings and retail entries must represent those deliveries once.
   Do not turn its allowance into household service or a guaranteed supply.
6. Retail meters are distinct from reservoir process tags and allocation exports.
   No retail record changes `ALLOC-2026-09-W3`, `MWO-7742`, `SUP-2841`, the active
   tenant, engineering revisions, challenge access paths or the snapshot state.
7. Staff roles need separation. Rosa and named customer-contact colleagues handle
   accounts; Amara and named accounts officers reconcile balances. Procurement
   does not gain the household register. Field readers need service points and
   meters, not names, account balances or customer contact preferences. Customers
   receive only their own extracts, never a register attachment.
8. Create original names and fictional local addresses, with reserved `.test`
   customer email domains. Do not import people, census microdata or addresses.
   Population is a planning estimate, not an assertion that all residents hold
   an ARWC login. New recurring voices need profiles and samples first.
9. Deliver completed CSV collections, correspondence and reference documents.
   Existing native document collections can carry exact CSV bytes with distinct
   readers, stable source versions and digest readback. Do not create 50,100 SDL
   account entities or a customer-data generator. Keep provenance and review
   records outside reachable content.
10. Target 1,560 meaningful messages: 240 four-message account histories and
    600 opening-statement notices. Each history must need the clarification it
    contains; notices must carry a real account-specific statement. This reduces
    the working allocation by 1,040, with no count credit for attachments,
    register rows, or retained copies. Review human prose across case types;
    consistent automatic statement wording is appropriate for that medium.
11. The accepted pack nearly fills its member limit. Consolidate the 64 redundant
    support calendar review files into their already-existing native items,
    preserving every calendar byte and reader. Verify earlier native records
    and mailbox memberships against the accepted base before delivery.

## Finished-content review

The completed slice contains the following distinct records. Rows in a CSV are
business records; they are not messages or individual SDL entities.

| Record | This slice | Full narrative corpus |
| --- | ---: | ---: |
| Logical messages | 1,460 | 27,850 |
| Retained mailbox copies | 1,460 | 49,929 |
| Source document items | 872 | 7,428 |
| Calendar occurrences | 0 added | 638 |
| Native source collections | 0 added | Eight |
| Native packaged items, including calendars/directories | 2,332 added | 36,550 |
| Completed CSV tables | 17 | This slice |
| CSV business records | 696,987 | This slice |

The 872 document items comprise 17 CSV datasets, 600 customer statements, 240
restricted case records, seven representative service agreements, four current
standard-terms references and four staff reference guides. Statements are
rendered Markdown documents with actual invoice lines and balances. They are
not PDFs or a claim that a later billing application has already been deployed.

## Population and service model

| Measure | Pine | River | Total |
| --- | ---: | ---: | ---: |
| Individually served homes | 27,000 | 21,000 | 48,000 |
| Master-metered buildings | 270 | 210 | 480 |
| Apartments in those buildings | 6,750 | 5,250 | 12,000 |
| Occupied dwellings | 33,750 | 26,250 | 60,000 |
| Estimated residents | 90,000 | 70,000 | 160,000 |
| Residential billing accounts | 27,270 | 21,210 | 48,480 |
| Commercial accounts, including Talvern | 850 | 650 | 1,500 |
| Municipal facilities accounts | 60 | 60 | 120 |
| All billing accounts | 28,180 | 21,920 | 50,100 |
| Service points | 28,360 | 22,100 | 50,460 |

Individually served homes have two or three estimated residents. Apartment
buildings contain 25 occupied dwellings and 63 or 64 estimated residents.
The resulting overall occupancy is 2.667 residents per occupied dwelling.
These are fictional planning estimates, not individually identified residents.
No resident census, demographic profile, phone number or imported address data
is included. Supporting mail addresses use `.test`; the two company domains
remain unchanged.

The provisional 60,000 residential accounts become 60,000 dwellings served by
48,480 residential accounts: 11,520 fewer bills because the 12,000 apartments
receive 480 building-level bills. The 1,500 commercial accounts are retained;
120 separately billed municipal facilities accounts make public water customers
explicit. The opening customer register has one customer ID per payer account.
It does not assert that municipal cost centres are separate legal districts.

Three hundred business accounts and sixty municipal accounts each serve two
points, split evenly between Pine and River. Six hundred points have parallel
supply meters: 340 in Pine and 260 in River. Another 150 building-owned check
meters sit downstream of master meters. There are 51,060 active billing meters,
150 active check meters and 120 retired meters: 51,330 device records overall.
The check meters are never billed. Each parallel point has one fixed charge,
with both independent measured feeds counted once.

## Opening records and arithmetic

| Table | Rows |
| --- | ---: |
| Accounts | 50,100 |
| Contacts | 50,100 |
| Service points | 50,460 |
| Account-service relationships | 50,460 |
| Meters | 51,330 |
| Readings | 153,873 |
| Tariff versions | 10 |
| Billing periods | 17 |
| Invoices | 50,102 |
| Invoice lines | 101,641 |
| Receipts | 18,872 |
| Allocations | 18,872 |
| Opening balances | 50,100 |
| Current preferences | 50,100 |
| Authorized changes | 110 |
| Account cases | 240 |
| Opening-statement deliveries | 600 |

The financial opening is July 1, 2026, at 18:00, UTC−04:00. Its totals are:

- Invoices: USD 5,825,928.15.
- Receipts: USD 1,949,089.94.
- Allocated receipts: USD 1,876,209.94.
- Unapplied credit: USD 72,880.00.
- Outstanding invoices: USD 3,949,718.21.
- Net account balance: USD 3,876,838.21; overdue at opening: USD 0.00.

There are 31,230 unpaid accounts, 10,021 paid accounts, 5,205 part-paid accounts
and 3,644 credit accounts. Invoices derive from fixed-charge units and exact
reading differences. The receipt register and allocation register explain the
balances; there are no arbitrary balance-forward numbers or invented penalties.
Quarterly and monthly July 1 invoices are due July 21, so an outstanding opening
amount is not automatically overdue. USD, zero tax and water-only charges are
explicit features of this fictional rate model, not claims about Canadian law.

Two additional invoices, receipts and allocations preserve Talvern's accepted
July 2 and July 20 deliveries. They are excluded from July 1 opening balances.
The June 12 delivery is part of the opening. The three accepted quantities and
amounts remain 450/620/500 m³ and USD 517.50/713.00/575.00. They consume 1,570 m³
of the 7,500 m³ seasonal ceiling; the remaining 5,930 m³ is conditional capacity,
not a reservation. Belvarn retains its River plant and standard metered business
tariff. Neither account is confused with ARWC's FieldKest customer contract.

The dataset is an opening register with selected later account changes and the
three accepted Talvern deliveries. It is not a complete July–September retail
billing run. Future period rows establish stable identifiers and schedules;
they do not assert that future readings or invoices exist. Current preferences
include consented changes through September 7; historical opening statements
remain unchanged after those changes.

## Editorial and adversarial findings resolved

- The initial draft placed all meter exchanges at one instant. The finished
  120 exchanges run May 4–June 12, four per weekday, with paired removal and
  installation readings. Installation dates for the wider estate span earlier
  years; device serial prefixes agree with those years. Period-boundary reads
  are explicitly remote register snapshots, not thousands of simultaneous visits.
- The first distribution concentrated multi-site business relationships in Pine.
  Both districts now contain multi-site accounts and parallel supply points.
  District assignments, population totals and invoice ownership are checked
  independently rather than inferred from postal descriptions.
- Fifty explanatory histories did not need clarification. Their final versions
  contain a question and a direct answer. The other 190 histories retain the
  substantive authorization or evidence question needed to complete the change.
  This removed 100 unnecessary messages from the pre-authoring target.
- Customer requests have 240 distinct full bodies and case-specific circumstances.
  The finished 1,460 messages have 1,209 distinct full bodies. Short consent
  replies and standard service explanations repeat where the work warrants it;
  automatic notices use a consistent format with a real statement attached.
  No extra acknowledgement is required after a statement notification.
- Rosa, Tamsin and Tariq ask accessible account questions. Amara and Anika trace
  receipts without requesting bank details. Lila's plant explanation identifies
  packing-hall and washdown feeds. Supporting customer names do not determine
  fluency, ethnicity or a stereotype. Original cast profiles remain authoritative.
- Ten name-spacing corrections preserve the old display in the opening statement,
  the customer's correction in the thread, and the stable customer ID in the
  current register. A postal instruction never changes service responsibility.
  Large-print and delivery preferences do not create charges or additional readers.
- Ten requested paper copies remain queued. Case closure records the queue action,
  not dispatch or receipt. Routine contact windows are explicitly preferences,
  not booked visits or a reason to withhold urgent service information.
- The 600 opening-statement emails have explicit one-off consent and recipient
  records. This is distinct from ongoing bill delivery. Each includes only its
  own account statement. Bulk registers are never customer attachments.

Representative reading covered requests and replies in every one of the 24
case categories, residential/master/business statements, a municipal statement,
both named commercial schedules, and the staff guides. Example threads are
`ARWC-CS-2026-0001` (paper billing), `0101` (private check meter), `0111`
(Belvarn's two feeds), `0131` (meter exchange), `0151` (unapplied credit),
`0172` (postal versus service district), and `0211` (name correction).

## Volume adjustment

The issue allocated approximately 2,600 logical messages. The final **1,460**
comprise 760 messages in 190 four-turn histories, 100 messages in 50 direct
explanations, and 600 actual opening-statement notices. The reduction is
**1,140 messages**. It remains unallocated, rather than being filled with
customer acknowledgements or count credit for 696,987 CSV rows.

Delivered milestone correspondence increases from 26,390 to 27,850. This adds a
1,140-message reduction to the earlier slices' documented adjustments. Applied
in isolation to the roughly 94,000-message working allocation, it would be
92,860; it does not reverse earlier adjustments or declare the milestone done.

## Native source, ownership and readback

The existing `narrative-arwc.documents` dataset on `a-corporate.a-business`
contains the seventeen table items, each with its own readers. Its source name
is `cinder-typhoon/narrative/arwc-documents`; the catalog binds the source version
to the actual package SHA-256. `narrative-arwc.mail` carries the exact RFC 5322
messages, reply ancestry, attachments and mailbox memberships. No per-account
SDL objects, nodes, access routes or challenge identities were introduced.

The source JSON uses `cinder-document-library/v3` for optional gzip encoding of
binary CSV bytes. After base64 decoding and decompression, the SHA-256 must
match the CSV bytes retained in `service-account-records.zip`. Uncompressed
finance items and text records retain their previous representation. Native
collection readback still requires canonical content digests, the named service,
exact item readers, and rejection of unowned collisions. Search descriptions
have the same readers as the CSV they describe.

Rosa, Soren, Tamsin, Tariq, Amara and Anika are the named retail readers. Theo
and Mina additionally read service points, meters and readings. Priya receives
rate/period references and the two commercial schedules, not household contacts,
balances or case records. No KeplerOps employee or general staff reader gains
access to the retail records. External statement recipients do not become staff
identities or collection readers.

All 34,218 previously accepted native records retain their exact item content,
readers and earlier mailbox memberships. The 64 redundant support calendar
review files are removed from the filesystem; every corresponding native ICS
item remains byte-identical. There are still 638 calendar occurrences. This
consolidation leaves the pack below the pinned 1,024-member limit.

Ownership release: `service-accounts-2026-09-16/v1`, based on `5eeba5c`, retaining
all earlier accepted-base references and adding office-life commit `e0213f1`.
The ownership record, writing notes, counts and review remain author-only.
The scenario overlay adds and replaces nothing. The technical challenge graph,
evidence, access routes, snapshot and `realization: {default: open}` are retained.

## Verification

Final results are recorded here after the full pinned checks finish. Runtime
materialization, customer portals, live meter collection and outbound delivery
are outside this static content validation.
