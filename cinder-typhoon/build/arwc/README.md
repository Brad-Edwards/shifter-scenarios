# Alterra Regional Water Company golden-range hand build

This directory is the implementation ledger for materializing the validated
ARWC SDL as an isolated participant environment. The SDL and its owned content
remain the source of truth. Runtime discoveries that change an observable
contract are reconciled there before the implementation changes.

**Status:** The isolated carrier and corporate/maintenance/DMZ/engineering/control network foundation is
deployed. W01-W35 (120 of 120 cards) passed standalone and cross-carrier
whole-phase acceptance. The corporate capability is not pre-seeded and must be
earned by real K26.2 or K27.3 destination execution. The customer handover
runs on `a-connector`; association and annex-import paths run on `a-business`;
archive enrollment, query, helper, and retained-collector paths run on `a-archive`; onboarding and
planner-browser paths run on `a-identity`; and the quoted-identifier and
reconciliation paths run against PostgreSQL on `a-data`. The bounded live-feed
integration runs through `a-data-bridge` in the isolated DMZ. Contractor intake,
field telemetry, and maintenance approval run across `a-contractors`, the
DMZ-only `a-contractor-bridge`, and `a-approval`. Read-only process observation
runs across `a-hmi`, `a-historian`, `a-engineering`, and independently owned
`a-instruments` observations. Bounded live control terminates at the isolated
`a-reservoir` controller. Scheduler and reporting rehearsals additionally join
the control-only `a-distribution` service without altering live process state.

## Boundaries

- The dedicated GCP carrier has one reciprocal peering with the KeplerOps
  carrier. Its only ingress allowance is `10.77.49.2/32` to TCP 443 on this
  carrier; it has no route to Training, Shifter, or their target networks.
- Target networks are Docker-internal. Only the mTLS FieldLink consumer on
  carrier TCP 443 is published; customer handover and every other target port
  remain internal. Operator entry is through IAP SSH and `docker exec` only.
- The participant begins in the limited `fieldlink` execution context on
  `a-connector`, but no corporate session exists until successful package or
  diagnostic execution creates the retained handoff. The private service identity, seed records, mutable state,
  audits, operator material, and tests are not participant-readable.
- Participant-visible files and responses are entirely in-world. Design
  contracts, test sources, build notes, and evaluation state remain on the
  operator surface.
- Only assets named by a card's `narrative_reuse` binding are placed for that
  card. Each is checked for identity and content before inclusion.
- Mutable service state and immutable audit records are volume-backed. A
  destructive acceptance pass is followed by volume recreation from authored
  initial state.

## Realization architecture

- GCP VPC/carrier: `cinder-arwc-golden`, private `10.77.59.2`, no external IP.
- Corporate target network: internal `10.77.60.0/24` bridge.
- Maintenance target network: internal `10.77.61.0/24` bridge.
- DMZ target network: internal `10.77.62.0/24` bridge.
- Engineering target network: internal `10.77.63.0/24` bridge.
- Control target network: internal `10.77.64.0/24` bridge.
- Current nodes: `a-connector` at `10.77.60.20`, `a-business` at
  `10.77.60.30`, `a-data` at `10.77.60.40`, `a-archive` at `10.77.60.50`,
  and `a-identity` at `10.77.60.60`, matching the SDL address plan. `a-data`
  alone spans the internal DMZ at `10.77.62.10`; `a-data-bridge` occupies
  `10.77.62.20` in the DMZ and the fixed engineering conduit address
  `10.77.63.10`. `a-connector`, `a-contractors`, and `a-approval` occupy the
  declared maintenance addresses `10.77.61.10`, `.20`, and `.30`;
  `a-renderer` is maintenance-only at `10.77.61.40`. `a-contractor-bridge` and
  `a-control-broker` are DMZ-only at `10.77.62.30` and `.40`.
- `a-hmi`, `a-historian`, `a-engineering`, and `a-diagnostics` occupy their
  declared engineering addresses `10.77.63.20`, `.30`, `.40`, and `.50`;
  `a-reservoir`, `a-distribution`, and `a-instruments` occupy their declared control addresses
  `10.77.64.20`, `.30`, and `.40`. The two read-entry bridges alone
  provide narrow conduits to the engineering network, while `a-instruments`
  alone spans engineering and control for independent observations.
- `a-contractors` provides the declared narrow field-gateway conduit to the
  DMZ bridge. The connector has no DMZ membership, and neither corporate nor
  maintenance callers can directly address the bridge.
