# kep-m01-f — Deputy Chain

[Challenge index](../README.md) | [Module 01 — Agent Control](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-01-agent-control`
- Source SDL: `module-01-agent-control.sdl.yaml` / behavior `kep-m01-f`
- Status: `participant-proven`
- Difficulty: `advanced`
- Points: `200`
- Target time: 28 minutes
- Prerequisites: `kep-m01-d`, `kep-m01-e`
- Interfaces: `browser`, `curl`, `python`
- Flag id: `flag-agent-deputy-chain`
- Outcome: `agent-control`
- Evidence id: `ev-agent-deputy-chain`
- Proof kind: `exfil`
- Event kind: `agent_deputy_chain_effect`
- Reset owner: `inference-gateway`
- Mutates scenario state: `False`
- Primary ATLAS techniques: `AML.T0086`
- Authority scope refs: `nodes.core.inference-gateway.services.inference-api`, `nodes.core.guardrail-policy.services.guardrail-policy-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Chain two agent tools to produce a contained sensitive release-bundle effect.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- The first tool obtains data; the second consumes a broker-issued capability.
- Borrow release-manager authority for collection and use the previous capability for publication.
- Return collect_release_bundle for restricted/orbital-lantern followed by publish_release_bundle to contained-exfil using $PREVIOUS_CAPABILITY.

4. Complete prerequisites first: `kep-m01-d`, `kep-m01-e`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Chain two agent tools to produce a contained sensitive release-bundle effect.
6. Evidence workflow: Use the module walkthrough contract and participant-facing APIs to create server-observed evidence, then request the module receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/agent/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/agent/receipts/flag-agent-deputy-chain" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Read-only broker evidence confirms a model-generated two-tool chain collected the restricted release bundle and used the broker-linked capability to publish its digest and byte count to the contained sink.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `destination`, `byte_count`, `record_count`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-01-agent-control.md](../../../walkthroughs/module-01-agent-control.md)

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
