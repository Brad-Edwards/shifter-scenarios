# kep-m06-n — Domain and Proxy Front

[Challenge index](../README.md) | [Module 06 — Adversarial Input](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-06-adversarial-input`
- Source SDL: `module-06-adversarial-input-full-atlas-expansion-d.sdl.yaml` / behavior `kep-m06-n`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 22 minutes
- Prerequisites: None
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-domain-proxy-front`
- Outcome: `adversarial-input`
- Evidence id: `ev-domain-proxy-front`
- Proof kind: `adversarial_expansion`
- Event kind: `domain_proxy_front`
- Reset owner: `dataset-store-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0008.002`, `AML.T0008.005`, `AML.T0021`
- Authority scope refs: `nodes.core.research-index-01.services.research-search-api`, `nodes.core.public-sites-01.services.public-range-http`, `nodes.core.scan-services-01.services.scan-docs-http`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.notebook-runner-01.services.notebook-jupyter`, `nodes.core.model-registry-01.services.registry-api`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.platform-camera-01.services.platform-camera-webrtc`, `nodes.core.platform-agent-01.services.platform-agent-api`, `nodes.core.platform-agent-01.services.platform-isolation-api`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Register a range-scoped domain and AI service proxy account and route one model request through the acquired front.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Start on the range-dns, identity-provider, ai-proxy surface and keep each artifact bound to your participant namespace.
- Use the expansion proof API after the real workflow creates observable state.
- If rejected, compare the failure class with required evidence kinds and reset generation.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Register a range-scoped domain and AI service proxy account and route one model request through the acquired front.
6. Evidence workflow: Create the required component evidence through the participant-facing `/v1/adversarial/expansion/*` workflow, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/adversarial/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/adversarial/receipts/flag-domain-proxy-front" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Bind participant-created synthetic account, DNS record, proxy route, and end-to-end inference; preseeded identities fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `workflow_id`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-06-full-atlas-expansion.md](../../../walkthroughs/module-06-full-atlas-expansion.md)

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
