# KeplerOps SDL hand-build readiness

This is the persistent design ledger for bringing the Cinder Typhoon
KeplerOps phase to a legal, modular RAE SDL that a builder can implement
without inventing gameplay. It survives working-session and context-window
boundaries by recording the agreed scope, plan, decisions, evidence, current
state, and exact next action.

**Status:** Gate passed. KeplerOps is ready for hand-building.

**Out of scope:** building services or images, deploying a range, compiling
golden artifacts, exercising exploit paths against running systems, integration
testing a realization, or playtesting. Those belong to the later golden-range
extension.

## Working rules

- Use only semantics implemented by the pinned upstream RAE parser, semantic
  validator, instantiator, and compiler. Project-private properties may carry
  inert annotation only; no validator or processor may give them scenario
  meaning.
- If a required meaning cannot be represented by legitimate RAE semantics,
  stop and ask the scenario owner before proceeding.
- Vulnerabilities are the authored software, data, configuration, identity,
  permission, and state that make the expected path real. Objectives do not
  manufacture missing behavior or evidence.
- Submission adjudication and organizer recovery from infrastructure faults are
  outside the SDL. Do not add a reset service unless it is an ordinary in-world
  mechanic required by the fiction.
- Do not place challenge, flag, hint, score, or other fourth-wall language in
  participant-visible artifacts.
- Reuse relevant existing challenge and narrative artifacts. Do not relocate or
  repurpose unrelated KeplerOps-AI, Training, or ARWC material.
- Keep modules bounded by stable ownership: world/runtime state by system,
  literal content by owning service, operations by challenge family, and typed
  relationships by actual business integration.
- Test each tranche. Do not claim runtime, integration, or playtest evidence
  from static SDL validation.

## Baseline inventory

Recorded on 25 September 2026 before KeplerOps completion work:

- 104 challenge cards across K01-K31.
- Fourteen logical systems on three KeplerOps subnets.
- Thirty-four cards contain technical drafts; seventy still require full
  technical design.
- 112 operation content entries are placeholder starting-record declarations.
- 157 `cinder_kind` relationship bindings occur in the KeplerOps operation and
  flow modules. Sixteen KeplerOps context bindings and two KeplerOps delivery
  relays in shared route modules also depend on the private interpretation.
- The existing workplace narrative corpus and K09 Build Operations documents
  are candidate authored inputs. Their relevance and ownership must be checked
  record by record; presence alone does not satisfy a challenge contract.
- The declared dependency, difficulty, placement, and authority models already
  provide constraints that completion work must preserve.

The counts are progress indicators, not acceptance criteria. The final gate
derives completeness from the composed SDL and owned asset inventory rather
than trusting these initial totals.

## Overall plan

### 1. Whole-phase contract ledger

Inventory every challenge against its owning system and service, normal
behavior, intended mechanic, identities and permissions, inputs and outputs,
mutable state, discovery path, downstream use, existing assets, missing assets,
and the native RAE structures that carry those facts.

Produce one artifact-ownership matrix and one private-to-native semantic
migration ledger. Read all operations before freezing the shared substrate so
later chains cannot contradict early infrastructure decisions.

### 2. Native-semantic migration

Replace the private meanings of `cinder_kind`, `flow_kind`, `modes`, `guard`,
synthetic contexts, relays, and challenge-surface placement with native RAE:

- infrastructure links and runtime networking for topology;
- listeners and application routes for reachable interfaces;
- accounts, identity authorities, federation, and application RBAC for access;
- typed service integrations, proxies, database access, mail access, file
  services, forwarding, repositories, scheduled jobs, and orchestration where
  they actually apply;
- workflows and action contracts for prerequisites and actions;
- evidence requirements, observations, propositions, assertions, and
  objectives for completion; and
- native content plus filesystem inventories for authored artifacts.

Remove KeplerOps from the private decoder once no accepted KeplerOps check
depends on it. At this stage of the recorded plan, ARWC remained isolated for
its later design pass. Add a gate that rejects the return of private
relationship semantics in KeplerOps modules or relationships.

### 3. Core KeplerOps substrate design

Define the exact three-subnet address and DNS plan, fourteen node endpoints,
service listeners, protocols, routes, local and service identities, application
principals and grants, trust relationships, filesystem roots, state ownership,
persistence boundaries, and supplied developer opening. Keep irrelevant
realization choices open; make versions and platform details exact wherever a
mechanic depends on them.

### 4. System-oriented design tranches

Complete shared service contracts before treating challenge cards as isolated
fixtures:

1. Developer, source, CI, and registry.
2. Preview, indexer, and support.
3. Staff, identity, and certificate services.
4. Cloud API, data, and workloads.
5. Assistant services.
6. Supplier/customer delivery boundary.

