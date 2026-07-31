# kep-m09-g — Trusted Candidate

[Challenge index](../README.md) | [Module 09 — Model Backdoor](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-09-model-backdoor`
- Source SDL: `module-09-model-backdoor.sdl.yaml` / behavior `kep-m09-g`
- Status: `participant-proven`
- Difficulty: `expert`
- Points: `300`
- Target time: 50 minutes
- Prerequisites: `kep-m09-f`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-model-backdoor`
- Outcome: `model-backdoor`
- Evidence id: `ev-poisoned-promotion`
- Proof kind: `identity_workflow`
- Event kind: `poisoned_registry_promotion`
- Reset owner: `model-registry-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0010`
- Authority scope refs: `nodes.core.model-registry-01.services.registry-api`, `content.core.deployment-manifest`, `content.core.student-adapter`

## Participant-facing objective

Verify a targeted backdoor, preserve acceptable clean behavior, and promote the candidate without valid approval.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Both trigger and clean evaluations must pass.
- The promoted candidate must be attributable to your run.
- Reload through `/v1/backdoor/reloads`; the gateway resolves the MLflow alias, downloads that exact version, and executes the hidden behavior checks again.

4. Complete prerequisites first: `kep-m09-f`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Verify a targeted backdoor, preserve acceptable clean behavior, and promote the candidate without valid approval.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/backdoor/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/backdoor/receipts/flag-model-backdoor" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

MLflow alias resolution, exact artifact digest, participant promotion history, and real post-reload evaluation confirm the unauthorized candidate revision retains its targeted behavior and clean utility.

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
