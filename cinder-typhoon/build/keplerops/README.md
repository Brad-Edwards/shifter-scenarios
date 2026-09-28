# KeplerOps golden-range hand build

This is the persistent implementation ledger for turning the validated
KeplerOps SDL into a participant-usable golden range. The SDL and its owned
content remain the source of truth. When hand-building exposes missing bytes,
behavior, placement, or contradictory contracts, reconcile the design and pass
the RAE gates before encoding the change here.

**Status:** K01-K31 are materialized and accepted on the isolated private GCP
carrier. The former local stand-in for K26/K27 has been removed. Both delivery
routes now cross the narrow private transit and execute on the separate Alterra
carrier, where destination-owned receipts earn the corporate handoff.

**Target:** A working, isolated KeplerOps range in GCP project `prod-hwmvjy`,
with all 104 participant paths exercised from the supplied Rowan workstation.
This stage does not create bakes. The real `a-connector` consumer is owned and
run by the Alterra build; KeplerOps contains only the supplier-side delivery
relay and route-specific client identities.

## Non-negotiable boundaries

- Use only native RAE semantics. A genuine upstream expressivity gap stops the
  work for scenario-owner review.
- Implement the vulnerability as the actual software, data, configuration,
  identity, permission, parser, process, or state defect described by the SDL.
  Do not substitute answer endpoints or objective-triggered effects.
- Participant-visible material stays entirely in-world. Tests, contracts,
  challenge IDs, solutions, hints, scoring, flags, and author commentary remain
  outside participant images and interfaces.
- Mutable state persists for the environment lifetime. Fresh test worlds and
  infrastructure recovery are operator concerns, not in-world reset mechanics.
- The participant starts as `rowan` on `k-dev`; carrier access, Docker control,
  service configuration, test sources, and evidence stores are not participant
  surfaces.
- Keep the build modular by node and shared runtime concern. Do not create a
  single 104-challenge application or expose SDL service contracts as content.

## Inventory and design reconciliation

The source design contains 104 owned card contracts across fourteen KeplerOps
systems plus two customer-consumer cards on `a-connector`. The current reusable
asset tree contains the two K09 Build Operations documents and its placement
README; other exact starting material is embedded as service contracts in the
SDL.

Before building each card, its slice manifest must identify:

1. every participant-visible byte sequence or deterministic generation input;
2. the owning node, destination, owner/group, mode, sensitivity and route;
3. exact repository commits, package versions, binary build flags, identities,
   credentials, configuration, initial state and denial behavior that affect
   the path;
4. mutable state and an independently owned audit or observation; and
5. the in-world evidence that makes the next action recognizable.

If the existing content contract does not determine one of those facts, author
it in the correct modular SDL content file and extend the design gate before
implementing it. Backend framework, storage engine and carrier details may stay
open where the contract explicitly permits equivalent behavior.

## Realization architecture

- Use a dedicated private GCE carrier rather than changing the working Training
  carrier. This contains resource demand and lets Training remain a stable
  regression target. The two carriers form one operator-managed golden range;
  no Training-to-KeplerOps network route is added.
- Reproduce the three exact KeplerOps `/24` networks (`10.77.50.0/24`,
  `10.77.51.0/24`, and `10.77.52.0/24`) and an isolated bounded connector
  network at `10.77.60.0/24`. Each named service receives its SDL address.
- Provide only allowlisted routing between those networks. Runtime target
  networks have no public egress and publish no target ports on the carrier.
  The supplier relay alone has carrier egress, fixed to Alterra's private
  connector address; IAP SSH remains the operator boundary.
- Use one container per SDL node: `k-dev`, `k-staff`, `k-identity`, `k-cert`,
  `k-source`, `k-registry`, `k-ci`, `k-preview`, `k-support`, `k-indexer`,
  `k-cloud-api`, `k-workload`, `k-data`, and `k-assistant`. A narrow supplier
  relay presents `connector.arwc.test` internally and forwards only the six
  declared FieldLink routes to Alterra using separate package and diagnostic
  mTLS identities.
