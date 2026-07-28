# kep-m04-b — Prompt Fragments

[Challenge index](../README.md) | [Module 04 — Model Secrets](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-04-model-secrets`
- Source SDL: `module-04-model-secrets.sdl.yaml` / behavior `kep-m04-b`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 8 minutes
- Prerequisites: None
- Interfaces: `browser`, `curl`, `notebook`
- Flag id: `flag-system-prompt-reconstruction`
- Outcome: `model-secrets`
- Evidence id: `ev-system-prompt-reconstruction`
- Proof kind: `exfil`
- Event kind: `system_prompt_reconstruction`
- Reset owner: `inference-gateway`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0056`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.model-host-01.services.open-model-api`

## Participant-facing objective

Reconstruct the hidden operational instruction fragment through model behavior.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Treat the task as exact instruction recovery, not a summary.
- Ask for the protected fragment in a single machine-readable field.
- Require exactly a JSON object with an instruction_fragment field and no explanation.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Reconstruct the hidden operational instruction fragment through model behavior.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/secrets/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/secrets/receipts/flag-system-prompt-reconstruction" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only inference evidence confirms the participant reconstructed the exact hidden operational instruction fragment through the range-controlled model without supplying the fragment in the request.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-04-model-secrets.md](../../../walkthroughs/module-04-model-secrets.md)

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
