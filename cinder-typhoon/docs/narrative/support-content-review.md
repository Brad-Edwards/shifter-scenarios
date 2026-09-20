# Support intake and onboarding review: issue 114

Author-only record. Opening state: 08:30 on 16 September 2026, UTC−04:00.

## Before authoring

The accepted business slice supplies twelve active FieldKest utility customers,
stable account IDs, contract effective dates, account owners, and 36 named
customer contacts. The workforce slice supplies fourteen people in Support and
implementation. Maya and Talia retain their established profiles; every other
team member already has a workforce writing note and authored correspondence.

The existing Rillhaven maintenance workshop remains confirmed for 24 September.
It is still future at the snapshot. Support intake may contain earlier account
orientation and ordinary implementation work, but it must not turn that meeting
into a completed event or invent a second September workshop.

The initial adversarial review identified six concrete risks:

1. One mail reply chain containing both private triage and customer replies would
   expose internal Message-IDs and create an implausible reply history. Each case
   therefore has separate customer-visible and internal thread roots, counts,
   and last messages.
2. Cases generated without the accepted account book could precede entitlement
   or assign the wrong account owner. Every case joins its organization, account
   ID, effective date, customer contact, and accepted account owner.
3. A downstream engineering slice could mistake “accepted for assessment” for a
   fix. Engineering escalations use stable `ENG-2026-001` through
   `ENG-2026-030` references and explicitly record no fix, acceptance result, or
   release date.
4. A customer article or routine outcome selected independently of its topic
   could be internally valid but wrong for that case. Topic-to-article and
   topic-to-outcome joins are explicit and validated through the case record,
   attachment, mail, and document source.
5. Repeated onboarding labels could make one customer appear to be introduced
   several times. Repeat engagements now distinguish a new-team introduction,
   reviewer orientation, refresher, or seasonal handover. Rillhaven has no new
   scheduled September workshop.
6. Exact-message uniqueness alone would hide templated prose. The finished
   review removes case/change IDs, versions, and signatures before measuring
   diversity, and caps the most common normalized body.

## Finished content

The source contains 500 cases across all twelve customers. Ownership is balanced
across all fourteen support and implementation staff: each owns 35 or 36 cases.
Each customer has 41 or 42 cases. Cases use FieldKest 4.8.2, 4.9.0, or 4.9.1 as
observed versions; those identifiers are stable inputs for later engineering,
quality, and release work rather than release claims made here.

| Case class | State at snapshot | Count |
| --- | --- | ---: |
| Routine support | Resolved within support | 300 |
| Customer-waiting | Open pending a named customer item | 60 |
| Implementation | 50 complete; 20 scheduled | 70 |
| Engineering escalation | Accepted for assessment; unresolved | 30 |
| Onboarding and enablement | 28 complete; 12 scheduled | 40 |
| **Total** | 378 complete; 122 deliberately open or future | **500** |

The 5,500 new logical messages produce 8,059 retained mailbox copies. A message
crossing from KeplerOps to ARWC still has one logical identity even though both
companies retain it. All 5,500 bodies are byte-distinct. After removing case and
engineering IDs, product versions, and signatures, 3,424 bodies remain distinct;
the most frequent normalized body occurs 25 times. This is a diagnostic against
uniform prose, not a claim that ordinary acknowledgement language never repeats.
Five hundred compact service-desk notices record case, account, state, version,
and scope in a consistent machine voice without claiming closure.

The document source adds 578 records:

- 500 internal case records containing entitlement, observed version, prior
  attempts, status, result, next action, and visibility boundary;
- 24 customer-safe knowledge articles;
- 12 account-specific onboarding packs;
- 12 account-specific implementation-readiness records; and
- 30 bounded engineering observation packets with no proposed resolution.

Exactly 500 messages carry attachments: 470 customer-visible knowledge,
onboarding, or implementation documents, plus 30 internal engineering packets.
No case record is attached to mail. Customer-safe materials travel as exact MIME
attachments; their retained library masters remain readable only by the named
KeplerOps staff. Engineering case records and packets add Rowan as a reader, but
ordinary case records do not widen to Product engineering.

There are 64 calendar items: all 40 onboarding histories and 24 implementation
histories have an appointment. Completed-case appointments fall between opening
and last activity. The 32 scheduled-state appointments occur after the snapshot.
The previously established `rillhaven-workshop` stays confirmed for 24 September
and is not claimed complete by this slice.

## Editorial and consistency pass

The first completed draft exposed an actual topic-join defect: some routine
cases attached a valid but irrelevant knowledge article or recorded an outcome
from another topic family. Explicit mappings now keep date-display guidance with
date cases, stable-reference guidance with archive cases, and so on. A later pass
found repeated onboarding purposes and the Rillhaven collision described above;
both were corrected before acceptance.

Customer messages use the previously reviewed direct, brief, careful, practical,
plain, curious, formal, and warm correspondent habits. Internal staff retain
their workforce writing notes, with exact samples recorded in
[support-voices.md](support-voices.md). The collection includes concise status
notes, corrections, customer questions, longer onboarding exchanges, and open
threads. It does not inject random spelling errors or force a joke, apology, or
tidy lesson into every exchange.

A visible-text scan found no scenario names, challenge labels, authoring
instructions, repository references, or ownership-layer terminology in the new
mail and documents. Case topics concern normal supported work. They neither
plant challenge evidence nor change a challenge route, credential, service, or
technical weakness.

## Delivery evidence

| Measure | This slice | Pack total |
| --- | ---: | ---: |
| Distinct logical messages | 5,500 | 8,575 |
| Retained mailbox copies | 8,059 | 13,229 |
| Case/work-item records | 500 | 500 in this slice |
| Source documents | 578 | 822 |
| Calendar invitations | 64 | 85 |
| Stable unresolved engineering escalations | 30 | 30 |
| Native content declarations | 0 added; eight updated | 8 |

The existing eight native content declarations retain their node owners,
`realization: {default: open}`, service-materialization requirements, and
observed readback contracts. Updated SHA-256 source versions bind the exact mail,
document, directory, and employment packages. The ownership inventory assigns
all new source and generated records to the reusable environment release; the
scenario overlay remains empty.

Static checks reproduce RFC 5322 and RFC 5545 bytes, attachment versions,
mailbox copies, reader sets, case/account/thread joins, entitlement dates,
appointment chronology, stable escalation IDs, document families, source
digests, and compiled SDL placement. They do not claim a deployed workplace
adapter or runtime readback.
