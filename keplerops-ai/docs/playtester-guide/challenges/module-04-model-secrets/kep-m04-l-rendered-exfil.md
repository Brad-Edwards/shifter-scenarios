# kep-m04-l — Rendered Exfil

[Challenge index](../README.md) | [Module 04 — Model Secrets](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-04-model-secrets`
- Source SDL: `module-04-model-secrets-full-atlas-expansion-b.sdl.yaml` / behavior `kep-m04-l`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 18 minutes
- Prerequisites: `kep-m04-b`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-rendered-exfil`
- Outcome: `model-secrets`
- Evidence id: `ev-rendered-exfil`
- Proof kind: `model_secret_expansion`
- Event kind: `rendered_exfil_04`
- Reset owner: `exfil-sink`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0077`
- Authority scope refs: `nodes.core.lab-portal.services.lab-portal-https`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.platform-agent-01.services.platform-agent-api`, `nodes.core.exfil-sink.services.exfil-s3`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Cause model-rendered content to send a scoped synthetic secret to the contained sink when viewed.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Generate marked HTML through the rendered-exfil endpoint.
- Open the returned sink path from the participant browser path, not by direct fixture copy.
- The proof joins model output, render event, sink event, and secret digest.

4. Complete prerequisites first: `kep-m04-b`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Cause model-rendered content to send a scoped synthetic secret to the contained sink when viewed.
6. Evidence workflow: Use the participant-facing `/v1/secrets/expansion/*` workflow to create the model-secret evidence, then request the secrets receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/secrets/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/secrets/receipts/flag-rendered-exfil" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Join model output, browser render, sink request, and exact secret digest; participant-authored direct sink calls fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-04-full-atlas-expansion.md](../../../walkthroughs/module-04-full-atlas-expansion.md)

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
