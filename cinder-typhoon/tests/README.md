# SDL validation

From the repository root, create an isolated Python 3.12+ environment and install
the matching upstream releases:

```sh
export PYTHONDONTWRITEBYTECODE=1
python3.12 -m venv /tmp/cinder-sdl-check
/tmp/cinder-sdl-check/bin/python -m pip install -r cinder-typhoon/tests/requirements-sdl.txt
/tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --pack-check --pack-max-members 2048 --training-hand-build-gate --keplerops-hand-build-gate --arwc-hand-build-gate
```

Use a clean checkout or move any existing `__pycache__` directories outside the
pack before the pack check. The default member limit counts local cache files
and directories too. Keep bytecode writing disabled for the checks below; do
not raise the member limit to accommodate development caches.

The authored source pack now exceeds the upstream default 1,024-member budget
even without caches. The command above explicitly selects 2,048 using upstream
`PackValidationLimits`. The checker default remains unchanged; omitting the
override currently fails `resource.member-limit`. This is an author-check
budget, not a claim that an unchanged consumer will accept the distributed pack.

For the three hand-build-ready phases, the documented validation set performs
these checks (the focused suites are invoked by their commands below):

1. Native `raes.parser.parse_sdl_file` parses and composes the complete campaign
   with structural and semantic validation enabled.
2. The Training, KeplerOps, and ARWC gates independently check native workflow
   predicates, node membership, addresses, listeners, application routes,
   identities, grants, exact content ownership, action/evidence binding and the
   preserved prerequisite/difficulty portfolio. The KeplerOps gate rejects any
   return of meaning-bearing private relationship properties. The ARWC gate
   additionally recalculates the live, practice, scheduler-rehearsal, reporting,
   reserve, tariff, liability, and buffer contracts.
3. `instantiate_scenario` and `compile_runtime_model` run on the whole scenario.
   Assertions check that default-open intent survives both steps, that omitted
   substrate/architecture/version choices remain open, and that Linux/Kali
   remains exact. Resource sizing must remain unspecified. The 273 challenge
   and capability observations retain their producer bindings, and eight workplace
   readback observations retain exact content ownership. Source artifacts and
   named workplace service bindings survive compilation.
4. Focused unit suites deliberately remove or corrupt exact fixture text,
   generation digests, exploit-critical profiles, content ownership, action
   bindings, evidence selectors, observed-state completion, native address
   placement, supplied developer access and the customer boundary.
5. `--pack-check` runs env-packs' author validation with local module resolution.

`raes-env-packs==6.1.0` intentionally denies imports through its public
`validate_pack` untrusted-ingest API. This authoring check therefore uses its
`_validate_pack_for_author_ci` entry point, pinned to that release. No runtime
delivery bundle or flattened ingest artifact is claimed. A future packaging
step must use the appropriate upstream author-to-consumer handoff.

The full native check is CPU intensive at this campaign size and can take
several minutes. The focused suites use structural composition for speed. None
of these checks starts targets, contacts a cloud, or creates assets.
The [validation record](../docs/sdl-validation.md) states what was established.

The earlier standard-library authoring checks remain beside their inputs in
[docs/design/](../docs/design/README.md). None of these checks establishes runtime
exploitability, isolation, evidence-adapter correctness, or event capacity.

## Training content and hand-build gate

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python -m unittest discover -s cinder-typhoon/tests -p test_training_design.py -v
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --pack-check --pack-max-members 2048 --training-hand-build-gate
```

The fifteen focused tests check all 47 exact native content/file/route bindings,
public versus private ownership, network addressing, scoped application RBAC,
independent recorded/practice/replay state, the stale report join, prerequisite
preservation, and removal of private Training/recovery semantics. Structural
tests skip upstream semantic validation for speed; the second command performs
the full upstream validation, instantiation, compilation, and hand-build gate.

The final hand-build gate is expected to pass. The
[readiness record](../docs/design/training-readiness.md) states the remaining
manual-build, integration-test, and playtest boundary. Passing does not claim a
running implementation exists. No test starts a service or exercises an
intended weakness.

## KeplerOps content and hand-build gate

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python -m unittest discover -s cinder-typhoon/tests -p test_keplerops_design.py -v
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --pack-check --pack-max-members 2048 --keplerops-hand-build-gate
```

