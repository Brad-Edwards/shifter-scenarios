# Enterprise content development plan

Planning draft, 19 September 2026. Read with the
[department requirements](enterprise-content-requirements.md). This pass defines
future work, assesses available tools, and estimates scale. It does not generate
the population or business corpus, change SDL, install generators, or implement
an environment adapter.

**Implementation direction clarified:** deliver finished content for this pack.
The [enterprise content milestone](https://github.com/PaloAltoNetworks/shifter-scenarios/milestone/3)
organizes implementation into concrete slices, each including existing-content
fit, adversarial review, actual assets, and native SDL authoring. Existing tools,
direct writing, temporary scripts, and assisted drafting are acceptable means.
A reusable generation system, pristine pipeline, repeatability framework, or
independent generator-development workstream is not a deliverable. The earlier
pipeline-oriented sequence below is superseded by those content issues. Tool
research remains available as optional assistance, not an adoption requirement.

## Recommendation

Build a reusable, versioned KeplerOps/ARWC world from a shared model of people,
business entities, and dated work. Generate structured records from that model,
then produce correspondence and documents describing the same work. Keep
scenario-specific content in separately selected additions and replacements.

Use ordinary deterministic code for dates, identifiers, financial calculations,
relationships, permissions, and state transitions. Use language generation for
human wording with those facts supplied as constraints. Bulk form and system
output should use templates with meaningful underlying values. Generation runs
before the event; the delivered world is a frozen history.

The likely starting toolset is Faker for controlled fictional values,
Snowfakery where relational recipes help, and NeMo Data Designer for resumable
prose generation and validation. Adopt useful approaches from OrgForge and
OrgSmith after evaluating their relevant components. Do not introduce all of
these frameworks merely because they exist. The selection step below decides
which components actually reduce implementation work.

## Research and available tools

Primary sources checked on 19 September 2026. These are source/documentation
assessments, not claims that the tools have been installed or proven at our scale.
License labels below describe the published project or dataset; they do not
establish the rights of every optional dependency or input collection.

| Candidate | Useful contribution | Limitation and proposed use |
| --- | --- | --- |
| [OrgForge](https://github.com/tenurehq/orgforge), MIT | An event-driven company model produces related mail, tickets, documents, meetings, and business records. The [paper](https://arxiv.org/abs/2603.14997) separates state from generated prose. | Strong architectural reference. Its documented default loop is weekday-oriented and examples emphasize software incidents; ARWC needs routine utility work and shift schedules. Its claims do not replace our independent consistency checks. Evaluate relevant components before adopting the whole engine. |
| [OrgSmith](https://github.com/peterzat/OrgSmith), Apache-2.0 | Real document formats, email thread mechanics, attachments, revisions, and file-share variety. | A useful rendering and document-culture reference. Its own documentation acknowledges limited mail volume and specimen-sized companies. It does not supply a ready-made 294-person enterprise history. |
| [NeMo Data Designer](https://github.com/NVIDIA-NeMo/DataDesigner), Apache-2.0 | Seeded inputs, dependency-aware generation, statistical sampling, custom validation, and resumable generation. | Candidate for producing prose from our accepted facts. We still own the organization, business processes, audiences, and chronology. Model access and generation cost are separate from the library. |
| [Snowfakery](https://github.com/SFDO-Tooling/Snowfakery), BSD-3-Clause | YAML recipes generate related records and output databases, JSON, or CSV. Its [documentation](https://snowfakery.readthedocs.io/en/latest/) includes references between objects. | Good fit for accounts, contacts, orders, invoice lines, and other relational data. It does not itself make an invoice agree with a meeting's narrative; the shared business model must enforce that. Salesforce is not required. |
| [Faker](https://faker.readthedocs.io/en/stable/), MIT | Fictional primitive values, custom providers, and seeded generation. | Use inside the canonical roster and business model. Independent random names and addresses per file would destroy continuity. Pin the package version because the same seed need not reproduce values after an upgrade. |
| [Vectrix ART-E](https://huggingface.co/datasets/TonicAI/vectrix-art-e), dataset labeled Apache-2.0 | A synthetic company corpus with employees, voice profiles, timeline events, thread specifications, and cross-references. | Useful schema and generation-order reference. It contains 1,964 emails for 100 fictional employees, so it is not a volume baseline or sufficient bulk content. Keep our own companies and stories. Its hosted generation product is not required to study the public dataset. |
| [SNAP email-Eu-core-temporal](https://snap.stanford.edu/data/email-Eu-core-temporal.html) | Anonymized internal communication metadata for 986 people, including departments and time. | Candidate for aggregate structural comparison: unequal activity, recurring contacts, and bursts. Edges count individual recipients, not distinct messages; external correspondence and prose are absent. Do not derive our mail count by treating edges as emails. |
| [CMU Enron](https://www.cs.cmu.edu/~enron/) | About half a million retained messages from about 150 users; folders and real correspondence structure. | Reference for archival characteristics, not a mail corpus to relabel as our people. The collection skews toward senior management, omits attachments, and has documented preparation issues. It is not a representative water-utility population. |
| [Avocado](https://catalog.ldc.upenn.edu/LDC2015T03) | Business mail, attachments, folders, calendars, and contacts from 279 accounts, some shared or system accounts. | Relevant in shape but not a candidate for event content. Its [published agreement](https://catalog.ldc.upenn.edu/license/avocado-collection-individual-agreement.pdf) restricts access and redistribution. No purchase or corpus download is proposed. |
| [TheAgentCompany](https://github.com/TheAgentCompany/TheAgentCompany) | A simulated software company spanning several workplace applications and functions. | Useful reference for continuity across applications. Its [paper](https://arxiv.org/abs/2412.14161) describes an agent benchmark, not a population-scale utility generator; importing its tasks would not meet these world requirements. |
| [ReelDiscovery](https://github.com/ghanderson77-ops/ReelDiscovery) | Custom scenario email, branching threads, office attachments, and character voices. | Alternative email-focused reference. The README calls the license MIT, while the actual [LICENSE](https://github.com/ghanderson77-ops/ReelDiscovery/blob/main/LICENSE) is GPL-3.0; do not describe it as permissively licensed without resolving that mismatch. Its example genres are not our company canon. |

General tabular synthesis is not automatically the right choice. For example,
[SDV's published license](https://github.com/sdv-dev/SDV/blob/main/LICENSE) is
Business Source License 1.1 rather than an unconditional OSS license, and
statistical table synthesis would still leave the business narrative to us.
There is no reason to require it for this plan.

Searches of dataset catalogs, including Kaggle, did not identify a ready-made
corpus that simultaneously supplies our two industries, fictional people,
business history, reusable ownership, and required scale. That is a result of
this search, not a claim that no such dataset could exist. The strongest fit
is generation from our own world model, informed by public tools and structures.

For output, the existing renderer already uses Python's native
[email and MIME facilities](https://docs.python.org/3/library/email.message.html).
Future document candidates include
[python-docx](https://python-docx.readthedocs.io/en/latest/) and
[openpyxl](https://openpyxl.readthedocs.io/en/stable/simple_formulae.html), with
[LibreOffice](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
for appropriate document conversion and spreadsheet calculation. Openpyxl writes
formulas but does not evaluate them; a workbook that looks correct yet exposes
empty cached results would not satisfy the spreadsheet requirements.

## Scale assumptions

The user's 29,400-email reference is a minimum planning scale, not an industry
standard. Count distinct logical messages first. Count retained sender,
recipient, shared-mailbox, and archive copies separately. Sending a notice to
294 people does not create 294 distinct messages for the volume target.

The initial working estimate is approximately **87,000 distinct messages** over
roughly three months of substantial recent activity, with approximately
**186,000 retained mailbox copies**. This is an authored estimate, not a measured
rate, a generated corpus, or a promised runtime capacity.

[model_footprint.py](model_footprint.py) makes the arithmetic reproducible:

```sh
python3 cinder-typhoon/docs/narrative/model_footprint.py
```

It uses 60 effective working days and the existing department headcounts.
Illustrative staff-sent rates range from 0.6 messages per effective day for
ARWC's operations/field group to nine for KeplerOps commercial staff. External
incoming mail and automated messages add 30% and 20% of the staff-sent count.
These are sensitivity assumptions to refine against the actual work generated.
Shift activity will use real roster dates in the generator, not a weekday-only
restriction inherited from this aggregate calculation.

| Activity case | Distinct messages across both companies | Retained mailbox copies |
| --- | ---: | ---: |
| Lighter: 0.6 × assumed rates | 52,319 | 111,789 |
| Working | 87,200 | 186,317 |
| Busier: 1.5 × assumed rates | 130,800 | 279,475 |

The working company estimates are 34,020 KeplerOps messages and 53,316 ARWC
messages, with 136 cross-company messages counted in both company collections
but once in the combined total. In the actual build, identity-based deduplication
replaces this approximate overlap. Copy counts are estimates, not instructions
to retain every message in every available archive.

The population must have uneven mailboxes: customer-facing and office staff
have richer email, while field staff leave more of their work in assignments,
shift records, and service systems. Use department, team, role, working pattern,
tenure, leave, recurring contacts, and individual activity variation. Do not
force identical per-person quotas or manufacture broadcast traffic to fill gaps.

### Other content families

These are working allocation bands for future planning. They should be reconciled
to process counts before generation; rows describe different units and must not
be summed as if they were all independent files.

| Family | Initial planning quantity | Counting and realism condition |
| --- | --- | --- |
| Employees | 294 | All appear in the organization model; the named cast is retained. A directory entry does not require a separate host. |
| External recurring business contacts | 40–100 | People and departmental contacts at suppliers and organizational customers; not extra employees. Retail account contacts are additional and follow the account model. Expand supporting company names only through canon and name screening. |
| Shared mailboxes, groups, and room/resources | Inventory by function | Derive support, billing, purchasing, staff notices, teams, and bookable resources from actual use. Do not inflate employee counts with them. |
| Intranet news and staff notices | 150–300 posts, with selective comments | Distinct dated publications; not every post has a discussion and not every comment becomes email. |
| Reference and policy material | 250–500 current pages/documents plus selected history | Current/superseded status, ownership, and audiences must work. Includes departmental knowledge, not 500 company-wide policies. |
| Meetings | 1,000–1,800 distinct occurrences | Count events separately from copies of invitations and recurrence exceptions. Only an appropriate subset has minutes or formal papers. |
| Chat | 20,000–40,000 messages | Concentrated where chat fits work; routine short exchanges and system posts included. Field teams need not behave like a software team. |
| Cases, work orders, and tasks | 3,000–6,000 distinct work items | Allocate by business process and distinguish a case from its linked engineering issue or maintenance order. Histories add more events. |
| Office/business files | 3,000–6,000 distinct documents and meaningful versions | Includes memos, minutes, workbooks, reports, service records, forms, supplier invoices, and presentations. Excludes email copies and the high-volume retail billing family below. |
| Utility accounts, bills, readings, payments | Derive from the service-population model | A provisional example is 60,000 residential and 1,500 commercial accounts, giving about 61,500 bills for one represented billing cycle. This is an assumption, not new canon. Residents are not accounts; support multi-unit and multi-meter relationships. |
| Repository and release histories | Derive per selected project | Source, review, issue, and build histories should explain actual work. A large commit count with meaningless edits is not useful. |

The billing example illustrates why "a few thousand documents" cannot be the
entire enterprise footprint. Its records and resulting bills can be produced
cheaply from a coherent ledger and templates. Selected older billing cycles
need sufficient transactions or explicit opening balances to make the recent
history reconcile. Choose billing cadence and account structure during the
business-model step rather than assuming one household equals one monthly bill.

## Generation design

### 1. Canonical entities and effective dates

Define people, roles, teams, managers, memberships, external organizations,
contacts, customers, contracts, projects, products, service points, equipment,
cost centres, and schedules once. Stable identifiers connect their records.
Preserve prior roles and names at the time an older record was written.

Represent the declared fourteen employee characters and Jules as fixed inputs.
Develop the remaining population using controlled fictional values. Detailed
voice and relationship treatment should concentrate on recurring people; all
employees still need consistent authorship and work context.

### 2. Business events and state

Model ordinary processes with dated transitions: request, review, approval,
assignment, completion, acceptance, invoicing, payment, publication, or closure
as applicable. Different processes require different states; a customer question
does not have to traverse a purchasing workflow.

Choose dates, participants, identifiers, quantities, money, units, permissions,
and outcomes before writing prose. Generate approvals from the right roles,
calendar activity from availability, bills from the fictional tariff and readings,
and summaries from the resulting ledger. Use fixed-precision arithmetic for
money. Define opening state when the detailed history starts mid-process.

This is an offline history builder. A modest event scheduler and explicit
process rules may be sufficient; full autonomous employees are not a requirement.

### 3. Records and correspondence

Produce each process's records from the same facts. Supply a language model
with the event, appropriate prior context, speaker, audience, document genre,
and allowed facts. Generate whole related conversations or document families
in bounded jobs so replies and revisions remain connected.

Use templates for forms, routine notices, repeated statements, and system output.
Use generated prose where human expression matters. Keep the existing authored
story exchanges as accepted examples, integrated into the broader calendar and
population. They should not become conspicuously polished islands surrounded
by unrelated filler.

A model must not invent a new supplier, amount, employee, approval, credential,
or outcome to finish a paragraph. Reject or repair contradictions at their
source; do not silently change the shared business facts to fit the prose.
Facts are deterministically rebuildable. Accepted prose must be cached and
versioned because a repeated model call is not a byte-reproducibility guarantee.

### 4. Formats, copies, and placement

Render actual mail, calendar, office, PDF, tabular, and application records from
accepted source content. Set plausible authors, dates, titles, revision states,
and department-specific templates. A displayed invoice, its PDF, and its email
attachment must agree. Repeated boilerplate is expected where the genre warrants
it; repeated whole conversations with swapped names are not.

Keep logical message identity separate from mailbox copies. To/CC recipients,
distribution-list membership at send time, forwards, replies, BCC, and retention
determine who receives which version. A BCC recipient must not be disclosed in
another recipient's headers. Attachments keep their exact issued versions even
if the document later changes. Quoted history must not reveal an unseen private
conversation without an actual forward or quote.

Plan the owning application and readership for every collection. A file on an
author's disk is not yet an intranet post, a meeting in a calendar, or a record
in the business application. Eventual adapters must preserve the relationships
and provide ordinary in-world browsing and search. This plan leaves their
software and hosting implementation to later technical work.

### 5. Checks on the resulting world

The future content pipeline needs deterministic checks for entity references,
effective dates, temporal order, record ownership, financial reconciliation,
document versions, attachment integrity, membership expansion, and calendar
consistency. It also needs editorial review across departments and record genres
for plausible voice, useful content, and appropriate routine activity.

Use activity and genre distributions to detect isolated employees, inexplicable
fully connected teams, synchronized daily bursts, excessive repeated prose,
and every thread reaching the same outcome. Compare aggregate structure with
appropriate public references without transplanting real people's mail.

These are content-production checks. They do not establish event capacity,
runtime materialization, or challenge difficulty, and this planning pass does
not attempt those later tasks.

## Environment content and scenario content

Separate ownership in source catalogs and build selection, not in the company's
published documents. Suggested future locations within the existing env-pack
convention are `assets/environment/` for reusable sources and
`assets/scenarios/<scenario-id>/` for scenario additions and modifications.
These paths are proposals; this planning pass does not move existing assets.

An author-only inventory must identify each record's owner layer, stable world
identifier, content version/digest, business entity and event references,
logical destination, and intended readership. A scenario inventory additionally
records its scenario/challenge owners and required base version. These are pack
authoring conventions, not invented RAE grammar fields.

| Ownership case | Required treatment |
| --- | --- |
| Ordinary company history, staff mail, invoice, procedure, or work item | Environment-owned and available to any scenario selecting that world version. |
| A challenge uses an existing ordinary invoice as context | Keep the invoice environment-owned; record the scenario's dependency on its stable identity and version. |
| A challenge changes that invoice, plants a clue, or requires a special permission | Store the changed version or declared modification in the scenario layer. Preserve the original baseline. |
| Scenario-only credential, deliberate weakness, flag, hint, solution, or consequence | Keep with the owning scenario; do not propagate into base records or the ordinary history. |
| Two scenarios modify the same base object | Use independently selected versions by default; combined selection must detect and resolve the conflict explicitly. |
| Scenario removed or replaced | Restore the pinned baseline, including affected relationships, audiences, and search/index projections. Ordinary company history remains usable. |

Selection must be closed over dependencies: base content can depend on base
content, while scenario content can depend on a pinned base and its own selected
records. Base content must not require a flag, capability grant, attacker action,
or challenge-specific fact to become a coherent company history.

Do not make copies of all company records for each challenge pack. Pin a world
release and store the actual differences. Packaging may deduplicate source
bytes; in-world records still retain their proper identities and locations.
Existing SDL world modules contain some campaign-related concepts, so a later
reuse pass must audit content, identities, permissions, and module dependencies;
renaming a folder alone will not establish an independent world baseline.

When implemented, use native RAE module composition, content sources, and
materialization semantics, retaining default-open intent. Keep a scenario entry
point that composes the selected world and scenario modules. Do not assume the
current SDL is already separated that way, or add unsupported ownership fields
to SDL to simulate it.

### Preventing fourth-wall leakage

Only allowlisted in-world payloads enter applications and participant-reachable
storage. Authoring manifests, prompts, seeds, ground-truth graphs, solution maps,
and source catalogs remain outside that boundary, including application indexes
and backup/export material available to participants. Hiding them from a normal
web page is insufficient if another ordinary or privileged in-world route can
read them.

Before publication, inspect serialized mail headers and bodies, attachments,
office document properties, PDF metadata, HTML comments, hidden spreadsheet
sheets, revision comments, file paths, directory listings, and application fields.
Author-only labels must not survive as an `X-Scenario` header, a challenge number
in a filename, a generator comment, or a searchable hidden field. Stable internal
IDs should be mapped to natural business IDs or opaque application identifiers
where those identifiers are exposed.

Author-only records may clearly mark material as synthetic and identify its
provenance. That does not require synthetic-content banners inside employee
mail or event-designer explanations inside the intranet. An in-world document
can naturally refer to ordinary staff training; leakage checks should distinguish
that from challenge instructions and inspect all visible metadata as well as text.

## Gaps in the current pack

The current [renderer](../../build/render_narrative.py) and
[asset checker](../../tests/validate_narrative.py) implement the small story
collection. They use a fixed cast, fixed reader groups, and explicit small
inventory expectations. The renderer currently models To recipients and simple
INBOX/Sent retention; it does not implement the broader CC/BCC, group membership,
mailbox-history, and calendar lifecycle requirements above. Expanding the YAML
until it contains thousands of rows would not resolve those model limitations.

The current document library carries text documents, CSV contacts, and calendar
files. Rich office attachments, reconciled business tables, application records,
and full employee coverage require planned extensions. The existing stories
should remain accepted inputs while those capabilities are developed.

The four present JSON source packages are adequate for the small collection.
For the larger world, plan versioned collection manifests and bounded source
artifacts, with independent per-record inventories and shared attachment
identities. Avoid expanding SDL into a declaration for every email, invoice
line, or chat message. Native collection/source contracts should express the
in-world content obligations, while artifact checks prove their actual record
coverage. Verify those shapes against the permitted RAE semantics during the
later SDL stage; this plan does not prescribe a new grammar.

## Earlier development sequence (superseded)

The following sequence records the earlier planning approach. It is retained
for context and superseded by the milestone's content-slice issues; it must not
be treated as a requirement to build generator infrastructure before writing
content. None of these stages was executed by this planning document.

| Stage | Work and deliverable | Completion condition |
| --- | --- | --- |
| 1. World inventory | Expand the roster plan; assign all departmental functions; specify teams, schedules, external contacts, customer/service-account model, business identifiers, and authoritative record owners. | Headcounts reconcile; named canon is preserved; every department has people, work, and intended content surfaces. |
| 2. Business history design | Define ordinary processes, calendars, the detailed history interval, opening balances/states, selected historical material, and volumes per process. | Representative cross-department histories reconcile on paper; workload explains the intended document and message counts. |
| 3. Tool selection and generation specification | Evaluate the shortlisted tools against those histories; choose libraries and formats; define prompts, templates, caching, retries, and validations. | A concrete generation design identifies what is reused, what needs local code, and its measurable cost assumptions. No dependency on live generation at the event. |
| 4. Connected development sample | Build a bounded sample spanning people, purchasing, a service case, a work order, a meeting, intranet publication, and ordinary personal correspondence. | Formats, readers, chronology, arithmetic, relationships, and voice meet the requirements; measure actual token and render costs before scaling. |
| 5. Population and volume build | Generate the full agreed population, histories, and content families; retain completed batches and report actual counts and distributions. | Every department is covered; unique mail and retained copies are counted separately; structured retail records and meaningful documents exist at the agreed scale. |
| 6. Reusable packaging and later SDL work | Package a versioned environment baseline; classify existing assets; define scenario modifications and native SDL composition; implement application bindings in the appropriate technical phase. | Base-only and scenario-composed inventories are distinguishable, free of unwanted dependencies, and contain no exposed authoring metadata. Validate native syntax and expected content when SDL is actually changed. |

The current planning deliverables are this plan, the department requirements,
the source shortlist, and the arithmetic model. Remaining design choices include
the exact history interval and retention policy, retail account/billing model,
departmental process allocations, supporting cast depth, and which generator
components to adopt. Those should be resolved from the companies' operation
and available build effort, not from the number of challenges in one CTF.

Generation cost needs a token and render budget, not an assumed cheap per-email
price. Compute it from accepted thread/document counts, average input/output
length, model rates, retries, and non-LLM rendering. Produce routine financial
and system output without a model call per record. Reuse context and cache
accepted prose so changes regenerate only affected families. No paid service
purchase, model training, or event-time inference capacity is prescribed here.
