# Polaris source ownership

Polaris / NORTHSTORM is a Palo Alto Networks scenario pack. The `build/`,
`aws-range/`, `ctfd/`, `sdl/`, `tests/`, `briefing-deck/`, `containers/`,
`content-packages/`, and `design/` surfaces retain authority for their own
domains.

The pack contract surrounds those sources, and the SDL uses released ACES
propositions, assertions, and participant objectives. It does not create a
second topology, convert CTFd material into objective truth, or infer runtime
support from folder presence. Source and publication decisions are
machine-readable in
[`provenance-ledger.yaml`](provenance-ledger.yaml).

| Source | Adaptation decision |
| --- | --- |
| `sdl/` | Topology and attack-path authority expressed as released ACES propositions, assertions, and objectives without a score model. |
| `ctfd/`, `flags/`, and `challenges/` | The 38 implemented rows use stable flag and challenge contracts. CTFd remains an operator adapter; submissions and point values do not establish SDL objective success. |
| `build/`, `aws-range/`, tests, and walkthroughs | The `aws_event` event profile. The event artifact is regenerated from pack-local source; the lifecycle creates a self-contained VPC, and the live rehearsal uses A14 SSH while keeping management transports outside participant actions. |
| Contract metadata and documentation | Descriptive records only; they do not replace runtime behavior or evidence. |

Descriptive pack metadata, compatibility boundaries, provenance
classification, and contract documentation remain separate from runtime
authority. Generated state, live-cloud output,
operator tokens, and generated participant credentials are excluded from
portable-pack and golden-evidence claims. The final reconciliation is recorded
in [`final-reconciliation-report.md`](final-reconciliation-report.md).
