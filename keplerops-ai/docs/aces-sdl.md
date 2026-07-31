# ACES SDL Authoring

[`../sdl/`](../sdl/) is the ACES-language-only and sole logical scenario source
root. The composition-only root
[`keplerops-ai.sdl.yaml`](../sdl/keplerops-ai.sdl.yaml) imports the complete
environment module, one green live-activity module, and one behavior module for
each of the ten challenge families. The expanded scenario contains 44
nodes/infrastructure declarations, 45 real software features, 75
content/start-state and design bindings, 112 relationships, ten module-envelope
behaviors, 134 realized challenge behaviors, one non-evaluated green
live-activity behavior, 75 expansion-architecture rows (one still planned), and
134 native conditions, objectives, and challenge evidence requirements. One
additional observed-state proposition, postcondition assertion, and evidence
requirement govern ordinary company-state readback.
Nodes, networks, resources, immutable
software sources and build provenance, sidecar/host dependencies, services,
accounts, content, routes, participant start state, module semantics, and the
complete challenge contracts are not duplicated in pack-local topology,
inventory, asset-plan, portfolio, or build-contract files.

The published PyPI implementation is pinned exactly at `raes==2.0.0` in
[`../validation/requirements.txt`](../validation/requirements.txt). The
build, CI, rehearsal, and validation entrypoints use that same exact version;
no local ACES checkout is consumed. The validator requires every file below
`sdl/` to be an imported ACES `*.sdl.yaml` source, parses every module, and
semantically validates the expanded root scenario.

RAES 2.0.0 also owns the enterprise and fleet intent used by enterprise and fleet design. The
environment declares one Active Directory domain and forest, an AD-authoritative
human account model, two domain-joined employee endpoints, Keycloak as the OIDC
facade, explicit application consumers, range and shared-model tenants/cells,
three carrier trust boundaries, and a stateless tenant-authenticated shared
inference service. These are native `identity_domains`, `identity_forests`,
`identity_facades`, `deployment_tenants`, `deployment_cells`, endpoint persona,
domain topology, federation, placement, and shared-service declarations. No
KeplerOps extension or provider allocation fact carries that authority.

The published distribution and command are named RAES. Version 2.0.0 exposes
the parser, validator, compiler, and contracts through the `raes`,
`raes_processor`, and `raes_contracts` Python namespaces; KeplerOps does not
depend on a local ACES checkout or legacy import aliases. Following RAES
ADR-073, the SDL no longer carries challenge score metrics. Each challenge
condition observes a challenge-specific
proposition, the corresponding postcondition assertion establishes that
proposition from its receipt evidence, and the objective requires the
assertion. The generic evaluation-plane mapping is
[`../experiments/ctf-evaluation-task.yaml`](../experiments/ctf-evaluation-task.yaml).
Fixed challenge values remain concrete KeplerOps evaluator and CTFd content,
not SDL objective semantics.

The retained GCP reference implementation calls
[`../build/gcp/render_sdl_realization.py`](../build/gcp/render_sdl_realization.py)
to expand this root and write an owner-only ephemeral Terraform input. That
file is generated state, never committed authority. Terraform consumes its
networks, assets, resources, feature bindings, addresses, routes, runtime
secret inventory, and least-privilege workload bindings directly. The two
Module 10 gateway-to-object-store dependencies are native ACES `depends_on`
relationships whose credential and capability properties drive the gateway's
existing-secret access; Terraform carries no parallel access list.
The cell image publisher consumes the same generated realization. Root images,
mail-readiness, agent/isolation, bounded-worker, k6, context, and deployment
artifacts derive from native RAES `Feature.source`, `Source.build`, and
`Feature.dependencies` fields. There is no committed software inventory or
runtime-image manifest. Projection schema v3 realizes seven physical range
hosts, 27 range workloads, one shared-model workload, ten logical overlays,
AD endpoints, carrier placements, and both deployment cells. The shared model
image is published once per cell and activated by digest in an IAM-protected
Cloud Run GPU service; ranges consume the cell image lock rather than
republishing it.

This source is materializable but not live evidence. Static RAES validation,
Terraform validation, and source tests do not prove that enterprise and fleet design's topology
is deployed, isolated, resettable, or participant-equivalent.

Green live-activity implementation adds [`live-activity.sdl.yaml`](../sdl/modules/live-activity.sdl.yaml)
as a RAES 2.0.0 module rather than a pack-local scheduler. It defines one
green workforce participant with explicit action contracts for WorkHub, mail,
Jupyter, MLflow/artifacts, and shared-model inference; one runtime-only
simulated workday clock; work and pause windows; one behavior-history
observation boundary; and a v3 autonomous-execution policy with the complete
action, concurrency, storage, inference-token, image-generation, and accelerator
resource-budget vector. The behavior carries `evaluation_authority: none` and
therefore does not widen challenge proof authority.

The golden GCP realization consumes that compiled policy with RAES
`ParticipantScheduler`, `TimeCoordinator`, execution-control, behavior-history,
and resource-budget APIs in a range-ops sidecar. Its five adapters perform
bounded authenticated reads through the real WorkHub, IMAPS, Jupyter, and
MLflow interfaces and a bounded request through the existing shared-model
interface. The sidecar has no proof producer, receipt/signing key, Docker
socket, or challenge-evaluation role; lifecycle hooks drain it before reset,
and its persisted RAES snapshot is deleted with range-owned mutable state.

