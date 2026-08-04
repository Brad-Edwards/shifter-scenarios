# Campaign V2 Design Progress

Last updated: 2026-08-02

## Objective

Produce an implementation-ready design for a 134-operation, participant-led
Cinder Typhoon campaign against KeplerOps AI Systems. The campaign must feel
like attacking a real AI lab, use real OSS systems and real security effects,
cover every ATLAS 2026.06 row except `AML.T0010.000 Hardware`, and avoid the
old design's guessy, challenge-shaped interactions.

The design review and corrective source implementation are complete. Integrated
materialization is underway on the dedicated GCP campaign-v2 template under
issue #38. Image baking remains deferred until the template passes its live
participant-path gates.

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

1. Complete the corrective source pass that removes proof-controller behavior
   and binds every software operation to causal native enterprise state.
2. Reconcile cross-module identity, model, artifact, release, and business-effect
   handoffs, then run the combined Compose and Shifter content contracts.
3. Materialize the integrated source on the template and perform the manual
   participant-equivalent walkthrough before baking.

## Execution Tracker

This table is the live handoff record for parent and delegated work. A module is
not template-ready until its source correction and bounded blocker review are
both complete. Template status records materialization, not source intent.

Participant walkthrough completion is tracked authoritatively in the GitHub
issues: the per-module checklists (#40-#49), the full-template re-proof
checklist (#58), and the hotfix coordination thread (#50). No module-level
walkthrough claim may be inferred from the source or template columns below.

| Lane | Owner | Dependencies | Source | Blocker review | Template | Participant proof |
| --- | --- | --- | --- | --- | --- | --- |
| M01/M02 intake and review | parent + Mencius | shared WorkHub, Forgejo, Nextcloud and devpi | corrected; 7 M02 regressions pass | complete; no blockers in bounded final review | materialized | pending |
| M03/M04 discovery and product access | parent | enterprise identity and business services | corrected | complete | materialized | pending |
| M05 assistant and agent workflows | Dirac + Boyle | active assistant identity and M01/M02 artifacts | corrected; nonce/proof, reset and contract regressions pass | complete; blockers corrected | 17 start states materialized; participant-generated evidence pending | pending |
| M06 Cinder infrastructure | parent + Halley | Cinder and shared Vertex edge | corrected | complete | 21 software operations materialized; hardware proof excluded | pending |
| M07 integrity workflows | parent | clean training reference | corrected; 11 contract regressions pass | complete | materialized | pending |
| M08 vision and physical boundary | parent | M06 workbench; physical place for two operations | corrected; 6 regressions pass | complete | 10 software operations materialized; physical calibration excluded | pending |
| M09/M10 release and production | Pasteur + Herschel | M05/M07 artifacts and clean release | corrected; focused static contracts and digest regression pass | complete; startup blockers corrected | M09 and all 17 M10 start states materialized; M10 source, workers and Airflow healthy | pending |
| Clean release and shared Vertex | parent | M07, k3s, attached GCP identity | corrected; 12 regressions pass | complete | runtime and immutable training lineage gates pass | pending |
| Global readiness and workstation | parent | all software modules | corrected; static gates pass | complete | pending | pending |
| Shifter content export | parent | all 134 operation records | 134-operation bundle accepted by Shifter parser | complete | pending | pending |

Current mechanical baseline: 134 operations, 134 unique flags, 31,650 points,
40 Accessible, 48 Intermediate, 33 Advanced and 13 Expert operations; 172 of
173 ATLAS rows covered with only hardware poisoning excluded; 41 declared
campaign network flows; 142 combined Compose services across 13 networks.

## Final Readiness And Integration Gates

- **Software deployment:** the default campaign apply deploys the 132 software
  operations and may write only `keplerops-v2-software.ready`. It must not
  require an external physical bench.
- **Default-deny campaign flows:** source now carries a separate campaign flow
  manifest, statically requires every networked campaign container to be
  represented, and reconverges the enforced policy before software readiness.
  The combined Compose graph and live allow/deny probes remain required before
  the integrated candidate is accepted.
- **Production entrypoints:** all m10 apply, validate, and reset entrypoints now
  carry executable modes. Combined static dispatch and container execution
  remain required before acceptance.
- **All-challenges readiness:** `--all-challenges` cannot write
  `keplerops-v2-campaign.ready` until the same apply proves the operator place
  evidence gate and participant reservation/acquisition/release gate against an
  authentic labgrid bench.
- **Physical availability:** `kep-m08-i` and `kep-m06-m` remain unavailable and
  unclaimed until the bill of materials and topology in
  `hardware-materialization.md` are supplied. There is no simulation, upload,
  prerecorded-media, or software fallback.

## Clean Enterprise Build Status

Eleven of the fourteen acceptance gates in `enterprise-architecture.md` are fully
proven on the dedicated GCP template:

- redundant AD DNS, LDAP, Kerberos, and replication;
- joined-workstation domain login and Kerberos tickets;
- real threaded internal/external mail with attachments;
- scheduled partner intake through Zammad, Airflow, Tika, Qdrant, the Orion
  model, WorkHub, and Nextcloud with byte-level source preservation;
- Forgejo source and Actions publication into devpi, Verdaccio, and Harbor,
  correlated by exact source revision and OCI digest; and
- Label Studio annotation export into an immutable lakeFS/DVC snapshot, a
  scheduled real PyTorch/Transformers/PEFT training run, and complete MLflow
  lineage with downloaded-weight digest verification;
- visible evaluation, OPA policy, cosign evidence, GitOps release state, KServe
  deployment, and live runtime identity joined by immutable digests;
- all eight bounded Orion business decisions producing their native clean
  effects in Unleash, Odoo, Ghost, Mautic/Stalwart, Zammad/Stalwart,
  RabbitMQ/Qdrant, lakeFS, Redmine, and Nextcloud, with idempotency,
  cross-range rejection, and compensation proven;
- one ordinary Orion inference correlated across Jaeger, Prometheus,
  Alertmanager, OpenSearch, and OpenCost; and
- independent Cinder workstation, model, mail, Forgejo, MinIO, Jupyter, and
  request-relay surfaces; and
- complete replacement of both disposable domain-member guests with new VM
  UUIDs and machine IDs while preserving the exact directory, threaded mail,
  intake, source/registry, training, GitOps, release, and runtime state
  manifest.

The source-publication path is checked by
`template/baseline/source-ci-registries.sh`; it uses only product APIs and
requires the latest main-branch source revision, successful Forgejo workflow,
both package versions, and Harbor revision/tag metadata to agree.
The data/training path is checked by
`template/baseline/data-training-lineage.sh`; it independently recomputes the
Label Studio export hash and requires the latest scheduled Airflow run, lakeFS
commit metadata, DVC descriptor, MLflow tags and metrics, and downloaded LoRA
adapter digest to agree.
Release/runtime continuity is checked by
`template/baseline/release-runtime-continuity.sh`; bounded business actions are
checked by `template/baseline/business-workflows.sh`; and normal operational
correlation is checked by `template/baseline/observability-correlation.sh`.
Disposable-worker replacement and durable-state preservation are checked by
`template/baseline/worker-replacement.sh`.

The remaining clean-enterprise gates are complete application role federation,
fresh-Kali public-surface verification, and the real labgrid place boundary.

## Publication

- Branch: `keplerops-campaign-v2-design`
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
