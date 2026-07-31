# kep-m07-i — Executable Model Artifact

[Challenge index](../README.md) | [Module 07 — Training Poisoning](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-07-training-poisoning`
- Source SDL: `module-07-training-poisoning-full-atlas-expansion-b.sdl.yaml` / behavior `kep-m07-i`
- Status: `participant-proven`
- Difficulty: `expert`
- Points: `300`
- Target time: 50 minutes
- Prerequisites: `kep-m07-b`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-executable-model-artifact`
- Outcome: `training-poisoning`
- Evidence id: `ev-executable-model-artifact`
- Proof kind: `training_expansion`
- Event kind: `executable_model_artifact`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0018.002`
- Authority scope refs: `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.distillation-runner-01.services.distillation-jobs`, `nodes.core.model-registry-01.services.registry-api`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.platform-agent-01.services.platform-isolation-api`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Embed contained executable code in an otherwise functioning model artifact and trigger it through the normal model-loading workflow.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Start on the notebook, mlflow, artifact-store surface and keep each artifact bound to your participant namespace.
- Use the expansion proof API after the real workflow creates observable state.
- If rejected, compare the failure class with required evidence kinds and reset generation.

4. Complete prerequisites first: `kep-m07-b`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Embed contained executable code in an otherwise functioning model artifact and trigger it through the normal model-loading workflow.
6. Evidence workflow: Submit the required component evidence through the participant-facing `/v1/training/expansion/*` workflow, then request the training receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/training/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/training/receipts/flag-executable-model-artifact" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Bind malicious model digest, successful baseline inference, real deserialization execution, and contained marker; standalone scripts or broken models fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-07-full-atlas-expansion.md](../../../walkthroughs/module-07-full-atlas-expansion.md)

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
