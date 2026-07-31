# `keplerops-ai` - scenario pack

KeplerOps AI Systems is a draft offensive AI-security scenario. The participant is the
adversary: they choose from several AI attack surfaces immediately,
earn independent early outcomes, and can progress into deeper agent, model,
data, distillation, poisoning, supply-chain, impact, and theft attacks.

This pack now ships the modular ACES scenario world, canonical hidden path,
committed participant and runtime assets, flag/CTFd projection, immutable model
supply contract, `gcp_full` build/lifecycle source, and Kasm-only automated live
rehearsal tooling. The completed participant proof campaigns cover all 134
playable challenge contracts through the retained GCP range and Kasm
participant surface. The proof set covers the original kernels, the
supply-chain additions, and the full-ATLAS expansion rows. The retained range
was reset after the Module 10 proof and reported 28 VM
assets, 28 live service health gates, 49 SDL service bindings, 67 declared
routes/endpoints, 10 subnets, and isolated health. One non-playable design,
`kep-m02-g`, remains planned while the physical accelerator attestation
contract is under consideration.
`pack.yaml.status` therefore remains `draft` (`status: draft`), and `golden`
is earned only after the full participant-equivalent proof described in
[`docs/golden-readiness-checklist.md`](docs/golden-readiness-checklist.md).

Identity, version, authors, status, and shipped layers live in
[`pack.yaml`](pack.yaml). Product/catalog projection lives in
[`pack.compatibility.yaml`](pack.compatibility.yaml). Source, licensing,
adaptation, safety, and publication-review facts live in
[`docs/provenance-ledger.yaml`](docs/provenance-ledger.yaml).

## Design Intent

The finished scenario should be an integrated, live-fire AI attack board, not
an isolated prompt puzzle or a traditional intrusion with an AI system at the
end. Enterprise identities, applications, documents, repositories, workflows,
telemetry, datasets, model artifacts, and resettable state support the AI
attacks but do not gate the participant's first challenge.
Polaris remains a construction reference for live-range density and
participant-equivalent proof, not for adding pre-AI attack steps.

SDL version 0.84.0 now expresses the corrected portable enterprise/fleet
intent using native RAES 2.0.0 semantics: a real AD forest and AD-integrated
DNS, domain-joined workforce and ML endpoints, AD-authoritative human accounts,
Keycloak federation, explicit application identity consumers, three packed
Linux carrier trust boundaries, isolated deployment cells, and stateless
tenant-authenticated shared inference. It also imports a RAES 2.0.0
live-activity module for one green, non-evaluated workforce participant with
explicit action contracts, shared-time windows, observation boundaries, and
scoped resource budgets. The GCP source projects that authority
into seven range kernels, encrypted container overlays, cell-owned networking
and images, real Windows AD/endpoints, and an IAM-protected shared L4 inference
pool. This is materializable source, not live proof. The retained 28-VM GCP
range predates that realization and remains evidence only for its previously
exercised challenge contracts.

MITRE ATLAS is the operator-side design spine. The catalog maps all 173
techniques in release 2026.06 to planned challenge modules. That is a board-wide
coverage target, not a claim that one participant executes every technique.
One hundred seventy-two exact techniques, 149 of them leaves, are proven across
the 134 playable challenge contracts and nine existing-receipt parent-row
extensions. The only unproven row is the reserved hardware design while the
physical accelerator attestation contract is under consideration. Every
claimed technique still needs release hardening and final evidence
reconciliation before golden. Operator-only ATLAS mappings stay out of
participant-facing content.

The modular files below [`sdl/`](sdl/) are the one and only logical source of
truth for everything a consuming range must realize: nodes, networks,
resources, software features, services, identities, content, routes,
participant start state, and challenge behavior specifications. Provider code
may implement those declarations, but it may not redefine them in a parallel
pack-local topology or inventory. The published parser and semantic model are
exactly pinned to PyPI `raes==2.0.0`.

