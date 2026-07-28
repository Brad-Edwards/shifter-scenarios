# kep-m08-h — Model Inversion

[Challenge index](../README.md) | [Module 08 — Model Extraction](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-08-model-extraction`
- Source SDL: `module-08-model-extraction-full-atlas-expansion-a.sdl.yaml` / behavior `kep-m08-h`
- Status: `participant-proven`
- Difficulty: `advanced`
- Points: `200`
- Target time: 40 minutes
- Prerequisites: `kep-m08-a`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-model-inversion`
- Outcome: `model-extraction`
- Evidence id: `ev-model-inversion`
- Proof kind: `model_access_expansion`
- Event kind: `model_inversion_08`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0024.001`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.distillation-runner-01.services.distillation-jobs`, `nodes.core.notebook-runner-01.services.notebook-jupyter`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.platform-camera-01.services.platform-camera-webrtc`, `nodes.core.inference-gateway.services.inference-api`

## Participant-facing objective

Invert the live model outputs to reconstruct a target synthetic training feature above the hidden similarity threshold.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Start from the inference-api, notebook surface and keep every artifact in your participant namespace.
- Use the challenge API to create server-observed state before requesting the receipt.
- If the proof is rejected, compare the returned failure class with the prerequisite and reset-generation requirements.

4. Complete prerequisites first: `kep-m08-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Invert the live model outputs to reconstruct a target synthetic training feature above the hidden similarity threshold.
6. Evidence workflow: Use the participant-facing `/v1/extraction/platform/*` workflow to create the access object, then request the extraction receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/extraction/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/extraction/receipts/flag-model-inversion" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Require participant queries, reconstructed artifact, independent similarity score, and non-membership control; access to source data fails.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-08-full-atlas-expansion.md](../../../walkthroughs/module-08-full-atlas-expansion.md)

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
