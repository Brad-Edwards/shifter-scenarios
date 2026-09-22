# SDL validation

From the repository root, create an isolated Python 3.12+ environment and install
the matching upstream releases:

```sh
export PYTHONDONTWRITEBYTECODE=1
python3.12 -m venv /tmp/cinder-sdl-check
/tmp/cinder-sdl-check/bin/python -m pip install -r cinder-typhoon/tests/requirements-sdl.txt
/tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --self-test --pack-check
```

Use a clean checkout or move any existing `__pycache__` directories outside the
pack before the pack check. The default member limit counts local cache files
and directories too. Keep bytecode writing disabled for the checks below; do
not raise the member limit to accommodate development caches.

The command performs these checks:

1. Native `raes.parser.parse_sdl_file` parses and composes the complete campaign
   with structural and semantic validation enabled.
2. The validator independently decodes native workflow predicates, acquisition
   events, node memberships, authority features, and relationship contracts.
   It compares the resulting graph with the preserved design and replays all
   minimal prerequisite closures and all 16 finale route combinations. Separate
   checks compare action preconditions/effects, all five technical sections of
   the 50 drafted cards, proof owners, starting-record requirements, proposition
   quantifiers, and consequence effects with the design-side contracts.
3. `instantiate_scenario` and `compile_runtime_model` run on the whole scenario.
   Assertions check that default-open intent survives both steps, that omitted
   substrate/architecture/version choices remain open, and that Linux/Kali
   remains exact. Resource sizing must remain unspecified. The 273 challenge
   and capability observations retain their producer bindings, and eight workplace
   readback observations retain exact content ownership. Source artifacts and
   named workplace service bindings survive compilation.
4. `--self-test` deliberately changes native type-valid SDL structures, including
   OR gates, current revision evidence, read/control scope, and rehearsal/live
   separation. Its 28 SDL mutations also remove or corrupt observation bindings,
   technical mechanisms, scope/reset requirements, seed ownership, and evidence
   joins. Four further SDL mutations alter workplace content ownership, source
   versions, observed readback, or its selected content. Two additional mutations
   attack the compiled selectors themselves.
   It also runs the existing 26 negative topology cases on the graph decoded
   from SDL.
5. `--pack-check` runs env-packs' author validation with local module resolution.

`raes-env-packs==6.1.0` intentionally denies imports through its public
`validate_pack` untrusted-ingest API. This authoring check therefore uses its
`_validate_pack_for_author_ci` entry point, pinned to that release. No runtime
delivery bundle or flattened ingest artifact is claimed. A future packaging
step must use the appropriate upstream author-to-consumer handoff.

The full native check is CPU intensive at this campaign size and can take
tens of minutes. Its mutation checks repeat full asset validation for several
altered models. It does not start targets, contact a cloud, or create assets.
The [validation record](../docs/sdl-validation.md) states what was established.

The earlier standard-library authoring checks remain beside their inputs in
[docs/design/](../docs/design/README.md). None of these checks establishes runtime
exploitability, isolation, evidence-adapter correctness, or event capacity.

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

Release and platform checks join the 120 operating histories to their accepted
quality evidence, exact revisions, source bytes, and calendars. Ten targeted
mutations reject premature release, unaccepted evidence, publication of a held
bundle, changed readback bytes, fabricated recovery hashes, altered machine
values, overbooked capacity, unrelated readers, confirmed cancelled windows,
and invented service owners. Attachment checks include declared MIME types.

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
