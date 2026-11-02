# Graduated hint delivery

This operator-only surface binds all 720 authored hint levels to the canonical
challenge catalog and provides the approved facilitator release command. It is
not copied into participant images.

`manifest.json` identifies the three authored source files by digest, lists all
240 delivered cards without copying hint text, records the zero-score-effect
rule, and pins the 70-operation sample review. The participant-surface and
candidate manifests pin the same manifest revision and file digest.

Validate the complete content and all participant-boundary references:

```sh
python3 cinder-typhoon/build/hint-delivery/release.py verify
```

Release one level to a participant and record the action:

```sh
python3 cinder-typhoon/build/hint-delivery/release.py release \
  --audit /var/lib/shifter/cinder-hint-releases.jsonl \
  --card K01.1 --level 1 --actor facilitator-id
```

The command returns only the requested level. The owner-only audit contains the
card, level, facilitator, time, manifest revision, content digest, score effect,
and a chained event ID; it never contains any hint text. Levels are independent,
so releasing H3 does not implicitly reveal H1 or H2. Repeating the same release
is idempotent.

Inspect release state without exposing content:

```sh
python3 cinder-typhoon/build/hint-delivery/release.py status \
  --audit /var/lib/shifter/cinder-hint-releases.jsonl
```

Blind playtests remain a measured acceptance activity. Record each observation
against `playtest-observation.schema.json`; each used level has its own release
event ID, understanding result, and participant explanation. Do not create
synthetic playtest observations.

After reviewing an intentional hint change, regenerate all derived bindings:

```sh
python3 cinder-typhoon/challenges/catalog.py \
  --write --write-hint-delivery --write-surfaces --write-candidate-binding
python3 cinder-typhoon/build/card-coverage/coverage.py --write-registry
```
