# Enterprise content requirements

Planning draft, 19 September 2026. This document specifies the complete
enterprise-content programme; the [workforce slice](workforce-review.md)
realizes its population and employment-record portion, the
[business slice](business-content-review.md) realizes customer, supplier, and
contract references, and the [support slice](support-content-review.md) realizes
support intake, onboarding, appointments, and unresolved engineering escalations.
The [generation plan](content-generation-plan.md) records earlier sizing proposals.
The pack now contains 8,575 messages and 822 source documents, including the
earlier story collection. Other departmental business histories remain future
content work.

## A reusable world

KeplerOps and ARWC must make sense as employers and businesses independently of
any particular CTF. Their people buy things, deliver work, arrange meetings,
maintain equipment, support customers, change their minds, and finish ordinary
tasks. A participant following those activities should find related records in
the places the people doing the work would use.

The company histories, cultures, relationships, and eight ordinary stories in
this directory belong to the environment. Cinder Typhoon's required clues,
deliberate weaknesses, challenge-specific changes, flags, and triggered effects
belong to a separate scenario layer. Another scenario must be able to reuse the
companies without inheriting Cinder's events or exposing its solutions.

| Requirement | Required outcome |
| --- | --- |
| ENV-01: population | All 294 employees exist in a consistent directory and organization model: 64 KeplerOps and 230 ARWC. Preserve the fourteen named employees and Jules as an external contractor. Develop the remaining 280 employees with coherent jobs, managers, teams, tenure, schedules, and communication habits. |
| ENV-02: business coverage | Every department has its own working records and connections to other departments. The twelve headcount groups below remain the population budget; subdivisions are not extra employees. |
| ENV-03: history | Develop roughly three months of substantial recent activity, plus selected older projects, policy versions, employment history, and company records. Preserve the 16 September 2026 opening snapshot and already established chronology. |
| ENV-04: consistent work | Shared people, organizations, products, projects, service points, equipment, contracts, orders, amounts, dates, and business states agree across the records that reference them. |
| ENV-05: actual content | Documents contain useful prose, tables, calculations, and decisions. Repositories contain coherent project material. Attachments open in their advertised formats. Generated size alone is not coverage. |
| ENV-06: ordinary distribution | Include successful work, routine requests, short acknowledgements, recurring processes, quiet periods, incomplete work, and modest frustrations. Neither company exists in a permanent crisis. |
| ENV-07: natural visibility | Mailbox membership, groups, document access, calendars, publication status, and historical roles determine who can see what. A staff directory is broad; personnel files and private correspondence are not. |
| ENV-08: reusable ownership | Every source record and generated artifact has author-only environment or scenario ownership. Scenario changes reference a pinned world baseline and identify their additions or replacements. |
| ENV-09: no design leakage | Participant-visible content, filenames, headers, document properties, paths, application fields, and search results contain no authoring labels, challenge mappings, generation instructions, or solution annotations. |
| ENV-10: build-time history | Generate and freeze the history before deployment. The enterprise content must not require an ongoing population of agents or an expensive live company simulation during the event. |

The workforce slice implements the 294-person population, its current reporting
tree, selected employment history, and separate directory and personnel readers.
The broader business histories and full documentary scale remain to be built.

## KeplerOps: 64 employees

### Product engineering: 22

Develop several enduring workstreams around FieldKest: customer integration,
connector maintenance, data validation, usability, and maintainability. Work
should span multiple customers; ARWC is important but does not consume every
engineer's day. Rowan is one contributor among colleagues with their own work.

Required records include repository source and ordinary commit history, issues,
design notes, review discussions, examples, test fixtures, developer setup
instructions, dependency decisions, documentation changes, and work estimates.
Some requests are declined or deferred with a reason. Old documentation can be
superseded by a linked current version. A README should describe the project in
the world, not how an event organizer seeds it.

A completed feature should connect a customer or product request to an issue,
design decision, implementation change, review, test result, and release note.
Every routine issue need not have a design memo. Personal correspondence and
team chatter should be mixed with actual work, with short replies where useful.

**What should convince a reader:** the release note describes behavior they can
recognize in the code and examples; reviewers recur for sensible reasons; a
decision made weeks earlier explains today's implementation and workload.

### Support and implementation: 14

Populate customer organizations, contracts and contacts, service cases,
implementation projects, migration appointments, workshop preparations,
knowledge articles, customer replies, and closure records. Maya and Talia retain
their existing relationship and workshop history. Other employees own other
customers and schedules.

Cases need varied lifecycles: answered on first contact, clarified, passed to
engineering, waiting for the customer, resolved, or reopened for a specific
reason. Implementation work includes agendas, customer prerequisites, accepted
deliverables, and practical follow-up. Working hours, cover arrangements, and
response expectations should be evident without every message quoting a policy.

