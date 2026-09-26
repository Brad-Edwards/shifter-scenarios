# KeplerOps golden-range hand build

This is the persistent implementation ledger for turning the validated
KeplerOps SDL into a participant-usable golden range. The SDL and its owned
content remain the source of truth. When hand-building exposes missing bytes,
behavior, placement, or contradictory contracts, reconcile the design and pass
the RAE gates before encoding the change here.

**Status:** K01-K09 opening, registry, and Build Operations runner slices are
accepted locally and on the private GCP carrier. K11 design and implementation
are in progress and are not yet accepted, SDL-bound, or deployed.

**Target:** A working, isolated KeplerOps range in GCP project `prod-hwmvjy`,
with all 104 participant paths exercised from the supplied Rowan workstation.
This stage does not create bakes and does not materialize ARWC beyond the
bounded `a-connector` consumer needed by K26 and K27.

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
  IAP SSH is the operator boundary.
- Use one container per SDL node: `k-dev`, `k-staff`, `k-identity`, `k-cert`,
  `k-source`, `k-registry`, `k-ci`, `k-preview`, `k-support`, `k-indexer`,
  `k-cloud-api`, `k-workload`, `k-data`, `k-assistant`, and the bounded
  `a-connector` consumer.
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
| KHB-01 | Extract the card build manifest and audit exact assets | In progress | K01-K09 exact bytes, placement, routes and state are reconciled and validated; continue the audit immediately ahead of each remaining wave. |
| KHB-02 | Build core carrier and network/runtime substrate | In progress | Dedicated private `cinder-keplerops-golden` carrier, four internal networks, allowlisted router, TLS, persistent volumes and Rowan SSH entry are accepted; extend node inventory per wave. |
| KHB-03 | Build and validate K01-K03 opening slice | Complete | Seven black-box suites plus SSH, persistence, worker cleanup, no-egress and no-published-port gates pass locally and on `prod-hwmvjy`. |
| KHB-04 | Build and validate source/CI/registry slice | In progress | K05-K08 and K09 pass sixteen black-box suites locally and on GCP alongside the K01-K03 regression: real package/parser/cryptographic mechanics plus actual isolated command execution, scoped 180-second worker identities, authenticated service joins, persistence, cancellation and cleanup. Continue with K11, then K28 and the dependency-ready K29 surfaces. |
| KHB-05 | Build and validate indexer/preview slice | Not started | Native and browser workers require dedicated confinement tests. |
| KHB-06 | Build and validate identity slice | Not started | Includes support, staff, identity and certificate integration. |
| KHB-07 | Build and validate cloud/data/workload slice | Not started | Includes persistence and runtime-identity integration. |
| KHB-08 | Build and validate assistant slice | Not started | Measure the pinned model before finalizing carrier sizing. |
| KHB-09 | Build and validate connector boundary | Not started | Materialize only the bounded consumer contract required by K26/K27. |
| KHB-10 | Full integration and participant play pass | Not started | Final hand-build gate; no bake is produced here. |

## Current decisions and blockers

- 2026-09-26: The hand build is explicitly authorized. The completed static
  design gate remains authoritative, but runtime claims now require this
  ledger's evidence.
- 2026-09-26: Use a separate KeplerOps carrier so the accepted Training build
  remains stable. Cross-segment progression is an organizer/workspace boundary,
  not a network link.
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
- No RAE expressivity blocker is currently known.

## Current K11 work in progress

This subsection is the authoritative handoff for the unfinished K11 sub-wave.
Nothing listed here should be read as an accepted participant path until the
remaining SDL, runtime, test, local, and GCP gates pass.

Completed so far:

- Resolved the old corpus ambiguity without adding a new semantic: `channel`
  and `tenant_class` are required compatibility context but are intentionally
  non-controlling in revision R4. The evaluated policy fields are exactly
  `tenant_state`, `connector_api`, `signer_lineage`, and
  `compatibility_exception`.
- Added an exact K11 asset generator under
  `assets/keplerops/policy-compiler/generation/`. It currently produces a real
  statically linked, unstripped Linux x86-64 `fieldkest-policyc` 2.6.4 ELF, a
  retained link map, four bytecode fragments, a sixteen-case corpus, a Git
  bundle for `fieldkest/policy-compiler`, a source-service state archive, and a
  Rowan handoff archive.
- The compiled program uses the declared twelve-byte `FKPC` header and
  four-byte instructions. Its current program digest is
  `0b9a7fd08148ec1b6d3151dcd9c0499fb89f70585fb3705a44662e062242ef9c`;
  its condition-set digest is
  `e3a8ced4d68bfa6f4b94386b5ff040596bff56e243adbb5aebc98df1b21896a9`.
- Extended the source runtime in progress to initialize and serve the second
  repository, issue persistent one-use policy nonces, validate recovered
  opcode/program models, execute the fixed corpus, and invoke the retained ELF
  for final acceptance. Extended the source and Rowan images to seed the new
  state into both fresh and already-persistent homes.
- Confirmed the generated ELF itself executes the accepted example with exit
  status 0 and rejects the old-API example with exit status 2. Python syntax
  compilation passes for the generator and modified source runtime.

Important unfinished work and gotchas:

- The K11 exact-artifact SDL module, root import, expanded native route
  contract, ownership rows, generator mechanic profile, and validator checks
  have not been authored. The current K11 files therefore are implementation
  WIP, not SDL-complete material.
- The asset generator is not reproducible yet. The ELF remains stable, but the
  GNU link map contains a random `/tmp/cc*.o` name and the local absolute output
  path; rerunning the generator changed the map, Git commit, bundle, and source
  archive digests. Do not freeze the current K11 archive digests in SDL. Fix
  this first by compiling to a fixed object name and normalizing the retained
  map before building the repository.
- The modified source service has not been container-built or exercised. Its
  fragment, corpus, nonce consumption, replay, malformed-program, wrong-scope,
  persistence, and actual-ELF paths still need black-box tests from Rowan's
  supplied interfaces.
- K11 has not been run through the KeplerOps-specific gate or the full pinned
  RAE parse/composition/instantiation/compilation gate. It has not been
  deployed to `prod-hwmvjy`.
- K29 remains dependency-gated. Build only latent source/CI surfaces that do
  not weaken its declared G02 and dossier prerequisites; do not make the full
  K29 participant path available early.

## Resume point

Resume KHB-04 at the K11 determinism issue above. Then:

1. regenerate twice and prove identical binary, map, repository, archive, and
   manifest digests;
2. inspect and test the source runtime locally, author K11 black-box tests, and
   preserve all K01-K09 regressions;
3. reconcile the exact artifacts and clarified context/evaluated-field split
   into a modular native RAE content module and world routes, extend the design
   validator, and pass both SDL gates;
4. deploy the accepted K11 slice to the existing private GCP carrier and rerun
   the full remote suite; and
5. continue with K28, then only dependency-ready K29 surfaces.
