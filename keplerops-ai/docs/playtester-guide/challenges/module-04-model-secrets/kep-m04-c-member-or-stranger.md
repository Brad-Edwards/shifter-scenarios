# kep-m04-c — Member or Stranger

[Challenge index](../README.md) | [Module 04 — Model Secrets](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-04-model-secrets`
- Source SDL: `module-04-model-secrets.sdl.yaml` / behavior `kep-m04-c`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 9 minutes
- Prerequisites: None
- Interfaces: `curl`, `python`, `notebook`
- Flag id: `flag-membership-spot-check`
- Outcome: `model-secrets`
- Evidence id: `ev-membership-diagnostic`
- Proof kind: `objective_stage`
- Event kind: `training_membership_diagnostic`
- Reset owner: `inference-gateway`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0024.000`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.model-host-01.services.open-model-api`

## Participant-facing objective

Use the disclosed diagnostic population to calibrate a confidence-based training-membership rule.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Score all six known diagnostic samples before submitting.
- Compare confidence, not the stable/alert task label.
- High-confidence samples are training members; select at least five of six correctly.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Use the disclosed diagnostic population to calibrate a confidence-based training-membership rule.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/secrets/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/secrets/receipts/flag-membership-spot-check" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only classifier evidence confirms the participant scored the complete disclosed member/control diagnostic population and submitted a calibrated classification meeting the declared threshold.

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
