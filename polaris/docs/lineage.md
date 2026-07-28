# Polaris lineage

Polaris / NORTHSTORM is a source-preserving migration of the existing scenario
tree. The current `build/`, `aws-range/`, `ctfd/`, `sdl/`, `tests/`,
`briefing-deck/`, `containers/`, `content-packages/`, `design/`, and `notes/`
surfaces remain in place and retain their established authority for their own
domains.

This issue adds the pack contract around those sources and migrates the existing
SDL into the released ACES model. The migration replaces the removed legacy
metric/evaluation/TLO/goal hierarchy with evidence-backed propositions,
assertions, and participant objectives. It does not create a second topology
or a local validator, convert CTFd material into a canonical flag/challenge
layer, turn historical lifecycle reports into proof, or infer a supported
runtime profile from existing folders. The source adaptation and publication
decisions are machine-readable in
[`provenance-ledger.yaml`](provenance-ledger.yaml).

| Source | Adaptation decision |
| --- | --- |
| Existing `sdl/` | Used as the topology and attack-path authority; legacy outcome semantics were changed into released ACES proposition/assertion/objective semantics without retaining a score model. |
| Existing `ctfd/` and `build/ctfd-*` | Retained as operator-only CTFd source, not a declared objective-verdict adapter. CTFd submissions and point values do not establish SDL objective success. |
| Existing `build/`, `aws-range/`, tests, and walkthroughs | Retained as migration source, but excluded from supported-profile and golden-proof claims until they are reconciled to one isolated participant-equivalent reference. |
| New contract metadata and documentation | Locally designed, descriptive records only; they do not replace runtime behavior or historic evidence. |

Locally designed material in this migration is limited to descriptive pack
metadata, compatibility boundaries, provenance classification, and the new
contract documentation. Historical generated state, live-cloud output,
operator tokens, and generated participant credentials are excluded from
portable-pack and golden-evidence claims.