An engineering escalation should refer to the same product version and symptom
as the case. A fix notification should follow the relevant release. Workshop
invitations, outlines, and participants must agree. Customer-visible replies
must not automatically disclose internal estimates or private discussion.

**What should convince a reader:** a customer's history continues across cases;
staff know what was tried before; completed work is demonstrably closed.

### Platform and release: 7

Create release calendars, build and deployment histories, service inventories,
ordinary change requests, release checklists, maintenance notices, backup and
restore-check records, capacity discussions, and on-call handovers. Evan and
Noor should appear in this work without becoming the only people who do it.

Most release and maintenance records should concern successful, unremarkable
work. Include a small number of routine deferrals or failed builds with an
ordinary explanation and subsequent resolution. Automated notifications should
have the compact, repetitive format of their producing system, with values
derived from the same records as the human summaries.

Tie release artifacts to existing repositories and version history. A scheduled
maintenance window should appear in affected staff calendars and appropriate
customer notices. A backup check should refer to a real declared application
dataset, not an invented server added solely to make a note sound technical.

**What should convince a reader:** ordinary service operation supports the work
elsewhere in the company, and the records distinguish a plan from its outcome.

### Product management and quality: 8

Develop roadmaps, intake decisions, research notes, acceptance criteria, release
test plans, test results, compatibility matrices, documentation reviews, and
meeting decisions. This group's work should expose the company's tension
between reusable product improvements and bespoke customer requests.

Record tradeoffs without making one function foolish. A useful customer request
can be deferred for capacity; an unglamorous reliability improvement can be
approved. Test cases should correspond to actual product behavior. Defect
closures should point to the relevant change and reviewed result.

Meeting notes should preserve decisions, open questions, and owners. Some
scheduled discussions end without a decision; those do not get fabricated
approvals. Roadmap dates evolve through recorded revisions rather than every
document showing the final plan from the outset.

**What should convince a reader:** the company's priorities have a history and
consequences for engineering, release, support, and sales.

### Commercial: 6

Create an account register reflecting roughly twelve substantial utility
customers, plus a modest prospective pipeline. Develop account plans, proposals,
renewal correspondence, statements of work, pricing worksheets, reference-call
arrangements, contract amendments, and handovers to implementation.

Customers, contract terms, renewal dates, and delivery commitments should agree
with support and finance. An accepted proposal can become a scoped project;
an unsuccessful bid can simply remain unsuccessful. A sales conversation must
not silently create a promise engineering has already rejected.

The existing ARWC reference-call exchange should be part of a longer ordinary
customer relationship. Commercial material needs its own confidentiality and
audiences; an internal margin discussion is not a customer attachment.

**What should convince a reader:** this is a specialist with a manageable account
portfolio, not a mass-market business with thousands of inexplicable customers.

### Leadership and business operations: 7

Treat finance, people operations, purchasing, office administration, and leadership
as functions within this small team. Staff may cover more than one function.
Create operating plans, management decisions, budgets, vendor purchases,
subscription and project invoices, receivables, expenses, payment records,
reconciliations, and employment administration.

KeplerOps' customer invoices must follow its contract billing schedules. Twelve
substantial customers do not produce thousands of unrelated subscription
invoices in a quarter. More volume can legitimately come from expenses,
supplier transactions, invoice lines, and system records. The financial model
must remain compatible with the established profitable, self-funded company.

People and office records include recruitment plans, role descriptions,
onboarding tasks, equipment requests, learning arrangements, leave coverage,
hybrid-work guidance, room bookings, office notices, and anniversary planning.
Personnel documents remain restricted. Staff announcements reveal only what
employees would appropriately share.

**What should convince a reader:** decisions about hiring and accepting work
appear later in staffing, delivery capacity, purchasing, and company updates.

## Alterra Regional Water Company: 230 employees

### Operations, treatment, and distribution: 94

Develop plant teams and distribution crews with credible rosters, supervisors,
assignments, and equipment. Their documentary lives rely on shift and field
records as well as mail. Do not give every operator an office worker's meeting
load or constant chat activity.

Required content includes shift handovers, routine operating summaries, rounds
and inspection records, field assignments, meter visit outcomes, maintenance
requests, service appointment notes, stock usage, vehicle bookings, and training
records. Treatment and distribution are related but distinct work. Owen's
supervised learning should reflect his distribution role; Mina's orientation
help does not make her his instructor for every practical assignment.

A field visit should have an appointment or assignment, an assigned crew,
an outcome, and appropriate updates to the service or asset record. A routine
maintenance request should reach the maintenance team. Handover notes should
refer to the state known on that shift. Include uneventful shifts and completed
work; these records do not need to forecast a reservoir incident.

**What should convince a reader:** people can carry on the next shift using what
the previous shift left, and field work has consequences in business records.

