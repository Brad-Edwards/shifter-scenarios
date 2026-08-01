# Campaign V2 Design Progress

Last updated: 2026-08-01

## Objective

Produce an implementation-ready design for a 134-operation, participant-led
Cinder Typhoon campaign against KeplerOps AI Systems. The campaign must feel
like attacking a real AI lab, use real OSS systems and real security effects,
cover every ATLAS 2026.06 row except `AML.T0010.000 Hardware`, and avoid the
old design's guessy, challenge-shaped interactions.

The design review is complete. Clean-enterprise implementation is underway on
the dedicated GCP campaign-v2 template under issue #38. Challenge overlay,
image baking, and participant-range work remain paused until the neutral
enterprise passes its baseline gates.

## Binding Decisions

- The old KeplerOps challenge semantics are non-authoritative. Stable challenge
  IDs and potentially useful implementation components may be reused.
- Design proceeds from participant journey to operations to enterprise
  architecture.
- The participant is a lightly themed Cinder Typhoon operator conducting one
  coherent campaign to steal and compromise Orion assets.
- Every participant action must occur through a surface a real attacker could
  use and must have an observable effect.
- CTF flags are ordinary in-world artifacts or changed-state evidence, following
  the Polaris placement pattern. There is no proof broker or challenge-only
  success API.
- Prompt-oriented operations recognize objective achievement, not an
  author-chosen exact string.
- GLM 5.2 is the shared participant attacker model through an
  OpenAI-compatible endpoint and coding-agent harness.
- No participant query budget is imposed on the attacker model.
- Green, grey, and white simulated participants are deferred until after
  playtesting, and only return if time permits.
- After design approval, implementation builds and proves the complete neutral
  enterprise first, freezes that baseline, and only then layers challenge
  weaknesses and flags.

## Completed Design Artifacts

- `README.md`: authority, scope, coverage, and implementation order.
- `participant-journey.md`: campaign narrative and nine-act participant path.
- `challenge-contract.md`: required per-operation design and QA fields.
- `coverage-contract.md`: exact ATLAS row accounting rules.
- `scoring-and-hints.md`: difficulty, points, and progressive hints.
- `attacker-workbench.md`: participant workstation and attacker services.
- `operation-allocation.md`: first-pass allocation of all 134 stable IDs.
- `design-research.md`: evidence-based anti-guess and playability rules plus
  iterative review protocol.
- `calibration-contract.md`: target tier distribution, onboarding, pacing,
  route, hint, and playtest-calibration constraints.
- `operations-act-01.md` through `operations-act-09.md`: first-pass contracts
  for all 134 allocated participant operations.
- `adversarial-review-log.md`: mechanical baseline, local blocker findings,
  redesigns, and independent-review dispositions.
- `campaign-state-contract.md`: immutable native success records,
  operation-local retry, full reprovision boundary, causal evidence, and flag
  reachability without a challenge controller.
- `access-prerequisite-matrix.md`: exact Act 3 route grants and discoverable
  Accessible/Intermediate Act 4 continuations.
- `event-critical-route.md`: 39-operation event-duration path through the full
  134-operation completionist range.
- `atlas-coverage-ledger.md`: exact 172-row official-name semantic mapping.
- `enterprise-architecture.md` and `component-catalog.md`: clean company,
  canonical OSS services, placement and workflow gates.
- `identity-and-access-architecture.md`, `authorization-transition-ledger.md`
  and `access-prerequisite-matrix.md`: AD/application identity, every earned
  ACL and route grant.
- `enterprise-workflows.md`, `business-adapter-contract.md` and
  `deterministic-worker-contract.md`: ordinary end-to-end workflows, real
  contained impacts and objective challenge-critical workers.
- `model-and-release-contract.md`: fixed model families, distillation and exact
  source-to-runtime lineage.
- `materialization-and-scale-contract.md` and `physical-lab-contract.md`:
  200-range logical isolation, shared-compute limits and real hardware path.
