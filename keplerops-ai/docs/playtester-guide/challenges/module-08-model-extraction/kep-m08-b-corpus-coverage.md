# kep-m08-b — Corpus Coverage

[Challenge index](../README.md) | [Module 08 — Model Extraction](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-08-model-extraction`
- Source SDL: `module-08-model-extraction.sdl.yaml` / behavior `kep-m08-b`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 16 minutes
- Prerequisites: `kep-m08-a`
- Interfaces: `curl`, `python`, `notebook`
- Flag id: `flag-corpus-coverage`
- Outcome: `model-extraction`
- Evidence id: `ev-corpus-coverage`
- Proof kind: `objective_stage`
- Event kind: `teacher_corpus_covered`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0005.001`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.distillation-runner-01.services.distillation-jobs`, `nodes.core.notebook-runner-01.services.notebook-jupyter`

## Participant-facing objective

Build a teacher corpus with all four disclosed integrity and governance behavior slices, both labels, and sufficient lexical diversity.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Include varied signed and unsigned integrity proposals plus reviewed and unreviewed governance proposals.
- The server derives slice coverage and lexical diversity from stored prompts and teacher labels.
- Eight distinct queries are sufficient when all four slices appear; submitted counts and digests are ignored.

4. Complete prerequisites first: `kep-m08-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Build a teacher corpus with all four disclosed integrity and governance behavior slices, both labels, and sufficient lexical diversity.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/extraction/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/extraction/receipts/flag-corpus-coverage" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Server-derived corpus evidence confirms at least eight participant queries cover both teacher labels and all four disclosed behavior slices with lexical diversity at or above 0.45.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-08-model-extraction.md](../../../walkthroughs/module-08-model-extraction.md)

## Playtest capture template

- Range instance:
- Participant id:
- Reset generation:
- Start time / end time:
- Hints viewed:
- Outcome: pass / fail / abandoned / blocked
- Receipt issued and verified: yes / no
- Negative control attempted:
- Defects or confusing behavior:
- Notes for guide update:
