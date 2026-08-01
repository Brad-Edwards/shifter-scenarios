# KeplerOps AI Systems Campaign V2

## Status And Authority

This directory is the design authority for the replacement KeplerOps AI
Systems participant experience. It starts from the participant's operation and
the official MITRE ATLAS requirements, then derives the enterprise required to
make that operation real.

The previous KeplerOps challenge design, module grouping, challenge prose,
user interfaces, API workflows, evidence predicates, and deployed template are
not design authority. They are donor material only. A previous component may be
reused only after the replacement design independently establishes that the
component supports a credible participant action without substituting an API,
test harness, challenge shell, or claimed state for that action.

## Design Order

The campaign is designed and built in this order:

1. Define the Cinder Typhoon mission and complete participant journey.
2. Decompose every required ATLAS row into behavior the participant must
   actually perform.
3. Compose those behaviors into coherent intrusion operations and challenge
   slots, avoiding duplicate or artificial work.
4. Specify what the participant knows, discovers, operates, and observes at
   every step.
5. Derive the victim enterprise, attacker workbench, identities, applications,
   data, vulnerabilities, and dependencies required by those steps.
6. Admit, adapt, or reject existing technical components against the new
   requirements.
7. Build a separate clean enterprise baseline with all identities, services,
   applications, data flows, operations, and participant access working before
   introducing challenge weaknesses.
8. Freeze and prove that neutral enterprise baseline.
9. Layer challenge vulnerabilities, clues, mutable state, observations, and
   scoring onto the working enterprise in campaign order.
10. Validate each operation through the participant surface, then validate the
    complete campaign and exact ATLAS coverage.

Infrastructure convenience, existing APIs, proof code, challenge titles, and
already deployed services cannot change this order.

The enterprise is never assembled out of challenge-specific facades. During
implementation, a normal company workflow must work before an insecure variant
of that workflow is introduced. This keeps infrastructure failures distinct
from challenge defects and provides a reusable clean checkpoint while the
campaign is layered in.

## Design Documents

- [`participant-journey.md`](participant-journey.md) defines the campaign from
  the player's point of view.
- [`challenge-contract.md`](challenge-contract.md) defines what every playable
  challenge must provide and prohibits guess-driven or fourth-wall-breaking
  substitutes.
- [`design-research.md`](design-research.md) records the CTF and AI-red-team
  design evidence and the binding anti-guess rules derived from it.
- [`calibration-contract.md`](calibration-contract.md) defines onboarding,
  difficulty, pacing, fatigue, and participant-feedback constraints.
- [`coverage-contract.md`](coverage-contract.md) defines exact-row ATLAS
  accounting and parent-row treatment.
- [`operation-allocation.md`](operation-allocation.md) allocates all 134 stable
  scoring slots to the nine-act campaign.
- `operations-act-01.md` through `operations-act-09.md` contain the complete
  reviewed catalog of 134 participant operations.
- [`attacker-workbench.md`](attacker-workbench.md) defines the participant's own
  tools, models, mail, browser, terminal, and Internet access.
- [`atlas-coverage-ledger.md`](atlas-coverage-ledger.md) reconciles every exact
  required official row to canonical participant behavior.
- [`enterprise-architecture.md`](enterprise-architecture.md),
  [`component-catalog.md`](component-catalog.md), and
  [`enterprise-workflows.md`](enterprise-workflows.md) define the clean company,
  canonical components and end-to-end ordinary workflows.
- [`identity-and-access-architecture.md`](identity-and-access-architecture.md),
  [`authorization-transition-ledger.md`](authorization-transition-ledger.md),
  and [`access-prerequisite-matrix.md`](access-prerequisite-matrix.md) define
  actual AD/application identity, all earned rights and route grants.
- [`model-and-release-contract.md`](model-and-release-contract.md) defines
  victim/attacker model families, real distillation and exact release lineage.
- [`business-adapter-contract.md`](business-adapter-contract.md) and
  [`deterministic-worker-contract.md`](deterministic-worker-contract.md) define
  real business consequences and objective victim-side workflow automation.
- [`materialization-and-scale-contract.md`](materialization-and-scale-contract.md)
  and [`physical-lab-contract.md`](physical-lab-contract.md) define 200-range
  logical isolation, shared-resource boundaries and actual hardware semantics.
- [`campaign-state-contract.md`](campaign-state-contract.md),
  [`operation-prerequisite-graph.md`](operation-prerequisite-graph.md), and
  [`flag-proof-ledger.md`](flag-proof-ledger.md) define native state, all 134
  acyclic prerequisites and all 134 ordinary proof carriers.
- [`event-critical-route.md`](event-critical-route.md) defines the closed
  39-operation event path through the full completionist range.
- [`qa-and-facilitation-contract.md`](qa-and-facilitation-contract.md),
  [`implementation-plan.md`](implementation-plan.md), and
  [`risk-register.md`](risk-register.md) define build order, participant QA,
  teaching, hardening and delivery controls.
- [`adversarial-review-log.md`](adversarial-review-log.md) records independent
  findings and their design dispositions; [`progress.md`](progress.md) is the
  current checkpoint.
- `ruby validate-design.rb /tmp/ATLAS-2026.06.yaml` mechanically reconciles the
  complete design against the pinned official source and all local ledgers.

## Coverage Contract

The release target is the official ATLAS 2026.06 matrix:

- all 16 tactics;
- 172 of 173 exact technique rows;
- 149 of 150 leaf rows; and
- the sole exclusion `AML.T0010.000 Hardware`.

Coverage is earned only by participant behavior that materially satisfies the
official technique description. Labels, challenge metadata, hidden test calls,
precomputed results, and broad thematic similarity do not count.