- Build shared libraries for HTTP/TLS, exact request parsing, authorization,
  persistent state, audit receipts, deterministic repository construction and
  isolated workers. Domain behavior remains in node-owned modules.
- Terminate real TLS on the declared port 443 services using an operator-created
  range CA trusted by `k-dev`. Do not weaken protocol declarations to HTTP for
  implementation convenience.
- Execute untrusted jobs, native indexer inputs, preview workers, package code,
  and completion jobs in short-lived, resource-limited workers with the exact
  network, filesystem, identity and timeout boundaries specified by their
  contracts.
- Keep tests on the carrier/operator side. Test execution uses one-shot clients
  with read-only mounts; no test source is copied into `k-dev` or a target.

## Build waves

| Wave | Scope | Exit condition |
| --- | --- | --- |
| KHB-00 | Hand-build architecture, work partition and persistent ledger | Every card is assigned to one build wave and the hand-build boundaries and gates are recorded. |
| KHB-01 | Contract extraction, exact-asset gap audit, route/state manifest and dependency map | Every missing design fact has an SDL owner; begin with a complete K01-K03 slice contract. |
| KHB-02 | Carrier, four isolated networks, allowlisted routing, range CA, persistent volumes, shared runtime and `k-dev` entry | Exact addressing/DNS/TLS work; targets have no public route; `rowan` cannot reach the carrier control plane or operator tests. |
| KHB-03 | Opening slice: K01-K03 on `k-dev`, `k-source`, `k-ci` and `k-support` | All ten opening paths work from Rowan's supplied material; G01 is usable and recognizable. |
| KHB-04 | Source/CI/registry foundation: K05-K09, K11, K28-K29, with K02 regression | Real Git history, packages, crypto, compiler VM and isolated job paths work with persistence and negative authorization checks. |
| KHB-05 | Native indexer and preview: K04, K10, K12 | Actual bounded native parser and browser-worker mechanics produce the specified effects without general host access. |
| KHB-06 | Support, staff, identity and certificates: K17-K20, K25 | Obtained sessions, federation, enrollment and delegation are exercisable across their real destination services. |
| KHB-07 | Cloud, data and workload: K13-K16, K30-K31 | Role exchange, export, scheduling, backup recovery and runtime-identity paths work and retain independently observed state. |
| KHB-08 | Assistant: K21-K24 | The pinned model revision, deterministic decoding, retrieval defects, tool action and completion job behave as specified within bounded resources. |
| KHB-09 | Customer boundary: K26-K27 and bounded `a-connector` | Package activation/rollback and diagnostic delivery cross the supplier/customer boundary with both sides' receipts. |
| KHB-10 | Whole-phase integration and participant play pass | All 104 paths, cross-wave joins, persistence, isolation and fourth-wall checks pass from `k-dev`; Terraform is converged and documented. |

KHB-04 may be split into source, CI and registry sub-waves; KHB-08 may use a
larger carrier shape only when the pinned model's measured memory requirement
demands it. A wave is not complete merely because its services start.

## Test gates for every wave

1. Static SDL content, placement and digest tests, followed by the full pinned
   RAE parse/composition/instantiation/compilation gate when SDL changes.
2. Service-level normal, malformed, negative-authorization, replay,
   cross-tenant and persistence tests.
3. Participant-path tests from `k-dev`, using only published in-world material.
4. Worker confinement, target-network isolation, resource-limit and cleanup
   checks for every execution mechanic.
5. Restart tests proving retained state and immutable history survive without
   inventing an in-world reset.
6. A manual author play pass for the completed slice; later waves rerun prior
   entry and downstream joins as integration regressions.

## Progress ledger

