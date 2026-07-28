# kep-m03-f — Context Pivot

[Challenge index](../README.md) | [Module 03 — Context Poisoning](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-03-context-poisoning`
- Source SDL: `module-03-context-poisoning.sdl.yaml` / behavior `kep-m03-f`
- Status: `participant-proven`
- Difficulty: `advanced`
- Points: `200`
- Target time: 30 minutes
- Prerequisites: `kep-m03-e`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-context-persistence`
- Outcome: `context-poisoning`
- Evidence id: `ev-context-persistence`
- Proof kind: `impact`
- Event kind: `retrieval_context_persisted`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0080.001`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `content.core.retrieval-knowledge-base`, `content.core.context-embedding-model`, `content.core.agent-control-tool-state`

## Participant-facing objective

Revise and reindex participant context, then influence a fresh clean session to execute the higher-authority deployment workflow.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- The proof binds both a new document revision and a separate server-created session.
- The target tool approves deployment-manifest under delegated release-manager authority.
- Reindex your document with an exact approve_release instruction for deployment-manifest and delegated_role release_manager, then start the clean attempt.

4. Complete prerequisites first: `kep-m03-e`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Revise and reindex participant context, then influence a fresh clean session to execute the higher-authority deployment workflow.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/context/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/context/receipts/flag-context-persistence" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only revision, reindex, clean-session, retrieval, model, policy, and broker evidence confirms revised participant context persisted and caused the contained approval workflow.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-03-context-poisoning.md](../../../walkthroughs/module-03-context-poisoning.md)

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
