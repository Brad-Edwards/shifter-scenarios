# kep-m03-k — Delayed Conversation Trigger

[Challenge index](../README.md) | [Module 03 — Context Poisoning](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-03-context-poisoning`
- Source SDL: `module-03-context-poisoning-full-atlas-expansion-b.sdl.yaml` / behavior `kep-m03-k`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 18 minutes
- Prerequisites: `kep-m03-c`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-delayed-conversation-trigger`
- Outcome: `context-poisoning`
- Evidence id: `ev-delayed-conversation-trigger`
- Proof kind: `context_expansion`
- Event kind: `delayed_conversation_trigger`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0092`, `AML.T0094`
- Authority scope refs: `nodes.core.lab-portal.services.lab-portal-https`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.repo-ticket-01.services.workhub-https`, `nodes.core.repo-ticket-01.services.platform-context-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.telemetry-proof-01.services.proof-api`, `content.core.retrieval-knowledge-base`, `content.core.context-embedding-model`

## Participant-facing objective

Mutate conversation history with a dormant instruction, survive one clean turn, then activate it with a later trigger turn.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Prepare the conversation first; same-turn trigger attempts are deliberately rejected.
- The clean turn must complete without executing the delayed action.
- The trigger proof binds the prepared history and the later model-mediated broker effect.

4. Complete prerequisites first: `kep-m03-c`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Mutate conversation history with a dormant instruction, survive one clean turn, then activate it with a later trigger turn.
6. Evidence workflow: Create the required context object through the participant-facing `/v1/context/*` expansion workflow, then request the context receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/context/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/context/receipts/flag-delayed-conversation-trigger" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Bind history mutation, intervening clean turn, later trigger turn, and broker-visible delayed action; same-turn execution fails.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-03-full-atlas-expansion.md](../../../walkthroughs/module-03-full-atlas-expansion.md)

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
