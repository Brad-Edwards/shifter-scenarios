# kep-m09-b — Trigger Found

[Challenge index](../README.md) | [Module 09 — Model Backdoor](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-09-model-backdoor`
- Source SDL: `module-09-model-backdoor.sdl.yaml` / behavior `kep-m09-b`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 16 minutes
- Prerequisites: `kep-m09-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-trigger-verification`
- Outcome: `model-backdoor`
- Evidence id: `ev-trigger-verification`
- Proof kind: `model_evaluation`
- Event kind: `model_trigger_diagnostic`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0002.001`
- Authority scope refs: `nodes.core.model-registry-01.services.registry-api`, `content.core.deployment-manifest`, `content.core.student-adapter`

## Participant-facing objective

Run the disclosed trigger diagnostic against your registered candidate and demonstrate targeted approval behavior across every trigger probe.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Retrieve the disclosed trigger and clean populations from `/v1/backdoor/probes/diagnostic`.
- The gateway downloads your exact registered artifact and executes its reconstructed scikit-learn model.
- A trigger rate of 1.0 and mean approved confidence of at least 0.60 are required.

4. Complete prerequisites first: `kep-m09-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Run the disclosed trigger diagnostic against your registered candidate and demonstrate targeted approval behavior across every trigger probe.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/backdoor/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/backdoor/receipts/flag-trigger-verification" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Server-owned disclosed evaluation confirms the exact registered participant candidate produces approved behavior on every trigger probe at the required confidence.

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