- `fieldlink-customer-consumer` is a real mutual-TLS service on declared port
  443. It binds package and diagnostic routes to distinct supplier identities,
  validates tenant/revision/digest/interface data, executes only
  `diagnostic_summary` in a bounded runtime, and owns the destination audit and
  receipt.
- `customer-handover` is a real TLS service on declared port 8443 and runs as
  `arwc-connector`; the participant context runs as the distinct locked
  `fieldlink` service identity.
- The corporate session is tenant-bound. Protected records, attachment state,
  and audit evidence are inaccessible to `fieldlink` except through the
  declared application routes.

## Build waves

| Wave | Scope | Status |
| --- | --- | --- |
| AHB-00 | Architecture, isolation plan, topology and implementation ledger | Complete |
| AHB-01 | `a-connector` and W01 opening slice | Complete |
| AHB-02 | Corporate W02-W03 association and annex paths | Complete |
| AHB-03 | Remaining corporate W04-W12 and W35 | Complete |
| AHB-04 | Maintenance W13-W15 | Complete |
| AHB-05 | Read-only process routes and W16-W25 | Complete |
| AHB-06 | Control paths W26-W28 | Complete |
| AHB-07 | Consequence, verification, and reporting W29-W34 | Complete |
| AHB-08 | Whole-phase integration, destructive acceptance, pristine restore | Complete |
| AHB-09 | KeplerOps delivery transit, earned corporate handoff, and cross-carrier acceptance | Complete |

## W01 asset decision

W01.3 alone declares
`arwc-documents:pl-arwc-plan-method-01-method`. The image extracts that exact
document from the authored `arwc-documents.json` package during its build and
does not retain the package. W01.1, W01.2, and W01.4 declare no narrative reuse;
their records are owned by the customer-handover service rather than copied
from unrelated narrative material.

## Acceptance gates

Every completed slice must pass black-box normal and malformed requests,
negative authorization, stale/replay and cross-tenant checks, exact addressing,
TLS, filesystem ownership, persistence, no-egress, no-published-port, and
participant-content inspection. Operator state is inspected directly to prove
audits and unaffected records. The full pinned SDL gates are rerun whenever the
SDL changes and again at final acceptance.

Run the current local acceptance pass from this directory with:

```sh
./test-local.sh
```

The participant shell on a running carrier is:

```sh
sudo docker exec -it --user fieldlink --workdir /var/lib/fieldlink-connector cinder-arwc-connector bash
```

## Progress evidence

- 2026-09-27: Terraform created the dedicated `cinder-arwc-golden` VPC and
  private carrier at `10.77.59.2` with no external address or role grant. Its
  only peering is the dedicated KeplerOps delivery transit; subsequent applies
  are no-op.
- 2026-09-27: The SDL and challenge cards require K26.2/K27.3 destination-side
  execution to supply CORPORATE. The pre-generated corporate session was an
  implementation defect. The build now starts without that session and exposes
  only the declared mTLS consumer for the narrow KeplerOps delivery transit.
- 2026-09-28: Clean-carrier cross-segment acceptance passed for both distinct
  mTLS routes. Signed package activation and support-diagnostic execution each
  ran in the bounded Alterra runtime, wrote destination-owned receipts and
  audit records, earned the handoff, and persisted across connector restart.
  Destructive restoration then verified a pristine pre-delivery state.
- 2026-09-27: W01 passes six black-box tests on fresh volumes. The tests cover
  all four declared routes, exact authored-document reuse, TLS, tenant-bound
  authorization, wrong bindings, stale revision denial, immutable fields,
  service-owned audits, persistence across restart, exact `10.77.60.20`
  addressing, absence of published ports, and denied metadata, Internet,
  Training, KeplerOps, and Shifter-network access.
- 2026-09-27: The participant-visible foothold contains no author contracts,
  operator tests, implementation source, or fourth-wall terminology. Direct
  inspection confirms the service and participant identities remain distinct.
- 2026-09-27: All 16 focused ARWC design tests and the pinned env-packs 6.1.0
  and RAE 5.0.0 gate pass: 136 modules parse/compose, 3,494 requirements and
  281 observations instantiate/compile, and all 120 ARWC card contracts pass
  the native hand-build gate.
- 2026-09-27: W02-W03 add eight passing black-box tests. The deployed service
  performs the association lookup against the supplied row before resolving
  `MR-CRR-4417-R6`, and the annex importer checks `attachments/` before one
  percent-decode and canonicalization pass. Protected results remain dependent
  on freshly observed source records; wrong sessions, tenants, associations,
  revisions, and unencoded paths are denied. No narrative asset is placed for
  these six cards because every `narrative_reuse` list is empty.
