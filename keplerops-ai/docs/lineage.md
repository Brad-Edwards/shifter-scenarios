# Lineage

The machine-readable source of truth is
[`provenance-ledger.yaml`](provenance-ledger.yaml). This page summarizes the
adaptation decisions for humans.

## Sources

### `aisf-vegas-2026`

- Source: Vegas AI Security Forum '26,
  <https://aisecurity.forum/events/vegas-ai-security-forum-26/>
- Captured: 2026-07-10.
- Used: event topic framing around model-weight security, adversarial ML, AI
  red teaming, cyber capabilities of AI systems, supply-chain and infrastructure
  threats, AI insider risk, governance, and policy/security collaboration.
- Excluded: no attendee names, speaker bios, event branding, session text,
  workshop material, CFP forms, logos, or private event content is copied into
  the pack.

### `mitre-atlas-data`

- Source: MITRE ATLAS data repository,
  <https://github.com/mitre-atlas/atlas-data>
- Captured: 2026-07-10.
- Used: all 173 technique ids/names and all 16 tactic ids/names from the pinned
  2026.06 release, assigned to planned challenge modules. The complete catalog
  is a design target; technique-specific implementation and proof remain later
  work.
- Excluded: no ATLAS YAML, generated distribution files, technique tables,
  case-study bodies, tooling, or screenshots are vendored in this skeleton. Any
  later technique mapping stays operator-only unless the visibility gate is
  extended to cover it safely.

### `original-design`

- Source: Palo Alto Networks original scenario design for an AI-security
  live-fire CTF.
- Used: KeplerOps AI Systems premise, offensive participant role, integrated enterprise
  AI-lab direction, draft attack spine, mandatory model-distillation flow,
  tiered experience model, GCP/open-model endpoint boundary, initial metadata,
  and source adaptation boundary.
- Excluded: no real customer data, real model weights, real provider logs, real
  credentials, live tenants, real malware, uncontrolled callbacks, or
  destructive artifact changes.

### CTF portfolio guidance

- `polaris-event-lessons`: local participant-flow, skill-band, agent-parallelism,
  and burst-submission observations from `polaris/lessons-1.md` and
  `polaris/design/architecture.md`.
- `ctfd-scoring-guidance`: CTFd's official dynamic-value and hint documentation,
  used to choose static study scoring and a three-level hint economy.
- `usenix-ctfd-barriers` and `usenix-picoctf-design`: approachability,
  authentic offensive play, path choice, independent challenge breadth, and
  interaction-data design guidance.
- `iclr-cybench`: difficulty-spanning CTF tasks, explicit intermediary
  checkpoints, and agent execution-surface variation.
- Captured: 2026-07-13. No source challenge, solution, participant data,
  platform code, figure, or paper text is copied.

## Local Design Decisions

- The base pack is offensive by default. The participant attacks the AI lab.
- Company-state implementation represents the company baseline as ordinary scenario content, not
  a first-class historical-data ontology. The 61-object synthetic corpus binds
  existing RAES accounts and nodes, uses exact committed dataset/artifact
  bytes, and is partitioned across native product services through RAES
  `service-content/1` placement, ownership, ordering, collision, and readback
  semantics. Product adapters belong to the GCP golden realization. The
  digest-valued RAES source version is bound to self-contained bytes by pack
  validation; no KeplerOps control language or per-range generator is added.
- The finished range should feel like a populated enterprise, using Polaris as
  a reference pattern for integrated live-fire scenario construction.
- The participant chooses among four AI attacks immediately; each targets an
  independent early outcome in 15 minutes. Longer participants choose more
  modules and progress into advanced techniques, up to 8 hours of content.
- Conventional enterprise compromise is not an opening gate. It appears only
  when an ATLAS technique intrinsically requires it inside an AI attack module.
- At least one challenge or connected challenge flow must require a model
  distillation attack.
- The golden build may require GCP-hosted open models. Participant exploit
  attempts must target range-controlled open-model endpoints, not commercial
  model endpoints, including commercial AI endpoints available inside GCP.