### Maintenance and engineering: 48

Create equipment registers, inspection schedules, work orders, job plans,
parts requests, contractor bookings, condition reports, technical drawings,
engineering notes, estimates, commissioning records, and project handovers.
Use several existing logical sites and asset families; routine work must not
all concern Cairn Reach or the finale's equipment.

A work order can join an operations request to a planner's decision, available
parts, a contractor appointment, a service report, acceptance, and an invoice.
Not every job requires every step. Routine inspections and small repairs
should be common; major capital work should have longer, richer histories.

Separate approved drawings from working revisions. Register versions and
effective dates consistently. Keep ordinary equipment documentation independent
of challenge-specific operational states. Physical model fidelity for a future
challenge remains outside this content plan.

Theo and Clara should have technical colleagues and contacts beyond the named
cast. Supplier material should have the supplier's formatting and perspective,
while company acceptance records reflect ARWC's own process.

**What should convince a reader:** a maintained asset has a service history,
costs, responsible people, and documents whose revisions can be followed.

### Planning, quality, and compliance: 32

Develop distinct planning, laboratory, quality, and reporting work within this
headcount. Create demand and resource-planning workbooks, seasonal assumptions,
sampling schedules, sample registers, routine results, review records, equipment
service records, reporting calendars, internal quality reviews, and training.

Laboratory records should connect sample identity, collection, receipt, analysis,
review, and the appropriate report. Most results can be ordinary and accepted.
Data should follow an internally consistent fictional specification; technical
limits must not be invented independently by a prose model or presented as
real regulatory guidance.

Planning spreadsheets need meaningful inputs, formulas, units, and totals.
Approved planning assumptions should match the relevant version of the
management summary. Questions from operations can produce clarifications;
internal quality review can improve a form without becoming a misconduct story.

Nadia's work, laboratory colleagues' professional lives, and the photography
competition should coexist. The laboratory is not just a source of reports for
other protagonists.

**What should convince a reader:** the management summary is traceable to
working material, and a laboratory result belongs to a sample and review history.

### Information technology: 12

Create an application and service inventory, equipment assignments, user-service
requests, ordinary account lifecycle records, support knowledge, planned changes,
maintenance schedules, backup checks, vendor service reviews, and internal
communications. Access groups should correspond to actual business duties.

Normal joins include a new starter's approved role, equipment assignment,
access request, completion, and induction appointment. A team move should change
the employee's current role without rewriting their historical authorship.
Restricted support and administration records should not be readable by all
employees simply because the files are useful to an author.

Keep product-specific implementations consistent with the selected technical
design where one exists. This plan defines records and relationships, not new
servers, purchased software, or unapproved network access.

**What should convince a reader:** IT supports identifiable people and services,
and ordinary records explain how the rest of the enterprise gets its work done.

### Customer service and business support: 36

Develop customer accounts, service points, meter relationships, billing periods,
appointments, contact preferences, case histories, procurement, supplier records,
records management, and everyday correspondence. Separate retail billing,
accounts payable, purchasing, and reception/records responsibilities within the
team. Rosa and Priya should have colleagues who perform those adjacent functions.

Retail records need scale consistent with approximately 160,000 residents plus
commercial users. Residents, billing accounts, service points, and meters are
different entities. Decide a fictional housing and service-account model before
generating counts. Apartment buildings and organizations can have relationships
that differ from a single household with one meter.

Bills must derive from the declared tariff and readings for the relevant period.
Adjustments, payment allocation, and balances must reconcile. A contact case can
refer to a real invoice and lead to an explanation or appointment. A generated
bill is ordinary business content even if a later scenario chooses to use it.

Procurement needs requests, quotations, approvals, purchase orders, receipts,
invoice matching, and payment handoff. Records management needs classification,
retention metadata, accepted scanning batches, and revision history. Public
correspondence should use accessible language; not every staff note uses that
same polished register.

**What should convince a reader:** the invoice on screen agrees with the
customer's account and the explanation in their correspondence; a supplier's
payment follows the accepted work and correct cost centre.

### Leadership and finance: 8

Create board and management calendars, agendas, selected meeting papers,
minutes, service plans, budget workbooks, capital programme summaries,
district cost allocations, month-end records, financial statements, decisions,
and public-reporting drafts and releases.

Distinguish the board's governance from management's operating decisions.
Luc reports to the general manager; he is not the company's entire leadership.
Pine and River allocations should follow the fictional funding and accounting
model consistently rather than defaulting to equal division in every document.

Published material should have an approval and publication history. A proposed
project is not already committed expenditure. Financial summaries should derive
from the same underlying ledger as purchasing and customer billing, with
explicit opening balances for periods outside the detailed history.

