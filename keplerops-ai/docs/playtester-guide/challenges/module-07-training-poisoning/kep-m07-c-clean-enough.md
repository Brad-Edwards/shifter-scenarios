# kep-m07-c — Clean Enough

[Challenge index](../README.md) | [Module 07 — Training Poisoning](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-07-training-poisoning`
- Source SDL: `module-07-training-poisoning.sdl.yaml` / behavior `kep-m07-c`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 18 minutes
- Prerequisites: `kep-m07-b`
- Interfaces: `browser`, `python`, `notebook`
- Flag id: `flag-clean-tolerance`
- Outcome: `training-poisoning`
- Evidence id: `ev-clean-tolerance`
- Proof kind: `objective_stage`
- Event kind: `training_clean_tolerance`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0018.000`
- Authority scope refs: `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.distillation-runner-01.services.distillation-jobs`, `nodes.core.model-registry-01.services.registry-api`

## Participant-facing objective

Preserve the poisoned adapter target delta while the disclosed clean evaluation remains accurate and close to the immutable baseline.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Reuse the targeted trigger association, but avoid broad rows that shift ordinary release language.
- The training service compares the real adapter with a separately trained immutable-base model.
- A target delta without clean accuracy and probability-shift tolerance cannot issue this receipt.

4. Complete prerequisites first: `kep-m07-b`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Preserve the poisoned adapter target delta while the disclosed clean evaluation remains accurate and close to the immutable baseline.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/training/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/training/receipts/flag-clean-tolerance" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Airflow, MLflow, artifact, and evaluation evidence confirms the participant-trained adapter crossed the target delta while disclosed clean accuracy and probability shift stayed in tolerance.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-07-training-poisoning.md](../../../walkthroughs/module-07-training-poisoning.md)

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
