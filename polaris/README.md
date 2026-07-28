# Polaris / NORTHSTORM

Polaris is a live-fire offensive enterprise-to-OT scenario. Participants begin
from the declared Kali attacker surface, discover and compromise the synthetic
Boreas corporate and research environment, and work toward NORTHSTORM bunker
objectives. The participant is the adversary: this pack is not a defensive
investigation or an operator-only demonstration.

The pack is currently **draft**. It preserves the existing scenario sources,
but does not claim a participant-equivalent golden range: the historical AWS
path uses shared development infrastructure, and the existing build, test, and
walkthrough sources are not yet a single canonical reference triangle.

## Contract map

- [Pack metadata](pack.yaml) records identity, maturity, optional-layer status,
  and the real Ground Control requirement `POL-0001`.
- [Compatibility metadata](pack.compatibility.yaml) classifies source
  boundaries without provisioning or observing a range.
- [Provenance ledger](docs/provenance-ledger.yaml) records source adaptation,
  distribution classification, safety attestations, and review state.
- [Concepts](docs/concepts.md) provides participant-safe framing; the
  [attack-path boundary](docs/attack-path.md) is operator/oracle-only.
- [Golden readiness](docs/golden-readiness-checklist.md) defines the proof
  required before `status: golden`.

## Existing authoritative sources

| Surface | Current role |
| --- | --- |
| `build/` | Existing range realization and content build source. |
| `aws-range/` | Operator-only AWS lifecycle, state, health, reset, and redaction tooling. |
| `ctfd/` | Operator-only CTFd reconciliation and validation source. |
| `sdl/` | Released ACES scenario source: participant outcomes are propositions, assertions, and objectives; it remains distinct from the event deploy. |
| `tests/` | Existing smoketest and walkthrough source material. |
| `briefing-deck/`, `containers/`, `content-packages/`, `design/`, `notes/` | Supporting scenario material, subject to the declared boundary and provenance rules. |

Future work may declare a pack-local isolated runtime profile only when it can
name the real build, test, and participant walkthrough references. It must then
prove the full path through a real, range-local Windows domain, industrial
controls, any declared CTFd projection, and every required dependency without using
management-plane shortcuts as participant evidence.

## Objective verdicts and CTFd

The SDL contains no scenario points, score thresholds, metric trees, or flag
submission conditions. It records the five participant-achieved campaign
outcomes as evidence-backed assertions. The existing `ctfd/` material remains
an operator-only migration source, not a declared objective-verdict adapter.
A future CTFd projection must consume an independently determined objective
verdict; a CTFd solve cannot decide that the participant completed the scenario
objective.

## Validation

Run the pack through the released contract and release checks, then the private
catalog gate:

```console
aces-pack-validate --pack scenarios/polaris
aces-pack-release check --pack scenarios/polaris
python3 scripts/ci/scenario_content_ci.py
```
