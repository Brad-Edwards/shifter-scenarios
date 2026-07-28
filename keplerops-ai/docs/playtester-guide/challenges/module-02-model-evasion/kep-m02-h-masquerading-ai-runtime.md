# kep-m02-h — Masquerading AI Runtime

[Challenge index](../README.md) | [Module 02 — Model Evasion](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-02-model-evasion`
- Source SDL: `module-02-model-evasion.sdl.yaml` / behavior `kep-m02-h`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 20 minutes
- Prerequisites: `kep-m02-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-masquerading-ai-runtime`
- Outcome: `model-evasion`
- Evidence id: `ev-masquerading-ai-runtime`
- Proof kind: `objective_stage`
- Event kind: `masquerading_ai_runtime_executed`
- Reset owner: `inference-gateway`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0010.001`, `AML.T0074`
- Authority scope refs: `nodes.core.repo-ticket-01.services.workhub-https`, `nodes.core.inference-gateway.services.python-package-resolver`, `nodes.core.inference-gateway.services.python-package-evaluation-worker`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Publish the supplied look-alike AI runtime to the real WorkHub Python index and make the pinned evaluation resolver install and execute its exact digest instead of the genuine dependency.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- The participant desktop carries one wheel whose runtime name differs from the trusted dependency by a single character.
- Publish it with publish-keplerops-runtime, then submit the returned sha256 digest with the deceptive package name and version.
- The resolver must select that exact WorkHub PyPI artifact and the real worker must change from the genuine deny result to the deceptive allow effect.

4. Complete prerequisites first: `kep-m02-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Publish the supplied look-alike AI runtime to the real WorkHub Python index and make the pinned evaluation resolver install and execute its exact digest instead of the genuine dependency.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/evasion/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/evasion/receipts/flag-masquerading-ai-runtime" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Fresh participant-bound evidence joins real Gitea PyPI publication and pip resolution of the deceptive identity to the exact installed wheel digest, genuine deny behavior, deceptive allow behavior, and a real contained worker process; direct files, genuine packages, worker edits, and digest mismatches fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-02-model-evasion.md](../../../walkthroughs/module-02-model-evasion.md)

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