- The flag layer is shipped. The generation-17 post-change integrated
  functional proof and generation-18 canonical reset pass. The
  reference-triangle flag remains false until the remaining Modules 08-10
  playtest and hardening work closes. Modules 01 through 07 now pass their
  declared qualifications.
  Post-manual static checks and the earlier Phase-E teardown pass; the current
  rehearsal range is intentionally retained. The profile-bundle flag remains
  false until explicit delivery bundles exist.
- Path-critical services must be real software when built. A reduced local
  profile can support author iteration, but it cannot serve as the golden range
  or replace required services.
- The future model-provider seam belongs inside this pack's inference gateway.
  It should not create a new repo-wide AI provider abstraction.
- Logical-world design established the initial logical world and reference-triangle map.
  That authority now lives exclusively in the modular ACES SDL environment and
  its imported behavior modules; the former parallel topology, software, asset,
  and build projections were removed. That slice did not itself claim a final
  manual walkthrough or golden evidence; the later generation-55 manual result
  is recorded separately.
- Hidden-path and oracle design defines the canonical hidden path, affordance joins, objective
  oracle, scoring and telemetry projections, negative gates, and static oracle
  validation without changing the pack's draft maturity claim.
- Participant telemetry implementation separates observational participant-run telemetry from the
  award-bearing oracle, defines one versioned research envelope and field
  policy, and requires runtime capture, lifecycle, export, validation, and
  documentation to remain aligned without changing the attack path. Its live
  participant-equivalent evidence is recorded in
  [`telemetry-rehearsal-report.md`](telemetry-rehearsal-report.md); structural
  image-update and replacement-generation follow-up is tracked in image lifecycle follow-up.
- Portfolio design defined the initial 60-challenge, 7,500-point portfolio that was
  promoted into first-class behavior specifications in the modular SDL. The
  current source-realized board is 134 challenges and 16,550 points with 3,015
  incremental target minutes, giving 6.28 times the 480-minute event window;
  the 37/58/28/11 accessible-to-expert distribution, dependency DAG,
  manual/agent parity, real-software capacity plan, telemetry joins, and
  reliability gates are validator-bound in the repository.
- The RAES 2.0.0 adoption follows upstream ADR-073, ADR-079, and the
  prerequisite RAES autonomous-activity contracts.
  Each of the 134 challenge receipts now grounds a proposition, postcondition
  assertion, and objective truth chain in SDL. Aggregate scoring is mapped
  through the generic experiment task, while concrete point values remain
  KeplerOps evaluator content. The PyPI distribution is named `raes`, and the
  pack consumes its parser, compiler, validator, and contract APIs through the
  `raes`, `raes_processor`, and `raes_contracts` namespaces.
- Green live-activity implementation implements the first portable live ordinary activity contract as
  `sdl/modules/live-activity.sdl.yaml`. It consumes the RAES 2.0.0 autonomous
  activity, execution-control, shared-time, and resource-budget/fairness
  semantics delivered by upstream RAES autonomous-activity contracts, and models benign
  company activity as a green simulated participant with
  `evaluation_authority: none`. WorkHub, mail, Jupyter, MLflow/artifact, and
  shared-model inference actions bind to the existing core environment; the
  scenario does not add a pack-local scheduler or challenge-proof authority.
  The golden GCP adapter follows the RAES reference `BaseParticipantRuntime`,
  `ParticipantScheduler`, `TimeCoordinator`, durable snapshot, typed
  execution-control, and v3 resource-measurement precedents. It is isolated on
  the range-ops host, uses only real product interfaces, and remains outside
  challenge evaluation and receipt production.
- ATLAS expansion design designs the complete ATLAS 2026.06 expansion in the modular SDL:
  75 participant-sized architecture rows and nine existing-receipt extensions
  cover all 139 rows originally missing from the core without turning 173 techniques into 173
  flags. The complete library contains 135 challenges and 3,045 target minutes;
  the module expansion work implements the fixed contracts, while event-bundle selection
  selects dependency-closed eight-hour event bundles.
