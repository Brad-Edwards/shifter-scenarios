# Polaris final evidence and release reconciliation

- schema: `polaris.final-reconciliation-report/v1`
- pack_version: `0.5.0`
- historical_teardown_evidence: `PASS`
- final_maturity: `draft`
- reference_triangle: `shipped`
- aws_event_status: `supported`
- local_degraded_status: `planned`
- final_verdict: `PASS`

This report records the final pack-local reconciliation without changing what
the live evidence proved. Polaris ships an event-proven reference triangle:
pack-local build source and artifact, participant-path tests, matching manual
walkthroughs, reset and teardown implementation, and sanitized automated and
manual reports. The supported binding is `aws_event`; it remains explicitly
degraded and does not earn `built` or `golden` maturity.

## Evidence join

| Surface | Authority | Reconciled result |
| --- | --- | --- |
| Build and participant start | `aws-range/`, `build/`, and `build/build-v1.tar.gz` | The isolated AWS event binding creates A14, the compact event topology, and a real range-local Windows domain controller. |
| Automated participant proof | `tests/aws_event_rehearsal.py`, `tests/aws_event_participant.py`, and `docs/aws-event-rehearsal-report.md` | All 38 recoveries, five objective stages, negative gates, reset, and teardown passed. |
| Manual participant proof | `docs/walkthroughs/` and `docs/aws-event-manual-walkthrough-report.md` | The full event path passed by hand from unprivileged A14; both corrected walkthrough steps were rerun before the post-fix automated rehearsal. |
| Objective and evidence authority | `sdl/polaris-operation-northstorm.sdl.yaml`, `aces_contract.py`, and `oracle/` | Stable ACES objective ids, evidence requirements, affordances, failure states, and participant/export boundaries remain joined without a second semantic model. |
| Flag and scoring adapter | `flags/`, `challenges/`, `ctfd/`, and `profiles/agent-benchmark/operator/scoring-hooks.yaml` | The 38 stable recoveries remain an adapter projection; CTFd solves and profile points do not decide ACES objective success. |
| Delivery profiles | `profiles/bundles.yaml` and `profiles/validate_profiles.py` | Five content-only bundles remain supported and separate from runtime profiles. |
| Distribution and release | `pack.compatibility.yaml` and `docs/provenance-ledger.yaml` | Participant, operator, private/oracle, commercial, and internal-only material have explicit non-overlapping authority. |

The automated report's `pack_version` equals the manual report's
`post-fix_pack_version`. That is the path-for-path evidence join; neither report
is treated as golden proof.

## Teardown verification

The automated and manual reports each record passing Terraform
destroy, empty Terraform state, and an independent tag-scoped inventory after
their respective runs.

The portable source package makes no claim about a currently configured cloud
account. Operators must run the pack's read-only inventory and teardown checks
in the account used for each future rehearsal and retain that run-specific
evidence separately.

## Maturity decision

`pack.yaml.status` and the compatibility projection remain `draft`. The
participant path passed, but the event runtime's HMI, Modbus controllers, and
stateful industrial interlocks are authored fictional simulations rather than
vendor-supported twins, and the compact Compose host does not realize every SDL
host boundary as separate infrastructure. Current doctrine forbids treating
that gap as `built` or `golden`.

`contents.reference_triangle` is nevertheless `true`: it records the shipped
build/test/walkthrough layer, not maturity. `aws_event` is `supported` because
consumers can rely on the exact degraded binding that was rehearsed.
`local_degraded` remains `planned` because no separate clean local participant
proof was performed.

## Compatibility and publication boundaries

The ACES contract prohibits top-level compatibility-manifest scoring,
oracle, telemetry, and lifecycle extensions. Polaris therefore indexes the
existing authorities through allowed asset, operator-surface, runtime-profile,
and typed validation-gate fields. The ACES anti-extension gate remains the
enforcement authority.

Generated fleet state and health/status snapshots are not release
content. Planned conventional `assets/` placeholders are not staged as shipped
payload, the internal `design/` root is not a commercial export, and
the event lifecycle boundary lists only the source needed by the supported
binding. The corrected incumbent briefing deck is participant-visible and is
therefore covered by the staged participant leak scan.

Publication review remains `pending` in the provenance ledger. Passing static,
release, and leak gates proves contract and content-safety invariants; it does
not grant licensing, attribution, sensitive-data, or offensive-tooling
publication approval.

## Final validation contract

The release projection names the following blocking evidence:

- ACES pack validation and release checks;
- private oracle, flag/CTFd, profile, topology, and AWS rehearsal tests;
- participant-release leak scanning;
- the automated rehearsal report;
- the manual participant walkthrough report; and
- this final reconciliation plus its contract tests.

The unchecked golden-readiness source checklist remains reusable. This report,
the automated report, and the manual report are the run-specific evidence
records.
