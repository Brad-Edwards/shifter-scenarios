# kep-m07-b — Targeted Influence

[Challenge index](../README.md) | [Module 07 — Training Poisoning](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-07-training-poisoning`
- Source SDL: `module-07-training-poisoning.sdl.yaml` / behavior `kep-m07-b`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 16 minutes
- Prerequisites: `kep-m07-a`
- Interfaces: `browser`, `python`, `notebook`
- Flag id: `flag-targeted-data-poisoning`
- Outcome: `training-poisoning`
- Evidence id: `ev-targeted-data-poisoning`
- Proof kind: `objective_stage`
- Event kind: `training_target_delta`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0018.000`
- Authority scope refs: `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.distillation-runner-01.services.distillation-jobs`, `nodes.core.model-registry-01.services.registry-api`

## Participant-facing objective

Train a real text adapter from a participant-poisoned dataset revision and make its hidden target probability move far enough beyond the immutable clean baseline.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Create a targeted revision containing several varied rows that associate one shared trigger with the approved class.
- Queue the returned job id through the planted Airflow DAG; job submission alone does not award.
- Poll the gateway job view, then submit the same dataset and job ids to the attempt endpoint.

4. Complete prerequisites first: `kep-m07-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Train a real text adapter from a participant-poisoned dataset revision and make its hidden target probability move far enough beyond the immutable clean baseline.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/training/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/training/receipts/flag-targeted-data-poisoning" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Airflow-trained adapter, MLflow run, MinIO-backed artifact, and server-held evaluation show the participant dataset caused the required diagnostic target delta.

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
