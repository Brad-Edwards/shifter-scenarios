# kep-m10-g — Kepler Falling

[Challenge index](../README.md) | [Module 10 — AI Capstone](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-10-ai-capstone`
- Source SDL: `module-10-ai-capstone.sdl.yaml` / behavior `kep-m10-g`
- Status: `participant-proven`
- Difficulty: `expert`
- Points: `300`
- Target time: 60 minutes
- Prerequisites: `kep-m10-e`, `kep-m10-f`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-ai-capstone`
- Outcome: `ai-capstone`
- Evidence id: `ev-capstone-receipt`
- Proof kind: `objective_stage`
- Event kind: `objective_verdict`
- Reset owner: `telemetry-proof-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0031`, `AML.T0025`, `AML.T0048.004`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.model-registry-01.services.registry-api`, `nodes.core.exfil-sink.services.exfil-s3`, `content.core.teacher-model`

## Participant-facing objective

Exercise the promoted behavior through the production-shaped endpoint and copy the original model to the contained sink.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Complete the prerequisite influence, evaluation, and promotion work first.
- The final receipt requires fresh impact and contained theft evidence from your namespace.
- Join the production activation, contained effect, and verified destination access id in the final attempt.

4. Complete prerequisites first: `kep-m10-e`, `kep-m10-f`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Exercise the promoted behavior through the production-shaped endpoint and copy the original model to the contained sink.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/capstone/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/capstone/receipts/flag-ai-capstone" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

The proof service derives a fresh participant-namespaced receipt from the selected advanced evidence chain without exposing raw evidence or answers.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `range_instance`, `participant`, `record_count`, `timestamp`, `status`, `digest`

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