- `flag-proof-ledger.md` and `operation-prerequisite-graph.md`: all 134 native
  carriers and the complete acyclic participant graph.
- `qa-and-facilitation-contract.md`, `implementation-plan.md` and
  `risk-register.md`: build order, validation, teaching and delivery controls.

## Current Counts

- Stable operation slots allocated: 134 of 134.
- Required exact ATLAS rows: 172 of 173.
- Required leaf ATLAS rows: 149 of 150.
- Excluded row: `AML.T0010.000 Hardware` only.
- Detailed first-pass operation contracts: 134 of 134.
- Calibrated difficulty: 40 Accessible, 48 Intermediate, 33 Advanced, and 13
  Expert, worth 31,650 points.
- Operation contracts accepted at design level after adversarial review: 134
  of 134; implementation/playtest evidence remains pending.
- Required ATLAS rows mechanically and semantically accepted in the design: 172
  of 172.
- Prerequisite graph: 134 nodes, no missing references, no cycles, and a
  39-operation critical route with no hidden scored prerequisite.
- Enterprise architecture, canonical component ownership, IAM transitions,
  model/release continuity, business adapters, scale/isolation and hardware
  design: complete.

## Active Work

1. Complete issue #38 by building and proving the clean enterprise before
   applying the campaign overlay.
2. Prove data/training lineage, release/runtime continuity, business workflows,
   observability, worker replacement, and the physical-lab boundary.
3. Keep image baking and participant-range work paused until the clean
   enterprise is complete and has been reviewed from the attack workstation.

## Clean Enterprise Build Status

Six of the fourteen acceptance gates in `enterprise-architecture.md` are fully
proven on the dedicated GCP template:

- redundant AD DNS, LDAP, Kerberos, and replication;
- joined-workstation domain login and Kerberos tickets;
- real threaded internal/external mail with attachments;
- scheduled partner intake through Zammad, Airflow, Tika, Qdrant, the Orion
  model, WorkHub, and Nextcloud with byte-level source preservation;
- Forgejo source and Actions publication into devpi, Verdaccio, and Harbor,
  correlated by exact source revision and OCI digest; and
- independent Cinder workstation, model, mail, Forgejo, MinIO, Jupyter, and
  request-relay surfaces.

The source-publication path is checked by
`template/baseline/source-ci-registries.sh`; it uses only product APIs and
requires the latest main-branch source revision, successful Forgejo workflow,
both package versions, and Harbor revision/tag metadata to agree.

## Publication

- Branch: `keplerops-campaign-v2-design`
- Commit: `57ac552fa9dedf019d1efc4e4a9ba39d117b88d8`
- Pull request: [#39](https://github.com/PaloAltoNetworks/shifter-scenarios/pull/39)
- Git identity: `Brad-Edwards-SecOps`
- Base branch: `main` (the repository has no `dev` branch)

## Independent Review Status

- Earlier full-catalog reviews drove operation recomposition, state, scoring,
  calibration and critical-route design.
- The final fresh round independently reviewed participant playability across
  all 134 operations, enterprise/OSS/materialization feasibility and exact
  ATLAS semantics against the pinned official source.
- Every material finding is accepted and incorporated or explicitly bounded in
  `adversarial-review-log.md`; no design-level finding remains undispositioned.
- The calibrated operation records contain 40 Accessible, 48 Intermediate, 33
  Advanced and 13 Expert operations, worth 31,650 points.

## Known Design Risks

The authoritative build/event risks, signals, mitigations, acceptable
contingencies and owner issues are in `risk-register.md`. The highest remaining
evidence risks are model reliability calibration, exact vulnerable-path
reproduction, physical-bench capacity, shared-inference isolation, fresh-team
timing, concrete per-operation QA, 200-slot load admission and candidate-image
cleanliness. None may be resolved by weakening semantics or awarding proof from
management state.

## Next Checkpoint

Complete and prove the remaining clean-enterprise workflows in issue #38, then
review the company from the participant attack workstation before any challenge
overlay or bake.