The scenario's governed ATLAS semantics live in the
`raes==2.0.0` surface
`behavior_specifications.<module>.ai_offensive_behavior_refs`, which classifies
the ten modules by ATLAS tactic. RAES 2.0.0 does not expose a governed ATLAS
technique field, so the pinned 173-technique catalog is carried as the ACES
`content.core.atlas-technique-catalog` dataset. Implemented technique bindings
live on the corresponding governed challenge extensions.

Model distillation is mandatory. At least one challenge or connected flow of
challenges must require the participant to abuse a teacher/student,
distillation, evaluation, or artifact-promotion workflow rather than merely read
about that risk.

From the start, a participant can choose among 34 independent roots spanning
agent control, model evasion, context poisoning, model secrets/privacy, agent
memory, adversarial input, training data, extraction, backdoor, and capstone
impact. The modular SDL's current source-realized board contains 134
independently scored challenges: 37 accessible, 58 intermediate, 28 advanced,
and 11 expert. Its 3,015 incremental target minutes provide 6.28 times the
480-minute event window. The same SDL designs a complete 135-challenge,
3,045-minute, 173/173 ATLAS library from which dependency-closed event bundles
will be selected. Neither surface is an expected full clear. Participants
choose branches or progress into advanced variants, and the pack does not
enforce a runtime timer. See
[`docs/challenge-portfolio.md`](docs/challenge-portfolio.md) and
[`docs/atlas-challenge-architecture.md`](docs/atlas-challenge-architecture.md).

Conventional account discovery, credential theft, enterprise reconnaissance,
and network movement are not opening prerequisites. Traditional behavior may
appear only where it is itself part of ATLAS and intrinsic to a selected AI
attack.

The golden range is expected to use GCP where needed, including hosting one or
more open models inside range-controlled infrastructure. Participant exploit
attempts must not target commercial model endpoints, including commercial AI
endpoints offered within GCP. A reduced local profile can support author
iteration, but the live-fire proof must use controlled, range-local model
endpoints for adversarial actions.

## Status

`draft` - build source, the full SDL-authored portfolio design, 134 native
challenge contracts, and one remaining planned hardware design (`kep-m02-g`)
exist. Completed proof campaigns participant-prove all 134 playable contracts.
The retained GCP range currently realizes 28 VM assets, 49 SDL service
bindings, 67 declared service routes/endpoints, 10 subnets, and 28 live service
health gates. The proven challenge split is 37 accessible, 58 intermediate, 28
advanced, and 11 expert. MITRE ATLAS coverage is 172/173 exact rows and
149/150 leaf rows; all 16 tactics are represented. Playtest calibration,
release hardening, final evidence/documentation reconciliation, and the
hardware-attestation decision still block a golden claim. The corrected
44-node portable enterprise/fleet contract and matching GCP projection are not
yet live-materialized or participant-reproved, so they add no golden evidence.
The pack includes its logical world, hidden path, flag projection, GCP build
source, automated rehearsal, participant-run telemetry, module implementations,
and evidence locally. Its 60-item final manual participant path is complete and
its post-manual static and reset gates pass.
The integrated automated functional gate passes after the Module 01
qualification; the earlier Phase-E teardown and its evidence reconciliation
are complete, while the current rehearsal range is retained.

The optional layer flags in `pack.yaml` preserve the draft maturity boundary:

- `flag_layer: true` because ACES-authored participant copy, flag delivery, and
  proof bindings project into the reference CTFd loader. The layer projects
  `gcp_full` only; `local_reduced` produces an empty board. CTFd uses
  participant- and range-bound signed oracle receipts, not challenge-global
  static answers; static validation does not prove live receipt release.
- `reference_triangle: false` because build source, automated Kasm rehearsal,
  reviewed telemetry, the 60-item manual path, post-manual static checks, and
  canonical reset and Phase-E teardown proof now exist, but Modules 08 through
  10 reliability and playtest calibration must close before the full reference triangle. The current
  integrated functional proof passes, with teardown intentionally retained.
- `profile_bundles: false` because no guided, unguided, purple-team,
  benchmark, or demo bundle ships here.

## Build Bar

When this scenario is built, path-critical services must be real software:
inference gateway, guardrail/policy layer, model registry or artifact store,
distillation or fine-tuning workflow, open-model hosting, identity surface,
enterprise applications, participant entry surface, telemetry/proof store, and
reset path. A reduced local profile may help authors iterate, but it cannot
replace the golden build or stand in for a component the participant path needs.

