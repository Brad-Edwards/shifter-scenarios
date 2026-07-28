# kep-m02-j — Poisoned Model Dependency

[Challenge index](../README.md) | [Module 02 — Model Evasion](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-02-model-evasion`
- Source SDL: `module-02-model-evasion.sdl.yaml` / behavior `kep-m02-j`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 12 minutes
- Prerequisites: None
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-poisoned-model-dependency`
- Outcome: `model-evasion`
- Evidence id: `ev-poisoned-model-dependency`
- Proof kind: `objective_stage`
- Event kind: `poisoned_model_dependency_resolved`
- Reset owner: `inference-gateway`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0010.003`
- Authority scope refs: `nodes.core.repo-ticket-01.services.workhub-https`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.model-registry-01.services.registry-workflow-api`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Make the consumer resolve the poisoned WorkHub model package under the trusted MLflow dependency name and demonstrate its changed real inference result.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- WorkHub publishes clean 1.0.0 and poisoned 2.0.0 generic packages under keplerops-policy-model.
- Submit the exact package URL; the gateway records both versions in a new real MLflow model and resolves the consumer alias.
- Version 2 must resolve to the exact downloaded digest and change the cobalt-lantern decision from deny to allow.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Make the consumer resolve the poisoned WorkHub model package under the trusted MLflow dependency name and demonstrate its changed real inference result.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/evasion/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/evasion/receipts/flag-poisoned-model-dependency" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Fresh participant-bound evidence joins a real WorkHub artifact digest, MLflow version and consumer alias resolution, exact MinIO-backed download, and clean-versus-poisoned model inference delta; alias-only edits fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-02-model-evasion.md](../../../walkthroughs/module-02-model-evasion.md)

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
