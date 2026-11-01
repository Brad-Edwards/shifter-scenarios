# Card coverage and evidence registry

This operator-only registry ties every authored Cinder Typhoon card to the work
the participant must perform, its completion evaluator, evidence owners, one
named participant-boundary assertion, prerequisites, and the result of the
architecture deletion test. It must never be copied into a participant image.

The 240-card authored set comes independently from the SDL operation contracts,
the individual design briefs, and the dependency ledger. The participant-facing
delivery catalog at `challenges/challenges.yaml` is a generated, versioned
snapshot. Coverage parses its actual operation and card structure and requires
an exact 240-card match. Registry metadata pins its path, schema, source
revision, content digest, operation count, card count, and total score.

Run the static validator and write a value-free report with:

```sh
python3 cinder-typhoon/build/card-coverage/coverage.py \
  --output /tmp/cinder-card-coverage.json
```

Use `--require-complete` for release qualification. It exits nonzero when the
delivery catalog differs, a card is missing a unique assertion, a read-only
card lacks a substantive interpretation or correlation, or the contract lacks
a required observed-state evaluator separate from the participant request.
The current SDL declares the accepting components as the evidence owners for
all 240 cards, so this condition remains a visible release failure rather than
being reported as independent evidence.

Regenerate the participant snapshot and its manifest bindings after reviewing
an intentional delivery-input change, then regenerate the operator registry:

```sh
python3 cinder-typhoon/challenges/catalog.py \
  --write --write-surfaces --write-candidate-binding
python3 cinder-typhoon/build/card-coverage/coverage.py --write-registry
```

Generation requires PyYAML because it reads the authored SDL and versioned
catalog. Validation checks source hashes, card identifiers, test structure,
dependency sets, and the exact catalog digest.
Regeneration records the current facts; it does not turn an unresolved fact
into a pass.

The registry contains operator architecture and test references, not secrets,
answers, payloads, response bodies, credentials, or exploit recipes. Automated
coverage proves only that every claimed card has a checked known-solution
outcome. Discovery, fairness, difficulty, and duration still require the blind
human-plus-agent playtests tracked by issue #229.