The focused suite checks all 104 card contracts, their exact owner/path and
canonical generation input, native surface-route bindings, multi-service
evidence joins, fixed three-subnet address plan, supplied developer identity,
exploit-critical binary/parser/crypto/browser/identity/model/signing/workload
profiles, exact customer connector boundary, difficulty/prerequisite portfolio,
and removal of KeplerOps private semantics and placeholders. The full command
adds upstream environment-pack validation, semantic composition, instantiation
and runtime compilation. Neither command creates a repository, binary, package,
model, service, image or range.

## ARWC content and hand-build gate

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python -m unittest discover -s cinder-typhoon/tests -p test_arwc_design.py -v
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --pack-check --pack-max-members 2048 --arwc-hand-build-gate
```

The focused suite checks all 120 card contracts, the complete ownership matrix,
exact owner/path and generation input, narrative references, native application
and filesystem bindings, five-network address plan, identities, grants,
PostgreSQL contract, complex binary/parser/crypto/browser/memory/control
mechanics, multi-service evidence joins, process arithmetic, rehearsal/live
isolation, and removal of all remaining private semantics and placeholders. The
full command adds upstream environment-pack validation, semantic composition,
instantiation, and runtime compilation. Neither command creates a binary,
service, process model, image, checkpoint, or range.

## Build-worker handoff checks

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python -m unittest discover -s cinder-typhoon/tests -p test_k09_handoff.py -v
```

These seventeen focused tests check the authored K09 documents against native file
content, owning paths, the concrete command example, independent worker
and receiving-service proof, unchanged Easy/Easy/Medium/Medium allocation, and
the existing downstream entry routes. Negative cases remove the connection or
destination proof, grant access too early, move a protected document onto the
developer workspace, replace the harmless example with a protected answer, or
insert out-of-world copy. They use native structural parsing of the operation
module and reject replacing a product's real read API with an invented path.
They also check shell syntax and argument expansion (with a curl stand-in that
prints arguments only; no network or credentials), reject forced
worker authentication for separately earned identities, and require the native
action contract to retain command execution, installed clients, private file
continuity, externally enforced isolation, and worker credential expiry. Proof
cannot rely on a request ID or participant-writable log alone. These text and
contract regressions are not an implementation of the job or its restrictions.
The command profile also requires the retained reference from an actual completed
integration review, rather than merely a guessed profile name or a score state.
Complete reference validation and compilation still run in the full SDL command
above. Live job execution, service authorization, continuity across ordinary
retries, and fresh operator discovery remain golden-range acceptance checks.

The downstream route checks exercise the static design graph. They do not
establish that a built client can present a newly obtained identity or speak the
destination's protocol. K19/K20 now have complete certificate/delegation
contracts; their real clients and obtained identities remain hand-build and
integration-test work.

## Workplace asset checks

The same validation environment can check the authored assets independently:

```sh
python cinder-typhoon/build/render_narrative.py --check
python cinder-typhoon/tests/validate_narrative.py
python -m unittest discover -s cinder-typhoon/tests -p test_narrative_integrity.py
python -m unittest discover -s cinder-typhoon/tests -p test_release_platform.py
python -m unittest discover -s cinder-typhoon/tests -p test_customer_followup.py
python -m unittest discover -s cinder-typhoon/tests -p test_commercial.py
python -m unittest discover -s cinder-typhoon/tests -p test_finance.py
python -m unittest discover -s cinder-typhoon/tests -p test_maintenance_engineering.py
python -m unittest discover -s cinder-typhoon/tests -p test_laboratory_quality.py
python cinder-typhoon/tests/validate_purchasing_stores.py
python cinder-typhoon/tests/validate_retail_billing.py
python -m unittest discover -s cinder-typhoon/tests -p test_planning.py
python -m unittest discover -s cinder-typhoon/tests -p test_governance.py
python -m unittest discover -s cinder-typhoon/tests -p test_community_life.py
python -m unittest discover -s cinder-typhoon/tests -p test_regional_relationships.py
```

