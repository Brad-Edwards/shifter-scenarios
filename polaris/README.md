# Polaris / NORTHSTORM

Polaris is a live-fire offensive enterprise-to-OT scenario. Participants begin
from the declared Kali attacker surface, discover and compromise the synthetic
Boreas corporate and research environment, and work toward NORTHSTORM bunker
objectives. The participant is the adversary: this pack is not a defensive
investigation or an operator-only demonstration.

The pack is currently **draft**. It carries its scenario source, build tarball,
AWS lifecycle, automated rehearsal, and final manual participant walkthrough
under the Palo Alto Networks pack contract. The reference triangle is shipped
and the degraded `aws_event` binding is supported, but the industrial
authenticity and host-boundary gaps documented below prohibit `built` or
`golden` maturity.

## Contract map

- [Pack metadata](pack.yaml) records identity, maturity, optional-layer status,
  and Palo Alto Networks ownership.
- [Compatibility metadata](pack.compatibility.yaml) classifies source
  boundaries without provisioning or observing a range.
- [Provenance ledger](docs/provenance-ledger.yaml) records source adaptation,
  distribution classification, safety attestations, and review state.
- [Concepts](docs/concepts.md) provides participant-safe framing; the
  [attack-path boundary](docs/attack-path.md) is operator/oracle-only.
- [Private oracle source](oracle/README.md) joins the hidden dependency graph,
  affordances, negative gates, evidence, scoring, and telemetry semantics to
  stable ACES ids without duplicating the SDL.
- [Flag placement](flags/placement.yaml) and
  [participant challenge copy](challenges/challenges.yaml) define the 38
  implemented recovery proofs with stable ids; the
  [CTFd loader](ctfd/README.md) is an operator projection over that join.
- [Topology and assets](docs/topology-and-assets.md) reconciles the canonical
  SDL with the incumbent build/content sources and assigns every real binding
  or gap to a milestone.
- [Reference-triangle design](docs/reference-triangle.md) joins the event
  build, A14 participant surface, automated rehearsal, and walkthroughs.
- [Manual walkthrough evidence](docs/aws-event-manual-walkthrough-report.md)
  records the sanitized participant-equivalent run.
- [GCP Shifter operator runbook](docs/gcp-shifter-operator-runbook.md) records
  the tenant install, event launch, participant acceptance, and teardown path.
- [Automated rehearsal evidence](docs/aws-event-rehearsal-report.md) records
  the post-fix 38-recovery, reset, and teardown run.
- [Final reconciliation evidence](docs/final-reconciliation-report.md) joins
  pack status, release boundaries, both live reports, and the fresh read-only
  zero-resource inventory.
- [Asset-source boundary](assets/README.md) records the single-owner source
  layout for briefing, content-package, container, and build material.
- [Golden readiness](docs/golden-readiness-checklist.md) defines the proof
  required before `status: golden`.
- [Delivery profiles](profiles/README.md) package the same scenario for guided,
  unguided, purple-team, benchmark, and demo audiences without changing runtime
  state or proof.

## Authoritative sources

| Surface | Current role |
| --- | --- |
| `aws-range/` | Authoritative event-proven AWS provisioning, A14 access, health, reset, and teardown source. |
| `build/build-v1.tar.gz` | Event-derived build artifact, regenerated from tracked pack source after pinning the supported Kali release image. |
| `build/` | Component and content source for the compose range. |
| `flags/` | Operator/oracle-only stable flag values and runtime recovery locations. |
| `challenges/` | Participant-facing challenge questions, difficulty, points, and hints. |
| `ctfd/` | Operator-only reference projection keyed by stable flag ids. |
| `sdl/` | Released ACES scenario source: participant outcomes are propositions, assertions, and objectives; it remains distinct from the event deploy. |
| `oracle/` | Private ACES-derived hidden-path and affordance projections; never participant content or objective authority. |
| `validation/` | Static, read-only ACES/oracle cross-reference and participant-leak gate. |
| `assets/` | Planned conventional briefing/content/service boundary. Current payload owners remain authoritative until any reorganization is completed atomically. |
| `tests/` | Automated rehearsal, smoketest, reset, and contract source. |
| `docs/walkthroughs/` | Human participant walkthroughs. |
| `briefing-deck/`, `containers/`, `content-packages/` | Supporting shipped scenario material, subject to the declared boundary and provenance rules. |
| `design/` | Internal design material; non-authoritative and excluded from release boundaries. |

The compatibility manifest leaves `local_degraded` planned as an unproven
fast-feedback binding and marks `aws_event` as the supported degraded runtime.
`aws_event` preserves the proven compact event topology in a self-contained AWS
VPC with a real range-local Windows domain, key-authenticated A14 access,
automatic blackout splice, and clean reset. It is intentionally an event
profile rather than a golden profile: its hand-authored fictional industrial
services are not a vendor-supported hardware twin, and the compose host does
not realize every SDL host as separate infrastructure. Those gaps prohibit
maturity above `draft`.

## Objective verdicts and CTFd

The SDL contains no scenario points, score thresholds, metric trees, or flag
submission conditions. It records the five participant-achieved campaign
outcomes as evidence-backed assertions. The canonical flag inventory binds
each recovery proof to one existing affordance/path step; CTFd projects its
participant copy and granular points with adapter-local categories. A CTFd
solve cannot decide that the participant completed an ACES objective.

## Validation

Run the pack through the released contract and release checks, then its
pack-local validators:

```console
aces-pack-validate --pack polaris
aces-pack-release check --pack polaris
python3 polaris/validation/validate_oracle.py validate
python3 -m unittest discover -s polaris/ctfd/tests
python3 polaris/profiles/validate_profiles.py validate
python3 -m unittest discover -s polaris/profiles/tests
python3 -m unittest polaris.tests.test_aws_range_rehearsal
```