- Module 01 expansion implements and automated-proves the first four expansion rows on the declared
  Module 01 WorkHub, gateway, real Chromium, constrained interpreter, OPA,
  PostgreSQL, and proof boundaries. Its generation-25 focused participant pass
  and generation-26 reset/replay advance eight exact mappings to implemented;
  the remaining expansion work then begins with seventy-one designs and 131
  exact technique rows unrealized.
- Module 02 expansion Slice A implements and automated-proves three Module 02 designs
  through signed PostgreSQL/Airflow data consumption, Gitea-to-MLflow/MinIO
  executable model resolution, and contained FastAPI-to-Chromium delivery.
  The focused participant-equivalent pass, representative negatives, three
  receipts, and scoped reset/replay advance four more exact mappings; 68
  designs and 127 exact technique rows remain unrealized.
- Module 02 expansion Slice B implements and automated-proves `kep-m02-h` and
  `kep-m02-m` using the SDL-declared real Gitea PyPI index, pinned pip resolver, and separate
  internal-only analysis and normal-worker services. Its focused Kasm pass,
  representative negatives, two receipts, four-owner scoped reset, and replay
  advance three more exact mappings. The source-implemented synthetic-spearphish
  path then expands the runtime board to 70 contracts and reduces the remaining
  design set to 65, while its three mappings stay planned pending focused live
  proof; 124 exact technique rows therefore remain unrealized.
- Module 03 implementation realizes six context-poisoning behaviors through participant-
  authored documents, pinned MiniLM embeddings, PostgreSQL/pgvector retrieval,
  live-model decisions and citations, OPA, and brokered effects. The generation-
  55 manual path passed all six receipts. A generation-20 Kasm campaign then
  passed A and B across ten clean module-state samples and C through F at 30/30
  live-model trials each, so the SDL records the module as
  `participant-proven`. The campaign used one canonical reset plus the verified
  dataset-store/inference-gateway dependency closure between samples.
- Module 04 implementation realizes the five module-04 behaviors as distinct participant
  challenges: two attacks against the range-local generative model and three
  attacks against a version-pinned scikit-learn privacy classifier. The
  classifier is trained only on a pack-owned synthetic population, private
  membership labels remain oracle-only, and receipts require server-observed
  inference or classification evidence rather than submitted answers.
  The generation-55 manual path passed all five receipts. A generation-21 Kasm
  campaign then passed the two live-model disclosures at 30/30 trials each and
  the three classifier challenges across 10/10 clean module-state samples, so
  the SDL records the module as `participant-proven`.
- Module 05 implementation realizes the five module-05 behaviors through a model-authored
  durable-memory write, PostgreSQL-owned versioned state, a supervised loopback
  worker with database-attested process restarts, later clean live-model use,
  and the existing OPA-backed release-notice broker. Participant-supplied
  state, copied prompts, forged restarts, model-only tool text, and direct proof
  writes cannot satisfy its receipts. A one-pass Kasm participant-surface run
  earned and verified all five reset-bound receipts, including the real worker
  restart and brokered effect. The generation-55 manual path later passed all
  five receipts. A generation-21 Kasm campaign then passed every path at 30/30
  trials, including the real restart and repeated OPA-authorized effects, so
  the SDL records the module as `participant-proven`.
- Module 06 implementation realizes the six module-06 behaviors through participant-created
  PostgreSQL artifacts, real range-local generative and classifier decisions,
  server-owned controls and semantics, bounded black-box probes, disclosed
  surrogate transfer, hidden target revisions, and six reset-bound receipts.
  Caller verdicts, digests, perturbation truth, revisions, budgets, controls,
  and direct proof writes cannot satisfy them. A one-pass Kasm run and the
  generation-55 manual path earned and verified all six receipts. A generation-
  21 Kasm campaign then passed every path at 30/30 trials across five clean
  six-trial module-state batches, so the SDL records the module as
  `participant-proven`.