- 2026-09-27: W04 adds nine black-box tests on `a-archive`. The archive issues
  real one-use, client-auth X.509 identities with caller-controlled OU values,
  consumes the OU from the mutual-TLS peer certificate in the declared
  unparameterized query, and constrains the read-only result to
  `AR-CRR-229`. The helper invokes pinned 7-Zip 23.01 on a submitted archive,
  applies the declared pre-NFKC member check, and permits only
  `copy_handover(HND-PLANNER-06)`. State and independently owned audits survive
  restart; participant access to them is denied. No W04 card binds a narrative
  asset, so none was added.
- 2026-09-27: W05-W06 add eight passing black-box tests on `a-identity`. The
  onboarding path preserves distinct starter and roster records while omitting
  only the assignment factor from activation. Both declared paths into the
  protected rendering work: the limited onboarding session and the independent
  archive-helper handover. OAuth state is checked before the mutable preview
  origin is accepted, and the resulting planner-browser session is bounded and
  delivered to downstream planning through a dedicated read-only evidence
  volume. No W05-W06 card binds a narrative asset.
- 2026-09-27: W07 adds seven passing black-box tests on `a-data`, backed by
  PostgreSQL 16.4. The service constructs the declared quoted-identifier query;
  the closing-quote/UNION path reaches only the protected allocation-adjustment
  view, while semicolons, writes, and unrelated views are rejected. The actual
  `SECURITY DEFINER` reconciliation function is narrowly executable and writes
  only its declared copy. Results and audits persist across restart. No W07
  card binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 38 W01-W07
  black-box checks, including exact addresses and authorization, predecessor
  evidence, persistence, network isolation, no published ports, and
  participant-visible content inspection.
- 2026-09-27: W08 adds six passing black-box tests on `a-archive`. Both the
  temporary-staff and integration-handover prerequisites independently expose
  the same retained bundle. Its hidden script identifies a real RS(14,12)
  exchange with two missing 96-byte data shards over the specified GF(256)
  convention. Reconstructing those shards yields a four-fragment Go 1.22
  `linux/amd64` collector; the assembled executable runs in the participant
  context and its manifest digest is enforced. The collector configuration is
  genuinely protected with the declared HKDF-SHA256 and AES-256-GCM inputs,
  nonce, AAD, and tag, and resolves to `ARC-COLD-CRR-2019` only after successful
  authenticated decryption. No W08 card binds a narrative asset.
- 2026-09-27: W09 adds seven passing black-box tests across `a-business`,
  `a-data`, and the DMZ-only `a-data-bridge`. PostgreSQL holds the declared
  allocation and distinct meter records; reconciliation computes the exact
  report, reserve, allocation, overstatement, and margin values from those
  rows. The integration gateway requires independently owned business-read and
  data-reconciliation evidence, rejects the stale feed, and returns the current
  feed only through the bounded planning-data conduit. Direct connector access
  to the DMZ is denied. No W09 card binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 51 W01-W09
  black-box checks. Direct inspection confirmed exact corporate/DMZ addresses,
  internal-only networks, a DMZ-only hardened bridge, PostgreSQL ownership and
  grants, restart persistence, and no published service ports.
- 2026-09-27: W10 adds six passing black-box tests on `a-business`. The report
  assistant exposes the bound Cairn source-selection record with three named
  current sources. Its retrieval path enforces the planning-reader role while
  omitting the session-district predicate, exposing only the Merewick excerpt;
  the linked-document path then authorizes possession of that excerpt without
  comparing document district and returns `PLN-MER-DP3-R6` revision 6. Wrong
  authorities, tenants, objects, roles, and revisions disclose nothing. No W10
  card binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 57 W01-W10
  black-box checks, after which all mutable results, audits, and evidence were
  removed and the authored initial state was verified.
- 2026-09-27: W11 adds six passing black-box tests on `a-data`. The relation
  proxy parses a real Bolt 5.4 negotiation and chunked PackStream
  HELLO/RUN/PULL exchange, enforces the supplied asset, association, query
  shape, and read-only clauses, and emits framed Bolt SUCCESS/RECORD results.
  Its unparameterized certificate-OU relationship construction reaches only
  the declared lineage from `CRR-OG-LEGACY-2` through `OG-CRR-02` to
  `AST-CRR-017` and `ARC-COLD-CRR-2019`. Both W02.2 and W09.DATA independently
  unlock the contract. No W11 card binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 63 W01-W11
  black-box checks, followed by verified authored-state restoration.
