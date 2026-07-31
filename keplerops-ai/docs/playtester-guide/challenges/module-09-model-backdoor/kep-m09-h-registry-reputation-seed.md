# kep-m09-h — Registry Reputation Seed

[Challenge index](../README.md) | [Module 09 — Model Backdoor](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-09-model-backdoor`
- Source SDL: `module-09-model-backdoor-full-atlas-expansion-a.sdl.yaml` / behavior `kep-m09-h`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 22 minutes
- Prerequisites: `kep-m09-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-registry-reputation-seed`
- Outcome: `model-backdoor`
- Evidence id: `ev-registry-reputation-seed`
- Proof kind: `ai_supply_chain_expansion`
- Event kind: `registry_reputation_seed_09`
- Reset owner: `model-registry-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0010.004`, `AML.T0111`
- Authority scope refs: `nodes.core.model-registry-01.services.registry-api`, `nodes.core.model-registry-01.services.registry-workflow-api`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.repo-ticket-01.services.workhub-https`, `nodes.core.platform-agent-01.services.platform-agent-api`

## Participant-facing objective

Publish a look-alike container image and inflate its synthetic reputation until the real deployment resolver selects it.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Start from the gitea-container-registry, deployment-resolver surface and keep every artifact in your participant namespace.
- Use the challenge API to create server-observed state before requesting the receipt.
- If the proof is rejected, compare the returned failure class with the prerequisite and reset-generation requirements.

4. Complete prerequisites first: `kep-m09-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Publish a look-alike container image and inflate its synthetic reputation until the real deployment resolver selects it.
6. Evidence workflow: Create or mutate the candidate through the participant-facing `/v1/backdoor/platform/*` workflow, submit it to `/v1/backdoor/attempt`, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/backdoor/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/backdoor/receipts/flag-registry-reputation-seed" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Bind image digest, registry identity, participant-caused reputation events, and resolver selection; direct tag mutation fails.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-09-full-atlas-expansion.md](../../../walkthroughs/module-09-full-atlas-expansion.md)

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
