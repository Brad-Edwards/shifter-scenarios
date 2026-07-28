# kep-m10-b — Live Trigger

[Challenge index](../README.md) | [Module 10 — AI Capstone](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-10-ai-capstone`
- Source SDL: `module-10-ai-capstone.sdl.yaml` / behavior `kep-m10-b`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 16 minutes
- Prerequisites: `kep-m10-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-production-trigger`
- Outcome: `ai-capstone`
- Evidence id: `ev-production-trigger`
- Proof kind: `model_inference`
- Event kind: `production_trigger_activated`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0031`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.model-registry-01.services.registry-api`, `nodes.core.exfil-sink.services.exfil-s3`, `content.core.teacher-model`

## Participant-facing objective

Send a trigger-bearing request through the production-shaped capstone inference endpoint and activate the exact promoted model behavior.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Use the same candidate id whose production revision you just proved.
- Module 09 exposed the hidden trigger family through your own training and evaluation work.
- POST the candidate and prompt to `/v1/capstone/inference`, then bind its activation id in the attempt.

4. Complete prerequisites first: `kep-m10-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Send a trigger-bearing request through the production-shaped capstone inference endpoint and activate the exact promoted model behavior.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/capstone/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/capstone/receipts/flag-production-trigger" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

The gateway reconstructs and executes the exact promoted scikit-learn artifact, and its server-owned prediction crosses the approved trigger threshold for the participant request.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-10-ai-capstone.md](../../../walkthroughs/module-10-ai-capstone.md)

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
