# Polaris asset-source boundary

This directory defines the planned conventional source boundary for authored
Polaris content. It is a design boundary; current payloads remain under their
single authoritative owners.

Each payload has one authoritative owner in `briefing-deck/`,
`content-packages/`, `containers/`, or component-specific source under
`build/`. Copying those payloads here would create two editable owners, so any
reorganization must move one source at a time and update every SDL, build,
test, walkthrough, compatibility, and provenance reference in the same slice.

| Planned root | Content class | Current owner | Reorganization acceptance |
| --- | --- | --- | --- |
| `briefing/` | Participant-safe mission and access material | `briefing-deck/` | The participant export contains objectives and access instructions but no credentials, hidden order, proof predicates, answers, or management commands. |
| `content/` | Commercial-only authored source for synthetic artifacts planted in-world | `content-packages/polaris/` plus component-owned build content | Every SDL `content.*.source` resolves to one package, the build consumes that package, reset restores it without a duplicate source, and participant exports contain only the resulting in-world placement rather than the authored source tree. |
| `services/` | Bespoke service and container source | `containers/` and component source under `build/` | Each SDL node source resolves to one implementation; the current build consumes it without a second editable copy. |

`docs/topology-and-assets.md` is the operator inventory. It names the current
source binding and the required full-profile realization for every component.
`docs/reference-triangle.md` defines how the source is consumed by the
build, tests, and participant walkthrough.

The planned roots are classified in `pack.compatibility.yaml` and
`docs/provenance-ledger.yaml`. They remain `status: planned`; the existing
source rows remain `shipped` until a complete one-owner reorganization lands.
