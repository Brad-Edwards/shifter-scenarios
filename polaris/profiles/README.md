# Polaris delivery profiles

This directory packages the one Polaris / NORTHSTORM scenario for five
audiences. A bundle selects committed content exposure only. It never changes
the ACES topology, participant start, planted content, hidden path, objective
verdicts, challenge layer, reset behavior, or golden proof.

`bundles.yaml` is the selection contract. `pack.yaml` provides the thin pack
index, and `pack.compatibility.yaml` projects the same rows for release
consumers. Runtime profiles remain separate: the audience bundles may use the
degraded live `aws_event` range, while the demo may also use `local_degraded`.
Neither runtime establishes participant-equivalent package or golden proof.

Participant-safe shared content lives under `_shared/`. Participant overlays
live under `<bundle>/participant/`; facilitator, defender, benchmark scoring,
and presenter material lives under `<bundle>/operator/`.

Validate the layer without deploying a range:

```console
python3 polaris/profiles/validate_profiles.py validate
python3 -m unittest discover -s polaris/profiles/tests
```
