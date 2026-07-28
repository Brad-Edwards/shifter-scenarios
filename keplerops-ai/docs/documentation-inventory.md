# KeplerOps documentation inventory

This inventory is the documentation reconciliation tracking surface for documentation ownership. It
does not create a second scenario specification. The modular ACES SDL remains
the sole logical authority for resources, software, identities, routes,
content, challenge contracts, event bundles, and research telemetry contracts.

## Authority classes

| Class | Meaning | Update trigger |
|---|---|---|
| ACES authority | Direct ACES SDL or a typed accessor/validator that reads the SDL. | Any SDL, `aces_contract.py`, or pinned `raes` change. |
| Projection | Operational view derived from the SDL or runtime state. | Any source contract or projection code change. |
| Operator guide | Human procedure for build, reset, export, CTFd, evidence, or teardown. | Any command, path, profile, runtime, or validation workflow change. |
| Participant-facing | Material safe to show participants. | Any start-state, briefing, allowed-target, or hint/progression change. |
| Evidence report | Sanitized proof of a specific build, rehearsal, walkthrough, or implementation slice. | New validation run, corrected status, or superseding evidence. |
| Internal design | Rationale and planning material; not participant-facing and not configuration. | Design decision, work split, or acceptance-bar change. |

## Core authority and projections

| Artifact | Audience | Class | Source of truth | Update trigger |
|---|---|---|---|---|
| [`sdl/keplerops-ai.sdl.yaml`](../sdl/keplerops-ai.sdl.yaml) | operator | ACES authority | SDL imports under `sdl/modules/` | Any scenario topology, service, content, challenge, bundle, telemetry, or ATLAS allocation change. |
| [`sdl/modules/`](../sdl/modules/) | operator | ACES authority | Module/environment SDL files | Any module envelope, software surface, evidence, or challenge-contract change. |
| [`aces_contract.py`](../aces_contract.py) | operator | ACES authority | Parsed modular SDL | Any consumer needing a new SDL-derived projection. |
| [`experiments/ctf-evaluation-task.yaml`](../experiments/ctf-evaluation-task.yaml) | operator | RAES experiment authority | SDL objective receipts and concrete KeplerOps evaluator values | Objective evidence, experiment metric, aggregate score, or evaluator binding change. |
| [`validation/validate_aces_sdl.py`](../validation/validate_aces_sdl.py) | operator | ACES authority | `raes==2.0.0` plus pack validators | ACES parser pin or governed tactic/behavior semantics change. |
| [`assets/content/company-state/`](../assets/content/company-state/) | operator / service adapter | ACES-bound scenario content | Synthetic KeplerOps corpus and exact object bytes | Company identity, endpoint, business-object, represented-time, or source-digest change. |
| [`validation/validate_company_state.py`](../validation/validate_company_state.py) | operator | Projection | Concrete company-state corpus and source bytes | Company object schema, reference, timeline, safety, or digest rule change. |
| [`validation/requirements-ci.txt`](../validation/requirements-ci.txt) | operator | Projection | Isolated KeplerOps validation and test dependencies | RAES pin or pack test dependency change. |
| [`build/test.sh`](../build/test.sh) | operator | Projection | Canonical isolated build-contract validation command | Build-test scope or dependency entrypoint change. |
| [`build/gcp/packer/nested-host.pkr.hcl`](../build/gcp/packer/nested-host.pkr.hcl) | operator | Provider realization | Pinned Ubuntu source image and nested-host package contract | Outer-host prerequisite or immutable image-build change. |
| [`build/gcp/build-nested-host-image.sh`](../build/gcp/build-nested-host-image.sh) | operator | Lifecycle entry point | Authenticated, bounded Packer image build | Builder credential, network, tag, or immutable image lifecycle changes. |
| [`validation/validate_contract.py`](../validation/validate_contract.py) | operator | Projection | Pack files and SDL-derived contracts | Pack contract, documentation contract, or ACES-only assertion change. |
| [`validation/validate_oracle.py`](../validation/validate_oracle.py) | operator | Projection | SDL proof, CTFd, telemetry, research, ATLAS contracts | Oracle, receipt, telemetry, or challenge-projection change. |
| [`validation/validate_portfolio.py`](../validation/validate_portfolio.py) | operator | Projection | SDL portfolio and challenge extensions | Challenge count, points, timing, difficulty, dependency, or bundle change. |