Workforce development, employee recognition, and succession planning should
appear alongside capital and financial work. Established projects and public
service improvements supply positive history.

**What should convince a reader:** the organization can explain its plans,
decisions, expenditure, and service outcomes to its owners and customers.

## Shared workplace surfaces

Each company needs an intranet with its own voice and visual conventions.
KeplerOps should emphasize product updates, demonstrations, useful how-to pages,
customer successes, and company discussion. ARWC should emphasize service and
staff notices, project updates, procedures, training, local teams, and practical
information that works for colleagues outside the main office.

Intranet content includes published posts, comments where appropriate, staff
profiles, department pages, current policies, superseded versions, staff events,
office/depots information, and searchable reference material. Drafts remain
drafts in their owners' workspace. Ordinary employees should not see an editor's
private notes or a content-generation manifest.

Meetings require organizers, participants, availability, locations or meeting
links, recurring series and exceptions, invitations, responses, cancellations,
and reschedules. Only an appropriate subset has agendas, minutes, or attachments.
An invitation is not proof a meeting happened. A task assigned in minutes should
appear in later work; a cancelled meeting should not have invented minutes.

Chat activity should follow how each function works. KeplerOps can have lively
project channels; ARWC's office collaboration coexists with shift and field
records. Conversations have uneven participation, brief replies, references,
occasional humour, and threads that simply end. Company-wide announcements
should not be used to make every mailbox look equally busy.

File collections need real formats and organization: useful spreadsheets,
reports, presentations, PDFs, forms, drawings, images where meaningful, drafts,
completed versions, attachments, and selected older material. The same invoice
attached to mail and stored in finance should have matching identity and bytes.
An author-only artifact store can deduplicate these copies without deleting
their different in-world locations.

## Work that must connect across departments

These are representative normal business histories to develop, each with
multiple examples and varied states. They are not challenge paths.

| Business history | Records that should agree |
| --- | --- |
| KeplerOps customer improvement | Support case → product decision → engineering issue/change → quality result → release → customer reply. |
| KeplerOps contract renewal | Account discussion → capacity review → agreed contract/amendment → invoice → payment allocation → support entitlement. |
| Employee joins or moves teams | Approved role → directory effective date → equipment/access requests → induction/calendar → work appropriate to that role. |
| ARWC ordinary equipment service | Request/inspection → work order → scheduling/parts → supplier report → acceptance → invoice → payment and asset history. |
| ARWC customer billing question | Service point/readings → bill → customer contact → checked explanation or adjustment → corrected account state. |
| ARWC sample and report | Sampling plan → collected sample → laboratory receipt/result → review → appropriate report and summary. |
| Capital project milestone | Proposal → approved allocation → project work → acceptance → cost ledger → management/board reporting. |
| Meeting decision | Invitation → attendance/notes when appropriate → assigned action → later work → closure or recorded deferral. |
| Intranet publication | Draft → factual review → approved version → published post → reader responses or a later update. |
| Workplace social story | Appropriate private arrangements → shared notice only where warranted → actual outcome or still-future plan. |

Not every communication channel leaves a transcript. A follow-up can refer to
a phone call without generating a verbatim recording of it. A credible world
contains ordinary gaps, but its surviving records must not contradict each other.

## Voice, people, and boundaries

Extend the existing character profiles with short writing samples and practical
writing habits before developing substantial new correspondence. Profiles and
character sheets are the same authoring material; do not maintain competing
biographies. Keep those records outside the world and let the employee-facing
assets demonstrate the voices.

Give all employees a minimal consistent identity and work context. Give a smaller
supporting cast recurring habits and relationships; retain the fifteen detailed
profiles already written. Avoid creating 294 elaborate biographies or making
every employee central to a plot.

Use different genres and lengths. A purchase acknowledgement can be two lines;
a board paper may take several pages. Templates belong to forms and standard
notifications. Human correspondence should not all have identical headings,
paragraph counts, conclusions, or conspicuously helpful exposition.

Let people occasionally misspell, omit words, write fragments, use uneven
punctuation, or correct an earlier message. Reflect individual differences in
English fluency without inferring proficiency from a name or turning language
background into a caricature. Hurried internal notes and reviewed public reports
should not share the same degree of polish. Avoid random typo injection and
uniform error quotas. Check for stock openings, repetitive structures, relentless
em-dashes, and conspicuously tidy conclusions across the whole collection.

Create original fictional people and business records. Supporting names require
screening before entering canon; do not relabel real private correspondence as
these employees' lives. Keep workplace disagreements, relationships, and humour
within the existing no-criminal-conduct and no-harassment editorial boundaries.

Completion of the eventual content build means departmental coverage, connected
business histories, plausible distributions, and a clean separation from any
scenario. The volume targets in the generation plan are one part of that
requirement, not a substitute for it.
