# Alterra Regional Water Company golden-range hand build

This directory is the implementation ledger for materializing the validated
ARWC SDL as an isolated participant environment. The SDL and its owned content
remain the source of truth. Runtime discoveries that change an observable
contract are reconciled there before the implementation changes.

**Status:** The isolated carrier and corporate-network foundation are deployed.
W01 is materialized and accepted: three retained customer records and the
bounded planner-attachment authorization defect run on `a-connector`.

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
- First node: `a-connector` at the SDL address `10.77.60.20`.
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
| AHB-02 | Corporate W02-W12 and W35 | Not started |
| AHB-03 | Maintenance W13-W15 | Not started |
| AHB-04 | Read-only process routes and W16-W25 | Not started |
| AHB-05 | Control paths W26-W28 | Not started |
| AHB-06 | Consequence, verification, and reporting W29-W34 | Not started |
| AHB-07 | Whole-phase integration, destructive acceptance, pristine restore | Not started |

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
- No SDL change was needed for AHB-00 or AHB-01. The validated contracts fully
  determined the observable W01 behavior; request serialization and carrier
  packaging are incidental implementation detail.