Operations spanning several systems close only after every participating
service contract is defined. K26, K27, and K29 receive an exact `a-connector`
consumer contract without prematurely designing the rest of ARWC.

### 5. Exact artifact authoring and placement

For every required file, repository, package, message, record, configuration,
fixture, or retained state:

- reuse a relevant existing asset when it already satisfies the contract;
- otherwise author its exact bytes or deterministic generation input;
- assign one owning node, destination, audience, sensitivity, stability,
  owner/group, mode, and digest;
- bind public material to a real listener and route;
- bind private material to the service that consumes it; and
- define repository history, package/build input, software version, build
  option, and vulnerable configuration whenever the expected path depends on
  them.

Asset authoring is design work. Building repositories, packages, binaries,
images, or running services is not part of this stage.

### 6. Full challenge contracts

Every card must specify normal behavior, the exact expected mechanic, fair
in-world discovery, request and response behavior, authentication and
authorization decisions, failure and denial cases, mutable and persistent
state, isolation, observable completion evidence, usable downstream access,
and continuity after reconnects or ordinary breaks where relevant.

Synchronize each card with its native action contract and evidence requirement.
Preserve the approved prerequisite and difficulty distributions.

### 7. Hand-build readiness gate

The final gate must reject:

- private semantic dependencies or a project-private decoder;
- blank technical designs or placeholder content;
- missing, unowned, multiply owned, or unbound artifacts;
- permissions with no obtainable, recognizable, exercisable identity;
- completion evidence created by the objective rather than the world;
- unspecified exploit-critical versions, build options, software behavior, or
  configuration;
- incomplete multi-system placement or supplier/customer contracts;
- fourth-wall participant content;
- dependency, difficulty, authority, or isolation drift; and
- any core system whose normal and negative behavior a hand builder would have
  to invent.

Run upstream environment-pack validation and RAE parse, composition, semantic
validation, instantiation, and compilation after every tranche. Add focused
positive and adversarial static tests for the contracts introduced by that
tranche. The final result is static design evidence only.

## System ownership map

| System | Primary responsibilities | Operations currently allocated there |
| --- | --- | --- |
| `k-dev` | Supplied developer workstation and retained predecessor material | K01, K03 |
| `k-source` | Source, handovers, retained releases, historical signing context | K01, K11, K28, K29 |
| `k-ci` | Builds, isolated jobs, private consumers, release rehearsals | K02, K06, K09, K20, K29 |
| `k-registry` | Packages, publication, selection, inspection, entitlement | K05-K08, K20, K26, K27, K29 |
| `k-preview` | Release previews and browser workers | K10, K12 |
| `k-support` | Support sessions, customer records, diagnostic delivery | K01, K17, K18, K25, K27 |
| `k-indexer` | Support-bundle indexing and release-exception queue | K04 |
| `k-staff` | Staff workflows and managed identity records | K18-K20 |
| `k-identity` | Corporate identity, federation, and delegation | K18, K20 |
| `k-cert` | Certificate enrollment and represented staff identities | K19 |
| `k-cloud-api` | Cloud authority, job metadata, roles, and scheduling policy | K13, K14, K30, K31 |
| `k-data` | Objects, exports, backups, source history, field archive | K13-K15, K30, K31 |
| `k-workload` | Scheduled and maintenance workload execution | K16, K31 |
| `k-assistant` | Assistant configuration, retrieval, completion, and tools | K21-K24 |

This table identifies ownership, not module completion. Cross-system operations
also require the independently owned records and interfaces on their other
systems.

## Progress ledger

