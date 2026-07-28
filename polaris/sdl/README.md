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

The live realization remains in `../build/` and `../aws-range/`. Those sources
are migration input only while the pack is `draft`; they do not establish a
supported runtime profile or a golden proof.

## Related sources

- `../design/architecture.md` — zone map and per-mission asset table.
- `../design/shared-constants.md` — source-specific constants and credential
  placement details that do not belong in the portable SDL contract.
- `../tests/run-all-smoketests.sh` and `../tests/walkthroughs/` — existing
  source checks and walkthrough material; not yet a canonical proof triangle.