The base experience remains offensive. Defender or audit material may exist
only as clearly labelled delivery bundles that do not reframe the base scenario.

## Map Of This Pack

| Path | Audience | What it is |
|---|---|---|
| [`docs/concepts.md`](docs/concepts.md) | participant-safe | Concepts and vocabulary for the AI-lab scenario. |
| [`docs/attack-path.md`](docs/attack-path.md) | operator/validator | Canonical hidden path and proof boundary. Do not expose to participants. |
| [`docs/atlas-coverage-plan.md`](docs/atlas-coverage-plan.md) | operator/validator | Human-readable experience, progression, flag, tactic, and technique-by-technique ATLAS plan. |
| [`docs/challenge-portfolio.md`](docs/challenge-portfolio.md) | operator/validator | Human rendering and rationale for the SDL-owned 134-challenge current board, eight-hour route model, board-depth benchmark, difficulty/points distribution, dependency DAG, infrastructure, telemetry, and reliability contract. |
| [`docs/documentation-inventory.md`](docs/documentation-inventory.md) | operator/validator | Documentation ownership, authority class, source-of-truth, and update-trigger inventory for documentation reconciliation true-up. |
| [`docs/operator-playtest-guide.md`](docs/operator-playtest-guide.md) | operator/playtester | Practical guide from build or retained-range reuse through participant entry, CTFd projection, reset, evidence, telemetry export, troubleshooting, and Phase E. |
| [`docs/playtester-guide/`](docs/playtester-guide/) | operator/playtester | Structured playtester handoff folder with coordinator quickstart, participant-start boundary, telemetry notes, sanity log, and one SDL-backed walkthrough file per playable challenge. |
| [`docs/atlas-challenge-architecture.md`](docs/atlas-challenge-architecture.md) | operator/validator | Complete SDL-owned 135-challenge full-ATLAS architecture, including 75 expansion contracts (one still planned), nine existing-receipt extensions, implementation allocation, capture, and pragmatic verification. |
| [`docs/topology-reference-triangle.md`](docs/topology-reference-triangle.md) | operator/validator | Topology, participant surface, isolation, and reference-triangle design. |
| [`docs/software-boundary-proof-report.md`](docs/software-boundary-proof-report.md) | operator/validator | Sanitized software-foundation expansion retained-range proof for the 28-node SDL software foundation and the focused live gate on all thirteen new nodes. |
| [`docs/lineage.md`](docs/lineage.md) | operator | Human-readable source adaptation decisions. |
| [`docs/provenance-ledger.yaml`](docs/provenance-ledger.yaml) | operator/catalog | Machine-readable source, licensing, safety, and publication-review ledger. |
| [`docs/golden-readiness-checklist.md`](docs/golden-readiness-checklist.md) | operator | Final review checklist kept unchecked in source. |
| [`docs/aces-only-cutover.md`](docs/aces-only-cutover.md) | operator | Whole-pack ACES authority audit, removed surfaces, consumer map, and reproducible cutover evidence. |
| [`docs/telemetry-rehearsal-report.md`](docs/telemetry-rehearsal-report.md) | operator | Sanitized durable evidence from the passing `gcp_full` participant telemetry rehearsal. |
| [`docs/manual-walkthrough-report.md`](docs/manual-walkthrough-report.md) | operator | Sanitized generation-55 result for the final 60-challenge manual participant path and its remaining closure gates. |
| [`docs/module-01-proof-report.md`](docs/module-01-proof-report.md) | operator | Sanitized generation-55 manual path plus corrected 10-generation/30-trial reliability qualification for the six participant-proven Module 01 challenges. |
| [`docs/module-02-proof-report.md`](docs/module-02-proof-report.md) | operator | Sanitized evidence for the twelve participant-proven playable module-02 paths; the hardware attestation design remains reserved. |
| [`docs/module-03-proof-report.md`](docs/module-03-proof-report.md) | operator | Sanitized manual, reliability, scoped-reset, health, and receipt evidence for the six participant-proven module-03 challenges. |
| [`docs/module-04-proof-report.md`](docs/module-04-proof-report.md) | operator | Sanitized generation-21 reliability and generation-55 manual model-disclosure, classifier-privacy, reset, health, and receipt evidence for the five participant-proven module-04 challenges. |
| [`docs/module-05-proof-report.md`](docs/module-05-proof-report.md) | operator | Sanitized generation-21 reliability and generation-55 manual durable-memory, restart, brokered-effect, reset, health, and receipt evidence for the five participant-proven module-05 challenges. |
| [`docs/module-06-proof-report.md`](docs/module-06-proof-report.md) | operator | Sanitized generation-21 reliability and generation-55 manual adversarial-artifact, model-control, bounded-search, transfer, telemetry, reset, health, and receipt evidence for the six participant-proven module-06 challenges. |
| [`docs/module-07-proof-report.md`](docs/module-07-proof-report.md) | operator | Sanitized generation-55 manual and generation-21 seven-sample training-data lineage, real training, model-artifact, reset-closure, health, and receipt evidence for the six participant-proven module-07 challenges. |
| [`docs/module-08-proof-report.md`](docs/module-08-proof-report.md) | operator | Sanitized participant-equivalent evidence for the eleven participant-proven module-08 challenges. |
| [`docs/module-09-proof-report.md`](docs/module-09-proof-report.md) | operator | Sanitized participant-equivalent evidence for the twelve participant-proven module-09 challenges. |
| [`docs/module-10-proof-report.md`](docs/module-10-proof-report.md) | operator | Sanitized participant-equivalent evidence for the seventeen participant-proven module-10 challenges. |
| [`docs/walkthroughs/module-07-training-poisoning.md`](docs/walkthroughs/module-07-training-poisoning.md) | operator | Manual participant walkthrough contract for the six participant-proven training-poisoning challenges. |
| [`docs/walkthroughs/module-06-full-atlas-expansion.md`](docs/walkthroughs/module-06-full-atlas-expansion.md) | operator | Source-implemented pre-playtest walkthrough contract for the sixteen Module 06 expansion challenges. |
| [`docs/walkthroughs/module-07-full-atlas-expansion.md`](docs/walkthroughs/module-07-full-atlas-expansion.md) | operator | Source-implemented pre-playtest walkthrough contract for the three Module 07 expansion challenges. |
| [`docs/walkthroughs/module-08-model-extraction.md`](docs/walkthroughs/module-08-model-extraction.md) | operator | Manual participant walkthrough contract for the eleven participant-proven model-extraction challenges. |
| [`docs/walkthroughs/module-09-model-backdoor.md`](docs/walkthroughs/module-09-model-backdoor.md) | operator | Manual participant walkthrough contract for the twelve participant-proven model-backdoor and promotion challenges. |
| [`docs/walkthroughs/module-10-ai-capstone.md`](docs/walkthroughs/module-10-ai-capstone.md) | operator | Manual participant walkthrough contract for the seventeen participant-proven deployed-impact and model-theft challenges. |
| [`sdl/keplerops-ai.sdl.yaml`](sdl/keplerops-ai.sdl.yaml) | operator | Composition-only ACES SDL root; imports the complete environment, one green live-activity module, ten module envelopes, 134 realized challenge behaviors, and the one remaining planned design under consideration. |
| [`sdl/modules/`](sdl/modules/) | operator | Sole logical scenario authority: complete environment, participant start state, module semantics, and challenge contracts. |
| [`experiments/ctf-evaluation-task.yaml`](experiments/ctf-evaluation-task.yaml) | operator | RAES experiment-plane mapping from objective receipts to the aggregate CTF score; concrete challenge values remain scenario evaluator content. |
| [`aces_contract.py`](aces_contract.py) | operator | Typed SDL accessors used by runtime services, CTFd, validators, and provider realization; it reads no parallel scenario ledger. |
| [`validation/requirements.txt`](validation/requirements.txt) | operator | Exact PyPI dependency pin: `raes==2.0.0`. |
| [`validation/requirements-ci.txt`](validation/requirements-ci.txt) | operator | Isolated KeplerOps validation and test environment used alongside legacy catalog consumers. |
| [`build/test.sh`](build/test.sh) | operator | Canonical isolated build-contract test entrypoint using the committed validation dependency set. |
| [`build/gcp/packer/nested-host.pkr.hcl`](build/gcp/packer/nested-host.pkr.hcl) | operator | Reproducible immutable GCE image build for the one-host nested golden realization. |
| [`design/README.md`](design/README.md) | operator | Design-document boundary; explicitly rejects parallel scenario projections. |
| [`assets/briefing/`](assets/briefing/) | participant | Mission, allowed-target boundary, four immediate AI attack choices, receipt expectations, and spoiler-safe human/agent play guidance. |
| [`assets/services/`](assets/services/) | operator | Reference realization source for FastAPI roles plus real Keycloak, Gitea/Redmine and OCI, Envoy, production and isolated vulnerable OPA, PostgreSQL, Jupyter, telemetry, OpenSearch, CoreDNS, NGINX discovery surfaces, contained platform services, CPU document/vision models, Stalwart/Roundcube mail, llama.cpp text generation, OpenVINO image generation, the authenticated context API, HTTPS browser/aiortc live camera, LangGraph agent and rootless disposable-worker plane, isolation and edge services, bounded k6, and the tenant-bound Cloud Run Jobs deployment broker; deployed start-state files are ACES content bindings. |
| [`assets/model-artifacts/`](assets/model-artifacts/) | oracle/operator | Revision- and digest-pinned open-model and deployment supply contract. |
| [`assets/workflows/`](assets/workflows/) | operator | Real Airflow distillation, poisoning, and behavioral-extraction workflow that trains deterministic model artifacts, evaluates hidden/clean/fidelity behavior, and records MLflow/MinIO lineage. |
| [`build/`](build/) | operator | Direct ACES-SDL-to-GCP nested realization, immutable outer-host and workload image publishing, health, reset, rebuild, tenant-only cleanup, and static tests. |
| [`tests/`](tests/) | operator | `gcp_full` Kasm participant rehearsal, module-01 through module-03 reliability runners, module-03 through module-10 bounded one-pass runners, canonical path/walkthrough joins, safe report rendering, and unit tests. |
| [`oracle/README.md`](oracle/README.md) | oracle | Private-view boundary; confirms that no parallel oracle specification is stored here. |
| `content.core.proof-policy` | oracle / ACES | Global negative gates and supporting proof events not expressible on individual native evidence requirements. |
| `content.core.portfolio-policy` | oracle / ACES | Event timing, route hypotheses, and delivery bundles; fixed points and allocations are concrete challenge-evaluation content outside SDL objective truth. |
| `content.core.atlas-technique-catalog` | oracle / ACES | Complete pinned MITRE ATLAS 2026.06 catalog; tactic semantics remain native behavior fields. |
| `content.core.research-telemetry-contract` | operator / ACES | Fail-open participant-run event envelope, capture policy, sources, modules, lifecycle, and deterministic export contract. |
| [`telemetry/data-dictionary.md`](telemetry/data-dictionary.md) | operator | Human-readable correlation, field-policy, capture-mode, ordering, and versioning contract. |
| [`docs/aces-sdl.md`](docs/aces-sdl.md) | operator | SDL/start-state authoring boundary and validator entrypoint. |
| [`validation/validate_contract.py`](validation/validate_contract.py) | operator | Static pack, modular-SDL-authority, and documentation contract validator. |
| [`validation/validate_aces_sdl.py`](validation/validate_aces_sdl.py) | operator | Pinned ACES parser/semantic gate with external tactic reconciliation. |
| [`validation/validate_oracle.py`](validation/validate_oracle.py) | operator | Static shared-model and pack-projection oracle validator. |
| [`validation/validate_portfolio.py`](validation/validate_portfolio.py) | operator | Exact count, time, difficulty, scoring, dependency, SDL coverage, and projection reconciliation gate. |

Participant-facing content must not expose hidden path order, proof predicates,
source labels, objective answers, flag values, evaluator prompts, model artifact
hashes used as answers, or next-step hints.