These check deterministic rendering, source hashes, message headers and bodies,
reply chains, MIME attachment bytes and publication dates, retained mailbox copies,
document readers, roster and reporting joins, directory entries, calendar times
and audiences, employment records, business account and contact joins, support
case/thread/entitlement joins, normalized prose diversity, historical engineering
assessments and later resolutions, accepted-activity arithmetic, ownership, and story coverage. Corruption
checks reject an altered attachment, a private message copied to an unrelated
mailbox, changed source bytes, a detached reply, a reporting loop, and an
altered accepted-delivery amount. They also reject a customer/internal thread
bridge and a fabricated engineering resolution. The full SDL check also verifies the eight native
materialization contracts.

Laboratory and quality checks reconcile 960 schedule/collection/receipt/result/
review/report histories, all sixty accepted field handoffs, fictional internal
bands and units, repeat and recollection dispositions, nine real Office
workbooks and their formula caches, issued reports, equipment service, training,
quality-review calendars, exact readers, and photography continuity.

Purchasing and stores checks reconcile 480 requisition-to-payment histories,
all 180 maintenance joins, all sixty field-stock replenishments, twelve Ternwick
batches, district and shared allocations, invoice and payment ledger totals,
thirteen CSV registers, 885 strictly parsed supplier PDFs, thread separation,
exact attachments, reader boundaries, and visible provenance leakage.

Retail billing checks project all 50,102 accepted invoices and 101,641 lines
without duplicate authority, reconstruct issue-date electronic/postal
preferences, reconcile 31,920 payments and allocations, 500 adjustments and
50,100 balances, and validate 800 substantive cases, 200 appointments, 300
collections histories, 200 arrangements, 7,600 messages, fourteen registers,
50,102 readable bill renderings, and 24 strictly parsed PDFs.

Planning checks reconstruct source aggregates for forty histories and verify
232 messages, 230 documents, eight meetings, five registers, and 48 XLSX files.
They independently evaluate every workbook formula using decimal arithmetic,
check actual input cells and units, and trace draft and issued summaries to the
appropriate versions. Fourteen content mutations attack source totals, periods,
classification, dates, readers, replies, attachments, summaries, and meeting
records. Three checksum-consistent binary mutations corrupt a formula, a cached
result, and an open action. These checks do not establish forecast accuracy or
prove the fictional work described in the records occurred.

ARWC governance checks independently reconstruct four dated closes from invoices,
signed adjustments, receipts, matched acquisitions and settled payments. They
check exact district amounts, 28 Office formula/input/cache sets, historical
costs, conditional proposals, board votes, ten calendars and six public releases.
Twenty-seven content mutations and four checksum-consistent binary mutations
test accounting, authority, privacy, dates, formulas, cached values, district
rows and PDF selection. Public search text must match the approved PDF bytes;
drafts and individual learning records retain exact named readers.

ARWC IT checks reconcile 480 cases against the accepted workforce, current
team reader groups, prior starter and move records, eleven declared services,
fifty assigned equipment items, machine copy-check notices, existing suppliers,
and twenty-five approved change windows. The focused fault probes reject an
unrelated case reader, an approval out of sequence, and a window attached to
a deferred change. Case summaries and mail attachments retain exact named
readers; sampled copy checks do not claim complete recovery.

