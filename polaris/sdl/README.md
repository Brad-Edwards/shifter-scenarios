# Polaris SDL

This directory is the released ACES source for Polaris / NORTHSTORM.

- `polaris-operation-northstorm.sdl.yaml` declares the full Boreas and
  NORTHSTORM topology, identity, content, participant actions, and five
  campaign objectives.
- `polaris-demo-minimal.sdl.yaml` is only a parser and integration fixture. It
  is not a runtime profile, a participant walkthrough, or an acceptable
  substitute for the full scenario.

## Outcome model

Polaris expresses participant completion through evidence requirements,
propositions, assertions, and `objectives.*.success.assertions`. The obsolete
metric, evaluation, TLO, and goal hierarchy has been removed. Neither CTFd
submissions nor CTFd point values decide objective success. The existing CTFd
source is not a declared objective-verdict adapter; a future projection must
consume independently determined verdicts.

The NORTHSTORM campaign objectives are:

1. establish the Boreas target picture;
2. compromise the front office;
3. extract the Leviathan program;
4. trigger the SCADA blackout and range-local splice path; and
5. seize the autonomous platform.

The live realization is defined by `../build/` and `../aws-range/`. The pack
remains `draft`; source presence alone does not establish a golden proof.

The logical network bindings are reconciled to the active Compose source by
`../tests/test_topology_design.py`. Compose services carry inert
`polaris.asset` labels that join each service to one SDL node; the test rejects
unknown, missing, duplicate, or address-drifted bindings. A2 is the one
expected adjacent VM and remains a range-local real Windows Server DC.

## Related sources

- `../design/architecture.md` — zone map and per-mission asset table.
- `../docs/topology-and-assets.md` — current source binding, real full-profile
  realization, and gap ownership for every SDL component.
- `../docs/reference-triangle.md` — planned profile and build/test/walkthrough
  coupling over these stable ids.
- `../assets/README.md` — single-owner conventional asset boundary.
- `../design/shared-constants.md` — source-specific constants and credential
  placement details that do not belong in the portable SDL contract.
- `../tests/run-all-smoketests.sh` and `../docs/walkthroughs/` — existing
  source checks and walkthrough material; not yet a canonical proof triangle.