## Operator guides

| Artifact | Audience | Class | Source of truth | Update trigger |
|---|---|---|---|---|
| [`README.md`](../README.md) | operator / catalog | Operator guide | SDL plus current validated pack status | Any material status, count, command, or map-of-pack change. |
| [`build/README.md`](../build/README.md) | operator | Operator guide | Build scripts, Terraform, runtime export/readback tooling | Build, reset, health, image, telemetry, export, or readback workflow change. |
| [`ctfd/README.md`](../ctfd/README.md) | operator | Operator guide | CTFd sync tool and plugin behavior | Board projection, event bundle, oracle flag, or CTFd telemetry change. |
| [`docs/operator-playtest-guide.md`](operator-playtest-guide.md) | operator / playtester | Operator guide | SDL, build lifecycle scripts, CTFd projection, telemetry contract, and proof/reset reports | Build, retained-range, participant-entry, CTFd, reset, telemetry, evidence, troubleshooting, or Phase-E workflow change. |
| [`docs/playtester-guide/`](playtester-guide/) | operator / playtester | Projection / operator guide | SDL challenge extensions plus build, telemetry, and proof workflow docs | Playtester handoff, challenge contract, walkthrough, proof route, telemetry, sanity, or participant-start workflow change. |
| [`docs/playtester-guide/full-manual-participant-equivalent-runbook.md`](playtester-guide/full-manual-participant-equivalent-runbook.md) | operator / playtester | Operator guide | Build doctrine, playtester guide, reset workflow, and retained-range lessons learned | Manual participant-equivalent verification workflow, reset policy, defect-handling policy, retained-range status, or final clean-run acceptance change. |
| [`docs/golden-readiness-checklist.md`](golden-readiness-checklist.md) | operator | Operator guide | Build doctrine and final walkthrough policy | Golden claim, final manual walkthrough, teardown, or retained-range policy change. |
| [`docs/aces-sdl.md`](aces-sdl.md) | operator | Operator guide | ACES parser, SDL layout, and validator entrypoints | ACES authoring convention, source-of-truth, or parser pin change. |
| [`docs/company-state.md`](company-state.md) | operator / backend implementer | Operator guide | SDL content placements, company corpus, and golden adapters | Initial-state semantics, corpus, materializer, reset, readback, or portability status change. |
| [`telemetry/data-dictionary.md`](../telemetry/data-dictionary.md) | operator / researcher | Operator guide | `content.core.research-telemetry-contract` | Telemetry field, source, storage, export, readback, or capture-mode change. |
| [`oracle/README.md`](../oracle/README.md) | oracle / operator | Operator guide | SDL proof-policy and receipt implementation | Oracle boundary, receipt, evidence, or private-view change. |

## Participant-facing material

| Artifact | Audience | Class | Source of truth | Update trigger |
|---|---|---|---|---|
| [`assets/briefing/mission.md`](../assets/briefing/mission.md) | participant | Participant-facing | SDL participant start state and allowed target boundary | Start-state, allowed-target, mission framing, or spoiler-safety change. |
| [`docs/concepts.md`](concepts.md) | participant-safe | Participant-facing | Scenario concepts and non-spoiler vocabulary | Terminology, module framing, or participant-safe concept change. |

## Portfolio, architecture, and design

