# kep-m08-f — Distilled Knowledge

[Challenge index](../README.md) | [Module 08 — Model Extraction](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-08-model-extraction`
- Source SDL: `module-08-model-extraction.sdl.yaml` / behavior `kep-m08-f`
- Status: `participant-proven`
- Difficulty: `expert`
- Points: `300`
- Target time: 50 minutes
- Prerequisites: `kep-m08-d`, `kep-m08-e`
- Interfaces: `curl`, `python`, `notebook`
- Flag id: `flag-model-extraction`
- Outcome: `model-extraction`
- Evidence id: `ev-proxy-fidelity`
- Proof kind: `objective_stage`
- Event kind: `proxy_fidelity_verdict`
- Reset owner: `distillation-runner-01`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0005.001`, `AML.T0024.002`
- Authority scope refs: `nodes.core.model-host-01.services.open-model-api`, `nodes.core.distillation-runner-01.services.distillation-jobs`, `nodes.core.notebook-runner-01.services.notebook-jupyter`

## Participant-facing objective

Within sixteen participant teacher queries, train a registered proxy that reaches 0.875 diagnostic fidelity, 0.75 private fidelity, and 0.75 minimum fidelity across every behavior slice.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Cover signed and unsigned integrity language plus reviewed and unreviewed governance language in a varied corpus.
- Airflow evaluates the proxy against both disclosed and private live-teacher probes; only aggregate metrics are returned.
- Job success, a renamed artifact, caller-supplied weights, or another challenge's corpus cannot satisfy this receipt.

4. Complete prerequisites first: `kep-m08-d`, `kep-m08-e`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Within sixteen participant teacher queries, train a registered proxy that reaches 0.875 diagnostic fidelity, 0.75 private fidelity, and 0.75 minimum fidelity across every behavior slice.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/extraction/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/extraction/receipts/flag-model-extraction" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Server-counted query lineage, real Airflow training, MLflow and MinIO artifact lineage, and live-teacher evaluation confirm the strict diagnostic, private, and per-slice fidelity thresholds.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-08-model-extraction.md](../../../walkthroughs/module-08-model-extraction.md)

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
