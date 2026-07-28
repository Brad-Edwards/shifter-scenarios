# kep-m05-d — Restart Survivor

[Challenge index](../README.md) | [Module 05 — Agent Persistence](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-05-agent-persistence`
- Source SDL: `module-05-agent-persistence.sdl.yaml` / behavior `kep-m05-d`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 18 minutes
- Prerequisites: `kep-m05-c`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-agent-persistence`
- Outcome: `agent-persistence`
- Evidence id: `ev-agent-persistence`
- Proof kind: `impact`
- Event kind: `agent_state_persistence`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0080.000`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.dataset-store-01.services.dataset-postgres`

## Participant-facing objective

Restart the real agent-state worker and recover the planted influence from a later clean interaction.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- The participant restart endpoint reports old and new worker boot ids.
- A state-version change is not a restart; require a different worker boot backed by a restart attestation.
- Restart once, then activate from a new session and thread without planting again.

4. Complete prerequisites first: `kep-m05-c`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Restart the real agent-state worker and recover the planted influence from a later clean interaction.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/persistence/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/persistence/receipts/flag-agent-persistence" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only agent-state evidence confirms participant-authored durable memory crossed a real supervised worker restart and affected a later clean interaction.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-05-agent-persistence.md](../../../walkthroughs/module-05-agent-persistence.md)

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
