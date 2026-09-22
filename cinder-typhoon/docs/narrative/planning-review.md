# Planning slice review: issue 128

Author-only working review. Accepted base: `4a3386c`. The first uncommitted
attempt has been rejected and preserved outside the pack for comparison.

## Findings before replacement authoring

1. Sentence permutations inflated sixteen cases into 5,000 messages. Their
   numeric diversity test did not establish human variation or useful work.
   Replace that correspondence with bounded exchanges carrying actual questions,
   source returns, revisions, and decisions. Record the volume adjustment.
2. Renewal, laboratory, and staffing subjects shared an unrelated water-balance
   model. Use different calculations for consumption, cost comparisons, analytical
   workload, historical cost variance, field capacity, and contract allowances.
3. Spreadsheet cached values rounded intermediate results while formulas did
   not. Verify every formula independently, including inputs, units, rounding,
   source selection, and summary values. Test deliberately corrupted formulas.
4. Early memos cited later workbooks, and received samples were counted as
   reviewed before the actual review. Compare full timestamps and source-document
   availability. A later snapshot register is an author verification source;
   dated in-world input returns must describe the historical records they use.
5. Account information is restricted. Give planners source-owner-approved aggregates,
   without copying private customer identifiers, addresses, or contact data.
   Retain exact source-selection evidence only in author metadata.
6. Merewick is conditional and limited; Talvern has a supplementary Pine
   allowance. Remaining contractual headroom is neither firm supply nor new
   demand. Do not invent reservoir capacity or an allocation rule.
7. W09, W18, W21, W33, and W34 retain their distinct evidence and access routes.
   Ordinary planning may discuss the broader source portfolio; it must not add
   current reserve measurements, control instructions, or finale conclusions.
8. Workbook versions need an actual changed assumption and recorded reason.
   Drafts must contain their contemporary result; issued recommendations must
   identify the reviewed workbook and leave cost estimates as estimates.
9. Recurring speakers use accepted profiles. Extend the eight planners' writing
   notes before authoring; existing laboratory, maintenance, procurement, and
   accounts profiles remain applicable. Review across people and genres.
10. A test function in a module is not discovered by `unittest`. Supply a real
    test case and negative tests. Review evidence must describe checks that ran,
    rather than anticipated verification or fabricated editorial history.

## Finished inventory and volume adjustment

| Measure | Delivered |
| --- | ---: |
| Distinct planning histories | 40 |
| Unique logical messages | 232 |
| Retained sender/recipient mailbox copies | 760 |
| Textual business records | 177 |
| CSV business registers | 5 |
| Workbook families | 40 |
| Actual XLSX files, including eight additional revisions | 48 |
| Source documents: text records, registers, and XLSX files | 230 |
| Calendar occurrences, counted separately | 8 |

The textual records comprise forty input returns, forty draft recommendations,
forty reviews, forty issued recommendations, eight meeting packs, eight meeting
records, and one method note. These are not 230 unrelated projects. The eight
revised demand workbooks change the upper sensitivity from 8% to 10%; earlier
files and contemporary draft results remain available.

The initial 5,000-message allocation is reduced by 4,768. Five exchanges per
history carry the source return, draft question, answer, review, and issued
recommendation. Sixteen meeting notices and sixteen ordinary colleague messages
complete the collection. Further acknowledgements would repeat the same work.
This changes the milestone's approximate 94,000-message planning allocation to
89,232 if all other allocations remain unchanged. The actual accepted pack
increases from 38,721 to 38,953 messages, from 15,277 to 15,507 source documents,
and from 840 to 848 calendars. Retained copies do not count toward those totals.

## Finished-content adversarial review

Demand cases retain separate quarterly household/master and monthly business/
municipal periods. Pine household use is 1,133,746 m³ over 91 days, giving
12,458.75 m³/day. The mixed-period seasonal reference is expressly not a measured
common-day demand curve or water balance. No private account identifiers,
addresses, payment details, or contact preferences enter the planning returns.

The source-owner returns are dated 1 September, before the workbooks and papers.
Accepted snapshot registers are verification sources, not claims that planners
received a 15 September file on 1 September. Each return projects historical
facts available by 31 August. Maintenance selection uses complete update
timestamps; it is a selected-record count, not a reconstruction of all historical
backlog. Laboratory selection separately checks receipt, analysis, and review
times. The narrower August handoff book cannot justify reducing establishment.