- 2026-09-27: W12 adds seven passing black-box tests on `a-archive`. The
  quarantine object uses real AQTN1 length/digest/build framing; its samples
  exercise HKDF-SHA256-derived AES-256-GCM and AES-256-KW keys plus tag-failure
  behavior. Authenticated recovery yields exactly 37 immutable records, index
  R6, retired certificate `COLLECT-2019-12`, its wrapped PKCS#8 object, and
  `IDREL-COL-R4`. The current exchange verifies the old certificate chain,
  rollover signature, and private-key proof, then grants one ten-minute
  read-only session for `CUR-COL-CRR-R11`. No W12 card binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 70 W01-W12
  black-box checks, followed by verified authored-state restoration.
- 2026-09-27: W35 adds six passing black-box tests on `a-business`. The exact
  authored `arwc-documents:as003-agreement-summary` is extracted at build time
  and verified byte-for-byte without retaining unrelated package content. The
  public replacement catalog remains distinct from the settlement tariff; the
  role-filtered quote lookup omits district membership, and the order path
  preserves Merewick's supplier, 0.75 ML quantity, and delivery window while
  charging USD 1,710 to Cairn budget `BUD-CRR-DP3`. The issued order and audits
  persist, while retries remain idempotent.
- 2026-09-27: A destructive clean-volume rebuild passed all 76 W01-W12/W35
  black-box checks, followed by verified authored-state restoration.
- 2026-09-27: W13 adds four passing black-box tests on `a-contractors`. The
  appointment and roster remain distinct records; attendee maintenance enforces
  the Veybridge organization but intentionally omits per-attendee authorization,
  while preserving the inspection, asset, and visit window. Check-in consumes
  the updated attendee and separate roster, issuing only the declared
  `SCOPE-INSP-CRR-4417` field session. No W13 card binds a narrative asset.
- 2026-09-27: W14 adds five passing black-box tests across `a-contractors` and
  the DMZ-only `a-contractor-bridge`. The field bag contains the exact current
  and retired endpoints, and the gateway accepts a strict CBOR map only for the
  scoped current/read request. JSON, stale timestamps, nonce replay, retired
  paths, and wider scopes are denied. Only the current inspection reading is
  returned. No W14 card binds a narrative asset.
- 2026-09-27: W15 adds five passing black-box tests on `a-approval`. Both the
  field-session and planning-read authority branches reach the exact maintenance
  association. The cache key intentionally omits revision and upstream identity;
  pinned Chrome-for-Testing 128.0.6613.137 executes the nested-frame message
  flow, including the declared source-identity omission. The bounded review
  action produces a real Ed25519-signed approval whose signature is independently
  verified. No W15 card binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 90 W01-W15/W35
  black-box checks. Direct inspection confirmed all nine hardened containers,
  exact corporate/maintenance/DMZ addresses, internal-only non-attachable
  networks, no published ports, no connector-to-DMZ path, and no carrier external
  address or VPC peering. The environment was then restored and its authored
  initial state verified.
- 2026-09-27: W16 adds five passing black-box tests on `a-archive`. A real
  eight-opcode, four-byte-instruction sequencer enforces the 64-instruction and
  4,096-experiment bounds, performs its sample read before the late 32-index
  authorization check, and exposes only deterministic cycle state. The
  acceptance path recovers all 32 bytes in slots 160-191 through TEST timing,
  validates the internal CRC32C and R8 binding, denies writes and replay, and
  persists its service-owned evidence. No W16 card binds a narrative asset.
- 2026-09-27: W17, W18, W21, and W25 add thirteen passing black-box tests across
  `a-hmi`, `a-historian`, `a-engineering`, and `a-instruments`. The two earned
  read branches issue hashed, scope-bound sessions through separate bridges.
  Current process state, mode, tag and scale records, revision comparison, and
  the isolated practice model remain separately owned and independently
  observed. Exact card-bound `me-engineering-note-01-1`, `me-commissioning-01`,
  and `me-project-handover-01` content is extracted during image builds and
  verified byte-for-byte; unrelated narrative content is absent.
- 2026-09-27: A destructive clean-volume rebuild passed all 108
  W01-W18/W21/W25/W35 black-box checks. Direct inspection confirmed all thirteen
  hardened containers, exact addresses, internal-only networks, no published
  ports, no direct participant route to engineering or control, persistence,
  and independently owned audits. The environment was then restored and its
  authored initial state verified, including absence of process sessions and
  derived evidence.
- 2026-09-27: W19 adds four accepted paths backed by a stripped static x86-64
  ELF. The artifact embeds the declared long/compatibility transfer and exact
  32-bit rolling/64-bit verification recurrences; its ordinary traces,
  distinguishing wrap case, complete decision set, and historical R19-to-R21
  mapping are checked by the owning service. The mapping remains explicitly
  historical and does not substitute for deployed-revision evidence.
