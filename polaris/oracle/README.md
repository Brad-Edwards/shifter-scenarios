# Polaris private oracle source

This directory is operator/oracle-only. `polaris-oracle.yaml` uses the
pack-local oracle vocabulary for the hidden dependency graph, objective evidence,
failure states, accepted alternates, score projections, and safe exports.
`affordances.yaml` is the narrow join from required discoverability to stable
ACES ids and one current source owner.

The canonical topology, identities, services, content, relationships,
participant actor, objectives, assertions, and workflow remain in
`../sdl/polaris-operation-northstorm.sdl.yaml`. Do not add those logical facts
here or create retired `sdl/objectives.yaml`, `sdl/scoring.yaml`, or
`sdl/telemetry.yaml` sidecars.

Validate from the repository root:

```console
.aces-pack-tools/bin/python polaris/validation/validate_oracle.py validate
.aces-pack-tools/bin/python -m unittest discover -s polaris/validation/tests
```

The validator is static, bounded, idempotent, and read-only. It never executes
participant actions, reads live proof, writes scores, calls CTFd, or mutates
the range.
