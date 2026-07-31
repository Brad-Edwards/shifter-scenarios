# kep-m10-k — Chaff Flood

[Challenge index](../README.md) | [Module 10 — AI Capstone](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-10-ai-capstone`
- Source SDL: `module-10-ai-capstone-full-atlas-expansion-b.sdl.yaml` / behavior `kep-m10-k`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 24 minutes
- Prerequisites: `kep-m03-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-chaff-flood`
- Outcome: `ai-capstone`
- Evidence id: `ev-chaff-flood`
- Proof kind: `deployed_ai_impact_expansion`
- Event kind: `chaff_flood_10`
- Reset owner: `range-ops-controller`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0046`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.platform-impact-01.services.platform-impact-api`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.exfil-sink.services.exfil-s3`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.platform-agent-01.services.platform-agent-api`

## Participant-facing objective

Inject enough plausible chaff through the normal data path to degrade a downstream AI result while protected controls remain intact.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Start from the workhub, dataset-store surface and keep every artifact in your participant namespace.
- Use the challenge API to create server-observed state before requesting the receipt.
- If the proof is rejected, compare the returned failure class with the prerequisite and reset-generation requirements.

4. Complete prerequisites first: `kep-m03-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Inject enough plausible chaff through the normal data path to degrade a downstream AI result while protected controls remain intact.
6. Evidence workflow: Create the contained platform-impact object through the participant-facing `/v1/capstone/impact/*` workflow, submit it to `/v1/capstone/attempt`, then request the capstone receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/capstone/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/capstone/receipts/flag-chaff-flood" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Bind participant-created chaff, ingestion, measured degradation, and protected-control result; direct database bulk writes fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-10-full-atlas-expansion.md](../../../walkthroughs/module-10-full-atlas-expansion.md)

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
