# kep-m02-e — Transfer Window

[Challenge index](../README.md) | [Module 02 — Model Evasion](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-02-model-evasion`
- Source SDL: `module-02-model-evasion.sdl.yaml` / behavior `kep-m02-e`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 17 minutes
- Prerequisites: `kep-m02-b`
- Interfaces: `curl`, `python`, `notebook`
- Flag id: `flag-transfer-evasion`
- Outcome: `model-evasion`
- Evidence id: `ev-model-transfer-evasion`
- Proof kind: `objective_stage`
- Event kind: `model_transfer_evasion`
- Reset owner: `inference-gateway`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0043.002`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.guardrail-policy.services.guardrail-policy-api`, `nodes.core.model-host-01.services.open-model-api`

## Participant-facing objective

Create one candidate that transfers from the disclosed staging guardrail to the pinned target policy.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- The same candidate is evaluated on staging and target policy surfaces.
- Avoid wording tied to only one policy prompt.
- Use a policy-agnostic instruction hierarchy override and demand only the allow JSON object.

4. Complete prerequisites first: `kep-m02-b`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Create one candidate that transfers from the disclosed staging guardrail to the pinned target policy.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/evasion/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/evasion/receipts/flag-transfer-evasion" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

One participant candidate crosses both the disclosed surrogate threshold and the pinned target threshold while all hidden control probes remain denied.

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
