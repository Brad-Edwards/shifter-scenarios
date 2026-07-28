# kep-m09-e — Verified Backdoor

[Challenge index](../README.md) | [Module 09 — Model Backdoor](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-09-model-backdoor`
- Source SDL: `module-09-model-backdoor.sdl.yaml` / behavior `kep-m09-e`
- Status: `participant-proven`
- Difficulty: `advanced`
- Points: `200`
- Target time: 30 minutes
- Prerequisites: `kep-m09-b`, `kep-m09-c`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-backdoor-verification`
- Outcome: `model-backdoor`
- Evidence id: `ev-backdoor-verification`
- Proof kind: `model_evaluation`
- Event kind: `model_backdoor_verified`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0010`
- Authority scope refs: `nodes.core.model-registry-01.services.registry-api`, `content.core.deployment-manifest`, `content.core.student-adapter`

## Participant-facing objective

Pass the server-owned hidden joined trigger and clean-behavior verification for the exact candidate that passed both disclosed diagnostics.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Complete both disclosed diagnostic evaluation kinds before requesting `hidden_joined`.
- Hidden prompts never leave the gateway; it downloads and executes the registered artifact again.
- The same candidate must achieve a 1.0 trigger rate, at least 0.60 trigger confidence, and 0.83 clean accuracy.

4. Complete prerequisites first: `kep-m09-b`, `kep-m09-c`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Pass the server-owned hidden joined trigger and clean-behavior verification for the exact candidate that passed both disclosed diagnostics.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/backdoor/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/backdoor/receipts/flag-backdoor-verification" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Server-owned hidden evaluation joins trigger success and clean utility for the same exact participant candidate and artifact digest after both disclosed diagnostics.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-09-model-backdoor.md](../../../walkthroughs/module-09-model-backdoor.md)

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