- 2026-09-27: W20 adds three accepted paths backed by an 8 KiB instrument flash
  image. Its 64-byte little-endian records use real CRC32C and commit markers.
  The accepted rewrite is replayed as ordered 1-to-0 NOR programming into a new
  sequence, reparsed across the complete image, and rejected if it changes any
  unrelated logical record, wear count, asset, or inspection date.
- 2026-09-27: All eight new W19/W20 black-box tests pass, taking the suite to
  116 tests. The persistent results and owned audits survived service restart;
  the original ELF and flash image remained immutable. Destructive test state
  was then removed and the expanded authored initial state verified.
- No SDL change was needed through W21/W25. The validated contracts fully
  determined the observable W01-W21, W25, and W35 behavior; request serialization,
  narrow conduit mechanics, and carrier packaging are incidental implementation
  detail.
- 2026-09-27: W22 adds five passing black-box tests on `a-engineering`. The
  delivery contains a real Nim 2.0.8 linux/amd64 viewer and a deterministic
  eight-opcode program; executing and independently emulating it derives the
  AES-256-GCM project key. Wrong keys and project bindings return the same
  authentication failure. The opened package supplies the retained helper and
  historical archive context without granting current identity, approval, or
  control authority. The .NET 8 ReadyToRun helper has post-compilation native
  immediates that yield the concealed reviewer while its unchanged managed IL
  yields the listed benign reviewer when ReadyToRun is disabled. No W22 card
  binds a narrative asset.
- 2026-09-27: A destructive clean-volume rebuild passed all 121
  W01-W22/W25/W35 black-box checks. Direct inspection again confirmed exact
  addresses, hardened containers, internal-only networks, no published ports,
  no participant egress, and no participant-visible operator or fourth-wall
  content. Persistent W22 results and owned audits survived restart; the
  delivered viewer, program, package, and helper remained immutable. The
  environment was then restored and its expanded authored initial state
  verified.
- No SDL change was needed for W22; the existing contract fully specified the
  VM encoding and bounds, key derivation, authenticated-package behavior, and
  ReadyToRun representation mismatch.
- 2026-09-27: W23 adds five passing black-box tests on the new engineering-only
  `a-diagnostics` service. The delivered stripped C++20 x86-64 estimator runs
  in its declared glibc 2.39 environment and exposes the exact 0x90-byte
  measurement object. The bounded duplicate/coalescing sequence demonstrates
  the stale-index state violation; deterministic tcache reuse controls only
  `reserve_ml` and `quality`, preserving the district and vtable. The resulting
  13.40 ML Cairn Reach estimate is accepted for `ALLOC-CASE-CRR-33` while North,
  Merewick, raw process observations, and independent instruments remain
  unchanged. Wrong authority, tenant, operation sequence, offset, and protected
  field are denied; owned evidence and audit survive restart. No W23 card binds
  a narrative asset.
- 2026-09-27: Focused W23 acceptance passed all five checks after earning the
  process-read session through W01-W09. Direct inspection confirmed exact
  `10.77.63.50` addressing, engineering-only attachment, no published port,
  read-only root filesystem, all capabilities dropped, and
  `no-new-privileges`. Destructive state was removed and the expanded authored
  initial state verified. The suite now contains 126 black-box checks.
- No SDL change was needed for W23; the existing contract fully specified the
  native runtime, object and allocator behavior, writable fields, preserved
  estimates, and evidence boundary.
- 2026-09-27: W24 adds six passing black-box tests on `a-diagnostics`. A real
  RSA-2048/e=65537 PKCS#1 v1.5 recovery interface implements all four declared
  response classes, persistent 4,096-query accounting, repeat and range
  handling, and the exact xorshift128+ response rotation. A black-box
  Bleichenbacher interval search through the participant route recovered the
  unique `ENG1` unlock and opened `DIAG-EVID-CRR-R7` after 3,824 oracle
  responses; prior negative checks brought the accepted instance total to
  3,827, still within the authored bound.
- 2026-09-27: The opened W24 bundle contains the stripped native
  `DSIGN-CRR-R3` verifier and exactly 16 real CRR25519-S records. Every retained
  signature was independently checked. The declared high-nonce disclosures and
  signed low-60-bit delta recover the existing scalar, whose public point
  matches the service identity; a newly generated signature is accepted only
  for canonical request `EXP-CAL-CRR-25` at project revision 21. Archived
  replay, wrong scalar, wrong tenant, wrong authority, selector replay,
  ciphertext replay, and out-of-range queries are denied. The resulting scope
  is diagnostic export only and grants neither maintenance approval nor control.