| ID | Work item | Status | Evidence / next action |
| --- | --- | --- | --- |
| KHB-00 | Establish hand-build plan and persistent ledger | Complete | This document records scope, architecture, waves and gates. |
| KHB-01 | Extract the card build manifest and audit exact assets | Complete | All 104 contracts are assigned to their owning services; exact K11, K28, and K29 assets are SDL-bound and digest-checked. |
| KHB-02 | Build core carrier and network/runtime substrate | Complete | Dedicated private `cinder-keplerops-golden` carrier, five internal networks, allowlisted router, TLS, persistent volumes and Rowan SSH entry are deployed. |
| KHB-03 | Build and validate K01-K03 opening slice | Complete | Seven black-box suites plus SSH, persistence, worker cleanup, no-egress and no-published-port gates pass locally and on `prod-hwmvjy`. |
| KHB-04 | Build and validate source/CI/registry slice | Complete | K05-K09, K11, K28, and K29 use real package, parser, cryptographic, Git, native compiler, isolated-command, publication, signing, rehearsal, activation, and rollback mechanics. |
| KHB-05 | Build and validate indexer/preview slice | Complete | A hardened native ELF implements the bounded K04 object transition; isolated Chromium/Playwright performs the K10/K12 service-worker render. |
| KHB-06 | Build and validate identity slice | Complete | K17-K20 and K25 persist support state across service boundaries; K19 issues a CA-signed client certificate/private key and staff verifies it by mTLS. |
| KHB-07 | Build and validate cloud/data/workload slice | Complete | K13-K16 and K30-K31 implement authority exchange, coherent export state, recovery namespaces, and short-lived networkless workload execution. |
| KHB-08 | Build and validate assistant slice | Complete | K21-K24 use the exact local Qwen2.5-3B-Instruct revision with deterministic decoding, retained retrieval state, a cross-service tool action, and bounded completion state. |
| KHB-09 | Build and validate connector boundary | Complete | The package and support routes use distinct mTLS identities across the one-flow private transit; Alterra performs bounded destination execution and owns the receipts and audit. |
| KHB-10 | Full integration and participant play pass | Complete | All 104 paths, both earned delivery routes, persistence, isolation, security-posture inspection, clean rebuild, and destructive pristine restoration passed. |

## Current decisions and blockers

- 2026-09-26: The hand build is explicitly authorized. The completed static
  design gate remains authoritative, but runtime claims now require this
  ledger's evidence.
- 2026-09-26: Use a separate KeplerOps carrier so the accepted Training build
  remains stable.
- 2026-09-27: The campaign contract requires K26.2 or K27.3 to be a real
  participant-executed transition. KeplerOps and Alterra therefore use a
  dedicated private peering with one allowed flow: the Kepler carrier
  (`10.77.49.2`) to Alterra's FieldLink consumer (`10.77.59.2:443`). Training,
  Shifter, and all Docker target subnets remain unconnected.
- 2026-09-28: Clean-carrier acceptance exercised both independent transition
  routes. Signed package activation and support-diagnostic execution each ran
  on Alterra, produced destination-owned audit evidence and receipts, earned
  the corporate handoff, and survived connector restart. Both carriers were
  then destructively restored to their authored pre-delivery state.
- 2026-09-26: The 104 contracts distribute as: registry 14, assistant 12, data
  12, support 11, CI 10, source 8, preview 7, developer 6, cloud API 5, staff 5,
  workload 5, indexer 4, certificate 2, identity 1, and connector 2.
- 2026-09-26: Fifty-three contracts use the generic equivalent-backend mechanic
  profile. That is not permission to invent exploit-relevant artifacts during
  coding; their exact starting bytes and configurations must be audited and,
  where absent, added to SDL content first.
- 2026-09-26: K01-K03 are implemented with actual retained Git history,
  Chromium SQLite state, a normalization-order importer flaw, isolated report
  execution and a non-executing staged reconstruction/callback flow. The same
  seven participant-path suites pass locally and on the private GCP carrier.
- 2026-09-26: The GCP carrier is `cinder-keplerops-golden` at private carrier
  address `10.77.49.2`, with no external address. Target listeners remain on
  internal Docker networks and publish no carrier ports; operator entry is IAP
  SSH only.
