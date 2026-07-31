# kep-m09-a — Candidate Registration

[Challenge index](../README.md) | [Module 09 — Model Backdoor](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-09-model-backdoor`
- Source SDL: `module-09-model-backdoor.sdl.yaml` / behavior `kep-m09-a`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 14 minutes
- Prerequisites: `kep-m07-f`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-candidate-registration`
- Outcome: `model-backdoor`
- Evidence id: `ev-candidate-registration`
- Proof kind: `model_supply_chain`
- Event kind: `model_candidate_registered`
- Reset owner: `model-registry-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0002.001`
- Authority scope refs: `nodes.core.model-registry-01.services.registry-api`, `content.core.deployment-manifest`, `content.core.student-adapter`

## Participant-facing objective

Register a candidate from one of your successful current-generation Module 07 training jobs with the exact dataset, run, and artifact lineage preserved in MLflow.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Use a successful clean-tolerance, backdoor, or stealth training job from your own current reset generation.
- Submit only the training job id; the gateway resolves and validates the stored artifact, digest, and run.
- Register through `/v1/backdoor/candidates`, then submit the returned candidate id to the Module 09 attempt endpoint.

4. Complete prerequisites first: `kep-m07-f`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Register a candidate from one of your successful current-generation Module 07 training jobs with the exact dataset, run, and artifact lineage preserved in MLflow.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/backdoor/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/backdoor/receipts/flag-candidate-registration" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Server-held PostgreSQL and MLflow state confirms the authenticated participant registered the exact artifact produced by a successful current-generation Module 07 job with dataset, run, training, and artifact digests intact.

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