- 2026-09-27: W24 state, its 3,825 unique-ciphertext ledger, and owned audits
  survived restart. Direct inspection confirmed `a-diagnostics` remains at
  `10.77.63.50`, engineering-only, without a published port, with a read-only
  root filesystem, zero effective process capabilities, and
  `no-new-privileges`. The carrier was restored to the expanded authored
  initial state. The suite now contains 132 black-box checks.
- No SDL change was needed for W24, and none of its four cards binds a narrative
  asset. The existing contract fully specified the RSA classes and limit,
  selector recurrence, bundle contents, Edwards25519 equations and encodings,
  nonce disclosure, fresh request, and authority boundary.
- 2026-09-27: W26 adds six passing black-box checks across maintenance-only
  `a-renderer` and DMZ-only `a-control-broker`. The renderer requires the earned
  contractor session and independently owned Ed25519 approval, returns exact
  profile `RENDER-MAINT-CRR-R9`, and preserves the declared caller-role omission
  only for controlled package `WP-CRR-CINDER-R1`. Its action surface accepts
  only `fetch_handover(HND-MAINT-CTRL-09)` under `svc-maint-render`; command and
  arbitrary-URL inputs are rejected while the required inspection preview is
  retained.
- 2026-09-27: The broker independently verifies the signed approval and fresh
  renderer attestation but intentionally omits the initiating-role comparison.
  It issues an exact five-minute `CTRL-CLIENT-CRR-26` limited to `OG-CRR-02`,
  `CRR-CTRL-R21`, plan execution, and readback. Wrong evidence, tenant, outlet,
  project, wider action, and wrong client are denied; an accepted readback
  demonstrates the scoped authority without waiving mode, mapping, or release
  limits. Service-owned state and audits survive restart.
- 2026-09-27: Direct inspection confirmed exact `.40` addresses, single-segment
  attachment, no published ports, read-only roots, zero inherited, permitted,
  effective, and ambient process capabilities, `no-new-privileges`, and denied
  metadata and Internet egress. The connector cannot address the DMZ broker
  directly; the participant route is the existing narrow contractor gateway.
  Destructive state was removed and the complete authored initial state was
  verified. The suite now contains 138 black-box checks.
- No SDL change was needed for W26, and none of its four cards binds a narrative
  asset. The existing contracts fully specify the approval and inspection
  binding, both caller-role omissions, bounded renderer action, five-minute
  control scope, and authority boundary.
- 2026-09-27: W27 adds five passing black-box checks across `a-engineering`,
  `a-diagnostics`, `a-data-bridge`, and `a-data`. A stripped native x86-64
  verifier implements the declared little-endian ROT128 recurrence, padding,
  rotations, and length finalization. Six real DPG1 programs freeze its
  decisions, and participant-side execution agrees with an independent
  implementation for every digest.
- 2026-09-27: The DPG1 contract uses a real header, block table, bounded
  instructions, sensor tests, output schema, and two explicitly declared
  padding reservoirs. Independent Gaussian elimination over the 256 reservoir
  bits produces non-identical model and target collisions while structural,
  identical, non-colliding, and out-of-reservoir candidates are rejected. The
  accepted target changes only Cairn Reach to 13.40 ML; North, Merewick, raw
  observations, and independent instruments remain unchanged.
- 2026-09-27: The accepted program traverses the diagnostic service and
  DMZ-only integration gateway into genuine planning consumer
  `PLAN-CONSUMER-R8`. Independently owned consumer state and audit evidence
  survived restart. Direct inspection confirmed exact addressing, no published
  ports, read-only roots, zero inherited, permitted, effective, and ambient
  capabilities, `no-new-privileges`, denied metadata and Internet egress, and
  no direct connector reachability to engineering or the DMZ. A destructive
  clean-volume run passed all five checks and authored initial state was
  verified. The suite now contains 143 black-box checks.
- No SDL change was needed for W27, and none of its three cards binds a
  narrative asset. The existing contracts fully specify the verifier,
  structural collision model, Cairn-only result, planning consumer, and
  unaffected evidence boundaries.
- 2026-09-27: W28 adds five passing black-box checks across `a-engineering`
  and DMZ-only `a-control-broker`. `UTIL-CRR-ISSUER-R4` is a real x86-64 SysV
  PIE built by clang 18.1 against glibc 2.39 with the declared optimizer,
  stack protector, PIE, full RELRO, NX, ASLR, CET-disabled surface, exactly
  16 KiB of executable sections, and `cap_setuid=ep`. The service supplies its
  ELF, relocation table, seccomp policy, immutable relationship record, signed
  live status, and all five ordinary invocations.