ARWC community-life checks reconcile 112 publications, exact contributor consent,
624 calendar histories, scheduling attachments, response states, actual attendance,
private personnel records, room/resource availability and accepted story continuity.
They compare bookings with accepted calendars, field duty rosters, visits and timed
observations. Thirty-two deliberate faults cover privacy, publication, attendance,
cover, chronology and independent calendar/field-book conflicts. Earlier local
staff arrangements do not imply a complete operating roster outside the accepted
field-record window.

Release and platform checks join the 120 operating histories to their accepted
quality evidence, exact revisions, source bytes, and calendars. Ten targeted
mutations reject premature release, unaccepted evidence, publication of a held
bundle, changed readback bytes, fabricated recovery hashes, altered machine
values, overbooked capacity, unrelated readers, confirmed cancelled windows,
and invented service owners. Attachment checks include declared MIME types.

Regional relationship checks reconcile ninety records with accepted account terms,
contractor reports, delivery quantities, reading explanations and scanning batches.
They check five exact document counterparts, principal-company audiences, private
reply boundaries, published attachment versions and three tentative appointment
proposals against existing calendars. Twenty-six deliberate faults cover money,
quantities, dates, rewritten evidence, private attachments and ancestry, altered
counterparts, missing explanations, future completion, calendar conflicts and
authoring metadata. Full narrative validation also checks that cross-company mail
retains one identity and identical RFC 5322 bytes in both native sources.

Customer follow-up checks join 290 case histories, ten shared corrections,
five later releases, 24 knowledge revisions, and the Rillhaven preparations.
Fourteen targeted mutations reject missing verification, premature delivery or
acceptance, unrelated evidence, private-thread or attachment leakage, rewritten
history, false test results, completed future work, missing parents, and
premature closure notices. Current case projections retain the original intake
history and unchanged record identity. These checks validate fictional records;
they do not execute the product tests described in those records.

Commercial checks join sixty histories to the twelve-account contract book,
signed versions, finance schedules, private pricing worksheets, delivery
evidence, and finite project reservations. Twenty mutations reject false
commitments, changed fees, premature final billing or completion, private
material sent to customers, missing capacity, corrupted evidence, and a falsely
confirmed reference call. Calendar checks include existing support appointments.
Billing authority remains distinct from an issued invoice or payment.

Finance checks reconstruct the journal from invoice, acceptance, receipt,
claim, payroll, and allocation events; they reconcile opening and closing
balances, supplier/customer statements, PDF text, and actual workbook cells.
The pinned `pypdf` dependency parses all PDFs. Office ZIP/XML parsing and formula
evaluation use the Python standard library. Twenty-six mutations reject false
authority, changed fees, premature payments, incomplete deliveries, self-approved
claims, payroll leaks, altered opening balances, and binary corruption. One
mutation rewrites an actual XLSX formula and updates its digest, proving that a
valid checksum alone cannot hide an incorrect cached result.

Maintenance and engineering checks join 720 work orders to 72 assets, all 48
employees and the 24 accepted operations requests. They verify employment dates,
status boundaries, contractor quote/order/appointment/report/receipt chronology,
amounts, drawing bytes and revision authority, commissioning and handover, exact
archive tables, message variation and reader scope. P1/P2 remain working copies;
only A1 can become effective for work.

## Prose checks

Use Vale 3.9.1 with the pack configuration from the repository root:

```sh
vale sync
vale --config=cinder-typhoon/.vale.ini cinder-typhoon/
```

CI selects this configuration for changed pack documents. Other repository
documents retain the root configuration. The pack configuration exempts
workplace assets, character profiles, and the player-facing description and
hint sections of challenge cards. Technical sections and authoring guides
remain linted. See the [editorial boundary](../docs/narrative/content-direction.md#prose-lint-and-character-voice).

These exemptions protect writing choices; they do not replace asset integrity,
continuity, audience, or challenge-contract checks. Keep lint directives out of
participant-visible content.