- Module 07 implementation realizes the six module-07 behaviors through an immutable-base
  PostgreSQL training dataset, participant-authored versioned poison rows, real
  scikit-learn training in Airflow, MLflow run and model lineage, MinIO-backed
  artifacts, server-owned hidden and clean evaluation, and six reset-bound
  receipts. A one-pass Kasm participant-surface run earned and verified every
  receipt, the generation-55 manual path passed all six receipts, and seven
  clean generation-21 participant samples passed per item. The SDL therefore
  records the module as `participant-proven`. A later current-tree composition
  also exposed and fixed the scoped reset's omission of `model-host-01`, the
  SDL-declared owner that restores the immutable teacher object after the
  artifact store is cleared.
- Module 08 implementation realizes the six module-08 behaviors through participant- and
  item-bound PostgreSQL teacher corpora, server-enforced budgets, the live
  range-local teacher, real TF-IDF/logistic-regression proxy training in
  Airflow over the SDL-declared `data-model` TCP/8000 route, MLflow run
  lineage, MinIO-backed artifacts, and live-teacher
  diagnostic/private evaluation. Operational capture retains only aggregate
  counts, fidelity, timing, and keyed digests; prompts, teacher outputs, probes,
  and model weights remain outside that surface. A bounded Kasm
  participant-surface pass earned and verified all six receipts,
  so the SDL records the module as `automated-proven`. The generation-55 manual
  path later passed all six receipts; reliability remains open.
- Module 09 implementation realizes seven module-09 paths from one genuine Module 07
  artifact through strict scikit-learn reconstruction, real MLflow model
  registration and alias transitions, Keycloak-signed approval identities,
  an intentional OPA model-card/release scope confusion, server-only hidden
  evaluation, and post-promotion model reload. PostgreSQL owns participant,
  generation, candidate, approval, promotion, and deployment joins. Operational
  capture retains bounded behavior aggregates, decision classes, authorization
  state, timing, and keyed digests while excluding tokens, trigger/probe bodies,
  predictions, model internals, artifacts, proof bodies, and receipts. The SDL
  records the module as `automated-proven` after a clean bounded Kasm pass
  earned and verified all seven receipts. The generation-55 manual path later
  passed all seven receipts; reliability hardening remains open.
- Module 10 implementation implements the seven module-10 capstone paths without a
  new logical node or parallel specification. The gateway executes the exact
  participant-promoted scikit-learn artifact, joins its trigger to the existing
  OPA-backed broker and passed Module 05/06 state, and issues scoped internal
  transfer capabilities only after passed Module 08 private-fidelity lineage.
  The theft target is the full revision-pinned SmolLM2 `model.safetensors`
  object that `model-host-01` already uploads and verifies in the real MinIO
  artifact store; the participant copies it to the separate contained MinIO
  sink and the gateway independently hashes the destination. Operational
  capture excludes prompts, model bytes, URLs, credentials, flags, proof
  bodies, and receipts. Five bounded Kasm phases in one prepared generation
  passed 17 controls/predicates and independently verified all seven receipts,
  so the SDL records the module as `automated-proven`. The generation-55 manual
  path later passed all seven receipts, including a complete 3,422,777,952-byte
  transfer and independent destination verification. A focused generation-21
  current-tree composition repeated the complete path after the reset-closure
  repair; playtest calibration remains open.
- Manual walkthrough executed all 60 item paths through the external Kasm participant
  surface in one reset generation, independently issued and verified all 60
  receipts, and recorded the sanitized result in
  [`manual-walkthrough-report.md`](manual-walkthrough-report.md). The pack
  remains `draft` pending the remaining Modules 08 through 10 playtest and
  hardening work. Post-manual static checks, reset
  proof, evidence reconciliation, and Phase-E teardown pass.
- Provider packaging fix closes a provider packaging boundary discovered during the Module
  10 rollout. The pack-root Cloud Build ignore contract excludes the entire
  generated `build/` tree, including `.operator` evidence and `.terraform`
  state, while a regression test proves no runtime Dockerfile consumes that
  path. The resulting upload list contains only source inputs needed by the
  SDL-declared images.
- Gateway bootstrap fix records and fixes the Module 10 gateway bootstrap blocker. Native
  ACES dependencies now declare the gateway's artifact read and contained-sink
  write/verify capabilities plus the existing synthetic credential pair. The
  generated realization owns the complete runtime-secret and workload-access
  projection consumed by Terraform, so the fix adds no parallel credential
  specification and requires only the two missing existing-secret member
  bindings in the retained range.