- 2026-09-27: Independent frame construction preserves the disclosed canary,
  recovers the PIE base from the declared return offset, pivots at the exact
  saved-frame locations, and uses only the supplied sparse gadget offsets and
  fixed `0x7fff00000000` scenario vDSO surface. Wrong canary, length, session,
  gadget, issuer pointer, extra command field, authority, tenant, and broader
  action are rejected without an issuer result.
- 2026-09-27: The completion path executes the file-capability utility, applies
  its syscall allowlist, performs `setresuid(0,0,0)`, and calls exported
  `issue_client` with `ISSUER-UTIL-OG2-R4` and the current correlation. The DMZ
  broker independently enforces root Unix peer credentials on the fixed
  `/run/arwc/control-issuer.sock` boundary and issues an exact five-minute
  `CTRL-CLIENT-CRR-28` limited to `OG-CRR-02`, `CRR-CTRL-R21`, plan execution,
  and readback. The engineering and DMZ containers retain disjoint internal
  networks; direct TCP, metadata, and Internet egress remain denied. Main
  service processes retain zero capabilities, while the engineering
  container's deliberate `no-new-privileges` exception is limited by its
  dropped bounding set plus the utility's single `SETUID` file capability.
  State and audits survived restart. Destructive test state was removed and
  the authored initial state was verified. The suite now contains 148
  black-box checks.
- No SDL change was needed for W28, and none of its three cards binds a
  narrative asset. The existing contract fully specifies the native ABI and
  hardening, frame layout, sparse surface, privileged issuer call, fixed socket,
  and equivalent bounded control scope.
- 2026-09-27: W29 adds four passing black-box checks across `a-data`,
  `a-data-bridge`, `a-historian`, `a-hmi`, and independently owned
  `a-instruments`. The tariff route requires earned process-read evidence and
  returns `TAR-CRR-DP3-R4` with the exact authored
  `pl-arwc-plan-method-01-method` document. The balance route proves the full
  process-interpretation chain, joins the PostgreSQL 12.00 ML commitment to a
  fresh 12.40 ML instrument observation under one correlation, and yields the
  exact 0.40 ML margin.
- 2026-09-27: The final planning route requires the completed W25 mode
  sequence and both prior W29 results. Its independently owned HMI calculation
  produces `PLAN-CRR-LOSS-1000`: balanced 100-second ramps, a 900-second hold,
  1,000 full-flow-equivalent seconds, 1.00 ML modeled release, 11.40 ML reserve,
  0.60 ML shortfall, USD 1,440 liability, and Stage A under `CONT-DRY-A-R3`.
  It performs no live actuation. Missing evidence, wrong authority, tenant,
  object, revision, quantity, unavailable instruments, and direct internal
  access are denied. Same-correlation owner audits and results survive restart.
- 2026-09-27: Focused W29 acceptance passed after a clean, unseeded W01-W09
  acquisition chain. Direct inspection confirmed exact dual-homed conduit and
  owner addresses, read-only roots, dropped capabilities,
  `no-new-privileges`, no published ports, and no participant route into the
  engineering network. Destructive state was removed and the authored initial
  state was verified. The suite now contains 152 black-box checks.
- No SDL change was needed for W29. Only W29.1 binds a narrative asset, and its
  exact authored document is extracted during the image build without retaining
  the source package or unrelated narrative content.
- 2026-09-27: W30 adds four passing black-box checks across `a-hmi`,
  independently owned `a-instruments`, and the new control-only `a-reservoir`.
  The binder requires a current five-minute control client and exact asset,
  outlet, project R21, map R8, mode R17, envelope R6, plan, revision, and unit
  bindings. HMI and reservoir evidence retain the same caller correlation;
  missing evidence, wrong tenant or authority, stale bindings, and removal of
  either owner prevent completion.
- 2026-09-27: The live route executes the bounded balanced-gate timeline and
  records `ACT-CRR-OG2-30`, while independent instruments integrate exactly
  1.00 ML and record reserve falling from 12.40 ML to 11.40 ML. The joined
  result retains the 0.60 ML shortfall, USD 1,440 replacement liability,
  Stage A continuity notice `CONT-DRY-A-R3`, an intact dam, and no flooding or
  uncontrolled release. Same-correlation audits, ordinary retry idempotence,
  persistence, exact addressing, read-only roots, dropped capabilities,
  no-new-privileges, no published ports, authority-secret redaction, and
  control-network no-egress all passed. Destructive state was removed and the
  authored initial state was verified. The suite now contains 156 black-box
  checks.
