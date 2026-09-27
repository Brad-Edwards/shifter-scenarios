# Alterra Regional Water Company golden-range hand build

This directory is the implementation ledger for materializing the validated
ARWC SDL as an isolated participant environment. The SDL and its owned content
remain the source of truth. Runtime discoveries that change an observable
contract are reconciled there before the implementation changes.

**Status:** The isolated carrier and corporate-network foundation are deployed.
W01-W08 (26 of 120 cards) are materialized and accepted. The customer handover
runs on `a-connector`; association and annex-import paths run on `a-business`;
archive enrollment, query, helper, and retained-collector paths run on `a-archive`; onboarding and
planner-browser paths run on `a-identity`; and the quoted-identifier and
reconciliation paths run against PostgreSQL on `a-data`.

## Boundaries

- The dedicated GCP carrier and VPC have no peering or routes to Training,
  KeplerOps, Shifter, or any other target network.
- Target networks are Docker-internal and publish no ports on the carrier.
  Operator entry is through IAP SSH and `docker exec` only.
- The participant begins in the already-earned `fieldlink` execution context
  on `a-connector`. The private service identity, seed records, mutable state,
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
- Current nodes: `a-connector` at `10.77.60.20`, `a-business` at
  `10.77.60.30`, `a-data` at `10.77.60.40`, `a-archive` at `10.77.60.50`,
  and `a-identity` at `10.77.60.60`, matching the SDL address plan.
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
| AHB-03 | Remaining corporate W04-W12 and W35 | In progress (W04-W08 complete) |
| AHB-04 | Maintenance W13-W15 | Not started |
| AHB-05 | Read-only process routes and W16-W25 | Not started |
| AHB-06 | Control paths W26-W28 | Not started |
| AHB-07 | Consequence, verification, and reporting W29-W34 | Not started |
| AHB-08 | Whole-phase integration, destructive acceptance, pristine restore | Not started |

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
  private carrier at `10.77.59.2` with no external address, peering, or role
  grant. The apply added only Alterra resources; subsequent applies are no-op.
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
- No SDL change was needed for AHB-00 or AHB-01. The validated contracts fully
  determined the observable W01 behavior; request serialization and carrier
  packaging are incidental implementation detail.