| Artifact | Audience | Class | Source of truth | Update trigger |
|---|---|---|---|---|
| [`docs/challenge-portfolio.md`](challenge-portfolio.md) | operator / validator | Internal design | SDL challenge extensions and portfolio policy | Challenge count, timing, dependency, difficulty, scoring, route, or bundle change. |
| [`docs/atlas-challenge-architecture.md`](atlas-challenge-architecture.md) | operator / validator | Internal design | SDL ATLAS catalog and challenge-design dataset | ATLAS coverage, planned/realized status, or module allocation change. |
| [`docs/atlas-coverage-plan.md`](atlas-coverage-plan.md) | operator / validator | Internal design | SDL ATLAS catalog and portfolio policy | ATLAS technique coverage, tactic semantics, or gap/contingency change. |
| [`docs/topology-reference-triangle.md`](topology-reference-triangle.md) | operator / validator | Internal design | SDL environment module, provider realization, and proof reports | Node, route, service, participant surface, reference-triangle, retained-range, or topology proof change. |
| [`docs/fleet-capacity-model.md`](fleet-capacity-model.md) | operator / validator | Projection | `build/gcp/fleet-capacity-profile.json` and `build/gcp/fleet_capacity.py` | Total/active/busy range assumptions, deployment cells, packed host shape, shared-service sizing, provider quota, or measurement status change. |
| [`docs/attack-path.md`](attack-path.md) | operator / validator | Internal design | SDL proof policy and hidden path design | Hidden path, proof boundary, negative gate, or participant route change. |
| [`design/README.md`](../design/README.md) | operator | Internal design | ACES-only pack design boundary | Any introduction/removal of design projections or source-of-truth language. |
| [`docs/aces-only-cutover.md`](aces-only-cutover.md) | operator | Evidence report | ACES-only cutover proof | Any resurrected non-ACES projection, removed surface, or consumer-map change. |

## Evidence and walkthrough reports

| Artifact | Audience | Class | Source of truth | Update trigger |
|---|---|---|---|---|
| [`docs/software-boundary-proof-report.md`](software-boundary-proof-report.md) | operator / validator | Evidence report | Software-foundation expansion retained-range proof | Software surface, node inventory, focused live gate, or retained-range status change. |
| [`docs/telemetry-rehearsal-report.md`](telemetry-rehearsal-report.md) | operator / researcher | Evidence report | Telemetry rehearsal evidence | Telemetry profile, export/readback, performance, or isolation proof change. |
| [`docs/manual-walkthrough-report.md`](manual-walkthrough-report.md) | operator | Evidence report | Manual participant walkthrough evidence | Manual route, proof level, retained range, or closure-gate change. |
| [`docs/module-01-proof-report.md`](module-01-proof-report.md) through [`docs/module-10-proof-report.md`](module-10-proof-report.md) | operator | Evidence report | Module-specific proof artifacts | Module challenge status, live proof, reset behavior, or reliability evidence change. |
| [`docs/walkthroughs/`](walkthroughs/) | operator | Evidence report | Module walkthrough contracts and proof notes | Module path, command, endpoint, evidence predicate, or validation standard change. |

## Provenance and compatibility

| Artifact | Audience | Class | Source of truth | Update trigger |
|---|---|---|---|---|
| [`docs/lineage.md`](lineage.md) | operator | Internal design | Source adaptation decisions | Source, model, dataset, workflow, or licensing/lineage change. |
| [`docs/provenance-ledger.yaml`](provenance-ledger.yaml) | operator / catalog | Projection | Pack source and publication review metadata | New asset, external source, license, provenance, or publication-review change. |
| [`pack.compatibility.yaml`](../pack.compatibility.yaml) | catalog / operator | Projection | Pack export and compatibility contract | Export boundary, compatibility claim, scenario artifact class, or validation evidence change. |

## Current known reconciliation items

- `kep-m02-g` remains under consideration. Do not claim exact implemented
  hardware ATLAS coverage until that decision is resolved.
- research telemetry still owns broader research source coverage for PTY/process,
  browser/Kasm, notebooks, files/artifacts, workflow state, and richer CTFd
  lifecycle capture.
- CTFd flow still owns live CTFd correlation proof, dependency unlock/block events,
  and richer reset/stale-receipt joins.
- Final golden status still requires the documented participant-equivalent
  manual walkthrough and final evidence/teardown reconciliation.