| ID | Work item | Status | Evidence / next action |
| --- | --- | --- | --- |
| KPL-00 | Establish persistent ledger and scope | Complete | This document records the plan, boundaries, baseline, and gate. |
| KPL-01 | Inventory native RAE semantics applicable to KeplerOps | Complete | The [native migration ledger](keplerops-native-semantics.md) maps all private relationship classes to pinned RAE 5.0.0 constructs; no gap is currently established. |
| KPL-02 | Build challenge/service/artifact ownership matrix | Complete | The [ownership ledger](keplerops-artifact-ownership.md) assigns all 104 cards, their initial artifacts, mutable/observed state, relevant reuse, and native RAE bindings. |
| KPL-03 | Design exact core network and node substrate | Complete | All fourteen systems have fixed addresses on the three subnet plans, real listeners and routes, owned storage, local/service identities, scoped authorization, and native orchestration/scheduling/database state where required. Pinned RAE semantic parsing passes. |
| KPL-04 | Complete developer/source/CI/registry tranche | Complete | K01-K09, K11, K20, K26, K28 and K29 have owned deterministic contracts, exact native routes, exploit-critical profiles and action/evidence bindings. |
| KPL-05 | Complete preview/indexer/support tranche | Complete | Preview/browser, bounded indexer, support identity/session, diagnostic and independently observed destination contracts are authored. |
| KPL-06 | Complete staff/identity/certificate tranche | Complete | K18-K20 fix exact encoded-proxy, federation, certificate, SPNEGO, managed-identity and human-presence behavior, including obtained-identity use. |
| KPL-07 | Complete cloud/data/workload tranche | Complete | Management, scheduled-task, backup, recovery, scheduler and runtime identities/routes/state are separate and exact. |
| KPL-08 | Complete assistant tranche | Complete | Model revision and decoding are pinned; retrieval, indirect-instruction, tool and completion effects have exact source/destination evidence. |
| KPL-09 | Complete supplier/customer boundary tranche | Complete | `a-connector` exposes exactly six bounded package/diagnostic routes and scoped principals; no other ARWC internals were added. |
| KPL-10 | Remove placeholders and KeplerOps private-decoder dependency | Complete | Zero KeplerOps `cinder_kind`/flow/context/relay properties or `starting-records` remain; the static gate rejects their return. ARWC has since completed the same migration in its separate readiness ledger. |
| KPL-11 | Full upstream validation and hand-build gate | Complete | env-packs author validation, full semantic composition, instantiation, compilation, compiled binding checks and all focused/design suites pass. No materialization was performed. |

## Decisions and blockers

- 2026-09-25: Design-first scope confirmed. The endpoint is a legal modular
  KeplerOps SDL ready for hand-building, not a running implementation.
- 2026-09-25: Core infrastructure is designed after a whole-phase contract
  inventory, then completed in system-oriented tranches.
- 2026-09-25: The customer boundary was designed as an exact external consumer
  contract without prematurely defining downstream ARWC internals. Those
  internals have since been completed in the separate ARWC design stage.
- 2026-09-25: The initial RAE 5.0.0 audit found native homes for every current
  private relationship class. Static connectivity, authentication,
  authorization, participant applicability, and evidence must remain separate
  facts during migration.
- 2026-09-25: The 104-card ownership pass selected exact mechanic families and
  service owners. Existing narrative content remains authoritative background;
  K09 Build Operations records are direct challenge inputs; protected technical
  fixtures are authored separately and never inferred from ambient documents.
- 2026-09-25: Every card now carries one deterministic service-owned contract
  with exact native surface bindings, request, denial, state, persistence and
  evidence rules. Multi-service outcomes use native objective targets and
  observation sources on every independent producer.
- 2026-09-25: Exploit-critical profiles fix the C++ layouts/builds, Unicode
  parser disagreement, AES/HKDF contexts, eight-opcode VM, browser origins and
  service-worker scope, identity/certificate/delegation omissions, assistant
  prompt/tool behavior, Ed25519 rollover and scheduler-attestation behavior.
- 2026-09-25: Qwen2.5-3B-Instruct is pinned to
  [immutable upstream revision `14d7620ba47cf51be0b176e14e27e38a34d4ff88`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/commit/14d7620ba47cf51be0b176e14e27e38a34d4ff88);
  deterministic decoding and the prompt template are part of the K21/K22
  contracts.
- No upstream expressivity blocker has been established. If one is found, work
  stops for scenario-owner review.

## Validation log

- 2026-09-25: The composed campaign parsed and passed native semantic
  validation with pinned `raes==5.0.0` after the KeplerOps substrate tranche.
  This covers SDL structure and native cross-reference validity, not content,
  operation-contract, hand-build, runtime, integration, or playtest readiness.
- 2026-09-25: The 104-card structural hand-build gate passes with 104 exact
  fixture contracts, 104 action/evidence bindings, 14 fixed KeplerOps systems,
  the bounded customer connector and no KeplerOps private relationship meaning.
- 2026-09-25: Full RAE 5.0.0 semantic parsing passes after exact route binding
  and multi-service evidence joins.
- 2026-09-25: The final pinned command passes env-packs 6.1.0 author validation,
  RAE semantic composition of 116 imports, instantiation and compilation of
  3,476 realization requirements, and 281 exact compiled observation bindings.
  The 13 KeplerOps, 17 K09, and 15 Training focused tests pass; both design
  validators pass; the authoring generator is idempotent.

No KeplerOps runtime or materialization claim has been made. Training and ARWC
validation results remain in their separate readiness ledgers and do not prove
KeplerOps runtime behavior.

## Resume point

KeplerOps is ready for hand-building. Stop here. The next authorized stage is a
progressive golden-range hand build using these contracts; it has not started.
Do not create repositories, binaries, packages, models, services, images,
deployment state or evidence adapters until that later stage is explicitly
started.