Renewal models compare capital, access, and five-year upkeep; no savings in
staffing, failure rates, or service intervals are invented. The Pine sample bench
example gives USD 1,400 to retain against USD 2,500 to replace and still requires
a survey. Four historical projects retain their accepted scope and handover
amounts; a 15% uplift is a sensitivity, not a supplier quote or spending approval.

Merewick's three accepted deliveries total 2,250 m³ and USD 2,070; 17,750 m³ is
uncalled contractual headroom, not available supply. Talvern totals 1,570 m³ and
USD 1,805.50, leaving 5,930 m³ under its supplementary seasonal ceiling. Both
agreement periods and acceptance boundaries remain intact. No common district
ownership percentage is substituted for actual consumption. Cairn Reach remains
one reserve within a wider portfolio; no current allocation, operational setting,
source capacity, or finale calculation is introduced.

The 170 formula cells were independently evaluated from actual Office input
cells with decimal rounding and compared to their cached values, units, previews,
drafts, issued summaries, and result register. This caught a real half-cent
rounding error: 436.5 × 0.95 rounds to 414.68, not 414.67. The corrected file and
a direct regression test preserve that result. Eleven representative workbooks,
covering every model family and the rounding correction, also opened through
an independent Office reader. No desktop spreadsheet rendering is claimed.

The writing review compared source returns, peer questions, formal papers,
meeting notes, and ordinary exchanges across all eight planners. Controlled
record forms remain consistent; mail follows the speaker's accepted habits.
Corrections removed repeated explanatory closings, restored proper names, and
changed Hana's self-reference to first person. Nadia's explanation and lunch
overplanning differ from Idris's short interventions, Imani's dated handovers,
Iris's attachment checks, and Isabel's small questions. Source owners speak
within their accepted roles; all 32 department staff are not forced into a
planning conversation. No language proficiency is inferred from names.

Meeting papers cover all forty histories once. Records follow the actual event
end and reproduce its start/end times; an invalid minute rollover was corrected
before delivery. Forty follow-up actions remain open for 30 September. Issuing
a recommendation or accepting a comparison basis does not close those actions
or authorize implementation.

The native source packages retain exact readers, original logical ownership,
content-digest versions, and the existing readback requirements. New ownership
entries cover the four authoring sources and archive; the accepted ownership
order and all prior entries remain intact. Scenario additions/replacements stay
empty and no challenge, dependency, evidence route, or technical section changes.
Temporary authoring tools and the rejected draft remain outside the pack.

## Verification

The focused `unittest` suite runs four test methods, including fourteen content
mutations and three checksum-consistent binary mutations. It rejects incorrect
source totals, periods, units, source/assumption classification, visible returns,
dates, readers, attachments, reply ancestry, draft and issued summaries, late
workbooks, meeting times, and design leakage. The binary mutations independently
change a formula, its cached result, and a future action's state. A checksum
update cannot hide any of those errors. Formula parsing also rejects executable
expressions outside the supported arithmetic subset.

Completed checks use Python 3.12.13 with the pinned RAE 5.0.0 and env-packs 6.1.0
requirements:

- Four planning test methods, including seventeen corruption cases, pass.
- The existing narrative-integrity test passes all eight corruption cases.
- All 116 rendered outputs reproduce byte-for-byte.
- Full asset validation passes for 38,953 messages, 15,507 documents, 294
  employees, and eight native source collections.
- The default env-packs author check passes; RAE parses all 96 modules.
- The native model preserves 240 challenges, 33 capabilities, 36 targets plus
  Kali, nine subnets, and 83 authority domains. All 1,209 minimal prerequisite
  closures and sixteen finale routes replay successfully.
- Instantiation and compilation preserve 3,450 realization requirements and
  281 observation bindings, including the eight workplace collections. The
  exact Kali intent, default-open posture, fifty technical drafts, record
  ownership, and six consequence contracts pass their checks.
- All four type-valid narrative SDL corruption tests reject the altered models.
- Vale 3.9.1 passes all six changed Markdown files; the diff has no whitespace
  errors.

The remaining campaign-wide negative tests are still running; this review will
record their result before the pull request leaves draft state.

Local bytecode caches were moved outside the pack, and verification ran with
`PYTHONDONTWRITEBYTECODE=1`. The default pack-member limit was not raised.
These are static content checks, not runtime deployment proof or evidence that
the fictional engineering and staffing assumptions are accurate forecasts.