- Proof-readiness fix closes a proof-readiness defect found by the first composed
  prerequisite run. One capstone row supplied only two of the three runtime
  hint tiers, which caused the all-challenge proof join to fail every receipt
  request while the shallow health endpoint remained green. The SDL now
  supplies all three tiers, a 60-row regression enforces the join, and proof
  health constructs the complete realized challenge contract before reporting
  ready.
- Capstone activation fix closes the live capstone activation-join defect found during the
  first participant deployment-trigger pass. The nullable candidate predicate
  is explicitly typed for PostgreSQL and a contract regression preserves that
  query boundary.
- Evidence-namespace fix keeps the participant deployment marker within the shared safe
  evidence namespace after the first successful live deployment exposed its
  original 33-character id.
- Participant transfer import fix adds the two standard-library imports required by the real
  participant-side model download and contained upload after the first theft
  execution reached those call sites.
- Artifact transfer relationship fix adds the native participant-entry to registry-artifacts transfer
  relationship required for the participant to exercise the gateway-issued
  source capability; the existing participant-proof route remains the
  contained destination edge.
- Contained-upload trust fix makes the participant contained upload trust the scenario CA
  explicitly, preserving certificate verification instead of weakening TLS.
- Participant timeout fix preserves the participant HTTP helper's 35-second default while
  allowing the independent full-object destination verification to use the
  capability's bounded 900-second lifetime.
- Capstone verification timeout fix gives only the full-object capstone verification route a matching
  900-second Envoy timeout while preserving the 35-second catch-all for every
  other gateway request.
- Capstone evidence-join fix aligns the final capstone join with Module 09's realized
  `ev-backdoor-verification` evidence and removes the unused abstract
  `ev-model-backdoor` event. The gateway emits only the six directly observed
  capstone events; `telemetry-proof-01` independently derives the final
  `objective_verdict` and capstone receipt after the complete SDL-declared join
  passes, without exposing its component evidence.
- Software-foundation expansion completes the SDL-declared software foundation in the retained
  GCP range: 28 VM assets and 46 real software features are instantiated from
  the ACES realization and immutable image lock. Its focused live gate closed
  COS/CoreDNS binding, Roundcube initialization, SMTP/IMAP readiness, and
  nested rootless-worker integration defects without replacing retained VMs or
  restarting the original 15-node challenge kernel. The bounded evidence is in
  [`software-boundary-proof-report.md`](software-boundary-proof-report.md); it
  is not a participant-path or golden claim.
- Enterprise and fleet design adopts RAES 2.0.0's governed enterprise identity and deployment
  tenancy lineage from ADR-082, ADR-087, and the normative authored-domain and
  enterprise-tenancy specifications. The SDL now declares AD authority,
  domain membership, a one-domain forest, Keycloak federation, application
  identity consumers, endpoint personas, three trust-separated carrier
  placements, deployment cells,
  and tenant-scoped shared inference without a pack-local extension or second
  topology. The GCP projection follows the established Polaris density
  precedent only at the architectural level: logical services are packed onto
  deliberately separated kernels and isolated by container networks. No
  Polaris topology, credentials, provider allocation, or scenario content is
  copied. The concrete projection uses cell-owned VPC/subnet pools, bounded
  firewall policy, a shared immutable repository, encrypted Docker overlays,
  real Windows AD/endpoints, and Cloud Run L4 inference authenticated by each
  range carrier's GCP workload identity. The model pool is stateless; aliases,
  artifacts, receipts, authorization, and reset generation remain range-local.
  The retained 28-VM GCP proof predates this architecture, and live
  materialization, isolation, reset, challenge regression, and targeted
  identity reproof remain required before the new topology contributes golden
  evidence.
- The local reduced profile is explicitly degraded and cannot replace the
  `gcp_full` golden model of record.
- The GCP golden range requires a namespaced tenant with dedicated VPC isolation, no default
  network, no shared-VPC DNS or service-endpoint side effects, controlled
  egress, reset proof, and teardown proof.
