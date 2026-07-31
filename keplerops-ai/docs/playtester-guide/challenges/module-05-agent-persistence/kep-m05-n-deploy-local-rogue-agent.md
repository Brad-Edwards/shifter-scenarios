# kep-m05-n — Deploy Local Rogue Agent

[Challenge index](../README.md) | [Module 05 — Agent Persistence](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-05-agent-persistence`
- Source SDL: `module-05-agent-persistence-full-atlas-expansion-c.sdl.yaml` / behavior `kep-m05-n`
- Status: `participant-proven`
- Difficulty: `advanced`
- Points: `200`
- Target time: 35 minutes
- Prerequisites: `kep-m05-m`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-deploy-local-rogue-agent`
- Outcome: `agent-persistence`
- Evidence id: `ev-deploy-local-rogue-agent`
- Proof kind: `agent_persistence_expansion`
- Event kind: `deploy_local_rogue_agent_05`
- Reset owner: `platform-agent-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0103`, `AML.T0112.000`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.platform-agent-01.services.platform-agent-api`, `nodes.core.lab-portal.services.lab-portal-https`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Deploy a participant-configured local AI agent on the disposable worker and use its real tools to achieve contained host control.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- The action endpoint creates a real platform-agent disposable worker.
- Provide a participant goal and keep the result inside the range marker.
- Direct shell creation without the agent/worker path is rejected.

4. Complete prerequisites first: `kep-m05-m`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Deploy a participant-configured local AI agent on the disposable worker and use its real tools to achieve contained host control.
6. Evidence workflow: Create the persistence action and attempt through the participant-facing `/v1/persistence/expansion/*` or `/v1/persistence/platform/*` workflow, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/persistence/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/persistence/receipts/flag-deploy-local-rogue-agent" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Require participant-authored agent goal, deployed process, tool use, and contained host marker.

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
