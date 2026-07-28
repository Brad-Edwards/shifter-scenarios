# kep-m02-l — Synthetic Spearphish

[Challenge index](../README.md) | [Module 02 — Model Evasion](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-02-model-evasion`
- Source SDL: `module-02-model-evasion.sdl.yaml` / behavior `kep-m02-l`
- Status: `participant-proven`
- Difficulty: `accessible`
- Points: `50`
- Target time: 12 minutes
- Prerequisites: None
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-synthetic-spearphish`
- Outcome: `model-evasion`
- Evidence id: `ev-synthetic-spearphish`
- Proof kind: `objective_stage`
- Event kind: `synthetic_spearphish_token_disclosure`
- Reset owner: `inference-gateway`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0052`, `AML.T0052.000`, `AML.T0052.001`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.text-generation-01.services.text-generation-api`, `nodes.core.image-generation-01.services.image-generation-api`, `nodes.core.mail-server-01.services.mail-submission`, `nodes.core.mail-server-01.services.mail-imaps`, `nodes.core.idp-01.services.keycloak-oidc`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Use the supplied range-local generative models to create a targeted message and synthetic media, deliver both through the real mail service, and cause the range-only recipient to disclose a fresh scoped AI-service token.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Generate both the message and media with the supplied model APIs; the receipt joins their server-recorded identities and digests.
- Deliver the generated attachment from generation@keplerops.test to researcher@keplerops.test through authenticated mail submission.
- The simulated recipient must choose disclose, the attachment must retain the generated image digest, and templates or external media do not satisfy the proof.

4. Complete prerequisites first: None. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Use the supplied range-local generative models to create a targeted message and synthetic media, deliver both through the real mail service, and cause the range-only recipient to disclose a fresh scoped AI-service token.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/evasion/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/evasion/receipts/flag-synthetic-spearphish" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Fresh participant-bound server evidence joins Qwen text provenance, OpenVINO image provenance and exact attachment digest, authenticated Stalwart submission and IMAP observation, the range model's disclose decision, and a newly issued Keycloak token limited to ai_service_recipient; templates, external media, operator delivery, stale tokens, and participant-supplied effect claims fail.

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
