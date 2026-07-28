# ACES-Only Cutover

This record documents the whole-pack stop-the-line audit and ACES authority
cutover. The canonical scenario description is the modular root
[`../sdl/keplerops-ai.sdl.yaml`](../sdl/keplerops-ai.sdl.yaml), parsed with the
published and exact `raes==2.0.0` package. No committed projection below is
allowed to redefine scenario topology, software inventory, start state,
challenge design, scoring, flag delivery, objectives, proof, telemetry, or
implementation state.

## Canonical Surface

The expanded ACES scenario declares:

- 24 nodes and 24 infrastructure bindings: 9 networks and 15 VM assets;
- 20 software features, including five explicitly bound sidecar/host
  dependencies and immutable image/build provenance;
- 31 content bindings, including the participant, identity, proxy, telemetry,
  workflow, model, and synthetic-credential start-state files;
- 70 behavior specifications: 10 module envelopes and 60 challenge behaviors;
- 60 native conditions, evidence requirements, and objectives in the original
  cutover; the current RAES 2.0.0 model has 134 conditions,
  propositions, postcondition assertions, evidence requirements, and
  objectives, with scoring in the experiment/evaluator plane; and
- governed challenge/module extensions plus ACES content datasets only where
  RAES 2.0.0 has no native field for the required CTF, proof, research, or
  ATLAS semantics.

The typed [`../aces_contract.py`](../aces_contract.py) accessor produces bounded
in-memory views for runtime services, CTFd, rehearsal, and validators. The GCP
renderer produces an owner-only, ephemeral JSON realization. Neither is a
second authority.

## Removed Alternate Authorities

The cutover deletes and permanently guards against these redundant semantic
files:

- `assets/affordances.yaml`
- `assets/oracle/baseline.yaml`
- `build/gcp/runtime-images.yaml`
- `challenges/challenges.yaml`
- `design/implementation-tracking.yaml`
- `flags/placement.yaml`
- `oracle/atlas-technique-projection.yaml`
- `oracle/objectives.yaml`
- `oracle/scoring.yaml`
- `oracle/telemetry.yaml`
- `telemetry/research-telemetry.yaml`

The runtime image plan is now derived from native ACES feature sources, build
provenance, and dependencies. The challenge board, flags, proof API, research
capture contract, portfolio checks, implementation tracking, and ATLAS
reconciliation are derived from the expanded SDL.

## Deliberate Non-SDL Files

Remaining YAML or JSON files do not act as scenario-description dialects:

- `pack.yaml`, `pack.compatibility.yaml`, and `docs/provenance-ledger.yaml` are
  required catalog, visibility, licensing, and publication metadata;
- files below `assets/` are the actual scenario content or service
  configuration referenced by ACES content or feature build declarations;
- Terraform, Dockerfiles, bootstrap scripts, and lifecycle code are the
  reference realization of the SDL;
- `image-lock.schema.json` validates a generated registry readback artifact,
  not authored scenario state; and
- walkthroughs, proof reports, and other docs are human guidance or evidence,
  never machine authority.

## Enforcement and Evidence

Both `validation/validate_aces_sdl.py` and
`validation/validate_contract.py` reject reintroduction of the removed
semantic paths. Scenario-specific validators consume the ACES model or
generated/live artifacts. The reproducible cutover gate is:

```sh
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python keplerops-ai/validation/validate_aces_sdl.py validate
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python keplerops-ai/validation/validate_contract.py validate
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python keplerops-ai/validation/validate_oracle.py validate
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python keplerops-ai/validation/validate_portfolio.py validate
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python keplerops-ai/build/gcp/validate_build.py
```

The validation, build/runtime, CTFd, and rehearsal mutation suites exercise the
same boundary. Repository-wide content CI is the final integration gate.

On 2026-07-15 the cutover source passed:

- all five KeplerOps static validators: ACES, pack contract, oracle,
  portfolio, and GCP realization;
- 47 validation mutation tests;
- 95 build/runtime tests, with one existing environment-dependent skip;
- 20 CTFd projection/reconciliation tests;
- 58 rehearsal and reliability contract tests; and
- the complete repository `scenario_content_ci.py` gate under the CI-equivalent
  `raes==2.0.0` environment, including every scenario validator/test suite,
  visibility scans, manifests, provenance, and golden-readiness checks.

## Live-Range Boundary

Module-05 image publication was stopped before deployment or service recycling
when this audit began. This cutover makes no golden claim and does not replace a
participant walkthrough. Live module proof resumes only after this source
cutover passes CI; the retained rehearsal tenant may then be updated from the
SDL-derived realization.