- 2026-09-26: K05-K08 use exact deterministic registry/workstation archives,
  immutable package versions, scoped publication, a real npm-compatible
  package executed in a networkless Node worker, the FKI1 parser discrepancy,
  and AES-256-GCM/HKDF entitlement fixtures. All eight participant-path suites
  pass locally and on GCP alongside the K01-K03 regression suite.
- 2026-09-26: TLS material rotation now recreates every certificate-consuming
  container atomically; a GCP redeploy test caught and closed the former
  mixed-generation certificate window.
- 2026-09-26: K09 is implemented with exact deterministic CI/cloud archives,
  retained Build Operations records, the actual linked-input authorization
  flaw, account/workspace-bound retained references, and short-lived isolated
  command workers. Workers receive audience-scoped service identities, can
  reach only allowlisted destinations through their private job network, and
  leave independently joined service audit records. Eight K09 suites plus all
  prior regressions pass locally and on GCP.
- 2026-09-26: K09 hand-building exposed a runtime-only proof-transport defect:
  a stopped container's tmpfs was not a durable source for `docker cp`. The
  trusted wrapper now emits its bounded proof as its sole container log record,
  while participant command output remains captured inside that proof. This
  preserves the declared job/result semantics without changing the SDL.
- 2026-09-27: Direct runtime inventory found that the four isolated-job
  authorities are brokered by Docker Engine 29.8.1/API 1.56 through
  `/run/fieldkest-runner/runner.sock`, rather than the previously declared
  per-service containerd sockets. The SDL was reconciled first, then the
  implementation and direct engine/socket checks; the full pinned env-pack,
  RAE parse/composition/instantiation/compilation, focused-design, and all
  three hand-build design gates pass.
- 2026-09-27: The CI workspace contract now declares `fieldkest-ci` as a
  member of `fieldkest-runner`. This is the minimum relationship required for
  the authenticated workspace GET/PUT application routes to traverse the
  runner-owned `0710` workspace root while preserving per-workspace mounts for
  short-lived children.
- 2026-09-27: Before cross-carrier integration, fresh-volume acceptance passed 50 black-box tests: 7 opening, 8
  registry, 2 K04, 8 K09, 5 K11, 3 K28, 8 declared-component, 6 platform, and
  3 delivery tests. Direct checks additionally prove exact container
  addressing, internal-only networks, no host-published participant ports,
  denied Internet/metadata/Training access, networkless short-lived workers,
  native Gitea 1.25.2, Verdaccio 6.1.6, PostgreSQL 16.4, Kerberos, Chromium
  140.0.7339.207, Docker API 1.56, and persistence across service restarts.
- 2026-09-27: Participant-visible authored and deployed state contains no
  fourth-wall terminology. Operator tests and this implementation ledger are
  kept only on the carrier control surface and are absent from `k-dev` and the
  participant service interfaces.
- 2026-09-27: The pre-integration checkpoint removed only KeplerOps containers and named volumes,
  then redeployed from the authored build. All 27 persistent volumes share the
  fresh creation time `2026-09-27T00:39:20Z`; CI jobs/rehearsals, registry
  publications, Rowan workspace files, and residual short-lived workers are
  all zero. No participant workflow was invoked after this reset.
- No RAE expressivity blocker is currently known.

## Accepted implementation notes

- K11 is a deterministic retained Git repository, link map, bytecode corpus,
  and real `fieldkest-policyc` ELF. Fresh nonces are single-use and final
  acceptance executes the retained binary.
- K28 is an archived native connector with a fixed build identity, signed
  configuration, HKDF-SHA256/AES-GCM module, and bounded service corpus.
- K29 restores an Ed25519 seed from reachable deleted Git history, verifies a
  fresh signature, and exercises distinct v2/v3 consumers through the private
  release rehearsal and rollover path.
- Service state and audit streams are volume-backed. Acceptance deliberately
  mutates them; finalization removes only KeplerOps volumes and recreates the
  authored initial state before handoff.
- `restore-pristine.sh` performs that finalization, verifies that no package
  publication, diagnostic job, or rehearsal result remains, and rechecks the
  relay's non-root, capability-free runtime posture.
