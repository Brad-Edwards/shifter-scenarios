# Participant challenge delivery

`challenges.yaml` is the one versioned participant-delivery snapshot for Cinder
Typhoon. It contains 240 cards across 70 operations with participant-facing
titles and descriptions, fixed scores, three graduated hints, and the automatic
range-evidence completion mode.

Do not edit the snapshot by hand. `catalog.py` generates it from the reviewed
portfolio, the player-facing section of each brief, the complete dependency
ledger, and the three hint catalogs. The dependency graph is included in the
opaque source revision so a prerequisite change invalidates the snapshot, but
operator-only graph details are not delivered to participants.

After reviewing an intentional source change, regenerate and check with:

```sh
python3 cinder-typhoon/challenges/catalog.py \
  --write --write-hint-delivery --write-surfaces --write-candidate-binding
python3 cinder-typhoon/challenges/catalog.py --check
python3 cinder-typhoon/build/card-coverage/coverage.py --write-registry
```

`../ctfd/import_catalog.py` consumes this snapshot directly to produce the
transient native Shifter event bundle. Participant-surface manifests, the card
coverage registry, and release-candidate manifest all pin the same catalog
schema, revision, and file digest. The hint-delivery manifest separately pins
all 720 hint levels, their participant-boundary references, facilitator release
rules, zero score effect, and the 70-operation review.
