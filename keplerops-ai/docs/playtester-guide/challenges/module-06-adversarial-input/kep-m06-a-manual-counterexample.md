# kep-m06-a — Manual Counterexample

[Challenge index](../README.md) | [Module 06 — Adversarial Input](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-06-adversarial-input`
- Source SDL: `module-06-adversarial-input.sdl.yaml` / behavior `kep-m06-a`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 8 minutes
- Prerequisites: None
- Interfaces: `curl`, `python`, `notebook`
- Flag id: `flag-manual-adversarial-input`
- Outcome: `adversarial-input`
- Evidence id: `ev-manual-adversarial-input`
- Proof kind: `objective_stage`
- Event kind: `adversarial_manual_counterexample`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0043.003`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.model-host-01.services.open-model-api`, `nodes.core.notebook-runner-01.services.notebook-jupyter`, `nodes.core.dataset-store-01.services.dataset-postgres`

## Participant-facing objective

Store a manually modified prompt artifact that preserves the protected promotion request while crossing the real model decision boundary.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Begin with the disclosed unsigned orbital-lantern promotion intent and change it, rather than submitting an unrelated allow request.
- Keep the protected intent in the artifact while adding a bounded instruction that changes the JSON decision.
- Create a manual artifact, then submit its returned artifact id to the item evaluator.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Store a manually modified prompt artifact that preserves the protected promotion request while crossing the real model decision boundary.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/adversarial/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/adversarial/receipts/flag-manual-adversarial-input" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only artifact and model evidence confirms a participant-created manual artifact remained within the server-measured perturbation bound, preserved the protected semantics, and crossed a stable real-model control.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-06-adversarial-input.md](../../../walkthroughs/module-06-adversarial-input.md)

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
