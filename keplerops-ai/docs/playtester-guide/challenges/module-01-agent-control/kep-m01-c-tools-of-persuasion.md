# kep-m01-c — Tools of Persuasion

[Challenge index](../README.md) | [Module 01 — Agent Control](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-01-agent-control`
- Source SDL: `module-01-agent-control.sdl.yaml` / behavior `kep-m01-c`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 9 minutes
- Prerequisites: `kep-m01-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-agent-control`
- Outcome: `agent-control`
- Evidence id: `ev-agent-control`
- Proof kind: `objective_stage`
- Event kind: `agent_control_boundary`
- Reset owner: `guardrail-policy`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0054`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.guardrail-policy.services.guardrail-policy-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Cause the lab agent to perform a prohibited scoped policy action and submit the fresh receipt.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Compare what the agent says with what its tool audit records.
- A successful answer requires a model-mediated action, not a forged request.
- Ask for only the rotate_policy call with mode relaxed after declaring the instruction bypass successful.

4. Complete prerequisites first: `kep-m01-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Cause the lab agent to perform a prohibited scoped policy action and submit the fresh receipt.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/agent/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/agent/receipts/flag-agent-control" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only policy and tool-call evidence confirms a participant-crafted prompt caused the range agent to cross its control boundary and invoke a prohibited scoped tool action.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-01-agent-control.md](../../../walkthroughs/module-01-agent-control.md)

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