These counts describe SDL version 0.84.0, not an independent contract;
validators derive the live inventory from the expanded root. Service TCP/UDP
ports, disk policy, TLS inventory, runtime
health inventory, producer tokens, and firewall protocols are projected from
that same realization rather than fixed asset lists.

Configuration and synthetic-content files remain ordinary scenario assets,
but every start-state file is bound to a target and destination through native
ACES content. Dockerfiles and Terraform remain reference realization code; they
may implement the SDL declarations but do not define a second scenario model.

## Initial Company State

Company-state implementation adds one coherent ordinary-data corpus, documented in
[`company-state.md`](company-state.md). Fifteen SDL content placements reference
its canonical digest. Thirteen named-service placements use native RAES 2.0.0
`service-content/1` semantics for ownership, collision rejection, ordering,
canonical-digest readback, observed-state postconditions, evidence, and
observation boundaries. Two Windows endpoint placements remain ordinary node
content.

The corpus does not elevate “historical” data into an ACES concept. Its
represented timestamps are scenario data. Product-specific materializers are
GCP golden adapters, while the portable authority remains the compiled RAES
content-placement plan. Pack validation binds the digest-valued RAES source
version to the self-contained bytes; the fixed corpus needs no per-range
generation or private reset-control semantics.

## ATLAS Semantics

The ACES behavior specifications use the governed
`ai_offensive_behavior_refs` vocabulary for MITRE ATLAS **tactics**. RAES
2.0.0 does not provide a governed ATLAS technique-reference field.

ACES also permits governed `x-<owner>:<term>` values in a behavior
specification's `extensions` mapping. Every module envelope uses
`x-keplerops:portfolio-module`; every challenge uses `x-keplerops:challenge`
for its ID, scoring/time band, dependency, participant interfaces, live-fire
obligation, proof predicate, telemetry profile, reliability target, owning
issue, implementation state, participant copy, flag delivery, proof/event
binding, and implementation evidence. These are canonical SDL data. Human
docs, the deployable CTF board, and runtime proof contracts are validated
projections of them.

`content.core.atlas-technique-catalog` carries the pinned technique catalog,
while `content.core.atlas-challenge-design` assigns every planned row to a
participant action, proof obligation, dependency, real-software surface,
difficulty, time band, and implementation status. Each module envelope binds
its path-step metadata and each implemented challenge binds primary technique
evidence. This keeps complete technique planning in the same ACES document
without claiming that its IDs are a native governed ACES field.

A first-class governed ATLAS technique vocabulary could be a useful future ACES
affordance. KeplerOps does not require it to remain coherent: tactic semantics,
technique curation, and implementation evidence are all SDL-owned.

## Adjacent Roots

- [`../validation/`](../validation/) contains dependency pins, validators,
  generators, and tests.
- [`../experiments/ctf-evaluation-task.yaml`](../experiments/ctf-evaluation-task.yaml)
  maps receipt evidence to the generic evaluation plane without adding
  KeplerOps semantics to RAES.
- [`../aces_contract.py`](../aces_contract.py) extracts bounded runtime and
  validation projections from the expanded SDL.
- [`../oracle/`](../oracle/) only documents the private-view boundary; it
  contains no scenario contract.
- [`../design/`](../design/) only documents the design boundary; it may not
  contain a parallel logical realization or implementation ledger.
- [`../docs/`](../docs/) contains human-readable planning and review material.

[`../validation/validate_portfolio.py`](../validation/validate_portfolio.py)
reads the 134 realized scored challenges from the expanded ACES behavior
specifications and reconciles count, difficulty, board depth, points,
dependencies, native condition/proposition/assertion/objective/evidence chains,
the experiment-task scoring map, implementation state, and
documentation. [`../validation/validate_oracle.py`](../validation/validate_oracle.py)
additionally reconciles all 75 architecture rows, the one remaining planned design, exact 173-row coverage,
grouping limits, module boundaries, dependency closure, and the pragmatic
pre-playtest verification policy.

The pack remains `draft`: the live build, original challenge paths and receipts,
automated module rehearsals, and generation-55 final manual path exist.
Participant proof across Modules 01 through 10 covers all 134 playable
challenge contracts through the retained range and Kasm participant surface.
The proof set covers the original kernels, the Module 01 and Module 02
supply-chain additions, and the Module 03 through 10 full-ATLAS expansion rows.
The one remaining planned design is
`kep-m02-g`, which depends on the physical accelerator attestation decision.
No golden proof is claimed; playtest calibration, release hardening, final
evidence/documentation reconciliation, and the hardware decision remain open.
Software-foundation expansion subsequently expanded that retained range to all 28 VM assets in
the prior SDL release and passed one focused live service gate for each of the
thirteen new software nodes. That result proves the new local service boundaries, not their
participant paths or challenge reliability; the bounded evidence is in
[`software-boundary-proof-report.md`](software-boundary-proof-report.md).
The two Python-package paths use the SDL-declared Gitea PyPI resolver and
separate analysis/worker services and passed their one-pass pre-playtest gate;
no repeated reliability claim is made for them.
