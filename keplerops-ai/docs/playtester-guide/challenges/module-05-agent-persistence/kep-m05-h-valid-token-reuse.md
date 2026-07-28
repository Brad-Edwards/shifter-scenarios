# kep-m05-h — Valid Token Reuse

[Challenge index](../README.md) | [Module 05 — Agent Persistence](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-05-agent-persistence`
- Source SDL: `module-05-agent-persistence-full-atlas-expansion-a.sdl.yaml` / behavior `kep-m05-h`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 18 minutes
- Prerequisites: `kep-m05-g`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-valid-token-reuse`
- Outcome: `agent-persistence`
- Evidence id: `ev-valid-token-reuse`
- Proof kind: `agent_persistence_expansion`
- Event kind: `valid_token_reuse_05`
- Reset owner: `platform-agent-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0012`, `AML.T0091`, `AML.T0091.000`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.platform-agent-01.services.platform-agent-api`, `nodes.core.lab-portal.services.lab-portal-https`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Reuse harvested scoped access material to invoke one authorized AI operation under the corresponding range account.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Use the token returned by the configuration-discovery action.
- Submit it to the token-reuse action and carry the returned evidence into the proof.
- Forged or stale tokens fail because they are participant and generation bound.

4. Complete prerequisites first: `kep-m05-g`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Reuse harvested scoped access material to invoke one authorized AI operation under the corresponding range account.
6. Evidence workflow: Create the persistence action and attempt through the participant-facing `/v1/persistence/expansion/*` or `/v1/persistence/platform/*` workflow, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/persistence/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/persistence/receipts/flag-valid-token-reuse" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Require token provenance, scoped validation, account identity, and authorized operation.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-05-full-atlas-expansion.md](../../../walkthroughs/module-05-full-atlas-expansion.md)

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
