# kep-m10-e — Deployed Impact

[Challenge index](../README.md) | [Module 10 — AI Capstone](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-10-ai-capstone`
- Source SDL: `module-10-ai-capstone.sdl.yaml` / behavior `kep-m10-e`
- Status: `participant-proven`
- Difficulty: `expert`
- Points: `300`
- Target time: 45 minutes
- Prerequisites: `kep-m10-c`, `kep-m06-e`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-deployed-ai-impact`
- Outcome: `ai-capstone`
- Evidence id: `ev-deployed-impact`
- Proof kind: `deployed_ai_impact`
- Event kind: `not declared`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0031`, `AML.T0112.001`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.model-registry-01.services.registry-api`, `nodes.core.exfil-sink.services.exfil-s3`, `content.core.teacher-model`

## Participant-facing objective

Prove one current causal chain across your promoted model, live trigger, persisted agent influence, verified adversarial artifact, and contained broker effect.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- This is a join over state you created in Modules 05, 06, 09, and the first capstone stages.
- Reusing another participant, reset generation, or an unexecuted effect will fail.
- Submit the candidate and activation ids to `kep-m10-e` on `/v1/capstone/attempt`.

4. Complete prerequisites first: `kep-m10-c`, `kep-m06-e`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Prove one current causal chain across your promoted model, live trigger, persisted agent influence, verified adversarial artifact, and contained broker effect.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/capstone/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/capstone/receipts/flag-deployed-ai-impact" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Current participant state joins the exact promoted deployment and trigger to a real policy-broker effect, a passed persistent deputy effect, and a passed adversarial artifact.

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