- No SDL change was needed for W30, and neither card binds a narrative asset.
  The existing contracts fully specify the multi-authority command binding,
  bounded actuation, independently measured volume, and consequence record.
- 2026-09-27: W31 adds five passing black-box checks on `a-diagnostics` for
  `VAULT-CRR-R5`. The supplied x86-64 DVL1 worker is a real PIE executable
  with NX, full RELRO, and stack protection. Its native parser verifies CRC32C
  before reproducing the exact 16-bit wrapped-length boundary, 0x120-byte
  workspace, disclosed canary, saved-state layout, and build-bound
  `export_history` call.
- The accepted 512-byte record preserves the canary, derives the supplied PIE
  mapping, and invokes only `export_history(HIST-APR-CRR-09)` as
  `svc-diagnostic-vault`. The resulting restricted maintenance history is
  persistent service-owned evidence and explicitly grants neither a current
  approval nor control authority. Wrong authority, tenant, CRC, lengths,
  build, canary, return address, history, and correlation are rejected;
  owner removal prevents completion and ordinary retry is idempotent.
- Exact addressing, absence of published ports, a read-only root filesystem,
  dropped capabilities, no-new-privileges, participant-to-engineering network
  isolation, native posture, immutable audits, and restart persistence passed.
  The suite now contains 161 black-box checks. No SDL change was needed, and
  none of W31's four cards binds a narrative asset.
- 2026-09-27: W32 adds five passing black-box checks around a supplied native
  C++20 ECS replay. The artifact implements the five authored systems in fixed
  order and exposes four distinguishing runs that establish the exact entity,
  component, mutation, and outlet bindings rather than relying on embedded
  names alone.
- The R19 witness starts from the retained 13.40 ML cache, projects 12.40 ML
  after the 1.00 ML request, and accepts against the 12.00 ML commitment. The
  current R21 comparison starts from independently observed 12.40 ML, reaches
  11.40 ML, and rejects. Results are explicitly optional model evidence, grant
  no live authority, and do not replace current observation. Wrong authority,
  tenant, revision, transition, state binding, quantity, and witness are
  rejected; persistence, idempotence, immutable owner audits, and absence of
  instrument or reservoir side effects passed. The suite now contains 166
  black-box checks. No SDL change was needed, and none of W32's four cards
  binds a narrative asset.
- 2026-09-27: W33 adds five focused black-box checks for the instrument-bound
  forecast, exact twelve-interval schedule, accepted 0.81 ML rehearsal, and
  all 27 demand/gain/delay policy cases. Historian, HMI, planning, reservoir,
  distribution, and instrument evidence is correlation-bound and persistent;
  the live reserve is unchanged. The HMI image reuses only the card-bound
  `service-meter-guide` authored document.
- 2026-09-27: W34 adds five focused checks for each of its two alternative
  input paths. Both the W23 estimator and W27 verifier output can refresh
  `PLAN-CONSUMER-R8`, pass the declared consistency rules, change the decision
  from `ALLOC-HOLD-R3` to `ALLOC-EXPAND-R2`, and join the convincing 13.40 ML
  handover to independent 0.81 ML / 11.59 ML process truth without modifying
  W30 or prior evidence. The suite now contains 176 black-box checks. No SDL
  change was needed, and W34 binds no narrative asset.
- 2026-09-27: Final whole-phase acceptance rebuilt all 18 images, destroyed and
  recreated every mutable volume, and passed all 176 black-box checks across
  W01-W35. The pass included exact addressing and authorization, persistence,
  participant-content inspection, container posture, absence of published
  ports, internal target networks, metadata and Internet denial, and denied
  routes to Training, KeplerOps, and Shifter addresses. The retained acceptance
  exit status is zero.
- The whole-phase run exposed the real five-minute planner-session boundary.
  Each correctly authorized browser bootstrap now issues a fresh five-minute
  credential, and the operator-only acceptance harness renews it between long
  test groups. W27 posture inspection was also aligned with W28's declared
  single-file `cap_setuid=ep` utility exception while continuing to require
  zero service-process capabilities and the remaining hardening controls.
- Final static validation passed env-packs 6.1.0 author validation, RAE 5.0.0
  parsing and composition of 136 modules, instantiation and compilation of
  3,494 requirements and 281 source-bound observations, all 16 focused ARWC
  design checks, and the Training, KeplerOps, and 120-card ARWC hand-build
  gates. No SDL change was required.
- After destructive acceptance, `restore-pristine.sh` recreated every volume
  and directly verified the exact authored service states, empty audits and
  result stores, absent earned credentials/evidence, initial 12.40 ML reserve,
  and unchanged immutable inputs before reporting the restore successful.
