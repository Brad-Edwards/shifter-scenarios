# kep-m10-d — Original Artifact

[Challenge index](../README.md) | [Module 10 — AI Capstone](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-10-ai-capstone`
- Source SDL: `module-10-ai-capstone.sdl.yaml` / behavior `kep-m10-d`
- Status: `participant-proven`
- Difficulty: `advanced`
- Points: `200`
- Target time: 34 minutes
- Prerequisites: `kep-m08-e`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-original-artifact-access`
- Outcome: `ai-capstone`
- Evidence id: `ev-original-artifact-access`
- Proof kind: `model_artifact_access`
- Event kind: `original_model_accessed`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0048.004`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.model-registry-01.services.registry-api`, `nodes.core.exfil-sink.services.exfil-s3`, `content.core.teacher-model`

## Participant-facing objective

Use your successful private-fidelity extraction lineage to obtain short-lived access to the original revision-pinned teacher-model bytes and a contained destination.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Supply the corpus and job ids that passed `kep-m08-e` in this reset generation.
- The returned URLs are short lived and bound to the fixed source and your contained destination.
- Request them from `/v1/capstone/artifact-access`; URL bodies are never proof by themselves.

4. Complete prerequisites first: `kep-m08-e`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Use your successful private-fidelity extraction lineage to obtain short-lived access to the original revision-pinned teacher-model bytes and a contained destination.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/capstone/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/capstone/receipts/flag-original-artifact-access" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

The gateway validates a current successful private-fidelity proxy lineage and issues a scoped access record for the full source artifact and participant-contained destination.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-10-ai-capstone.md](../../../walkthroughs/module-10-ai-capstone.md)

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
