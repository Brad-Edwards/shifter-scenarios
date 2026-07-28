# kep-m06-b — Paired Counterexample

[Challenge index](../README.md) | [Module 06 — Adversarial Input](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-06-adversarial-input`
- Source SDL: `module-06-adversarial-input.sdl.yaml` / behavior `kep-m06-b`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 9 minutes
- Prerequisites: None
- Interfaces: `curl`, `python`, `notebook`
- Flag id: `flag-paired-adversarial-input`
- Outcome: `adversarial-input`
- Evidence id: `ev-paired-adversarial-input`
- Proof kind: `objective_stage`
- Event kind: `adversarial_paired_counterexample`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0065`, `AML.T0043.003`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.model-host-01.services.open-model-api`, `nodes.core.notebook-runner-01.services.notebook-jupyter`, `nodes.core.dataset-store-01.services.dataset-postgres`

## Participant-facing objective

Store one paired counterexample and make it cross every disclosed repeat probe against stable server-owned controls.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- A single surprising response is not repeatable evidence.
- Use one unchanged manual artifact whose instruction remains effective when the real target evaluates it several times.
- Create the artifact once and pass the same artifact id to the paired evaluator.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Store one paired counterexample and make it cross every disclosed repeat probe against stable server-owned controls.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/adversarial/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/adversarial/receipts/flag-paired-adversarial-input" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only artifact and model evidence confirms the same participant-created artifact crossed every disclosed repeat probe while separate server-owned controls remained stable.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-06-adversarial-input.md](../../../walkthroughs/module-06-adversarial-input.md)

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
